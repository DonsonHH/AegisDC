"""Read-only CLI commands do not initialize the private facility executor."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AegisCLILoadingTests(unittest.TestCase):
    def test_status_keeps_private_executor_unloaded(self):
        script = """
import contextlib
import io
import json
import sys
from aegis_dc.__main__ import main
sys.argv = ['aegis-dc', 'status']
output = io.StringIO()
with contextlib.redirect_stdout(output):
    main()
print(json.dumps({'status': json.loads(output.getvalue()),
                  'private_modules': sorted(name for name in sys.modules
                      if name in {'aegis_dc.plant', 'aegis_dc.replay',
                                  'aegis_dc.policy_execution'})}))
"""
        completed = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                                   capture_output=True, text=True, check=True)
        result = json.loads(completed.stdout)
        self.assertEqual(result['private_modules'], [])
        self.assertIn('mainline_progress', result['status'])
        self.assertEqual(result['status']['field_calibration'], 'PENDING')
