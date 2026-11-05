"""Bounded one-observation planning adaptation, never an actual-state oracle."""
from copy import deepcopy
from fractions import Fraction
from .action_value import assess_action_value
from .evidence_ledger import _fields,_require,_text

OPTION_FIELDS={'belief_model','catalog','preparation_requests','value_model','bindings','unknown_inspection_policy'}
BIND_FIELDS={'question_id','inspection_candidate_id','intervention_candidate_id','source_note'}

def validate_execution_bindings(policy,inspection_program):
    """Bind known work/report timing and reference report law to actual interfaces."""
    options=policy['options'];candidates={c['id']:c for c in policy['candidates']}
    locals={q['question_id']:q for q in options['value_model']['question_models']}
    _require(inspection_program is not None,'Lookahead inspection plans need actual declared measurement bindings')
    bindings={b['task_id']:b for b in inspection_program['profile']['bindings']}
    models={m['model']['id']:m for m in inspection_program['profile']['nonfixed_profile']['models']}
    belief=options['belief_model'];reference_belief=belief['variants'][0]
    outcomes=options['catalog']['outcomes']
    for mapping in options['bindings']:
        local=locals[mapping['question_id']]
        for stage,key in (('inspection','inspection_candidate_id'),('intervention','intervention_candidate_id')):
            candidate=candidates[mapping[key]];task=candidate['task']
            _require(local[stage]['work_s']==policy['workforce_profile']['work_times_s'][task['work_interface_id']],
                'Forecast professional work duration differs from the declared actual crew interface')
            if policy['schema']=='aegisdc-dispatch-policy-program-v3':
                _require(local[stage]['cost']==candidate['issue_cost'],'Forecast and common task issue costs differ')
        task=candidates[mapping['inspection_candidate_id']]['task'];binding=bindings.get(task['id'])
        _require(binding is not None,'Forecast first inspection must produce a declared actual observation')
        _require(local['inspection']['report_latency_s']==binding['arrival_latency_s'],
            'Forecast report latency differs from its actual observation channel')
        measured=models[binding['model_id']]
        channels=[c for c in belief['channels'] if all(c[k]==measured[k] for k in ('source_id','target_id','observable_id'))]
        _require(len(channels)==1,'Actual lookahead inspection requires one declared belief update channel')
        channel=channels[0];reference_value=local['variants'][0]
        expected=[sum(Fraction(str(o['conditional_probability'][h['id']]))*Fraction(str(reference_value['positive_likelihood'][o['id']]))
            for o in outcomes) for h in belief['hypotheses']]
        actual=list(map(lambda x:Fraction(str(x)),reference_belief['positive_likelihood'][channel['id']]))
        _require(expected==actual,'Prospective reference report law differs from the arrived-evidence belief channel')

def evaluate(frame,options,candidates,audits):
    _fields(options,OPTION_FIELDS,'One-observation policy options')
    _require(frame['requests']==options['preparation_requests'],'Use the same public planning requests')
    _require(options['unknown_inspection_policy']=='fifo','Declare the shared unknown-inspection fallback')
    model=deepcopy(options['value_model'])
    for local in model['question_models']:
        local['action_on_positive']=local['action_on_negative']='minimum_service_deficit'
    values=assess_action_value(frame,options['belief_model'],options['catalog'],model)
    locals={row['question_id']:row for row in model['question_models']}
    requests={r['id']:r for r in frame['requests']}
    questions={q['id']:q for q in values['risk']['questions']}
    _require(type(options['bindings']) is list,'Declare finite forecast-to-work bindings')
    bindings={};bound_ids=set()
    for binding in options['bindings']:
        _fields(binding,BIND_FIELDS,'Forecast-to-work binding');q=binding['question_id']
        for key in ('question_id','inspection_candidate_id','intervention_candidate_id'):_text(binding[key],'Forecast binding '+key)
        _text(binding['source_note'],'Forecast binding provenance')
        _require(q in locals and q not in bindings,'Unknown/repeated value question binding')
        local=locals[q];qa=questions[q]
        for key,kind in (('inspection_candidate_id','inspect'),('intervention_candidate_id','intervene')):
            candidate=candidates.get(binding[key])
            _require(candidate is not None and candidate['kind']==kind and candidate['question_id']==q,
                'Forecast option must bind a same-question declared work kind')
            task=candidate['task'];role='inspector_id' if kind=='inspect' else 'intervenor_id'
            _require(local[role] in {r['worker_id'] for r in task['crew']}
                and task['tool_carrier_id']==local[role],'Forecast actor differs from actual work intention')
            if kind=='inspect':
                option=next(o for o in qa['options'] if o['id']==local['inspection_option_id']);request=requests[option['request_id']]
                _require(task['target_id']==request['target_id'] and task['work_interface_id']==request['work_interface_id'],
                    'Forecast inspection target/capability differs from its work intention')
            else:
                option=next(o for o in qa['options'] if o['id']==local['intervention_option_id'])
                _require(task['target_id']==option['target_id'] and task['work_interface_id']==option['capability_interface_id'],
                    'Forecast intervention target/capability differs from its work intention')
            _require(candidate['id'] not in bound_ids,'A task cannot stand for multiple forecast actions')
            bound_ids.add(candidate['id'])
        bindings[q]=binding
    _require(set(bindings)==set(locals),'Bind every declared finite value question')
    by_id={r['candidate_id']:r for r in audits};plans=[];choices=[];branches=0
    for value in values['question_values']:
        q=value['question_id'];binding=bindings[q];alternatives=[]
        for alternative in value['alternatives']:
            kind=alternative['kind'];candidate_id=(binding['inspection_candidate_id'] if kind=='inspect_then_act' else
                binding['intervention_candidate_id'] if kind=='direct_intervention' else None)
            branches+=len(alternative['branches'])
            allowed=alternative['eligible_for_planning'] is True and (candidate_id is None or by_id[candidate_id]['eligible'])
            # A branch plan cannot reserve a continuation which the shared public
            # resource book already knows to be unavailable at this decision.
            if kind=='inspect_then_act' and any(b['action']=='intervene' and b['probability']>0 for b in alternative['branches']):
                allowed=allowed and by_id[binding['intervention_candidate_id']]['eligible']
            score=alternative['expected']['service_deficit_time_s']['value']
            alternatives.append(dict(kind=kind,candidate_id=candidate_id,eligible=allowed,
                expected_service_deficit_s=score,planning_reasons=alternative['planning_reasons']))
            if allowed and score is not None:
                row=(score,alternative['expected']['person_s']['value'],alternative['expected']['cost']['value'],kind,q,candidate_id)
                choices.append(row)
        eligible=[a for a in alternatives if a['eligible'] and a['expected_service_deficit_s'] is not None]
        best=min(eligible,key=lambda a:(a['expected_service_deficit_s'],a['kind'])) if eligible else None
        plans.append(dict(question_id=q,best_alternative=best['kind'] if best else None,
            best_expected_service_deficit_s=best['expected_service_deficit_s'] if best else None,alternatives=alternatives))
    unmodeled={q['id'] for q in values['risk']['questions'] if q['quantification']=='UNMODELED'}
    # Unknown questions remain unknown. They share an explicit FIFO inspection
    # fallback, used only when no finite actionable plan beats its own deferral.
    best=min(choices,key=lambda row:row[:-1]) if choices else None
    selected=best[-1] if best else None;reason='ONE_OBSERVATION_FIRST_ACTION_ONLY' if selected else 'MODEL_PREFERS_DEFER'
    if selected is None:
        fallback=sorted((a for a in audits if a['eligible'] and a['kind']=='inspect' and a['question_id'] in unmodeled),
            key=lambda a:(a['available_at_s'],a['candidate_id']))
        if fallback:selected=fallback[0]['candidate_id'];reason='EXPLICIT_UNKNOWN_INSPECTION_FIFO_FALLBACK'
    for audit in audits:
        if audit['candidate_id'] not in bound_ids and audit['question_id'] not in unmodeled:
            audit['reasons'].append('NO_DECLARED_FINITE_VALUE_BINDING');audit['eligible']=False
        audit['forecast_selected']=audit['candidate_id']==selected
    return selected,dict(reason=reason,model_evaluations=dict(risk=0,action_value=1),unmodeled_question_ids=sorted(unmodeled),
        forecast_plans=plans,forecast_branch_count=branches,forecast_window_s=[frame['as_of_s'],frame['as_of_s']+options['catalog']['horizon_s']],
        forecast_scope='SAME_CATALOG_DEMAND_JOINT_OUTCOME_AND_HORIZON_SINGLE_FIRST_ACTION_NO_ADDITION',
        forecast_belief=values['risk']['belief'],forecast_is_actual_observation=False,
        adaptation='BOUNDED_ONE_OBSERVATION_LOOKAHEAD_NOT_LIFECYCLE_OPTIMALITY')
