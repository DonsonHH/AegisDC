"""Frozen ticket26 engineering capture and saved-only delivery verification."""
import argparse
from copy import deepcopy
from html import escape
import json
import math
import os
from pathlib import Path
import sys
from time import perf_counter_ns

from inspection_delivery import git, hashes, require, read, digest, write, durable, unchanged

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'evidence/mainline/engineering/26-candidate'
PROTOCOL = 'docs/mainline/26-candidate-engineering-protocol.json'


def pins(protocol, revision):
    names = git('ls-tree', '-rz', '--name-only', revision, 'src', 'tests', 'configs', PACKAGE,
        'evidence/mainline/engineering/18-beliefs/capture-01',
        'evidence/mainline/engineering/23-interventions/reference').decode().strip('\0').split('\0')
    names = [name for name in names if '__pycache__' not in name and not name.endswith(('.pyc', '.pyo'))]
    tools = [protocol['authoring_tool'], protocol['helper_tool'], protocol['input_preparation_tool']]
    inputs = [PROTOCOL, *protocol['contracts'], *[name for name in names if name.startswith((
        'tests/', 'configs/full-facility', 'configs/materials/', PACKAGE + '/development/', PACKAGE + '/reference/', PACKAGE + '/oracles/',
        'evidence/mainline/engineering/18-beliefs/capture-01/', 'evidence/mainline/engineering/23-interventions/reference/'))],
        PACKAGE + '/.gitattributes']
    return {role: hashes(revision, paths) for role, paths in dict(
        runtime=[name for name in names if name.startswith('src/') and name.endswith('.py')],
        tools=tools, inputs=inputs,
        historical_development=[name for name in names if name.startswith(PACKAGE + '/development-originals-')]).items()}


def declared(protocol):
    return set(protocol['durable_root']) | {
        case['id'] + '/' + name for case in protocol['pure_cases'] for name in protocol['durable_pure']
    } | {case['id'] + '/' + name for case in protocol['physical_cases'] for name in protocol['durable_physical']}


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def close(actual, expected, label, protocol):
    require(type(actual) in (int, float) and math.isclose(actual, expected, rel_tol=0,
        abs_tol=protocol['absolute_tolerance']), label + ' differs')


def plans(choice):
    return {row['kind']: row for row in choice['forecast_plans'][0]['alternatives']}


def check_decision(folder, case, protocol):
    path = folder / case['id']
    choice = read(path / 'decision.json')
    computation = read(path / 'computation.json')
    document = read(ROOT / case['input'])
    expected = case['expected']
    require(choice['chosen_candidate_id'] == expected['chosen'], case['id'] + ': selection differs')
    require(choice['as_of_s'] == document['frame']['as_of_s'] and choice['facility_id'] == document['frame']['facility_id'], 'Decision identity/clock differs')
    require(not choice['execution_permission'] and not choice['generated_tour'] and not choice['forecast_is_actual_observation'], 'Forecast acquired physical authority')
    alternatives = plans(choice)
    for kind, ratio in expected.get('values', {}).items():
        actual = alternatives[kind]['expected_service_deficit_s']
        if ratio is None:
            require(actual is None, 'Unknown prospective value became numeric')
        else:
            close(actual, ratio[0] / ratio[1], case['id'] + ':' + kind, protocol)
    if expected.get('classification'):
        audit = choice['prospective_evidence_audit'][0]
        require(audit['classification'] == expected['classification'], 'Projection classification differs')
        if 'reason' in expected:
            require(expected['reason'] in audit['reasons'], 'Unknown value lost its reason')
        for index, item in enumerate(audit.get('compatibility_by_assumption', [])):
            if 'exact_current' in expected and index == 0:
                require(item['exact_current_outcome_mass']['cooling-limited'] == expected['exact_current'], 'Exact current mass differs')
            for branch in ('positive', 'negative'):
                if expected.get(branch):
                    require(item['branches'][branch]['projected_outcome_mass']['cooling-limited'] == expected[branch], 'Exact report posterior differs')
            if 'projected_positive' in expected:
                require(item['branches']['positive']['projected_outcome_mass']['cooling-limited'] == expected['projected_positive'], 'Projected incompatible mass differs')
                require(item['branches']['positive']['original_joint_report_posterior']['cooling-limited'] == expected['original_positive'], 'Original conditional mass differs')
        if case['id'] == 'nonadaptive-candidate':
            require(audit['covered_report_classes'] == ['positive', 'negative', 'threshold_straddled', 'missing'], 'Nonadaptive proof omitted a report class')
            require(audit['marginalization'] == 'SUM_ORIGINAL_REPORT_MASS_PER_JOINT_OUTCOME_EQUALS_ONE', 'Original outcome/report mass changed')
    if 'common_exact' in expected:
        require(choice['valuation_mass_basis'] == 'EXACT_FINITE_PUBLIC_BELIEF_CONTEXT_V1', 'Shared exact basis differs')
        require(all(value['cooling-limited'] == expected['common_exact'] for value in
            choice['valuation_current_outcome_mass_by_belief_variant'].values()), 'Common current world mass differs')
        require(choice['model_evaluations']['valuation_exact_belief_context'] == 2, 'Exact valuation reads not accounted')
    require(type(computation['elapsed_ns']) is int and computation['elapsed_ns'] >= 0, 'Missing measured decision time')
    require(computation['model_evaluations'] == choice['model_evaluations'], 'Computation counters differ')
    return dict(status='PASS', chosen=choice['chosen_candidate_id'],
        values={kind: row['expected_service_deficit_s'] for kind, row in alternatives.items()},
        model_evaluations=choice['model_evaluations'], measured_elapsed_ns=computation['elapsed_ns'])


def check_physical(folder, case, protocol):
    path = folder / case['id']
    run = read(path / 'run.json')
    document = read(ROOT / case['input'])
    expected = case['expected']
    trace, balances = rows(path / 'private-state.jsonl'), rows(path / 'balances.jsonl')
    decisions = run['policy_public_decisions']
    require(read(path / 'scenario.json') == document['model'] and
        run['inputs']['dispatch_program'] == document['dispatch_program'], 'Actual saved input differs')
    require([row['frame']['as_of_s'] for row in decisions] == document['dispatch_program']['decision_times_s'], 'Decision instants differ')
    require([row['choice']['chosen_candidate_id'] for row in decisions] == expected['chosen'], 'Online selection sequence differs')
    for row in decisions:
        frame, choice, now = row['frame'], row['choice'], row['frame']['as_of_s']
        require(choice['as_of_s'] == now and choice['facility_id'] == frame['facility_id'], 'Online identity/clock differs')
        require(not choice['execution_permission'] and not choice['generated_tour'], 'Selection created authority/Tour')
        require(all(record['observed_at_s'] <= record['arrived_at_s'] <= now for record in frame['evidence']['records']), 'Future evidence in public frame')
        require(all(record['observed_at_s'] <= record['arrived_at_s'] <= now for record in row['history']['work_feedback']), 'Future feedback in public history')
        require(choice['valuation_mass_basis'] == 'EXACT_FINITE_PUBLIC_BELIEF_CONTEXT_V1', 'Online shared basis lost')
    work = run['work_records']
    require(all(row['status'] == 'completed' for row in work), 'Unexpected unfinished/rejected actual work')
    require([row['completed_at_s'] for row in work] == expected['completed_at_s'] and
        [row['work_started_at_s'] for row in work] == expected['work_started_at_s'], 'Actual work clocks differ')
    effects = run['intervention_private_audit']['events']
    require([row['applied_at_s'] for row in effects] == expected['effect_at_s'], 'Named effect clock differs')
    for row in effects:
        require(row['outcome'] == 'APPLIED' and row['old_value'] == 4 and row['new_value'] == 2, 'Residual filter action differs')
    require(all(not row['risk_closed'] for row in run['intervention_public_feedback']), 'Action report closed risk')
    require([row['polled_at_s'] for row in run['policy_sensor_private_audit']] == expected['polls'], 'Continuing fixed polls differ')
    records = run['inspection_public_snapshot']['records']
    if expected['handheld'] is None:
        require(records == [], 'Unperformed inspection produced a record')
    else:
        require(len(records) == 1, 'Expected exactly one actual handheld record')
        record = records[0]
        require(record['observed_at_s'] == 2.25 and record['arrived_at_s'] == 2.75 and
            record['provenance']['origin_id'] == 'post-clean-flow', 'Actual handheld identity/times differ')
        require(not any(item['source_id'] == 'portable-intake-meter' for item in decisions[1]['frame']['evidence']['records']), 'Handheld arrived before2.75')
        if expected['handheld'] == 'missing':
            require(record['value'] is None and record['availability'] == 'missing' and record['quality']['status'] == 'unknown', 'Unsupported actual result fabricated a reading')
            require(run['inspection_public_feedback'][0]['confirmation'] == 'UNCONFIRMED' and
                not run['inspection_public_feedback'][0]['current_confirmation'], 'Unknown measurement became confirmation')
            require(run['inspection_private_audit']['events'][0]['disposition'] == 'CONDITION_OUTSIDE_DECLARED_RANGE', 'Actual unsuitable cause differs')
        else:
            close(record['value'], math.sqrt(1 / 340), 'Literal initial intake flow', protocol)
    if expected.get('closure_pending'):
        before = decisions[2]['choice']['question_lifecycle']['questions'][0]
        after = decisions[3]['choice']['question_lifecycle']['questions'][0]
        require(before['status'] == 'OPEN_UNCONFIRMED' and after['status'] == 'ACTION_COMPLETED_PENDING_VERIFICATION' and not after['risk_closed'], 'Arrived feedback fabricated risk closure')
    if expected.get('first_reason'):
        audit = decisions[0]['choice']['prospective_evidence_audit'][0]
        require(audit['classification'] == 'UNMODELED' and expected['first_reason'] in audit['reasons'] and
            plans(decisions[0]['choice'])['inspect_then_act']['expected_service_deficit_s'] is None, 'Pending background did not remain unknown')
    if 'inspection_prediction' in expected:
        first = plans(decisions[0]['choice'])
        close(first['inspect_then_act']['expected_service_deficit_s'], 1.5, 'Uninformative inspection forecast', protocol)
        close(first['direct_intervention']['expected_service_deficit_s'], 17 / 16, 'Direct forecast', protocol)
    summary = run['summary']
    for name in ('demand_service_unit_s', 'delivered_service_unit_s', 'service_deficit_time_s'):
        close(summary[name], expected[name], name, protocol)
    close(summary['worker_work_person_s'], expected['work_person_s'], 'Paid actual work', protocol)
    require(run['policy_public_resource_ledger']['spent_or_reserved'] == expected['spent'], 'Permanent admission spending differs')
    require(abs(summary['whole_run_energy_residual_J']) < protocol['energy_tolerance_J'] and
        summary['max_mass_residual_kg'] <= protocol['mass_tolerance_kg'], 'Physical conservation residual failed')
    require(len(trace) == len(balances) + 1 and trace[0]['time_s'] == 0 and trace[-1]['time_s'] == 6, 'Incomplete actual trace')
    require(all(0 < row['end_s'] - row['start_s'] <= protocol['maximum_step_s'] + protocol['absolute_tolerance'] for row in balances), 'Integration step outside declared bound')
    # Independent fixed-head hydraulic literals; evaluator reads cannot enter a decision.
    for row in trace:
        applied = bool(expected['effect_at_s']) and row['time_s'] >= expected['effect_at_s'][0]
        close(row['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s'], math.sqrt(1 / (180 if applied else 340)), 'Actual residual filter hydraulics', protocol)
    audits = run['policy_computation_audit']
    require(len(audits) == len(decisions) and all(type(row['elapsed_ns']) is int and row['elapsed_ns'] >= 0 for row in audits), 'Online measured decision cost absent')
    require(all(a['model_evaluations'] == d['choice']['model_evaluations'] for a, d in zip(audits, decisions)), 'Online computational counters differ')
    require(run['research_trials'] == run['model_calls'] == run['training_calls'] == 0 and run['field_calibration'] == 'PENDING', 'Engineering evidence upgraded')
    for name, identity in run['artifacts'].items():
        require(digest((path / name).read_bytes()) == identity['sha256'], 'Original saved run member differs')
    return dict(status='PASS', chosen=expected['chosen'], actual_work_person_s=summary['worker_work_person_s'],
        summary=summary, measured_decision_ns=sum(row['elapsed_ns'] for row in audits),
        model_evaluations=[row['model_evaluations'] for row in audits], trace_points=len(trace),
        observed_effect_at_s=expected['effect_at_s'])


def check_pairs(protocol):
    for name in ('same_public_pair', 'same_exact_pair', 'same_online_pair'):
        documents = [read(ROOT / next(case['input'] for case in protocol['pure_cases'] + protocol['physical_cases'] if case['id'] == identifier)) for identifier in protocol[name]]
        common = deepcopy(documents)
        for document in common:
            program = document.get('dispatch_program', document)
            program['policy_program'].pop('policy')
        require(common[0] == common[1], 'Paired world/public models/resources differ: ' + name)
    return True


def check_saved(folder, protocol):
    return dict(status='PASS', pure={case['id']: check_decision(folder, case, protocol) for case in protocol['pure_cases']},
        physical={case['id']: check_physical(folder, case, protocol) for case in protocol['physical_cases']},
        paired_inputs_identical_except_policy_name=check_pairs(protocol), registered_research_trials=0,
        scope=protocol['scope'])


def figures(folder, checks, protocol):
    """Deterministic vector figures from saved data; no project/plant call."""
    def start(height, title, subtitle):
        return ['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="' + str(height) + '" viewBox="0 0 1440 ' + str(height) + '">',
            '<metadata>Saved checks SHA256 ' + digest(json.dumps(checks, sort_keys=True).encode()) + '</metadata>',
            '<rect width="1440" height="' + str(height) + '" fill="#f4f7fb"/>',
            '<style>text{font-family:Arial,sans-serif;fill:#152b45}.title{font-size:32px;font-weight:bold}.h{font-size:23px;font-weight:bold}.b{font-size:19px}.n{font-size:17px}</style>',
            label(40, 50, title, 'title'), label(40, 84, subtitle, 'n')]
    def label(x, y, text, cls='b'):
        return '<text x="' + str(x) + '" y="' + str(y) + '" class="' + cls + '">' + escape(str(text)) + '</text>'
    actual = start(1100, 'Actual candidate execution | saved six-second engineering worlds',
        'Synthetic full-facility V6. Actual plant data; no effectiveness comparison or field calibration.')
    actual.append(label(40, 130, '1  Paid work, actual sampling and arrived records', 'h'))
    x = lambda time: 330 + time * 165
    for index, (name, a, b, color) in enumerate((('Inspection work', 1.25, 2.25, '#087f8c'), ('Inspection latency', 2.25, 2.75, '#8364b2'),
        ('Action work', 3, 4, '#b57519'), ('Action report latency', 4, 4.5, '#8364b2'))):
        y = 160 + 39 * index
        actual += [label(40, y + 22, name), '<rect x="%.3f" y="%d" width="%.3f" height="27" fill="%s"/>' % (x(a), y, x(b) - x(a), color)]
    for time in (0, 1, 2, 3, 4, 5, 6):
        actual += ['<line x1="%g" x2="%g" y1="155" y2="315" stroke="#cbd5e1"/>' % (x(time), x(time)), label(x(time) - 5, 342, str(time) + ' s', 'n')]
    actual += [label(40, 385, '2  Actual intake flow; filter multiplier 4 → 2, with residual resistance', 'h')]
    for time in (0, 1, 2, 3, 4, 5, 6):
        actual += ['<line x1="%g" x2="%g" y1="410" y2="620" stroke="#d9e2ec"/>' % (x(time), x(time)), label(x(time) - 5, 647, time, 'n')]
    for value in (.05, .06, .07, .08):
        y = 620 - (value - .05) / .03 * 210
        actual += ['<line x1="330" x2="1320" y1="%g" y2="%g" stroke="#d9e2ec"/>' % (y, y), label(235, y + 6, '%.2f m³/s' % value, 'n')]
    for identifier, color in (('online-candidate-defer', '#8894a2'), ('online-candidate-direct', '#b57519'), ('online-candidate-inspect', '#087f8c')):
        trace = rows(folder / identifier / 'private-state.jsonl')
        points = ' '.join('%.3f,%.3f' % (x(row['time_s']), 620 - (row['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s'] - .05) / .03 * 210) for row in trace)
        actual.append('<polyline points="' + points + '" fill="none" stroke="' + color + '" stroke-width="3"/>')
    actual += [label(40, 680, 'Teal: inspect then act at 4 s. Gold: direct at 2.25 s. Gray: defer. Nominal clean flow is 0.1 m³/s.', 'n'),
        label(40, 725, '3  Same remaining service bottleneck; different actual work costs', 'h')]
    for index, case in enumerate(protocol['physical_cases']):
        y = 765 + index * 42
        result = checks['physical'][case['id']]
        actual += [label(40, y + 20, case['id'].replace('online-', ''), 'n'),
            '<rect x="440" y="%d" width="195" height="25" fill="#087f8c"/>' % y,
            '<rect x="635" y="%d" width="585" height="25" fill="#ccd5df"/>' % y,
            label(456, y + 19, '1.5 served', 'n'), label(790, y + 19, '4.5 deficit', 'n'),
            label(1240, y + 19, str(result['actual_work_person_s']) + ' person-s', 'n')]
    actual += [label(40, 1054, 'All six worlds: offered demand 6 service-unit·s; network capacity 0.25 remains limiting.', 'n'),
        label(40, 1083, 'Action completion does not verify closure. Fixed sensors continue polling; actual missing reports remain unknown.', 'n'), '</svg>']

    values = start(680, 'Prospective values | public finite-law predictions',
        'Model predictions in seconds of service deficit. These bars are not measured plant outcomes.')
    for index, name in enumerate(('nonadaptive-baseline', 'nonadaptive-candidate', 'informative-candidate', 'exact-baseline', 'exact-candidate')):
        y = 135 + index * 96
        value = checks['pure'][name]
        values.append(label(40, y, name + ' → ' + str(value['chosen']), 'n'))
        for offset, (kind, color) in enumerate((('inspect_then_act', '#087f8c'), ('direct_intervention', '#b57519'), ('defer', '#8894a2'))):
            amount = value['values'][kind]
            values += ['<rect x="470" y="%d" width="%g" height="18" fill="%s"/>' % (y - 20 + offset * 23, amount * 360, color),
                label(500 + amount * 360, y - 5 + offset * 23, '%.6f' % amount, 'n')]
    values += [label(40, 636, 'Teal inspect; gold direct; gray defer. Shared exact basis is available to both value policies.', 'n'),
        label(40, 663, 'Unknown projection values and incompatible outcome contexts remain explicit nulls in the saved decisions.', 'n'), '</svg>']

    boundary = start(730, 'Public decisions, private execution and evidence-verified closure',
        'One complete synthetic facility. Every arrow is a declared interface; plant truth stays private.')
    boxes = [(40, '#dceff1', 'PUBLIC FRAME + DECLARATIONS', ['Arrived evidence + provenance', 'Static profiles, skills and grants', 'Same catalog/report law/numeric basis', 'Known pending arrivals stay explicit']),
        (510, '#e9e0f2', 'PUBLIC SELECTOR', ['Candidate: test prospective admission', 'Closest baseline: same common inputs', 'Inspect / intervene / defer are legal', 'Count model reads and decision time']),
        (980, '#f4e7d2', 'PRIVATE EXECUTOR', ['Real actor, tool, gate and work time', 'Finite sampling may fail or be missing', 'Named delayed action, residual effects', 'Existing local protection stays active'])]
    for left, color, title, lines in boxes:
        boundary += ['<rect x="%d" y="135" width="420" height="245" rx="12" fill="%s"/>' % (left, color), label(left + 15, 174, title, 'b')]
        boundary += [label(left + 15, 217 + i * 39, text, 'n') for i, text in enumerate(lines)]
    boundary += ['<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#087f8c"/></marker></defs>',
        '<path d="M460 258H508M930 258H978" stroke="#087f8c" stroke-width="4" fill="none" marker-end="url(#arrow)"/>',
        '<path d="M1190 380V430H250V382" stroke="#087f8c" stroke-width="4" fill="none" marker-end="url(#arrow)"/>',
        label(408, 418, 'Only actual arrived records and task-local feedback return', 'n'),
        label(40, 487, 'Forecast regime', 'h'), label(40, 523, 'Explicit uncalibrated per-world report-support assumption; never forced onto the actual producer.', 'b'),
        label(40, 570, 'Closure gate', 'h'), label(40, 606, 'Completion → pending verification. No post-action restoration evidence means the risk remains open.', 'b'),
        label(40, 664, 'Scope: ticket 26 engineering. Cross-system replay 27 and full negative controls 28 remain required.', 'n'),
        label(40, 699, 'Registered effectiveness trials: 0. Field calibration PENDING. AI/RSI deferred until eligibility.', 'n'), '</svg>']
    return {name: ('\n'.join(lines) + '\n').encode() for name, lines in (
        ('actual-online.svg', actual), ('decision-values.svg', values), ('candidate-boundary.svg', boundary))}


def append(path, value):
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def capture(folder, protocol):
    require(not git('status', '--porcelain'), 'Use a clean frozen execution checkout')
    require(Path(os.environ.get('PYTHONPATH', '')).resolve() == ROOT / 'src', 'Set PYTHONPATH=src')
    source = git('rev-parse', 'HEAD').decode().strip()
    identities = pins(protocol, source)
    require(unchanged(source, identities), 'Initial source pins differ')
    require(check_pairs(protocol), 'Pair declarations differ')
    folder.mkdir(exist_ok=False)
    write(folder / 'attempt.json', dict(classification=protocol['classification'], execution_commit=source,
        argv=sys.argv, executable=sys.executable, executable_sha256=digest(Path(sys.executable).read_bytes()), python=sys.version,
        declared_selector_calls=protocol['pure_selector_calls'], declared_physical_runs=protocol['physical_runs'],
        declared_simulated_duration_s=protocol['total_simulated_duration_s']))
    receipt = dict(schema='aegisdc-candidate-engineering-receipt-v1', execution_commit=source, pinned=identities,
        pure_attempts=0, pure_completed=0, physical_attempts=0, physical_completed=0, validated_cases=0,
        simulated_duration_attempted_s=0, failures=0, registered_research_trials=0, llm_calls=0, training_calls=0,
        field_calibration='PENDING', global_regression_gate='PENDING_ROOT_INTEGRATED_FULL')
    try:
        from aegis_dc.dispatch_policy import choose_work
        from aegis_dc.plant import simulate_scenario, save_run
        for kind, cases in (('pure', protocol['pure_cases']), ('physical', protocol['physical_cases'])):
            for case in cases:
                require(unchanged(source, identities), 'Source changed before case')
                document = read(ROOT / case['input'])
                receipt[kind + '_attempts'] += 1
                if kind == 'physical':
                    receipt['simulated_duration_attempted_s'] += case['duration_s']
                append(folder / 'attempts.jsonl', dict(case=case['id'], kind=kind, status='STARTED', execution_commit=source))
                try:
                    if kind == 'pure':
                        path = folder / case['id']
                        path.mkdir()
                        started = perf_counter_ns()
                        result = choose_work(document['frame'], document['policy_program'], document['history'])
                        elapsed = perf_counter_ns() - started
                        receipt['pure_completed'] += 1
                        write(path / 'decision.json', result)
                        write(path / 'computation.json', dict(elapsed_ns=elapsed, model_evaluations=result['model_evaluations'],
                            scope='DIAGNOSTIC_WALL_TIME_NOT_PHYSICAL_TIME_OR_POLICY_INPUT'))
                        check_decision(folder, case, protocol)
                    else:
                        result = simulate_scenario(document['model'], duration_s=case['duration_s'],
                            step_s=protocol['maximum_step_s'], dispatch_program=document['dispatch_program'])
                        receipt['physical_completed'] += 1
                        save_run(result, folder / case['id'])
                        check_physical(folder, case, protocol)
                    receipt['validated_cases'] += 1
                    append(folder / 'attempts.jsonl', dict(case=case['id'], kind=kind, status='COMPLETED', execution_commit=source))
                except Exception as error:
                    append(folder / 'attempts.jsonl', dict(case=case['id'], kind=kind, status='FAILED',
                        execution_commit=source, error_type=type(error).__name__, error=str(error)))
                    raise
        checks = check_saved(folder, protocol)
        write(folder / 'checks.json', checks)
        for name, raw in figures(folder, checks, protocol).items():
            write(folder / name, raw)
        require(durable(folder) == declared(protocol), 'Durable output set differs')
        receipt['status'] = 'PASS'
    except Exception as error:
        receipt.update(status='FAIL', failures=1, error_type=type(error).__name__, error=str(error))
        raise
    finally:
        receipt['source_head_and_bytes_unchanged'] = unchanged(source, identities)
        if not receipt['source_head_and_bytes_unchanged']:
            receipt.update(status='FAIL', failures=1, source_guard_error='Source changed during capture')
        receipt['artifacts'] = {name: digest((folder / name).read_bytes()) for name in sorted(durable(folder))}
        write(folder / protocol['terminal_receipt'], receipt)
    require(receipt['status'] == 'PASS', 'Frozen capture source/receipt failed')
    return dict(status=receipt['status'], execution=source, selector_calls=receipt['pure_attempts'],
        physical_runs=receipt['physical_attempts'], simulated_duration_s=receipt['simulated_duration_attempted_s'])


def verify(folder, protocol, delivery):
    require(git('rev-parse', 'HEAD').decode().strip() == delivery and not git('status', '--porcelain'), 'Use clean declared delivery checkout')
    receipt = read(folder / protocol['terminal_receipt'])
    source = receipt['execution_commit']
    require(receipt['status'] == 'PASS' and receipt['failures'] == 0 and receipt['source_head_and_bytes_unchanged'], 'Original capture failed')
    require(receipt['pure_attempts'] == receipt['pure_completed'] == protocol['pure_selector_calls'], 'Selector attempt budget differs')
    require(receipt['physical_attempts'] == receipt['physical_completed'] == protocol['physical_runs'] and
        receipt['simulated_duration_attempted_s'] == protocol['total_simulated_duration_s'], 'Physical attempt budget differs')
    all_cases = [('pure', case) for case in protocol['pure_cases']] + [('physical', case) for case in protocol['physical_cases']]
    require(receipt['validated_cases'] == len(all_cases), 'Validated case count differs')
    require(set(receipt['artifacts']) == declared(protocol) and durable(folder) == declared(protocol) | {protocol['terminal_receipt']}, 'Durable declaration differs')
    for name, value in hashes(delivery, [(folder / n).relative_to(ROOT).as_posix() for n in durable(folder)]).items():
        require(digest((ROOT / name).read_bytes()) == value, 'Committed delivery blob differs')
    for name, value in receipt['artifacts'].items():
        require(digest((folder / name).read_bytes()) == value, 'Original artifact differs')
    require(receipt['pinned'] == pins(protocol, source), 'Execution pin role sets differ')
    for role, identities in receipt['pinned'].items():
        require(identities == hashes(delivery, identities) and all(digest((ROOT / name).read_bytes()) == value for name, value in identities.items()), 'Execution/delivery pin differs: ' + role)
    ledger = rows(folder / 'attempts.jsonl')
    require(len(ledger) == 2 * len(all_cases), 'Attempt ledger count differs')
    for index, (kind, case) in enumerate(all_cases):
        pair = ledger[index * 2:index * 2 + 2]
        require([row['status'] for row in pair] == ['STARTED', 'COMPLETED'] and
            all(row['case'] == case['id'] and row['kind'] == kind and row['execution_commit'] == source for row in pair), 'Attempt/source order differs')
        if kind == 'physical':
            identity = read(folder / case['id'] / 'run.json')['code_identity']
            require(identity['git_commit'] == source and not identity['implementation_has_changes'], 'Actual execution source differs')
            require(all(name in receipt['pinned']['runtime'] and receipt['pinned']['runtime'][name] == value for name, value in identity['files'].items()), 'Actual runtime files differ from source guard')
    checks = check_saved(folder, protocol)
    require(checks == read(folder / 'checks.json'), 'Saved check recomputation differs')
    for name, raw in figures(folder, checks, protocol).items():
        require(raw == (folder / name).read_bytes(), 'Saved figure recomputation differs')
    return dict(status='PASS', execution=source, delivery=delivery, selector_calls=receipt['pure_attempts'],
        physical_runs=receipt['physical_attempts'], simulated_duration_s=receipt['simulated_duration_attempted_s'],
        artifacts=len(receipt['artifacts']), pins={role: len(items) for role, items in receipt['pinned'].items()},
        new_physical_runs=0, new_selector_calls=0, full_regression_rerun=False, runtime_caches_required=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['capture', 'verify'])
    parser.add_argument('--capture', required=True, type=Path)
    parser.add_argument('--delivery')
    args = parser.parse_args()
    folder = (ROOT / args.capture).resolve()
    require(folder.parent == ROOT / PACKAGE, 'Use a new declared candidate output directory')
    protocol = read(ROOT / PROTOCOL)
    print(json.dumps(capture(folder, protocol) if args.mode == 'capture' else verify(folder, protocol, args.delivery), ensure_ascii=False))
