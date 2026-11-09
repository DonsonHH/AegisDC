"""Known earliest reference report is after cutoff, with real work and no early reading."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run,simulate_scenario

ROOT=Path(__file__).resolve().parents[1]


class DiagnosticTooLateTests(unittest.TestCase):
    def test_known_minimum_report_after_cutoff_is_not_an_eligible_window(self):
        data=json.loads((ROOT/'tests/fixtures/39c-too-late-opportunity-12.json').read_bytes())
        descriptor=json.loads((ROOT/data['descriptor']).read_bytes())
        fixture=json.loads((ROOT/descriptor['base_fixture']).read_bytes())
        dispatch=fixture['dispatch_program'];dispatch['schema']='aegisdc-policy-run-program-v4'
        dispatch['decision_times_s']=[0,1.75,2];dispatch['diagnostic_profile']=deepcopy(descriptor['public_profile'])
        inspection=dispatch['inspection_program']['profile']
        next(row for row in inspection['bindings'] if row['task_id']=='network-case/inspect-0')['arrival_latency_s']=1.25
        dispatch['policy_program']['inspection_declaration']=deepcopy(inspection)
        business=deepcopy(descriptor['business_program']);business['schema']='aegisdc-business-diagnostic-evaluation-v2'
        business['id']=data['id'];business['reference'].update(id=data['reference_id'],
            inspection_profile_sha256=data['inspection_profile_sha256'],source_note=data['reference_note'])
        business['events'][0]['opportunity'].update(reference_id=data['reference_id'],status='TOO_LATE',
            earliest_report_at_s=2.5,source_note=data['reference_note'])
        output=Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        def save(name,value):
            if output is not None:
                with (output/name).open('x',encoding='utf-8',newline='\n') as stream:
                    json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
        save('frozen-call-input.json',dict(model=fixture['model'],dispatch_program=dispatch,business_program=business,
            duration_s=2,step_s=.01,boundary_events=[]))
        self.facility_calls=1
        result=simulate_scenario(fixture['model'],duration_s=2,step_s=.01,dispatch_program=dispatch,business_program=business)
        self.returned_decisions=len(result['policy_public_decisions'])
        if output is not None:save_run(result,output/'actual-run')
        evaluation=result['business_evaluation'];save('business-result.json',evaluation)
        save('actual-execution-summary.json',dict(code_identity=result['code_identity'],summary=result['summary'],
            work_records=result['work_records'],resource_ledger=result['policy_public_resource_ledger'],
            decisions=[dict(at_s=row['frame']['as_of_s'],choice=row['choice']['chosen_candidate_id'],
                work_feedback=row['history']['work_feedback']) for row in result['policy_public_decisions']]))
        event=evaluation['events'][0]
        self.assertEqual(event['initial_truth'],'FAULT')
        self.assertEqual(event['reference_opportunity']['status'],'TOO_LATE')
        self.assertEqual(event['reference_opportunity']['earliest_report_at_s'],2.5)
        self.assertFalse(event['deadline_right_censored'])
        self.assertIsNone(event['first_corroborated_fault_report_at_s'])
        self.assertEqual(evaluation['counts']['events_total'],1)
        self.assertEqual(evaluation['counts']['reference_too_late'],1)
        self.assertEqual(evaluation['counts']['reference_unavailable'],0)
        self.assertEqual(evaluation['counts']['eligible_fault_matured'],0)
        self.assertIsNone(evaluation['rates']['missed_confirmation']['value'])
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in result['policy_public_decisions']],
            ['network-case/inspect-0',None,None])
        self.assertEqual(len(result['work_records']),1)
        self.assertEqual(result['work_records'][0]['status'],'completed')
        self.assertEqual(result['work_records'][0]['completed_at_s'],1.25)
        acknowledgement=next(row for row in result['policy_public_decisions'][1]['history']['work_feedback'] if row['status']=='completed')
        self.assertEqual((acknowledgement['observed_at_s'],acknowledgement['arrived_at_s']),(1.25,1.75))
        self.assertAlmostEqual(result['summary']['worker_work_person_s'],1,places=12)
        self.assertEqual(result['inspection_public_snapshot']['records'],[])
        self.assertEqual(result['intervention_public_feedback'],[])
        self.assertTrue(all(row['condition_assessment']['conditions'][0]['status']=='UNKNOWN' for row in result['policy_public_decisions']))
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'],1.5,places=12)
        self.assertEqual(self.returned_decisions,3)


if __name__=='__main__':unittest.main()
