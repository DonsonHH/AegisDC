from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aegis_dc.facility import load_model,candidate_service_exposure
from aegis_dc.risk import assess,recommend

ROOT=Path(__file__).resolve().parents[1]


class FacilityFoundationTests(unittest.TestCase):
    def setUp(self):
        self.model=load_model(ROOT/'configs/facility-structure-v0.1.json')
        self.case=json.loads((ROOT/'configs/risk-method-demo.json').read_text(encoding='utf-8'))
        self.question=deepcopy(self.case['questions'][0])

    def observation(self,**changes):
        return {'question_id':self.question['id'],'source':'fixed_sensor','finding':'positive',
                'observed_hour':0,'available_hour':0,'sensitivity':.9,'specificity':.95,
                'parameter_basis':'synthetic_assumption','parameter_source':'controlled test observation',**changes}

    def test_model_covers_facility_support_and_keeps_walking_separate(self):
        ids={row['id'] for row in self.model['assets']}
        self.assertTrue({'main_switchgear','rectifier_hvdc','battery','ups','chiller','cooling_tower','plate_hx','cdu','network','bms'}<=ids)
        self.assertIn('compute_service',candidate_service_exposure(self.model,'main_switchgear'))
        self.assertTrue(set(self.model['fixed_sensor_assets'])<ids)
        altered=deepcopy(self.model);altered['walking_links'][0]['to']='cdu'
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'invalid.json';file.write_text(json.dumps(altered),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Walking links use zones'):load_model(file)

    def test_fixed_sensor_inventory_is_optional_not_full_coverage(self):
        no_fixed=deepcopy(self.model);no_fixed.pop('fixed_sensor_assets')
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'no-fixed.json';file.write_text(json.dumps(no_fixed),encoding='utf-8')
            loaded=load_model(file)
            self.assertIn('compute_service',candidate_service_exposure(loaded,'main_switchgear'))
        self.assertAlmostEqual(assess(self.question)['net_inspection_value'],1195)

    def test_documented_example_works_without_fixed_measurements(self):
        result=assess(self.question)
        self.assertAlmostEqual(result['best_cost_without_inspection'],2000)
        self.assertAlmostEqual(result['expected_total_cost_with_inspection'],805)
        self.assertAlmostEqual(result['net_inspection_value'],1195)
        self.assertEqual(result['evidence_used'],[])

    def test_optional_fixed_measurement_updates_only_its_declared_question(self):
        result=assess(self.question,[self.observation()])
        self.assertAlmostEqual(result['posterior_defect_probability'],.6666666666666666)
        self.assertEqual(result['evidence_used'],['fixed_sensor'])

    def test_future_evidence_is_not_available_to_the_decision(self):
        result=assess(self.question,[self.observation(observed_hour=1,available_hour=2)],as_of_hour=0)
        self.assertAlmostEqual(result['posterior_defect_probability'],.1)
        self.assertEqual(result['evidence_ignored'][0]['reason'],'not_available')

    def test_inspection_does_not_reduce_loss_without_an_effective_action(self):
        self.question['mitigation_available']=False
        result=assess(self.question)
        self.assertAlmostEqual(result['expected_total_cost_with_inspection'],2200)
        self.assertAlmostEqual(result['net_inspection_value'],-200)

    def test_high_risk_can_call_for_direct_action_instead_of_another_inspection(self):
        high=assess(self.case['questions'][1])
        self.assertAlmostEqual(high['expected_loss_without_mitigation'],16000)
        self.assertEqual(high['best_action_without_inspection'],'mitigate')
        self.assertAlmostEqual(high['net_inspection_value'],-200)
        result=recommend(self.case['questions'])
        self.assertEqual(result['next_inspection'],'uncertain_power_path')
        self.assertIn('known_high_risk',result['direct_action_candidates'])
        self.assertFalse(result['automatic_equipment_actions'])

    def test_no_open_question_does_not_create_a_fixed_tour(self):
        result=recommend([])
        self.assertIsNone(result['next_inspection']);self.assertFalse(result['default_tour_created'])
        self.assertEqual(result['reason'],'no_open_questions')

    def test_budget_and_units_are_not_silently_ignored(self):
        result=recommend([self.question],time_budget_minutes=1)
        self.assertIsNone(result['next_inspection'])
        other=deepcopy(self.question);other.update(id='other',currency='USD')
        with self.assertRaisesRegex(ValueError,'one currency and horizon'):recommend([self.question,other])

    def test_unknown_probability_and_hidden_state_are_not_accepted_as_zero_risk(self):
        self.question['defect_probability']=None
        with self.assertRaisesRegex(ValueError,'unknown is not zero'):assess(self.question)
        self.question=deepcopy(self.case['questions'][0]);self.question['hidden_simulator_fault']=True
        with self.assertRaisesRegex(ValueError,'fields do not match'):assess(self.question)

    def test_duplicate_or_joint_observations_need_an_explicit_likelihood_model(self):
        with self.assertRaisesRegex(ValueError,'correlated/joint'):assess(self.question,[self.observation(),self.observation()])

    def test_public_demo_is_synthetic_and_has_no_automatic_actions(self):
        process=subprocess.run([sys.executable,'-m','aegis_dc','risk-demo'],cwd=ROOT,capture_output=True,text=True,check=True)
        result=json.loads(process.stdout)
        self.assertEqual(result['basis'],'synthetic_assumption')
        self.assertEqual(result['research_gain_claim'],'NOT_ESTABLISHED')
        self.assertFalse(result['requires_full_realtime_telemetry'])
        self.assertFalse(result['default_tour_created'])


if __name__=='__main__':unittest.main()
