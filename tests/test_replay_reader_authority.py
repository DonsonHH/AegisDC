"""Copy-only public reader/replay/CLI authority boundaries; no stored original edits."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from aegis_dc.replay import read_attempt, replay_attempt
from aegis_dc.replay import run_recorded
from aegis_dc.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'evidence/mainline/engineering/13-replay/capture-02/causal-baseline'


def replace_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding='utf-8', newline='\n')


def change_header(folder, mutation):
    record = json.loads((folder / 'attempt.json').read_text(encoding='utf-8'))
    if mutation == 'terminal_schema':
        record['schema'] = 'aegisdc-facility-attempt-v999'
    elif mutation == 'declaration_schema':
        path = folder / 'declaration.json'
        declaration = json.loads(path.read_text(encoding='utf-8'))
        declaration['schema'] = 'aegisdc-attempt-declaration-v999'
        replace_json(path, declaration)
        record['artifacts']['declaration.json'] = sha256(path.read_bytes()).hexdigest()
    elif mutation == 'terminal_status':
        record['status'] = 'UNRECOGNIZED_TERMINAL_STATE'
        path = folder / 'lifecycle.jsonl'
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        rows[-1]['state'] = record['status']
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8', newline='\n')
        record['artifacts']['lifecycle.jsonl'] = sha256(path.read_bytes()).hexdigest()
    replace_json(folder / 'attempt.json', record)


class ReplayReaderAuthorityTests(unittest.TestCase):
    def test_unsupported_terminal_or_declaration_versions_and_states_are_not_authority(self):
        before = {path.relative_to(ORIGINAL).as_posix(): sha256(path.read_bytes()).hexdigest()
                  for path in ORIGINAL.rglob('*') if path.is_file()}
        with tempfile.TemporaryDirectory() as temporary:
            for mutation in ('terminal_schema', 'declaration_schema', 'terminal_status'):
                with self.subTest(mutation=mutation):
                    folder = Path(temporary) / mutation
                    shutil.copytree(ORIGINAL, folder)
                    change_header(folder, mutation)
                    with self.assertRaisesRegex(ValueError, 'schema|version|status|state'):
                        read_attempt(folder)
        self.assertEqual(before, {path.relative_to(ORIGINAL).as_posix(): sha256(path.read_bytes()).hexdigest()
                                  for path in ORIGINAL.rglob('*') if path.is_file()})

    def test_setup_interruption_is_unknown_and_bad_lifecycle_is_a_retained_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            incomplete = base / 'declaration-only'
            incomplete.mkdir()
            (incomplete / 'declaration.json').write_bytes((ORIGINAL / 'declaration.json').read_bytes())
            state = read_attempt(incomplete)
            self.assertEqual(state['record']['status'], 'UNFINALIZED_RUNNING_OR_INTERRUPTED')
            self.assertIsNone(state['run'])
            malformed = base / 'bad-lifecycle'
            shutil.copytree(incomplete, malformed)
            (malformed / 'lifecycle.jsonl').write_bytes(b'42\n')
            with self.assertRaisesRegex(ValueError, 'lifecycle'):
                read_attempt(malformed)
            output = base / 'new-refusal'
            result = replay_attempt(malformed, output)
            self.assertEqual(result['status'], 'FAILED')
            self.assertIn('lifecycle', result['failure']['stage'])
            self.assertEqual((output / 'origin/lifecycle.jsonl').read_bytes(), b'42\n')
            self.assertEqual((malformed / 'lifecycle.jsonl').read_bytes(), b'42\n')
            self.assertIsNone(read_attempt(output)['run'])

    def test_supported_version_still_requires_typed_terminal_and_declaration_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index, mutation in enumerate(('identity', 'failure', 'cache_policy', 'tools_type')):
                with self.subTest(mutation=mutation):
                    folder = Path(temporary) / str(index)
                    shutil.copytree(ORIGINAL, folder)
                    record = json.loads((folder / 'attempt.json').read_text())
                    if mutation == 'identity':
                        record['attempt_id'] = 42
                    elif mutation == 'failure':
                        record['failure'] = {'stage': 'invented', 'type': 'invented', 'message': 'not a completed run'}
                    else:
                        path = folder / 'declaration.json'
                        declaration = json.loads(path.read_text())
                        declaration['runtime_caches' if mutation == 'cache_policy' else 'tools'] = ('EVIDENCE' if mutation == 'cache_policy' else 42)
                        replace_json(path, declaration)
                        record['artifacts']['declaration.json'] = sha256(path.read_bytes()).hexdigest()
                    replace_json(folder / 'attempt.json', record)
                    with self.assertRaises(ValueError):
                        read_attempt(folder)

    def test_actual_CLI_retains_refusals_and_bad_origin_bytes_without_overwriting(self):
        environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for mutation in ('terminal_schema', 'declaration_schema', 'terminal_status', 'bad_lifecycle', 'declaration_only'):
                with self.subTest(mutation=mutation):
                    origin, output = base / mutation, base / (mutation + '-refused')
                    shutil.copytree(ORIGINAL, origin)
                    if mutation in {'bad_lifecycle', 'declaration_only'}:
                        (origin / 'attempt.json').unlink()
                        if mutation == 'bad_lifecycle':
                            (origin / 'lifecycle.jsonl').write_bytes(b'42\n')
                        else:
                            (origin / 'lifecycle.jsonl').unlink()
                    else:
                        change_header(origin, mutation)
                    before = {path.relative_to(origin).as_posix(): path.read_bytes() for path in origin.rglob('*') if path.is_file()}
                    command = [sys.executable, '-Xutf8', '-m', 'aegis_dc', 'replay', '--attempt', str(origin), '--output', str(output)]
                    refusal = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
                    self.assertEqual(refusal.returncode, 1, refusal.stderr)
                    record = json.loads(refusal.stdout)
                    self.assertEqual(record['status'], 'FAILED')
                    self.assertTrue(record['failure']['stage'].startswith('replay_origin'))
                    self.assertIsNone(read_attempt(output)['run'])
                    for name in ('attempt.json', 'declaration.json', 'lifecycle.jsonl'):
                        if name in before:
                            self.assertEqual((output / 'origin' / name).read_bytes(), before[name])
                    preserved = (output / 'attempt.json').read_bytes()
                    overwrite = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
                    self.assertEqual(overwrite.returncode, 2, overwrite.stderr)
                    self.assertEqual((output / 'attempt.json').read_bytes(), preserved)
                    self.assertEqual(before, {path.relative_to(origin).as_posix(): path.read_bytes() for path in origin.rglob('*') if path.is_file()})

    def test_supported_v1_historical_origin_remains_readable_without_executing_it(self):
        result = read_attempt(ORIGINAL)
        self.assertEqual(result['record']['schema'], 'aegisdc-facility-attempt-v1')
        self.assertEqual(result['record']['status'], 'COMPLETED')
        self.assertEqual(result['run']['summary']['delivered_service_unit_s'], 2)

    def test_failed_request_can_retain_invalid_declared_duration_without_claiming_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'invalid-duration'
            frozen = dict(schema='aegisdc-facility-replay-inputs-v1', seed=None,
                          exogenous_events=[], action_commands=[], work_requests=[])
            result = run_recorded(load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json'),
                                  output, inputs=frozen, duration_s=-1)
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(read_attempt(output)['request']['duration_s'], -1)
            self.assertIsNone(read_attempt(output)['run'])


if __name__ == '__main__':
    unittest.main()
