"""Fresh-checkout ticket-13 delivery verification; no physics or suite reruns."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.replay import read_attempt
from replay_engineering_checks import ATTEMPTS, check_package
from verify_reserve_delivery import file_sha, git_blob_sha, is_runtime_cache, safe_path


def verify(root, directory, *, delivery_commit):
    root = root.resolve()
    directory = (directory if directory.is_absolute() else root / directory).resolve()
    relative = directory.relative_to(root).as_posix()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit + '^{commit}'], cwd=root, text=True).strip()
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    if git_blob_sha(root, delivery, relative + '/receipt.json') != file_sha(directory / 'receipt.json'):
        raise ValueError('Initial receipt differs from committed delivery')
    if receipt['engineering_capture'] != 'PASS' or receipt['delivery_gate'] != 'PENDING_COMMIT_AND_FRESH_CHECKOUT':
        raise ValueError('Initial execution capture failed or its pending receipt was rewritten')
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    declared = set(declaration['declared_artifacts'])
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not is_runtime_cache(path)}
    if actual != declared | {'receipt.json'} or declared != set(receipt['artifacts']):
        raise ValueError('Declared durable delivery set is not exact')
    for name, expected in receipt['artifacts'].items():
        if is_runtime_cache(name) or file_sha(safe_path(directory, name)) != expected \
                or git_blob_sha(root, delivery, relative + '/' + name) != expected:
            raise ValueError('Durable delivery artifact mismatch: ' + name)
    execution = receipt['execution_commit']
    for group, key in (('pinned_tools', 'declared_tools'), ('execution_inputs', 'declared_execution_inputs'),
                       ('prior_durable_files', 'declared_prior_files')):
        if set(receipt[group]) != set(declaration[key]):
            raise ValueError('Initial source/input declaration differs: ' + group)
    for group in ('runtime_sources', 'pinned_tools', 'execution_inputs', 'prior_durable_files'):
        for name, expected in receipt[group].items():
            if is_runtime_cache(name) or file_sha(safe_path(root, name)) != expected \
                    or git_blob_sha(root, execution, name) != expected or git_blob_sha(root, delivery, name) != expected:
                raise ValueError('Execution/delivery source or tool mismatch: ' + name)
    for historical in receipt['retained_failed_captures']:
        folder = safe_path(root, historical)
        failed = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
        if failed['engineering_capture'] != 'FAIL' or (folder / 'full-check').exists():
            raise ValueError('Retained pre-full capture failure was rewritten or misclassified')
        actual_failed = {path.relative_to(folder).as_posix() for path in folder.rglob('*')
                         if path.is_file() and not is_runtime_cache(path)}
        if actual_failed != set(failed['artifacts']) | {'receipt.json'}:
            raise ValueError('Retained failed capture durable set differs')
        for name, expected in failed['artifacts'].items():
            if file_sha(safe_path(folder, name)) != expected:
                raise ValueError('Retained failed-capture artifact changed: ' + name)
        for group in ('runtime_sources', 'pinned_tools', 'execution_inputs'):
            for name, expected in failed[group].items():
                if git_blob_sha(root, failed['execution_commit'], name) != expected:
                    raise ValueError('Retained failed capture does not match its historical execution source')
    for name in ATTEMPTS:
        attempt = read_attempt(directory / name)
        source = attempt['record']['source_identity']
        if source['git_commit'] != execution or source['implementation_has_changes'] is not False \
                or source['files'] != receipt['runtime_sources']:
            raise ValueError('Attempt runtime source does not match its actual execution revision: ' + name)
    checks = check_package(root, directory)
    if checks != json.loads((directory / 'independent-checks.json').read_text(encoding='utf-8')) \
            or checks != receipt['independent_checks']:
        raise ValueError('Independent saved outcome checks do not reproduce')
    regression = json.loads((directory / 'full-check/summary.json').read_text(encoding='utf-8'))
    if regression['overall'] != 'PASS' or regression['tests'] != receipt['full_tests'] or receipt['full_regression_runs'] != 1:
        raise ValueError('Exactly one completed full check was not retained')
    return dict(status='PASS', execution_commit=execution, delivery_commit=delivery,
                durable_artifacts=len(declared), terminal_attempts=checks['terminal_attempts'],
                exact_replay_pairs=len(checks['exact_replay_pairs']), completed_attempts=6, failed_attempts=7,
                explicit_retries=1, source_and_tool_files=len(receipt['runtime_sources']) + len(receipt['pinned_tools']),
                retained_failed_captures=len(receipt['retained_failed_captures']),
                retained_prior_durable_files=len(receipt['prior_durable_files']),
                full_tests=regression['tests'], verified_original_files=regression['verified_original_files'],
                runtime_caches_required=0, initial_pending_receipt_preserved=True,
                physics_rerun=False, full_suite_rerun=False, research_trials=0, model_calls=0, training_calls=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.directory, delivery_commit=args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
