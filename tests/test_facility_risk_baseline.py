"""One public baseline entry keeps eight domains, unknowns and time scopes explicit."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class FacilityRiskBaselineTests(unittest.TestCase):
    def test_eight_domain_catalogue_separates_risk_value_unknowns_and_time_alignment(self):
        command=[sys.executable,'-m','aegis_dc','risk-baseline']
        run=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(run.stdout)
        self.assertEqual(result['schema'],'aegisdc-facility-risk-inspection-baseline-v1')
        self.assertEqual(len(result['domains']),8)
        self.assertEqual(result['coverage']['risk_modelled_primary_domains'],2)
        self.assertEqual(result['coverage']['risk_unmodelled_primary_domains'],6)
        self.assertEqual(result['coverage']['inspection_value_modelled_primary_domains'],1)
        self.assertEqual(result['coverage']['inspection_value_unmodelled_primary_domains'],7)
        self.assertEqual(result['known_subset_portfolio']['aggregation'],'JOINT_OUTCOME_AND_WINDOW_UNION')
        self.assertIsNone(result['whole_facility_expected_risk'])
        for row in result['domains']:
            if row['risk_status']=='UNMODELED':self.assertIsNone(row['conditional_risk'])
            if row['inspection_value_status']=='UNMODELED':self.assertIsNone(row['inspection_value'])
            self.assertTrue(row['asset_ids'])
            self.assertTrue(row['inspection_question'])
            self.assertTrue(row['evidence_triggers'])
        self.assertEqual(result['time_foundation']['status'],'UNRESOLVED_ALIGNMENT')
        self.assertEqual(result['time_foundation']['risk_horizon_s'],2)
        self.assertEqual(result['time_foundation']['default_work_s'],30)
        self.assertEqual(result['time_foundation']['default_walk_s'],[60,120])
        self.assertAlmostEqual(result['time_foundation']['value_inspection_s'],0.625)
        self.assertFalse(result['execution_permission'])
        self.assertEqual(result['physical_actions'],[])
        self.assertFalse(result['field_calibrated'])
        baseline=json.loads((ROOT/'configs/facility-risk-baseline-v1.json').read_bytes())
        with tempfile.TemporaryDirectory() as folder:
            invalid=deepcopy(baseline);invalid['domains'][2]['probability']=0
            path=Path(folder)/'invalid.json';path.write_text(json.dumps(invalid),encoding='utf-8')
            rejected=subprocess.run(command+['--manifest',str(path)],cwd=ROOT,text=True,capture_output=True)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn('closed domain baseline',rejected.stderr)
