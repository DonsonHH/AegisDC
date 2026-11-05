"""Transparent choices through the evidence-only public decision-frame seam."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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

def lookahead_run_fixture():
    from test_action_value import fixture as value_fixture
    frame,belief,catalog,value=value_fixture()
    inputs=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/filter-later-inspection.json').read_bytes())
    catalog['horizon_s']=5;catalog['demand']=[dict(start_s=0,end_s=5,rate=1)]
    for outcome in catalog['outcomes']:outcome['capacity_profile'][0]['end_s']=5
    for question in catalog['questions']:
        question['window_s']=[0,5]
        question['consequence_bounds']['service_deficit_time_s']['interval']=[0,5]
        question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,5]
    for resource in value['availability']:resource['window_s']=[0,5]
    _,policy,_,ledger,nominal,_=risk_fixture()
    # This finite witness declares a co-located initial actor/tool in both the
    # public design and actual fixture. Other tests retain costly travel.
    nominal['id']='V6-policy25-colocated-engineering'
    for entity in nominal['entities']:
        if entity['id'] in {'worker_cooling','tool_flow_meter'}:entity['nominal_location_id']='loc_lake'
    for entity in inputs['model']['entities']:
        if entity['id'] in {'worker_cooling','tool_flow_meter'}:entity['location_id']='loc_lake'
    policy['workforce_profile']=inputs['work_program']['profile']
    policy['workforce_profile']['nominal_knowledge_id']=nominal['id']
    catalog['nominal_knowledge_id']=nominal['id'];belief['scope']['nominal_knowledge_id']=nominal['id'];value['nominal_knowledge_id']=nominal['id']
    inspection=deepcopy(inputs['work_program']['submissions'][1]['task']);inspection['id']='lookahead-inspect'
    action=deepcopy(inputs['work_program']['submissions'][0]['task']);action['id']='lookahead-action'
    policy['candidates']=[dict(id='first-inspection',kind='inspect',task=inspection,available_at_s=0,question_id='cooling',source_note='First actual paid check.'),
        dict(id='first-action',kind='intervene',task=action,available_at_s=0,question_id='cooling',source_note='First authorized actual action.')]
    requests=deepcopy(frame['requests'])
    next(r for r in requests if r['id']=='intent-filter-check')['target_id']='intake_pump'
    actual=deepcopy(inputs['inspection_program']);binding=actual['profile']['bindings'][0];binding['task_id']=inspection['id']
    actual['realizations']={inspection['id']:dict(seed=25,bias=0,noise_half_width=0)}
    source=next(m for m in actual['profile']['nonfixed_profile']['models'] if m['model']['id']==binding['model_id'])
    belief['channels'].append(dict(id='lookahead-flow-channel',source_id=source['source_id'],target_id=source['target_id'],
        observable_id=source['observable_id'],unit='m3/s',positive_when='below',threshold=.07))
    for variant in belief['variants']:variant['positive_likelihood']['lookahead-flow-channel']=[.1,.8,.1,.1]
    local=value['question_models'][0]
    local['inspection'].update(travel_s=0,wait_s=.25,work_s=1,report_latency_s=.5,cost=0)
    local['intervention'].update(travel_s=0,wait_s=.25,work_s=1,cost=0)
    actions=deepcopy(inputs['intervention_program']);actions['bindings'][0]['task_id']=action['id']
    actions['profile']['nominal_knowledge_id']=nominal['id']
    policy.update(policy='one_observation_lookahead',options=dict(belief_model=belief,catalog=catalog,value_model=value,
        preparation_requests=requests,unknown_inspection_policy='fifo',bindings=[dict(question_id='cooling',inspection_candidate_id='first-inspection',
            intervention_candidate_id='first-action',source_note='Explicit reference model/first-work mapping with declared actual measurement channel.')]))
    program=dict(schema='aegisdc-policy-run-program-v1',id='online-lookahead-engineering',policy_program=policy,nominal_knowledge=nominal,
        evidence_ledger=ledger,decision_times_s=[0,1.5,1.75,4],inspection_program=actual,intervention_program=actions)
    return inputs['model'],program

class DispatchPolicyTests(unittest.TestCase):
    def test_forecast_does_not_credit_actions_completed_at_or_after_known_authority_expiry(self):
        model,program=lookahead_run_fixture();program['decision_times_s']=[0]
        grant=program['intervention_program']['profile']['authorizations'][0]
        grant['expires_at_s']=3
        result=simulate_scenario(model,duration_s=.5,step_s=.01,dispatch_program=program)
        choice=result['policy_public_decisions'][0]['choice']
        plan=next(a for a in choice['forecast_plans'][0]['alternatives'] if a['kind']=='inspect_then_act')
        self.assertFalse(plan['eligible'])
        self.assertIn('FORECAST_ACTION_AUTHORITY_UNAVAILABLE_AT_COMPLETION',plan['planning_reasons'])
        self.assertNotEqual(choice['chosen_candidate_id'],'first-inspection')

    def test_lookahead_rejects_a_continuation_exceeding_the_common_admission_envelopes(self):
        model,program=lookahead_run_fixture();program['decision_times_s']=[0]
        policy=program['policy_program']
        policy.update(schema='aegisdc-dispatch-policy-program-v3',intervention_declaration=program['intervention_program'],
            resource_budget=dict(person_s=15,tool_s=15,cost=2,cost_unit='research_cost_unit'))
        for candidate in policy['candidates']:candidate['issue_cost']=1
        local=policy['options']['value_model']['question_models'][0];local['inspection']['cost']=local['intervention']['cost']=1
        result=simulate_scenario(model,duration_s=.5,step_s=.01,dispatch_program=program)
        choice=result['policy_public_decisions'][0]['choice']
        plan=next(a for a in choice['forecast_plans'][0]['alternatives'] if a['kind']=='inspect_then_act')
        self.assertFalse(plan['eligible'])
        self.assertIn('COMMON_CONTINUATION_ENVELOPE_EXCEEDS_BUDGET',plan['planning_reasons'])
        self.assertNotEqual(choice['chosen_candidate_id'],'first-inspection')

    def test_online_closure_consumes_actual_arrived_action_reports_without_auto_closing(self):
        from test_verified_closure import fixture as closure_fixture
        model,program=lookahead_run_fixture();_,closure,closure_ledger,_=closure_fixture()
        closure['intervention_feedback']=[];closure['intervention_declaration']=program['intervention_program']
        closure['profile']['nominal_knowledge_id']=program['nominal_knowledge']['id']
        closure['risk_catalog']['nominal_knowledge_id']=program['nominal_knowledge']['id']
        closure['belief_model']['scope']['nominal_knowledge_id']=program['nominal_knowledge']['id']
        rule=closure['profile']['rules'][0];rule.update(task_id='lookahead-action',operation_id=program['intervention_program']['bindings'][0]['operation_id'])
        rule['checks'][0]['source_ids']=['portable-intake-meter']
        rule['checks'][0]['accepted_interval']=[.07,.08]
        static=program['evidence_ledger']
        for field in ('sources','observables'):
            ids={r['id'] for r in static[field]}
            static[field].extend(deepcopy(r) for r in closure_ledger[field] if r['id'] not in ids)
        program.update(schema='aegisdc-policy-run-program-v3',sensor_program=None,closure_program=closure,
            preparation_requests=program['policy_program']['options']['preparation_requests'])
        result=simulate_scenario(model,duration_s=4,step_s=.01,dispatch_program=program)
        before=result['policy_public_decisions'][0]['choice']['question_lifecycle']['questions'][0]
        after=result['policy_public_decisions'][-1]['choice']['question_lifecycle']['questions'][0]
        self.assertEqual(before['status'],'OPEN_UNCONFIRMED')
        self.assertEqual(after['status'],'ACTION_COMPLETED_PENDING_VERIFICATION')
        self.assertFalse(after['question_closed'])
        action=next(e for e in after['trace'] if e['event']=='ACTION_REPORT_AVAILABLE')
        self.assertEqual((action['observed_at_s'],action['arrived_at_s']),(3,3.5))

    def test_question_closure_uses_same_public_evidence_and_blocks_only_declared_closed_question(self):
        from aegis_dc.dispatch_policy import choose_work
        from test_verified_closure import fixture as closure_fixture
        frame,closure,_,_=closure_fixture()
        _,policy,history,_,_,_=risk_fixture(time=6)
        policy['policy']='fifo';policy['options']={}
        policy['candidates']=policy['candidates'][:1]
        result=choose_work(frame,policy,history,closure_program=closure)
        self.assertIsNone(result['chosen_candidate_id'])
        self.assertIn('DECLARED_QUESTION_CLOSED',result['candidates'][0]['reasons'])
        self.assertEqual(result['question_lifecycle']['questions'][0]['status'],'VERIFIED_CLOSED')
        self.assertTrue(result['question_lifecycle']['unevaluated_question_ids'])
        closure['intervention_feedback']=[]
        unverified=choose_work(frame,policy,history,closure_program=closure)
        self.assertEqual(unverified['chosen_candidate_id'],'cooling-check')
        self.assertEqual(unverified['question_lifecycle']['questions'][0]['status'],'OPEN_UNCONFIRMED')

    def test_lookahead_runs_one_first_check_then_updates_from_its_actual_arrived_record(self):
        model,program=lookahead_run_fixture()
        policy=program['policy_program']
        policy.update(schema='aegisdc-dispatch-policy-program-v3',intervention_declaration=program['intervention_program'],
            resource_budget=dict(person_s=100,tool_s=100,cost=2,cost_unit='research_cost_unit'))
        for candidate in policy['candidates']:candidate['issue_cost']=1
        local=policy['options']['value_model']['question_models'][0]
        local['inspection']['cost']=local['intervention']['cost']=1
        result=simulate_scenario(model,duration_s=4,step_s=.01,dispatch_program=program)
        decisions=result['policy_public_decisions']
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in decisions],['first-inspection',None,'first-action',None])
        self.assertEqual(decisions[0]['choice']['forecast_plans'][0]['best_alternative'],'inspect_then_act')
        self.assertAlmostEqual(decisions[0]['choice']['forecast_plans'][0]['best_expected_service_deficit_s'],.925)
        self.assertEqual(decisions[1]['frame']['evidence']['records'],[])
        record=decisions[2]['frame']['evidence']['records'][0]
        self.assertEqual((record['observed_at_s'],record['arrived_at_s']),(1.25,1.75))
        self.assertAlmostEqual(decisions[2]['choice']['forecast_belief']['posterior']['cooling-limited'],8/11)
        self.assertEqual(result['intervention_private_audit']['events'][0]['applied_at_s'],3)
        self.assertFalse(result['intervention_public_feedback'][0]['risk_closed'])
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'],dict(person_s=20,tool_s=20,cost=2))
        self.assertEqual(result['summary']['worker_work_person_s'],2)
        self.assertEqual(len(result['policy_computation_audit']),4)

    def test_online_forecast_cannot_replace_known_work_duration_with_unrelated_timing(self):
        model,program=lookahead_run_fixture()
        program['decision_times_s']=[0]
        program['policy_program']['options']['value_model']['question_models'][0]['inspection']['work_s']=99
        with self.assertRaisesRegex(ValueError,'Forecast professional work duration differs'):
            simulate_scenario(model,duration_s=1,step_s=.01,dispatch_program=program)

    def test_public_binding_identity_refuses_container_values_as_invalid_json_contract(self):
        from aegis_dc.dispatch_policy import choose_work
        frame,policy,history=fixture()
        declaration=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json').read_bytes())['intervention_program']
        declaration['bindings'][0]['task_id']=[]
        with self.assertRaises(ValueError):choose_work(frame,policy,history,intervention_declaration=declaration)

    def test_simulate_cli_runs_the_declared_policy_program_without_implicit_work(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json').read_bytes())
        frame,policy,_=fixture('no_human')
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        program=dict(schema='aegisdc-policy-run-program-v1',id='cli-policy-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0],inspection_program=None,intervention_program=None)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'model.json';declared=root/'policy.json';out=root/'run'
            model.write_text(json.dumps(inputs['model']),encoding='utf-8');declared.write_text(json.dumps(program),encoding='utf-8')
            command=[sys.executable,'-B','-X','utf8','-m','aegis_dc','simulate','--model',str(model),'--duration','.5','--step','.01',
                '--dispatch-program',str(declared),'--output',str(out)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',env=dict(os.environ,PYTHONPATH=str(ROOT/'src')))
            self.assertEqual(result.returncode,0,result.stderr)
            saved=json.loads((out/'run.json').read_bytes())
            self.assertEqual(saved['work_records'],[])
            self.assertIsNone(saved['policy_public_decisions'][0]['choice']['work_intention'])
            self.assertAlmostEqual(saved['summary']['delivered_service_unit_s'],.125)
            again=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',env=dict(os.environ,PYTHONPATH=str(ROOT/'src')))
            self.assertNotEqual(again.returncode,0)

    def test_current_public_intervention_authority_blocks_submission_before_paid_work(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json').read_bytes())
        frame,policy,_=fixture()
        policy['candidates']=policy['candidates'][:1]
        actions=inputs['intervention_program'];actions['bindings'][0]['task_id']='work-first'
        actions['profile']['authorizations'][0]['starts_at_s']=2
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        program=dict(schema='aegisdc-policy-run-program-v1',id='known-authority-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0],
            inspection_program=None,intervention_program=actions)
        result=simulate_scenario(inputs['model'],duration_s=1,step_s=.01,dispatch_program=program)
        choice=result['policy_public_decisions'][0]['choice']
        self.assertIsNone(choice['chosen_candidate_id'])
        self.assertIn('declared_authorization_unavailable_at_issue',choice['candidates'][0]['reasons'])
        self.assertEqual(result['work_records'],[])
        self.assertEqual(result['summary']['worker_work_person_s'],0)

    def test_decimal_completed_inspection_reports_its_full_declared_work(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/22-inspections/reference/input-v1.json').read_bytes())
        inputs['work_program']['profile']['access_check_s']=.2
        for entity in inputs['model']['entities']:
            if entity['id'] in {'worker_control','tool_flow_meter'}:entity['location_id']='loc_hx'
        result=simulate_scenario(inputs['model'],duration_s=2,step_s=.01,work_program=inputs['work_program'],inspection_program=inputs['inspection_program'])
        self.assertEqual(result['work_records'][0]['completed_at_s'],1.2)
        record=result['inspection_public_snapshot']['records'][0]
        self.assertEqual((record['observed_at_s'],record['arrived_at_s']),(1.2,1.7))

    def test_delayed_task_local_rejection_releases_only_its_public_reservation(self):
        inputs=json.loads((ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json').read_bytes())
        frame,policy,_=fixture()
        policy['candidates'][0]['task']['deadline_s']=.5
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
            basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
        actions=inputs['intervention_program'];actions['bindings'][0]['task_id']='work-first'
        actions['bindings'].append(dict(actions['bindings'][0],task_id='work-second',setting=.5))
        program=dict(schema='aegisdc-policy-run-program-v1',id='rejected-intention-engineering',policy_program=policy,
            nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0,.25,1],
            inspection_program=None,intervention_program=actions)
        result=simulate_scenario(inputs['model'],duration_s=3,step_s=.01,dispatch_program=program)
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in result['policy_public_decisions']],['a-first',None,'b-second'])
        self.assertEqual([r['status'] for r in result['work_records']],['rejected','completed'])
        self.assertEqual(result['policy_public_decisions'][1]['history']['work_feedback'],[])
        report=result['policy_public_decisions'][2]['history']['work_feedback'][0]
        self.assertEqual((report['status'],report['observed_at_s'],report['arrived_at_s']),('rejected',0,.5))
        self.assertEqual(report['reason'],'DECLARED_TASK_ADMISSION_REFUSAL')
        self.assertIsNone(report['location_id'])

    def test_common_budget_remains_spent_after_terminal_feedback_across_decisions(self):
        from aegis_dc.dispatch_policy import choose_work
        frame,policy,history=fixture()
        policy.update(schema='aegisdc-dispatch-policy-program-v3',options={},
            intervention_declaration=None,resource_budget=dict(person_s=15,tool_s=15,cost=1,cost_unit='research_cost_unit'))
        for candidate in policy['candidates']:
            candidate.update(kind='inspect',issue_cost=1)
        first=choose_work(frame,policy,history)
        self.assertEqual(first['chosen_candidate_id'],'a-first')
        self.assertEqual(first['resource_ledger']['remaining'],dict(person_s=15,tool_s=15,cost=1))
        history['issued']=[dict(candidate_id='a-first',issued_at_s=0)]
        history['work_feedback']=[dict(task_id='work-first',source_id='workforce-execution-report',observed_at_s=1.25,
            arrived_at_s=1.75,status='completed',reason=None,location_id='loc_it',origin_id='workforce:work-first',
            coverage='THIS_ISSUED_TASK_ONLY',basis='SYNTHETIC_FINITE_TIMED_EXECUTION_CHANNEL')]
        frame,_,_=fixture(time=2)
        next_choice=choose_work(frame,policy,history)
        self.assertIsNone(next_choice['chosen_candidate_id'])
        self.assertEqual(next_choice['resource_ledger']['spent_or_reserved'],dict(person_s=10,tool_s=10,cost=1))
        self.assertEqual(next_choice['resource_ledger']['remaining'],dict(person_s=5,tool_s=5,cost=0))
        blocked=next(c for c in next_choice['candidates'] if c['candidate_id']=='b-second')
        self.assertIn('COMMON_CUMULATIVE_BUDGET_EXHAUSTED',blocked['reasons'])
        policy['policy']='no_human'
        nohuman=choose_work(frame,policy,history)
        self.assertEqual(nohuman['resource_ledger'],next_choice['resource_ledger'])

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
        # The fifth .1-second epoch rounds to .5 in binary64; it still samples.
        profile['measurements'][0]['period_s']=.1
        program['decision_times_s']=[1]
        decimal=simulate_scenario(inputs['model'],duration_s=1,step_s=.01,dispatch_program=program)
        decimal_records=decimal['policy_public_decisions'][0]['frame']['evidence']['records']
        fifth=next(r for r in decimal_records if r['id']=='power-transfer:5')
        self.assertEqual((fifth['observed_at_s'],fifth['arrived_at_s']),(.5,1))
        self.assertEqual(len(decimal_records),6)
        program['decision_times_s']=[.5]
        prefix=simulate_scenario(inputs['model'],duration_s=.5,step_s=.01,dispatch_program=program)
        self.assertEqual(len(prefix['policy_sensor_private_audit']),6)
        self.assertEqual(prefix['policy_sensor_private_audit'][-1]['poll_index'],5)
        self.assertEqual(prefix['policy_sensor_private_audit'][-1]['polled_at_s'],.5)

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
