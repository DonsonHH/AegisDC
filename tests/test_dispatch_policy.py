"""Transparent choices through the evidence-only public decision-frame seam."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from aegis_dc.decision_view import DecisionGateway
from aegis_dc.plant import simulate_scenario
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
    def test_declared_inspection_cannot_silently_execute_an_intervention_binding(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json').read_bytes())
        frame,policy,_=fixture()
        policy.update(schema='aegisdc-dispatch-policy-program-v2',options={})
        for candidate in policy['candidates']:candidate['kind']='inspect'
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        actions=inputs['intervention_program'];binding=actions['bindings'][0];binding['task_id']='work-first'
        actions['bindings'].append(dict(binding,task_id='work-second',setting=.5))
        program=dict(schema='aegisdc-policy-run-program-v1',id='mismatched-operation-kind-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0],
            inspection_program=None,intervention_program=actions)
        with self.assertRaises(ValueError):simulate_scenario(inputs['model'],duration_s=.5,step_s=.01,dispatch_program=program)

    def test_periodic_inspection_runs_at_declared_due_time_in_the_same_facility(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/22-inspections/reference/input-v1.json').read_bytes())
        submitted=inputs['work_program']['submissions'][0];frame=submitted['frame']
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        policy=dict(schema='aegisdc-dispatch-policy-program-v2',id='periodic-policy25',basis='synthetic_assumption',policy='periodic',
            workforce_profile=inputs['work_program']['profile'],options=dict(schedule=[dict(candidate_id='due-inspection',due_at_s=1)]),
            candidates=[dict(id='due-inspection',kind='inspect',task=submitted['task'],available_at_s=0,question_id='cooling',
                source_note='Explicit periodic reference inspection, not a generated facility tour.')])
        program=dict(schema='aegisdc-policy-run-program-v1',id='online-periodic-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0,1,2,4],
            inspection_program=inputs['inspection_program'],intervention_program=None)
        result=simulate_scenario(inputs['model'],duration_s=4,step_s=.01,dispatch_program=program,boundary_events=inputs['boundary_events'])
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in result['policy_public_decisions']],[None,'due-inspection',None,None])
        self.assertEqual((result['work_records'][0]['issued_at_s'],result['work_records'][0]['completed_at_s']),(1,3.25))
        record=result['policy_public_decisions'][-1]['frame']['evidence']['records'][0]
        self.assertEqual((record['observed_at_s'],record['arrived_at_s'],record['value']),(3.25,3.75,0))

    def test_periodic_reference_uses_only_explicit_inspection_schedule(self):
        from aegis_dc.dispatch_policy import choose_work
        frame,program,history=fixture()
        program.update(schema='aegisdc-dispatch-policy-program-v2',policy='periodic',
            options=dict(schedule=[dict(candidate_id='b-second',due_at_s=1)]))
        for candidate in program['candidates']:candidate['kind']='inspect'
        before=choose_work(frame,program,history)
        self.assertIsNone(before['chosen_candidate_id'])
        self.assertIn('NOT_IN_DECLARED_PERIODIC_REFERENCE',before['candidates'][0]['reasons'])
        self.assertIn('PERIODIC_REFERENCE_NOT_DUE',before['candidates'][1]['reasons'])
        frame,_,_=fixture(time=1)
        due=choose_work(frame,program,history)
        self.assertEqual(due['chosen_candidate_id'],'b-second')
        self.assertEqual(due['reason'],'EXPLICIT_PERIODIC_INSPECTION_REFERENCE')
        self.assertFalse(due['generated_tour'])
        program['candidates'][1]['kind']='intervene'
        with self.assertRaises(ValueError):choose_work(frame,program,history)

    def test_real_onsite_measurement_enters_a_later_policy_frame_only_after_arrival(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/22-inspections/reference/input-v1.json').read_bytes())
        submitted=inputs['work_program']['submissions'][0];frame=submitted['frame']
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        policy=dict(schema='aegisdc-dispatch-policy-program-v1',id='onsite-policy25',basis='synthetic_assumption',policy='fifo',
            workforce_profile=inputs['work_program']['profile'],candidates=[dict(id='actual-flow-check',task=submitted['task'],
                available_at_s=0,question_id='cooling',source_note='Actual paid site inspection in the same advancing facility.')])
        program=dict(schema='aegisdc-policy-run-program-v1',id='online-actual-observation-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0,2.5,3],
            inspection_program=inputs['inspection_program'],intervention_program=None)
        result=simulate_scenario(inputs['model'],duration_s=3,step_s=.01,dispatch_program=program,boundary_events=inputs['boundary_events'])
        decisions=result['policy_public_decisions']
        self.assertEqual(decisions[0]['frame']['evidence']['records'],[])
        self.assertEqual(decisions[1]['frame']['evidence']['records'],[])
        record=decisions[2]['frame']['evidence']['records'][0]
        self.assertEqual((record['observed_at_s'],record['arrived_at_s'],record['value']),(2.25,2.75,0))
        self.assertEqual(result['work_records'][0]['completed_at_s'],2.25)

    def test_hidden_access_change_cannot_change_choices_before_paid_feedback_arrives(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json').read_bytes())
        frame,policy,_=fixture()
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        actions=deepcopy(inputs['intervention_program']);binding=actions['bindings'][0];binding['task_id']='work-first'
        actions['bindings'].append(dict(binding,task_id='work-second',setting=.5))
        program=dict(schema='aegisdc-policy-run-program-v1',id='online-hidden-access-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0,.5],
            inspection_program=None,intervention_program=actions)
        open_run=simulate_scenario(inputs['model'],duration_s=.5,step_s=.01,dispatch_program=program)
        closed=deepcopy(inputs['model']);next(p for p in closed['parameters'] if p['id']=='it_access_permit')['value']=0
        closed_run=simulate_scenario(closed,duration_s=.5,step_s=.01,dispatch_program=program)
        self.assertEqual(open_run['policy_public_decisions'],closed_run['policy_public_decisions'])
        self.assertEqual(open_run['work_records'][0]['status'],'working')
        self.assertEqual(closed_run['work_records'][0]['status'],'aborted')
        self.assertGreater(closed_run['summary']['access_check_person_s'],0)
        self.assertEqual(closed_run['workforce_public_feedback'],[])

    def test_no_human_runs_the_same_facility_without_creating_crew_work(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json').read_bytes())
        frame,policy,_=fixture('no_human')
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        actions=deepcopy(inputs['intervention_program']);binding=actions['bindings'][0];binding['task_id']='work-first'
        actions['bindings'].append(dict(binding,task_id='work-second',setting=.5))
        program=dict(schema='aegisdc-policy-run-program-v1',id='online-no-human-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0,1,2],
            inspection_program=None,intervention_program=actions)
        result=simulate_scenario(inputs['model'],duration_s=2,step_s=.01,dispatch_program=program)
        self.assertEqual(result['work_records'],[])
        self.assertEqual(result['intervention_private_audit']['events'],[])
        self.assertTrue(all(r['choice']['chosen_candidate_id'] is None for r in result['policy_public_decisions']))
        self.assertEqual(result['summary']['worker_work_person_s'],0)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'],.5)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'],1.5)

    def test_fifo_runs_incrementally_in_one_facility_with_delayed_public_feedback(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json').read_bytes())
        frame,policy,history=fixture()
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        actions=inputs['intervention_program']
        first=deepcopy(actions['bindings'][0]);first['task_id']='work-first'
        second=deepcopy(first);second.update(task_id='work-second',setting=.5)
        actions['bindings']=[first,second]
        program=dict(schema='aegisdc-policy-run-program-v1',id='online-fifo-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0,1,2],
            inspection_program=None,intervention_program=actions)
        result=simulate_scenario(inputs['model'],duration_s=4,step_s=.01,dispatch_program=program)
        choices=result['policy_public_decisions']
        self.assertEqual([c['choice']['chosen_candidate_id'] for c in choices],['a-first',None,'b-second'])
        self.assertEqual([r['completed_at_s'] for r in result['work_records']],[1.25,3.25])
        self.assertEqual([r['applied_at_s'] for r in result['intervention_private_audit']['events']],[1.25,3.25])
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'],2.6875)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'],1.3125)
        self.assertEqual(result['summary']['demand_service_unit_s'],4)
        self.assertEqual(result['research_trials'],0)
        self.assertFalse(choices[1]['history']['work_feedback'])
        self.assertEqual(choices[2]['history']['work_feedback'][0]['arrived_at_s'],1.75)

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
