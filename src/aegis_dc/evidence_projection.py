"""Public symbolic evidence admission; no prospective measured values are made."""
from copy import deepcopy
from fractions import Fraction

from .belief import infer_belief
from .decision_view import DecisionGateway
from .evidence_ledger import _fields,_require,_text,_finite,RECORD_FIELDS
from .inspection_execution import PROFILE_FIELDS,BINDING_FIELDS
from .nonfixed_evidence import validate_nonfixed_profile,_arrival
from .sensor_channels import validate_channel_profile,_number

FIELDS={'schema','basis','source_note','inspection_profile','background_sensor_profile','context_assumption'}


def _shared_registry(frame,registry,label):
    static=frame['evidence']['static_knowledge']
    _require(registry['facility_id']==frame['facility_id'] and set(registry['entity_ids'])==set(static['entity_ids']),
        label+' and public evidence entity identities differ')
    for field in ('sources','observables'):
        current={row['id']:row for row in static[field]}
        _require(all(row['id'] in current and row==current[row['id']] for row in registry[field]),label+' registry differs from public frame')


def validate_projection(frame,projection):
    _fields(projection,FIELDS,'Public evidence projection')
    _require(projection['schema']=='aegisdc-evidence-projection-v1' and projection['basis']=='synthetic_assumption'
        and projection['context_assumption']=='NO_UNSCHEDULED_RECORD_ARRIVALS_UNTIL_PROJECTED_REPORT','Declare the finite projection context assumption')
    _text(projection['source_note'],'Projection assumption provenance')
    profile=projection['inspection_profile'];_fields(profile,PROFILE_FIELDS,'Projection public inspection profile')
    _require(profile['schema']=='aegisdc-inspection-profile-v1' and profile['basis']=='synthetic_assumption'
        and profile['facility_id']==frame['facility_id'],'Projection inspection identity differs')
    for key in ('id','source_note'):_text(profile[key],'Projection inspection '+key)
    validated=validate_nonfixed_profile(profile['nonfixed_profile'])
    _shared_registry(frame,validated['registry'],'Projection inspection')
    models={row['model']['id'] for row in validated['models']};tasks=set();records=set()
    _require(type(profile['bindings']) is list,'Declare finite public inspection bindings')
    for binding in profile['bindings']:
        _fields(binding,BINDING_FIELDS,'Projection inspection binding')
        for key in ('task_id','model_id','tool_id','qualification_id','record_id'):_text(binding[key],'Projection '+key)
        _require(binding['task_id'] not in tasks and binding['record_id'] not in records and binding['model_id'] in models,'Unknown/repeated projection binding')
        tasks.add(binding['task_id']);records.add(binding['record_id'])
        for key in ('minimum_work_s','arrival_latency_s','validity_s','confirmation_threshold'):_finite(binding[key],'Projection '+key)
        _require(binding['minimum_work_s']>0 and binding['arrival_latency_s']>=0 and binding['validity_s']>0,'Invalid projection work/latency/validity')
        bounds=binding['condition_range'];_require(type(bounds) is list and len(bounds)==2,'Declare projection suitability range')
        for bound in bounds:_finite(bound,'Projection suitability endpoint')
        _require(bounds[0]<=bounds[1],'Reversed projection suitability range')
        _fields(binding['provenance'],{'origin_id','copied_from_record_id'},'Projection provenance')
        _text(binding['provenance']['origin_id'],'Projection origin')
        if binding['provenance']['copied_from_record_id'] is not None:_text(binding['provenance']['copied_from_record_id'],'Projection copy parent')
    if projection['background_sensor_profile'] is not None:
        background=validate_channel_profile(projection['background_sensor_profile'])
        _shared_registry(frame,background['ledger'],'Projection background')


def _projected_frame(frame,arrival):
    static=frame['evidence']['static_knowledge']
    ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
        basis='synthetic_assumption',time_unit='s',**deepcopy(static),
        records=[{k:deepcopy(r[k]) for k in RECORD_FIELDS} for r in frame['evidence']['records']])
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id=frame['plan_id']+'-counterfactual-context',basis='synthetic_assumption',
        time_unit='s',decision_times_s=[arrival],requests=deepcopy(frame['requests']))
    return DecisionGateway(frame['nominal_knowledge'],ledger,plan).next_frame()


def _pending_background(profile,now,arrival):
    if profile is None:return False
    channels=profile['channels']
    for measurement in profile['measurements']:
        if not measurement['enabled']:continue
        # A finite public schedule, including pre-now polls whose reports are pending.
        count=max(0,int((Fraction(arrival)-Fraction(measurement['phase_s']))//Fraction(measurement['period_s']))+2)
        if count>10000:return True
        for index in range(count):
            poll=_number(Fraction(measurement['phase_s'])+index*Fraction(measurement['period_s']))
            if poll>arrival:break
            for channel in channels:
                if channel['measurement_id']==measurement['id']:
                    delivered=_number(Fraction(poll)+Fraction(channel['delay_s']),upward=True)
                    if now<delivered<=arrival:return True
    return False


def _factor_signature(belief):
    return sorted((r['record_id'],r['observation_epoch'],r['channel_id'],r['positive'])
        for r in belief['record_audit'] if r['disposition']=='used')


def _pending_inspections(frame,candidates,bindings,history):
    visible={r['id'] for r in frame['evidence']['records']}
    stopped={r['task_id'] for r in history['work_feedback'] if r['status'] in {'aborted','rejected'}}
    pending=[]
    for issued in history['issued']:
        candidate=candidates[issued['candidate_id']]
        if candidate['kind']!='inspect':continue
        task=candidate['task']['id'];binding=bindings.get(task)
        if task not in stopped and (binding is None or binding['record_id'] not in visible):pending.append(task)
    return sorted(pending)


def project_inspections(frame,options,candidates,projection,history):
    validate_projection(frame,projection)
    profile=projection['inspection_profile'];bindings={b['task_id']:b for b in profile['bindings']}
    models={m['model']['id']:m for m in profile['nonfixed_profile']['models']}
    pending_tasks=_pending_inspections(frame,candidates,bindings,history)
    belief_model=options['belief_model'];channels=belief_model['channels'];priority={c['id']:i for i,c in enumerate(channels)}
    independent={frozenset(pair) for pair in belief_model['independent_pairs']}
    current=infer_belief(frame,belief_model);calls=1;current_signature=_factor_signature(current)
    sources={s['id']:s for s in frame['evidence']['static_knowledge']['sources']}
    locals={m['question_id']:m for m in options['value_model']['question_models']};modes={};audits=[]
    for mapping in options['bindings']:
        q=mapping['question_id'];local=locals[q];candidate=candidates[mapping['inspection_candidate_id']]
        binding=bindings.get(candidate['task']['id']);_require(binding is not None,'Projection task lacks declared inspection binding')
        model=models[binding['model_id']];now=frame['as_of_s'];work_started=now
        for key in ('travel_s','wait_s'):work_started+=local['inspection'][key]
        observed=work_started+local['inspection']['work_s']
        arrival=_arrival(observed,binding['arrival_latency_s']);valid_until=_arrival(observed,binding['validity_s'])
        reasons=[];classification='UNMODELED';covered=['positive','negative','threshold_straddled','missing'] if model['model']['kind']=='numeric' else []
        audit=dict(question_id=q,classification=classification,predicted_work_started_at_s=work_started,
            predicted_observed_at_s=observed,predicted_arrived_at_s=arrival,
            predicted_valid_until_s=valid_until,covered_report_classes=covered,context_assumption=projection['context_assumption'],
            unchanged_factor_record_ids=[],marginalization=None,pending_inspection_task_ids=pending_tasks,
            proof='SUFFICIENT_STRUCTURAL_CONDITION_NOT_A_NECESSARY_INFORMATION_TEST')
        scope=belief_model['scope'];epoch=lambda t:(Fraction(t)-Fraction(scope['starts_at_s']))//Fraction(scope['epoch_s'])
        if observed<=now or observed<=work_started:reasons.append('PROJECTED_MEASUREMENT_CLOCK_NOT_ADVANCING')
        if Fraction(local['inspection']['work_s'])<Fraction(binding['minimum_work_s']) or observed<work_started+binding['minimum_work_s']:
            reasons.append('DECLARED_WORK_BELOW_MEASUREMENT_MINIMUM')
        if epoch(now)!=epoch(arrival):reasons.append('CROSS_EPOCH_PROJECTION_UNMODELED')
        if _pending_background(projection['background_sensor_profile'],now,arrival):reasons.append('BACKGROUND_ARRIVAL_JOINT_LAW_UNMODELED')
        if pending_tasks:reasons.append('PENDING_INSPECTION_RECORD_JOINT_LAW_UNMODELED')
        if model['model']['kind']!='numeric':reasons.append('PRODUCER_CLASS_PARTITION_UNMODELED')
        prospective=next((c for c in channels if all(c[k]==model[k] for k in ('source_id','target_id','observable_id'))),None)
        _require(prospective is not None,'Projection measurement lacks a declared belief channel')
        if prospective['positive_when']=='true':reasons.append('NUMERIC_PRODUCER_BOOLEAN_CHANNEL_MISMATCH')
        provenance=binding['provenance'];records=frame['evidence']['records']
        if provenance['copied_from_record_id'] is not None or any(r['provenance']['origin_id']==provenance['origin_id']
            or r['provenance']['copied_from_record_id']==binding['record_id'] for r in records):reasons.append('PROSPECTIVE_PROVENANCE_INTERACTION_UNMODELED')
        if any(r['id']==binding['record_id'] or all(r[k]==model[k] for k in ('source_id','target_id','observable_id')) for r in records):
            reasons.append('PROSPECTIVE_BINDING_CONFLICT_OR_REPLACEMENT_UNMODELED')
        group=sources[model['source_id']]['dependency_group']
        if group is not None and any(sources[r['source_id']]['dependency_group']==group for r in records):
            reasons.append('PROSPECTIVE_COMPONENT_INTERACTION_UNMODELED')
        if not reasons:
            future=infer_belief(_projected_frame(frame,arrival),belief_model);calls+=1
            signature=_factor_signature(future)
            if signature!=current_signature:reasons.append('PROJECTED_BACKGROUND_FACTORS_CHANGED')
            else:
                # No numeric representative values are sampled. All nonmissing
                # classes either never enter selection or follow the same lower
                # priority branch. Disjoint binding/provenance prevents changes
                # to any old factor, even for arbitrary finite reported values.
                selected={r['record_id']:r for r in future['record_audit'] if r['disposition']=='used'}
                visible={r['id']:r for r in _projected_frame(frame,arrival)['evidence']['records']}
                blocked=any(visible[key]['availability']=='current' and priority[row['channel_id']]<priority[prospective['id']]
                    and frozenset((row['channel_id'],prospective['id'])) not in independent for key,row in selected.items())
                if arrival>=valid_until or blocked:
                    classification='NON_ADAPTIVE_UNDER_DECLARED_UPDATER'
                    audit.update(unchanged_factor_record_ids=[r[0] for r in signature],
                        marginalization='SUM_ORIGINAL_REPORT_MASS_PER_JOINT_OUTCOME_EQUALS_ONE',unchanged_factor_signature=[list(r) for r in signature])
                else:reasons.append('INFORMATIVE_OR_RESULT_DEPENDENT_CONTEXT_LAW_UNMODELED')
        modes[q]=classification;audit.update(classification=classification,reasons=sorted(set(reasons)));audits.append(audit)
    return modes,audits,calls
