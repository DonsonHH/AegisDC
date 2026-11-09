"""Arrived measurement confirms one private state event, independent of sample count."""
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class BusinessStateDiagnosticTests(unittest.TestCase):
    def test_actual_network_reading_confirms_one_event_with_fixed_opportunity(self):
        descriptor = json.loads((ROOT/'tests/fixtures/39c-network-state-diagnostic.json').read_bytes())
        fixture = json.loads((ROOT/descriptor['base_fixture']).read_bytes())
        dispatch = fixture['dispatch_program']
        dispatch['schema'] = 'aegisdc-policy-run-program-v4'
        dispatch['decision_times_s'] = [0, 1.75, 2]
        dispatch['diagnostic_profile'] = descriptor['public_profile']
        output = None
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR'])
            with (output/'frozen-call-input.json').open('x',encoding='utf-8',newline='\n') as stream:
                json.dump(dict(model=fixture['model'], dispatch_program=dispatch,
                    business_program=descriptor['business_program'], duration_s=2, step_s=.01,
                    boundary_events=[]), stream,ensure_ascii=False,indent=2,allow_nan=False)
                stream.write('\n')
        self.facility_calls = 1
        result = simulate_scenario(fixture['model'],duration_s=2,step_s=.01,
            dispatch_program=dispatch,business_program=descriptor['business_program'])
        self.returned_decisions = len(result['policy_public_decisions'])
        if output is not None:
            save_run(result,output/'actual-run')
            with (output/'business-result.json').open('x',encoding='utf-8',newline='\n') as stream:
                json.dump(result['business_evaluation'],stream,ensure_ascii=False,indent=2,allow_nan=False)
                stream.write('\n')
        decisions = result['policy_public_decisions']
        initial = decisions[0]['condition_assessment']['conditions'][0]
        self.assertEqual(initial['status'],'UNKNOWN')
        self.assertIn('a-it-desk-claim',initial['external_context_record_ids'])
        self.assertEqual(initial['supporting_record_ids'],[])
        measured = decisions[1]['condition_assessment']['conditions'][0]
        self.assertEqual(measured['status'],'ABNORMAL')
        self.assertEqual(measured['observed_at_s'],1.25)
        self.assertEqual(measured['available_at_s'],1.75)
        self.assertEqual(measured['supporting_record_ids'],['it-capacity-before'])
        self.assertEqual(decisions[2]['condition_assessment']['conditions'][0]['supporting_record_ids'],['it-capacity-before'])
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in decisions],
                         ['network-case/inspect-0','network-case/action-0',None])
        evaluation = result['business_evaluation']
        self.assertEqual(evaluation['visibility'],'PRIVATE_EVALUATOR_ONLY')
        event = evaluation['events'][0]
        self.assertEqual(event['initial_truth'],'FAULT')
        self.assertEqual(event['first_corroborated_fault_report_at_s'],1.75)
        self.assertEqual(event['timely_outcome'],'TIMELY_CONFIRMED')
        self.assertEqual(evaluation['counts']['events_total'],1)
        self.assertEqual(evaluation['counts']['eligible_fault_matured'],1)
        self.assertEqual(evaluation['counts']['timely_confirmed_fault'],1)
        self.assertEqual(evaluation['counts']['missed_fault_confirmation'],0)
        self.assertEqual(evaluation['rates']['missed_confirmation']['denominator'],1)
        self.assertEqual(evaluation['rates']['missed_confirmation']['value'],0)
        self.assertEqual(evaluation['rates']['false_positive_state_events']['denominator'],0)
        self.assertIsNone(evaluation['rates']['false_positive_state_events']['value'])
        self.assertEqual(self.returned_decisions,3)


if __name__=='__main__':unittest.main()
