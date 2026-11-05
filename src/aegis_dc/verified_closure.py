"""Question lifecycle from current public evidence and declared verification rules."""
from copy import deepcopy
from fractions import Fraction

from .decision_view import validate_current_frame
from .evidence_ledger import _fields,_plain_json,_registry,_require,_strings,_text,_finite
from .risk_scenarios import assess_risks
from .intervention_execution import _profile as _intervention_profile,BIND_FIELDS,SETTING_BOUNDS

PROGRAM_FIELDS={'schema','profile','risk_catalog','belief_model','intervention_feedback','intervention_declaration'}
PROFILE_FIELDS={'schema','id','facility_id','nominal_knowledge_id','risk_catalog_id','basis','time_unit','source_note','rules','review_channels','authorizations','false_alarm_reviews'}
RULE_FIELDS={'id','question_id','opened_at_s','task_id','operation_id','minimum_span_s','required_samples','checks'}
CHECK_FIELDS={'id','role','target_id','observable_id','source_ids','accepted_interval'}
FEEDBACK_FIELDS={'task_id','operation_id','source_id','observed_at_s','arrived_at_s','outcome','reason','origin_id','coverage','risk_closed'}
REVIEW_FIELDS={'id','question_id','source_id','target_id','observable_id','authorization_id'}
GRANT_FIELDS={'id','source_id','question_ids','dispositions','starts_at_s','expires_at_s','basis','source_note'}

def _profile(frame,program,risks):
    profile=program['profile'];_fields(profile,PROFILE_FIELDS,'Closure profile')
    _require(profile['schema']=='aegisdc-closure-profile-v1' and profile['basis']=='synthetic_assumption'
        and profile['time_unit']=='s','Declare synthetic closure profile in SI seconds')
    for key in ('id','source_note'):_text(profile[key],'Closure '+key)
    _require(profile['facility_id']==frame['facility_id'] and profile['nominal_knowledge_id']==frame['nominal_knowledge']['id']
        and profile['risk_catalog_id']==program['risk_catalog']['id'],'Closure facility/catalog identity differs')
    questions={q['id']:q for q in program['risk_catalog']['questions']}
    rules=_registry(profile['rules'],'Closure rule');seen=set()
    sources={s['id']:s for s in frame['evidence']['static_knowledge']['sources']}
    observables={o['id']:o for o in frame['evidence']['static_knowledge']['observables']}
    for rule in rules.values():
        _fields(rule,RULE_FIELDS,'Closure rule')
        for key in ('question_id','task_id','operation_id'):_text(rule[key],'Closure '+key)
        _require(rule['question_id'] in questions and rule['question_id'] not in seen,'Unknown/repeated closure question')
        seen.add(rule['question_id']);q=questions[rule['question_id']]
        _finite(rule['opened_at_s'],'Question opening');_finite(rule['minimum_span_s'],'Verification span')
        _require(0<=rule['opened_at_s']<=frame['as_of_s'] and rule['minimum_span_s']>0,'Invalid opening or span')
        _require(type(rule['required_samples']) is int and rule['required_samples']>=2,'Declare at least two genuine samples')
        checks=_registry(rule['checks'],'Verification check');roles=set()
        for check in checks.values():
            _fields(check,CHECK_FIELDS,'Verification check');role=check['role'];roles.add(role)
            _require(role in {'condition','service'},'Unknown verification role')
            _require(check['target_id'] in q['target_ids'] if role=='condition' else
                     check['target_id']==program['risk_catalog']['service_id'],'Verification target outside question/service')
            observable=observables.get(check['observable_id'])
            _require(observable is not None and observable['value_type']=='number','Numeric verification needs declared observable')
            _strings(check['source_ids'],'Verification sources')
            for identifier in check['source_ids']:
                source=sources.get(identifier)
                _require(source is not None and check['target_id'] in source['target_ids']
                    and check['observable_id'] in source['observable_ids'],'Verification source outside declared coverage')
            bounds=check['accepted_interval'];_require(type(bounds) is list and len(bounds)==2,'Declare accepted interval')
            for bound in bounds:_finite(bound,'Accepted numeric bound')
            _require(bounds[0]<=bounds[1],'Reversed accepted interval')
        _require(roles=={'condition','service'},'Require both physical condition and service verification')
    return rules

def _reviews(frame,program,rules):
    profile=program['profile'];grants=_registry(profile['authorizations'],'Review authorization')
    channels=_registry(profile['review_channels'],'Review channel')
    sources={s['id']:s for s in frame['evidence']['static_knowledge']['sources']}
    observables={o['id']:o for o in frame['evidence']['static_knowledge']['observables']}
    questions={r['question_id']:r for r in rules.values()}
    for grant in grants.values():
        _fields(grant,GRANT_FIELDS,'Review authorization')
        _text(grant['source_note'],'Review authority provenance')
        _strings(grant['question_ids'],'Authorized questions');_strings(grant['dispositions'],'Authorized dispositions')
        _require(grant['source_id'] in sources and set(grant['question_ids'])<=set(questions)
            and set(grant['dispositions'])<={'ACCEPT_RISK','ESCALATE','FALSE_ALARM'} and grant['basis']=='synthetic_assumption','Unknown review authority scope')
        _finite(grant['starts_at_s'],'Authority start');_finite(grant['expires_at_s'],'Authority expiry')
        _require(0<=grant['starts_at_s']<grant['expires_at_s'],'Invalid review authorization interval')
    result={q:[] for q in questions}
    current_ids=set(frame['evidence']['current_record_ids'])
    disputed={identifier for issue in frame['evidence']['provenance_issues']
        if set(issue['record_ids'])&current_ids for identifier in issue['record_ids']}
    disputed|={identifier for issue in frame['evidence']['conflicts']
        if set(issue['record_ids'])<=current_ids for identifier in issue['record_ids']}
    for channel in channels.values():
        _fields(channel,REVIEW_FIELDS,'Review channel')
        _require(channel['question_id'] in questions and channel['source_id'] in sources
            and channel['authorization_id'] in grants,'Unknown review binding')
        source=sources[channel['source_id']];observable=observables.get(channel['observable_id'])
        _require(channel['target_id'] in source['target_ids'] and channel['observable_id'] in source['observable_ids']
            and observable is not None and observable['value_type']=='text','Review channel exceeds categorical source coverage')
        grant=grants[channel['authorization_id']]
        _require(grant['source_id']==source['id'] and channel['question_id'] in grant['question_ids'],'Review source/authority mismatch')
        rule=questions[channel['question_id']]
        for row in frame['evidence']['records']:
            if any(row[key]!=channel[key] for key in ('source_id','target_id','observable_id')):continue
            if row['observed_at_s']<rule['opened_at_s'] or row['availability']!='current' or row['quality']['status']!='reported':continue
            if row['id'] in disputed:continue
            if row['provenance']['copied_from_record_id'] is not None:continue
            if row['value'] not in grant['dispositions']:continue
            if not grant['starts_at_s']<=row['observed_at_s']<grant['expires_at_s'] or not grant['starts_at_s']<=frame['as_of_s']<grant['expires_at_s']:continue
            result[channel['question_id']].append(row)
    return result

def _false_alarm_dossiers(program,rules):
    rows=program['profile']['false_alarm_reviews'];_require(type(rows) is list,'Declare false-alarm review dossiers')
    result={};questions={r['question_id'] for r in rules.values()}
    for row in rows:
        _fields(row,{'review_record_id','question_id','supporting_record_ids','rationale'},'False-alarm dossier')
        _text(row['review_record_id'],'Review record identity');_text(row['rationale'],'Explicit false-alarm review rationale')
        _strings(row['supporting_record_ids'],'False-alarm supporting records')
        _require(row['question_id'] in questions and row['review_record_id'] not in result,'Unknown/repeated false-alarm review')
        result[row['review_record_id']]=row
    return result

def _feedback(frame,program):
    _require(type(program['intervention_feedback']) is list,'Declare arrived intervention feedback list')
    result={}
    for row in program['intervention_feedback']:
        _fields(row,FEEDBACK_FIELDS,'Arrived intervention feedback')
        for key in ('task_id','operation_id','origin_id'):_text(row[key],'Feedback '+key)
        _require(row['source_id']=='intervention-execution-report' and row['coverage']=='THIS_AUTHORIZED_TASK_ONLY'
            and row['risk_closed'] is False and row['origin_id']=='intervention:'+row['task_id'],'Invalid task-local feedback channel')
        _require(row['outcome'] in {'APPLIED','NO_EFFECT'},'Unknown intervention outcome')
        _require(row['reason'] is None if row['outcome']=='APPLIED' else type(row['reason']) is str and bool(row['reason']),
            'Feedback reason differs from outcome')
        _finite(row['observed_at_s'],'Feedback observation');_finite(row['arrived_at_s'],'Feedback arrival')
        _require(0<=row['observed_at_s']<=row['arrived_at_s']<=frame['as_of_s'],'Feedback cannot contain future/private time')
        _require(row['task_id'] not in result,'Repeated terminal task feedback')
        result[row['task_id']]=row
    return result

def _action_declaration(frame,program,rules,feedback):
    declared=program['intervention_declaration']
    _fields(declared,{'schema','profile','bindings'},'Public intervention declaration')
    _require(declared['schema']=='aegisdc-intervention-program-v1','Unknown declared intervention schema')
    operations,grants=_intervention_profile(declared['profile'],frame['nominal_knowledge'])
    _require(type(declared['bindings']) is list,'Declare task-operation bindings')
    bindings={}
    for binding in declared['bindings']:
        _fields(binding,BIND_FIELDS,'Declared task-operation binding')
        _text(binding['task_id'],'Declared task identity');_finite(binding['setting'],'Declared operation setting')
        _require(binding['task_id'] not in bindings and binding['operation_id'] in operations
            and binding['authorization_id'] in grants,'Unknown/repeated task operation declaration')
        op=operations[binding['operation_id']];grant=grants[binding['authorization_id']]
        low,high=SETTING_BOUNDS[op['kind']]
        _require(low<=binding['setting']<=high and op['id'] in grant['operation_ids']
            and op['target_id'] in grant['target_ids'],'Declared operation setting or authority differs')
        if op['kind']=='request_backup_cooling':_require(binding['setting'] in (0,1),'Backup declaration must be binary')
        bindings[binding['task_id']]=binding
    questions={q['id']:q for q in program['risk_catalog']['questions']}
    for rule in rules.values():
        binding=bindings.get(rule['task_id'])
        _require(binding is not None and binding['operation_id']==rule['operation_id']
            and operations[rule['operation_id']]['target_id'] in questions[rule['question_id']]['target_ids'],
            'Closure action must bind a declared named task operation within question scope')
        report=feedback.get(rule['task_id'])
        if report is not None and report['outcome']=='APPLIED':
            grant=grants[binding['authorization_id']]
            _require(grant['starts_at_s']<=report['observed_at_s']<grant['expires_at_s'],
                'Applied action report contradicts its declared authorization interval')

def _check(frame,rule,check,after):
    rows=[r for r in frame['evidence']['records'] if r['target_id']==check['target_id']
        and r['observable_id']==check['observable_id']
        and r['observed_at_s']>=after]
    eligible=[];issues=[];seen=set();seen_times=set()
    current_ids={r['id'] for r in rows if r['availability']=='current'}
    conflict_ids={identifier for conflict in frame['evidence']['conflicts']
        if set(conflict['record_ids'])<=current_ids for identifier in conflict['record_ids']}
    provenance_ids={identifier for issue in frame['evidence']['provenance_issues']
        if set(issue['record_ids'])&current_ids for identifier in issue['record_ids']}
    for row in sorted(rows,key=lambda r:(r['observed_at_s'],r['id'])):
        origin=row['provenance']['origin_id']
        if row['source_id'] not in check['source_ids']:
            if row['availability']=='current' and row['id'] in conflict_ids|provenance_ids:issues.append(row['id'])
            elif row['availability']=='current' and row['quality']['status']=='bounded':
                low=Fraction(row['value'])-Fraction(row['quality']['error_bound']);high=Fraction(row['value'])+Fraction(row['quality']['error_bound'])
                if high<Fraction(check['accepted_interval'][0]) or low>Fraction(check['accepted_interval'][1]):issues.append(row['id'])
            continue
        if row['availability']=='expired':continue
        if row['availability']!='current' or row['quality']['status']!='bounded':issues.append(row['id']);continue
        if row['id'] in conflict_ids|provenance_ids:issues.append(row['id']);continue
        low=Fraction(row['value'])-Fraction(row['quality']['error_bound']);high=Fraction(row['value'])+Fraction(row['quality']['error_bound'])
        if low<Fraction(check['accepted_interval'][0]) or high>Fraction(check['accepted_interval'][1]):issues.append(row['id']);continue
        if row['provenance']['copied_from_record_id'] is not None or origin in seen or row['observed_at_s'] in seen_times:continue
        seen.add(origin);seen_times.add(row['observed_at_s'])
        eligible.append(row)
    span_ok=bool(eligible) and eligible[-1]['observed_at_s']>=eligible[0]['observed_at_s']+rule['minimum_span_s']
    passed=not issues and len(eligible)>=rule['required_samples'] and span_ok
    return dict(check_id=check['id'],role=check['role'],passed=passed,
        supporting_record_ids=[r['id'] for r in eligible],insufficient_record_ids=issues,
        genuine_sample_count=len(eligible),span_s=eligible[-1]['observed_at_s']-eligible[0]['observed_at_s'] if eligible else None,
        independence='NOT_ESTABLISHED_NO_PROBABILITY_MULTIPLICATION')

def assess_closure(frame,program):
    """Evaluate declared question criteria from currently arrived public records only."""
    frame=validate_current_frame(frame);_plain_json(program);_fields(program,PROGRAM_FIELDS,'Closure program')
    _require(program['schema']=='aegisdc-closure-program-v1','Unknown closure program schema')
    risks=assess_risks(frame,program['belief_model'],program['risk_catalog'])
    rules=_profile(frame,program,risks);feedback=_feedback(frame,program);reviews=_reviews(frame,program,rules)
    _action_declaration(frame,program,rules,feedback)
    dossiers=_false_alarm_dossiers(program,rules);questions=[]
    for rule in rules.values():
        action=feedback.get(rule['task_id']);checks=[];trace=[]
        if action is None:status='OPEN_UNCONFIRMED'
        else:
            _require(action['operation_id']==rule['operation_id'] and action['observed_at_s']>=rule['opened_at_s'],'Action differs from question rule')
            trace.append(dict(event='ACTION_REPORT_AVAILABLE',observed_at_s=action['observed_at_s'],arrived_at_s=action['arrived_at_s'],origin_id=action['origin_id'],outcome=action['outcome']))
            status='ACTION_COMPLETED_PENDING_VERIFICATION' if action['outcome']=='APPLIED' else 'OPEN_ACTION_FAILED'
            if action['outcome']=='APPLIED':
                checks=[_check(frame,rule,check,action['observed_at_s']) for check in rule['checks']]
                if all(c['passed'] for c in checks):status='VERIFIED_CLOSED'
                elif all(c['passed'] for c in checks if c['role']=='condition'):status='SYMPTOM_RETREATED_PENDING_VERIFICATION'
        supported=sorted({identifier for c in checks for identifier in c['supporting_record_ids']})
        for row in frame['evidence']['records']:
            if row['id'] in supported:trace.append(dict(event='VERIFICATION_RECORD_AVAILABLE',record_id=row['id'],
                observed_at_s=row['observed_at_s'],arrived_at_s=row['arrived_at_s'],valid_until_s=row['valid_until_s'],provenance=deepcopy(row['provenance'])))
        dispositions=reviews[rule['question_id']]
        verified_reviews=[]
        for review in dispositions:
            if review['value']!='FALSE_ALARM':continue
            dossier=dossiers.get(review['id'])
            if dossier is None or dossier['question_id']!=rule['question_id']:continue
            ids=set(dossier['supporting_record_ids'])
            # The reviewer could only use records available by their review time.
            prior=deepcopy(frame)
            prior['evidence']['records']=[r for r in frame['evidence']['records'] if r['id'] in ids
                and r['observed_at_s']<=review['observed_at_s'] and r['arrived_at_s']<=review['observed_at_s']]
            if len(prior['evidence']['records'])!=len(ids):continue
            prior_ids={r['id'] for r in prior['evidence']['records']}
            prior['evidence']['conflicts']=[c for c in frame['evidence']['conflicts'] if set(c['record_ids'])<=prior_ids]
            evidence_checks=[_check(prior,rule,c,rule['opened_at_s']) for c in rule['checks']]
            current_checks=[_check(frame,rule,c,rule['opened_at_s']) for c in rule['checks']]
            if all(c['passed'] for c in evidence_checks) and all(c['passed'] for c in current_checks):
                verified_reviews.append(review);supported=sorted(set(supported)|ids)
        if any(r['value']=='ESCALATE' for r in dispositions):status='ESCALATED'
        elif any(r['value']=='ACCEPT_RISK' for r in dispositions):status='RISK_ACCEPTED'
        elif verified_reviews:status='FALSE_ALARM_REVIEWED'
        traced={e['record_id'] for e in trace if e.get('event')=='VERIFICATION_RECORD_AVAILABLE'}
        for row in frame['evidence']['records']:
            if row['id'] in set(supported)-traced:trace.append(dict(event='VERIFICATION_RECORD_AVAILABLE',record_id=row['id'],
                observed_at_s=row['observed_at_s'],arrived_at_s=row['arrived_at_s'],valid_until_s=row['valid_until_s'],provenance=deepcopy(row['provenance'])))
        for row in dispositions:trace.append(dict(event='AUTHORIZED_REVIEW_AVAILABLE',record_id=row['id'],disposition=row['value'],
            observed_at_s=row['observed_at_s'],arrived_at_s=row['arrived_at_s'],valid_until_s=row['valid_until_s'],provenance=deepcopy(row['provenance'])))
        trace.sort(key=lambda e:(e['arrived_at_s'],e.get('record_id','')))
        questions.append(dict(question_id=rule['question_id'],rule_id=rule['id'],as_of_s=frame['as_of_s'],status=status,
            risk_closed=status=='VERIFIED_CLOSED',question_closed=status in {'VERIFIED_CLOSED','RISK_ACCEPTED','FALSE_ALARM_REVIEWED'},
            physical_restoration_claim=False,scope='DECLARED_FINITE_SAMPLED_CRITERIA_ONLY',
            supporting_record_ids=supported,disposition_record_ids=sorted(r['id'] for r in dispositions),checks=checks,trace=trace))
    return dict(schema='aegisdc-closure-assessment-v1',facility_id=frame['facility_id'],as_of_s=frame['as_of_s'],questions=questions,
        unevaluated_question_ids=sorted(q['id'] for q in risks['questions'] if q['id'] not in {r['question_id'] for r in rules.values()}),
        execution_permission=False,physical_actions=[],field_calibration='PENDING',research_gain_claim='NOT_ESTABLISHED')

def main():
    import argparse
    import json
    from pathlib import Path
    from patrol_rsi.contracts import strict_json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame',type=Path,required=True);parser.add_argument('--program',type=Path,required=True)
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    try:
        result=assess_closure(strict_json(args.frame.read_text(encoding='utf-8')),strict_json(args.program.read_text(encoding='utf-8')))
        content=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8',newline='\n') as stream:stream.write(content)
    except (ValueError,KeyError,OSError) as error:parser.error(str(error))
    print(content,end='')

if __name__=='__main__':main()
