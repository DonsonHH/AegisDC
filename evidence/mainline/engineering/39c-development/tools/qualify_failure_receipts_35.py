"""Qualify runner failure receipts with synthetic reported counters, never plant calls."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import socket
import sys
import traceback
import unittest
from unittest.mock import patch
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    root = Path('/root/private_data/aegisdc-mainline-39c').resolve()
    if (socket.gethostname() != manifest['hostname'] or os.geteuid() != 0
            or platform.python_version() != '3.12.7' or os.environ.get('SLURM_JOB_ID')
            or not Path('/root/private_data').is_mount()
            or args.output.resolve() != Path(manifest['output_root']).resolve()
            or not args.output.resolve().is_relative_to(root)):
        raise SystemExit('Frozen infrastructure qualification host/root differs')
    args.output.mkdir(mode=0o700, exist_ok=False)
    save(args.output/'attempt.json', dict(source=manifest['source_commit'],
        manifest_sha256=sha(manifest_bytes), hostname=socket.gethostname(),
        started_utc=datetime.now(timezone.utc).isoformat(),
        classification='SYNTHETIC_RUNNER_COUNTER_FIXTURE_NOT_RESEARCH_OR_FACILITY_EXECUTION',
        maximum_runner_invocations=3))
    terminal = dict(status='FAILED', source=manifest['source_commit'],
                    real_public_choice_calls=0, real_facility_calls=0, new_research_trials=0)
    rows = []
    try:
        if sha(args.snapshot.read_bytes()) != manifest['snapshot_sha256']:
            raise ValueError('Qualification archive hash differs')
        with zipfile.ZipFile(args.snapshot) as archive:
            if sorted(archive.namelist()) != sorted(manifest['files']):
                raise ValueError('Qualification source paths differ')
            sources = {name: archive.read(name) for name in archive.namelist()}
        for name, record in manifest['files'].items():
            if sha(sources[name]) != record['sha256'] or len(sources[name]) != record['bytes']:
                raise ValueError('Qualification source differs: ' + name)
        runner_path = args.output/'frozen-runner35.py'
        runner_path.write_bytes(sources[manifest['tested_runner']])
        spec = importlib.util.spec_from_file_location('frozen_runner35', runner_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def invoke(case, body, expected, corrupt_snapshot=False):
            control = args.output/case
            control.mkdir(mode=0o700)
            snapshot = control/'source.zip'
            source = ('import unittest\nclass CounterFixture(unittest.TestCase):\n'
                      ' def test_receipt(self):\n' + body).encode()
            relative = 'tests/counter_fixture.py'
            with zipfile.ZipFile(snapshot, 'x') as archive:
                archive.writestr(relative, source)
            output = control/'output'
            inner = dict(attempt=case, phase='green', tests=1, direct_public_choice_calls=1,
                attempt_root=str(output), execution_source=manifest['source_commit'],
                control_source=manifest['source_commit'], watchdog_s=30,
                expected_host=dict(hostname=manifest['hostname'], python='3.12.7',
                    persistent_mount='/root/private_data', project_root=str(root)),
                snapshot_sha256='0'*64 if corrupt_snapshot else sha(snapshot.read_bytes()),
                snapshot_bytes=snapshot.stat().st_size,
                files={relative: dict(bytes=len(source), sha256=sha(source))},
                test=relative, test_names=['counter_fixture.CounterFixture.test_receipt'])
            save(control/'manifest.json', inner)
            prior_path = list(sys.path)
            try:
                with patch.object(sys, 'argv', [str(runner_path), '--manifest', str(control/'manifest.json'),
                            '--snapshot', str(snapshot), '--output', str(output)]):
                    with unittest.TestCase().assertRaises(ValueError):
                        module.main()
            finally:
                sys.path[:] = prior_path
                sys.modules.pop('counter_fixture', None)
            receipt = json.loads((output/'terminal.json').read_bytes())
            for key, value in expected.items():
                if receipt.get(key) != value:
                    raise AssertionError(f'{case}: {key}: {receipt.get(key)!r} != {value!r}')
            if 'numpy' in sys.modules or 'aegis_dc' in sys.modules:
                raise AssertionError('Infrastructure fixture imported a prohibited runtime')
            rows.append(dict(case=case, passed=True, expected=expected,
                actual={key: receipt[key] for key in expected},
                nested_terminal=str((output/'terminal.json').relative_to(args.output)),
                nested_terminal_sha256=sha((output/'terminal.json').read_bytes()),
                reported_values_are_synthetic=True, real_facility_calls=0))

        class ReceiptQualification(unittest.TestCase):
            def test_known_budget_violation(self):
                invoke('known-budget-violation',
                    '  self.public_choice_calls=2\n  self.facility_calls=3\n  self.returned_decisions=5\n',
                    dict(status='FAILED', tests_run=1, direct_public_choice_calls=2,
                         new_facility_entries=3, returned_native_decisions=5,
                         counter_observation='RESULT_AVAILABLE'))

            def test_known_test_failure(self):
                invoke('known-test-failure', '  self.public_choice_calls=1\n  self.fail("synthetic red")\n',
                    dict(status='FAILED', tests_run=1, failures=1, errors=0,
                         direct_public_choice_calls=1, new_facility_entries=0,
                         returned_native_decisions=0, counter_observation='RESULT_AVAILABLE'))

            def test_unknown_before_result(self):
                invoke('unknown-before-result', '  pass\n',
                    dict(status='FAILED', tests_run=None, direct_public_choice_calls=None,
                         new_facility_entries=None, returned_native_decisions=None,
                         counter_observation='RESULT_UNAVAILABLE'), corrupt_snapshot=True)

        with (args.output/'test.log').open('x', encoding='utf-8') as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ReceiptQualification))
        save(args.output/'qualification.json', rows)
        terminal.update(tests_run=result.testsRun, failures=len(result.failures),
                        errors=len(result.errors), skips=len(result.skipped),
                        nested_runner_invocations=len(rows))
        if (not result.wasSuccessful() or result.testsRun != 3 or result.skipped or len(rows) != 3):
            raise ValueError('Failure receipt qualification differs from its three frozen outcomes')
        if sha(args.manifest.read_bytes()) != sha(manifest_bytes) or sha(args.snapshot.read_bytes()) != manifest['snapshot_sha256']:
            raise ValueError('Qualification frozen inputs changed')
        terminal['status'] = 'FAILURE_RECEIPT_QUALIFICATION_PASSED'
    except BaseException as error:
        terminal.update(error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal.update(finished_utc=datetime.now(timezone.utc).isoformat(),
            output_files={path.relative_to(args.output).as_posix():dict(bytes=path.stat().st_size,
                sha256=sha(path.read_bytes())) for path in args.output.rglob('*') if path.is_file()})
        save(args.output/'terminal.json', terminal)
    print(json.dumps({key: terminal[key] for key in ('status', 'tests_run', 'failures', 'errors', 'real_facility_calls')}))


if __name__ == '__main__':
    main()
