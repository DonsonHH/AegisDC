"""Minimal versioned finite-endpoint admission correction and fresh proof."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.evidence_ledger import EvidenceLedger
from capture_evidence_engineering import file_sha, git_blob_sha, is_runtime_cache, write
from qualify_evidence_correction import pins as correction_pins, precision_cases, require

BOOK = 'docs/mainline/14-evidence-admission-runbook.json'


def pins(root):
    result = correction_pins(root)
    result['frozen_inputs'][BOOK] = file_sha(root / BOOK)
    return result


def retained(root, book):
    previous = root / book['previous_directory']
    record = json.loads((previous / 'receipt.json').read_text(encoding='utf-8'))
    original_book = json.loads((previous / 'runbook-copy.json').read_text(encoding='utf-8'))
    require(record['execution_commit'] == book['previous_execution_commit'], 'Prior corrected execution differs')
    files = json.loads((previous / 'prior-preservation.json').read_text(encoding='utf-8'))
    revisions = {name: original_book['previous_proof_commit'] if name == original_book['previous_fresh_proof']
                 else original_book['previous_delivery_commit'] for name in files}
    for name, expected in record['artifacts'].items():
        identifier = book['previous_directory'] + '/' + name
        files[identifier] = expected
        revisions[identifier] = book['previous_delivery_commit']
    terminal = book['previous_directory'] + '/receipt.json'
    files[terminal] = git_blob_sha(root, book['previous_delivery_commit'], terminal)
    revisions[terminal] = book['previous_delivery_commit']
    files[book['previous_fresh_proof']] = git_blob_sha(root, book['previous_proof_commit'], book['previous_fresh_proof'])
    revisions[book['previous_fresh_proof']] = book['previous_proof_commit']
    for name, expected in files.items():
        require(file_sha(root / name) == expected, 'Retained original changed: ' + name)
        require(git_blob_sha(root, revisions[name], name) == expected, 'Retained committed blob differs: ' + name)
    historical = {group: record[group] for group in ('runtime_sources', 'authoring_verification_tools', 'frozen_inputs')}
    for entries in historical.values():
        for name, expected in entries.items():
            require(git_blob_sha(root, book['previous_execution_commit'], name) == expected, 'Prior execution source differs: ' + name)
            require(git_blob_sha(root, book['previous_delivery_commit'], name) == expected, 'Prior source delivery differs: ' + name)
    proof = json.loads((root / book['previous_fresh_proof']).read_text(encoding='utf-8'))
    require(proof['status'] == 'PASS' and proof['delivery_commit'] == book['previous_delivery_commit'], 'Prior fresh proof differs')
    return dict(file_hashes=files, source_attribution=historical, source_execution=book['previous_execution_commit'])


def inputs():
    integer = precision_cases()['integer-zero']
    integer['id'] = 'V6-bound-admission-engineering-example-v1'
    integer['records'] = integer['records'][:1]
    integer['records'][0]['value'] = int(sys.float_info.max) - 1
    integer['records'][0]['quality']['error_bound'] = 2 ** 970
    floating = deepcopy(integer)
    floating['records'][0]['quality']['error_bound'] = float(2 ** 970)
    return dict(integer=integer, floating=floating)


def outcomes(cases):
    require(cases['integer'] == cases['floating'], 'Admission inputs are not numerically equal')
    snapshots = {name: EvidenceLedger(document).snapshot(0) for name, document in cases.items()}
    require(snapshots['integer'] == snapshots['floating'], 'Equal decoded bounds changed admission or snapshot')
    require(all(snapshot['current_record_ids'] == ['left'] for snapshot in snapshots.values()), 'Counterexample evidence missing')
    return dict(status='PASS', input_numeric_content_equal=True, load_status=dict(integer='ACCEPTED', floating='ACCEPTED'),
                snapshots=snapshots, input_values_and_error_bounds_modified=False)


def capture(directory):
    directory = directory.resolve()
    directory.relative_to(ROOT)
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip(), 'Freeze source/tool/input changes before capture')
    frozen = pins(ROOT)
    for entries in frozen.values():
        for name, expected in entries.items():
            require(git_blob_sha(ROOT, execution, name) == expected, 'Uncommitted authoring source: ' + name)
    book = json.loads((ROOT / BOOK).read_text(encoding='utf-8'))
    declared = ['declaration.json', 'runbook-copy.json', 'input-integer.json', 'input-floating.json',
                'outcomes.json', 'target.stdout.txt', 'target.stderr.txt', 'prior-retained.json', 'capture-failure.txt']
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / 'declaration.json', dict(schema='aegisdc-evidence-admission-declaration-v1',
        declared_artifacts=declared, terminal_receipt='receipt.json', runtime_caches='NOT_DELIVERABLE',
        classification='ENGINEERING_ARITHMETIC_CORRECTION_NOT_RESEARCH'))
    receipt = dict(schema='aegisdc-evidence-admission-receipt-v1', execution_commit=execution, **frozen,
        engineering_capture='FAIL', delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT',
        python=dict(version=sys.version, implementation=sys.implementation.name, executable_sha256=file_sha(sys.executable)),
        full_regression_executions=0, latest_full_regression='ROOT_INTEGRATION_REQUIRED',
        registered_research_trials=0, model_calls=0, training_calls=0)
    failure = ''
    try:
        (directory / 'runbook-copy.json').write_bytes((ROOT / BOOK).read_bytes())
        prior = retained(ROOT, book)
        write(directory / 'prior-retained.json', prior)
        cases = inputs()
        for name, document in cases.items():
            write(directory / ('input-' + name + '.json'), document)
        write(directory / 'outcomes.json', outcomes(cases))
        command = [sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests', '-p', book['target_pattern']]
        tested = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True)
        (directory / 'target.stdout.txt').write_bytes(tested.stdout)
        (directory / 'target.stderr.txt').write_bytes(tested.stderr)
        stderr = tested.stderr.decode('utf-8')
        count = re.search(r'Ran (\d+) tests', stderr)
        require(tested.returncode == 0 and count and int(count.group(1)) == book['expected_target_tests']
                and 'skipped=' not in stderr, 'Targeted admission regressions failed or skipped')
        receipt.update(engineering_capture='PASS', target_command=command, target_exit=0,
            target_tests=int(count.group(1)), preserved_prior_originals=len(prior['file_hashes']),
            previous_corrected_source_entries=sum(map(len, prior['source_attribution'].values())))
    except Exception as error:
        failure = traceback.format_exc()
        receipt['failure'] = dict(type=type(error).__name__, message=str(error))
    finally:
        (directory / 'capture-failure.txt').write_text(failure, encoding='utf-8', newline='\n')
        durable = {path.relative_to(directory).as_posix() for path in directory.rglob('*') if path.is_file() and not is_runtime_cache(path)}
        receipt['missing_declared_artifacts'] = sorted(set(declared) - durable)
        receipt['unexpected_durable_artifacts'] = sorted(durable - set(declared))
        if receipt['missing_declared_artifacts'] or receipt['unexpected_durable_artifacts']:
            receipt['engineering_capture'] = 'FAIL'
        receipt['artifacts'] = {name: file_sha(directory / name) for name in sorted(durable)}
        write(directory / 'receipt.json', receipt)
    return receipt


def verify(root, directory, delivery_commit):
    root, directory = root.resolve(), directory.resolve()
    relative = directory.relative_to(root).as_posix()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit], cwd=root, text=True).strip()
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == delivery, 'Use a fresh admission delivery checkout')
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    require(receipt['schema'] == 'aegisdc-evidence-admission-receipt-v1' and receipt['engineering_capture'] == 'PASS', 'Unsupported or failed admission capture')
    require(receipt['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'Original admission receipt changed')
    require(set(receipt['artifacts']) == set(declaration['declared_artifacts']), 'Admission durable declaration differs')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*') if path.is_file() and not is_runtime_cache(path)}
    require(actual == set(receipt['artifacts']) | {'receipt.json'}, 'Extra or missing admission original')
    for name in list(receipt['artifacts']) + ['receipt.json']:
        path = (directory / name).resolve()
        require(path.is_relative_to(directory), 'Admission original escapes directory')
        expected = git_blob_sha(root, delivery, relative + '/' + name)
        require(file_sha(path) == expected, 'Admission original differs from committed blob')
        if name != 'receipt.json':
            require(expected == receipt['artifacts'][name], 'Admission artifact manifest differs')
    for group, entries in pins(root).items():
        require(entries == receipt[group], 'Admission source/tool/input bytes differ')
        for name, expected in entries.items():
            require(git_blob_sha(root, receipt['execution_commit'], name) == expected, 'Recorded admission execution differs')
            require(git_blob_sha(root, delivery, name) == expected, 'Delivered admission source differs')
    require(receipt['python'] == dict(version=sys.version, implementation=sys.implementation.name,
        executable_sha256=file_sha(sys.executable)), 'Admission interpreter differs')
    book = json.loads((directory / 'runbook-copy.json').read_text(encoding='utf-8'))
    require(book == json.loads((root / BOOK).read_text(encoding='utf-8')), 'Admission runbook differs')
    prior = retained(root, book)
    require(prior == json.loads((directory / 'prior-retained.json').read_text(encoding='utf-8')), 'Retained correction history differs')
    cases = {name: json.loads((directory / ('input-' + name + '.json')).read_text(encoding='utf-8')) for name in ('integer', 'floating')}
    require(cases == inputs(), 'Admission counterexample does not reauthor')
    require(outcomes(cases) == json.loads((directory / 'outcomes.json').read_text(encoding='utf-8')), 'Admission outcomes do not reproduce')
    require(receipt['target_tests'] == book['expected_target_tests'] and receipt['target_exit'] == 0 and receipt['full_regression_executions'] == 0, 'Admission qualification scope differs')
    return dict(schema='aegisdc-evidence-admission-fresh-proof-v1', status='PASS',
        execution_commit=receipt['execution_commit'], delivery_commit=delivery, durable_artifacts=len(receipt['artifacts']),
        terminal_receipts=1, target_tests=receipt['target_tests'], admission_encodings_accepted=2,
        preserved_prior_originals=len(prior['file_hashes']), previous_corrected_source_entries=receipt['previous_corrected_source_entries'],
        pinned_runtime_sources=len(receipt['runtime_sources']), pinned_tools=len(receipt['authoring_verification_tools']),
        pinned_inputs=len(receipt['frozen_inputs']), full_regression_rerun=False, physics_rerun=False,
        latest_full_regression='ROOT_INTEGRATION_REQUIRED', registered_research_trials=0, model_calls=0,
        training_calls=0, runtime_caches_required=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    make = sub.add_parser('capture')
    make.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('verify')
    check.add_argument('--directory', type=Path, required=True)
    check.add_argument('--delivery-commit', required=True)
    check.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'capture':
        result = capture(args.output)
        print(json.dumps({key: result[key] for key in ('engineering_capture', 'execution_commit')}))
        raise SystemExit(0 if result['engineering_capture'] == 'PASS' else 1)
    require(not args.output.resolve().is_relative_to(ROOT), 'Write proof outside the read-only fresh checkout')
    result = verify(ROOT, args.directory, args.delivery_commit)
    write(args.output, result)
    print(json.dumps({key: result[key] for key in ('status', 'execution_commit', 'delivery_commit', 'durable_artifacts')}))
