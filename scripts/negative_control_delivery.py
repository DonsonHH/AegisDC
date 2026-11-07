"""Capture or verify the frozen ticket 28 negative engineering cases."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import subprocess
from pathlib import Path
import sys
import zipfile

from inspection_delivery import ROOT, digest, durable, git, hashes, read, require, unchanged, write
from negative_control_checks import check_case, paired
from negative_control_history import check_history, lineage

PROTOCOL = 'docs/mainline/28-negative-engineering-protocol-v3.json'


def append(path, value):
    with path.open('ab') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n').encode())
        stream.flush()
        os.fsync(stream.fileno())


def pins(protocol, source):
    tracked = git('ls-tree', '-rz', '--name-only', source, 'src').decode().strip('\0').split('\0')
    reference = read(ROOT / protocol['input'])
    properties = {case['model']['runtime']['property_table'] for case in reference['cases'].values()}
    preparation = read(ROOT / protocol['preparation'])
    idle = read(ROOT / protocol['protection_workforce_preparation'])
    roles = dict(runtime=[p for p in tracked if p.endswith('.py') and '__pycache__' not in p],
        tools=protocol['tools'], inputs=[PROTOCOL, protocol['contract'], protocol['input'],
            protocol['literals'], protocol['preparation'], protocol['protection_workforce_input'],
            protocol['protection_workforce_preparation'], *protocol['retained_context'], *properties,
            *preparation['source_inputs'], *idle['source_inputs']],
        retained_draft=protocol['retained_unexecuted_draft'], retained_review=protocol['retained_failed_reviews'])
    result = {role: hashes(source, paths) for role, paths in roles.items()}
    require(all(digest((ROOT / name).read_bytes()) == sha for group in result.values() for name,sha in group.items()),
            'Working inputs or tools differ from exact committed source')
    for name, sha in preparation['source_inputs'].items():
        require(result['inputs'][name] == sha, 'Preparation source input differs')
    for name, sha in preparation['outputs'].items():
        require(digest((ROOT / protocol['input']).parent.joinpath(name).read_bytes()) == sha,
                'Prepared output differs from its author receipt')
    require(preparation['authoring_tool_sha256'] == result['tools']['scripts/prepare_negative_control_inputs_v4.py'],
            'Physical-case authoring tool differs')
    for name, sha in idle['source_inputs'].items():
        require(result['inputs'][name] == sha, 'Idle-crew preparation source differs')
    require(idle['artifacts'] == {'idle-crew.json': result['inputs'][protocol['protection_workforce_input']]}
            and idle['authoring_tool_sha256'] == result['tools']['scripts/prepare_negative_control_workforce.py'],
            'Idle-crew tool or input differs')
    from preserve_negative_control_reviews import verify as verify_preserved_reviews
    old_review = verify_preserved_reviews()
    review_paths = [ROOT / name for name in protocol['retained_failed_reviews']]
    parents = {path.parent for path in review_paths}
    require(len(parents) == 1 and durable(review_paths[0].parent) == {path.name for path in review_paths},
            'Retained review package has unlisted durable files')
    with zipfile.ZipFile(review_paths[0].parent / 'originals.zip') as archive:
        for name, sha in protocol['retained_review_seal_sha256'].items():
            require(digest(archive.read(name)) == sha, 'Original failed review seal changed')
    require(old_review['source'] == protocol['supersedes_unexecuted_source']
            and old_review['members'] == 222, 'Original failed pre-capture reviews changed')
    result.update(lineage(protocol, source))
    check_history(protocol, result['runtime'])
    return result


def declared(protocol):
    return set(protocol['durable_root']) | {
        name + '/' + file for name in protocol['cases'] for file in protocol['durable_case']
    } | {name + '/' + file for name, files in protocol['durable_case_extra'].items() for file in files}


def reviews(source, files):
    reports, originals = {}, {}
    require(len(files) == 2, 'Two independent source-bound review reports are required')
    for file in files:
        report = read(file)
        axis = report.get('axis')
        require(axis in {'Spec','Standards'} and axis not in reports
                and report.get('source',report.get('data')) == source and report['status'].startswith('PASS')
                and not report.get('unresolved') and report['checks'] > 0, 'Review did not accept this fixed source')
        manifest_path = next((file.parent / name for name in ('manifest.json','delivery-manifest.json')
                              if (file.parent / name).is_file()), None)
        require(manifest_path is not None, 'Review has no immutable artifact manifest')
        seal = read(manifest_path)
        names = set(seal['artifacts'])
        require(file.name in names, 'Review verdict is not sealed')
        for name, expected in seal['artifacts'].items():
            raw = file.parent.joinpath(name).read_bytes()
            require(digest(raw) == expected['sha256'] and len(raw) == expected['bytes'], 'Independent review file changed')
            originals[axis + '/' + name] = raw
        originals[axis + '/' + manifest_path.name] = manifest_path.read_bytes()
        reports[axis] = dict(source=source, checks=report['checks'], status=report['status'], unresolved=report['unresolved'],
            report=axis + '/' + file.name, report_sha256=digest(file.read_bytes()),
            manifest=axis + '/' + manifest_path.name, manifest_sha256=digest(manifest_path.read_bytes()))
    require(set(reports) == {'Spec','Standards'}, 'Both review axes are required')
    return reports, originals


def execute(case, folder, counters, protocol):
    # The saved V2-compatible envelope is static input. This author uses the
    # declared public scenario seam once, not the replay transport or a selector
    # call outside the online program. Actual random measurement laws are in
    # the sensor and inspection realizations, preserved in the run inputs.
    from aegis_dc.plant import save_run, simulate_scenario
    options = {}
    gateway = None
    frames = []
    proposal = None
    if case['kind'] == 'online_dispatch':
        envelope = case['replay_inputs']
        options = dict(dispatch_program=deepcopy(envelope['dispatch_program']),
            boundary_events=deepcopy(envelope['exogenous_events']),
            action_commands=deepcopy(envelope['action_commands']), work_requests=deepcopy(envelope['work_requests']))
    elif case['kind'] == 'plant_without_manual_dispatch':
        from aegis_dc.decision_view import DecisionGateway
        idle = read(ROOT / protocol['protection_workforce_input'])
        counters['protection_initial_frames'] += 1
        initial = DecisionGateway(idle['nominal_knowledge'], idle['evidence_ledger'], idle['plan']).next_frame()
        write(folder / 'idle-crew-frame.json', initial)
        options = dict(boundary_events=deepcopy(case['boundary_events']),
            work_program=dict(schema='aegisdc-work-program-v2', id='ticket28-no-manual-jobs',
                profile=deepcopy(idle['profile']), initial_frame=initial, submissions=[]))
    elif case['kind'] == 'report_triggered_crew':
        from aegis_dc.decision_view import DecisionGateway
        from aegis_dc.intervention_execution import prepare_intervention
        declaration = case['public_preparation']
        task = declaration['task']
        plan = dict(schema='aegisdc-public-preparation-plan-v1', id='ticket28-late-public-clock',
            basis='synthetic_assumption', time_unit='s', decision_times_s=declaration['decision_times_s'],
            requests=deepcopy(declaration['requests']))
        gateway = DecisionGateway(declaration['nominal_knowledge'], declaration['evidence_ledger'], plan)
        for _ in range(2):
            counters['late_preparation_frames'] += 1
            frames.append(gateway.next_frame())
        require(frames[-1]['as_of_s'] == declaration['issued_at_s']
                and declaration['trigger_record_id'] in frames[-1]['evidence']['current_record_ids']
                and declaration['trigger_record_id'] not in frames[0]['evidence']['current_record_ids'],
                'Report is not available at the declared issue instant')
        counters['late_preparation_assessments'] += 1
        proposal = prepare_intervention(frames[-1], declaration['workforce_profile'], task,
            case['intervention_program']['profile'], case['intervention_program']['bindings'][0])
        write(folder / 'pre-call-preparation.json', dict(frames=frames, proposal=proposal))
        options = dict(boundary_events=deepcopy(case['boundary_events']),
            intervention_program=deepcopy(case['intervention_program']),
            work_program=dict(schema='aegisdc-work-program-v2', id='ticket28-report-triggered-crew',
                profile=deepcopy(declaration['workforce_profile']), initial_frame=deepcopy(frames[0]),
                submissions=[dict(frame=deepcopy(frames[-1]), task=deepcopy(task))]))
    else:
        raise ValueError('Unknown finite engineering case kind')
    counters['attempted_integrations'] += 1
    run = simulate_scenario(case['model'], duration_s=case['duration_s'], step_s=case['maximum_step_s'], **options)
    counters['completed_integrations'] += 1
    save_run(run, folder / 'trajectory')
    if gateway is not None:
        from aegis_dc.verified_closure import assess_closure
        assessments = []
        for _ in range(2):
            counters['late_preparation_frames'] += 1
            frame = gateway.next_frame()
            frames.append(frame)
            program = deepcopy(case['closure_program'])
            program['intervention_feedback'] = [deepcopy(report) for report in run['intervention_public_feedback']
                if report['arrived_at_s'] <= frame['as_of_s']]
            counters['late_closure_assessments'] += 1
            assessments.append(assess_closure(frame, program))
        write(folder / 'public-preparation.json', dict(frames=frames, proposal=proposal))
        write(folder / 'closure.json', assessments)
    return run


def check_review_archive(folder, summary):
    with zipfile.ZipFile(folder / 'reviews.zip') as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), 'Repeated review archive member')
        expected = set()
        for axis, row in summary.items():
            require(axis in {'Spec','Standards'} and row['checks'] > 0 and not row['unresolved']
                    and row['status'].startswith('PASS'), 'Independent review no longer passed')
            require(digest(archive.read(row['report'])) == row['report_sha256']
                    and digest(archive.read(row['manifest'])) == row['manifest_sha256'], 'Review seal changed')
            report = json.loads(archive.read(row['report']))
            require(report.get('source',report.get('data')) == row['source'], 'Review source mismatch')
            manifest = json.loads(archive.read(row['manifest']))['artifacts']
            expected.add(row['manifest'])
            for name, pin in manifest.items():
                path = axis + '/' + name
                raw = archive.read(path)
                require(digest(raw) == pin['sha256'] and len(raw) == pin['bytes'], 'Review artifact changed')
                expected.add(path)
        require(set(summary) == {'Spec','Standards'} and set(archive.namelist()) == expected, 'Review archive role set differs')


def capture(protocol, review_files):
    source = git('rev-parse', 'HEAD').decode().strip()
    require(not git('status', '--porcelain'), 'Freeze and commit inputs and tools before capture')
    require(protocol['status'] == 'FROZEN_ENGINEERING_REQUIRES_INDEPENDENT_FIXED_SOURCE_REVIEW',
            'No frozen engineering protocol')
    identities = pins(protocol, source)
    history = check_history(protocol, identities['runtime'])
    reviewed, review_bytes = reviews(source, review_files)
    folder = ROOT / protocol['output']
    require(not folder.exists(), 'Attempt directory exists; never retry or overwrite')
    folder.mkdir(parents=True)
    write(folder / 'capture.json', dict(status='STARTED', source=source, pins=identities,
        reviews=reviewed, retained_history=history, declared_artifacts=sorted(declared(protocol)), terminal='receipt.json',
        utc=datetime.now(timezone.utc).isoformat(), executable=sys.executable, python=sys.version,
        executable_sha256=digest(Path(sys.executable).read_bytes()), registered_research_trials=0))
    with zipfile.ZipFile(folder / 'reviews.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(review_bytes.items()):
            archive.writestr(name, raw)
    cases = read(ROOT / protocol['input'])['cases']
    oracle = read(ROOT / protocol['literals'])
    counters = dict(attempted_integrations=0, completed_integrations=0, validated_cases=0,
        late_preparation_frames=0, late_preparation_assessments=0, late_closure_assessments=0, protection_initial_frames=0,
        attempted_simulated_seconds=0)
    receipt = dict(status='FAIL', source=source, pins=identities, counters=counters,
        retained_history=history, error=None, source_guard=False, registered_research_trials=0)
    try:
        checks = {}
        sys.path.insert(0, str(ROOT / 'src'))
        for name in protocol['cases']:
            case = cases[name]
            path = folder / name
            path.mkdir()
            write(path / 'input.json', case)
            append(folder / 'attempts.jsonl', dict(case=name, status='STARTED', source=source, kind=case['kind'],
                duration_s=case['duration_s'], utc=datetime.now(timezone.utc).isoformat()))
            counters['attempted_simulated_seconds'] += case['duration_s']
            try:
                execute(case, path, counters, protocol)
                checks[name] = check_case(path, name, case, oracle, protocol, source, identities)
                write(path / 'validation.json', checks[name])
                counters['validated_cases'] += 1
                append(folder / 'attempts.jsonl', dict(case=name, status='COMPLETED', source=source,
                    utc=datetime.now(timezone.utc).isoformat()))
            except Exception as error:
                append(folder / 'attempts.jsonl', dict(case=name, status='FAILED', source=source,
                    error_type=type(error).__name__, error=str(error), utc=datetime.now(timezone.utc).isoformat()))
                raise
        checks['paired_normal_false_report'] = paired(folder)
        require(counters == protocol['expected_counters'], 'Frozen physical/public evaluation budget differs')
        write(folder / 'checks.json', checks)
        require(durable(folder) == declared(protocol), 'Frozen durable output set differs')
        receipt['status'] = 'PASS'
    except Exception as error:
        receipt.update(error=dict(type=type(error).__name__, message=str(error)))
    finally:
        try:
            receipt['source_guard'] = unchanged(source, identities)
        except (OSError, subprocess.SubprocessError) as error:
            receipt.update(source_guard=False, source_guard_error=str(error))
        if not receipt['source_guard']:
            receipt['status'] = 'FAIL'
        receipt['artifacts'] = {name: digest((folder / name).read_bytes()) for name in sorted(durable(folder))}
        write(folder / 'receipt.json', receipt)
    require(receipt['status'] == 'PASS', 'Frozen negative engineering capture failed; retain records and stop')
    return dict(status='PASS', source=source, counters=counters, scope='FINITE_ENGINEERING_NOT_METHOD_GAIN')


def verify(protocol, delivery):
    require(git('rev-parse','HEAD').decode().strip() == delivery and not git('status','--porcelain'),
            'Verify saved files from a clean committed delivery')
    folder = ROOT / protocol['output']
    receipt, capture = (read(folder / name) for name in ('receipt.json','capture.json'))
    source = receipt['source']
    require(receipt['status'] == 'PASS' and receipt['source_guard'] and receipt['counters'] == protocol['expected_counters']
            and capture['source'] == source and capture['pins'] == receipt['pins'], 'Author capture did not pass')
    names = declared(protocol)
    require(set(receipt['artifacts']) == names and durable(folder) == names | {'receipt.json'}
            and capture['declared_artifacts'] == sorted(names), 'Durable delivery role set differs')
    for name, sha in receipt['artifacts'].items():
        require(digest((folder / name).read_bytes()) == sha, 'Original negative-control artifact differs: ' + name)
    paths = [folder.relative_to(ROOT).as_posix() + '/' + name for name in names | {'receipt.json'}]
    require(all(digest((ROOT / name).read_bytes()) == sha for name,sha in hashes(delivery, paths).items()),
            'Committed delivery differs from original durable bytes')
    require(pins(protocol, source) == receipt['pins'], 'Author tool/input/runtime identity differs')
    history = check_history(protocol, receipt['pins']['runtime'])
    require(history == capture['retained_history'] == receipt['retained_history'], 'Retained attempt accounting differs')
    for group in receipt['pins'].values():
        require(group == hashes(delivery, group), 'Delivery source/tool/input set differs from execution revision')
    for row in capture['reviews'].values():
        require(row['source'] == source, 'Independent review is not bound to the execution source')
    check_review_archive(folder, capture['reviews'])
    ledger = [json.loads(line) for line in (folder / 'attempts.jsonl').read_bytes().splitlines()]
    require([(row['case'],row['status'],row['source']) for row in ledger] ==
            [(name,status,source) for name in protocol['cases'] for status in ('STARTED','COMPLETED')],
            'Frozen lifecycle ledger differs')
    require(sum(row['duration_s'] for row in ledger if row['status'] == 'STARTED') == 21.5, 'Started duration budget differs')
    cases = read(ROOT / protocol['input'])['cases']
    oracle = read(ROOT / protocol['literals'])
    checks = {name: check_case(folder / name, name, cases[name], oracle, protocol, source, receipt['pins']) for name in protocol['cases']}
    require(all(read(folder / name / 'validation.json') == checks[name] for name in protocol['cases']),
            'A saved per-case check differs from original data')
    checks['paired_normal_false_report'] = paired(folder)
    require(read(folder / 'checks.json') == checks, 'Saved checks do not recompute from originals')
    return dict(status='PASS', execution_source=source, delivery=delivery, artifacts=len(names),
        completed_integrations=4, simulated_seconds=21.5, public_online_decisions=14,
        late_preparation_frames=4, late_closure_assessments=2, protection_initial_frames=1,
        pins={role: len(group) for role,group in receipt['pins'].items()},
        retained_history=history, new_physics=0, new_selector_calls=0, new_closure_calls=0, registered_research_trials=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('capture','verify'))
    parser.add_argument('--delivery')
    parser.add_argument('--spec-review', type=Path)
    parser.add_argument('--standards-review', type=Path)
    args = parser.parse_args()
    protocol = read(ROOT / PROTOCOL)
    if args.mode == 'capture':
        require(args.spec_review is not None and args.standards_review is not None, 'Supply both fixed-source review files')
        result = capture(protocol, [args.spec_review, args.standards_review])
    else:
        require(args.delivery is not None, 'Supply the clean delivery commit')
        result = verify(protocol, args.delivery)
    print(json.dumps(result, ensure_ascii=False))
