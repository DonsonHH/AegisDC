"""Read-only fresh delivery/Git verification; no physics or full regression rerun."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from build_decision_fixture import build
from capture_decision_engineering import BOOK, FIGURES, FIXTURE, declared_artifacts, file_sha, git_blob_sha, is_runtime_cache, pin_paths, write
from decision_engineering_checks import check_package, read, require
from plot_decision_privacy import render


def safe(root, name):
    require(type(name) is str and bool(name), 'Declared artifact path must be nonempty text')
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()) and path != root.resolve(), 'Declared path escapes its root')
    require(not is_runtime_cache(path), 'Runtime caches are not delivered evidence')
    return path


def verify(root, directory, delivery_commit):
    root, directory = root.resolve(), directory.resolve()
    relative = directory.relative_to(root).as_posix()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit], cwd=root, text=True).strip()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    require(head == delivery, 'Use a fresh checkout at the declared delivery revision')
    receipt, declaration = read(directory / 'receipt.json'), read(directory / 'declaration.json')
    require(receipt['schema'] == 'aegisdc-decision-engineering-receipt-v1', 'Unknown receipt')
    require(declaration['schema'] == 'aegisdc-decision-delivery-declaration-v1', 'Unknown delivery declaration')
    require(receipt['engineering_capture'] == 'PASS', 'Failed captures remain failed')
    require(receipt['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'Original pending receipt was rewritten')
    require(receipt['missing_declared_artifacts'] == receipt['unexpected_durable_artifacts'] == [], 'Original durable set is incomplete')
    declared = declaration['declared_artifacts']
    require(declared == declared_artifacts() and len(declared) == len(set(declared)), 'Durable declaration differs from frozen tool')
    require(set(declared) == set(receipt['artifacts']), 'Declaration differs from original hashed artifacts')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not is_runtime_cache(path)}
    require(actual == set(declared) | {'receipt.json'}, 'Extra/missing durable files in delivery')
    for name, identity in receipt['artifacts'].items():
        require(file_sha(safe(directory, name)) == identity, 'Original artifact changed: ' + name)
        require(git_blob_sha(root, delivery, relative + '/' + name) == identity, 'Delivery blob differs: ' + name)
    require(file_sha(directory / 'receipt.json') == git_blob_sha(root, delivery, relative + '/receipt.json'),
            'Original terminal receipt differs from committed blob')
    execution = receipt['execution_commit']
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', execution, delivery], cwd=root)
    require(ancestor.returncode == 0, 'Execution source is not an ancestor of delivery')
    paths = pin_paths(root)
    require(declaration['pinned_paths'] == paths, 'Source/tool/input declaration differs')
    for group, names in paths.items():
        require(set(receipt[group]) == set(names), 'Source/tool/input pin set differs: ' + group)
        for name, identity in receipt[group].items():
            require(file_sha(safe(root, name)) == identity, 'Runtime/tool/input bytes drifted: ' + name)
            require(git_blob_sha(root, execution, name) == identity, 'Recorded execution source differs: ' + name)
            require(git_blob_sha(root, delivery, name) == identity, 'Delivery source blob differs: ' + name)
    require(receipt['python'] == dict(version=sys.version, implementation=sys.implementation.name,
        executable_sha256=file_sha(sys.executable)), 'Fresh verification interpreter differs')
    require(receipt['numpy_version'] == importlib.metadata.version('numpy'), 'Fresh NumPy version differs')
    require(file_sha(directory / 'runbook-copy.json') == file_sha(root / BOOK), 'Exact frozen runbook copy differs')
    require(read(directory / 'audit/runbook-copy.json') == read(root / BOOK), 'Private audit used a different runbook')
    for name, document in build().items():
        require(read(directory / 'fixture-copy' / name) == document, 'Canonical public input does not rebuild: ' + name)
        require((directory / 'fixture-copy' / name).read_bytes() == (directory / 'fixture-rebuilt' / name).read_bytes(),
                'Rebuilt public input bytes differ: ' + name)
        require(file_sha(directory / 'fixture-copy' / name) == file_sha(root / FIXTURE / name),
                'Exact frozen public input copy differs: ' + name)
    checks = check_package(directory)
    require(checks == receipt['independent_checks'] == read(directory / 'independent-checks.json'),
            'Independent saved-data checks do not reproduce')
    require(read(directory / 'audit/audit-status.json')['status'] == 'PASS', 'Private audit was not successful')
    for world in ('A', 'B'):
        manifest = read(directory / f'audit/private-worlds/{world}/run.json')
        identity = manifest['code_identity']
        require(identity['git_commit'] == execution and identity['implementation_has_changes'] is False,
                'Actual private run source is not the recorded clean execution revision')
        for name, value in identity['files'].items():
            require(value == receipt['runtime_sources'][name] == git_blob_sha(root, execution, name),
                    'Actual runtime source manifest differs: ' + name)
    with tempfile.TemporaryDirectory(prefix='aegisdc-15-svg-') as temporary:
        regenerated = Path(temporary)
        render(directory, regenerated)
        for name in FIGURES:
            require(file_sha(regenerated / name) == file_sha(directory / 'figures' / name), 'Data SVG does not reproduce: ' + name)
    regression = read(directory / 'full-check/summary.json')
    require(regression['overall'] == 'PASS' and receipt['full_regression_executions'] == 1, 'Exactly one passing author full regression is required')
    require(regression['tests'] == receipt['full_tests'] and regression['tests']['unexpected_skips'] == [], 'Saved full regression summary differs')
    require(regression['verified_original_files'] == receipt['verified_historical_originals'], 'Historical original verification differs')
    for name in ('registered_research_trials', 'model_calls', 'training_calls'):
        require(receipt[name] == 0, 'Engineering fixtures cannot claim research/model/training execution')
    return dict(schema='aegisdc-decision-fresh-delivery-proof-v1', status='PASS',
        execution_commit=execution, delivery_commit=delivery, durable_artifacts=len(declared), terminal_receipts=1,
        pinned_runtime_sources=len(paths['runtime_sources']), pinned_authoring_verification_tools=len(paths['authoring_verification_tools']),
        pinned_inputs_and_development_originals=len(paths['frozen_inputs']), independent_checks=checks,
        full_tests=regression['tests'], verified_historical_originals=regression['verified_original_files'],
        full_regression_rerun=False, physics_rerun=False, original_receipt_rewritten=False, runtime_caches_required=0,
        registered_research_trials=0, model_calls=0, training_calls=0, field_calibration='PENDING')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.resolve().is_relative_to(args.root.resolve()), 'Write fresh proof outside the read-only checkout')
    result = verify(args.root, args.directory, args.delivery_commit)
    write(args.output, result)
    print(json.dumps({key: result[key] for key in ('status', 'execution_commit', 'delivery_commit', 'durable_artifacts')}))
