"""Verify closed service/replay development packages; never run project code."""
import argparse
import json
from pathlib import Path
import zipfile

from full_loop_development import FILES, PACKAGE, ROOT, digest, durable, git, require, verify as verify_v1, write


TOOL = Path(__file__).relative_to(ROOT).as_posix()


def root_members(folder):
    return {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and durable(p.relative_to(folder).as_posix())}


def verify_service(folder, delivery):
    require(root_members(folder) == FILES, 'Unexpected nested development artifact')
    declaration = json.loads((folder / 'declaration.json').read_bytes())
    cases = declaration['cases']
    require(type(cases) is list and len(cases) == len(set(cases)), 'Duplicate service attempt declaration')
    with zipfile.ZipFile(folder / 'originals.zip') as archive:
        names = set(archive.namelist())
        require({name.split('/')[0] for name in names} == set(cases), 'Service archive case set differs')
        for case in cases:
            prefix = case + '/'
            attempt = json.loads(archive.read(prefix + 'attempt.json'))
            terminal = json.loads(archive.read(prefix + 'terminal.json'))
            expected = {'attempt.json', 'terminal.json', 'input.json'} | {'pre-call/' + p for p in attempt['source_files']}
            if terminal['integration_returned']:
                expected |= {'original/' + name for name in ('run.json', 'scenario.json', 'private-state.jsonl', 'balances.jsonl')}
            require({name.removeprefix(prefix) for name in names if name.startswith(prefix)} == expected, 'Service original member roles differ')
    return verify_v1(folder, delivery)


def replay_checks(folder, delivery):
    require(root_members(folder) == FILES, 'Unexpected nested replay artifact')
    declaration, receipt, manifest = (json.loads((folder / name).read_bytes()) for name in ('declaration.json', 'receipt.json', 'members.json'))
    require(set(declaration['artifacts']) == set(receipt['artifacts']) == FILES - {'receipt.json'}, 'Replay durable declaration differs')
    require(receipt['tool_sha256'] == digest((ROOT / TOOL).read_bytes()), 'Replay packager identity differs')
    for name, identity in receipt['artifacts'].items():
        require(digest((folder / name).read_bytes()) == identity, 'Replay durable identity differs')
    for name, identity in declaration['support'].items():
        require(digest((ROOT / name).read_bytes()) == identity, 'Replay tool or log changed')
    if delivery:
        require(git('rev-parse', 'HEAD').decode().strip() == delivery and not git('status', '--porcelain'), 'Use a clean replay delivery revision')
        for path in [*(folder / name for name in FILES), ROOT / TOOL, *(ROOT / name for name in declaration['support'])]:
            require(path.read_bytes() == git('cat-file', 'blob', delivery + ':' + path.relative_to(ROOT).as_posix()), 'Committed replay blob differs')
    cases = declaration['cases']
    require(len(cases) == len(set(cases)) and len(cases) == 6, 'Expected six separately preserved record/replay attempts')
    summaries, completed, origins = [], {}, {}
    with zipfile.ZipFile(folder / 'originals.zip') as archive:
        names = set(archive.namelist())
        require(len(names) == len(archive.namelist()) and names == set(manifest), 'Replay ZIP member set differs')
        require({name.split('/')[0] for name in names} == {*cases, 'reader-boundaries'}, 'Replay ZIP case roots differ')
        require({name for name in names if name.startswith('reader-boundaries/')} == set(declaration['reader_fixtures']), 'Saved reader fixture set differs')
        for name, identity in manifest.items():
            raw = archive.read(name)
            require(durable(name) and digest(raw) == identity['sha256'] and len(raw) == identity['bytes'], 'Replay ZIP identity differs')
        for case in cases:
            prefix = case + '/'
            def member(name):
                return json.loads(archive.read(prefix + name))
            outer, submitted = member('development-attempt.json'), member('input.json')
            record = member('recorded/attempt.json')
            recorded_declaration = member('recorded/declaration.json')
            require(outer['status'] == 'STARTED' and record['source_identity']['git_commit'] == outer['source_commit'], 'Replay lifecycle source differs')
            require({name.removeprefix(prefix) for name in names if name.startswith(prefix)} ==
                {'development-attempt.json', 'input.json', 'recorded/attempt.json'} |
                {'pre-call/' + name for name in outer['source_files']} |
                {'recorded/' + name for name in record['artifacts']}, 'Replay original member roles differ')
            require(set(record['artifacts']) <= set(recorded_declaration['allowed_before_finalization']), 'Replay original exceeds its declaration')
            for name, value in outer['source_files'].items():
                require(digest(archive.read(prefix + 'pre-call/' + name)) == value, 'Replay precall snapshot differs')
            for name, value in record['source_identity']['files'].items():
                require(outer['source_files'][name] == value, 'Recorded actual runtime source differs from snapshot')
            for name, value in record['artifacts'].items():
                require(digest(archive.read(prefix + 'recorded/' + name)) == value, 'Recorded original artifact differs')
            lifecycle = [json.loads(line) for line in archive.read(prefix + 'recorded/lifecycle.jsonl').splitlines()]
            require([row['state'] for row in lifecycle] == ['STARTED', record['status']], 'Recorded lifecycle differs')
            require(member('recorded/inputs.json') == submitted['replay_inputs'] and member('recorded/scenario-input.json') == submitted['model'], 'Submitted replay inputs differ')
            if record['status'] == 'COMPLETED':
                run = member('recorded/trajectory/run.json')
                require(set(record['artifacts']) == set(recorded_declaration['required_when_completed']), 'Completed run is missing durable originals')
                require(run['code_identity']['files'] == record['source_identity']['files'], 'Actual run source does not bind replay')
                require(run['inputs']['dispatch_program'] == member('recorded/frozen-inputs.json')['dispatch_program'], 'Actual run dispatch differs')
                effects = run['intervention_private_audit']['events']
                require(len(effects) == 1 and (effects[0]['applied_at_s'], effects[0]['old_value'], effects[0]['new_value']) == (1.25, 4, 1), 'Named actual effect differs')
                for row in run['policy_computation_audit']:
                    require(type(row['elapsed_ns']) is int and row.pop('elapsed_ns') >= 0, 'Diagnostic wall time missing')
                require(outer['operation'] not in completed, 'Duplicate completed replay role')
                completed[outer['operation']] = (run, record['artifacts']['trajectory/private-state.jsonl'], record['artifacts']['trajectory/balances.jsonl'])
                origins[outer['operation']] = (record['attempt_id'], digest(archive.read(prefix + 'recorded/attempt.json')),
                    record['replay_of'], record['artifacts'].get('origin/attempt.json'))
            else:
                require(record['status'] == 'FAILED' and record['execution_kind'] == 'NOT_STARTED' and
                    record['failure']['stage'] == 'validate_inputs', 'Invalid attempt was relabeled')
            summaries.append(dict(case=case, operation=outer['operation'], status=record['status']))
    require(set(completed) == {'record', 'replay'} and completed['record'] == completed['replay'], 'Deterministic replay output differs')
    original_id, original_sha, _, _ = origins['record']
    _, _, origin, copied = origins['replay']
    require(origin == dict(attempt_id=original_id, attempt_sha256=original_sha, mode='EXACT_REEXECUTION')
        and copied == original_sha, 'Replayed attempt is not bound to its exact origin')
    require(summaries == receipt['attempts'] and len(manifest) == receipt['members'], 'Replay receipt differs')
    return dict(status='PASS_SAVED_REPLAY_DEVELOPMENT_ONLY', attempts=summaries, members=len(manifest),
        completed_physical_runs=2, elapsed_ns_only_excluded=True, delivery=delivery, new_project_calls=0)


def seal_replay(folder):
    folder.mkdir(exist_ok=False)
    base = ROOT / '.work/27-replay-development'
    reader = ROOT / '.work/27-replay-boundary-fixtures'
    cases = sorted(p.name for p in base.iterdir() if p.is_dir())
    files = {case + '/' + name: base / case / name for case in cases for name in root_members(base / case)}
    auxiliary = {'reader-boundaries/' + name: reader / name for name in root_members(reader)}
    files.update(auxiliary)
    support = ['scripts/check_full_loop_replay_boundaries.py', 'tests/test_full_loop_replay.py']
    support += [(PACKAGE / 'development' / name).relative_to(ROOT).as_posix() for name in
        ('05-recorded-online-dispatch-red.log', '06-recorded-online-dispatch-green.log', '07-replay-boundaries-saved-check.log')]
    write(folder / 'declaration.json', dict(artifacts=sorted(FILES - {'receipt.json'}), cases=cases,
        reader_fixtures=sorted(auxiliary), support={name: digest((ROOT / name).read_bytes()) for name in support},
        cache_classification='EXCLUDED_RUNTIME_CACHES'))
    members = {}
    with zipfile.ZipFile(folder / 'originals.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            raw = path.read_bytes()
            archive.writestr(name, raw)
            members[name] = dict(sha256=digest(raw), bytes=len(raw))
    write(folder / 'members.json', members)
    attempts = []
    for case in cases:
        outer = json.loads((base / case / 'development-attempt.json').read_bytes())
        record = json.loads((base / case / 'recorded/attempt.json').read_bytes())
        attempts.append(dict(case=case, operation=outer['operation'], status=record['status']))
    write(folder / 'receipt.json', dict(tool=TOOL, tool_sha256=digest((ROOT / TOOL).read_bytes()), members=len(members),
        attempts=attempts, artifacts={name: digest((folder / name).read_bytes()) for name in FILES - {'receipt.json'}},
        classification='DEVELOPMENT_RECORD_AND_REPLAY_ORIGINALS_NOT_FORMAL_CAPTURE'))
    return replay_checks(folder, None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['verify-service', 'seal-replay', 'verify-replay'])
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--delivery')
    args = parser.parse_args()
    folder = (ROOT / args.package).resolve()
    require(folder.parent == PACKAGE, 'Use a declared ticket27 package')
    result = (seal_replay(folder) if args.mode == 'seal-replay' else
              verify_service(folder, args.delivery) if args.mode == 'verify-service' else replay_checks(folder, args.delivery))
    print(json.dumps(result, ensure_ascii=False))
