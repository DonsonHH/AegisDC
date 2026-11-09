"""Private event truth and fixed-reference confirmation denominators after a run."""
from copy import deepcopy
from fractions import Fraction

from patrol_rsi.contracts import digest
from .evidence_ledger import _fields, _finite, _plain_json, _registry, _require, _text
from .nonfixed_evidence import SIGNALS

PROGRAM_FIELDS={'schema','id','facility_id','basis','time_unit','diagnostic_profile_id','reference','events','source_note'}
EVENT_FIELDS={'id','condition_id','opened_at_s','truth','opportunity','source_note'}
OPPORTUNITY_FIELDS={'reference_id','status','inspection_task_id','starts_at_s','earliest_report_at_s','deadline_s','source_note'}


def validate_diagnostic_evaluation(program,facility_id,duration_s,dispatch,scenario,boundary_events):
    _plain_json(program);_fields(program,PROGRAM_FIELDS,'Private diagnostic evaluation')
    version2=program['schema']=='aegisdc-business-diagnostic-evaluation-v2'
    _require(program['schema'] in ('aegisdc-business-diagnostic-evaluation-v1','aegisdc-business-diagnostic-evaluation-v2')
             and program['basis']=='synthetic_assumption'
             and program['time_unit']=='s' and program['facility_id']==facility_id,'Diagnostic evaluation identity/basis differs')
    for name in ('id','source_note'):_text(program[name],'Diagnostic evaluation '+name)
    _plain_json(dispatch)
    _require(type(dispatch) is dict and dispatch.get('schema')=='aegisdc-policy-run-program-v4'
             and type(dispatch.get('diagnostic_profile')) is dict,'Declare a separate public diagnostic profile')
    profile=dispatch['diagnostic_profile']
    _require(profile.get('id')==program['diagnostic_profile_id'],'Private event/public diagnostic identity differs')
    rules=_registry(profile['rules'],'Public condition rule')
    inspection=dispatch['inspection_program']['profile'] if dispatch['inspection_program'] is not None else None
    _require(type(scenario) is dict and type(boundary_events) in (list,tuple),'Bind the actual finite scenario and boundary inputs')
    values=dict(scenario_sha256=scenario,boundary_events_sha256=list(boundary_events),
        nominal_knowledge_sha256=dispatch['nominal_knowledge'],ledger_sha256=dispatch['evidence_ledger'],
        workforce_profile_sha256=dispatch['policy_program']['workforce_profile'],inspection_profile_sha256=inspection)
    reference=program['reference'];_fields(reference,{'id','source_note'}|set(values),'Reference inspection envelope')
    for name in ('id','source_note'):_text(reference[name],'Reference '+name)
    for name,value in values.items():
        _require(reference[name]==digest(value),'Fixed reference differs from actual input: '+name)
    events=_registry(program['events'],'Diagnostic event');_require(0<len(events)<=1024,'Declare one to1024 diagnostic events')
    seen=set();points={0,duration_s,*dispatch['decision_times_s']}
    for event in events.values():
        _fields(event,EVENT_FIELDS,'Diagnostic event');_text(event['source_note'],'Event basis')
        _finite(event['opened_at_s'],'Event opening')
        _require(0<=event['opened_at_s']<=duration_s and event['opened_at_s'] in points,'Event opening needs an actual declared snapshot instant')
        rule=rules.get(event['condition_id']);_require(rule is not None,'Unknown event condition')
        truth=event['truth'];_require(type(truth) is dict,'Declare modeled or unmodeled truth')
        if truth.get('kind')=='UNMODELED':
            _fields(truth,{'kind','source_note'},'Unmodeled truth')
        else:
            _fields(truth,{'kind','signal_id','target_id','unit','threshold','source_note'},'Private state predicate')
            _finite(truth['threshold'],'Private truth threshold')
            signal=SIGNALS.get(truth['signal_id'])
            _require(truth['kind']=='SIGNAL_BELOW' and signal is not None and signal[:2]==(truth['target_id'],truth['unit'])
                     and truth['target_id']==rule['target_id'] and truth['unit']==rule['unit'],'Truth signal/target/unit outside the declared condition')
        _text(truth['source_note'],'Private truth basis')
        opportunity=event['opportunity'];_fields(opportunity,OPPORTUNITY_FIELDS,'Reference opportunity')
        _text(opportunity['source_note'],'Opportunity basis')
        _require(opportunity['reference_id']==reference['id'] and opportunity['status'] in {'ELIGIBLE','UNAVAILABLE','UNMODELED'},'Unknown reference opportunity')
        if version2 and opportunity['status']=='UNMODELED':
            for name in ('starts_at_s','deadline_s'):_finite(opportunity[name],'Opportunity '+name)
            _require(opportunity['earliest_report_at_s'] is None,'Unmodeled reference time must remain null')
            _require(event['opened_at_s']<=opportunity['starts_at_s']<=opportunity['deadline_s'],
                     'Reference window clock order differs')
        else:
            for name in ('starts_at_s','earliest_report_at_s','deadline_s'):_finite(opportunity[name],'Opportunity '+name)
            _require(event['opened_at_s']<=opportunity['starts_at_s']<=opportunity['earliest_report_at_s']<=opportunity['deadline_s'],
                     'Reference opportunity clock order differs')
        if version2 and opportunity['inspection_task_id'] is not None:
            _text(opportunity['inspection_task_id'],'Reference inspection task')
            _require(inspection is not None and any(row['task_id']==opportunity['inspection_task_id'] for row in inspection['bindings']),
                     'Named reference inspection must bind an actual declared task')
        key=(event['condition_id'],event['opened_at_s'],opportunity['deadline_s'])
        _require(key not in seen,'Do not duplicate an event under another ID');seen.add(key)
        if opportunity['status']=='ELIGIBLE':
            _require(inspection is not None and any(row['task_id']==opportunity['inspection_task_id'] for row in inspection['bindings']),
                     'Eligible inspection reference must bind an actual declared task')
    return deepcopy(program)


def _truth_at(result,truth,time_s):
    if truth['kind']=='UNMODELED':return 'UNKNOWN',None
    selected=[row for row in result['trace'] if row['time_s']==time_s]
    _require(len(selected)==1,'No exact private truth snapshot; interpolation/future substitution is forbidden')
    value=selected[0]['domains']
    for part in SIGNALS[truth['signal_id']][2]:value=value[part]
    _finite(value,'Private truth scalar')
    return ('FAULT' if Fraction(value)<Fraction(truth['threshold']) else 'NORMAL'),value


def evaluate_diagnostic_events(result,program):
    end=result['summary']['duration_s'];events=[]
    counts=dict(events_total=len(program['events']),truth_fault=0,truth_normal=0,truth_unknown=0,
        eligible_fault_matured=0,timely_confirmed_fault=0,missed_fault_confirmation=0,
        normal_matured=0,false_positive_state_events=0,window_censored=0,reference_unavailable=0,reference_unmodeled=0)
    for event in program['events']:
        opportunity=event['opportunity'];deadline=opportunity['deadline_s'];initial,value=_truth_at(result,event['truth'],event['opened_at_s'])
        censored=end<deadline;counts['truth_'+initial.lower()]+=1;counts['window_censored']+=censored
        counts['reference_unavailable']+=opportunity['status']=='UNAVAILABLE';counts['reference_unmodeled']+=opportunity['status']=='UNMODELED'
        assessments=[];confirmed=[];wrong_abnormal=[];wrong_normal=[]
        for decision in result.get('policy_public_decisions',[]):
            public=decision.get('condition_assessment')
            if public is None:continue
            for row in public['conditions']:
                if row['condition_id']!=event['condition_id'] or row['available_at_s']<event['opened_at_s']:continue
                observed=row['observed_at_s'];ground=None
                in_window=observed is not None and event['opened_at_s']<=observed<=deadline
                if in_window and row['status']!='UNKNOWN':ground,_=_truth_at(result,event['truth'],observed)
                assessments.append(dict(available_at_s=row['available_at_s'],observed_at_s=observed,
                    public_status=row['status'],truth_at_observation=ground,observation_in_event_window=in_window,
                    supporting_record_ids=deepcopy(row['supporting_record_ids']),external_context_record_ids=deepcopy(row['external_context_record_ids'])))
                if in_window and ground=='FAULT' and row['status']=='ABNORMAL':confirmed.append(row['available_at_s'])
                if in_window and row['available_at_s']<=deadline:
                    if ground=='NORMAL' and row['status']=='ABNORMAL':wrong_abnormal.append(row['available_at_s'])
                    if ground=='FAULT' and row['status']=='NORMAL':wrong_normal.append(row['available_at_s'])
        first=min(confirmed) if confirmed else None;timely=first is not None and first<=deadline
        eligible=initial=='FAULT' and opportunity['status']=='ELIGIBLE' and not censored
        counts['eligible_fault_matured']+=eligible;counts['timely_confirmed_fault']+=eligible and timely
        counts['missed_fault_confirmation']+=eligible and not timely
        normal=initial=='NORMAL' and not censored;counts['normal_matured']+=normal
        counts['false_positive_state_events']+=normal and bool(wrong_abnormal)
        outcome=('UNKNOWN_TRUTH' if initial=='UNKNOWN' else 'WINDOW_CENSORED' if censored else
            'TIMELY_CONFIRMED' if initial=='FAULT' and timely else 'LATE_CONFIRMATION' if initial=='FAULT' and first is not None else
            'NO_TIMELY_CONFIRMATION' if initial=='FAULT' else 'WRONG_ABNORMAL_STATE' if wrong_abnormal else 'NO_WRONG_ABNORMAL_STATE')
        events.append(dict(id=event['id'],condition_id=event['condition_id'],opened_at_s=event['opened_at_s'],
            initial_truth=initial,initial_private_value=value,reference_opportunity=deepcopy(opportunity),
            deadline_right_censored=censored,first_corroborated_fault_report_at_s=first,timely_outcome=outcome,
            wrong_abnormal_state_observed=bool(wrong_abnormal),wrong_normal_state_observed=bool(wrong_normal),assessments=assessments))
    def rate(numerator,denominator,reason):
        return dict(numerator=numerator,denominator=denominator,value=numerator/denominator if denominator else None,
                    unit='1',unavailable_reason=None if denominator else reason)
    return dict(schema='aegisdc-business-diagnostic-result-v2' if program['schema']=='aegisdc-business-diagnostic-evaluation-v2'
                       else 'aegisdc-business-diagnostic-result-v1',program_id=program['id'],facility_id=result['facility_id'],
        visibility='PRIVATE_EVALUATOR_ONLY',basis=program['basis'],time_unit='s',window_end_s=end,
        execution_code_identity=deepcopy(result['code_identity']),reference=deepcopy(program['reference']),events=events,counts=counts,
        rates=dict(missed_confirmation=rate(counts['missed_fault_confirmation'],counts['eligible_fault_matured'],'NO_MATURE_ELIGIBLE_INITIAL_FAULT_EVENTS'),
                   false_positive_state_events=rate(counts['false_positive_state_events'],counts['normal_matured'],'NO_MATURE_KNOWN_NORMAL_EVENTS')),
        scope='DECLARED_INITIAL_STATE_EVENTS_AND_REFERENCE_INSPECTION_NOT_ROOT_CAUSE_OR_CAUSAL_SERVICE_GAIN',
        prevention_effect=dict(status='NOT_IDENTIFIED_NO_PAIRED_COUNTERFACTUAL',value=None),
        field_calibration='PENDING',new_research_trials=0,research_gain_claim='NOT_ESTABLISHED')
