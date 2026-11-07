"""Verify retained attempt and public-validation bytes without importing AegisDC."""
import json

from inspection_delivery import ROOT, digest, durable, git, hashes, read, require
from prepare_negative_control_inputs_v5 import neutralize
from prepare_negative_control_inputs_v6 import neutralize_authority


def lineage(protocol, execution_source):
    result = {}
    for role, group in protocol['retained_execution_records'].items():
        scope = group['folder']
        revision = group['delivery']
        names = {f'{scope}/{name}' for name in durable(ROOT / scope)}
        expected = set(git('ls-tree', '-rz', '--name-only', revision, '--', scope).decode().strip('\0').split('\0'))
        require(len(names) == group['files'] and names == expected, f'Retained file roles differ: {role}')
        result[role] = hashes(revision, names)
        require(result[role] == hashes(execution_source, names), f'Retained Git bytes differ: {role}')
        for name, sha in result[role].items():
            require(digest((ROOT / name).read_bytes()) == sha, f'Retained checkout bytes differ: {name}')
    return result


def check_history(protocol, runtime):
    retained = protocol['retained_execution_records']
    def folder(role):
        return ROOT / retained[role]['folder']

    old = folder('failed_capture')
    failure = read(old / 'receipt.json')
    original_source = protocol['retained_failed_source']
    attempt = [json.loads(row) for row in (old / 'attempts.jsonl').read_bytes().splitlines()]
    require(failure['status'] == 'FAIL' and failure['source'] == original_source and failure['source_guard']
            and failure['counters']['attempted_integrations'] == 1
            and failure['counters']['completed_integrations'] == failure['counters']['validated_cases'] == 0
            and failure['counters']['attempted_simulated_seconds'] == 7.25
            and [(row['case'], row['status'], row['source']) for row in attempt] ==
                [('normal', 'STARTED', original_source), ('normal', 'FAILED', original_source)]
            and 'Conservative bounds require' in failure['error']['message'], 'Original failed attempt relabeled')
    require(failure['pins']['runtime'] == runtime, 'Original failed call used different runtime bytes')
    for role in ('failed_capture', 'failed_public_preflight', 'passed_public_preflight', 'public_evidence_preflight'):
        path = folder(role)
        receipt = read(path / 'receipt.json')
        require(durable(path) == set(receipt['artifacts']) | {'receipt.json'}, f'Original terminal roles differ: {role}')
        for name, sha in receipt['artifacts'].items():
            require(digest((path / name).read_bytes()) == sha, f'Original terminal hash differs: {role}/{name}')
    launch = folder('failed_launch')
    terminal = read(launch / 'terminal.json')
    manifest = read(launch / 'manifest.json')
    require(terminal['status'] == 'FAILED' and terminal['returncode'] == 1 and terminal['source'] == original_source
            and set(manifest['identities']) == set(manifest['artifacts']) == durable(launch) - {'manifest.json'},
            'Original failed launch terminal differs')
    for name, sha in manifest['identities'].items():
        require(digest((launch / name).read_bytes()) == sha, f'Failed launch artifact changed: {name}')
    require(all(terminal[f'{name}_sha256'] == manifest['identities'][f'{name}.txt'] for name in ('stdout','stderr')),
            'Original failed launch streams differ')

    first = read(folder('failed_public_preflight') / 'receipt.json')
    passed = folder('passed_public_preflight')
    second = read(passed / 'receipt.json')
    public_budget = dict(validate_scenario_calls=4, initial_public_frames=3, assess_risks_calls=5,
                         physical_calls=0, selector_calls=0, closure_calls=0)
    require(first['status'] == 'FAIL' and 'Risk scope differs' in first['error']['message']
            and second['status'] == 'PASS_PUBLIC_INPUT_VALIDATION_ONLY' and second['error'] is None
            and first['source_guard'] and second['source_guard']
            and first['counters'] == second['counters'] == public_budget,
            'Public-preflight attempts or failure classification changed')
    require(first['source'] == protocol['public_preflight_sources'][0]
            and second['source'] == protocol['public_preflight_sources'][1], 'Public-preflight source changed')
    for receipt in (first, second):
        for group in receipt['pins'].values():
            require(group == hashes(receipt['source'], group),
                    'Original public-preflight inputs/tools differ from their actual execution revision')
        require(receipt['pins']['runtime'] == runtime, 'Public-preflight runtime differs from physical runtime')
    validated_input = protocol['validated_input_before_neutralization']
    require(second['pins']['inputs'][validated_input] == digest((ROOT / validated_input).read_bytes()),
            'Original input that passed public preflight changed')
    document = read(ROOT / protocol['input'])
    public_input = protocol['public_evidence_preflight_input']
    neutral = read(ROOT / public_input)
    require(neutralize(read(ROOT / validated_input)) == neutral and neutralize_authority(neutral) == document,
            'Physical input differs from validated input beyond declared public label neutralization')
    cases = document['cases']
    for name, case in cases.items():
        require(read(passed / 'scenarios' / (name + '.json')) == case['model'], 'Validated model differs: ' + name)
    require(set(read(passed / 'risks.json')) == {'normal', 'false_report', 'too_late'}, 'Preflight risk cases differ')
    require(read(passed / 'frames/too_late.json')['requests'] == cases['too_late']['public_preparation']['requests'],
            'Late preflight public declarations differ')
    evidence = folder('public_evidence_preflight')
    proof = read(evidence / 'receipt.json')
    require(proof['status'] == 'PASS_PUBLIC_EVIDENCE_ONLY' and proof['source_guard'] and proof['error'] is None
            and proof['source'] == protocol['public_evidence_preflight_source']
            and proof['pins']['runtime'] == runtime
            and proof['counters'] == dict(public_frames=6,public_choice_calls=4,standalone_closure_calls=1,physical_calls=0)
            and proof['pins']['inputs'][public_input] == digest((ROOT / public_input).read_bytes()),
            'Public record boundary proof does not use the declared prior input')
    for group in proof['pins'].values():
        require(group == hashes(proof['source'], group), 'Public evidence fixture source roles changed')
    early = read(evidence / 'frame-normal-1.json')
    require(early == read(evidence / 'frame-false_report-1.json'), 'Before-arrival public frame parity differs')
    for name, choice in (('normal-1',None),('normal-3',None),('false_report-1',None),('false_report-3','first-inspection')):
        observed = read(evidence / ('choice-' + name + '.json'))
        require(observed['chosen_candidate_id'] == choice and not observed['execution_permission'],
                'Public decision fixture differs')
    q, = read(evidence / 'closure-false-report-no-measurements.json')['questions']
    require(q['status'] == 'OPEN_UNCONFIRMED' and not q['question_closed'] and not q['risk_closed'],
            'Authorized opinion without arrived measurements closed a question')
    budgets = protocol['cumulative_attempt_budget']
    require(budgets == dict(previous_attempts=1, previous_charged_seconds=7.25, previous_completed=0,
        new_attempt_limit=4, new_charged_seconds_limit=21.5, cumulative_attempt_limit=5,
        cumulative_charged_seconds_limit=28.75), 'Physical continuation budget differs')
    return dict(retained_failure_attempts=1, retained_failure_charged_seconds=7.25,
        retained_failure_completed=0, public_preflight_phase_attempts=2,
        public_preflight_final='PASS_PUBLIC_INPUT_VALIDATION_ONLY',
        public_evidence_preflight='PASS_PUBLIC_EVIDENCE_ONLY',
        cumulative_attempt_limit=5, cumulative_charged_seconds_limit=28.75)
