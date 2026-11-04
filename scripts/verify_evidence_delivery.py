"""Read-only fresh-checkout verification of the declared ticket-14 delivery."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from build_evidence_fixture import build
from capture_evidence_engineering import file_sha, git_blob_sha, is_runtime_cache, pin_paths
from evidence_engineering_checks import check_package
from plot_evidence_ledger import render


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _safe(root, name):
    _require(type(name) is str and bool(name), 'Artifact path must be text')
    path = (root / name).resolve()
    _require(path.is_relative_to(root.resolve()) and path != root.resolve(), 'Artifact escapes its declared root')
    _require(not is_runtime_cache(path), 'Runtime caches cannot be delivered evidence')
    return path


def verify(root, directory, delivery_commit):
    root, directory = root.resolve(), directory.resolve()
    relative = directory.relative_to(root).as_posix()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit], cwd=root, text=True).strip()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    _require(head == delivery, 'Use a fresh checkout of the declared delivery revision')
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    _require(receipt['schema'] == 'aegisdc-evidence-engineering-receipt-v1', 'Unknown engineering receipt')
    _require(declaration['schema'] == 'aegisdc-evidence-delivery-declaration-v1', 'Unknown durable declaration')
    _require(receipt['engineering_capture'] == 'PASS', 'Failed captures remain failed')
    _require(receipt['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'Original terminal receipt was rewritten')
    _require(receipt['missing_declared_artifacts'] == receipt['unexpected_durable_artifacts'] == [], 'Incomplete original durable set')
    declared = declaration['declared_artifacts']
    _require(len(declared) == len(set(declared)), 'Duplicate declared artifact')
    _require(set(declared) == set(receipt['artifacts']), 'Declaration differs from hashed durable set')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not is_runtime_cache(path)}
    _require(actual == set(declared) | {'receipt.json'}, 'Extra or missing durable delivery file')
    for name, expected in receipt['artifacts'].items():
        _require(file_sha(_safe(directory, name)) == expected, 'Original artifact changed: ' + name)
        _require(git_blob_sha(root, delivery, relative + '/' + name) == expected, 'Delivery blob differs: ' + name)
    _require(file_sha(directory / 'receipt.json') == git_blob_sha(root, delivery, relative + '/receipt.json'), 'Terminal receipt differs from delivery blob')
    execution = receipt['execution_commit']
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', execution, delivery], cwd=root)
    _require(ancestor.returncode == 0, 'Execution source is not an ancestor of this delivery')
    expected_paths = pin_paths(root)
    _require(declaration['pinned_paths'] == expected_paths, 'Authoring/source/input declarations differ')
    for group, names in expected_paths.items():
        _require(set(receipt[group]) == set(names), 'Source/tool/input pin set differs: ' + group)
        for name, expected in receipt[group].items():
            _require(file_sha(_safe(root, name)) == expected, 'Runtime/tool/input bytes drifted: ' + name)
            _require(git_blob_sha(root, execution, name) == expected, 'Recorded execution source differs: ' + name)
            _require(git_blob_sha(root, delivery, name) == expected, 'Delivery source blob differs: ' + name)
    _require(receipt['python'] == dict(version=sys.version, implementation=sys.implementation.name,
                                     executable_sha256=file_sha(sys.executable)), 'Verification interpreter differs')
    _require(receipt['numpy_version'] == importlib.metadata.version('numpy'), 'Verification NumPy differs')
    book = json.loads((directory / 'runbook-copy.json').read_text(encoding='utf-8'))
    fixture = json.loads((directory / 'fixture-copy.json').read_text(encoding='utf-8'))
    _require(file_sha(directory / 'runbook-copy.json') == file_sha(root / 'docs/mainline/14-evidence-runbook.json'), 'Frozen runbook copy differs')
    _require(file_sha(directory / 'fixture-copy.json') == file_sha(root / book['fixture']), 'Frozen fixture copy differs')
    _require(build() == fixture, 'Static fixture does not rebuild from its pinned authoring tool')
    _require((directory / 'fixture-rebuilt.json').read_bytes() == (directory / 'fixture-copy.json').read_bytes(), 'Exact rebuilt fixture bytes differ')
    checks = check_package(directory)
    _require(checks == receipt['independent_checks'] == json.loads((directory / 'independent-checks.json').read_text(encoding='utf-8')), 'Literal checks do not reproduce')
    with tempfile.TemporaryDirectory(prefix='aegisdc-14-svg-') as temporary:
        regenerated = Path(temporary)
        render(fixture, regenerated)
        for name in ('arrival-timeline.svg', 'source-architecture.svg'):
            _require(file_sha(regenerated / name) == file_sha(directory / 'figures' / name), 'Figure does not reproduce: ' + name)
    regression = json.loads((directory / 'full-check/summary.json').read_text(encoding='utf-8'))
    _require(regression['overall'] == 'PASS' and receipt['full_regression_executions'] == 1,
             'One successful full engineering regression is required')
    _require(regression['tests'] == receipt['full_tests'] and regression['tests']['gate'] == 'PASS', 'Saved regression summary differs')
    _require(regression['tests']['unexpected_skips'] == [], 'Unexpected skipped tests')
    _require(regression['verified_original_files'] == receipt['verified_historical_originals'], 'Historical original count differs')
    for name in ('registered_research_trials', 'model_calls', 'training_calls'):
        _require(receipt[name] == 0, 'Engineering delivery cannot claim research/model/training execution')
    return dict(schema='aegisdc-evidence-fresh-delivery-proof-v1', status='PASS',
        execution_commit=execution, delivery_commit=delivery, durable_artifacts=len(declared), terminal_receipts=1,
        pinned_runtime_sources=len(receipt['runtime_sources']),
        pinned_authoring_verification_tools=len(receipt['authoring_verification_tools']),
        pinned_inputs_and_development_originals=len(receipt['frozen_inputs']),
        independent_checks=checks, full_tests=regression['tests'],
        verified_historical_originals=regression['verified_original_files'],
        full_regression_rerun=False, physics_rerun=False, original_receipt_rewritten=False,
        runtime_caches_required=0, registered_research_trials=0, model_calls=0, training_calls=0,
        current_dispatch_only_no_whole_input_hash=True, field_calibration='PENDING')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    _require(not args.output.resolve().is_relative_to(args.root.resolve()), 'Write proof outside the read-only fresh checkout')
    result = verify(args.root, args.directory, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'execution_commit', 'delivery_commit', 'durable_artifacts')}, ensure_ascii=False))
