"""Declared risk/condition priority adaptation using arrived evidence only."""
from fractions import Fraction
from .evidence_ledger import _fields,_require,_finite,_strings
from .risk_scenarios import assess_risks

OPTION_FIELDS={'belief_model','catalog','preparation_requests','minimum_service_deficit_s','unknown_inspection_policy','conditions'}
CONDITION_FIELDS={'candidate_id','source_ids','target_id','observable_id','accepted_interval','not_before_s'}

def _condition(frame,condition):
    rows=[r for r in frame['evidence']['records'] if r['target_id']==condition['target_id']
        and r['observable_id']==condition['observable_id'] and r['observed_at_s']>=condition['not_before_s']
        and r['availability']=='current']
    current_ids={r['id'] for r in rows}
    disputed={identifier for issue in frame['evidence']['conflicts'] if set(issue['record_ids'])<=current_ids for identifier in issue['record_ids']}
    disputed|={identifier for issue in frame['evidence']['provenance_issues'] if set(issue['record_ids'])&current_ids for identifier in issue['record_ids']}
    support=[];blocking=[];low,high=map(Fraction,condition['accepted_interval'])
    for row in rows:
        if row['id'] in disputed:blocking.append(row['id']);continue
        if row['quality']['status']!='bounded':
            if row['source_id'] in condition['source_ids']:blocking.append(row['id'])
            continue
        a=Fraction(row['value'])-Fraction(row['quality']['error_bound']);b=Fraction(row['value'])+Fraction(row['quality']['error_bound'])
        if b<low or a>high:blocking.append(row['id']);continue
        if row['source_id'] in condition['source_ids']:
            if a<low or b>high:blocking.append(row['id'])
            elif row['provenance']['copied_from_record_id'] is None:support.append(row['id'])
    return sorted(support),sorted(blocking)

def evaluate(frame,options,candidates,audits):
    _fields(options,OPTION_FIELDS,'Risk/condition policy options')
    _require(frame['requests']==options['preparation_requests'],'Use the same declared public preparation requests in the current frame')
    _finite(options['minimum_service_deficit_s'],'Risk trigger in service-deficit seconds')
    _require(options['minimum_service_deficit_s']>=0 and options['unknown_inspection_policy']=='fifo',
        'Declare a nonnegative trigger and explicit unknown inspection fallback')
    risk=assess_risks(frame,options['belief_model'],options['catalog'])
    questions={q['id']:q for q in risk['questions']};conditions={}
    _require(type(options['conditions']) is list,'Declare condition-maintenance bindings')
    sources={s['id']:s for s in frame['evidence']['static_knowledge']['sources']}
    observables={o['id']:o for o in frame['evidence']['static_knowledge']['observables']}
    for condition in options['conditions']:
        _fields(condition,CONDITION_FIELDS,'Condition-maintenance binding');key=condition['candidate_id']
        _require(key in candidates and candidates[key]['kind']=='intervene' and key not in conditions,'Unknown/repeated condition-action binding')
        q=questions.get(candidates[key]['question_id'])
        _require(q is not None and condition['target_id'] in q['target_ids'],'Condition outside the declared risk question')
        _strings(condition['source_ids'],'Condition evidence sources')
        _require(condition['observable_id'] in observables and observables[condition['observable_id']]['value_type']=='number','Condition requires a numeric declared observable')
        for source_id in condition['source_ids']:
            source=sources.get(source_id)
            _require(source is not None and condition['target_id'] in source['target_ids']
                and condition['observable_id'] in source['observable_ids'],'Condition exceeds declared source coverage')
        bounds=condition['accepted_interval'];_require(type(bounds) is list and len(bounds)==2,'Declare condition interval')
        for bound in bounds:_finite(bound,'Condition interval endpoint')
        _finite(condition['not_before_s'],'Condition earliest observation')
        _require(bounds[0]<=bounds[1] and condition['not_before_s']>=0,'Invalid condition interval/time')
        conditions[key]=condition
    for audit in audits:
        candidate=candidates[audit['candidate_id']];q=questions.get(candidate['question_id'])
        _require(q is not None and candidate['task']['target_id'] in q['target_ids'],'Candidate outside its declared risk question')
        value=q['consequences']['service_deficit_time_s']['value']
        audit.update(risk_service_deficit_s=value,condition_record_ids=[],condition_blocking_record_ids=[])
        if candidate['kind']=='intervene':
            condition=conditions.get(candidate['id'])
            support,blocking=_condition(frame,condition) if condition is not None else ([],[])
            audit.update(condition_record_ids=support,condition_blocking_record_ids=blocking)
            if not support:audit['reasons'].append('NO_CURRENT_CONDITION_SUPPORT')
            if blocking:audit['reasons'].append('CURRENT_CONDITION_CONTRADICTED_OR_UNCERTAIN')
        elif value is not None and value<options['minimum_service_deficit_s']:
            audit['reasons'].append('BELOW_DECLARED_RISK_TRIGGER')
        audit['reasons']=sorted(set(audit['reasons']));audit['eligible']=not audit['reasons']
    eligible=[r for r in audits if r['eligible']]
    order=lambda row:(row['risk_service_deficit_s'] is None,-row['risk_service_deficit_s'] if row['risk_service_deficit_s'] is not None else 0,
        row['available_at_s'],row['candidate_id'])
    maintenance=sorted((r for r in eligible if r['kind']=='intervene'),key=order)
    inspections=sorted((r for r in eligible if r['kind']=='inspect'),key=order)
    selected=(maintenance or inspections)
    chosen=selected[0]['candidate_id'] if selected else None
    return chosen,dict(reason='ARRIVED_CONDITION_MAINTENANCE_ADAPTATION' if maintenance else 'DECLARED_RISK_PRIORITY_ADAPTATION' if chosen else 'NO_RISK_OR_CONDITION_ELIGIBLE_CANDIDATE',
        model_evaluations=dict(risk=1,action_value=0),unmodeled_question_ids=sorted(q['id'] for q in risk['questions'] if q['quantification']=='UNMODELED'),
        risk_model_status=risk['status'],adaptation='FINITE_RISK_TRIGGER_AND_ARRIVED_CONDITION_PRIORITY_NOT_PAPER_REPRODUCTION',
        risk_aggregation='PER_QUESTION_PRIORITY_NO_ADDITION_OF_OVERLAPPING_SERVICE_DEFICITS')
