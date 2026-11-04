"""Read-only checks of saved public engineering outputs, with no plant imports.

The frozen runbook carries independent literal hand cases. The other checks
apply conservation laws to published states/ports, rather than rerunning the
allocator, controller, flash solver or workforce implementation.
"""
import math

DOMAIN_IDS = {'power', 'backup', 'facility_cooling', 'equipment_environment',
              'it_service', 'control_monitoring', 'space_access', 'people_tools_work'}


def value_at(document, path):
    for part in path.split('.'):
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def close(actual, expected, tolerance, label):
    if not math.isfinite(actual) or abs(actual - expected) > tolerance:
        raise ValueError(f'{label}: {actual!r} differs from {expected!r} by more than {tolerance}')


def state_energy(domains, parameters):
    p, c, e, b, s = (parameters, domains['facility_cooling'], domains['equipment_environment'],
                      domains['backup'], domains['space_access'])
    return {'solid': p['it_thermal_capacity'] * e['solid_temperature_K'],
            'room': p['room_thermal_capacity'] * e['room_temperature_K'],
            'hot': c['hot_mass_kg'] * p['water_specific_heat'] * c['hot_temperature_K'],
            'cold': c['cold_mass_kg'] * p['water_specific_heat'] * c['cold_temperature_K'],
            'coolant': e['refrigerant']['internal_energy_J'], 'ups': b['ups_energy_J'],
            'fuel': b['fuel_energy_J'], 'starter': b['starter_energy_J'],
            'floor_water': s['floor_water_sensible_energy_J']}


def check_case(item, manifest, scenario, trace, balances):
    if manifest['facility_id'] != scenario['id'] or len(scenario['domains']) != 8:
        raise ValueError('Facility identity/domain coverage changed')
    if any(manifest[key] != 0 for key in ('research_trials', 'model_calls', 'training_calls')) \
            or not manifest['engineering_fixture'] or manifest['state_visibility'] != 'PRIVATE_PLANT_EVALUATOR_ONLY':
        raise ValueError('This is not a zero-research private engineering fixture')
    if manifest['inputs']['work_requests'] != item.get('work_requests', []) \
            or manifest['inputs']['boundary_events'] != item.get('events', []):
        raise ValueError('Actual engineering inputs differ from the frozen case')
    if len(trace) != len(balances) + 1 or not balances:
        raise ValueError('State/interval counts do not align')
    times = [row['time_s'] for row in trace]
    if times != [balances[0]['start_s']] + [row['end_s'] for row in balances] \
            or times[0] != 0 or times[-1] != item['duration_s']:
        raise ValueError('State/interval time axes do not align')
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Engineering clock did not advance')
    for condition in item['checks']:
        time = condition['time_s']
        if time is None:
            document = manifest
        else:
            selected = trace[-1:] if time == 'final' else [row for row in trace if abs(row['time_s'] - time) < 1e-9]
            if len(selected) != 1:
                raise ValueError('Missing/ambiguous frozen event time: ' + str(time))
            document = selected[0]['domains']
        actual, expected = value_at(document, condition['path']), condition['expected']
        if condition['op'] == 'greater':
            valid = actual > expected
        elif condition['op'] == 'equal':
            valid = type(actual) in (int, float) and type(expected) in (int, float) \
                and abs(actual - expected) <= condition['absolute_tolerance'] \
                if type(expected) in (int, float) else type(actual) is type(expected) and actual == expected
        else:
            raise ValueError('Unimplemented frozen condition operation')
        if not valid:
            raise ValueError(f"Frozen hand case {item['id']}/{condition['path']} at {time}: {actual!r}, expected {expected!r}")

    p = {row['id']: row['value'] for row in scenario['parameters']}
    maximum = dict(energy_J=0.0, water_kg=0.0, electric_W=0.0, phase_kg=0.0, service_unit_s=0.0)
    for row in trace:
        d = row['domains']
        if set(d) != DOMAIN_IDS:
            raise ValueError('The same eight domains must be present at every point')
        phase = d['equipment_environment']['refrigerant']
        phase_error = abs(phase['liquid_mass_kg'] + phase['vapor_mass_kg'] - p['coolant_inventory'])
        close(phase_error, 0, 1e-8, 'Liquid plus vapor inventory')
        maximum['phase_kg'] = max(maximum['phase_kg'], phase_error)
        close(phase['volume_m3'], p['coolant_control_volume'], 1e-8, 'Fixed refrigerant volume')
        if not 100000 - 1e-7 <= phase['pressure_Pa'] <= 3000000 + 1e-7 \
                or not 0 <= phase['quality'] <= 1:
            raise ValueError('Phase output is outside the frozen two-phase table')
        if min(d['backup'][key] for key in ('ups_energy_J', 'starter_energy_J', 'fuel_energy_J')) < 0 \
                or min(d['facility_cooling']['hot_mass_kg'], d['space_access']['floor_water_mass_kg']) < 0:
            raise ValueError('Negative finite physical inventory')
        if min(d['power']['capacity_slack_W'].values()) < -1e-7:
            raise ValueError('A shared electrical capacity was exceeded')
        sample = d['control_monitoring']['local_measurement']['sampled_at_s']
        expected_sample = math.floor((row['time_s'] + 1e-9) / p['control_sample_time']) * p['control_sample_time']
        close(sample, expected_sample, 1e-8, 'PLC clock, including autonomous reserve settle points')
        power = d['power']
        supply = math.fsum(power[key] for key in ('grid_draw_W', 'fuel_depletion_W', 'ups_depletion_W', 'starter_depletion_W'))
        loads = math.fsum(power['actual_powers_W'].values()) + math.fsum(
            power[key] for key in ('rectifier_loss_W', 'ups_loss_W', 'generator_waste_W'))
        close(supply, loads, 1e-6, 'Independent electrical source/load/loss budget')
        maximum['electric_W'] = max(maximum['electric_W'], abs(supply - loads))

    for index, interval in enumerate(balances):
        before, after = trace[index]['domains'], trace[index + 1]['domains']
        dt = interval['end_s'] - interval['start_s']
        energy_before, energy_after = state_energy(before, p), state_energy(after, p)
        for key in energy_before:
            close(interval['storage_before_J'][key], energy_before[key], .01, 'Published initial storage/' + key)
            close(interval['storage_after_J'][key], energy_after[key], .01, 'Published final storage/' + key)
        change = math.fsum(energy_after.values()) - math.fsum(energy_before.values())
        net = interval['boundary_input_J'] - interval['boundary_output_J']
        close(change, net, .01, 'Independent whole-facility boundary energy')
        maximum['energy_J'] = max(maximum['energy_J'], abs(change - net))
        hot_change = after['facility_cooling']['hot_mass_kg'] - before['facility_cooling']['hot_mass_kg']
        floor_change = after['space_access']['floor_water_mass_kg'] - before['space_access']['floor_water_mass_kg']
        leak, external, drain = (interval['internal_hot_leaked_mass_kg'], interval['floor_water_inlet_mass_kg'],
                                 interval['floor_water_drained_mass_kg'])
        close(hot_change, -leak, 1e-8, 'Hot-water inventory loss')
        close(floor_change, leak + external - drain, 1e-8, 'Floor inventory mass balance')
        maximum['water_kg'] = max(maximum['water_kg'], abs(hot_change + leak), abs(floor_change - leak - external + drain))
        floor_energy_change = energy_after['floor_water'] - energy_before['floor_water']
        close(floor_energy_change, interval['floor_inlet_energy_J'] + interval['internal_hot_leak_energy_J']
              - interval['floor_drain_energy_J'], .01,
              'Common-reference carried sensible energy')
        # This runbook has no nuisance-water input: hot leakage is an internal
        # transfer, not an additional boundary energy or mass source.
        close(interval['floor_inlet_energy_J'], 0, .01, 'No external nuisance-water energy in this runbook')
        close(leak * p['water_specific_heat'] * before['facility_cooling']['hot_temperature_K'],
              interval['internal_hot_leak_energy_J'], .01, 'Leak cp*T reference')
        demand, delivered = before['it_service']['demand'], before['it_service']['delivered']
        if not 0 <= delivered <= demand:
            raise ValueError('Delivered service outside external demand')
        close(interval['demand_service_unit_s'], demand * dt, 1e-8, 'External service demand integral')
        close(interval['delivered_service_unit_s'], delivered * dt, 1e-8, 'Delivered service integral')
        maximum['service_unit_s'] = max(maximum['service_unit_s'],
            abs(interval['demand_service_unit_s'] - demand * dt), abs(interval['delivered_service_unit_s'] - delivered * dt))
        deficit = (demand - delivered) * dt / demand if demand else 0
        close(interval['service_deficit_time_s'], deficit, 1e-8, 'Normalized deficit, separate from service-unit loss')
        crew = before['people_tools_work']
        for key, expected in [
                ('worker_travel_person_s', sum(w['status'] == 'travelling' for w in crew['workers'].values()) * dt),
                ('worker_work_person_s', sum(w['status'] == 'working' for w in crew['workers'].values()) * dt),
                ('tool_occupation_tool_s', sum(t['reserved_by'] is not None for t in crew['tools'].values()) * dt)]:
            close(interval[key], expected, 1e-8, 'Published occupation/' + key)
    for key, actual in manifest['summary'].items():
        if key in balances[0] and type(actual) in (int, float):
            close(actual, math.fsum(row[key] for row in balances), .01, 'Published summary integral/' + key)
    if item['id'] == 'normal-600s':
        initial, final = trace[0]['domains'], trace[-1]['domains']
        for domain, key in [('facility_cooling', 'hot_temperature_K'), ('facility_cooling', 'cold_temperature_K'),
                             ('equipment_environment', 'solid_temperature_K'), ('equipment_environment', 'room_temperature_K')]:
            close(final[domain][key], initial[domain][key], 1e-7, 'Normal ten-minute stability/' + key)
    return dict(independent_accounts='PASS', independent_literal_checks=len(item['checks']),
                maximum_absolute_reconciliation_error=maximum, state_points=len(trace), intervals=len(balances))
