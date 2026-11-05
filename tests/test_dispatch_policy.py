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

def risk_fixture(time=0):
    from aegis_dc.evidence_ledger import RECORD_FIELDS
    load=lambda name:json.loads((ROOT/name).read_bytes())
    accepted=load('evidence/mainline/engineering/18-beliefs/capture-01/cli-frame.json')
    ledger=dict(schema='aegisdc-evidence-ledger-v1',id=accepted['evidence']['ledger_id'],facility_id=accepted['facility_id'],
        basis='synthetic_assumption',time_unit='s',**accepted['evidence']['static_knowledge'],records=[])
    ledger['sources'].append(dict(id='policy-condition-meter',kind='handheld',basis='synthetic_assumption',target_ids=['intake_pump'],
        observable_ids=['flow'],dependency_group='policy-meter-chain',source_note='Declared finite professional condition measurement channel.'))
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='risk-policy25',basis='synthetic_assumption',time_unit='s',decision_times_s=[time],requests=accepted['requests'])
    frame=DecisionGateway(accepted['nominal_knowledge'],ledger,plan).next_frame()
    _,program,history=fixture()
    task=program['candidates'][0]['task']
    task.update(id='cooling-inspection',target_id='intake_pump',work_interface_id='inspect_facility_cooling',
        crew=[dict(worker_id='worker_cooling',qualification_id='qualified_cooling_inspection')],tool_carrier_id='worker_cooling')
    repair=deepcopy(task);repair.update(id='filter-cleaning',target_id='filter')
    unknown=deepcopy(task);unknown.update(id='room-inspection',target_id='room',work_interface_id='inspect_equipment_environment')
    program.update(schema='aegisdc-dispatch-policy-program-v2',policy='risk_condition_priority_adapted',
        candidates=[dict(id='cooling-check',kind='inspect',task=task,available_at_s=0,question_id='cooling',source_note='Declared cooling check.'),
            dict(id='filter-action',kind='intervene',task=repair,available_at_s=0,question_id='cooling',source_note='Conditional filter action.'),
            dict(id='unknown-room-check',kind='inspect',task=unknown,available_at_s=0,question_id='room-boundary',source_note='Unmodeled room question stays explicit.')],
        options=dict(belief_model=load('configs/full-facility-belief-model-v1.json'),catalog=load('configs/full-facility-risk-scenarios-v1.json'),
            preparation_requests=accepted['requests'],
            minimum_service_deficit_s=0,unknown_inspection_policy='fifo',conditions=[dict(candidate_id='filter-action',source_ids=['policy-condition-meter'],
                target_id='intake_pump',observable_id='flow',accepted_interval=[0,.05],not_before_s=0)]))
    return frame,program,history,ledger,accepted['nominal_knowledge'],plan

class DispatchPolicyTests(unittest.TestCase):
    def test_live_sparse_fixed_measurement_is_sampled_once_and_delivered_with_latency(self):
        load=lambda name:json.loads((ROOT/name).read_bytes())
        inputs=load('evidence/mainline/engineering/23-interventions/reference/network-full.json')
        frame,policy,_=fixture('no_human')
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        profile=load('configs/full-facility-sensor-channels-v1.json')
        profile['measurements']=[m for m in profile['measurements'] if m['id']=='rectifier-meter']
        profile['channels']=[c for c in profile['channels'] if c['measurement_id']=='rectifier-meter']
        m=profile['measurements'][0];m.update(period_s=1,declared_bias_bound=0,declared_noise_bound=0,quantization_bound=0,declared_dropout_probability=0)
        realization=dict(schema='aegisdc-private-observation-realization-v1',seed=25,biases={'rectifier-meter':0},
            noise_bounds={'rectifier-meter':0},dropout_probabilities={'rectifier-meter':0})
        program=dict(schema='aegisdc-policy-run-program-v2',id='online-fixed-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0,.25,.5,1],
            inspection_program=None,intervention_program=None,sensor_program=dict(profile=profile,realization=realization))
        result=simulate_scenario(inputs['model'],duration_s=1,step_s=.01,dispatch_program=program)
        choices=result['policy_public_decisions']
        self.assertEqual(choices[0]['frame']['evidence']['records'],[])
        self.assertEqual(choices[1]['frame']['evidence']['records'],[])
        at=choices[2]['frame']['evidence']['records']
        self.assertEqual(len(at),1)
        self.assertEqual((at[0]['observed_at_s'],at[0]['arrived_at_s']),(0,.5))
        self.assertEqual(at[0]['value'],result['trace'][0]['domains']['power']['rectifier_input_W'])
        self.assertEqual(len(choices[3]['frame']['evidence']['records']),1)
        self.assertEqual(choices[3]['frame']['evidence']['records'][0]['id'],at[0]['id'])
        self.assertNotIn('private_realization',json.dumps(choices))
        self.assertEqual(len(result['policy_sensor_private_audit']),2)

    def test_one_observation_lookahead_selects_only_the_first_predicted_action(self):
        from aegis_dc.dispatch_policy import choose_work
        from test_action_value import fixture as value_fixture
        frame,belief,catalog,value_model=value_fixture()
        _,policy,history,_,_,_=risk_fixture()
        policy['candidates']=policy['candidates'][:2]
        policy['candidates'][0]['task']['target_id']='filter'
        policy.update(policy='one_observation_lookahead',options=dict(belief_model=belief,catalog=catalog,value_model=value_model,
            preparation_requests=frame['requests'],unknown_inspection_policy='fifo',bindings=[dict(question_id='cooling',
                inspection_candidate_id='cooling-check',intervention_candidate_id='filter-action',
                source_note='Explicit finite planning-option to same-scope first work-intention mapping.')]))
        before=deepcopy((frame,policy,history))
        result=choose_work(frame,policy,history)
        self.assertEqual(result['chosen_candidate_id'],'cooling-check')
        self.assertEqual(result['reason'],'ONE_OBSERVATION_FIRST_ACTION_ONLY')
        self.assertAlmostEqual(result['forecast_plans'][0]['best_expected_service_deficit_s'],12.5)
        self.assertEqual(result['forecast_plans'][0]['best_alternative'],'inspect_then_act')
        self.assertEqual(result['forecast_window_s'],[0,100])
        self.assertEqual(result['model_evaluations'],dict(risk=0,action_value=1))
        self.assertEqual((frame,policy,history),before)
        self.assertEqual(result['work_intention']['id'],'cooling-inspection')
        # Uninformative inspection should not force an extra check before action.
        for variant in policy['options']['value_model']['question_models'][0]['variants']:
            variant['positive_likelihood']={key:.5 for key in variant['positive_likelihood']}
        direct=choose_work(frame,policy,history)
        self.assertEqual(direct['chosen_candidate_id'],'filter-action')
        self.assertEqual(direct['forecast_plans'][0]['best_alternative'],'direct_intervention')
        self.assertAlmostEqual(direct['forecast_plans'][0]['best_expected_service_deficit_s'],20)
        # With no useful state response the predeclared alternative may be defer.
        for variant in policy['options']['value_model']['question_models'][0]['variants']:
            variant['after_capacity']={key:{c:0 for c in catalog['service_component_ids']} for key in variant['after_capacity']}
        deferred=choose_work(frame,policy,history)
        self.assertIsNone(deferred['chosen_candidate_id'])
        self.assertEqual(deferred['reason'],'MODEL_PREFERS_DEFER')

    def test_arrived_actual_inspection_drives_risk_policy_action_in_the_same_facility(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/22-inspections/reference/input-v1.json').read_bytes())
        _,policy,_,ledger,nominal,_=risk_fixture()
        inspection=inputs['work_program']['submissions'][0]['task']
        action=deepcopy(inspection);action.update(id='conditional-filter-action',target_id='filter')
        policy['candidates']=[dict(id='actual-check',kind='inspect',task=inspection,available_at_s=0,question_id='cooling',source_note='Actual paid cooling inspection.'),
            dict(id='conditional-action',kind='intervene',task=action,available_at_s=0,question_id='cooling',source_note='Conditioned research operation.')]
        policy['options']['catalog']['questions'][0]['target_ids'].append('internal_pump')
        source_id=inputs['inspection_program']['profile']['nonfixed_profile']['models'][0]['source_id']
        # The actual flow model named by the binding supplies this channel.
        model_id=inputs['inspection_program']['profile']['bindings'][0]['model_id']
        source_id=next(m['source_id'] for m in inputs['inspection_program']['profile']['nonfixed_profile']['models'] if m['model']['id']==model_id)
        policy['options']['conditions']=[dict(candidate_id='conditional-action',source_ids=[source_id],target_id='internal_pump',observable_id='flow',accepted_interval=[-.01,.05],not_before_s=0)]
        actions=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/filter-later-inspection.json').read_bytes())['intervention_program']
        actions['bindings'][0]['task_id']=action['id']
        program=dict(schema='aegisdc-policy-run-program-v1',id='online-risk-condition-engineering',policy_program=policy,
            nominal_knowledge=nominal,evidence_ledger=ledger,decision_times_s=[0,2.5,3,7],inspection_program=inputs['inspection_program'],intervention_program=actions)
        result=simulate_scenario(inputs['model'],duration_s=7,step_s=.01,dispatch_program=program,boundary_events=inputs['boundary_events'])
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in result['policy_public_decisions']],['actual-check',None,'conditional-action',None])
        decision=result['policy_public_decisions'][2]
        self.assertEqual(decision['choice']['reason'],'ARRIVED_CONDITION_MAINTENANCE_ADAPTATION')
        self.assertEqual(decision['frame']['evidence']['records'][0]['arrived_at_s'],2.75)
        self.assertEqual(result['intervention_private_audit']['events'][0]['applied_at_s'],6.25)
        self.assertFalse(result['intervention_public_feedback'][0]['risk_closed'])

    def test_risk_condition_policy_waits_for_arrived_condition_and_keeps_unknown_explicit(self):
        from aegis_dc.dispatch_policy import choose_work
        frame,program,history,ledger,nominal,plan=risk_fixture()
        first=choose_work(frame,program,history)
        self.assertEqual(first['chosen_candidate_id'],'cooling-check')
        self.assertEqual(first['model_evaluations'],dict(risk=1,action_value=0))
        unknown=next(c for c in first['candidates'] if c['candidate_id']=='unknown-room-check')
        self.assertIsNone(unknown['risk_service_deficit_s'])
        self.assertIn('room-boundary',first['unmodeled_question_ids'])
        action=next(c for c in first['candidates'] if c['candidate_id']=='filter-action')
        self.assertIn('NO_CURRENT_CONDITION_SUPPORT',action['reasons'])
        ledger['records'].append(dict(id='low-flow-confirmation',source_id='policy-condition-meter',target_id='intake_pump',observable_id='flow',
            unit='m3/s',value=.02,observed_at_s=.5,arrived_at_s=1,valid_until_s=3,
            quality=dict(status='bounded',error_bound=.005,note='Declared finite numeric condition witness.'),
            provenance=dict(origin_id='low-flow-origin',copied_from_record_id=None)))
        plan['decision_times_s']=[.75];early=DecisionGateway(nominal,ledger,plan).next_frame()
        self.assertEqual(choose_work(early,program,history)['chosen_candidate_id'],'cooling-check')
        plan['decision_times_s']=[1];arrived=DecisionGateway(nominal,ledger,plan).next_frame()
        ready=choose_work(arrived,program,history)
        self.assertEqual(ready['chosen_candidate_id'],'filter-action')
        self.assertEqual(ready['reason'],'ARRIVED_CONDITION_MAINTENANCE_ADAPTATION')
        self.assertEqual(next(c for c in ready['candidates'] if c['candidate_id']=='filter-action')['condition_record_ids'],['low-flow-confirmation'])
        plan['decision_times_s']=[3];expired=DecisionGateway(nominal,ledger,plan).next_frame()
        self.assertNotEqual(choose_work(expired,program,history)['chosen_candidate_id'],'filter-action')

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
