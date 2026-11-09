"""Declared unknown reference time stays distinct from known private fault truth."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run,simulate_scenario

ROOT=Path(__file__).resolve().parents[1]


class DiagnosticOpportunityTests(unittest.TestCase):
    def test_unmodeled_reference_keeps_null_time_and_full_fault_event(self):
        data=json.loads((ROOT/'tests/fixtures/39c-unmodeled-opportunity-10.json').read_bytes())
        descriptor=json.loads((ROOT/data['descriptor']).read_bytes())
        fixture=json.loads((ROOT/descriptor['base_fixture']).read_bytes())
        dispatch=fixture['dispatch_program'];dispatch['schema']='aegisdc-policy-run-program-v4'
        dispatch['decision_times_s']=data['decision_times_s']
        dispatch['policy_program']['policy']=data['policy']
        dispatch['diagnostic_profile']=deepcopy(descriptor['public_profile'])
        business=deepcopy(descriptor['business_program']);business['schema']=data['schema'];business['id']=data['id']
        opportunity=business['events'][0]['opportunity']
        opportunity.update(status=data['reference_status'],earliest_report_at_s=data['earliest_report_at_s'],source_note=data['source_note'])
        output=Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        def save(name,value):
            if output is not None:
                with (output/name).open('x',encoding='utf-8',newline='\n') as stream:
                    json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
        save('frozen-call-input.json',dict(model=fixture['model'],dispatch_program=dispatch,business_program=business,
            duration_s=data['duration_s'],step_s=data['step_s'],boundary_events=[]))
        self.facility_calls=1
        result=simulate_scenario(fixture['model'],duration_s=data['duration_s'],step_s=data['step_s'],
            dispatch_program=dispatch,business_program=business)
        self.returned_decisions=len(result['policy_public_decisions'])
        if output is not None:save_run(result,output/'actual-run')
        evaluation=result['business_evaluation'];save('business-result.json',evaluation)
        self.assertEqual(evaluation['schema'],'aegisdc-business-diagnostic-result-v2')
        event=evaluation['events'][0]
        self.assertEqual(event['initial_truth'],'FAULT')
        self.assertEqual(event['initial_private_value'],.25)
        self.assertEqual(event['reference_opportunity']['status'],'UNMODELED')
        self.assertIsNone(event['reference_opportunity']['earliest_report_at_s'])
        self.assertEqual(evaluation['counts']['events_total'],1)
        self.assertEqual(evaluation['counts']['truth_fault'],1)
        self.assertEqual(evaluation['counts']['reference_unmodeled'],1)
        self.assertEqual(evaluation['counts']['eligible_fault_matured'],0)
        self.assertEqual(evaluation['counts']['missed_fault_confirmation'],0)
        self.assertEqual(evaluation['rates']['missed_confirmation']['denominator'],0)
        self.assertIsNone(evaluation['rates']['missed_confirmation']['value'])
        self.assertEqual(evaluation['rates']['missed_confirmation']['unavailable_reason'],'NO_MATURE_ELIGIBLE_INITIAL_FAULT_EVENTS')
        self.assertEqual(evaluation['reference'],descriptor['business_program']['reference'])
        self.assertEqual(result['work_records'],[])
        for decision in result['policy_public_decisions']:
            assessment=decision['condition_assessment']
            self.assertEqual(assessment['conditions'][0]['status'],'UNKNOWN')
            self.assertFalse(assessment['private_truth_used'])
            self.assertNotIn(data['id'],json.dumps(decision['frame']))
            self.assertNotIn(evaluation['reference']['id'],json.dumps(decision['frame']))
        self.assertEqual(self.returned_decisions,3)


if __name__=='__main__':unittest.main()
