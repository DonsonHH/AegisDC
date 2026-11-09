"""Saved verifier CLI must reject optimization before it can bypass integrity guards."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class SavedDiagnosticVerificationTests(unittest.TestCase):
    def test_optimized_verification_is_rejected_and_normal_mode_is_recorded(self):
        manifest=ROOT/'manifest.json'
        # This dedicated tool fixture is run only by its declared Slurm protocol.
        # Root regression below uses a private temporary literal, never old raw data.
        if os.environ.get('AEGIS_SAVED_DIAGNOSTIC_MODE_PROTOCOL')!='39c-mode-07':
            with tempfile.TemporaryDirectory() as tmp:
                output=Path(tmp)/'must-not-be-created'
                child=subprocess.run([sys.executable,'-O','-B',str(ROOT/'scripts/check_saved_diagnostic_qualification.py'),
                    '--manifest',str(Path(tmp)/'absent.json'),'--output',str(output)],capture_output=True,text=True)
                self.assertNotEqual(child.returncode,0)
                self.assertIn('Optimized verification is forbidden',child.stderr)
                self.assertFalse(output.exists())
            return
        self.assertTrue(os.environ.get('SLURM_JOB_ID'),'Saved original checks require the remote Slurm fixture')
        output=Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR'])
        env=dict(os.environ);env.pop('PYTHONOPTIMIZE',None)
        def child_call(optimized,folder):
            command=[sys.executable]+(['-O'] if optimized else [])+['-B','-X','utf8',
                str(ROOT/'scripts/check_saved_diagnostic_qualification.py'),'--manifest',str(manifest),
                '--output',str(output/folder)]
            child=subprocess.run(command,env=env,capture_output=True)
            for suffix,data in [('stdout.log',child.stdout),('stderr.log',child.stderr)]:
                with (output/(folder+'-'+suffix)).open('xb') as stream:stream.write(data)
            return child
        rejected=child_call(True,'optimized-child')
        self.assertNotEqual(rejected.returncode,0)
        self.assertIn(b'Optimized verification is forbidden',rejected.stderr)
        self.assertFalse((output/'optimized-child').exists())
        normal=child_call(False,'normal-child')
        self.assertEqual(normal.returncode,0,normal.stderr.decode('utf-8','replace'))
        terminal=json.loads((output/'normal-child/terminal.json').read_bytes())
        attempt=json.loads((output/'normal-child/attempt.json').read_bytes())
        self.assertEqual(terminal['status'],'SAVED_ORIGINALS_AND_CORRECTED_LITERAL_PASSED')
        self.assertEqual(terminal['interpreter_optimize'],0)
        self.assertEqual(attempt['interpreter_optimize'],0)
        self.assertEqual(terminal['new_facility_calls'],0)


if __name__=='__main__':unittest.main()
