"""A transparent binary decision/inspection-value example, not a FEMA device score."""
import math

EVIDENCE_SOURCES={'historical_record','manual_report','fixed_sensor','portable_measurement'}
QUESTION_FIELDS={'id','asset_id','horizon_hours','currency','parameter_basis','parameter_source','defect_probability',
 'loss_event_probability_given_defect','loss_given_event','mitigation_cost','mitigation_residual_fraction',
 'mitigation_available','inspection_sensitivity','inspection_specificity','inspection_cost','inspection_minutes'}
EVIDENCE_FIELDS={'question_id','source','finding','observed_hour','available_hour','sensitivity','specificity','parameter_basis','parameter_source','observation_model'}
OBSERVATION_MODEL={'defect_state':'fixed_binary_from_prior_through_prospective_inspection',
                   'inspection_channel':'conditionally_independent_given_defect'}


def number(value,name,probability=False):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError(name+' requires a finite, nonnegative parameter; unknown is not zero')
    if probability and value>1:raise ValueError(name+' must be a probability in[0,1]')
    return float(value)


def check_question(question):
    if set(question)!=QUESTION_FIELDS:raise ValueError('Risk-question fields do not match the declared contract')
    if question['parameter_basis'] not in {'synthetic_assumption','calibrated_estimate'}:raise ValueError('Parameter basis must be explicit')
    if not isinstance(question['parameter_source'],str) or not question['parameter_source'].strip():raise ValueError('Parameter provenance is required')
    if not question['id'] or not question['asset_id'] or not question['currency']:raise ValueError('Question identity and currency are required')
    if type(question['mitigation_available']) is not bool:raise ValueError('Declare available actions')
    for name in ['defect_probability','loss_event_probability_given_defect','mitigation_residual_fraction','inspection_sensitivity','inspection_specificity']:
        number(question[name],name,True)
    for name in ['horizon_hours','loss_given_event','mitigation_cost','inspection_cost','inspection_minutes']:
        number(question[name],name)
    if question['horizon_hours']<=0 or question['inspection_minutes']<=0:raise ValueError('Horizon and duration must be positive')


def posterior(probability,sensitivity,specificity,positive):
    q=number(probability,'defect probability',True);se=number(sensitivity,'sensitivity',True);sp=number(specificity,'specificity',True)
    likelihood=se if positive else 1-se
    false_likelihood=1-sp if positive else sp
    mass=likelihood*q+false_likelihood*(1-q)
    return (None if mass==0 else likelihood*q/mass),mass


def assess(question,evidence=(),as_of_hour=0):
    check_question(question);number(as_of_hour,'available time')
    evidence=list(evidence)
    if len(evidence)>1:raise ValueError('One observation per question in this prototype; correlated/joint evidence needs a likelihood model')
    q=float(question['defect_probability']);used=[];ignored=[]
    for record in evidence:
        if record.get('observation_model')!=OBSERVATION_MODEL:
            raise ValueError('Unsupported or missing observation model; declare fixed binary state and conditional independence or supply a different joint model outside v0.1')
        if set(record)!=EVIDENCE_FIELDS or record['source'] not in EVIDENCE_SOURCES:
            raise ValueError('Evidence must be a declared historical/manual/fixed/portable observation')
        if record['question_id']!=question['id']:raise ValueError('Evidence refers to another question')
        observed=number(record['observed_hour'],'observed hour');available=number(record['available_hour'],'available hour')
        if available<observed:raise ValueError('Evidence cannot be available before observation')
        if record['finding'] not in {'positive','negative','inconclusive'}:raise ValueError('Unknown finding')
        if record['parameter_basis'] not in {'synthetic_assumption','calibrated_estimate'}:raise ValueError('Observation performance needs a basis')
        if not isinstance(record['parameter_source'],str) or not record['parameter_source'].strip():raise ValueError('Observation performance provenance is required')
        se=number(record['sensitivity'],'evidence sensitivity',True);sp=number(record['specificity'],'evidence specificity',True)
        if available>as_of_hour or record['finding']=='inconclusive':
            ignored.append({'source':record['source'],'reason':'not_available' if available>as_of_hour else 'inconclusive'});continue
        updated,_=posterior(q,se,sp,record['finding']=='positive')
        if updated is None:raise ValueError('Observation has zero likelihood under this model')
        q=updated;used.append(record['source'])
    conditional_loss=question['loss_event_probability_given_defect']*question['loss_given_event']

    def best_action(defect_probability):
        risk=defect_probability*conditional_loss
        if question['mitigation_available']:
            mitigated=question['mitigation_cost']+risk*question['mitigation_residual_fraction']
            if mitigated<risk:return 'mitigate',mitigated
        return 'no_mitigation',risk

    action_now,cost_without=best_action(q)
    branches=[];cost_after=question['inspection_cost']
    for positive in (True,False):
        belief,mass=posterior(q,question['inspection_sensitivity'],question['inspection_specificity'],positive)
        if belief is None:
            branches.append({'finding':'positive' if positive else 'negative','probability':0,'posterior_defect_probability':None,'action':None,'action_cost':0});continue
        action,cost=best_action(belief);cost_after+=mass*cost
        branches.append({'finding':'positive' if positive else 'negative','probability':mass,
                         'posterior_defect_probability':belief,'action':action,'action_cost':cost})
    return {'id':question['id'],'asset_id':question['asset_id'],'horizon_hours':question['horizon_hours'],
            'currency':question['currency'],'parameter_basis':question['parameter_basis'],'posterior_defect_probability':q,
            'parameter_source':question['parameter_source'],
            'expected_loss_without_mitigation':q*conditional_loss,'best_action_without_inspection':action_now,
            'best_cost_without_inspection':cost_without,'expected_total_cost_with_inspection':cost_after,
            'net_inspection_value':cost_without-cost_after,'inspection_minutes':question['inspection_minutes'],
            'evidence_used':used,'evidence_ignored':ignored,'branches':branches,
            'model_assumptions':{'defect_state':OBSERVATION_MODEL['defect_state'],
                                 'existing_and_prospective_observations':OBSERVATION_MODEL['inspection_channel'] if used else 'no_usable_existing_observation',
                                 'joint_model_basis':'DECLARED_ASSUMPTION_NOT_EMPIRICALLY_VERIFIED',
                                 'state_evolution_and_action_delays_modeled':False},
            'scope':'binary one-path decision model; does not aggregate overlapping facility losses or execute actions'}


def recommend(questions,evidence=(),as_of_hour=0,time_budget_minutes=120):
    number(time_budget_minutes,'time budget');number(as_of_hour,'available time')
    questions=list(questions);evidence=list(evidence)
    ids=[question['id'] for question in questions]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate risk question')
    if any(record.get('question_id') not in ids for record in evidence):raise ValueError('Unknown evidence target')
    if len({(q['currency'],q['horizon_hours']) for q in questions})>1:raise ValueError('Compare one currency and horizon at a time')
    rows=[assess(q,[e for e in evidence if e['question_id']==q['id']],as_of_hour) for q in questions]
    eligible=[row for row in rows if row['net_inspection_value']>0 and row['inspection_minutes']<=time_budget_minutes]
    selected=max(eligible,key=lambda row:(row['net_inspection_value'],-row['inspection_minutes'],row['id'])) if eligible else None
    return {'status':'METHOD_PROTOTYPE_NOT_FIELD_VALIDATED','assessments':rows,
            'time_budget_minutes':time_budget_minutes,
            'next_inspection':None if selected is None else selected['id'],
            'reason':'positive_net_value_within_budget' if selected else ('no_open_questions' if not rows else 'no_positive_feasible_inspection'),
            'direct_action_candidates':[row['id'] for row in rows if row['best_action_without_inspection']=='mitigate'],
            'default_tour_created':False,'automatic_equipment_actions':False,'requires_full_realtime_telemetry':False,
            'selection_scope':'single next inspection by net value; not an optimal multi-task schedule'}
