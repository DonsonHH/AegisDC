"""Verify the immutable coupled package, without simulation or full-suite reruns.

Execution Git objects establish the source/tools used. Delivery Git objects
establish the exact durable bytes delivered. A fresh checkout must have both
histories; shallow repositories cannot claim the historical-source check.
"""
import argparse
import json
from pathlib import Path
import subprocess

from coupled_engineering_checks import check_case
from verify_reserve_delivery import file_sha, git_blob_sha, is_runtime_cache, safe_path


def verify(root, directory, *, delivery_commit):
    root = root.resolve()
    directory = (directory if directory.is_absolute() else root / directory).resolve()
    relative = directory.relative_to(root).as_posix()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit + '^{commit}'], cwd=root, text=True).strip()
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    if git_blob_sha(root, delivery, relative + '/receipt.json') != file_sha(directory / 'receipt.json'):
        raise ValueError('Receipt differs from committed delivery')
    if receipt['engineering_capture'] != 'PASS' or receipt['delivery_gate'] != 'PENDING_COMMIT_AND_FRESH_CHECKOUT':
        raise ValueError('Initial execution receipt was missing or rewritten')
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    declared = set(declaration['declared_artifacts'])
    if declared != set(receipt['artifacts']):
        raise ValueError('Declared durable set differs from hashed outputs')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not is_runtime_cache(path)}
    if actual != declared | {'receipt.json'}:
        raise ValueError('Unexpected or missing durable files: ' + str(actual ^ (declared | {'receipt.json'})))
    for name, expected in receipt['artifacts'].items():
        if is_runtime_cache(name) or file_sha(safe_path(directory, name)) != expected \
                or git_blob_sha(root, delivery, relative + '/' + name) != expected:
            raise ValueError('Durable artifact mismatch: ' + name)
    execution = receipt['execution_commit']
    for group, declared_group in (('pinned_tools', 'declared_tools'), ('execution_inputs', 'declared_execution_inputs'),
                                   ('prior_durable_files', 'declared_prior_files')):
        if set(receipt[group]) != set(declaration[declared_group]):
            raise ValueError('Provenance set differs from its initial declaration: ' + group)
    for group in ('runtime_sources', 'pinned_tools', 'execution_inputs', 'prior_durable_files'):
        for name, expected in receipt[group].items():
            if is_runtime_cache(name) or git_blob_sha(root, execution, name) != expected \
                    or git_blob_sha(root, delivery, name) != expected or file_sha(safe_path(root, name)) != expected:
                raise ValueError('Execution/delivery provenance mismatch: ' + name)
    runbook = json.loads((directory / 'runbook-copy.json').read_text(encoding='utf-8'))
    if runbook != json.loads(safe_path(root, 'docs/mainline/11-coupled-runbook.json').read_text(encoding='utf-8')):
        raise ValueError('Declared runbook differs from execution input')
    checks, points, intervals = {}, 0, 0
    base = json.loads(safe_path(root, runbook['profile']).read_text(encoding='utf-8'))
    for item in runbook['cases']:
        folder = safe_path(directory, item['id'])
        manifest = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
        scenario = json.loads((folder / 'scenario.json').read_text(encoding='utf-8'))
        if scenario['entities'] != base['entities'] or scenario['graphs'] != base['graphs']:
            raise ValueError('One-V6 entity/topology identity changed')
        if manifest['code_identity']['git_commit'] != execution or manifest['code_identity']['implementation_has_changes'] \
                or manifest['code_identity']['files'] != receipt['runtime_sources']:
            raise ValueError('Run/source execution identity mismatch: ' + item['id'])
        for name, identity in manifest['artifacts'].items():
            path = safe_path(folder, name)
            if file_sha(path) != identity['sha256']:
                raise ValueError('Run manifest artifact hash mismatch: ' + name)
            if name.endswith('.jsonl') and len(path.read_text(encoding='utf-8').splitlines()) != identity['records']:
                raise ValueError('Run record count mismatch: ' + name)
        if item['via_cli'] and json.loads((directory / (item['id'] + '-stdout.json')).read_text(encoding='utf-8')) != manifest:
            raise ValueError('Actual CLI stdout differs from original manifest')
        trace = [json.loads(line) for line in (folder / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
        balances = [json.loads(line) for line in (folder / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
        checks[item['id']] = check_case(item, manifest, scenario, trace, balances)
        points += len(trace)
        intervals += len(balances)
    if checks != json.loads((directory / 'independent-checks.json').read_text(encoding='utf-8')):
        raise ValueError('Saved independent account checks do not reproduce')
    rejected = json.loads((directory / 'expected-rejections.json').read_text(encoding='utf-8'))
    if len(rejected) != len(runbook['rejections']) or len(rejected) != receipt['expected_rejections']:
        raise ValueError('Refusal count differs from declared cases')
    for expected, actual in zip(runbook['rejections'], rejected):
        path = directory / 'rejections' / (expected['id'] + '.json')
        if actual['id'] != expected['id'] or actual['successful_trajectory_returned'] \
                or expected['error_contains'] not in actual['error'] or actual['input_sha256'] != file_sha(path):
            raise ValueError('Expected domain refusal record does not reconcile')
    full = json.loads((directory / 'full-check/summary.json').read_text(encoding='utf-8'))
    if full['overall'] != 'PASS' or full['tests'] != receipt['full_tests'] or receipt['full_regression_runs'] != 1:
        raise ValueError('Full acceptance did not pass exactly once')
    return dict(status='PASS', execution_commit=execution, delivery_commit=delivery, cases=len(checks),
                expected_rejections=len(rejected), artifacts=len(declared), state_points=points, intervals=intervals,
                pinned_source_tools=len(receipt['pinned_tools']), prior_durable_files=len(receipt['prior_durable_files']),
                full_tests=full['tests'], verified_original_files=full['verified_original_files'], runtime_caches_required=0,
                physics_rerun=False, full_suite_rerun=False, research_trials=0, model_calls=0, training_calls=0,
                initial_pending_receipt_preserved=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    result = verify(arguments.root, arguments.directory, delivery_commit=arguments.delivery_commit)
    with arguments.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
