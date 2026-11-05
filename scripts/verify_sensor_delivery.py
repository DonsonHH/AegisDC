"""Read saved sensor artifacts in a fresh checkout; no adapter, plant or full run."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from capture_evidence_engineering import file_sha, git_blob_sha, is_runtime_cache
from capture_sensor_engineering import BOOK, original_identity, pins
from plot_sensor_channels import render
from sensor_engineering_checks import check, require


def safe(root, name):
    require(type(name) is str and bool(name), 'Artifact path must be text')
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()) and path != root.resolve(), 'Artifact escapes its declared root')
    require(not is_runtime_cache(path), 'Runtime caches are not delivered evidence')
    return path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify(root, directory, delivery_commit):
    root, directory = root.resolve(), directory.resolve()
    relative = directory.relative_to(root).as_posix()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit], cwd=root, text=True).strip()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    require(head == delivery, 'Use a fresh checkout at the declared delivery revision')
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip(), 'Fresh checkout must be clean')
    receipt, declaration = read(directory / 'receipt.json'), read(directory / 'declaration.json')
    require(receipt['schema'] == 'aegisdc-sensor-engineering-receipt-v1', 'Unknown capture receipt')
    require(declaration['schema'] == 'aegisdc-sensor-engineering-declaration-v1', 'Unknown delivery declaration')
    require(receipt['engineering_capture'] == 'PASS', 'Failed captures remain failed')
    require(receipt['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'Original pending receipt was rewritten')
    require(receipt['missing_declared_artifacts'] == receipt['unexpected_durable_artifacts'] == [], 'Original durable set is incomplete')
    declared = declaration['declared_artifacts']
    require(len(declared) == len(set(declared)) and set(declared) == set(receipt['artifacts']), 'Declared and hashed durable sets differ')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not is_runtime_cache(path)}
    require(actual == set(declared) | {'receipt.json'}, 'Extra or missing delivered durable file')
    for name, expected in receipt['artifacts'].items():
        require(file_sha(safe(directory, name)) == expected, 'Changed original artifact: ' + name)
        require(git_blob_sha(root, delivery, relative + '/' + name) == expected, 'Committed delivery blob differs: ' + name)
    require(file_sha(directory / 'receipt.json') == git_blob_sha(root, delivery, relative + '/receipt.json'), 'Terminal receipt blob differs')
    execution = receipt['execution_commit']
    require(subprocess.run(['git', 'merge-base', '--is-ancestor', execution, delivery], cwd=root).returncode == 0,
            'Execution revision is not an ancestor of the delivery')
    book = read(directory / 'runbook-copy.json')
    require(book == read(root / BOOK) and relative == book['output_directory'], 'Frozen runbook or unique directory differs')
    expected_pins = pins(root, book)
    require(declaration['pinned_paths'] == {group: sorted(entries) for group, entries in expected_pins.items()}, 'Pinned path declaration differs')
    for group, entries in expected_pins.items():
        require(receipt[group] == entries, 'Runtime source/tool/input bytes drifted: ' + group)
        for name, expected in entries.items():
            require(git_blob_sha(root, execution, name) == expected, 'Recorded execution source/input differs: ' + name)
            require(git_blob_sha(root, delivery, name) == expected, 'Delivered source/tool/input differs: ' + name)
    require(receipt['python'] == dict(version=sys.version, implementation=sys.implementation.name,
        executable_sha256=file_sha(sys.executable)), 'Verification interpreter differs')
    require(receipt['numpy_version'] == importlib.metadata.version('numpy') == '2.3.5', 'Verification NumPy differs')
    for copied, original in [('runbook-copy.json', BOOK), ('profile-copy.json', book['profile']),
                             ('realization-primary-private.json', book['realization'])]:
        require(file_sha(directory / copied) == file_sha(root / original), 'Frozen copy differs: ' + copied)
    identity = original_identity(root, book)
    require(identity == read(directory / 'original-input-identity.json'), 'Original physical execution identity differs')
    require(receipt['old_physical_execution'] == book['original_execution_commit'] and receipt['new_physical_runs'] == 0,
            'Historical physical trajectory was reattributed or rerun')
    primary = read(directory / 'cli-primary/production-private.json')
    mismatch = read(directory / 'mismatch-production-private.json')
    profile, snapshots = read(directory / 'profile-copy.json'), read(directory / 'snapshots.json')
    checks = check(primary, mismatch, profile, snapshots, book)
    require(checks == read(directory / 'independent-checks.json'), 'Saved-data checks do not reproduce')
    require(primary['public_model'] == read(directory / 'public-model.json') == read(directory / 'cli-primary/public-model.json')
            == read(directory / 'cli/model.stdout.txt'), 'Public static model copies differ')
    require(primary['private_realization'] == read(directory / 'realization-primary-private.json')
            and mismatch['private_realization'] == read(directory / 'realization-mismatch-private.json'), 'Private realization copies differ')
    changed_realization = read(directory / 'realization-primary-private.json')
    changed_realization['biases'][book['mismatch_bias_key']] = book['mismatch_bias_value']
    require(changed_realization == mismatch['private_realization'], 'Mismatch changed more than the frozen calibration factor')
    require(primary['private_input_identity'] == mismatch['private_input_identity'], 'Private input identities differ')
    require(primary['private_input_identity']['original_archive_sha256'] == identity['archive_sha256']
            and primary['private_input_identity']['original_code_identity'] == identity['original_code_identity'], 'Saved input provenance differs')
    commands = read(directory / 'commands.json')
    require([(row['id'], row['exit_code']) for row in commands] ==
            [('primary', 0), ('model', 0), ('overwrite', 2), ('queued-profile', 2)], 'Actual CLI outcome ledger differs')
    preservation = read(directory / 'overwrite-preservation.json')
    require(preservation['status'] == 'PRESERVED' and preservation['hashes'] == {
        name: file_sha(directory / 'cli-primary' / name) for name in ('production-private.json', 'public-model.json')},
        'Actual overwrite refusal did not preserve output')
    require(read(directory / 'negative-profile.json')['ledger']['records'] == [primary['ledger']['records'][0]],
            'Rejected queued-profile example differs')
    with tempfile.TemporaryDirectory(prefix='aegisdc-16-svg-') as temporary:
        regenerated = Path(temporary)
        (regenerated / 'cli-primary').mkdir()
        for name in ('profile-copy.json', 'cli-primary/production-private.json', 'mismatch-production-private.json'):
            shutil.copyfile(directory / name, regenerated / name)
        figure = render(regenerated)
        require(figure == read(directory / 'figure-receipt.json'), 'Figure input/tool/output pins do not reproduce')
        for name in figure['outputs']:
            require(file_sha(regenerated / 'figures' / name) == file_sha(directory / 'figures' / name), 'Figure bytes differ: ' + name)
            svg = ET.parse(directory / 'figures' / name).getroot()
            require(svg.tag == '{http://www.w3.org/2000/svg}svg', 'Figure is not an SVG')
    regression = read(directory / 'full-check/summary.json')
    require(regression['overall'] == 'PASS' and receipt['full_regression_executions'] == book['full_regression_executions'] == 1,
            'One full author regression is required')
    require(regression['tests'] == receipt['full_tests'] and regression['tests']['gate'] == 'PASS'
            and regression['tests']['unexpected_skips'] == [], 'Saved full-regression outcome differs')
    require(regression['verified_original_files'] == receipt['verified_historical_originals'], 'Historical original count differs')
    require(read(directory / 'source-guard.json') == dict(status='PASS', before_commit=execution, after_commit=execution,
        tracked_dirty_before=False, tracked_dirty_after=False, verified_paths=sum(map(len, expected_pins.values())),
        source_tool_input_bytes_unchanged=True), 'Actual before/after execution source guard differs')
    attempt = read(directory / 'attempt-ledger.json')
    require(attempt['capture_id'] == book['capture_id'] and attempt['attempt'] == 1 and attempt['status'] == 'PASS'
            and attempt['terminal_stage'] == 'complete' and attempt['failure'] is None, 'Engineering attempt ledger differs')
    require((directory / 'capture-failure.txt').read_bytes() == b'', 'Successful capture has failure text')
    for record in (receipt, attempt, book):
        require(all(record[name] == 0 for name in ('registered_research_trials', 'model_calls', 'training_calls')),
                'Engineering delivery cannot claim research/model/training execution')
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == delivery
            and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip(),
            'Read-only fresh verification changed the delivery')
    return dict(schema='aegisdc-sensor-fresh-delivery-proof-v1', status='PASS', execution_commit=execution,
        delivery_commit=delivery, durable_artifacts=len(declared), terminal_receipts=1,
        pinned_runtime_sources=len(receipt['runtime_sources']), pinned_authoring_verification_tools=len(receipt['authoring_verification_tools']),
        pinned_inputs_and_development_originals=len(receipt['frozen_inputs']), old_physical_execution=book['original_execution_commit'],
        independent_checks=checks, full_tests=regression['tests'], verified_historical_originals=receipt['verified_historical_originals'],
        full_regression_rerun=False, observation_adapter_rerun=False, physics_rerun=False,
        original_receipt_rewritten=False, runtime_caches_required=0, registered_research_trials=0,
        model_calls=0, training_calls=0, field_calibration='PENDING', research_gain_claim='NOT_ESTABLISHED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.resolve().is_relative_to(args.root.resolve()), 'Write proof outside the read-only fresh checkout')
    result = verify(args.root, args.directory, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({name: result[name] for name in ('status', 'execution_commit', 'delivery_commit', 'durable_artifacts')}))
