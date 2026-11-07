"""Check the registered development input boundary without physical execution."""

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
RUNNER=ROOT/'scripts/registered_development.py'


class RegisteredDevelopmentTests(unittest.TestCase):
    def test_plan_pins_development_only_and_rotates_arms_per_world(self):
        result=subprocess.run([sys.executable,'-B','-X','utf8',str(RUNNER),'plan'],cwd=ROOT,
            capture_output=True,encoding='utf-8',check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['status'],'PASS_DEVELOPMENT_PLAN_ONLY')
        self.assertEqual(data['phase'],'development')
        self.assertEqual(data['budget'],{'attempts':36,'simulated_charge_s':360,'scheduled_decisions':360})
        self.assertEqual(data['registered_research_trials'],0)
        self.assertEqual(data['held_inputs_read'],0)
        rows=data['slots']
        self.assertEqual(len(rows),36)
        self.assertEqual(len({(row['world_id'],row['arm']) for row in rows}),36)
        self.assertEqual([(rows[i]['world_id'],rows[i]['arm']) for i in range(0,36,6)],
            [('development-01','no_human'),('development-02','periodic'),
             ('development-03','fifo'),('development-04','risk_condition_priority_adapted'),
             ('development-05','one_observation_lookahead'),('development-06','evidence_consistent_contingent')])
        self.assertTrue(all(len(row['input_sha256'])==64 and row['duration_s']==10 for row in rows))
