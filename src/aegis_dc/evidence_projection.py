"""Public symbolic evidence admission; no prospective measured values are made."""
from copy import deepcopy
from fractions import Fraction

from .belief import infer_belief,exact_belief_context
from .decision_view import DecisionGateway
from .evidence_ledger import _fields,_require,_text,_finite,RECORD_FIELDS
from .inspection_execution import PROFILE_FIELDS,BINDING_FIELDS
from .nonfixed_evidence import validate_nonfixed_profile,_arrival
from .sensor_channels import validate_channel_profile,_number
from .action_value import SERIALIZED_MASS_BASIS,EXACT_MASS_BASIS

FIELDS={'schema','basis','source_note','inspection_profile','background_sensor_profile','context_assumption'}
SUPPORT_FIELDS={'question_id','inspection_task_id','record_id','assumption','source_note'}
CERTAIN_SUPPORT='EVERY_MODELED_OUTCOME_COMPLETES_SUITABLY_AT_DECLARED_TIME_WITH_DECISIVE_BINARY_REPORT'


def _shared_registry(frame,registry,label):
    static=frame['evidence']['static_knowledge']
    _require(registry['facility_id']==frame['facility_id'] and set(registry['entity_ids'])==set(static['entity_ids']),
        label+' and public evidence entity identities differ')
    for field in ('sources','observables'):
        current={row['id']:row for row in static[field]}
        _require(all(row['id'] in current and row==current[row['id']] for row in registry[field]),label+' registry differs from public frame')


def validate_projection(frame,projection):
    version3=type(projection) is dict and projection.get('schema')=='aegisdc-evidence-projection-v3'
    version2=type(projection) is dict and projection.get('schema') in ('aegisdc-evidence-projection-v2','aegisdc-evidence-projection-v3')
    _fields(projection,FIELDS|({'report_class_support'} if version2 else set())|({'valuation_mass_basis'} if version3 else set()),'Public evidence projection')
    _text(projection['schema'],'Projection schema')
    _require(projection['schema'] in {'aegisdc-evidence-projection-v1','aegisdc-evidence-projection-v2','aegisdc-evidence-projection-v3'} and projection['basis']=='synthetic_assumption'
        and projection['context_assumption']=='NO_UNSCHEDULED_RECORD_ARRIVALS_UNTIL_PROJECTED_REPORT','Declare the finite projection context assumption')
    _text(projection['source_note'],'Projection assumption provenance')
    if version3:
        _text(projection['valuation_mass_basis'],'Projection valuation mass basis')
        _require(projection['valuation_mass_basis']==EXACT_MASS_BASIS,'Projection-v3 requires the shared exact public valuation mass basis')
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
    if version2:
        _require(type(projection['report_class_support']) is list,'Declare finite report-support assumptions')
        questions=set();supported_tasks=set()
        for row in projection['report_class_support']:
            _fields(row,SUPPORT_FIELDS,'Report-support assumption')
            for key in SUPPORT_FIELDS:_text(row[key],'Report-support '+key)
            _require(row['question_id'] not in questions and row['inspection_task_id'] not in supported_tasks
                and row['inspection_task_id'] in tasks and row['record_id'] in records and row['assumption']==CERTAIN_SUPPORT,
                'Report support must bind a unique declared inspection under the supported per-world domain')
            binding=next(b for b in profile['bindings'] if b['task_id']==row['inspection_task_id'])
            _require(binding['record_id']==row['record_id'],'Report-support record differs from its inspection binding')
            questions.add(row['question_id']);supported_tasks.add(row['inspection_task_id'])


def _projected_frame(frame,arrival):
    static=frame['evidence']['static_knowledge']
    ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],
        basis='synthetic_assumption',time_unit='s',**deepcopy(static),
        records=[{k:deepcopy(r[k]) for k in RECORD_FIELDS} for r in frame['evidence']['records']])
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id=frame['plan_id']+'-counterfactual-context',basis='synthetic_assumption',
        time_unit='s',decision_times_s=[arrival],requests=deepcopy(frame['requests']))
    return DecisionGateway(frame['nominal_knowledge'],ledger,plan).next_frame()


def validate_value_projection_bindings(options,candidates,projection):
    """The baseline and candidate validate the same public support-to-value map."""
    mappings={m['question_id']:m for m in options['bindings']}
    profile_bindings={b['task_id']:b for b in projection['inspection_profile']['bindings']}
    for row in projection.get('report_class_support',[]):
        _require(row['question_id'] in mappings,'Report support references an unknown value question')
        task=candidates[mappings[row['question_id']]['inspection_candidate_id']]['task']
        _require(row['inspection_task_id']==task['id'] and task['id'] in profile_bindings
            and row['record_id']==profile_bindings[task['id']]['record_id'],
            'Report support differs from the public value-to-work binding')


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


def _fractions(masses):
    return None if masses is None else {key:Fraction(*value) for key,value in masses.items()}


def _outcomes(hypotheses,catalog):
    return {o['id']:sum(hypotheses[h]*Fraction(str(o['conditional_probability'][h])) for h in hypotheses)
        for o in catalog['outcomes']}


def _ratios(masses):
    return None if masses is None else {key:[value.numerator,value.denominator] for key,value in masses.items()}


def _informative_compatibility(frame,future,belief_model,current,catalog,local,binding,model,observed,arrival,valid_until,mass_basis):
    """Prove the finite updater and existing valuation use the same branch worlds."""
    initial=exact_belief_context(frame,belief_model)
    token=dict(schema='aegisdc-symbolic-report-token-v1',id=binding['record_id'],source_id=model['source_id'],target_id=model['target_id'],
        observable_id=model['observable_id'],unit=model['model']['unit'],observed_at_s=observed,arrived_at_s=arrival,
        valid_until_s=valid_until,provenance=deepcopy(binding['provenance']))
    branches={name:exact_belief_context(future,belief_model,symbolic_report=token,positive=positive)
        for name,positive in (('positive',True),('negative',False))}
    rows=[];all_matched=True
    for belief_id,exact in initial['posterior_mass_by_variant'].items():
        exact_hypotheses=_fractions(exact);serialized=current['posterior_by_variant'][belief_id]
        for variant in local['variants']:
            row=dict(belief_variant_id=belief_id,value_variant_id=variant['id'],status='MATCHED',branches={})
            if exact_hypotheses is None or serialized is None:
                row.update(status='UNMODELED',reason='CURRENT_BELIEF_MODEL_CONFLICT');all_matched=False;rows.append(row);continue
            exact_world=_outcomes(exact_hypotheses,catalog)
            total=sum(Fraction(str(p)) for p in serialized.values())
            represented_world=_outcomes({h:Fraction(str(p))/total for h,p in serialized.items()},catalog)
            valuation_world=exact_world if mass_basis==EXACT_MASS_BASIS else represented_world
            if valuation_world!=exact_world:
                row.update(status='UNMODELED',reason='VALUATION_REPRESENTATION_UNSUPPORTED',exact_current_outcome_mass=_ratios(exact_world),
                    valuation_current_outcome_mass=_ratios(valuation_world));all_matched=False;rows.append(row);continue
            if mass_basis==EXACT_MASS_BASIS:row.update(valuation_mass_basis=mass_basis,exact_current_outcome_mass=_ratios(exact_world),
                valuation_current_outcome_mass=_ratios(valuation_world))
            for name,positive in (('positive',True),('negative',False)):
                joint={o:p*(Fraction(str(variant['positive_likelihood'][o])) if positive else 1-Fraction(str(variant['positive_likelihood'][o])))
                    for o,p in valuation_world.items()}
                probability=sum(joint.values());projected_hypotheses=_fractions(branches[name]['posterior_mass_by_variant'][belief_id])
                expected={o:p/probability for o,p in joint.items()} if probability else None
                projected=_outcomes(projected_hypotheses,catalog) if projected_hypotheses is not None else None
                used=any(r[0]==binding['record_id'] for r in branches[name]['factor_signature'])
                matched=not probability or used and projected==expected
                row['branches'][name]=dict(status='ZERO_SUPPORT' if not probability else 'MATCHED' if matched else 'UNMODELED',
                    original_report_probability=[probability.numerator,probability.denominator],projected_outcome_mass=_ratios(projected),
                    original_joint_report_posterior=_ratios(expected),projected_factor_signature=branches[name]['factor_signature'])
                if not matched:row.update(status='UNMODELED',reason='IMPLEMENTATION_CONTEXT_OUTCOME_MASS_UNSUPPORTED');all_matched=False
            rows.append(row)
    return all_matched,rows,3


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
    support={r['question_id']:r for r in projection.get('report_class_support',[])};exact_calls=0
    _require(set(support)<=set(locals),'Report support references an unknown value question')
    for mapping in options['bindings']:
        q=mapping['question_id'];local=locals[q];candidate=candidates[mapping['inspection_candidate_id']]
        binding=bindings.get(candidate['task']['id']);_require(binding is not None,'Projection task lacks declared inspection binding')
        model=models[binding['model_id']];now=frame['as_of_s'];work_started=now
        declared_support=support.get(q)
        if declared_support is not None:
            _require(declared_support['inspection_task_id']==candidate['task']['id'] and declared_support['record_id']==binding['record_id'],
                'Report support differs from the forecast-to-work binding')
        for key in ('travel_s','wait_s'):work_started+=local['inspection'][key]
        observed=work_started+local['inspection']['work_s']
        arrival=_arrival(observed,binding['arrival_latency_s']);valid_until=_arrival(observed,binding['validity_s'])
        reasons=[];classification='UNMODELED';covered=['positive','negative','threshold_straddled','missing'] if model['model']['kind']=='numeric' else []
        audit=dict(question_id=q,classification=classification,predicted_work_started_at_s=work_started,
            predicted_observed_at_s=observed,predicted_arrived_at_s=arrival,
            predicted_valid_until_s=valid_until,covered_report_classes=covered,context_assumption=projection['context_assumption'],
            unchanged_factor_record_ids=[],marginalization=None,pending_inspection_task_ids=pending_tasks,
            proof='SUFFICIENT_STRUCTURAL_CONDITION_NOT_A_NECESSARY_INFORMATION_TEST')
        if declared_support is not None:audit.update(forecast_assumption=declared_support['assumption'],
            zero_forecast_mass_report_classes=['threshold_straddled','missing'])
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
            if signature==current_signature:
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
            else:reasons.append('PROJECTED_BACKGROUND_FACTORS_CHANGED')
            if classification=='UNMODELED' and declared_support is not None and arrival<valid_until:
                compatible,rows,count=_informative_compatibility(frame,_projected_frame(frame,arrival),belief_model,current,
                    options['catalog'],local,binding,model,observed,arrival,valid_until,projection.get('valuation_mass_basis',SERIALIZED_MASS_BASIS))
                exact_calls+=count;audit['compatibility_by_assumption']=rows
                if compatible:
                    classification='INFORMATIVE_COMPATIBLE_WITH_DECLARED_UPDATER';reasons=[]
                else:
                    reasons=[row['reason'] for row in rows if row['status']=='UNMODELED']
        modes[q]=classification;audit.update(classification=classification,reasons=sorted(set(reasons)));audits.append(audit)
    return modes,audits,dict(prospective_belief=calls,exact_belief_context=exact_calls)
