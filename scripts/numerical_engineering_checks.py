"""Independent saved-byte analysis; imports neither plant nor property solver."""
from bisect import bisect_right
import json
import math
import zipfile

from coupled_engineering_checks import DOMAIN_IDS, close, state_energy, value_at

SERIES = {
    'solid_K': 'equipment_environment.solid_temperature_K',
    'room_K': 'equipment_environment.room_temperature_K',
    'hot_K': 'facility_cooling.hot_temperature_K',
    'cold_K': 'facility_cooling.cold_temperature_K',
    'phase_K': 'equipment_environment.refrigerant.temperature_K',
    'pressure_Pa': 'equipment_environment.refrigerant.pressure_Pa',
    'condenser_W': 'facility_cooling.condenser_heat_W',
    'plate_W': 'facility_cooling.plate_hx_heat_W',
    'solid_phase_W': 'equipment_environment.solid_coolant_heat_W',
}


def member_identities(path):
    from hashlib import sha256
    with zipfile.ZipFile(path) as archive:
        return {name: dict(sha256=sha256(content).hexdigest(), bytes=len(content),
                           records=len(content.splitlines()) if name.endswith('.jsonl') else 1)
                for name in archive.namelist() for content in [archive.read(name)]}


def read_archive(path):
    with zipfile.ZipFile(path) as archive:
        if sorted(archive.namelist()) != ['balances.jsonl', 'private-state.jsonl', 'run.json', 'scenario.json']:
            raise ValueError('Archive must preserve exactly the four original public save_run files')
        raw = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(raw['run.json'])
    from hashlib import sha256
    for name, record in manifest['artifacts'].items():
        if sha256(raw[name]).hexdigest() != record['sha256']:
            raise ValueError('Archived public manifest hash mismatch: ' + name)
        if name.endswith('.jsonl') and len(raw[name].splitlines()) != record['records']:
            raise ValueError('Archived public record count mismatch: ' + name)
    return (manifest, json.loads(raw['scenario.json']),
            [json.loads(line) for line in raw['private-state.jsonl'].splitlines()],
            [json.loads(line) for line in raw['balances.jsonl'].splitlines()])


def inspect_run(item, manifest, scenario, trace, balances):
    p = {row['id']: row['value'] for row in scenario['parameters']}
    if manifest['inputs']['boundary_events'] != item['events'] or manifest['inputs']['work_requests'] != item['work_requests']:
        raise ValueError('Frozen inputs differ from actual inputs')
    if len(trace) != len(balances) + 1 or not balances:
        raise ValueError('State and interval counts differ')
    if manifest['time_coordinate_convention']['version'] != 'aegisdc-binary64-time-v1':
        raise ValueError('Missing numerical time convention')
    for key in ('research_trials', 'model_calls', 'training_calls'):
        if manifest[key] != 0:
            raise ValueError('An engineering fixture spent a research budget')
    maximum_energy, maximum_mass, maximum_sample = 0., 0., 0.
    for index, row in enumerate(trace):
        d = row['domains']
        if set(d) != DOMAIN_IDS:
            raise ValueError('Eight-domain facility scope changed')
        ref = d['equipment_environment']['refrigerant']
        close(ref['liquid_mass_kg'] + ref['vapor_mass_kg'], p['coolant_inventory'], 1e-8, 'closed phase mass')
        if not 0 <= ref['quality'] <= 1 or not 100000 <= ref['pressure_Pa'] <= 3000000:
            raise ValueError('Physical phase domain was extended')
        sampled = d['control_monitoring']['local_measurement']['sampled_at_s']
        tick = round(sampled / p['control_sample_time']) * p['control_sample_time']
        maximum_sample = max(maximum_sample, abs(sampled - tick))
        if index == len(balances):
            continue
        interval, after = balances[index], trace[index + 1]['domains']
        dt = interval['end_s'] - interval['start_s']
        if interval['start_s'] != row['time_s'] or interval['end_s'] != trace[index + 1]['time_s'] or dt <= 0:
            raise ValueError('Nonpositive or misaligned time interval')
        change = math.fsum(state_energy(after, p).values()) - math.fsum(state_energy(d, p).values())
        energy_error = change - interval['boundary_input_J'] + interval['boundary_output_J']
        close(energy_error, 0, .01, 'independent energy dimensions: J = W*s')
        maximum_energy = max(maximum_energy, abs(energy_error))
        floor_change = after['space_access']['floor_water_mass_kg'] - d['space_access']['floor_water_mass_kg']
        water_error = floor_change - interval['floor_water_inlet_mass_kg'] - interval['internal_hot_leaked_mass_kg'] + interval['floor_water_drained_mass_kg']
        close(water_error, 0, 1e-8, 'independent mass dimensions: kg = kg/s*s')
        maximum_mass = max(maximum_mass, abs(water_error))
        service = d['it_service']
        close(interval['demand_service_unit_s'], service['demand'] * dt, 1e-8, 'external demand')
        close(interval['service_deficit_time_s'], (1 - service['delivered'] / service['demand']) * dt if service['demand'] else 0,
              1e-8, 'normalized deficit has unit seconds')
    if maximum_sample > 8 * math.ulp(max(1., item['duration_s'])):
        raise ValueError('Sample epoch drifted from the zero-anchored clock')
    checkpoint_matches = []
    for check in item['checks']:
        when = check['time_s']
        if when is None:
            selected = manifest
        elif when == 'final':
            selected = trace[-1]['domains']
        else:
            anchor = check.get('event_anchor')
            exact = [row for row in trace if row['time_s'] == when]
            if anchor:
                matched_events = [row for row in manifest['events']
                                  if all(row.get(key) == value for key, value in anchor.items())
                                  and abs(row.get('applied_at_s', row['time_s']) - when) <= 1e-8]
                if len(matched_events) != 1:
                    raise ValueError('Missing/ambiguous explicitly anchored hand checkpoint')
                matched_time = matched_events[0].get('applied_at_s', matched_events[0]['time_s'])
                # Do not sweep a genuinely distinct nearby event into a
                # checkpoint window. The identity-specific right limit is
                # evaluated at the ACTUAL event, never claimed at target t.
                for event in manifest['events']:
                    event_time = event.get('applied_at_s', event['time_s'])
                    if abs(event_time - when) <= 1e-8 and abs(event_time - matched_time) > 8 * max(math.ulp(event_time), math.ulp(matched_time)):
                        raise ValueError('Distinct event makes the anchored checkpoint window ambiguous')
                row = next(row for row in trace if row['time_s'] == matched_time)
                checkpoint_matches.append(dict(path=check['path'], target_time_s=when,
                    matched_row_time_s=matched_time, actual_applied_event_time_s=matched_time,
                    timestamp_error_s=matched_time - when, basis='RIGHT_LIMIT_AT_IDENTIFIED_ACTUAL_EVENT', event_anchor=anchor))
            elif len(exact) == 1:
                row = exact[0]
                checkpoint_matches.append(dict(path=check['path'], target_time_s=when,
                    matched_row_time_s=when, actual_applied_event_time_s=None,
                    timestamp_error_s=0, basis='EXACT_SAVED_TIME'))
            else:
                raise ValueError('No exact unanchored hand checkpoint; do not borrow a future state')
            selected = row['domains']
        actual, expected = value_at(selected, check['path']), check['expected']
        if type(expected) in (int, float):
            close(actual, expected, check['absolute_tolerance'], 'independent accepted hand case/' + check['path'])
        elif actual != expected:
            raise ValueError('Hand-case discrete expectation differs')
    metrics = dict(service_deficit_time_s=manifest['summary']['service_deficit_time_s'],
        unserved_service_unit_s=manifest['summary']['demand_service_unit_s'] - manifest['summary']['delivered_service_unit_s'])
    for name, domain, field in [('ups_supply_s', 'power', 'ups_protected_output_W'),
                              ('generator_supply_s', 'power', 'generator_output_W'),
                              ('backup_fan_s', 'power', 'actual_powers_W.backup_fan')]:
        metrics[name] = math.fsum((b['end_s'] - b['start_s']) for row, b in zip(trace, balances)
                                 if value_at(row['domains'][domain], field) > 0)
    for key in ('worker_travel_person_s', 'worker_work_person_s', 'tool_occupation_tool_s'):
        metrics[key] = manifest['summary'][key]
    if item['id'] == 'isolated-room':
        analytic = [abs(row['domains']['equipment_environment']['room_temperature_K']
                        - (293.15 + 10 * math.exp(-row['time_s'] / 10))) for row in trace]
        metrics['analytic_max_temperature_error_K'] = max(analytic)
        metrics['analytic_terminal_temperature_error_K'] = analytic[-1]
    if item['id'] == 'normal':
        for path in SERIES.values():
            close(value_at(trace[-1]['domains'], path), value_at(trace[0]['domains'], path), 1e-6, 'normal stationary state')
    if item['id'] == 'zero-flow':
        start, end = [row['applied_at_s'] for row in manifest['events']
                      if row.get('parameter_id') == 'internal_valve_opening']
        for row in trace:
            if start <= row['time_s'] < end:
                for key in ('internal_mass_flow_kg_s', 'condenser_heat_W', 'plate_hx_heat_W'):
                    close(row['domains']['facility_cooling'][key], 0, 0, 'zero-flow signed transfer')
    if item['id'] == 'outage':
        close(metrics['service_deficit_time_s'], 3.5, 1e-9, 'independent outage interval')
    events = []
    for event in manifest['events']:
        if event['kind'] == 'reserve_transition' or event['kind'].endswith('_depleted') or event['kind'] in ('floor_access_closed', 'floor_access_opened', 'room_work_access_closed', 'room_work_access_opened'):
            events.append(dict(identity=[event['kind'], event.get('actor'), event.get('mode')], time_s=event['time_s']))
    previous = None
    for row in trace:
        c = row['domains']['control_monitoring']
        state = (c['mode'], c['compute_permitted'], c['pump_speed_command'])
        if state != previous:
            events.append(dict(identity=['PLC', *state], time_s=row['time_s']))
            previous = state
    return dict(metrics=metrics, events=events, times=[row['time_s'] for row in trace],
        series={key: [value_at(row['domains'], path) for row in trace] for key, path in SERIES.items()},
        observed_ranges={key: [min(value_at(row['domains'], path) for row in trace),
                               max(value_at(row['domains'], path) for row in trace)] for key, path in SERIES.items()},
        observed_quality_range=[min(row['domains']['equipment_environment']['refrigerant']['quality'] for row in trace),
                                max(row['domains']['equipment_environment']['refrigerant']['quality'] for row in trace)],
        checks=dict(energy_absolute_J=maximum_energy, mass_absolute_kg=maximum_mass, sample_epoch_error_s=maximum_sample),
        state_points=len(trace), intervals=len(balances), independent_literal_checks=len(item['checks']),
        literal_checkpoint_matches=checkpoint_matches)


def sample(times, values, when, *, hold=False):
    index = bisect_right(times, when + 8 * math.ulp(when)) - 1
    if hold or index >= len(times) - 1 or abs(times[index] - when) <= 8 * max(math.ulp(when), math.ulp(times[index])):
        return values[index]
    fraction = (when - times[index]) / (times[index + 1] - times[index])
    return values[index] + fraction * (values[index + 1] - values[index])


def compare(actual, reference, limits, *, factor=1):
    times = sorted(set(actual['times'] + reference['times']))
    errors = {key: max(abs(sample(actual['times'], values, t, hold=key.endswith('_W'))
                         - sample(reference['times'], reference['series'][key], t, hold=key.endswith('_W')))
                      for t in times) for key, values in actual['series'].items()}
    metric_errors = {key: abs(value - reference['metrics'][key]) for key, value in actual['metrics'].items()
                     if not key.startswith('analytic_')}
    sequence = [row['identity'] for row in actual['events']] == [row['identity'] for row in reference['events']]
    switch_error = max((abs(a['time_s'] - b['time_s']) for a, b in zip(actual['events'], reference['events'])), default=0.) if sequence else None
    within = (sequence and switch_error <= factor * limits['switch_time_s']
              and all(value <= factor * limits['temperature_K' if key.endswith('_K') else 'pressure_Pa' if key.endswith('_Pa') else 'heat_W']
                      for key, value in errors.items())
              and all(value <= factor * limits[key if key in limits else 'resource_time_s'] for key, value in metric_errors.items()))
    return dict(maximum_absolute_series_error=errors, absolute_integral_error=metric_errors,
                event_sequence_match=sequence, maximum_switch_time_error_s=switch_error, within_predeclared_limits=bool(within))


def assess(book, runs):
    results = {}
    for item in book['cases']:
        name = item['id']
        by_step = runs[name]
        reference = by_step[str(book['fine_reference_s'])]
        comparisons = {step: compare(value, reference, book['limits']) for step, value in by_step.items()}
        fine = compare(by_step[str(book['reference_refinement_s'])], reference, book['limits'],
                       factor=book['fine_reference_fraction_of_limits'])
        selected = comparisons[str(book['proposed_qualified_maximum_step_s'])]
        analytic_ok = name != 'isolated-room' or by_step[str(book['proposed_qualified_maximum_step_s'])]['metrics']['analytic_max_temperature_error_K'] <= item['qualified_analytic_absolute_error_K']
        results[name] = dict(comparisons=comparisons, fine_reference_refinement=fine,
            candidate_steps_within_comparison_limits=[float(step) for step, value in comparisons.items()
                                                      if value['within_predeclared_limits']],
            analytic_gate=analytic_ok, proposed_step_gate=selected['within_predeclared_limits'] and analytic_ok,
            qualified_for_declared_fixture=selected['within_predeclared_limits'] and analytic_ok and fine['within_predeclared_limits'])
    return dict(schema='aegisdc-numerical-assessment-v1', cases=results,
                all_declared_fixtures_qualified=all(value['qualified_for_declared_fixture'] for value in results.values()),
                qualification_scope='Finite engineering conditions only, not a continuous parameter-domain or empirical validation; registered research has not started.')
