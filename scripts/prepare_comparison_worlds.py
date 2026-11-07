"""Prepare public/private V6 comparison input documents, without executing them."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

from registered_comparison import METHODS, REFERENCE_ARMS, audit_plan, read, require

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
PROTOCOL = ROOT/'docs/mainline/30-comparison-protocol-v1.json'
REFERENCE = ROOT/'evidence/mainline/engineering/26-candidate/reference/online-baseline-inspect.json'
NETWORK_ACTION = ROOT/'evidence/mainline/engineering/23-interventions/reference/network-full.json'
BASELINE = ROOT/'configs/full-facility-mainline-reserve-v6.json'
MODES = ('healthy-clear','healthy-restricted','network-clear','network-restricted')


def _clock_and_context(program, world, plan):
    program['id'] = 'V6-M5-comparison'
    program['decision_times_s'] = plan['decision_times_s']
    program['closure_program'] = None
    policy = program['policy_program']
    policy['id'] = 'V6-M5-shared-policy-declaration'
    policy['resource_budget'] = deepcopy(plan['comparison']['common_admission_budget'])
    private_seed = 300000 + world['slot']
    inspection = program['inspection_program']
    inspection['realizations']['lookahead-inspect'] = dict(seed=private_seed,bias=0,noise_half_width=.002)
    profile = inspection['profile']
    for row in profile['nonfixed_profile']['models']:
        if row['model']['id']=='intake-flow':
            row['model'].update(reported_error_bound=.002001,
                quality_note='Synthetic bounded portable flow error, in cubic metres per second.')
    policy['evidence_projection']['inspection_profile'] = deepcopy(profile)
    program['sensor_program']['realization']['seed'] = private_seed
    # A reported symptom is a hypothesis cue; it does not disclose the fault.
    ledger = program['evidence_ledger']
    ledger['records'] = [dict(id='shared-operator-symptom',source_id='operator-report',
        target_id='filter',observable_id='vibration_reported',unit='1',value=True,observed_at_s=0,
        arrived_at_s=0,valid_until_s=8,quality=dict(status='reported',error_bound=None,
            note='Unconfirmed reported symptom, common to physically different study worlds.'),
        provenance=dict(origin_id='reported-symptom-acquisition',copied_from_record_id=None))]
    return policy


def _question(options, duration, operation, fallback):
    belief, catalog, value = (options[name] for name in ('belief_model','catalog','value_model'))
    channel_ids = {'manual-vibration','lookahead-flow-channel'}
    belief['channels'] = [row for row in belief['channels'] if row['id'] in channel_ids]
    belief['hypotheses'] = [
        dict(id=state, entity_ids=['intake_pump','filter','network'],
             meaning=meaning)
        for state,meaning in zip(MODES,(
            'Adequate intake flow and healthy network.',
            'Restricted intake flow; network remains healthy.',
            'Adequate intake flow with a limited network path.',
            'Restricted intake and limited network path together.',
        ),strict=True)
    ]
    belief['independent_pairs'] = [['manual-vibration','lookahead-flow-channel']]
    belief['independence_basis'] = 'Model-only conditional independence given the four joint hypotheses; no site evidence.'
    belief['unidentified'] = ['The pump signal does not identify network capacity on its own.',
        'The four joint states and conditional likelihoods are study assumptions, not calibrated frequencies.']
    likelihood = dict(zip(MODES,(0,1,0,1),strict=True))
    for index, variant in enumerate(belief['variants']):
        variant.update(prior=[.125,.375,.375,.125],
            transition=[[int(a==b) for b in MODES] for a in MODES],
            positive_likelihood={'manual-vibration':[.25,.75,.25,.75] if index==0 else [.375,.625,.375,.625],
                'lookahead-flow-channel':list(likelihood.values())},
            basis='Declared joint hypotheses and likelihoods; sensitivity varies the contextual symptom.')
    capacity = {name:dict(compute=1,network=(1 if name.startswith('healthy') else .5),storage=1)
                for name in MODES}
    catalog.update(horizon_s=duration,demand=[dict(start_s=0,end_s=duration,rate=1)],
        outcomes=[dict(id=name,meaning='Synthetic finite condition for '+name,
            conditional_probability={state:int(state==name) for state in MODES},
            capacity_profile=[dict(start_s=0,end_s=duration,capacities=capacity[name])]) for name in MODES])
    q = next(row for row in catalog['questions'] if row['id']=='cooling')
    catalog['questions'] = [q]
    q.update(target_ids=['filter','intake_pump','network','critical_service'],
        domain_ids=['facility_cooling','it_service'],outcome_ids=list(MODES),
        window_s=[0,duration],scenario='Distinguish cooling-side symptoms from a limited network path before applying a bounded network fallback.',
        impact_description='A fallback may restore a restricted path or reduce service if applied to a healthy path.',
        closure_evidence='Requires a new service readback after any named action; a flow report alone is not a network recovery claim.',
        conditional_consequence='Finite joint mode forecast; actual power, heat and service remain in the private facility.',
        evidence_gaps=['Flow is a differential diagnostic clue, not a direct network reading.','The fallback effect must be observed in the facility.'])
    for key in ('service_deficit_time_s','unserved_service_unit_s'):
        q['consequence_bounds'][key]['interval'] = [0,duration]
    q['options'] = [row for row in q['options'] if row['id']!='unqualified-cooling']
    action = next(row for row in q['options'] if row['kind']=='intervene')
    action.update(operation_id=operation,target_id='network',qualification_id='qualified_it_inspection',
        tool_ids=['tool_it_diagnostic'],candidate_worker_ids=['worker_it'],
        capability_interface_id='inspect_it_service',source_note='Qualified network fallback referral; actual completion and authority still required.')
    value['availability'] = [dict(resource_id=name,window_s=[0,duration])
        for name in ('worker_cooling','tool_flow_meter','worker_it','tool_it_diagnostic')]
    local = value['question_models'][0]
    local['intervenor_id'] = 'worker_it'
    local['intervention'].update(travel_s=0,wait_s=.25,work_s=1)
    for variant in local['variants']:
        variant.update(positive_likelihood=likelihood,during_capacity=capacity,
            after_capacity={name:dict(c,network=fallback) for name,c in capacity.items()},
            basis='Prospective bounded fallback setting; no immediate change while qualified work is underway.')


def _network_world(template, world, plan):
    program = template['dispatch_program']
    policy = _clock_and_context(program,world,plan)
    parameters = {row['id']:row for row in template['model']['parameters']}
    for name,value in (('network_service_capacity',.25),('filter_resistance_multiplier',1),('pump_min_speed',1)):
        parameters[name].update(value=value,basis='synthetic_assumption',source_refs=['R0'],
            source_note='Named synthetic development condition; no site measurement.')
    sample = read(NETWORK_ACTION)
    action = deepcopy(sample['intervention_program'])
    action['profile']['nominal_knowledge_id'] = program['nominal_knowledge']['id']
    action['profile']['operations'][0]['source_note'] = 'Bounded network fallback capacity setting; can reduce a healthy path.'
    action['bindings'][0].update(task_id='lookahead-action',setting=.75)
    program['intervention_program'] = action
    policy['intervention_declaration'] = deepcopy(action)
    check, repair = policy['candidates']
    check['task']['deadline_s'] = 6
    repair['task'] = deepcopy(sample['work_program']['submissions'][0]['task'])
    repair['task'].update(id='lookahead-action',deadline_s=9)
    operation = action['bindings'][0]['operation_id']
    _question(policy['options'],world['duration_s'],operation,.75)
    template.update(classification='REGISTERED_STUDY_INPUT_PENDING_GATES',duration_s=world['duration_s'],
        maximum_step_s=plan['maximum_step_s'],boundary_events=[])
    return template


def _apply_method(program, method):
    policy = program['policy_program']
    policy['policy'] = method
    if method in ('no_human','fifo'):
        policy['options'] = {}
    elif method=='periodic':
        policy['options'] = dict(schedule=[dict(candidate_id='first-inspection',due_at_s=1)])
    elif method=='risk_condition_priority_adapted':
        options=policy['options']
        policy['options'] = {key:options[key] for key in ('belief_model','catalog','preparation_requests')}
        policy['options'].update(minimum_service_deficit_s=.25,unknown_inspection_policy='fifo',
            conditions=[dict(candidate_id='first-action',source_ids=['portable-intake-meter'],
                target_id='intake_pump',observable_id='flow',accepted_interval=[.075,.15],not_before_s=0)])


def _admit(document, method):
    # No simulator, policy selection, sampling or completion call is made here.
    from aegis_dc.evidence_projection import validate_projection, validate_value_projection_bindings
    from aegis_dc.inspection_execution import InspectionSession
    from aegis_dc.intervention_execution import InterventionSession, prepare_intervention
    from aegis_dc.lookahead_policy import validate_execution_bindings
    from aegis_dc.plant import validate_boundary_events
    from aegis_dc.policy_budget import AdmissionBudget
    from aegis_dc.policy_execution import PolicySession
    from aegis_dc.refrigerant_initialization import assess_refrigerant_initialization
    from aegis_dc.water_envelope import assess_water_envelope
    from aegis_dc.workforce_dispatch import CrewWorkforce, prepare_work

    model, program = (document[k] for k in ('model','dispatch_program'))
    base = read(BASELINE)
    require(model['id']==base['id'] and model['graphs']==base['graphs']
            and model['site_gaps']==base['site_gaps'], 'Named input must keep the accepted V6 topology and gaps')
    duration = document['duration_s']
    validate_boundary_events(model,document['boundary_events'],duration_s=duration)
    assess_refrigerant_initialization(model)
    assess_water_envelope(model,horizon_s=duration)
    session = PolicySession(program,duration)
    frame = session.work_program['initial_frame']
    policy = program['policy_program']
    validate_projection(frame,policy['evidence_projection'])
    candidates = {row['id']:row for row in policy['candidates']}
    if method in METHODS:
        validate_execution_bindings(policy,program['inspection_program'],frame=frame)
        validate_value_projection_bindings(policy['options'],candidates,policy['evidence_projection'])
    parameters = {row['id']:row['value'] for row in model['parameters']}
    CrewWorkforce(model,parameters,session.work_program,duration)
    InspectionSession(model,session.catalog_program,program['inspection_program'])
    intervention=program['intervention_program']
    InterventionSession(model,session.catalog_program,intervention)
    budget = AdmissionBudget(frame,policy,dict(issued=[]),candidates)
    admitted = []
    for row in candidates.values():
        task = row['task']
        if row['kind']=='inspect':
            assessment = prepare_work(frame,policy['workforce_profile'],task)
        else:
            binding = next(binding for binding in intervention['bindings'] if binding['task_id']==task['id'])
            assessment = prepare_intervention(frame,policy['workforce_profile'],task,intervention['profile'],binding)
        if assessment['legal_for_planning'] and budget.can_reserve([row['id']]):
            admitted.append(row['id'])
    require(budget.can_reserve(list(candidates)), 'Declared initial paid options cannot share the common two-issue envelope')
    return admitted


def prepare(world_id, method):
    audit_plan(PROTOCOL)
    plan=read(PROTOCOL)
    development = {row['id']:row for row in plan['phases']['development']['worlds']}
    require(world_id in development,'Held phase is not released; only declared development inputs may be materialized here')
    require(method in REFERENCE_ARMS+METHODS,'Unknown planned comparison method')
    require(world_id=='development-01','This preparation slice currently admits development-01 only')
    document = _network_world(read(REFERENCE),development[world_id],plan)
    _apply_method(document['dispatch_program'],method)
    return document,_admit(document,method)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world',required=True)
    parser.add_argument('--method',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        document,admitted=prepare(args.world,args.method)
        with args.output.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(document,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.write('\n')
    except (ValueError,OSError,KeyError,TypeError) as error:
        parser.exit(2,f'{error}\n')
    print(json.dumps(dict(status='PASS_INPUT_ADMISSION_ONLY',world_id=args.world,
        public_initial_eligible_paid_tasks=len(admitted),initial_paid_candidates=admitted,
        facility_calls=0,selector_calls=0,registered_research_trials=0)))


if __name__=='__main__':
    main()
