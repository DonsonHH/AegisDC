"""Capture new frozen ticket-13 engineering attempts and exactly one full check."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.plant import ENGINEERING_COMMAND_PARAMETERS
from aegis_dc.replay import execution_source_identity, replay_attempt, run_recorded
from aegis_dc.scenario import load_scenario
from acceptance import verify as full_check
from replay_engineering_checks import ATTEMPTS, check_package
from verify_reserve_delivery import file_sha, git_blob_sha, is_runtime_cache


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def inputs(book, events=(), commands=(), jobs=()):
    return dict(schema='aegisdc-facility-replay-inputs-v1', seed=book['seed'],
                exogenous_events=list(events), action_commands=list(commands), work_requests=list(jobs))


def declare_attempt(name, reader_case=None):
    base = ['attempt.json', 'declaration.json', 'lifecycle.jsonl', 'request.json', 'scenario-input.json', 'inputs.json']
    if name not in {'invalid-replay-origin', 'research-before-protocol', 'malformed-CLI-input'} and reader_case is None:
        base += ['frozen-inputs.json']
    if name in ATTEMPTS[:6]:
        base += ['trajectory/run.json', 'trajectory/scenario.json', 'trajectory/private-state.jsonl', 'trajectory/balances.jsonl']
    if name in {'normal-600s', 'combined-episode-CLI', 'malformed-CLI-input'}:
        base += ['submitted-scenario.json', 'submitted-inputs.json']
    if name in {'normal-600s-replay', 'combined-episode-CLI-replay', 'causal-command'}:
        base += ['origin/attempt.json', 'origin/declaration.json', 'origin/lifecycle.jsonl']
    if reader_case is not None:
        base += ['origin/declaration.json']
        if reader_case['mutation'] != 'declaration_only':
            base += ['origin/lifecycle.jsonl']
        if reader_case['mutation'] not in {'declaration_only', 'bad_lifecycle'}:
            base += ['origin/attempt.json']
    return [name + '/' + path for path in base]


def capture(directory):
    directory = directory.resolve()
    directory.relative_to(ROOT)
    source = execution_source_identity()
    if source['implementation_has_changes'] is not False:
        raise ValueError('Commit frozen runtime/tool/runbook inputs before engineering capture')
    execution = source['git_commit']
    book_path = ROOT / 'docs/mainline/13-reader-runbook-v2.json'
    book = json.loads(book_path.read_text(encoding='utf-8'))
    prior = json.loads((ROOT / book['prior_runbook']).read_text(encoding='utf-8'))
    tool_paths = ['scripts/capture_replay_engineering.py', 'scripts/replay_engineering_checks.py',
                  'scripts/verify_replay_delivery.py', 'scripts/acceptance.py', 'scripts/verify_evidence.py',
                  'scripts/coupled_engineering_checks.py', 'scripts/verify_reserve_delivery.py', 'pyproject.toml']
    tool_paths += [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / 'tests').glob('*.py'))]
    tool_paths += [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / 'src/patrol_rsi').glob('*.py'))]
    input_paths = ['docs/mainline/13-reader-runbook-v2.json', book['prior_runbook'], book['profile'],
                   'configs/materials/reference-r134a-saturation.json', '.gitattributes',
                   'evidence/mainline/engineering/13-replay/.gitattributes']
    retained = book['retained_failed_captures'] + book['retained_successful_captures'] + book['retained_reviews']
    prior_paths = [path.relative_to(ROOT).as_posix() for folder in retained
                   for path in sorted((ROOT / folder).rglob('*')) if path.is_file() and not is_runtime_cache(path)]
    prior_paths += book['retained_indexes']
    for path in list(source['files']) + tool_paths + input_paths + prior_paths:
        if file_sha(ROOT / path) != git_blob_sha(ROOT, execution, path):
            raise ValueError('Uncommitted authoring/runtime/input bytes: ' + path)
    labels = ['normal-600s', 'normal-600s-replay', 'combined-episode-CLI', 'combined-episode-CLI-replay',
              'malformed-CLI-input', 'existing-output'] + [item['id'] for item in book['reader_cases']]
    declared = ['declaration.json', 'runbook-copy.json', 'README.md', 'command-receipts.json',
                'independent-checks.json', 'overwrite-refusal.json', 'inputs/normal-600s.json',
                'inputs/combined-episode-CLI.json', 'inputs/malformed.json',
                'full-check/summary.json', 'full-check/tests.log', 'full-check/evidence.json']
    declared += [path for name in ATTEMPTS for path in declare_attempt(name)]
    fixture_files = [path.relative_to(ROOT / book['reader_fixture_source']).as_posix()
                     for path in (ROOT / book['reader_fixture_source']).rglob('*') if path.is_file() and not is_runtime_cache(path)]
    for item in book['reader_cases']:
        declared += declare_attempt(item['id'], item)
        names = (['declaration.json'] if item['mutation'] == 'declaration_only' else
                 ['declaration.json', 'lifecycle.jsonl'] if item['mutation'] == 'bad_lifecycle' else fixture_files)
        declared += ['reader-origins/' + item['id'] + '/' + name for name in names]
    declared += [label + suffix for label in labels for suffix in ('-stdout.json', '-stderr.txt')]
    directory.mkdir(parents=True, exist_ok=False)
    declaration = dict(schema='aegisdc-replay-delivery-declaration-v2', classification='ENGINEERING_NOT_RESEARCH',
                       declared_artifacts=sorted(declared), declared_tools=tool_paths,
                       declared_execution_inputs=input_paths, declared_prior_files=prior_paths,
                       runtime_caches='NOT_DELIVERABLE',
                       terminal_receipt='receipt.json')
    write(directory / 'declaration.json', declaration)
    (directory / 'runbook-copy.json').write_bytes(book_path.read_bytes())
    (directory / 'README.md').write_text(
        '# Ticket 13 private engineering replay capture\n\n'
        'One accepted full V6 synthetic facility; exact re-execution, controlled causal response, '
        'explicit failed attempts/retry and no-overwrite checks. No method effect, AI, training or field calibration.\n\n'
        'The initial receipt stays PENDING_COMMIT_AND_FRESH_CHECKOUT. A separate verification receipt '
        'must pin this package to a committed delivery and independently check execution source bytes.\n',
        encoding='utf-8', newline='\n')
    (directory / 'inputs').mkdir()
    commands = []

    def cli(label, arguments, expected=0):
        command = [sys.executable, '-Xutf8', '-m', 'aegis_dc'] + list(map(str, arguments))
        result = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
                                capture_output=True, text=True, encoding='utf-8')
        (directory / (label + '-stdout.json')).write_text(result.stdout, encoding='utf-8', newline='\n')
        (directory / (label + '-stderr.txt')).write_text(result.stderr, encoding='utf-8', newline='\n')
        commands.append(dict(label=label, argv=command, returncode=result.returncode))
        if result.returncode != expected:
            raise ValueError('Actual CLI failed: ' + label + ': ' + result.stderr)
        return result

    receipt = dict(schema='aegisdc-replay-engineering-receipt-v2', execution_commit=execution,
                   started_at_utc=datetime.now(timezone.utc).isoformat(), engineering_capture='FAIL',
                   delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', research_trials=0, model_calls=0,
                   training_calls=0, research_protocol=None, research_budget=None, field_calibration='PENDING')
    try:
        for identifier in book['exact_replay_cases']:
            case = next(row for row in prior['cases'] if row['id'] == identifier)
            external, controls = [], []
            for index, event in enumerate(case['events']):
                if event['parameter_id'] in ENGINEERING_COMMAND_PARAMETERS:
                    controls.append(dict(event, id='declared-engineering-command-' + str(index)))
                else:
                    external.append(event)
            frozen = inputs(book, external, controls, case['work_requests'])
            input_file = directory / 'inputs' / (identifier + '.json')
            write(input_file, frozen)
            cli(identifier, ['record', '--model', ROOT / book['profile'], '--inputs', input_file,
                             '--duration', case['duration_s'], '--step', case['step_s'], '--output', directory / identifier])
            cli(identifier + '-replay', ['replay', '--attempt', directory / identifier, '--output', directory / (identifier + '-replay')])
        causal = book['causal_case']
        run_recorded(load_scenario(ROOT / book['profile']), directory / 'causal-baseline',
                     inputs=inputs(book, causal['exogenous_events']),
                     duration_s=causal['duration_s'], step_s=causal['maximum_step_s'])
        replay_attempt(directory / 'causal-baseline', directory / 'causal-command', action_commands=causal['action_commands'])
        case = next(row for row in prior['rejections'] if row['id'] == book['failure_source_case'])
        failed_scenario = deepcopy(load_scenario(ROOT / book['profile']))
        for row in failed_scenario['parameters']:
            if row['id'] in case['overrides']:
                row['value'] = case['overrides'][row['id']]
                row['source_note'] = 'Ticket 13 frozen engineering domain-refusal fixture; no site calibration.'
        for name, options in [('physical-failure', {}), ('explicit-retry', dict(retry_of=directory / 'physical-failure',
                             retry_reason='One explicit unchanged-input engineering confirmation of the retained domain refusal.'))]:
            run_recorded(failed_scenario, directory / name, inputs=inputs(book),
                         duration_s=case['duration_s'], step_s=case['step_s'], **options)
        invalid = dict(id='forbidden', time_s=.25, parameter_id='service_demand', value=0,
                       source_note='Invalid engineering authority fixture; offered demand cannot be commanded away.')
        run_recorded(load_scenario(ROOT / book['profile']), directory / 'forbidden-demand-command',
                     inputs=inputs(book, commands=[invalid]), duration_s=1)
        conflicts = [dict(id=str(index), time_s=.25 + index * math.ulp(.25), parameter_id='internal_valve_opening',
                          value=value, source_note='Deliberate numerically coincident command conflict fixture.')
                     for index, value in enumerate((0, 1))]
        run_recorded(load_scenario(ROOT / book['profile']), directory / 'coincident-command-conflict',
                     inputs=inputs(book, commands=conflicts), duration_s=1)
        replay_attempt(directory / 'deliberately-nonexistent-origin', directory / 'invalid-replay-origin')
        run_recorded(load_scenario(ROOT / book['profile']), directory / 'research-before-protocol',
                     inputs=inputs(book), duration_s=1, attempt_kind='registered_research',
                     research_registration=dict(protocol='UNOPENED_TICKET_30', budget='NOT_OPEN'))
        malformed = directory / 'inputs/malformed.json'
        malformed.write_bytes(b'{"schema":"duplicate","schema":"rejected"}\n')
        cli('malformed-CLI-input', ['record', '--model', ROOT / book['profile'], '--inputs', malformed,
                                   '--duration', 1, '--output', directory / 'malformed-CLI-input'], expected=1)
        for item in book['reader_cases']:
            origin = directory / 'reader-origins' / item['id']
            original = ROOT / book['reader_fixture_source']
            origin.parent.mkdir(parents=True, exist_ok=True)
            if item['mutation'] in {'bad_lifecycle', 'declaration_only'}:
                origin.mkdir()
                (origin / 'declaration.json').write_bytes((original / 'declaration.json').read_bytes())
                if item['mutation'] == 'bad_lifecycle':
                    (origin / 'lifecycle.jsonl').write_bytes(b'42\n')
            else:
                shutil.copytree(original, origin)
                record = json.loads((origin / 'attempt.json').read_text(encoding='utf-8'))
                if item['mutation'] == 'terminal_schema':
                    record['schema'] = 'aegisdc-facility-attempt-v999'
                elif item['mutation'] == 'declaration_schema':
                    path = origin / 'declaration.json'
                    value = json.loads(path.read_text(encoding='utf-8'))
                    value['schema'] = 'aegisdc-attempt-declaration-v999'
                    path.unlink()
                    write(path, value)
                    record['artifacts']['declaration.json'] = file_sha(path)
                else:
                    record['status'] = 'UNRECOGNIZED_TERMINAL_STATE'
                    path = origin / 'lifecycle.jsonl'
                    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
                    rows[-1]['state'] = record['status']
                    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8', newline='\n')
                    record['artifacts']['lifecycle.jsonl'] = file_sha(path)
                (origin / 'attempt.json').unlink()
                write(origin / 'attempt.json', record)
            cli(item['id'], ['replay', '--attempt', origin, '--output', directory / item['id']], expected=1)
        original = directory / 'normal-600s'
        before = {path.relative_to(original).as_posix(): file_sha(path) for path in original.rglob('*') if path.is_file()}
        refused = cli('existing-output', ['replay', '--attempt', original, '--output', original], expected=2)
        after = {path.relative_to(original).as_posix(): file_sha(path) for path in original.rglob('*') if path.is_file()}
        write(directory / 'overwrite-refusal.json', dict(returncode=refused.returncode, before=before, after=after))
        write(directory / 'command-receipts.json', commands)
        checks = check_package(ROOT, directory)
        write(directory / 'independent-checks.json', checks)
        regression = full_check(ROOT, directory / 'full-check')
        if regression['overall'] != 'PASS':
            raise ValueError('Full regression failed; preserve this capture and use a new directory after correction')
        actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
                  if path.is_file() and not is_runtime_cache(path)}
        if actual != set(declared):
            raise ValueError('Initial durable declaration differs from completed outputs: ' + str(actual ^ set(declared)))
        receipt.update(engineering_capture='PASS', independent_checks=checks,
                       full_regression_runs=1, full_tests=regression['tests'],
                       verified_original_files=regression['verified_original_files'])
    except Exception as error:
        receipt['failure'] = dict(type=type(error).__name__, message=str(error))
    receipt.update(runtime_sources=source['files'], pinned_tools={path: file_sha(ROOT / path) for path in tool_paths},
                   execution_inputs={path: file_sha(ROOT / path) for path in input_paths},
                   prior_durable_files={path: file_sha(ROOT / path) for path in prior_paths},
                   retained_failed_captures=book['retained_failed_captures'],
                   retained_successful_captures=book['retained_successful_captures'],
                   retained_reviews=book['retained_reviews'],
                   artifacts={path.relative_to(directory).as_posix(): file_sha(path) for path in sorted(directory.rglob('*'))
                              if path.is_file() and not is_runtime_cache(path)})
    write(directory / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    raise SystemExit(0 if result['engineering_capture'] == 'PASS' else 1)
