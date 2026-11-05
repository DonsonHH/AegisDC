"""Risk scenarios are evaluated only from validated public frames and declared models."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def read(name):
    return json.loads((ROOT / name).read_bytes())

def inputs():
    frame = read('evidence/mainline/engineering/18-beliefs/capture-01/cli-frame.json')
    belief = read('configs/full-facility-belief-model-v1.json')
    risk = read('configs/full-facility-risk-scenarios-v1.json')
    return frame, belief, risk

class TestRiskScenarios(unittest.TestCase):
    def test_open_question_has_window_evidence_gaps_and_separate_joint_service_risk(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame, belief, model = inputs()
        before = deepcopy((frame, belief, model))
        result = assess_risks(frame, belief, model)
        self.assertEqual(result['facility_id'], frame['facility_id'])
        self.assertEqual(len(result['domain_ids']), 8)
        self.assertEqual(result['physical_actions'], [])
        self.assertFalse(result['execution_permission'])
        question = result['questions'][0]
        self.assertEqual(question['window_s'], [12, 14])
        self.assertEqual(question['status'], 'OPEN')
        self.assertTrue(question['evidence_gaps'])
        self.assertEqual(question['consequences']['service_deficit_time_s']['unit'], 's')
        self.assertEqual(result['portfolio']['aggregation'], 'JOINT_OUTCOME_AND_WINDOW_UNION')
        self.assertEqual((frame, belief, model), before)

    def test_joint_portfolio_uses_union_of_question_windows_and_not_question_sum(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame, belief, model = inputs()
        result = assess_risks(frame, belief, model)
        self.assertAlmostEqual(result['portfolio']['consequences']['unserved_service_unit_s']['value'], 3097/2060)
        self.assertAlmostEqual(result['portfolio']['consequences']['service_deficit_time_s']['value'], 15877/16480)
        question_sum = sum(q['consequences']['service_deficit_time_s']['value'] for q in result['questions']
                           if q['quantification']=='FINITE_CONDITIONAL_LAW')
        self.assertGreater(question_sum, result['portfolio']['consequences']['service_deficit_time_s']['value'])
        model['questions'] = [dict(deepcopy(model['questions'][0]),window_s=[.5,1.5]),
                              dict(deepcopy(model['questions'][0]),id='same-question-other-window',window_s=[1,2])]
        model['questions'][0]['consequence_bounds']['service_deficit_time_s']['interval']=[0,1]
        model['questions'][0]['consequence_bounds']['unserved_service_unit_s']['interval']=[0,1.25]
        model['questions'][1]['consequence_bounds']=deepcopy(model['questions'][1]['consequence_bounds'])
        model['questions'][1]['consequence_bounds']['service_deficit_time_s']['interval']=[0,1]
        model['questions'][1]['consequence_bounds']['unserved_service_unit_s']['interval']=[0,2]
        result = assess_risks(frame, belief, model)
        self.assertEqual(result['portfolio']['outcome_windows_s']['other'], [[.5,2]])
        self.assertEqual(result['portfolio']['outcome_windows_s']['cooling-limited'], [[.5,2]])
        self.assertNotIn('power-limited',result['portfolio']['outcome_windows_s'])
        model['questions'] = []
        result = assess_risks(frame, belief, model)
        self.assertEqual(result['portfolio']['consequences']['service_deficit_time_s']['value'], 0)

    def test_unmodeled_domain_questions_remain_unknown_and_do_not_become_zero_risk(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame, belief, model = inputs()
        result = assess_risks(frame, belief, model)
        unsupported = [row for row in result['questions'] if row['quantification'] == 'UNMODELED']
        self.assertGreaterEqual(len(unsupported), 6)
        self.assertTrue(all(row['probability']['value'] is None for row in unsupported))
        self.assertTrue(all(row['consequences']['service_deficit_time_s']['value'] is None for row in unsupported))
        self.assertEqual(result['portfolio']['completeness'], 'PARTIAL_WITH_UNMODELED_QUESTIONS')
        self.assertTrue(result['portfolio']['unmodeled_question_ids'])
        self.assertEqual(set(result['covered_domain_ids']), set(result['domain_ids']))

    def test_closed_catalog_rejects_private_fields_bad_bindings_and_broken_trajectories(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame, belief, model = inputs()
        for change in ('private_state','bad_facility','bad_probability','trajectory_gap','bad_dependency','bad_unit'):
            changed = deepcopy(model)
            if change == 'private_state': changed['actual_fault'] = 'filter'
            elif change == 'bad_facility': changed['facility_id'] = 'another-facility'
            elif change == 'bad_probability': changed['outcomes'][0]['conditional_probability']['nominal'] = .5
            elif change == 'trajectory_gap': changed['outcomes'][0]['capacity_profile'][0]['end_s'] = .9
            elif change == 'bad_dependency': changed['questions'][0]['dependency_edge_ids'] = ['no-such-edge']
            else: changed['time_unit'] = 'hour'
            with self.subTest(change=change), self.assertRaises(ValueError):
                assess_risks(frame,belief,changed)

    def test_direct_intervention_and_defer_remain_options_without_forcing_inspection(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame, belief, model = inputs()
        result = assess_risks(frame,belief,model)
        options = {row['id']:row for row in result['questions'][0]['option_assessments']}
        self.assertTrue(options['defer-cooling']['legal_for_planning'])
        self.assertTrue(options['isolate-cooling']['legal_for_planning'])
        self.assertEqual(options['isolate-cooling']['requires_prior_inspection'],False)
        self.assertFalse(options['isolate-cooling']['execution_permission'])
        self.assertIn('execution_authorization',options['isolate-cooling']['unresolved_dynamic_requirements'])
        self.assertFalse(options['unqualified-cooling']['legal_for_planning'])
        self.assertIn('nominal_qualification_mismatch',options['unqualified-cooling']['public_reasons'])
        self.assertEqual(result['physical_actions'],[])
        self.assertEqual(options['isolate-cooling']['capability_interface_id'],'inspect_facility_cooling')
        changed = deepcopy(model)
        changed['questions'][0]['options'][1]['qualification_id'] = 'qualified_it_inspection'
        with self.assertRaises(ValueError):
            assess_risks(frame,belief,changed)

    def test_reference_model_conflict_is_unresolved_not_zero_risk(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame, belief, model = inputs()
        for variant in belief['variants']:
            variant['positive_likelihood']['fixed-hot'] = [0,0,0,0]
        result = assess_risks(frame,belief,model)
        self.assertEqual(result['status'],'MODEL_CONFLICT')
        self.assertIsNone(result['portfolio']['consequences']['service_deficit_time_s']['value'])
        self.assertIsNone(result['questions'][0]['probability']['value'])
        self.assertIsNone(result['portfolio']['assumption_envelope'])

    def test_domain_impact_routes_and_conservative_bounds_are_not_empty_labels(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame, belief, model = inputs()
        result = assess_risks(frame,belief,model)
        questions = {row['id']:row for row in result['questions']}
        self.assertIn('f_ups_internal_pump',questions['backup-support']['dependency_edge_ids'])
        self.assertIn('f_common_distribution',questions['backup-support']['dependency_edge_ids'])
        self.assertEqual(questions['access-and-leak']['immediate_service_effect'],'INDIRECT_VIA_ACTION_FEASIBILITY')
        self.assertEqual(questions['control-uncertainty']['immediate_service_effect'],'ALTERNATIVE_PHYSICAL_AND_INFORMATION_EFFECTS')
        self.assertEqual(questions['people-and-tools']['immediate_service_effect'],'INDIRECT_VIA_ACTION_FEASIBILITY')
        self.assertEqual(questions['backup-support']['consequence_bounds']['service_deficit_time_s']['interval'],[0,2])
        self.assertAlmostEqual(result['full_horizon_service']['offered_service_unit_s']['value'],2.5)
        self.assertAlmostEqual(result['full_horizon_service']['delivered_service_unit_s']['value'],2053/2060)
        for question in result['questions']:
            self.assertTrue(question['impact_description'])
            self.assertTrue(question['conditional_consequence'])
            self.assertTrue(question['option_assessments'])
            self.assertEqual(question['secondary_consequence_dimensions'][0]['unit'],'s')
            self.assertIsNone(question['secondary_consequence_dimensions'][0]['interval'])
            self.assertEqual(question['consequences_basis'],'EVENT_WEIGHTED_CONTRIBUTION_NOT_CONDITIONAL_ON_EVENT')

    def test_variant_envelope_is_a_model_range_and_missing_variants_withhold_it(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame,belief,model = inputs()
        result = assess_risks(frame,belief,model)
        question = result['questions'][0]
        values = [row['service_deficit_time_s']['value'] for row in question['consequences_by_variant'].values()]
        self.assertEqual(question['assumption_envelope']['service_deficit_time_s'],[min(values),max(values)])
        self.assertEqual(result['envelope_basis'],'DECLARED_MODEL_VARIANT_RANGE_NOT_CONFIDENCE_INTERVAL')
        belief['variants'][1]['positive_likelihood']['fixed-hot'] = [0,0,0,0]
        result = assess_risks(frame,belief,model)
        self.assertEqual(result['status'],'PARTIAL_MODEL_CONFLICT')
        self.assertIsNone(result['questions'][0]['assumption_envelope'])
        self.assertIsNotNone(result['questions'][0]['consequences']['service_deficit_time_s']['value'])

    def test_risk_cli_matches_public_function_and_rejects_private_fields(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame,belief,model = inputs()
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory)/name for name in ('frame.json','belief.json','catalog.json')]
            for path,value in zip(paths,(frame,belief,model)):
                path.write_text(json.dumps(value),encoding='utf-8')
            command = [sys.executable,'-B','-X','utf8','-m','aegis_dc.risk_scenarios',
                       '--frame',str(paths[0]),'--belief-model',str(paths[1]),'--catalog',str(paths[2])]
            result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),assess_risks(frame,belief,model))
            model['actual_state'] = {'failed':'filter'}
            paths[2].write_text(json.dumps(model),encoding='utf-8')
            result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(result.stdout,'')

    def test_inspection_referral_cannot_target_an_unrelated_question_asset(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame,belief,model = inputs()
        inspection = next(row for row in model['questions'][0]['options'] if row['kind']=='inspect')
        inspection['request_id']='intent-it-check'
        with self.assertRaises(ValueError):
            assess_risks(frame,belief,model)

    def test_claimed_conditional_bounds_cannot_exclude_declared_joint_consequences(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame,belief,model = inputs()
        model['questions'][0]['consequence_bounds']['service_deficit_time_s']['interval']=[0,.1]
        with self.assertRaises(ValueError):
            assess_risks(frame,belief,model)

    def test_independent_joint_event_witness_deduplicates_shared_compound_outcome(self):
        from aegis_dc.risk_scenarios import assess_risks
        from aegis_dc.decision_view import DecisionGateway
        frame,belief,model = inputs()
        static=frame['evidence']['static_knowledge']
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],
            facility_id=frame['facility_id'],basis='synthetic_assumption',time_unit='s',**static,records=[])
        plan=dict(schema='aegisdc-public-preparation-plan-v1',id='joint-hand-witness',basis='synthetic_assumption',
                  time_unit='s',decision_times_s=[0],requests=frame['requests'])
        frame=DecisionGateway(frame['nominal_knowledge'],ledger,plan).next_frame()
        model['demand']=[dict(start_s=0,end_s=2,rate=1)]
        for outcome,capacity in zip(model['outcomes'],(2,.6,.5,.3125)):
            outcome['capacity_profile']=[dict(start_s=0,end_s=2,capacities={key:capacity for key in model['service_component_ids']})]
        model['questions']=model['questions'][:2]
        for q in model['questions']:q['consequence_bounds']['unserved_service_unit_s']['interval']=[0,2]
        result=assess_risks(frame,belief,model)
        self.assertAlmostEqual(result['questions'][0]['consequences']['service_deficit_time_s']['value'],119/400)
        self.assertAlmostEqual(result['questions'][1]['consequences']['service_deficit_time_s']['value'],19/80)
        self.assertAlmostEqual(result['portfolio']['consequences']['service_deficit_time_s']['value'],159/400)
        self.assertNotAlmostEqual(result['portfolio']['consequences']['service_deficit_time_s']['value'],107/200)

    def test_nonrepresentable_universal_bound_uses_minimal_outward_binary64(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame,belief,model = inputs()
        model['demand']=[dict(start_s=0,end_s=1,rate=.1),dict(start_s=1,end_s=2,rate=.2)]
        for question in model['questions']:
            question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,.30000000000000004]
        result=assess_risks(frame,belief,model)
        self.assertEqual(result['questions'][0]['consequence_bounds']['unserved_service_unit_s']['interval'],[0,.30000000000000004])
        for upper in (.3,.3000000000000001):
            changed=deepcopy(model)
            changed['questions'][0]['consequence_bounds']['unserved_service_unit_s']['interval']=[0,upper]
            with self.subTest(upper=upper), self.assertRaises(ValueError):
                assess_risks(frame,belief,changed)

    def test_large_finite_universal_work_bound_is_allowed_and_overflow_is_explicit(self):
        from aegis_dc.risk_scenarios import assess_risks
        frame,belief,model = inputs()
        model['demand']=[dict(start_s=0,end_s=2,rate=5e307)]
        for question in model['questions']:
            question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,1e308]
        result=assess_risks(frame,belief,model)
        self.assertEqual(result['full_horizon_service']['offered_service_unit_s']['value'],1e308)
        model['demand'][0]['rate']=1e308
        for question in model['questions']:
            question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,sys.float_info.max]
        with self.assertRaisesRegex(ValueError,'finite binary64 output range'):
            assess_risks(frame,belief,model)

if __name__ == '__main__':
    unittest.main()
