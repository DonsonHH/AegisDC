"""Verify declared reserve artifacts against execution and delivery Git identities.

No simulation is rerun. Runtime caches are non-deliverable by initial policy;
missing/mismatching declared durable files always fail.
"""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess


def is_runtime_cache(path):
    return '__pycache__' in {part.lower() for part in Path(path).parts} or Path(path).suffix.lower() in {'.pyc', '.pyo'}


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Artifact path escapes its declared root: ' + str(relative))
    return path


def git_blob_sha(root, revision, relative):
    return sha256(subprocess.check_output(['git', 'cat-file', 'blob', revision + ':' + relative], cwd=root)).hexdigest()


def check_case(item, manifest, trace, balances, tolerance):
    for key, expected in item['expected'].items():
        if abs(manifest['summary'][key] - expected) > tolerance \
                or abs(math.fsum(row[key] for row in balances) - expected) > tolerance:
            raise ValueError('Independent case account failed: ' + item['id'] + '/' + key)
    final = trace[-1]['domains']
    checks = item.get('checks', {})
    final_values = {'final_starter_energy_J': final['backup']['starter_energy_J'],
                    'final_generator_mode': final['backup']['generator_mode'],
                    'final_hot_mass_kg': final['facility_cooling']['hot_mass_kg'],
                    'final_floor_mass_kg': final['space_access']['floor_water_mass_kg'],
                    'protection_latched': final['control_monitoring']['protection_latched']}
    for key, expected in checks.items():
        if key in final_values:
            actual = final_values[key]
            good = abs(actual - expected) <= tolerance if type(expected) in (int, float) else actual == expected
        elif key.endswith('_depleted_at_s'):
            kind = key.removesuffix('_at_s')
            good = any(row['kind'] == kind and abs(row['time_s'] - expected) <= tolerance for row in manifest['events'])
        elif key == 'no_main_PLC_or_protected_output':
            good = all(row['domains']['power']['actual_powers_W']['local_controller'] == 0
                       and row['domains']['power']['ups_protected_output_W'] == 0 for row in trace)
        elif key == 'no_cooling_request':
            good = all(row['domains']['backup']['reserve_states']['cooling']['requested_at_s'] is None for row in trace)
        elif key == 'cooling_requested_at_s':
            values = {row['domains']['backup']['reserve_states']['cooling']['requested_at_s'] for row in trace} - {None}
            good = bool(values) and all(abs(value - expected) <= tolerance for value in values)
        elif key == 'floor_energy_equals_leak':
            good = abs(final['space_access']['floor_water_sensible_energy_J'] - manifest['summary']['internal_hot_leak_energy_J']) <= tolerance
        elif key == 'positive_service_deficit':
            good = manifest['summary']['service_deficit_time_s'] > 0
        elif key == 'true_temperature_at_first_trip_min_K':
            protected = [row['domains'] for row in trace if row['domains']['control_monitoring']['protection_latched']]
            good = bool(protected) and protected[0]['equipment_environment']['refrigerant']['temperature_K'] >= expected
        elif key == 'initial_UPS_mode':
            good = trace[0]['domains']['backup']['reserve_states']['ups']['mode'] == expected
        elif key == 'UPS_requested_at_3':
            at3 = next(row['domains'] for row in trace if row['time_s'] == 3)
            ups = at3['backup']['reserve_states']['ups']
            good = ups['mode'] == 'waiting' and ups['requested_at_s'] == 3 and abs(ups['ready_at_s'] - 3.2) <= tolerance
        else:
            raise ValueError('Unknown frozen check: ' + key)
        if not good:
            raise ValueError('Independent case condition failed: ' + item['id'] + '/' + key)


def verify(root, directory, *, delivery_commit=None):
    root = root.resolve()
    directory = (directory if directory.is_absolute() else root / directory).resolve()
    relative_directory = directory.relative_to(root).as_posix()
    receipt_path = directory / 'receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt['engineering_capture'] != 'PASS':
        raise ValueError('Engineering capture did not pass')
    if delivery_commit:
        delivery_commit = subprocess.check_output(['git', 'rev-parse', delivery_commit + '^{commit}'], cwd=root, text=True).strip()
        if git_blob_sha(root, delivery_commit, relative_directory + '/receipt.json') != file_sha(receipt_path):
            raise ValueError('Receipt differs from committed delivery')
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    declared = set(declaration['declared_artifacts'])
    if declared != set(receipt['artifacts']):
        raise ValueError('Declared durable set differs from hashed artifact set')
    if set(declaration['declared_prior_files']) != set(receipt['prior_durable_files']) \
            or set(declaration['declared_tools']) != set(receipt['pinned_tools']) \
            or set(declaration['declared_execution_inputs']) != set(receipt['execution_inputs']):
        raise ValueError('Declared provenance set differs from recorded identities')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not is_runtime_cache(path.relative_to(directory))}
    if actual != declared | {'receipt.json'}:
        raise ValueError('Unexpected or missing durable files in the engineering package')
    for relative, expected in receipt['artifacts'].items():
        if is_runtime_cache(relative):
            raise ValueError('A runtime cache was incorrectly declared durable')
        path = safe_path(directory, relative)
        if file_sha(path) != expected:
            raise ValueError('Artifact SHA mismatch: ' + relative)
        if delivery_commit and git_blob_sha(root, delivery_commit, relative_directory + '/' + relative) != expected:
            raise ValueError('Artifact differs from committed delivery: ' + relative)
    for relative, expected in receipt['prior_durable_files'].items():
        if is_runtime_cache(relative) or file_sha(safe_path(root, relative)) != expected:
            raise ValueError('Prior durable file mismatch: ' + relative)
        if delivery_commit and git_blob_sha(root, delivery_commit, relative) != expected:
            raise ValueError('Prior file differs from committed delivery: ' + relative)
    execution = receipt['execution_commit']
    for group in ('runtime_sources', 'execution_inputs', 'pinned_tools'):
        for relative, expected in receipt[group].items():
            if is_runtime_cache(relative) or git_blob_sha(root, execution, relative) != expected:
                raise ValueError('Execution Git/source identity mismatch: ' + relative)
            if delivery_commit and git_blob_sha(root, delivery_commit, relative) != expected:
                raise ValueError('Delivered execution input/tool/source differs: ' + relative)
    runbook = json.loads((directory / 'runbook-copy.json').read_text(encoding='utf-8'))
    traces = balances_count = 0
    for item in runbook['cases']:
        case = safe_path(directory, item['id'])
        manifest = json.loads((case / 'run.json').read_text(encoding='utf-8'))
        if item.get('via_cli') and json.loads((directory / (item['id'] + '-stdout.json')).read_text(encoding='utf-8')) != manifest:
            raise ValueError('CLI stdout differs from the saved original')
        if manifest['code_identity']['git_commit'] != execution or manifest['code_identity']['implementation_has_changes']:
            raise ValueError('Runtime execution identity mismatch: ' + item['id'])
        if manifest['code_identity']['files'] != receipt['runtime_sources']:
            raise ValueError('Runtime source hashes differ between cases')
        for name, identity in manifest['artifacts'].items():
            path = safe_path(case, name)
            if file_sha(path) != identity['sha256']:
                raise ValueError('Run manifest SHA mismatch: ' + item['id'] + '/' + name)
            if name.endswith('.jsonl') and len(path.read_text(encoding='utf-8').splitlines()) != identity['records']:
                raise ValueError('Run record count mismatch')
        trace = [json.loads(line) for line in (case / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
        balances = [json.loads(line) for line in (case / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
        if not all(len(row['domains']) == 8 for row in trace):
            raise ValueError('Full-facility domain set lost')
        check_case(item, manifest, trace, balances, runbook['absolute_metric_tolerance'])
        traces += len(trace)
        balances_count += len(balances)
    return {'status': 'PASS' if delivery_commit else 'EXECUTION_DATA_PASS_DELIVERY_NOT_CHECKED',
            'execution_commit': execution, 'delivery_commit': delivery_commit,
            'cases': len(runbook['cases']), 'artifacts': len(receipt['artifacts']),
            'prior_durable_files': len(receipt['prior_durable_files']), 'trace_records': traces,
            'balance_records': balances_count, 'runtime_caches_required': 0,
            'physics_rerun': False, 'research_trials': 0, 'training_calls': 0, 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    result = verify(arguments.root, arguments.directory, delivery_commit=arguments.delivery_commit)
    if arguments.output:
        with arguments.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
