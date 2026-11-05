"""Transparent choices through the evidence-only public decision-frame seam."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from aegis_dc.decision_view import DecisionGateway
ROOT=Path(__file__).resolve().parents[1]

def fixture(policy='fifo',time=0):
    inputs=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json').read_bytes())
    original=inputs['work_program']['submissions'][0];frame=original['frame']
    ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
        basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='policy25',basis='synthetic_assumption',time_unit='s',decision_times_s=[time],requests=[])
    frame=DecisionGateway(frame['nominal_knowledge'],ledger,plan).next_frame()
    first=deepcopy(original['task']);first['id']='work-first'
    second=deepcopy(first);second['id']='work-second'
    candidates=[dict(id='a-first',task=first,available_at_s=0,question_id='it-dependence',source_note='Declared finite synthetic inspection intention.'),
        dict(id='b-second',task=second,available_at_s=0,question_id='it-dependence',source_note='Second finite intention, not automatic Tour generation.')]
    program=dict(schema='aegisdc-dispatch-policy-program-v1',id='policy25-fixture',basis='synthetic_assumption',policy=policy,
        workforce_profile=inputs['work_program']['profile'],candidates=candidates)
    return frame,program,dict(issued=[],work_feedback=[])

class DispatchPolicyTests(unittest.TestCase):
    def test_expired_declared_intentions_are_audited_as_unavailable(self):
        from aegis_dc.dispatch_policy import choose_work
        frame,program,history=fixture(time=11)
        result=choose_work(frame,program,history)
        self.assertIsNone(result['chosen_candidate_id'])
        self.assertTrue(all('DECLARED_DEADLINE_PASSED' in c['reasons'] for c in result['candidates']))

    def test_no_human_defers_with_public_candidate_audit_and_no_implicit_tour(self):
        from aegis_dc.dispatch_policy import choose_work
        frame,program,history=fixture('no_human');original=deepcopy((frame,program,history))
        result=choose_work(frame,program,history)
        self.assertIsNone(result['chosen_candidate_id'])
        self.assertIsNone(result['work_intention'])
        self.assertEqual(result['reason'],'POLICY_NO_HUMAN')
        self.assertFalse(result['execution_permission'])
        self.assertFalse(result['generated_tour'])
        self.assertEqual([c['candidate_id'] for c in result['candidates']],['a-first','b-second'])
        self.assertEqual((frame,program,history),original)

    def test_fifo_waits_for_arrived_resource_release_before_reusing_crew(self):
        from aegis_dc.dispatch_policy import choose_work
        frame,program,history=fixture()
        first=choose_work(frame,program,history)
        self.assertEqual(first['chosen_candidate_id'],'a-first')
        history['issued'].append(dict(candidate_id='a-first',issued_at_s=0))
        frame,_,_=fixture(time=2)
        waiting=choose_work(frame,program,history)
        self.assertIsNone(waiting['chosen_candidate_id'])
        self.assertIn('PUBLIC_UNACKNOWLEDGED_RESOURCE_OCCUPATION',waiting['candidates'][1]['reasons'])
        history['work_feedback'].append(dict(task_id='work-first',source_id='workforce-execution-report',observed_at_s=1.25,
            arrived_at_s=1.75,status='completed',reason=None,location_id='loc_it',origin_id='workforce:work-first',
            coverage='THIS_ISSUED_TASK_ONLY',basis='SYNTHETIC_FINITE_TIMED_EXECUTION_CHANNEL'))
        ready=choose_work(frame,program,history)
        self.assertEqual(ready['chosen_candidate_id'],'b-second')
        history['work_feedback'][0]['arrived_at_s']=3
        with self.assertRaises(ValueError):choose_work(frame,program,history)

if __name__=='__main__':unittest.main()
