"""Execute the frozen reserve runbook in a fresh, explicitly declared package."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import os
import subprocess
import sys
import traceback

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario
from verify_reserve_delivery import check_case, file_sha, git_blob_sha, is_runtime_cache

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'evidence/mainline/engineering/10-reserve'
PROFILE = ROOT / 'configs/full-facility-mainline-reserve-v6.json'


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def configure(overrides, case_id):
    scenario = load_scenario(PROFILE)
    for row in scenario['parameters']:
        if row['id'] in overrides:
            row.update(value=overrides[row['id']], basis='synthetic_assumption', source_refs=['Rreserve'],
                       source_note='Frozen ticket 10 engineering case ' + case_id + '; not site data.')
    return scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError('Use a fresh directory inside the repository for committed delivery')
    output.mkdir(parents=True, exist_ok=False)
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    runbook_path = BASE / 'runbook-v1.json'
    runbook = json.loads(runbook_path.read_text(encoding='utf-8'))
    if not runbook['cases'] or len({item['id'] for item in runbook['cases']}) != len(runbook['cases']):
        raise ValueError('Freeze a nonempty runbook with unique case IDs')
    tools = ['scripts/capture_reserve_engineering.py', 'scripts/verify_reserve_delivery.py', 'scripts/build_reserve_profile.py']
    inputs = ['configs/full-facility-mainline-reserve-v6.json', 'configs/full-facility-mainline-control-v5.json',
              'configs/materials/reference-r134a-saturation.json', runbook_path.relative_to(ROOT).as_posix()]
    pinned_tools = {name: file_sha(ROOT / name) for name in tools}
    execution_inputs = {name: file_sha(ROOT / name) for name in inputs}
    for name, identity in {**pinned_tools, **execution_inputs}.items():
        if git_blob_sha(ROOT, execution, name) != identity:
            raise ValueError('Input/tool is not committed at execution revision: ' + name)
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--', BASE.relative_to(ROOT).as_posix()], cwd=ROOT).decode('utf-8').split('\0')
    prior = {}
    for name in filter(None, tracked):
        if is_runtime_cache(name):
            raise ValueError('A cache was tracked in the requested durable source set: ' + name)
        prior[name] = file_sha(ROOT / name)
        if git_blob_sha(ROOT, execution, name) != prior[name]:
            raise ValueError('Prior evidence differs from execution Git: ' + name)
    # Classified before hashing the delivery set. These observations are not
    # required files and their existence/hashes never become portable gates.
    cache_observations = []
    for source in (ROOT / 'src/aegis_dc', BASE, ROOT / 'tests'):
        for path in sorted(source.rglob('*')):
            if path.is_file() and is_runtime_cache(path.relative_to(ROOT)):
                cache_observations.append({'path': path.relative_to(ROOT).as_posix(),
                    'classification': 'RUNTIME_CACHE_NOT_DELIVERED', 'observed_sha256': file_sha(path),
                    'reason': 'Automatic __pycache__/.pyc/.pyo; no gate requires this cache or its hash'})

    base = load_scenario(PROFILE)
    bad = []
    for identifier, mutation in [('unknown-profile', ('profile', 'unsupported')),
            ('fractional-availability', ('flag', 0.5)), ('zero-internal-control', ('control', 0)),
            ('wrong-air-quantity', ('quantity', 'thermal_conductance')),
            ('fractional-event', ('event', 0.5)), ('legacy-profile-selection', ('legacy', None))]:
        scenario = json.loads(json.dumps(base))
        events = []
        kind, value = mutation
        if kind == 'profile':
            scenario['runtime']['reserve_profile'] = value
        elif kind == 'flag':
            next(row for row in scenario['parameters'] if row['id'] == 'ups_in_service')['value'] = value
        elif kind == 'control':
            next(row for row in scenario['parameters'] if row['id'] == 'ups_internal_control_power').update(value=0, valid_range=[0, 10000])
        elif kind == 'quantity':
            next(row for row in scenario['parameters'] if row['id'] == 'backup_air_capacity_rate')['quantity'] = value
        elif kind == 'event':
            events = [{'time_s': 0.25, 'parameter_id': 'backup_cooling_requested', 'value': value,
                       'source_note': 'Frozen explicit invalid binary engineering input.'}]
        elif kind == 'legacy':
            scenario = load_scenario(ROOT / 'configs/full-facility-mainline-control-v5.json')
            scenario['runtime']['reserve_profile'] = base['runtime']['reserve_profile']
        bad.append({'id': identifier, 'scenario': scenario, 'events': events})
    planned = ['declaration.json', 'runbook-copy.json', 'cache-observations.json',
               'engineering-attempts.jsonl', 'expected-rejections.json', 'capture-status.json']
    for item in runbook['cases']:
        name = item['id']
        planned += [name + '/' + part for part in ('run.json', 'scenario.json', 'private-state.jsonl', 'balances.jsonl')]
        planned += ['inputs/' + name + '-model.json', 'inputs/' + name + '-inputs.json']
        if item.get('via_cli'):
            planned += [name + '-stdout.json', name + '-stderr.txt']
    planned += ['rejections/' + item['id'] + '.json' for item in bad]
    if any(is_runtime_cache(name) for name in planned):
        raise ValueError('Runtime cache was incorrectly planned as evidence')
    write_new(output / 'declaration.json', {'schema': 'aegisdc-declared-durable-set-v1',
        'execution_commit': execution, 'declared_artifacts': planned,
        'declared_prior_files': sorted(prior), 'declared_tools': tools, 'declared_execution_inputs': inputs,
        'initial_policy': 'All declared paths required; caches excluded by type before hashing; no mismatch skipping',
        'receipt_policy': 'receipt.json is separately checked against delivery Git bytes to avoid a self-hash cycle'})
    write_new(output / 'runbook-copy.json', runbook)
    write_new(output / 'cache-observations.json', cache_observations)
    summaries, rejections, runtime_sources = {}, [], None
    attempt = None
    with (output / 'engineering-attempts.jsonl').open('x', encoding='utf-8', newline='\n') as ledger:
        try:
            for item in runbook['cases']:
                name = item['id']
                attempt = name
                scenario = configure(item['overrides'], name)
                scenario_path = output / 'inputs' / (name + '-model.json')
                inputs_path = output / 'inputs' / (name + '-inputs.json')
                write_new(scenario_path, scenario)
                write_new(inputs_path, {'schema': 'aegisdc-engineering-inputs-v1', 'work_requests': [], 'boundary_events': item['events']})
                if item.get('via_cli'):
                    process = subprocess.run([sys.executable, '-m', 'aegis_dc', 'simulate', '--model', str(scenario_path),
                        '--duration', str(item['duration_s']), '--step', str(item['step_s']), '--inputs', str(inputs_path),
                        '--output', str(output / name)], cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
                        capture_output=True, text=True, encoding='utf-8')
                    (output / (name + '-stdout.json')).write_text(process.stdout, encoding='utf-8', newline='\n')
                    (output / (name + '-stderr.txt')).write_text(process.stderr, encoding='utf-8', newline='\n')
                    if process.returncode:
                        raise ValueError('CLI failed; stdout/stderr original retained')
                else:
                    result = simulate_scenario(scenario, duration_s=item['duration_s'], step_s=item['step_s'], boundary_events=item['events'])
                    save_run(result, output / name)
                case = output / name
                manifest = json.loads((case / 'run.json').read_text(encoding='utf-8'))
                if item.get('via_cli') and json.loads(process.stdout) != manifest:
                    raise ValueError('CLI stdout differs from saved run manifest')
                if manifest['code_identity']['implementation_has_changes'] or manifest['code_identity']['git_commit'] != execution:
                    raise ValueError('Runtime source is not clean execution source')
                if runtime_sources is None:
                    runtime_sources = manifest['code_identity']['files']
                    for path, identity in runtime_sources.items():
                        if git_blob_sha(ROOT, execution, path) != identity:
                            raise ValueError('Executed source differs from execution Git blob: ' + path)
                if runtime_sources != manifest['code_identity']['files']:
                    raise ValueError('Different runtime sources used within the runbook')
                for artifact, identity in manifest['artifacts'].items():
                    if file_sha(case / artifact) != identity['sha256']:
                        raise ValueError('Freshly read run artifact hash mismatch')
                trace = [json.loads(line) for line in (case / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
                balances = [json.loads(line) for line in (case / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
                check_case(item, manifest, trace, balances, runbook['absolute_metric_tolerance'])
                if not all(len(row['domains']) == 8 for row in trace):
                    raise ValueError('Full-facility domain coverage lost')
                if any(manifest[key] != 0 for key in ('research_trials', 'model_calls', 'training_calls')):
                    raise ValueError('Unexpected research/model/training activity')
                summaries[name] = {'summary': manifest['summary'], 'trace_records': len(trace), 'balance_records': len(balances),
                    'scenario_sha256': manifest['scenario_sha256'], 'entry_point': 'CLI' if item.get('via_cli') else 'simulate_scenario'}
                ledger.write(json.dumps({'case': name, 'outcome': 'ENGINEERING_COMPLETED',
                    'input_config_sha256': file_sha(scenario_path), 'inputs_sha256': file_sha(inputs_path),
                    'manifest_sha256': file_sha(case / 'run.json'), 'execution_commit': execution}) + '\n')
                ledger.flush()
            for item in bad:
                attempt = item['id']
                path = output / 'rejections' / (item['id'] + '.json')
                write_new(path, item)
                try:
                    simulate_scenario(item['scenario'], duration_s=2, boundary_events=item['events'])
                except ValueError as error:
                    rejections.append({'id': item['id'], 'error': str(error), 'input_sha256': file_sha(path), 'successful_trajectory_returned': False})
                    ledger.write(json.dumps({'case': item['id'], 'outcome': 'EXPECTED_REJECTION', 'error': str(error),
                                             'input_sha256': file_sha(path), 'execution_commit': execution}) + '\n')
                    ledger.flush()
                else:
                    raise ValueError('An intentionally unsupported condition was accepted')
        except Exception as error:
            ledger.write(json.dumps({'case': attempt, 'outcome': 'UNEXPECTED_FAILURE', 'error': repr(error), 'execution_commit': execution}) + '\n')
            ledger.flush()
            write_new(output / 'capture-status.json', {'status': 'FAIL', 'error': repr(error), 'traceback': traceback.format_exc()})
            raise
    write_new(output / 'expected-rejections.json', rejections)
    write_new(output / 'capture-status.json', {'status': 'PASS', 'cases': len(summaries), 'expected_rejections': len(rejections)})
    artifacts = {name: file_sha(output / name) for name in planned}
    receipt = {'schema': 'aegisdc-reserve-engineering-capture-v1', 'engineering_capture': 'PASS',
        'delivery_gate': 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'execution_commit': execution,
        'recorded_UTC': datetime.now(timezone.utc).isoformat(), 'runtime_sources': runtime_sources,
        'execution_inputs': execution_inputs, 'pinned_tools': pinned_tools, 'prior_durable_files': prior,
        'artifacts': artifacts, 'runs': summaries, 'expected_rejections': len(rejections),
        'runtime_caches_in_delivery_set': 0, 'cache_observations_are_gates': False,
        'research_trials': 0, 'model_calls': 0, 'training_calls': 0,
        'field_calibration': 'PENDING', 'research_gain': 'NOT_ESTABLISHED', 'M1_gate': 'IN_PROGRESS', 'overall_goal': 'ACTIVE'}
    write_new(output / 'receipt.json', receipt)
    print(json.dumps({'engineering_capture': 'PASS', 'cases': len(summaries), 'expected_rejections': len(rejections),
                      'declared_artifacts': len(artifacts), 'prior_durable_files': len(prior),
                      'receipt_sha256': file_sha(output / 'receipt.json')}))


if __name__ == '__main__':
    main()
