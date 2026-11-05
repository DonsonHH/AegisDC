"""Prepare frozen policy engineering cases without running a selector or plant."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
spec=importlib.util.spec_from_file_location('policy_development_fixture',ROOT/'tests/test_dispatch_policy.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
def read(name):return json.loads((ROOT/name).read_bytes())
def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def fixed_program(period=1):
    profile=read('configs/full-facility-sensor-channels-v1.json')
    profile['measurements']=[m for m in profile['measurements'] if m['id']=='rectifier-meter']
    profile['channels']=[c for c in profile['channels'] if c['measurement_id']=='rectifier-meter']
    profile['measurements'][0].update(period_s=period,declared_bias_bound=0,declared_noise_bound=0,quantization_bound=0,declared_dropout_probability=0)
    return dict(profile=profile,realization=dict(schema='aegisdc-private-observation-realization-v1',seed=25,
        biases={'rectifier-meter':0},noise_bounds={'rectifier-meter':0},dropout_probabilities={'rectifier-meter':0}))

def supplemental_cases(model,base,add):
    decimal=deepcopy(base);decimal['decision_times_s']=[.3]
    decimal['policy_program']['resource_budget'].update(person_s=19.4,tool_s=19.4)
    for candidate in decimal['policy_program']['candidates']:candidate['available_at_s']=.3
    add('exact-continuation-budget',deepcopy(model),decimal,.5,dict(forbidden_first='first-inspection',
        forecast_block='COMMON_CONTINUATION_ENVELOPE_EXCEEDS_BUDGET',completed_at_s=[],effect_at_s=[],
        delivered_service_unit_s=.125,service_deficit_time_s=.375,demand_service_unit_s=.5))
    original=read('evidence/mainline/engineering/23-interventions/reference/network-full.json')
    frame,policy,_=fixture.fixture()
    ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
        basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
    actions=deepcopy(original['intervention_program']);binding=actions['bindings'][0];binding['task_id']='work-first'
    actions['bindings'].append(dict(binding,task_id='work-second',setting=.5))
    program=dict(schema='aegisdc-policy-run-program-v1',id='online-hidden-access-engineering',policy_program=policy,
        nominal_knowledge=frame['nominal_knowledge'],evidence_ledger=ledger,decision_times_s=[0,.5],
        inspection_program=None,intervention_program=actions)
    for name,permit,status in [('hidden-open',1,'working'),('hidden-closed',0,'aborted')]:
        world=deepcopy(original['model']);next(p for p in world['parameters'] if p['id']=='it_access_permit')['value']=permit
        add(name,world,deepcopy(program),.5,dict(chosen=['a-first',None],work_status=[status],completed_at_s=[],effect_at_s=[],
            empty_work_feedback=True,delivered_service_unit_s=.125,service_deficit_time_s=.375,demand_service_unit_s=.5))
    rejected=deepcopy(program);rejected['id']='rejected-intention-engineering';rejected['decision_times_s']=[0,.25,1]
    rejected['policy_program']['candidates'][0]['task']['deadline_s']=.5
    add('delayed-rejection',deepcopy(original['model']),rejected,3,dict(chosen=['a-first',None,'b-second'],
        work_status=['rejected','completed'],completed_at_s=[2.25],effect_at_s=[2.25],
        rejection_observed_at_s=0,rejection_arrived_at_s=.5,delivered_service_unit_s=.9375,service_deficit_time_s=2.0625,demand_service_unit_s=3))

def main():
    folder=ROOT/'evidence/mainline/engineering/25-baselines/reference';folder.mkdir(exist_ok=False)
    cases=[]
    def add(name,model,program,duration,expected):
        path=folder/(name+'.json');write(path,dict(classification='ENGINEERING_ONLY_NOT_POLICY_EFFECT_TRIAL',model=model,dispatch_program=program))
        cases.append(dict(id=name,input=path.relative_to(ROOT).as_posix(),duration_s=duration,expected=expected))
    model,base=fixture.lookahead_run_fixture()
    base.update(schema='aegisdc-policy-run-program-v3',sensor_program=fixed_program(),closure_program=None,
        preparation_requests=deepcopy(base['policy_program']['options']['preparation_requests']))
    policy=base['policy_program'];policy.update(schema='aegisdc-dispatch-policy-program-v3',
        intervention_declaration=base['intervention_program'],resource_budget=dict(person_s=100,tool_s=100,cost=2,cost_unit='research_cost_unit'))
    for c in policy['candidates']:c['issue_cost']=1
    local=policy['options']['value_model']['question_models'][0];local['inspection']['cost']=local['intervention']['cost']=1
    # Full common budgets and initial/actual resources are held identical in all
    # five cases. Only the explicit selection rule/options differ.
    definitions=[('no-human','no_human',[None,None,None,None],[],[]),
        ('fifo','fifo',['first-inspection',None,'first-action',None],[1.25,3],[3]),
        ('periodic','periodic',[None,None,None,'first-inspection'],[],[]),
        ('risk-condition','risk_condition_priority_adapted',['first-inspection',None,'first-action',None],[1.25,3],[3]),
        ('one-observation','one_observation_lookahead',['first-inspection',None,'first-action',None],[1.25,3],[3])]
    fixed_records=[[],[[0,.5],[1,1.5]],[[0,.5],[1,1.5]],[[0,.5],[1,1.5],[2,2.5],[3,3.5]]]
    spent={'no-human':(0,0,0),'fifo':(20,20,2),'periodic':(10,10,1),'risk-condition':(20,20,2),'one-observation':(20,20,2)}
    for name,kind,choices,completed,effects in definitions:
        program=deepcopy(base);p=program['policy_program'];p['policy']=kind
        if kind in {'no_human','fifo'}:p['options']={}
        elif kind=='periodic':p['options']=dict(schedule=[dict(candidate_id='first-inspection',due_at_s=2)])
        elif kind=='risk_condition_priority_adapted':
            p['options']=dict(belief_model=deepcopy(policy['options']['belief_model']),catalog=deepcopy(policy['options']['catalog']),
                preparation_requests=deepcopy(base['preparation_requests']),minimum_service_deficit_s=0,unknown_inspection_policy='fifo',
                conditions=[dict(candidate_id='first-action',source_ids=['portable-intake-meter'],target_id='intake_pump',observable_id='flow',
                    accepted_interval=[0,.07],not_before_s=0)])
        add(name,deepcopy(model),program,4,dict(chosen=choices,completed_at_s=completed,effect_at_s=effects,
            delivered_service_unit_s=1,service_deficit_time_s=3,demand_service_unit_s=4,
            fixed_records_per_decision=fixed_records,sensor_poll_epochs_s=[0,1,2,3,4],
            handheld_records_per_decision=[0,0,1,1] if completed else [0,0,0,0],
            handheld_measurement=dict(observed_at_s=1.25,arrived_at_s=1.75,value_squared_ratio=[1,340]) if completed else None,
            final_spent_or_reserved=dict(zip(('person_s','tool_s','cost'),spent[name]))))
    # At4s the explicit periodic decision finally issues its due inspection;
    # finishing lies beyond this horizon, and no success/effect is credited.
    decimal=deepcopy(base);decimal['policy_program'].update(policy='no_human',options={})
    decimal['sensor_program']=fixed_program(.1);decimal['decision_times_s']=[.5]
    add('decimal-prefix',deepcopy(model),decimal,.5,dict(chosen=[None],completed_at_s=[],effect_at_s=[],sensor_polls=6,
        last_poll_index=5,last_polled_at_s=.5,delivered_service_unit_s=.125,service_deficit_time_s=.375,demand_service_unit_s=.5))
    expiry=deepcopy(base);expiry['decision_times_s']=[0]
    expiry['intervention_program']['profile']['authorizations'][0]['expires_at_s']=3
    expiry['policy_program']['intervention_declaration']=deepcopy(expiry['intervention_program'])
    add('future-authority',deepcopy(model),expiry,.5,dict(forbidden_first='first-inspection',forecast_block='FORECAST_ACTION_AUTHORITY_UNAVAILABLE_AT_COMPLETION',
        completed_at_s=[],effect_at_s=[],delivered_service_unit_s=.125,service_deficit_time_s=.375,demand_service_unit_s=.5))
    tight=deepcopy(base);tight['decision_times_s']=[0]
    tight['policy_program']['resource_budget'].update(person_s=15,tool_s=15)
    add('continuation-budget',deepcopy(model),tight,.5,dict(forbidden_first='first-inspection',forecast_block='COMMON_CONTINUATION_ENVELOPE_EXCEEDS_BUDGET',
        completed_at_s=[],effect_at_s=[],delivered_service_unit_s=.125,service_deficit_time_s=.375,demand_service_unit_s=.5))
    # Exercise the same closure consumer with actual arrived reports only. The
    # first pre-action reading and no service record cannot prove restoration.
    from test_verified_closure import fixture as closure_fixture
    _,closure,registry,_=closure_fixture();program=deepcopy(base)
    closure['intervention_feedback']=[];closure['intervention_declaration']=deepcopy(program['intervention_program'])
    nominal_id=program['nominal_knowledge']['id']
    closure['profile']['nominal_knowledge_id']=nominal_id;closure['risk_catalog']['nominal_knowledge_id']=nominal_id
    closure['belief_model']['scope']['nominal_knowledge_id']=nominal_id
    rule=closure['profile']['rules'][0];rule.update(task_id='lookahead-action',operation_id=program['intervention_program']['bindings'][0]['operation_id'])
    rule['checks'][0].update(source_ids=['portable-intake-meter'],accepted_interval=[.07,.08])
    for field in ('sources','observables'):
        ids={r['id'] for r in program['evidence_ledger'][field]}
        program['evidence_ledger'][field].extend(deepcopy(r) for r in registry[field] if r['id'] not in ids)
    program['closure_program']=closure
    add('closure-pending',deepcopy(model),program,4,dict(chosen=['first-inspection',None,'first-action',None],completed_at_s=[1.25,3],effect_at_s=[3],
        closure_status='ACTION_COMPLETED_PENDING_VERIFICATION',delivered_service_unit_s=1,service_deficit_time_s=3,demand_service_unit_s=4))
    supplemental_cases(model,base,add)
    protocol=dict(schema='aegisdc-policy-engineering-protocol-v1',ticket='25',classification='FINITE_ENGINEERING_INTERFACE_CHECKS_NOT_EFFECT_COMPARISON',
        cases=cases,maximum_step_s=.01,physical_runs=len(cases),total_simulated_duration_s=sum(c['duration_s'] for c in cases),
        hidden_public_equal_cases=['hidden-open','hidden-closed'],
        same_world_cases=[c[0] for c in definitions],authoring_tool='scripts/policy_delivery.py',helper_tool='scripts/inspection_delivery.py',
        input_preparation_tool='scripts/prepare_policy_inputs.py',input_fixture='tests/test_dispatch_policy.py',additional_test_input='tests/test_action_value.py',
        closure_test_input='tests/test_verified_closure.py',contract='docs/mainline/25-policy-execution.md',literature_note='docs/research/20261105/baseline-selection.md',
        durable_root=['attempt.json','attempts.jsonl','checks.json','policy-decisions.svg','policy-boundary.svg'],
        durable_case=['run.json','scenario.json','private-state.jsonl','balances.jsonl'],terminal_receipt='receipt.json',
        absolute_tolerance=1e-9,energy_tolerance_J=1e-4,mass_tolerance_kg=1e-9,
        retry_rule='One call per case. STARTED precedes actual call; save and validate before next attempt. Failure stops immediately and remains. No automatic retries; correction needs new protocol/source/output.',
        registered_research_trials=0,llm_calls=0,training_calls=0,field_calibration='PENDING',full_regression='ROOT_INTEGRATED_ONLY',
        scope='Same synthetic eight-domain facility, same public static/arrived inputs and actual resources for five declared policies. Literal task/observation/authority/budget/order checks only; no superiority claim. Forecast model remains declared uncalibrated finite law; actual power/service remains plant account.')
    write(ROOT/'docs/mainline/25-policy-engineering-protocol.json',protocol)
    print(json.dumps(dict(prepared_cases=len(cases),physical_runs=0,simulated_budget_s=protocol['total_simulated_duration_s'])))
if __name__=='__main__':main()
