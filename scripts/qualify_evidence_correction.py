"""Versioned exact-bound/figure correction; no full regression or plant run."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.evidence_ledger import EvidenceLedger
from build_evidence_fixture import build
from capture_evidence_engineering import file_sha, git_blob_sha, is_runtime_cache, pin_paths, write
from plot_evidence_ledger import render

BOOK = 'docs/mainline/14-evidence-correction-runbook.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pins(root):
    paths = pin_paths(root)
    paths['frozen_inputs'].append(BOOK)
    paths['frozen_inputs'].sort()
    return {group: {name: file_sha(root / name) for name in names} for group, names in paths.items()}


def previous_delivery(root, book):
    """Verify historical sources against their revisions, not the corrected runtime."""
    folder = root / book['previous_directory']
    old = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
    require(old['execution_commit'] == book['previous_execution_commit'], 'Historical execution identity differs')
    files = {book['previous_directory'] + '/' + name: expected for name, expected in old['artifacts'].items()}
    files[book['previous_directory'] + '/receipt.json'] = git_blob_sha(root, book['previous_delivery_commit'], book['previous_directory'] + '/receipt.json')
    files[book['previous_fresh_proof']] = git_blob_sha(root, book['previous_proof_commit'], book['previous_fresh_proof'])
    for name, expected in files.items():
        require(file_sha(root / name) == expected, 'Historical original changed: ' + name)
        revision = book['previous_proof_commit'] if name == book['previous_fresh_proof'] else book['previous_delivery_commit']
        require(git_blob_sha(root, revision, name) == expected, 'Historical delivery blob differs: ' + name)
    historical_sources = {}
    for group in ('runtime_sources', 'authoring_verification_tools', 'frozen_inputs'):
        for name, expected in old[group].items():
            require(git_blob_sha(root, book['previous_execution_commit'], name) == expected, 'Historical execution source differs: ' + name)
            require(git_blob_sha(root, book['previous_delivery_commit'], name) == expected, 'Historical delivered source differs: ' + name)
            historical_sources[name] = expected
    proof = json.loads((root / book['previous_fresh_proof']).read_text(encoding='utf-8'))
    require(proof['status'] == 'PASS' and proof['delivery_commit'] == book['previous_delivery_commit'], 'Historical fresh proof differs')
    return files, historical_sources


def precision_cases():
    base = build()
    base['id'] = 'V6-declared-bound-engineering-example-v1'
    prototype = next(row for row in base['records'] if row['id'] == 'handheld-negative')
    result = {}
    for name, a, ea, b, eb in [('integer-zero', 9007199254740992, 0, 9007199254740993, 0),
                              ('floating-zero', 9007199254740992, 0.0, 9007199254740993, 0.0),
                              ('binary64-positive-gap', 1.0, 2.7755575615628914e-17,
                               1.0000000000000002, 1.6653345369377348e-16)]:
        document = deepcopy(base)
        document['records'] = []
        for identifier, value, error in [('left', a, ea), ('right', b, eb)]:
            row = deepcopy(prototype)
            row.update(id=identifier, value=value, observed_at_s=0, arrived_at_s=0, valid_until_s=None)
            row['quality']['error_bound'] = error
            row['provenance'] = dict(origin_id='origin-' + identifier, copied_from_record_id=None)
            document['records'].append(row)
        result[name] = document
    return result


def outcomes(cases, book):
    require(set(cases) == set(book['precision_cases']), 'Precision case set differs')
    snapshots = {name: EvidenceLedger(document).snapshot(0) for name, document in cases.items()}
    for name, snapshot in snapshots.items():
        require([row['record_ids'] for row in snapshot['conflicts']] == book['expected_conflict_pairs_each'], 'Positive gap disappeared: ' + name)
    ledger = EvidenceLedger(cases['integer-zero'])
    before = json.dumps(ledger.snapshot(0), sort_keys=True)
    equivalent = deepcopy(cases['integer-zero']['records'][1])
    equivalent['quality']['error_bound'] = 0.0
    require(equivalent == cases['integer-zero']['records'][1], 'Duplicate is not numerically equal')
    result = ledger.ingest(equivalent)
    unchanged = before == json.dumps(ledger.snapshot(0), sort_keys=True)
    require(result == book['duplicate_ingest_result'] and unchanged is True, 'Equal duplicate changed encoding or outcome')
    duplicated = deepcopy(cases['integer-zero'])
    duplicated['records'].append(equivalent)
    constructor_unchanged = before == json.dumps(EvidenceLedger(duplicated).snapshot(0), sort_keys=True)
    require(constructor_unchanged, 'Duplicate constructor changed first accepted representation')
    integer_time = deepcopy(cases['integer-zero'])
    floating_time = deepcopy(integer_time)
    for row in floating_time['records']:
        row.update(observed_at_s=0.0, arrived_at_s=0.0)
    instant = book['large_integral_age_s']
    integer_snapshot = EvidenceLedger(integer_time).snapshot(instant)
    floating_snapshot = EvidenceLedger(floating_time).snapshot(instant)
    require(integer_snapshot == floating_snapshot, 'Equivalent timestamp encodings changed age')
    require(all(row['age_s'] == instant and type(row['age_s']) is int for row in floating_snapshot['records']), 'Integral age lost precision')
    fractional_age = EvidenceLedger(integer_time).snapshot(book['fractional_age_s'])['records'][0]['age_s']
    require(fractional_age == book['fractional_age_s'] and type(fractional_age) is float, 'Fractional age representation differs')
    overflow = deepcopy(integer_time)
    for row in overflow['records']:
        row['observed_at_s'] = -(2 ** 1023)
    try:
        EvidenceLedger(overflow).snapshot(2 ** 1023)
    except ValueError as error:
        overflow_error = dict(type=type(error).__name__, message=str(error))
    else:
        raise ValueError('Unsupported age overflow was silently accepted')
    return dict(status='PASS', snapshots=snapshots, equivalent_ingest_result=result,
                duplicate_serialization_unchanged=unchanged, duplicate_constructor_unchanged=constructor_unchanged,
                binary64_positive_gap_exact=book['binary64_positive_gap_exact'],
                age_examples=dict(integer_input=integer_time, floating_input=floating_time, as_of_s=instant,
                    integer_snapshot=integer_snapshot, floating_snapshot=floating_snapshot,
                    fractional_age_s=fractional_age, overflow_input=overflow, overflow_as_of_s=2 ** 1023,
                    overflow_error=overflow_error))


def capture(directory):
    directory = directory.resolve()
    directory.relative_to(ROOT)
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip(), 'Commit corrected source/tools/runbook before capture')
    frozen = pins(ROOT)
    for group in frozen.values():
        for name, expected in group.items():
            require(git_blob_sha(ROOT, execution, name) == expected, 'Uncommitted execution input: ' + name)
    book = json.loads((ROOT / BOOK).read_text(encoding='utf-8'))
    declared = ['declaration.json', 'runbook-copy.json', 'cases.json', 'outcomes.json',
                'target.stdout.txt', 'target.stderr.txt', 'prior-preservation.json', 'prior-frozen-source.json',
                'original-fixture-snapshots.json', 'capture-failure.txt', 'figure-checks.json',
                'figures/arrival-timeline.svg', 'figures/source-architecture.svg']
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / 'declaration.json', dict(schema='aegisdc-evidence-correction-declaration-v1',
        declared_artifacts=sorted(declared), terminal_receipt='receipt.json', runtime_caches='NOT_DELIVERABLE',
        classification='ENGINEERING_CORRECTION_NOT_RESEARCH'))
    receipt = dict(schema='aegisdc-evidence-correction-receipt-v1', execution_commit=execution,
        engineering_capture='FAIL', delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', **frozen,
        python=dict(version=sys.version, implementation=sys.implementation.name, executable_sha256=file_sha(sys.executable)),
        started_at_utc=datetime.now(timezone.utc).isoformat(), full_regression_executions=0,
        old_full_regression_execution=book['previous_execution_commit'], latest_full_regression='ROOT_INTEGRATION_REQUIRED',
        registered_research_trials=0, model_calls=0, training_calls=0, research_gain_claim='NOT_ESTABLISHED')
    failure = ''
    try:
        (directory / 'runbook-copy.json').write_bytes((ROOT / BOOK).read_bytes())
        originals, historical_sources = previous_delivery(ROOT, book)
        write(directory / 'prior-preservation.json', originals)
        write(directory / 'prior-frozen-source.json', historical_sources)
        cases = precision_cases()
        write(directory / 'cases.json', cases)
        write(directory / 'outcomes.json', outcomes(cases, book))
        fixture = build()
        original_book = json.loads((ROOT / book['original_snapshot_runbook']).read_text(encoding='utf-8'))
        snapshots = {case['id']: EvidenceLedger(fixture).snapshot(case['as_of_s']) for case in original_book['snapshots']}
        require(snapshots == json.loads((ROOT / book['previous_directory'] / 'snapshots.json').read_text(encoding='utf-8')), 'Original fixture outcomes changed')
        write(directory / 'original-fixture-snapshots.json', snapshots)
        (directory / 'figures').mkdir()
        render(fixture, directory / 'figures')
        figures = {}
        for name in ('arrival-timeline.svg', 'source-architecture.svg'):
            svg = ET.fromstring((directory / 'figures' / name).read_bytes())
            require(svg.tag == '{http://www.w3.org/2000/svg}svg', 'Malformed versioned SVG')
            figures[name] = dict(sha256=file_sha(directory / 'figures' / name), width=svg.attrib['width'], height=svg.attrib['height'])
        write(directory / 'figure-checks.json', dict(version=2, status='XML_AND_SOURCE_CHECKED',
            source_fixture_sha256=file_sha(ROOT / book['fixture']), figures=figures,
            interpretation='Both off-scale ends use arrows; actual 600 s expiry is printed; original figures retained'))
        command = [sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests', '-p', book['target_pattern']]
        tested = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True)
        (directory / 'target.stdout.txt').write_bytes(tested.stdout)
        (directory / 'target.stderr.txt').write_bytes(tested.stderr)
        count = re.search(r'Ran (\d+) tests', tested.stderr.decode('utf-8'))
        require(tested.returncode == 0 and count and int(count.group(1)) == book['expected_target_tests'], 'Targeted evidence regressions failed')
        receipt.update(engineering_capture='PASS', target_command=command, target_exit=0,
                       target_tests=int(count.group(1)), preserved_prior_originals=len(originals),
                       historical_source_tool_inputs=len(historical_sources))
    except Exception as error:
        failure = traceback.format_exc()
        receipt['failure'] = dict(type=type(error).__name__, message=str(error))
    finally:
        (directory / 'capture-failure.txt').write_text(failure, encoding='utf-8', newline='\n')
        durable = sorted(path.relative_to(directory).as_posix() for path in directory.rglob('*') if path.is_file() and not is_runtime_cache(path))
        receipt['missing_declared_artifacts'] = sorted(set(declared) - set(durable))
        receipt['unexpected_durable_artifacts'] = sorted(set(durable) - set(declared))
        if receipt['missing_declared_artifacts'] or receipt['unexpected_durable_artifacts']:
            receipt['engineering_capture'] = 'FAIL'
        receipt['artifacts'] = {name: file_sha(directory / name) for name in durable}
        write(directory / 'receipt.json', receipt)
    return receipt


def verify(root, directory, delivery_commit):
    root, directory = root.resolve(), directory.resolve()
    relative = directory.relative_to(root).as_posix()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    delivery = subprocess.check_output(['git', 'rev-parse', delivery_commit], cwd=root, text=True).strip()
    require(head == delivery, 'Use a fresh checkout at the declared correction delivery')
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    declaration = json.loads((directory / 'declaration.json').read_text(encoding='utf-8'))
    require(receipt['schema'] == 'aegisdc-evidence-correction-receipt-v1' and receipt['engineering_capture'] == 'PASS', 'Unsupported or failed correction receipt')
    require(receipt['delivery_gate'] == 'PENDING_COMMIT_AND_FRESH_CHECKOUT', 'Original correction receipt was rewritten')
    require(set(declaration['declared_artifacts']) == set(receipt['artifacts']), 'Correction durable set differs')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*') if path.is_file() and not is_runtime_cache(path)}
    require(actual == set(receipt['artifacts']) | {'receipt.json'}, 'Extra or missing correction artifact')
    for name in list(receipt['artifacts']) + ['receipt.json']:
        path = (directory / name).resolve()
        require(path.is_relative_to(directory), 'Correction artifact escapes directory')
        expected = git_blob_sha(root, delivery, relative + '/' + name)
        require(file_sha(path) == expected, 'Correction delivery blob differs: ' + name)
        if name != 'receipt.json':
            require(expected == receipt['artifacts'][name], 'Correction manifest differs: ' + name)
    current_pins = pins(root)
    require(receipt['python'] == dict(version=sys.version, implementation=sys.implementation.name,
        executable_sha256=file_sha(sys.executable)), 'Correction interpreter differs')
    for group in current_pins:
        require(current_pins[group] == receipt[group], 'Correction runtime/tools/inputs differ: ' + group)
        for name, expected in receipt[group].items():
            require(git_blob_sha(root, receipt['execution_commit'], name) == expected, 'Correction execution source differs: ' + name)
            require(git_blob_sha(root, delivery, name) == expected, 'Correction delivered source differs: ' + name)
    book = json.loads((directory / 'runbook-copy.json').read_text(encoding='utf-8'))
    require(book == json.loads((root / BOOK).read_text(encoding='utf-8')), 'Correction runbook differs')
    originals, historical_sources = previous_delivery(root, book)
    require(originals == json.loads((directory / 'prior-preservation.json').read_text(encoding='utf-8')), 'Prior originals changed')
    require(historical_sources == json.loads((directory / 'prior-frozen-source.json').read_text(encoding='utf-8')), 'Historical source attribution differs')
    cases = json.loads((directory / 'cases.json').read_text(encoding='utf-8'))
    require(cases == precision_cases(), 'Precision cases do not reauthor')
    require(outcomes(cases, book) == json.loads((directory / 'outcomes.json').read_text(encoding='utf-8')), 'Exact-gap outcomes do not reproduce')
    old_snapshots = json.loads((root / book['previous_directory'] / 'snapshots.json').read_text(encoding='utf-8'))
    require(old_snapshots == json.loads((directory / 'original-fixture-snapshots.json').read_text(encoding='utf-8')), 'Original example semantics changed')
    # Re-author figures in memory-adjacent temporary files, without modifying the checkout.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='aegisdc-14-correction-svg-') as temporary:
        render(build(), Path(temporary))
        for name in ('arrival-timeline.svg', 'source-architecture.svg'):
            require(file_sha(Path(temporary) / name) == file_sha(directory / 'figures' / name), 'Corrected SVG does not reproduce')
    require(receipt['target_tests'] == book['expected_target_tests'] and receipt['target_exit'] == 0, 'Saved target gate differs')
    require(receipt['full_regression_executions'] == 0, 'Do not reattribute the old full run to corrected source')
    return dict(schema='aegisdc-evidence-correction-fresh-proof-v1', status='PASS',
        execution_commit=receipt['execution_commit'], delivery_commit=delivery,
        durable_artifacts=len(receipt['artifacts']), terminal_receipts=1,
        preserved_prior_originals=len(originals), historical_source_tool_inputs=len(historical_sources),
        pinned_runtime_sources=len(receipt['runtime_sources']),
        pinned_authoring_verification_tools=len(receipt['authoring_verification_tools']),
        pinned_inputs=len(receipt['frozen_inputs']), target_tests=receipt['target_tests'],
        precision_cases=3, exact_gap='1/36028797018963968', duplicate_encoding_preserved=True,
        large_integral_age_s=9007199254740993, equivalent_time_encoding_age_equal=True,
        fractional_age_s=.25, age_overflow_refused=True,
        original_fixture_snapshots_unchanged=10, corrected_SVGs_reproduced=2,
        full_regression_rerun=False, physics_rerun=False, latest_full_regression='ROOT_INTEGRATION_REQUIRED',
        registered_research_trials=0, model_calls=0, training_calls=0, runtime_caches_required=0)


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
