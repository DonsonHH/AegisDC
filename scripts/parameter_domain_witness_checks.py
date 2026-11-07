"""Evaluate saved ticket 29 trajectories against prespecified engineering witnesses."""

import json
from math import fsum, isclose

from inspection_delivery import digest, read, require


def near(a, b, tolerance, message):
    require(isclose(a, b, rel_tol=0, abs_tol=tolerance), message)


def parameters(scenario):
    return {row['id']: row['value'] for row in scenario['parameters']}


def prepared_checks(prepared, case, declaration, baseline, declaration_sha):
    model = prepared['scenario']
    p = parameters(model)
    nominal = parameters(baseline)
    require(prepared['case_id'] == case['id'] and prepared['duration_s'] == case['duration_s']
            and prepared['maximum_step_s'] == declaration['maximum_step_s']
            and prepared['declaration_sha256'] == declaration_sha
            and prepared['status'] == 'ADMITTED_INITIALIZATION_NOT_TRAJECTORY_QUALIFIED'
            and prepared['field_calibration'] == 'PENDING', 'Prepared case identity differs')
    changed = set(case['initial_overrides'])
    if case['phase'] is not None:
        changed.update(('coolant_inventory', 'coolant_initial_energy'))
    require(set(p) == set(nominal) and all(p[k] == nominal[k] for k in nominal.keys() - changed)
            and all(p[k] == v for k, v in case['initial_overrides'].items()), 'Unexpected parameter changes')
    require(all(model[k] == baseline[k] for k in baseline.keys() - {'parameters'})
            and set(model) == set(baseline), 'Fixed facility, topology or provenance differs')
    require(prepared['boundary_events'] == sorted(case['boundary_events'], key=lambda row: row['time_s']),
            'Prepared exogenous schedule differs')
    phase = prepared['initialization']['phase']
    require(phase['mass_kg'] == p['coolant_inventory']
            and phase['volume_m3'] == p['coolant_control_volume']
            and phase['internal_energy_J'] == p['coolant_initial_energy']
            and 0 < phase['quality'] < 1, 'Prepared two-phase inventory differs')
    if case['phase'] is not None:
        near(phase['pressure_Pa'], case['phase']['pressure_Pa'], .0001, 'Named charge pressure differs')
        require(phase['mass_kg'] == case['phase']['mass_kg'], 'Named charge mass differs')
    public = prepared['public_static']
    require(set(public) == {'nominal_knowledge', 'workforce_profile', 'fixed_sensor_profile'},
            'Prepared public surface includes undeclared data')
    profile = public['fixed_sensor_profile']
    enabled = [row['id'] for row in profile['measurements'] if row['enabled']]
    require(set(enabled) == set(case['enabled_fixed_measurements'])
            and not profile['ledger']['records'], 'Enabled channels must not invent delivered records')
    workforce = public['workforce_profile']
    require(workforce['walk_times_s'] ==
            {edge['id']: p[edge['duration_parameter']] for edge in model['graphs']['access']}
            and workforce['work_times_s'] == {interface['id']: p[interface['duration_parameter']]
                 for domain in model['domains'] for interface in domain['work_interfaces']}
            and workforce['shifts'] == {row['id']: [0,p['shift_end_time']]
                 for row in model['entities'] if row['kind'] == 'worker'}, 'Public crew timing differs')
    return {'pressure_Pa':phase['pressure_Pa'], 'quality':phase['quality'], 'mass_kg':phase['mass_kg'],
            'enabled_fixed_channels':len(enabled)}


def _read_rows(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def _snapshot(trace, time, tolerance):
    candidates = [row for row in trace if abs(row['time_s']-time) <= tolerance]
    require(len(candidates) == 1, f'Missing or ambiguous selected physical event point: {time}')
    return candidates[0]['domains']


def _check_boundaries(case, trace, run, limits):
    t_tol = limits['time_tolerance_s']
    duration = case['seconds']
    observed = {}
    if 'flow_squared_over_realized_speed_squared' in case:
        actual = []
        for t, coefficient in case['flow_squared_over_realized_speed_squared']:
            pump = _snapshot(trace, t, t_tol)['facility_cooling']['lake_pump']
            require(pump['speed'] > 0, 'Hydraulic witness requires positive realized speed')
            normalized = (pump['volume_flow_m3_s']/pump['speed'])**2
            near(normalized, coefficient, 1e-12, 'Independent filter and valve law differs')
            actual.append(dict(time_s=t, flow_m3_s=pump['volume_flow_m3_s'], speed=pump['speed']))
        observed['lake_intake_stages'] = actual
    if 'common_loss_s' in case:
        start, end = case['common_loss_s']
        lost = [row['domains'] for row in trace if start <= row['time_s'] < end]
        require(lost and all(row['power']['grid_draw_W'] == row['power']['ups_protected_output_W'] ==
                row['it_service']['delivered'] == 0 for row in lost), 'A cut common path delivered protected service')
        observed['common_cut_samples'] = len(lost)
    if 'floor' in case:
        floor = case['floor']
        switches = [row for row in run['events'] if row['kind'] == 'floor_access_closed']
        require(len(switches) == 1, 'Expected a single analytic access transition')
        near(switches[0]['applied_at_s'], floor['open_until_s'], t_tol, 'Floor gate crossing differs')
        final = trace[-1]['domains']
        require('loc_it' not in trace[0]['domains']['space_access']['blocked_location_ids']
                and 'loc_it' in final['space_access']['blocked_location_ids'], 'Wet IT access boundary differs')
        near(final['space_access']['floor_water_mass_kg'], floor['terminal_mass_kg'], 1e-9, 'Floor mass differs')
        near(trace[0]['domains']['facility_cooling']['hot_mass_kg']
             - final['facility_cooling']['hot_mass_kg'], floor['leaked_kg'], 1e-9, 'Source water was not debited')
        observed['it_access_closed_s'] = switches[0]['applied_at_s']
        observed['final_floor_mass_kg'] = final['space_access']['floor_water_mass_kg']
    if 'local_trip_s' in case:
        start, reset = case['local_trip_s']
        pre = _snapshot(trace, 0, t_tol)
        autonomous = _snapshot(trace, start, t_tol)
        waiting = _snapshot(trace, 2.25, t_tol)
        recovered = _snapshot(trace, reset, t_tol)
        reconnect = _snapshot(trace, duration, t_tol)
        require(pre['control_monitoring']['compute_permitted']
                and autonomous['control_monitoring']['supervisory_mode'] == 'autonomous'
                and autonomous['control_monitoring']['mode'] == 'sensor_invalid_fail_safe'
                and not waiting['control_monitoring']['compute_permitted']
                and recovered['control_monitoring']['compute_permitted']
                and recovered['control_monitoring']['supervisory_mode'] == 'autonomous'
                and reconnect['control_monitoring']['supervisory_mode'] == 'connected',
                'Local sample, supervisory autonomy or reset gate differs')
        observed['local_compute_trip_s'] = [start, reset]
    if case['id'] == 'coupled-adverse':
        require('loc_it' in trace[0]['domains']['space_access']['blocked_location_ids'],
                'Adverse wet access begins closed')
    return observed


def trajectory_checks(folder, prepared, case, limits, execution, source_files, property_sha):
    run = read(folder / 'run.json')
    model = read(folder / 'scenario.json')
    require(model == prepared['scenario'] and run['facility_id'] == model['id'], 'Run used different frozen inputs')
    inputs = run['inputs']
    require(inputs == {'duration_s':case['seconds'], 'maximum_step_s':limits['maximum_step_s'],
                       'boundary_events':prepared['boundary_events'], 'work_requests':[]},
            'Run duration, step, exogenous schedule or work requests changed')
    require(run['engineering_fixture'] is True and run['field_calibration'] == 'PENDING'
            and run['state_visibility'] == 'PRIVATE_PLANT_EVALUATOR_ONLY'
            and run['dispatch_interface'] == 'DISABLED_FOR_THIS_RUN' and not run['work_records']
            and run['research_trials'] == run['model_calls'] == run['training_calls'] == 0,
            'Engineering, private state or no-dispatch boundary differs')
    code = run['code_identity']
    require(code['git_commit'] == execution and code['implementation_has_changes'] is False
            and code['files'] == source_files and run['property_reference']['sha256'] == property_sha,
            'Run source or table identity differs')
    require(set(run['artifacts']) == {'scenario.json','private-state.jsonl','balances.jsonl'}, 'Run artifact set differs')
    for name, ref in run['artifacts'].items():
        require(digest((folder / name).read_bytes()) == ref['sha256'], f'Run artifact hash differs: {name}')
    trace, balances = _read_rows(folder / 'private-state.jsonl'), _read_rows(folder / 'balances.jsonl')
    domains = {row['id'] for row in model['domains']}
    summary = run['summary']
    require(len(trace) == len(balances) + 1 and len(balances) == summary['integration_steps']
            and trace[0]['time_s'] == 0 and trace[-1]['time_s'] == case['seconds']
            and all(set(row['domains']) == domains for row in trace), 'Incomplete run times or domain states')
    require(run['artifacts']['private-state.jsonl']['records'] == len(trace)
            and run['artifacts']['balances.jsonl']['records'] == len(balances)
            and run['artifacts']['scenario.json']['records'] == 1, 'Run artifact counts differ')
    t_tol, s_tol = limits['time_tolerance_s'], limits['service_tolerance_unit_s']
    previous = 0
    offered, supplied, deficit = [], [], []
    for left, right, row in zip(trace, trace[1:], balances):
        start, end = row['start_s'], row['end_s']
        dt = end-start
        require(start == previous == left['time_s'] and end == right['time_s']
                and 0 < dt <= limits['maximum_step_s'] + t_tol, 'Noncontiguous or excessive integration interval')
        previous = end
        service = left['domains']['it_service']
        demand, delivery = service['demand'], service['delivered']
        require(0 <= delivery <= demand and all(delivery <= value for value in service['capacities'].values()),
                'Service exceeded demand or actual capacity')
        offered.append(demand * dt)
        supplied.append(delivery * dt)
        deficit.append((1-delivery/demand)*dt if demand else 0)
        for key, value in (('demand_service_unit_s',offered[-1]), ('delivered_service_unit_s',supplied[-1]),
                           ('service_deficit_time_s',deficit[-1])):
            near(row[key], value, s_tol, f'Interval {key} does not reconcile')
        require(min(row['capacity_slack_W'].values()) >= -limits['capacity_slack_tolerance_W'], 'Capacity overdraw')
    offers, delivery, missing = fsum(offered), fsum(supplied), fsum(deficit)
    for key, value in (('demand_service_unit_s',offers), ('delivered_service_unit_s',delivery),
                       ('service_deficit_time_s',missing)):
        near(summary[key], value, s_tol, f'Reintegrated {key} differs')
    near(offers, case['offered'], s_tol, 'Exogenous offered integral differs')
    low, high = case['delivered']
    require(low - s_tol <= delivery <= high + s_tol, 'Delivered service differs from frozen bound')
    whole = summary['final_stored_energy_J'] - summary['initial_stored_energy_J'] - (
        fsum(row['boundary_input_J'] for row in balances) - fsum(row['boundary_output_J'] for row in balances))
    energy = max(abs(v) for row in balances for v in row['energy_residuals_J'].values())
    mass = max(abs(v) for row in balances for v in row['mass_residuals_kg'].values())
    require(whole == summary['whole_run_energy_residual_J'] and energy == summary['max_energy_residual_J']
            and mass == summary['max_mass_residual_kg'], 'Reconstructed conservation summaries differ')
    require(abs(whole) <= limits['whole_energy_residual_J'] and energy <= limits['step_energy_residual_J']
            and mass <= limits['mass_residual_kg'], 'Conservation exceeds frozen engineering limits')
    phases = [row['domains']['equipment_environment']['refrigerant'] for row in trace]
    p = parameters(model)
    for phase in phases:
        x = phase['quality']
        require(0 <= x <= 1 and 100_000 <= phase['pressure_Pa'] <= 3_000_000
                and phase['mass_kg'] == p['coolant_inventory'], 'Two-phase state is outside the frozen reference')
        mass_check = phase['liquid_mass_kg'] + phase['vapor_mass_kg']
        volume = phase['mass_kg'] * ((1-x)*phase['v_l_m3_kg'] + x*phase['v_v_m3_kg'])
        specific_energy = (1-x)*phase['u_l_J_kg'] + x*phase['u_v_J_kg']
        near(mass_check, phase['mass_kg'], 1e-9, 'Phase mass differs')
        near(volume, p['coolant_control_volume'], 1e-10, 'Fixed phase geometry differs')
        near(specific_energy, phase['internal_energy_J']/phase['mass_kg'], 1e-6, 'Phase energy differs')
    init = prepared['initialization']['phase']
    near(phases[0]['pressure_Pa'], init['pressure_Pa'], 1e-5, 'Actual run did not start at the admitted phase')
    return {
        'case_id':case['id'], 'duration_s':case['seconds'], 'trace_points':len(trace),
        'offered_service_unit_s':offers, 'delivered_service_unit_s':delivery, 'deficit_time_s':missing,
        'initial_pressure_Pa':phases[0]['pressure_Pa'],
        'pressure_range_Pa':[min(r['pressure_Pa'] for r in phases),max(r['pressure_Pa'] for r in phases)],
        'whole_energy_residual_J':whole, 'max_step_energy_residual_J':energy, 'max_mass_residual_kg':mass,
        'observed_boundaries':_check_boundaries(case,trace,run,limits),
    }
