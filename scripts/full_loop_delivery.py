"""Frozen ticket 27 complete-facility record/replay and saved-only verification."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from inspection_delivery import digest, durable, git, hashes, read, require, unchanged, write


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = 'docs/mainline/27-loop-engineering-protocol-v2.json'
PACKAGE = 'evidence/mainline/engineering/27-full-loop'
DOMAINS = {'power', 'backup', 'facility_cooling', 'equipment_environment', 'it_service',
           'control_monitoring', 'space_access', 'people_tools_work'}


def lines(path):
    return [json.loads(raw) for raw in path.read_bytes().splitlines()]


def pins(protocol, source):
    paths = git('ls-tree', '-rz', '--name-only', source, 'src', PACKAGE).decode().strip('\0').split('\0')
    paths = [name for name in paths if '__pycache__' not in name and not name.endswith(('.pyc', '.pyo'))]
    source_doc = read(ROOT / protocol['input'])
    inputs = [PROTOCOL, protocol['input'], protocol['independent_literals'], *protocol['contracts'], *protocol['retained_protocol_inputs'],
        *source_doc['source_inputs'], source_doc['model']['runtime']['property_table']]
    groups = dict(runtime=[name for name in paths if name.startswith('src/') and name.endswith('.py')],
        tools=protocol['tools'], inputs=inputs,
        development_originals=[name for name in paths if name.startswith(PACKAGE + '/development')])
    result = {role: hashes(source, names) for role, names in groups.items()}
    for name, sha in source_doc['source_inputs'].items():
        require(result['inputs'][name] == sha, 'Template source differs from authored input identity')
    service = read(ROOT / PACKAGE / 'development-service-20261107-02/receipt.json')
    require(result['tools']['scripts/full_loop_development.py'] == service['tool_sha256'], 'Prior development verification helper differs')
    return result


def declared(protocol):
    return set(protocol['durable_root']) | {case + '/' + name for case in protocol['cases'] for name in protocol['durable_case']} | {
        'replay/' + name for name in protocol['durable_replay_extra']}


def coincident_time(actual, requested):
    """The frozen eight-ULP clock convention, not a physical tolerance."""
    return (math.isfinite(actual) and math.isfinite(requested) and
        abs(actual - requested) <= 8 * max(math.ulp(actual), math.ulp(requested)))


def external_epochs(run, requested):
    events = [row for row in run['events'] if row['kind'] == 'exogenous_boundary_input']
    require(len(events) == len(requested), 'Exogenous event coverage differs')
    epochs = {}
    for wanted in requested:
        matching = [row for row in events if all(row[key] == value for key, value in wanted.items())]
        require(len(matching) == 1, 'Exogenous request/value differs')
        applied = matching[0]['applied_at_s']
        require(coincident_time(applied, wanted['time_s']), 'Applied exogenous event is outside the declared clock coincidence')
        epochs[(wanted['parameter_id'], wanted['time_s'])] = applied
    return epochs


def check_case(folder, name, protocol, doc, source, identity):
    case = folder / name
    original = case / 'trajectory'
    attempt, run = read(case / 'attempt.json'), read(original / 'run.json')
    declarations = read(case / 'declaration.json')
    request = read(case / 'request.json')
    lifecycle = lines(case / 'lifecycle.jsonl')
    require(attempt['status'] == 'COMPLETED' and attempt['failure'] is None, name + ': record/replay failed')
    require([row['state'] for row in lifecycle] == ['STARTED', 'COMPLETED'] and
        all(row['attempt_id'] == attempt['attempt_id'] for row in lifecycle), name + ': attempt lifecycle differs')
    require(set(attempt['artifacts']) == set(declarations['required_when_completed']) == durable(case) - {'attempt.json'}, 'Recorded durable case differs')
    for path, sha in attempt['artifacts'].items():
        require(digest((case / path).read_bytes()) == sha, 'Recorded artifact differs: ' + path)
    require(read(case / 'frozen-inputs.json') == doc['replay_inputs'] == read(case / 'inputs.json'), 'Frozen replay inputs differ')
    require(read(original / 'scenario.json') == doc['model'] == read(case / 'scenario-input.json'), 'Frozen facility differs')
    require(run['inputs']['dispatch_program'] == doc['replay_inputs']['dispatch_program'] and
        run['inputs']['boundary_events'] == doc['replay_inputs']['exogenous_events'] and not run['inputs']['work_requests'] and
        not run['inputs'].get('action_commands', []), 'Recorded inputs conflate external and endogenous actions')
    for key, value in (('duration_s', protocol['duration_s_per_case']), ('maximum_step_s', protocol['maximum_step_s'])):
        require(request[key] == attempt[key] == run['inputs'][key] == value, 'Frozen request/execution ' + key + ' differs')
    code = run['code_identity']
    require(code['git_commit'] == attempt['source_identity']['git_commit'] == source and not code['implementation_has_changes'], 'Actual revision differs')
    expected_runtime = {name: sha for name, sha in identity['runtime'].items()
        if name.startswith('src/aegis_dc/') or name == 'src/patrol_rsi/contracts.py'}
    require(code['files'] == attempt['source_identity']['files'] == expected_runtime, 'Executed runtime file set/bytes differ')
    require(run['research_trials'] == run['model_calls'] == run['training_calls'] == 0 and run['field_calibration'] == 'PENDING', 'Engineering classification differs')
    for path, item in run['artifacts'].items():
        require(digest((original / path).read_bytes()) == item['sha256'], 'Private trajectory member differs')
    trace, balance = lines(original / 'private-state.jsonl'), lines(original / 'balances.jsonl')
    literals = read(ROOT / protocol['independent_literals'])
    duration = protocol['duration_s_per_case']
    tol = protocol['absolute_tolerance']
    require(len(trace) == len(balance) + 1 and trace[0]['time_s'] == 0 and trace[-1]['time_s'] == duration, 'Saved complete time axis differs')
    require(set(doc['model']['graphs']) == {'physical', 'functional', 'control_information', 'access'}, 'Four facility relations differ')
    for i, row in enumerate(balance):
        require(row['start_s'] == trace[i]['time_s'] and row['end_s'] == trace[i + 1]['time_s'] and
            0 < row['end_s'] - row['start_s'] <= protocol['maximum_step_s'] + tol, 'Step/trace alignment differs')
    epochs = external_epochs(run, doc['replay_inputs']['exogenous_events'])
    load_at = epochs['service_demand', .5]
    maintenance_at = epochs['ups_in_service', 1]
    degradation_at = epochs['filter_resistance_multiplier', 1.5]
    outage_at = epochs['grid_capacity', 2]
    mains_at = epochs['grid_capacity', 3.4]
    at = {row['time_s']: row['domains'] for row in trace}
    require(set(epochs.values()) <= set(at), 'Applied event lacks its actual trace point')
    recovery = [time for time, domains in at.items() if coincident_time(time, 4) and
        domains['control_monitoring']['local_measurement']['sampled_at_s'] == time]
    require(len(recovery) == 1 and mains_at < recovery[0], 'Expected local restoration sample differs')
    restored_at = recovery[0]
    for row in trace:
        time, domains = row['time_s'], row['domains']
        require(set(domains) == DOMAINS, 'Complete eight-domain trajectory missing')
        demand = .5 if time < load_at else 1
        delivered = 0 if outage_at <= time < restored_at else demand
        require(domains['it_service']['demand'] == demand and domains['it_service']['delivered'] == delivered,
            'Independent piecewise service/protection witness differs at ' + str(time))
    require(at[0]['power']['actual_powers_W']['compute'] == 1_000_000 and
        at[load_at]['power']['actual_powers_W']['compute'] == 2_000_000, 'Actual requested-load heat witness differs')
    require(at[maintenance_at]['backup']['reserve_states']['ups']['mode'] == 'maintenance' and
        at[outage_at]['power']['ups_output_W'] == at[outage_at]['power']['generator_output_W'] == 0, 'Maintenance/reserve gating differs')
    require(not at[outage_at]['control_monitoring']['compute_permitted'] and not at[mains_at]['control_monitoring']['compute_permitted'] and
        at[restored_at]['control_monitoring']['compute_permitted'], 'Local protection/restoration timing differs')
    for time, squared in ((0, 1/100), (degradation_at, 1/340), (outage_at, 0), (4.25, 1/340), (6, 1/100)):
        flow = at[time]['facility_cooling']['lake_pump']['volume_flow_m3_s']
        require(math.isclose(flow ** 2, squared, rel_tol=0, abs_tol=tol), 'Independent hydraulic witness differs')
    summary = run['summary']
    actual = literals['physical']
    ratio = lambda values: values[0] / values[1]
    for metric, expected in (('demand_service_unit_s', ratio(actual['offered_demand_integral'])),
                             ('delivered_service_unit_s', ratio(actual['delivered_integral'])),
                             ('service_deficit_time_s', ratio(actual['normalized_deficit_time_s'])),
                             ('worker_work_person_s', 2)):
        require(math.isclose(summary[metric], expected, rel_tol=0, abs_tol=tol), 'Independent ' + metric + ' differs')
    require(abs(summary['whole_run_energy_residual_J']) < protocol['energy_tolerance_J'] and
        summary['max_mass_residual_kg'] <= protocol['mass_tolerance_kg'], 'Independent boundary conservation differs')
    work = run['work_records']
    require([(r['issued_at_s'], r['work_started_at_s'], r['completed_at_s'], r['status']) for r in work] ==
        [(3, 3.25, 4.25, 'completed'), (4.75, 5, 6, 'completed')], 'Actual paid work chronology differs')
    effect = run['intervention_private_audit']['events']
    require(len(effect) == 1 and (effect[0]['parameter_id'], effect[0]['applied_at_s'], effect[0]['old_value'], effect[0]['new_value']) ==
        ('filter_resistance_multiplier', 6, 4, 1), 'Actual named cleaning effect differs')
    feedback = run['intervention_public_feedback']
    require(len(feedback) == 1 and feedback[0]['arrived_at_s'] == 6.5 and not feedback[0]['risk_closed'], 'Action report fabricated closure')
    decisions = run['policy_public_decisions']
    require([r['frame']['as_of_s'] for r in decisions] == protocol['decisions_s'] and
        [r['choice']['chosen_candidate_id'] for r in decisions] == protocol['choices'], 'Online selection or decision chronology differs')
    closures = []
    record_counts = []
    for row in decisions:
        now = row['frame']['as_of_s']
        require(not row['choice']['execution_permission'] and not row['choice']['generated_tour'], 'Public selection gained execution authority')
        records = {r['id']: r for r in row['frame']['evidence']['records']}
        require(all(r['observed_at_s'] <= r['arrived_at_s'] <= now for r in records.values()), 'Future measurement entered the decision frame')
        require(all(r['observed_at_s'] <= r['arrived_at_s'] <= now for r in row['history']['work_feedback']), 'Future workforce feedback entered the decision')
        require(('delayed-lake-work-order' in records) == (now >= 3) and
            ('actual-lake-flow-before-action' in records) == (now >= 4.75), 'Late evidence visibility differs')
        question = row['choice']['question_lifecycle']['questions'][0]
        closures.append(question)
        record_counts.append(len(records))
    require([r['status'] for r in closures] == protocol['closure_states'], 'Verified closure chronology differs')
    require(not any(r['risk_closed'] for r in closures[:-1]) and closures[-1]['risk_closed'], 'Risk closed before multi-sample verification')
    handheld = next(r for r in decisions[3]['frame']['evidence']['records'] if r['id'] == 'actual-lake-flow-before-action')
    require((handheld['observed_at_s'], handheld['arrived_at_s'], handheld['source_id'], handheld['quality']['status']) ==
        (4.25, 4.75, 'portable-intake-meter', 'bounded') and
        math.isclose(handheld['value'] ** 2, 1/340, rel_tol=0, abs_tol=tol), 'Actual handheld sampling/value differs')
    polls = run['policy_sensor_private_audit']
    for instrument, epochs in (('rectifier-meter', [0, 10]), ('lake-flow', [7, 8, 9, 10]), ('joint-service-meter', [7, 8, 9, 10])):
        require([r['polled_at_s'] for r in polls if r['measurement_id'] == instrument] == epochs, 'Declared sparse instrument schedule differs')
    closure_checks = closures[-1]['checks']
    require(len(closure_checks) == 2 and {(row['check_id'], row['role']) for row in closure_checks} ==
        {('flow-restored', 'condition'), ('service-restored', 'service')}, 'Verification role set differs')
    require(all(check['passed'] and check['genuine_sample_count'] == 2 and check['span_s'] == 1
        for check in closure_checks), 'Verification used too few real post-action samples')
    public = decisions[-1]['frame']['evidence']['records']
    all_support = set()
    for source_id, expected_value, role in (('intake-flow-record', 99.8, 'condition'), ('joint-service-record', 1, 'service')):
        rows = [r for r in public if r['source_id'] == source_id]
        require([(r['observed_at_s'], r['arrived_at_s']) for r in rows] == [(7, 7.5), (8, 8.5)] and
            all(math.isclose(r['value'], expected_value, rel_tol=0, abs_tol=tol) and r['quality']['status'] == 'bounded' for r in rows)
            and len({r['provenance']['origin_id'] for r in rows}) == 2, 'Actual independent-time recovery evidence differs')
        record_ids = {r['id'] for r in rows}
        check = next(row for row in closure_checks if row['role'] == role)
        require(set(check['supporting_record_ids']) == record_ids, 'Closure did not bind the actual recovered channel records')
        all_support.update(record_ids)
    require(set(closures[-1]['supporting_record_ids']) == all_support, 'Closure support does not equal the four real records')
    first = decisions[1]['choice']
    require(first['prospective_evidence_audit'][0]['classification'] == 'INFORMATIVE_COMPATIBLE_WITH_DECLARED_UPDATER', 'Work order did not produce compatible contingent planning')
    declared_belief = doc['replay_inputs']['dispatch_program']['policy_program']['options']['belief_model']
    worlds = first['valuation_current_outcome_mass_by_belief_variant']
    require(set(worlds) == {row['id'] for row in declared_belief['variants']} and
        all(world['cooling-limited'] == [25, 124] for world in worlds.values()), 'Independent arrived-work-order posterior coverage/value differs')
    values = {r['kind']: r['expected_service_deficit_s'] for r in first['forecast_plans'][0]['alternatives']}
    for key, literal in (('inspect_then_act', 'inspect_deficit_s'), ('direct_intervention', 'direct_deficit_s'), ('defer', 'defer_deficit_s')):
        require(math.isclose(values[key], ratio(literals['public_model'][literal]), rel_tol=0, abs_tol=tol), 'Independent forecast differs: ' + key)
    computation = run['policy_computation_audit']
    require(len(computation) == protocol['scheduled_online_decisions_per_case'] and
        all(a['decision_at_s'] == d['frame']['as_of_s'] and a['model_evaluations'] == d['choice']['model_evaluations'] and
            type(a['elapsed_ns']) is int and a['elapsed_ns'] >= 0 for a, d in zip(computation, decisions)), 'Decision compute accounting differs')
    return dict(status='PASS', decision_times=protocol['decisions_s'], chosen=protocol['choices'], closure=protocol['closure_states'],
        public_record_counts=record_counts, work_records=work, closure_support=closures[-1]['supporting_record_ids'],
        actual=summary, forecast_after_work_order=values, trace_points=len(trace),
        external_events=[dict(parameter_id=parameter, requested_at_s=requested, applied_at_s=applied)
            for (parameter, requested), applied in epochs.items()], restoration_sample_s=restored_at)


def compare(folder):
    original, replay = [read(folder / case / 'trajectory/run.json') for case in ('original', 'replay')]
    for run in (original, replay):
        for row in run['policy_computation_audit']:
            row.pop('elapsed_ns')
    require(json.dumps(original, sort_keys=True, allow_nan=False) == json.dumps(replay, sort_keys=True, allow_nan=False),
        'Run differs outside explicitly classified diagnostic elapsed_ns')
    for name in ('scenario.json', 'private-state.jsonl', 'balances.jsonl'):
        require((folder / 'original/trajectory' / name).read_bytes() == (folder / 'replay/trajectory' / name).read_bytes(), 'Exact trajectory replay differs: ' + name)
    a, b = [read(folder / case / 'attempt.json') for case in ('original', 'replay')]
    require(a['attempt_id'] != b['attempt_id'] and b['replay_of'] == dict(attempt_id=a['attempt_id'],
        attempt_sha256=digest((folder / 'original/attempt.json').read_bytes()), mode='EXACT_REEXECUTION'), 'Replay origin identity differs')
    for name in ('attempt.json', 'declaration.json', 'lifecycle.jsonl'):
        require((folder / 'original' / name).read_bytes() == (folder / 'replay/origin' / name).read_bytes(), 'Original identity snapshot differs')
    return dict(status='PASS', wall_clock_exception='policy_computation_audit[*].elapsed_ns',
        scenario_trace_balances_byte_equal=True, original_and_replay_distinct=True)


def append(path, value):
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def capture(folder, protocol):
    require(not git('status', '--porcelain') and sys.dont_write_bytecode and sys.flags.utf8_mode, 'Use clean committed source with -B -X utf8')
    require(sys.pycache_prefix is not None and not Path(sys.pycache_prefix).exists(), 'Use a fresh absent cache prefix')
    require(Path(os.environ.get('PYTHONPATH', '')).resolve() == ROOT / 'src', 'Set PYTHONPATH to the execution source')
    source = git('rev-parse', 'HEAD').decode().strip()
    identity = pins(protocol, source)
    require(unchanged(source, identity), 'Execution source differs before capture')
    doc = read(ROOT / protocol['input'])
    require(protocol['cases'] == ['original', 'replay'] and protocol['attempt_budget'] == 2 and
        protocol['simulated_duration_budget_s'] == 2 * doc['duration_s'] == 20 and
        doc['maximum_step_s'] == protocol['maximum_step_s'], 'Unexpected frozen budget')
    folder.mkdir(exist_ok=False)
    write(folder / 'capture.json', dict(execution_source=source, python=sys.version, executable=sys.executable,
        executable_sha256=digest(Path(sys.executable).read_bytes()), argv=sys.argv, cache_prefix=sys.pycache_prefix,
        no_bytecode=sys.dont_write_bytecode, utf8_mode=sys.flags.utf8_mode, planned_attempts=2,
        declared_simulated_duration_s=20, classification=protocol['classification']))
    receipt = dict(status='FAIL', source=source, pins=identity, attempts=0, completed_integrations=0, validated=0,
        simulated_duration_attempted_s=0, registered_effect_trials=0, field_calibration='PENDING')
    try:
        from aegis_dc.replay import replay_attempt, run_recorded
        checks = {}
        for case in protocol['cases']:
            require(unchanged(source, identity), 'Execution source differs before case')
            receipt['attempts'] += 1
            receipt['simulated_duration_attempted_s'] += doc['duration_s']
            append(folder / 'attempts.jsonl', dict(case=case, status='STARTED', source=source, duration_s=doc['duration_s']))
            try:
                if case == 'original':
                    result = run_recorded(doc['model'], folder / case, inputs=doc['replay_inputs'],
                        duration_s=doc['duration_s'], step_s=doc['maximum_step_s'])
                else:
                    result = replay_attempt(folder / 'original', folder / case)
                require(result['status'] == 'COMPLETED', str(result['failure']))
                receipt['completed_integrations'] += 1
                checks[case] = check_case(folder, case, protocol, doc, source, identity)
                receipt['validated'] += 1
                append(folder / 'attempts.jsonl', dict(case=case, status='COMPLETED', source=source))
            except Exception as error:
                append(folder / 'attempts.jsonl', dict(case=case, status='FAILED', source=source, error=str(error)))
                raise
        checks['replay_comparison'] = compare(folder)
        write(folder / 'checks.json', checks)
        require(durable(folder) == declared(protocol), 'Declared output set differs')
        receipt['status'] = 'PASS'
    except Exception as error:
        receipt.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        try:
            receipt['source_guard'] = unchanged(source, identity)
        except (OSError, subprocess.SubprocessError) as error:
            receipt.update(source_guard=False, source_guard_error=str(error))
        if not receipt['source_guard']:
            receipt['status'] = 'FAIL'
        receipt['artifacts'] = {name: digest((folder / name).read_bytes()) for name in sorted(durable(folder))}
        write(folder / protocol['terminal'], receipt)
    require(receipt['status'] == 'PASS', 'Terminal capture failed')
    return dict(status='PASS', source=source, physical_runs=receipt['completed_integrations'], simulated_duration_s=20)


def verify(folder, protocol, delivery):
    require(git('rev-parse', 'HEAD').decode().strip() == delivery and not git('status', '--porcelain'), 'Use clean committed delivery')
    receipt = read(folder / protocol['terminal'])
    source = receipt['source']
    require(receipt['status'] == 'PASS' and receipt['source_guard'] and receipt['attempts'] == receipt['completed_integrations'] == receipt['validated'] == 2 and
        receipt['simulated_duration_attempted_s'] == 20, 'Original frozen attempt did not pass')
    require(durable(folder) == declared(protocol) | {protocol['terminal']} and set(receipt['artifacts']) == declared(protocol), 'Frozen durable output set differs')
    for name, sha in receipt['artifacts'].items():
        require(digest((folder / name).read_bytes()) == sha, 'Original artifact differs: ' + name)
    for name, sha in hashes(delivery, [(folder / n).relative_to(ROOT).as_posix() for n in durable(folder)]).items():
        require(digest((ROOT / name).read_bytes()) == sha, 'Committed artifact differs: ' + name)
    require(receipt['pins'] == pins(protocol, source), 'Recorded execution source/inputs/tools differ')
    for names in receipt['pins'].values():
        require(names == hashes(delivery, names) and all(digest((ROOT / name).read_bytes()) == sha for name, sha in names.items()), 'Delivery pin bytes differ')
    ledger = lines(folder / 'attempts.jsonl')
    require([(r['case'], r['status'], r['source']) for r in ledger] ==
        [(case, stage, source) for case in protocol['cases'] for stage in ('STARTED', 'COMPLETED')], 'Frozen attempt ledger differs')
    require(all(row['duration_s'] == protocol['duration_s_per_case'] for row in ledger if row['status'] == 'STARTED'), 'Started attempt budget differs')
    doc = read(ROOT / protocol['input'])
    rebuilt = {case: check_case(folder, case, protocol, doc, source, receipt['pins']) for case in protocol['cases']}
    rebuilt['replay_comparison'] = compare(folder)
    require(rebuilt == read(folder / 'checks.json'), 'Saved check results differ')
    return dict(status='PASS', source=source, delivery=delivery, artifacts=len(receipt['artifacts']),
        pins={role: len(names) for role, names in receipt['pins'].items()}, physical_runs=2, simulated_duration_s=20,
        new_physics=0, new_selector_calls=0, registered_effect_trials=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['capture', 'verify'])
    parser.add_argument('--delivery')
    args = parser.parse_args()
    protocol = read(ROOT / PROTOCOL)
    folder = ROOT / protocol['output']
    print(json.dumps(capture(folder, protocol) if args.mode == 'capture' else verify(folder, protocol, args.delivery), ensure_ascii=False))
