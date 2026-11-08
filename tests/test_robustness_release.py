"""Pure public robustness design contracts; no unsealing or model execution."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/'scripts/robustness_release.py'

class RobustnessReleaseTests(unittest.TestCase):
    def call(self,*args):
        return subprocess.run([sys.executable,'-B','-X','utf8',str(CLI),*map(str,args)],cwd=ROOT,
            capture_output=True,text=True,encoding='utf-8')

    def test_public_description_keeps_actual_and_forecast_changes_distinct(self):
        result=self.call('describe-public')
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout);rows={r['id']:r for r in data['worlds']}
        self.assertEqual(data['contrast_blocks'],4)
        self.assertEqual([rows[f'robustness-{i:02}']['offered_demand'] for i in (1,2)],[.75,1.25])
        self.assertEqual([rows[f'robustness-{i:02}']['public_demand'] for i in (1,2)],[.75,1.25])
        self.assertEqual([rows[f'robustness-{i:02}']['rectifier_meter_enabled'] for i in (3,4)],[True,False])
        self.assertEqual([rows[f'robustness-{i:02}']['ups_in_service'] for i in (5,6)],[1,0])
        self.assertEqual([rows[f'robustness-{i:02}']['actual_fallback_capacity'] for i in (7,8)],[.75,.75])
        self.assertEqual([rows[f'robustness-{i:02}']['forecast_capacity'] for i in (7,8)],[.75,1])
        self.assertEqual(len({r['graphs_sha256'] for r in rows.values()}),1)
        self.assertEqual(data['physical_calls'],0);self.assertEqual(data['selector_calls'],0)
        self.assertEqual(data['nonce_reads'],0);self.assertEqual(data['admission_calls'],0)

    def test_contrast_refuses_an_undeclared_changed_field(self):
        with TemporaryDirectory() as directory:
            left=Path(directory)/'left.json';right=Path(directory)/'right.json'
            left.write_text(json.dumps({'arbitrary':0}),encoding='utf-8')
            right.write_text(json.dumps({'arbitrary':1}),encoding='utf-8')
            result=self.call('audit-contrast','--family','load-level','--left',left,'--right',right)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Load contrast exceeds its three declared quantities',result.stderr)

if __name__=='__main__':unittest.main()
