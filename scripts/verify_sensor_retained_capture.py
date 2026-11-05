"""Verify retained failed capture bytes and the separate two-test environment closure."""
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
from capture_sensor_engineering import original_identity
from close_sensor_environment import PROTOCOL, check_original
from plot_sensor_channels import render
from sensor_engineering_checks import check, require
from verify_sensor_delivery import read, safe


def durable_set(root, directory, revision, missing):
    receipt, declaration = read(directory / 'receipt.json'), read(directory / 'declaration.json')
    declared = declaration['declared_artifacts']
    require(len(declared) == len(set(declared)), 'Duplicate durable declaration')
    require(receipt['missing_declared_artifacts'] == missing and receipt['unexpected_durable_artifacts'] == [],
            'Durable-set exceptions differ from the exact registered failure')
    require(set(receipt['artifacts']) == set(declared) - set(missing), 'Hashed durable set differs from declaration minus exact missing roles')
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and not is_runtime_cache(p)}
    require(actual == set(receipt['artifacts']) | {'receipt.json'}, 'Extra or missing durable file')
    relative = directory.relative_to(root).as_posix()
    for name, expected in receipt['artifacts'].items():
        require(file_sha(safe(directory, name)) == expected == git_blob_sha(root, revision, relative + '/' + name),
                'Durable bytes or committed blob differ: ' + relative + '/' + name)
    require(file_sha(directory / 'receipt.json') == git_blob_sha(root, revision, relative + '/receipt.json'), 'Terminal receipt differs from committed blob')
    return receipt, declaration


def verify(root, delivery_commit):
    root = root.resolve()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit], cwd=root, text=True).strip()
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == delivery,
            'Use a fresh checkout of the exact delivery revision')
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip(), 'Fresh checkout must be clean')
    addendum = read(root / PROTOCOL)
    original_dir = root / addendum['original_capture']
    original, declaration = durable_set(root, original_dir, delivery, addendum['original_declared_missing'])
    require(original['schema'] == 'aegisdc-sensor-engineering-receipt-v1'
            and original['execution_commit'] == addendum['original_execution_commit'], 'Original observation execution identity differs')
    require(original['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT' and original['engineering_capture'] == 'FAIL',
            'Original failed pending receipt cannot be rewritten or upgraded')
    check_original(root, addendum)
    require(file_sha(original_dir / 'receipt.json') == git_blob_sha(root, addendum['original_delivery_commit'], addendum['original_capture'] + '/receipt.json'),
            'Original failure differs from its first committed delivery')
    for prior in (addendum['original_execution_commit'], addendum['original_delivery_commit']):
        require(subprocess.run(['git', 'merge-base', '--is-ancestor', prior, delivery], cwd=root).returncode == 0,
                'Historical execution/delivery is not an ancestor')
    for group in ('runtime_sources', 'authoring_verification_tools', 'frozen_inputs'):
        require(declaration['pinned_paths'][group] == sorted(original[group]), 'Original declared source/tool/input set differs')
        for name, expected in original[group].items():
            require(git_blob_sha(root, delivery, name) == expected, 'Original delivered source/tool/input drifted: ' + name)
    require(original['python'] == dict(version=sys.version, implementation=sys.implementation.name,
        executable_sha256=file_sha(sys.executable)) and original['numpy_version'] == importlib.metadata.version('numpy') == '2.3.5',
        'Verification runtime differs from the recorded observation execution')
    book = read(original_dir / 'runbook-copy.json')
    for copied, origin in [('runbook-copy.json', 'docs/mainline/16-sensor-runbook.json'),
                           ('profile-copy.json', book['profile']), ('realization-primary-private.json', book['realization'])]:
        require(file_sha(original_dir / copied) == file_sha(root / origin), 'Original frozen input copy differs: ' + copied)
    identity = original_identity(root, book)
    require(identity == read(original_dir / 'original-input-identity.json'), 'Original physical archive/source identity differs')
    primary = read(original_dir / 'cli-primary/production-private.json')
    mismatch = read(original_dir / 'mismatch-production-private.json')
    profile, snapshots = read(original_dir / 'profile-copy.json'), read(original_dir / 'snapshots.json')
    checks = check(primary, mismatch, profile, snapshots, book)
    require(checks == read(original_dir / 'independent-checks.json'), 'Saved observation-component checks do not reproduce')
    require(primary['private_input_identity'] == mismatch['private_input_identity']
            and primary['private_input_identity']['original_archive_sha256'] == identity['archive_sha256']
            and primary['private_input_identity']['original_code_identity'] == identity['original_code_identity'], 'Physical input provenance differs')
    require(primary['public_model'] == read(original_dir / 'public-model.json')
            == read(original_dir / 'cli-primary/public-model.json') == read(original_dir / 'cli/model.stdout.txt'), 'Public model copies differ')
    require(primary['private_realization'] == read(original_dir / 'realization-primary-private.json')
            and mismatch['private_realization'] == read(original_dir / 'realization-mismatch-private.json'), 'Private realization copies differ')
    changed = read(original_dir / 'realization-primary-private.json')
    changed['biases'][book['mismatch_bias_key']] = book['mismatch_bias_value']
    require(changed == mismatch['private_realization'], 'Mismatch changed more than its frozen calibration factor')
    commands = read(original_dir / 'commands.json')
    require([(row['id'], row['exit_code']) for row in commands] ==
            [('primary', 0), ('model', 0), ('overwrite', 2), ('queued-profile', 2)], 'Original CLI outcome ledger differs')
    preservation = read(original_dir / 'overwrite-preservation.json')
    require(preservation['status'] == 'PRESERVED' and preservation['hashes'] == {
        name: file_sha(original_dir / 'cli-primary' / name) for name in ('production-private.json', 'public-model.json')}, 'Actual overwrite-preservation proof differs')
    require(read(original_dir / 'negative-profile.json')['ledger']['records'] == [primary['ledger']['records'][0]], 'Rejected queued-profile payload differs')
    with tempfile.TemporaryDirectory(prefix='aegisdc-16-retained-svg-') as temporary:
        regenerated = Path(temporary)
        (regenerated / 'cli-primary').mkdir()
        for name in ('profile-copy.json', 'cli-primary/production-private.json', 'mismatch-production-private.json'):
            shutil.copyfile(original_dir / name, regenerated / name)
        figure = render(regenerated)
        require(figure == read(original_dir / 'figure-receipt.json'), 'Saved-data figures do not reproduce')
        for name in figure['outputs']:
            require(file_sha(regenerated / 'figures' / name) == file_sha(original_dir / 'figures' / name), 'SVG bytes differ: ' + name)
            require(ET.parse(original_dir / 'figures' / name).getroot().tag == '{http://www.w3.org/2000/svg}svg', 'Invalid SVG')
    full = read(original_dir / 'full-check/summary.json')
    require({name: full['tests'][name] for name in addendum['original_full_tests']} == addendum['original_full_tests']
            and full['tests'] == original['full_tests'] and full['overall'] == 'FAIL', 'Original full regression was changed or relabeled')
    require(full['tests']['unexpected_skips'] == [] and full['verified_original_files'] == original['verified_historical_originals'] == 20,
            'Saved historical evidence/optional-skip outcome differs')
    attempt = read(original_dir / 'attempt-ledger.json')
    require(attempt['status'] == 'FAIL' and attempt['attempt'] == 1 and attempt['terminal_stage'] == 'one-frozen-full-regression'
            and attempt['full_regression_executions'] == original['full_regression_executions'] == 1, 'Original failed-attempt ledger differs')
    closure_dir = root / addendum['closure_output']
    closure, closure_declaration = durable_set(root, closure_dir, delivery, [])
    require(closure['status'] == 'PASS_NARROW_ENVIRONMENT_CLOSURE_ONLY'
            and closure['narrow_tests'] == dict(run=2, failures=0, errors=0, skipped=0), 'Narrow closure did not pass exactly two tests')
    require(closure['original_capture_status'] == closure['original_full_regression_remains'] == 'FAIL'
            and closure['global_regression_gate'] == addendum['global_regression_gate'], 'Narrow closure overstates the original global result')
    require(read(closure_dir / 'protocol-copy.json') == addendum, 'Frozen environment-closure protocol differs')
    require(set(closure['new_verification_tools']) == set(addendum['new_verification_paths']), 'New verifier/closure tool declaration differs')
    for name, expected in closure['new_verification_tools'].items():
        require(file_sha(root / name) == expected == git_blob_sha(root, closure['execution_commit'], name)
                == git_blob_sha(root, delivery, name), 'New frozen closure/verifier bytes differ: ' + name)
    children = read(closure_dir / 'children.json')
    require([row['test_id'] for row in children] == [row['test_id'] for row in addendum['original_results']]
            and children[0]['exit_code'] == 0 and children[1]['exit_code'] != 0, 'Two actual CLI execution identities differ')
    require((closure_dir / 'cli/0.stderr.txt').read_bytes() == b''
            and 'Duplicate JSON object key' in (closure_dir / 'cli/1.stderr.txt').read_text(encoding='utf-8'), 'Actual text-mode child stderr differs')
    guard = read(closure_dir / 'source-guard.json')
    require(guard == dict(status='PASS', before_commit=closure['execution_commit'], after_commit=closure['execution_commit'],
        observation_execution_commit=original['execution_commit'], original_capture_bytes_unchanged=True,
        original_runtime_tool_input_bytes_unchanged=True, closure_tool_bytes_unchanged=True), 'Narrow closure source/byte guard differs')
    require((closure_dir / 'failure.txt').read_bytes() == b'', 'Successful narrow closure has failure text')
    for record in (original, attempt, closure, addendum):
        require(all(record[name] == 0 for name in ('registered_research_trials', 'model_calls', 'training_calls')),
                'Engineering records cannot claim research/model/training execution')
    require(all(closure[name] == 0 for name in ('full_regression_reruns', 'observation_adapter_reruns', 'new_physical_runs')),
            'Narrow closure ran work outside its declared scope')
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == delivery
            and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip(), 'Read-only verification changed the fresh checkout')
    return dict(schema='aegisdc-sensor-retained-capture-fresh-proof-v1', status='PASS_SAVED_DATA_AND_NARROW_CLOSURE_ONLY',
        delivery_commit=delivery, observation_execution_commit=original['execution_commit'], closure_execution_commit=closure['execution_commit'],
        original_capture_status='FAIL', original_full_tests=full['tests'], original_missing_declared=addendum['original_declared_missing'],
        original_durable_files=len(original['artifacts']) + 1, closure_durable_files=len(closure['artifacts']) + 1,
        observation_component='PASS_FROM_ORIGINAL_SAVED_DATA', independent_checks=checks, narrow_tests=closure['narrow_tests'],
        global_regression_gate=addendum['global_regression_gate'], old_physical_execution=book['original_execution_commit'],
        full_regression_rerun=False, observation_adapter_rerun=False, physics_rerun=False, original_receipt_rewritten=False,
        runtime_caches_required=0, registered_research_trials=0, model_calls=0, training_calls=0,
        field_calibration='PENDING', research_gain_claim='NOT_ESTABLISHED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--delivery-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.resolve().is_relative_to(args.root.resolve()), 'Write proof outside the read-only fresh checkout')
    result = verify(args.root, args.delivery_commit)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({name: result[name] for name in ('status', 'delivery_commit', 'observation_execution_commit', 'closure_execution_commit')}))
