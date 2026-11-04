"""Independent copy-only review; no plant or full-suite execution."""
from hashlib import sha1, sha256
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(r'C:/Users/Donson/Documents/ChatGPT/Renly/.work/worktrees/full-site-13')
OUT = Path(__file__).resolve().parent
PIN = '9a68ea7fb2eeee580d3fa0b794e8cbe0fb734a97'
DELIVERY = '3e508cbe3ce3c157ef4ad13d0b7d8d4d1f6e802e'
CAPTURE = ROOT / 'evidence/mainline/engineering/13-replay/capture-04'
BASE = CAPTURE / 'causal-baseline'
OLD = ROOT / 'evidence/mainline/engineering/13-replay/capture-02/causal-baseline'


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def copy(name, source=BASE):
    target = OUT / 'copies' / name
    shutil.copytree(source, target)
    return target


def rehash(folder, artifact):
    path = folder / 'attempt.json'
    value = json.loads(path.read_bytes())
    value['artifacts'][artifact] = file_hash(folder / artifact)
    write_json(path, value)


def main():
    OUT.mkdir(exist_ok=True)
    receipt = json.loads((CAPTURE / 'receipt.json').read_bytes())
    names = set(receipt['runtime_sources']) | set(receipt['pinned_tools']) | set(receipt['execution_inputs'])
    names |= {'AGENTS.md', 'GLOSSARY.md', 'docs/MAINLINE.md', 'docs/mainline/progress.json',
              '.scratch/full-facility-mainline/spec.md', '.scratch/full-facility-mainline/issues/13-event-replay.md',
              'docs/mainline/13-replay-contract.md', 'docs/mainline/evidence/13-reader-v2.json'}
    names |= {p.relative_to(ROOT).as_posix() for base in (BASE, OLD) for p in base.rglob('*') if p.is_file()}
    identity = lambda: {name: file_hash(ROOT / name) for name in sorted(names)}
    before = identity()
    tree = {}
    for entry in subprocess.check_output(['git', 'ls-tree', '-r', '-z', PIN], cwd=ROOT).split(b'\0'):
        if entry:
            header, path = entry.split(b'\t', 1)
            tree[path.decode('utf-8')] = header.split()[2].decode('ascii')
    git_bound = {}
    for name in names:
        raw = (ROOT / name).read_bytes()
        blob = sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()
        # Source/tool and exact original data bytes must equal the frozen Git blobs.
        if blob != tree[name]:
            raise AssertionError('Working-tree bytes differ from frozen Git: ' + name)
        git_bound[name] = tree[name]
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
    replay = importlib.import_module('aegis_dc.replay')
    calls = []
    def forbidden_plant(*args, **kwargs):
        calls.append(dict(kwargs))
        raise AssertionError('Review must never execute the plant')
    replay.simulate_scenario = forbidden_plant
    results = {}
    for label, folder in [('known_v1', OLD), ('known_v2', BASE)]:
        got = replay.read_attempt(folder)
        assert got['record']['status'] == 'COMPLETED' and got['run'] is not None
        results[label] = dict(status='PASS', attempt_schema=got['record']['schema'],
                              terminal_sha256=got['record_sha256'])

    def rejected(name, folder, expected):
        try:
            replay.read_attempt(folder)
        except ValueError as error:
            read_status = dict(status='REFUSED', error=str(error), type=type(error).__name__)
        else:
            raise AssertionError('Unexpected authority: ' + name)
        target = OUT / 'new-refusals' / name
        got = replay.replay_attempt(folder, target)
        assert got['status'] == 'FAILED' and got['execution_kind'] == 'NOT_STARTED'
        assert expected in got['failure']['stage'], (name, got['failure'])
        checked = replay.read_attempt(target)
        assert checked['run'] is None
        for original in ('attempt.json', 'declaration.json', 'lifecycle.jsonl'):
            if (folder / original).exists():
                assert (target / 'origin' / original).read_bytes() == (folder / original).read_bytes()
        results[name] = dict(read=read_status, request_status=got['status'], failure=got['failure'],
                             execution_kind=got['execution_kind'], retained_bytes=True)

    for kind in ('terminal_version', 'declaration_version', 'terminal_state'):
        folder = copy(kind)
        terminal = json.loads((folder / 'attempt.json').read_bytes())
        if kind == 'terminal_version':
            terminal['schema'] = 'aegisdc-facility-attempt-v999'
            write_json(folder / 'attempt.json', terminal)
        elif kind == 'declaration_version':
            decl = json.loads((folder / 'declaration.json').read_bytes())
            decl['schema'] = 'aegisdc-attempt-declaration-v999'
            write_json(folder / 'declaration.json', decl)
            rehash(folder, 'declaration.json')
        else:
            terminal['status'] = 'UNRECOGNIZED_TERMINAL_STATE'
            rows = [json.loads(row) for row in (folder / 'lifecycle.jsonl').read_bytes().splitlines()]
            rows[-1]['state'] = terminal['status']
            (folder / 'lifecycle.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8', newline='\n')
            terminal['artifacts']['lifecycle.jsonl'] = file_hash(folder / 'lifecycle.jsonl')
            write_json(folder / 'attempt.json', terminal)
        rejected(kind, folder, 'declaration_header' if kind == 'declaration_version' else 'terminal_header')
    folder = OUT / 'copies' / 'declaration_only'
    folder.mkdir()
    (folder / 'declaration.json').write_bytes((BASE / 'declaration.json').read_bytes())
    got = replay.read_attempt(folder)
    assert got['record']['status'] == 'UNFINALIZED_RUNNING_OR_INTERRUPTED' and got['run'] is None
    results['declaration_only'] = dict(status=got['record']['status'])
    refused = replay.replay_attempt(folder, OUT / 'new-refusals' / 'declaration_only')
    assert refused['status'] == 'FAILED' and refused['execution_kind'] == 'NOT_STARTED'
    assert refused['failure']['stage'] == 'replay_origin.unfinalized_setup'
    malformed = OUT / 'copies' / 'scalar_lifecycle'
    shutil.copytree(folder, malformed)
    (malformed / 'lifecycle.jsonl').write_bytes(b'42\n')
    rejected('scalar_lifecycle', malformed, 'lifecycle')

    # Closed-format structure is valid, but these independent copies disagree
    # with the actual recorded run's duration/grid. No model is called.
    mismatch_results = {}
    for key, supplied in [('duration_s', 3.0), ('maximum_step_s', 0.25)]:
        folder = copy('request_' + key)
        request = json.loads((folder / 'request.json').read_bytes())
        original = request[key]
        request[key] = supplied
        write_json(folder / 'request.json', request)
        rehash(folder, 'request.json')
        got = replay.read_attempt(folder)
        canonical_key = 'duration_s' if key == 'duration_s' else 'maximum_step_s'
        canonical = got['record'][canonical_key]
        actual = got['run']['inputs'][canonical_key]
        assert got['record']['status'] == 'COMPLETED'
        assert canonical == actual and got['request'][key] != actual
        mismatch_results[key] = dict(reader_status=got['record']['status'], original_request_value=original,
            mutated_request_value=got['request'][key], terminal_value=canonical, actual_run_value=actual,
            record_sha256=got['record_sha256'], request_sha256=file_hash(folder / 'request.json'),
            observed_inconsistent_authority=True,
            replay_uses='replay_attempt passes prior.request duration_s and maximum_step_s to _run_recorded; no simulation executed by this probe')
    after = identity()
    assert before == after
    assert not calls
    result = dict(candidate=PIN, execution=receipt['execution_commit'], delivery=DELIVERY,
        known_versions_and_original_five_cases=results, new_request_binding_counterexamples=mismatch_results,
        guarded_files=len(names), source_and_original_guard='PASS', guarded_sha256=after,
        git_blobs=git_bound, plant_calls=0, full_suite_runs=0, research_trials=0, model_calls=0)
    with (OUT / 'independent-check-01.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(original_five_cases='PASS', supported_versions=2,
        request_binding_counterexamples=mismatch_results, guarded_files=len(names),
        source_guard='PASS', plant_calls=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
