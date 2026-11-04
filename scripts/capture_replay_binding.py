"""Capture the minimal reader-v3 correction; focused tests only, never a full suite."""
import argparse
from copy import deepcopy
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.replay import execution_source_identity, replay_attempt, run_recorded
from aegis_dc.scenario import load_scenario
from verify_replay_binding import cache, check_outcomes, file_sha, git_hashes


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def attempt_files(replayed=False, refused=False):
    result = ['attempt.json', 'declaration.json', 'lifecycle.jsonl', 'request.json', 'scenario-input.json', 'inputs.json']
    if not refused:
        result += ['frozen-inputs.json', 'trajectory/run.json', 'trajectory/scenario.json', 'trajectory/private-state.jsonl', 'trajectory/balances.jsonl']
    if replayed or refused:
        result += ['origin/attempt.json', 'origin/declaration.json', 'origin/lifecycle.jsonl']
    return result


def capture(directory):
    directory = directory.resolve()
    directory.relative_to(ROOT)
    source = execution_source_identity()
    if source['implementation_has_changes'] is not False:
        raise ValueError('Freeze the runtime before capture')
    book_path = ROOT / 'docs/mainline/13-reader-runbook-v3.json'
    book = json.loads(book_path.read_text(encoding='utf-8'))
    tools = ['scripts/capture_replay_binding.py', 'scripts/verify_replay_binding.py',
             'tests/test_mainline_replay.py', 'tests/test_replay_reader_authority.py', 'tests/test_replay_execution_binding.py']
    inputs = ['docs/mainline/13-reader-runbook-v3.json', book['profile'], 'configs/materials/reference-r134a-saturation.json',
              '.gitattributes', 'evidence/mainline/engineering/13-replay/.gitattributes']
    prior = json.loads((ROOT / book['prior_capture'] / 'receipt.json').read_text(encoding='utf-8'))
    prior_names = set(prior['prior_durable_files']) | set(book['retained_indexes'])
    for folder in [book['prior_capture']] + book['retained_reviews']:
        prior_names |= {path.relative_to(ROOT).as_posix() for path in (ROOT / folder).rglob('*') if path.is_file() and not cache(path)}
    prior_names = sorted(prior_names)
    all_names = set(source['files']) | set(tools) | set(inputs) | set(prior_names)
    pinned = git_hashes(ROOT, [(source['git_commit'], name) for name in all_names]
                        + [(book['core_pin'], name) for name in ('src/aegis_dc/replay.py', 'src/aegis_dc/replay_format.py')])
    for name in all_names:
        if file_sha(ROOT / name) != pinned[(source['git_commit'], name)]:
            raise ValueError('Source/tool/input/prior bytes not committed: ' + name)
    for name in ('src/aegis_dc/replay.py', 'src/aegis_dc/replay_format.py'):
        if file_sha(ROOT / name) != pinned[(book['core_pin'], name)]:
            raise ValueError('Reviewed core changed before capture')
    declared = ['declaration.json', 'runbook-copy.json', 'README.md', 'cli-commands.json', 'independent-checks.json', 'target-tests.log', 'target-summary.json']
    for case in book['positive_cases']:
        for suffix in ('', '-replay'):
            declared += [case['id'] + suffix + '/' + name for name in attempt_files(replayed=bool(suffix))]
    for case in book['refusal_cases']:
        declared += ['origins/' + case['id'] + '/' + name for name in attempt_files()]
        declared += [case['id'] + '/' + name for name in attempt_files(refused=True) + ['origin/' + case['artifact']]]
        declared += [case['id'] + suffix for suffix in ('-stdout.json', '-stderr.txt')]
    if len(set(declared)) != len(declared):
        raise ValueError('Duplicate declared output role')
    directory.mkdir(parents=True, exist_ok=False)
    declaration = dict(schema='aegisdc-replay-binding-declaration-v1', declared_artifacts=sorted(declared),
                       declared_tools=tools, declared_inputs=inputs, declared_prior_files=prior_names,
                       runtime_caches='NOT_DELIVERABLE', terminal_receipt='receipt.json')
    write(directory / 'declaration.json', declaration)
    (directory / 'runbook-copy.json').write_bytes(book_path.read_bytes())
    (directory / 'README.md').write_text('# Reader-v3 binding correction\n\nShort full-V6 engineering fixtures and focused public tests. No author full-suite execution.\n'
                                       'Origins are deliberate copies for request/interval refusal checks, not new historical outcomes.\n'
                                       'Older large packages and cf9 full345/343 retain their own execution identities.\n', encoding='utf-8', newline='\n')
    receipt = dict(schema='aegisdc-replay-binding-receipt-v1', status='FAIL', execution_commit=source['git_commit'],
                   delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', author_full_suite='NOT_RUN_THIS_REVISION',
                   prior_capture=book['prior_capture'], research_trials=0, model_calls=0, training_calls=0, field_calibration='PENDING')
    try:
        frozen = dict(schema='aegisdc-facility-replay-inputs-v1', seed=book['seed'], exogenous_events=[], action_commands=[], work_requests=[])
        for case in book['positive_cases']:
            scenario = deepcopy(load_scenario(ROOT / book['profile']))
            for row in scenario['parameters']:
                if row['id'] in case['default_overrides']:
                    row['value'] = case['default_overrides'][row['id']]
                    row['source_note'] = 'Reader-v3 short synthetic validation default; full V6 identities/graphs unchanged.'
            run_recorded(scenario, directory / case['id'], inputs=frozen,
                         duration_s=case['duration_s'], step_s=case['maximum_step_s'])
            replay_attempt(directory / case['id'], directory / (case['id'] + '-replay'))
        commands = []
        for case in book['refusal_cases']:
            folder = directory / 'origins' / case['id']
            folder.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(directory / 'explicit', folder)
            record = json.loads((folder / 'attempt.json').read_text(encoding='utf-8'))
            changed = []
            if case['mutation'] == 'balance_start':
                path = folder / 'trajectory/balances.jsonl'
                rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
                rows[0]['start_s'] = case['value']
                path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8', newline='\n')
                path = folder / 'trajectory/run.json'
                inner = json.loads(path.read_text(encoding='utf-8'))
                inner['artifacts']['balances.jsonl']['sha256'] = file_sha(folder / 'trajectory/balances.jsonl')
                path.write_text(json.dumps(inner, indent=2) + '\n', encoding='utf-8', newline='\n')
                changed = ['trajectory/balances.jsonl', 'trajectory/run.json']
            else:
                path = folder / 'request.json'
                request = json.loads(path.read_text(encoding='utf-8'))
                request[case['mutation']] = case['value']
                path.write_text(json.dumps(request, indent=2) + '\n', encoding='utf-8', newline='\n')
                changed = ['request.json']
            for name in changed:
                record['artifacts'][name] = file_sha(folder / name)
            (folder / 'attempt.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
            command = [sys.executable, '-Xutf8', '-m', 'aegis_dc', 'replay', '--attempt', str(folder), '--output', str(directory / case['id'])]
            ran = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True, text=True, encoding='utf-8')
            (directory / (case['id'] + '-stdout.json')).write_text(ran.stdout, encoding='utf-8', newline='\n')
            (directory / (case['id'] + '-stderr.txt')).write_text(ran.stderr, encoding='utf-8', newline='\n')
            commands.append(dict(argv=command, returncode=ran.returncode))
            if ran.returncode != 1:
                raise ValueError('Expected actual CLI staged refusal did not occur')
        write(directory / 'cli-commands.json', commands)
        checks = check_outcomes(directory, book)
        write(directory / 'independent-checks.json', checks)
        sys.path.insert(0, str(ROOT / 'tests'))
        suite = unittest.defaultTestLoader.loadTestsFromNames(book['targets'])
        stream = StringIO()
        tested = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        (directory / 'target-tests.log').write_text(stream.getvalue(), encoding='utf-8', newline='\n')
        summary = dict(run=tested.testsRun, failures=len(tested.failures), errors=len(tested.errors), skipped=len(tested.skipped))
        write(directory / 'target-summary.json', summary)
        if not tested.wasSuccessful() or tested.skipped:
            raise ValueError('Focused public regression did not pass')
        actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*') if path.is_file() and not cache(path)}
        if actual != set(declared):
            raise ValueError('Durable output roles differ from their initial declaration: ' + str(actual ^ set(declared)))
        if execution_source_identity() != source:
            raise ValueError('Runtime source changed during capture')
        receipt.update(status='PASS', focused_tests=summary, checks=checks)
    except Exception as error:
        receipt['failure'] = dict(type=type(error).__name__, message=str(error))
    receipt.update(runtime_sources=source['files'], tools={name: file_sha(ROOT / name) for name in tools},
                   inputs={name: file_sha(ROOT / name) for name in inputs}, prior_durable_files={name: file_sha(ROOT / name) for name in prior_names},
                   artifacts={path.relative_to(directory).as_posix(): file_sha(path) for path in sorted(directory.rglob('*')) if path.is_file() and not cache(path)})
    write(directory / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
