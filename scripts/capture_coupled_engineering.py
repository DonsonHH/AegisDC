"""Capture a frozen same-V6 engineering runbook, figures and one full check."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario
from coupled_engineering_checks import check_case
from verify_reserve_delivery import file_sha, git_blob_sha, is_runtime_cache

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = 'docs/mainline/11-coupled-runbook.json'
PROFILE = 'configs/full-facility-mainline-reserve-v6.json'


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def configured(base, item):
    scenario = deepcopy(base)
    known = {row['id'] for row in scenario['parameters']}
    if not set(item.get('overrides', {})) <= known:
        raise ValueError('Unknown engineering override')
    for row in scenario['parameters']:
        if row['id'] in item.get('overrides', {}):
            row.update(value=item['overrides'][row['id']], basis='synthetic_assumption',
                       source_note='Frozen ticket 11 synthetic engineering case: ' + item['id'])
    return scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plot-dependencies', type=Path,
                        help='Optional isolated matplotlib directory; project NumPy is loaded before it')
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError('Use a fresh directory inside the worktree for committed delivery')
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    tracked_changes = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=ROOT, text=True).strip()
    if tracked_changes:
        raise ValueError('Commit the source, tools and runbook before capture')
    runbook = json.loads((ROOT / RUNBOOK).read_text(encoding='utf-8'))
    base = load_scenario(ROOT / PROFILE)
    tools = ['scripts/' + name for name in ('capture_coupled_engineering.py', 'coupled_engineering_checks.py',
        'verify_coupled_delivery.py', 'plot_mainline_coupled.py', 'build_coupled_runbook.py',
        'verify_reserve_delivery.py', 'acceptance.py', 'verify_evidence.py')]
    source_paths = subprocess.check_output(['git', 'ls-files', '-z', '--', 'src', 'tests'], cwd=ROOT).decode('utf-8').split('\0')
    tools += [path for path in source_paths if path.endswith('.py') and not is_runtime_cache(path)]
    inputs = [RUNBOOK, PROFILE, 'configs/materials/reference-r134a-saturation.json',
        'evidence/mainline/engineering/06-phase/eos-reference-01/direct-eos-reference.json']
    prior = [f'docs/mainline/evidence/{number:02d}.json' for number in range(2, 11)]
    prior += ['evidence/mainline/engineering/' + name + '/receipt.json' for name in
              ('04-06-root-acceptance', '07-root-acceptance', '08-root-acceptance',
               '09-root-acceptance', '10-root-acceptance', 'property-reference')]
    pinned_tools, execution_inputs, prior_files = {}, {}, {}
    for paths, records in ((tools, pinned_tools), (inputs, execution_inputs), (prior, prior_files)):
        for name in paths:
            if is_runtime_cache(name):
                raise ValueError('A cache was declared durable: ' + name)
            records[name] = file_sha(ROOT / name)
            if git_blob_sha(ROOT, execution, name) != records[name]:
                raise ValueError('Execution input/tool/prior is not committed: ' + name)
    planned = ['declaration.json', 'runbook-copy.json', 'engineering-attempts.jsonl',
        'expected-rejections.json', 'independent-checks.json', 'capture-status.json',
        'full-check/tests.log', 'full-check/summary.json', 'full-check/evidence.json']
    for item in runbook['cases']:
        name = item['id']
        planned += [name + '/' + part for part in ('run.json', 'scenario.json', 'private-state.jsonl', 'balances.jsonl')]
        planned += ['inputs/' + name + suffix for suffix in ('-model.json', '-inputs.json')]
        if item['via_cli']:
            planned += [name + '-stdout.json', name + '-stderr.txt']
    planned += ['rejections/' + item['id'] + '.json' for item in runbook['rejections']]
    planned += ['figures/' + name + suffix for name in ('coupled-response', 'inventory-ledgers', 'facility-architecture')
                for suffix in ('.png', '.svg', '.json')]
    if len(planned) != len(set(planned)) or any(is_runtime_cache(name) for name in planned):
        raise ValueError('The durable delivery set is ambiguous or contains runtime caches')
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / 'declaration.json', dict(schema='aegisdc-declared-durable-set-v1', execution_commit=execution,
        declared_artifacts=planned, declared_tools=sorted(pinned_tools), declared_execution_inputs=inputs,
        declared_prior_files=prior, runtime_cache_policy='__pycache__, .pyc and .pyo excluded by type BEFORE hashing; never required',
        receipt_policy='receipt.json excluded only from its own self-hash and independently checked against delivery Git bytes',
        full_regression_runs=1, classification='ENGINEERING_FIXTURES_NOT_REGISTERED_RESEARCH'))
    write_new(output / 'runbook-copy.json', runbook)
    summaries, checks, refused, sources = {}, {}, [], None
    attempt = None
    with (output / 'engineering-attempts.jsonl').open('x', encoding='utf-8', newline='\n') as ledger:
        def record(value):
            ledger.write(json.dumps(dict(value, execution_commit=execution), ensure_ascii=False, allow_nan=False) + '\n')
            ledger.flush()
        try:
            for item in runbook['cases']:
                name = attempt = item['id']
                scenario = configured(base, item)
                model, inputs_path = output / 'inputs' / (name + '-model.json'), output / 'inputs' / (name + '-inputs.json')
                write_new(model, scenario)
                write_new(inputs_path, dict(schema='aegisdc-engineering-inputs-v1',
                    boundary_events=item['events'], work_requests=item['work_requests']))
                if item['via_cli']:
                    command = [sys.executable, '-m', 'aegis_dc', 'simulate', '--model', str(model), '--inputs', str(inputs_path),
                               '--duration', str(item['duration_s']), '--step', str(item['step_s']), '--output', str(output / name)]
                    process = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
                                             capture_output=True, text=True, encoding='utf-8')
                    (output / (name + '-stdout.json')).write_text(process.stdout, encoding='utf-8', newline='\n')
                    (output / (name + '-stderr.txt')).write_text(process.stderr, encoding='utf-8', newline='\n')
                    if process.returncode:
                        raise ValueError('Real CLI failed; original stdout/stderr retained')
                else:
                    result = simulate_scenario(scenario, duration_s=item['duration_s'], step_s=item['step_s'],
                        boundary_events=item['events'], work_requests=item['work_requests'])
                    save_run(result, output / name)
                directory = output / name
                manifest = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
                if item['via_cli'] and json.loads(process.stdout) != manifest:
                    raise ValueError('CLI stdout differs from saved manifest')
                if manifest['code_identity']['git_commit'] != execution or manifest['code_identity']['implementation_has_changes']:
                    raise ValueError('Runtime did not execute the clean frozen source')
                if sources is None:
                    sources = manifest['code_identity']['files']
                    for path, identity in sources.items():
                        if git_blob_sha(ROOT, execution, path) != identity:
                            raise ValueError('Runtime differs from execution Git blob: ' + path)
                if sources != manifest['code_identity']['files']:
                    raise ValueError('Runtime identity changed within the runbook')
                trace = [json.loads(line) for line in (directory / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
                balances = [json.loads(line) for line in (directory / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
                checks[name] = check_case(item, manifest, scenario, trace, balances)
                summaries[name] = dict(summary=manifest['summary'], scenario_sha256=manifest['scenario_sha256'],
                    entry_point='actual CLI' if item['via_cli'] else 'load_scenario / simulate_scenario / save_run')
                record(dict(case=name, outcome='ENGINEERING_COMPLETED', input_config_sha256=file_sha(model),
                            inputs_sha256=file_sha(inputs_path), manifest_sha256=file_sha(directory / 'run.json')))
                print('captured ' + name, flush=True)
            for item in runbook['rejections']:
                attempt = item['id']
                scenario = configured(base, item)
                path = output / 'rejections' / (item['id'] + '.json')
                write_new(path, dict(request=item, scenario=scenario))
                try:
                    simulate_scenario(scenario, duration_s=item['duration_s'], step_s=item['step_s'], boundary_events=item['events'])
                except ValueError as error:
                    if item['error_contains'] not in str(error):
                        raise ValueError('Unexpected refusal category: ' + str(error)) from error
                    refused.append(dict(id=item['id'], error=str(error), input_sha256=file_sha(path), successful_trajectory_returned=False))
                    record(dict(case=item['id'], outcome='EXPECTED_REJECTION', error=str(error)))
                else:
                    raise ValueError('Unsupported domain exit returned a successful trajectory')
            write_new(output / 'expected-rejections.json', refused)
            write_new(output / 'independent-checks.json', checks)
            attempt = 'engineering-figures'
            import numpy
            if numpy.__version__ != '2.3.5':
                raise ValueError('Use the project-pinned NumPy 2.3.5 for the formal capture/full check')
            original_paths = list(sys.path)
            try:
                if arguments.plot_dependencies:
                    sys.path.insert(0, str(arguments.plot_dependencies.resolve()))
                from plot_mainline_coupled import render
                figures = render(output)
            finally:
                sys.path[:] = original_paths
            record(dict(phase=attempt, outcome='RENDERED_FROM_SAVED_ORIGINALS', figures=figures))
            print('rendered saved-data figures', flush=True)
            attempt = 'one-full-acceptance'
            from acceptance import verify
            full = verify(ROOT, output / 'full-check')
            record(dict(phase=attempt, outcome=full['overall'], tests=full.get('tests'), verified_original_files=full.get('verified_original_files')))
            if full['overall'] != 'PASS':
                raise ValueError('Full acceptance failed; its original logs are retained')
        except Exception as error:
            record(dict(case=attempt, outcome='UNEXPECTED_FAILURE', error=repr(error)))
            write_new(output / 'capture-status.json', dict(status='FAIL', error=repr(error), traceback=traceback.format_exc()))
            raise
    write_new(output / 'capture-status.json', dict(status='PASS', cases=len(summaries), expected_rejections=len(refused), full_regression_runs=1))
    actual = {path.relative_to(output).as_posix() for path in output.rglob('*') if path.is_file() and not is_runtime_cache(path)}
    if actual != set(planned):
        raise ValueError('Missing or unexpected durable capture outputs: ' + str(actual ^ set(planned)))
    receipt = dict(schema='aegisdc-coupled-engineering-capture-v1', engineering_capture='PASS',
        delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', execution_commit=execution,
        recorded_UTC=datetime.now(timezone.utc).isoformat(), runtime_sources=sources,
        pinned_tools=pinned_tools, execution_inputs=execution_inputs, prior_durable_files=prior_files,
        artifacts={name: file_sha(output / name) for name in planned}, runs=summaries, expected_rejections=len(refused),
        full_tests=full['tests'], verified_original_files=full.get('verified_original_files'), full_regression_runs=1,
        toolchain=dict(python=platform.python_version(), executable_sha256=file_sha(Path(sys.executable)),
                       authoring_versions=figures['toolchain']),
        runtime_caches_in_delivery_set=0, research_trials=0, model_calls=0, training_calls=0,
        field_calibration='PENDING', research_gain='NOT_ESTABLISHED', M1_gate='PENDING_ROOT_ACCEPTANCE', overall_goal='ACTIVE')
    write_new(output / 'receipt.json', receipt)
    print(json.dumps(dict(engineering_capture='PASS', execution_commit=execution, cases=len(summaries),
                         expected_rejections=len(refused), declared_artifacts=len(planned), full_tests=full['tests'])))


if __name__ == '__main__':
    main()
