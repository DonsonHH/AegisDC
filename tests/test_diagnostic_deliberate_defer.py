"""A legal method DEFER causes real late evidence without removing its reference chance."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run,simulate_scenario

ROOT=Path(__file__).resolve().parents[1]


class DiagnosticDeliberateDeferTests(unittest.TestCase):
    def test_legal_defer_then_real_late_confirmation_keeps_the_reference_denominator(self):
        data=json.loads((ROOT/'tests/fixtures/39c-deliberate-defer-13.json').read_bytes())
        descriptor=json.loads((ROOT/data['descriptor']).read_bytes())
        fixture=json.loads((ROOT/descriptor['base_fixture']).read_bytes())
        dispatch=fixture['dispatch_program'];dispatch['schema']='aegisdc-policy-run-program-v4'
        dispatch['decision_times_s']=data['decision_times_s'];dispatch['diagnostic_profile']=deepcopy(descriptor['public_profile'])
        dispatch['policy_program']['policy']=data['policy']
        business=deepcopy(descriptor['business_program']);business['schema']='aegisdc-business-diagnostic-evaluation-v2'
        business['id']=data['id']
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
        decisions=result['policy_public_decisions']
        save('actual-execution-summary.json',dict(code_identity=result['code_identity'],summary=result['summary'],
            work_records=result['work_records'],resource_ledger=result['policy_public_resource_ledger'],
            decisions=[dict(at_s=row['frame']['as_of_s'],choice=row['choice']['chosen_candidate_id'],
                condition_assessment=row['condition_assessment'],policy=row['choice']['policy'],
                selector_policy=row['choice']['stage_selector_policy']) for row in decisions]))
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in decisions],
            [None,'network-case/inspect-0',None,None,'network-case/action-0',None])
        self.assertEqual([row['choice']['stage_selector_policy'] for row in decisions],['no_human']+['fifo']*5)
        self.assertTrue(all(row['choice']['policy']=='defer_once' for row in decisions))
        self.assertEqual([row['condition_assessment']['conditions'][0]['status'] for row in decisions],
            ['UNKNOWN']*4+['ABNORMAL']*2)
        tasks={row['id']:row for row in result['work_records']}
        self.assertEqual(tasks['network-case/inspect-0']['completed_at_s'],1.75)
        self.assertEqual(tasks['network-case/action-0']['status'],'working')
        self.assertEqual(result['intervention_public_feedback'],[])
        self.assertEqual(evaluation['reference'],descriptor['business_program']['reference'])
        event=evaluation['events'][0]
        self.assertEqual(event['reference_opportunity']['status'],'ELIGIBLE')
        self.assertEqual(event['reference_opportunity']['earliest_report_at_s'],1.75)
        self.assertEqual(event['first_corroborated_fault_report_at_s'],2.25)
        self.assertEqual(event['timely_outcome'],'LATE_CONFIRMATION')
        self.assertFalse(event['deadline_right_censored'])
        self.assertEqual(evaluation['counts']['events_total'],1)
        self.assertEqual(evaluation['counts']['eligible_fault_matured'],1)
        self.assertEqual(evaluation['counts']['timely_confirmed_fault'],0)
        self.assertEqual(evaluation['counts']['missed_fault_confirmation'],1)
        self.assertEqual(evaluation['counts']['reference_too_late'],0)
        self.assertEqual(evaluation['rates']['missed_confirmation']['value'],1)
        self.assertEqual(event['assessments'][-1]['observed_at_s'],1.75)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'],1.875,places=12)
        self.assertEqual(self.returned_decisions,6)


if __name__=='__main__':unittest.main()
