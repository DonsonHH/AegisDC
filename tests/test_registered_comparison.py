"""Public preregistration CLI refuses changes outside the primary policy field."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts/registered_comparison.py'
REFERENCE = ROOT / 'evidence/mainline/engineering/26-candidate/reference'


class RegisteredComparisonTests(unittest.TestCase):
    def test_historical_pair_reuses_the_entire_common_world(self):
        left = REFERENCE / 'online-baseline-inspect.json'
        right = REFERENCE / 'online-candidate-inspect.json'

        def audit(candidate):
            return subprocess.run(
                [sys.executable, '-B', '-X', 'utf8', str(CLI), 'audit-pair', str(left), str(candidate)],
                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=False,
            )

        result = audit(right)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['allowed_difference'], 'dispatch_program.policy_program.policy')
        self.assertEqual(receipt['shared_input_sha256'], '12ae64aa679a0d0fe08e160ff0cb0849b843884533f372907e50401463947f02')
        self.assertEqual(receipt['facility_calls'], 0)
        with TemporaryDirectory() as folder:
            edited = Path(folder) / 'edited.json'
            candidate = json.loads(right.read_bytes())
            candidate['dispatch_program']['decision_times_s'][0] += .125
            edited.write_text(json.dumps(candidate), encoding='utf-8')
            result = audit(edited)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Another pair input differs', result.stderr)
