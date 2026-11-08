"""Public preparation seam for the preregistered planner-only masks."""
import json,subprocess,sys,unittest
from pathlib import Path
from historical_research_checkout import historical_checkout
ROOT=Path(__file__).resolve().parents[1]

class AblationMasksTests(unittest.TestCase):
    def test_public_masks_keep_real_plant_and_team_capability(self):
        with historical_checkout() as historical:
            result=subprocess.run([sys.executable,'-B','-X','utf8','scripts/prepare_ablation.py','audit-masks'],
                cwd=historical,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        facts=json.loads(result.stdout)
        self.assertEqual(facts['status'],'PASS_PUBLIC_MASKS')
        self.assertEqual(facts['public_worlds'],8)
        self.assertEqual(facts['checked_arm_views'],32)
        self.assertEqual(facts['nonce_reads'],0)
        self.assertEqual(facts['physical_calls'],0)
        self.assertTrue(facts['actual_plant_preserved'])
        self.assertTrue(facts['actual_executor_preserved'])
        team=facts['joint_fixture']
        self.assertEqual(team['actual_catalog_tasks'],2)
        self.assertEqual(team['planner_candidates'],1)
        self.assertEqual(team['actual_intervention_bindings'],1)
        self.assertEqual(team['planner_intervention_bindings'],0)
        self.assertTrue(team['unmodeled_question_retained'])
        self.assertEqual(team['chosen_kind'],'inspect')
