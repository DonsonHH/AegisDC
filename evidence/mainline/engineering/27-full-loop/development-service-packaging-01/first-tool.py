"""Seal and verify exact ticket 27 development originals without reexecution."""
import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'evidence/mainline/engineering/27-full-loop'
TOOL = Path(__file__).relative_to(ROOT).as_posix()
FILES = {'declaration.json', 'members.json', 'originals.zip', 'receipt.json'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return sha256(raw).hexdigest()


def durable(name):
    p = PurePosixPath(name)
    return (not p.is_absolute() and '..' not in p.parts and '__pycache__' not in p.parts
            and p.suffix not in {'.pyc', '.pyo'})


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def verify(folder, delivery=None):
    receipt = json.loads((folder / 'receipt.json').read_bytes())
    declaration = json.loads((folder / 'declaration.json').read_bytes())
    members = json.loads((folder / 'members.json').read_bytes())
    require({p.name for p in folder.iterdir() if p.is_file()} == FILES, 'Development durable package differs')
    require(set(declaration['artifacts']) == FILES - {'receipt.json'} == set(receipt['artifacts']), 'Development declaration differs')
    for name, identity in receipt['artifacts'].items():
        require(digest((folder / name).read_bytes()) == identity, 'Development artifact hash differs')
    require(receipt['tool_sha256'] == digest((ROOT / TOOL).read_bytes()), 'Development verification tool differs')
    for name, identity in declaration['logs'].items():
        require(digest((ROOT / name).read_bytes()) == identity, 'Original test log hash differs')
    if delivery:
        require(git('rev-parse', 'HEAD').decode().strip() == delivery and not git('status', '--porcelain'), 'Use clean delivery revision')
        for path in [*(folder / name for name in FILES), ROOT / TOOL, *(ROOT / name for name in declaration['logs'])]:
            require(path.read_bytes() == git('cat-file', 'blob', delivery + ':' + path.relative_to(ROOT).as_posix()), 'Committed original blob differs')
    attempts = []
    with zipfile.ZipFile(folder / 'originals.zip') as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(members), 'Development member set differs')
        for name, identity in members.items():
            raw = archive.read(name)
            require(durable(name) and digest(raw) == identity['sha256'] and len(raw) == identity['bytes'], 'Development original member differs')
        for case in declaration['cases']:
            prefix = case + '/'
            attempt = json.loads(archive.read(prefix + 'attempt.json'))
            terminal = json.loads(archive.read(prefix + 'terminal.json'))
            inputs = json.loads(archive.read(prefix + 'input.json'))
            require(attempt['status'] == 'STARTED' and terminal['source_commit'] == attempt['source_commit'] and terminal['source_unchanged'], 'Development source lifecycle differs')
            for name, identity in attempt['source_files'].items():
                require(digest(archive.read(prefix + 'pre-call/' + name)) == identity, 'Original precall snapshot differs')
            if terminal['integration_returned']:
                run = json.loads(archive.read(prefix + 'original/run.json'))
                require(run['code_identity'] == terminal['executed_source'] and run['code_identity']['git_commit'] == attempt['source_commit'], 'Executed development identity differs')
                require(all(attempt['source_files'][name] == identity for name, identity in run['code_identity']['files'].items()), 'Actual development runtime bytes differ')
                require(run['inputs']['dispatch_program'] == inputs['dispatch_program'] and
                    run['inputs']['duration_s'] == inputs['duration_s'] and
                    run['inputs']['maximum_step_s'] == inputs['maximum_step_s'] and
                    run['inputs']['boundary_events'] == sorted(inputs['boundary_events'],
                        key=lambda row: (row['time_s'], row['parameter_id'])) and
                    json.loads(archive.read(prefix + 'original/scenario.json')) == inputs['model'], 'Actual saved input differs')
                for name, identity in run['artifacts'].items():
                    require(digest(archive.read(prefix + 'original/' + name)) == identity['sha256'], 'Original saved run member differs')
            attempts.append(dict(case=case, terminal=terminal['status'], integration_returned=terminal['integration_returned']))
    require(attempts == receipt['attempts'] and len(members) == receipt['members'], 'Development receipt differs')
    return dict(status='PASS_SAVED_DEVELOPMENT_ONLY', attempts=attempts, members=len(members),
        delivery=delivery, new_physical_calls=0, new_selector_calls=0, registered_research_trials=0)


def seal(folder, cases, log_paths):
    folder.mkdir(exist_ok=False)
    files, attempts = {}, []
    for case in cases:
        require(case.startswith('service-') and PurePosixPath(case).name == case, 'Expected a specific new service attempt id')
        base = ROOT / '.work/27-development' / case
        terminal = json.loads((base / 'terminal.json').read_bytes())
        attempts.append(dict(case=case, terminal=terminal['status'], integration_returned=terminal['integration_returned']))
        files.update({case + '/' + p.relative_to(base).as_posix(): p for p in base.rglob('*')
            if p.is_file() and durable(p.relative_to(base).as_posix())})
    write(folder / 'declaration.json', dict(artifacts=sorted(FILES - {'receipt.json'}), cases=cases,
        logs={name: digest((ROOT / name).read_bytes()) for name in log_paths}, cache_classification='EXCLUDED_RUNTIME_CACHES'))
    members = {}
    with zipfile.ZipFile(folder / 'originals.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            raw = path.read_bytes()
            archive.writestr(name, raw)
            members[name] = dict(sha256=digest(raw), bytes=len(raw))
    write(folder / 'members.json', members)
    write(folder / 'receipt.json', dict(classification='SAVED_ORIGINALS_NOT_FORMAL_CAPTURE_OR_TICKET_ACCEPTANCE',
        tool=TOOL, tool_sha256=digest((ROOT / TOOL).read_bytes()), attempts=attempts, members=len(members),
        artifacts={name: digest((folder / name).read_bytes()) for name in sorted(FILES - {'receipt.json'})}))
    return verify(folder)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['seal', 'verify'])
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--log', action='append', default=[])
    parser.add_argument('--delivery')
    args = parser.parse_args()
    folder = (ROOT / args.package).resolve()
    require(folder.parent == PACKAGE, 'Use a declared ticket27 development package')
    print(json.dumps(seal(folder, args.case, args.log) if args.mode == 'seal' else verify(folder, args.delivery), ensure_ascii=False))
