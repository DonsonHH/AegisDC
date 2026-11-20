"""Independent saved-data evaluation for the finite native comparison; no plant calls."""
from fractions import Fraction
import json
import math
from pathlib import Path

from patrol_rsi.contracts import digest
from .native_compare_inputs import file_hash, read

CHECKPOINTS = (5,7.5,10)
PERSON = ('worker_travel_person_s','worker_work_person_s','worker_wait_person_s')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_native(directory):
    directory=Path(directory)
    run=read(directory/'run.json')
    for name in ('scenario.json','private-state.jsonl','balances.jsonl'):
        require(file_hash(directory/name)==run['artifacts'][name]['sha256'], 'Saved native file differs: '+name)
    def lines(name):
        with (directory/name).open(encoding='utf-8') as stream:
            rows=[json.loads(line) for line in stream]
        require(len(rows)==run['artifacts'][name]['records'], 'Native record count differs')
        return rows
    return run,lines('private-state.jsonl'),lines('balances.jsonl')


def segment(profile, start, end, *rates):
    if profile and profile[-1][1]==start and profile[-1][2:]==list(rates):
        profile[-1][1]=end
    else:
        profile.append([start,end,*rates])


def service(rows):
    """Exact sums of decoded native balances, separate from rate-history integrals."""
    L=U=rate_L=rate_U=Fraction(0)
    profile=[]
    previous=0
    for start,end,d,y,b_loss,b_demand,b_delivery in rows:
        require(start==previous and end>start and 0<=y<=d,'Invalid contiguous service history')
        require(all(type(v) in (int,float) and math.isfinite(v) for v in (start,end,d,y,b_loss,b_demand,b_delivery)),
                'Invalid numeric input in saved service history')
        dt=Fraction(end)-Fraction(start)
        missing=Fraction(d)-Fraction(y)
        L+=Fraction(b_loss)
        U+=Fraction(b_demand)-Fraction(b_delivery)
        rate_L+=dt*missing/Fraction(d) if d else 0
        rate_U+=dt*missing
        segment(profile,start,end,d,y)
        previous=end
    require(previous==10,'Incomplete H10 service window')
    return dict(balance=[str(L),str(U)],rate=[str(rate_L),str(rate_U)],profile=profile)


def numeric_direction(balance, rate, identical_history=False):
    if identical_history or balance==rate==0:
        return 'EQUAL'
    if balance>0 and rate>0:
        return 'BETTER'
    if balance<0 and rate<0:
        return 'WORSE'
    return 'NUMERIC_UNRESOLVED'


def combine(directions):
    kinds=set(directions)-{'EQUAL'}
    if not kinds:return 'EQUAL'
    if 'NUMERIC_UNRESOLVED' in kinds:return 'NUMERIC_UNRESOLVED'
    if len(kinds)==1:return kinds.pop()
    return 'TRADEOFF'


def differences(candidate, comparator, identical):
    balance=[Fraction(y)-Fraction(x) for x,y in zip(candidate['balance'],comparator['balance'])]
    rates=[Fraction(y)-Fraction(x) for x,y in zip(candidate['rate'],comparator['rate'])]
    directions=[numeric_direction(a,b,c) for a,b,c in zip(balance,rates,identical)]
    return dict(direction=combine(directions),components=directions,balance_delta=list(map(str,balance)),rate_delta=list(map(str,rates)))


def compare_service(candidate, comparator):
    # The exact integral of a step function is invariant under splitting any
    # interval. Coalesced rate histories represent its common-grid equivalence.
    return differences(candidate,comparator,[candidate['profile']==comparator['profile']]*2)


def compare_arms(candidate, comparator):
    if candidate['status']!='COMPLETED' or comparator['status']!='COMPLETED':
        return dict(comparable=False,physical=None,resources=None,closure=None,service_gain=None,same_service_resource_improvement=None)
    service_delta=compare_service(candidate['service'],comparator['service'])
    a,b=candidate['resources'],comparator['resources']
    resource_delta=differences(a,b,[x==y for x,y in zip(a['profiles'],b['profiles'])])
    cq,dq=candidate['questions'],comparator['questions']
    require(cq.keys()==dq.keys(),'Mismatched predeclared question denominator')
    lost=[];gained=[]
    for key in dq:
        for label,x,y in [('ever',cq[key]['first'] is not None,dq[key]['first'] is not None),
                *[(str(t),cx['closed'],dx['closed']) for t,cx,dx in zip(CHECKPOINTS,cq[key]['at'],dq[key]['at'],strict=True)]]:
            if y and not x:lost.append([key,label])
            if x and not y:gained.append([key,label])
    compliant=not candidate['violations'] and not comparator['violations']
    protected=compliant and not lost
    return dict(comparable=compliant,physical=service_delta,resources=resource_delta,closure=dict(lost=lost,gained=gained,preserved=not lost),
        service_gain=protected and service_delta['components']==['BETTER','BETTER'],
        same_service_resource_improvement=protected and service_delta['direction']=='EQUAL' and resource_delta['direction']=='BETTER')


def resource_rates(snapshot, task_workers, shifts):
    work=snapshot['domains']['people_tools_work']
    workers=work['workers']
    busy={w for w,r in workers.items() if r['status'] in ('travelling','working','waiting')}
    for task in work.get('queued_requests',[]):
        for w in task_workers[task]:
            if workers[w]['status']=='idle' and shifts[w][0]<=snapshot['time_s']<shifts[w][1]:
                busy.add(w)
    tools=sum(r['reserved_by'] is not None for r in work['tools'].values())
    return len(busy),tools


def questions(run, decisions, work):
    episodes=run['inputs']['business_program']['components']['instance_closure']['episodes']
    out={}
    violations=[]
    for episode in episodes:
        key=episode['question_id'];action=episode['task_id'];verify=episode['recheck_task_id']
        by_time={}
        for decision in decisions:
            entries=decision['choice']['question_lifecycle']['questions']
            values=[v for v in entries if v['question_id']==key]
            require(len(values)<=1,'Duplicate question assessment')
            by_time[decision['frame']['as_of_s']]=values[0] if values else None
        first=next((t for t,q in by_time.items() if q and q['risk_closed'] and q['question_closed']),None)
        checkpoints=[]
        for t in CHECKPOINTS:
            q=by_time[t]
            checkpoints.append(dict(time=t,state=q['status'] if q else 'NOT_OPENED',
                closed=bool(q and q['risk_closed'] and q['question_closed']),
                risk_closed=bool(q and q['risk_closed']),question_closed=bool(q and q['question_closed']),
                record=q['own_recheck']['record_id'] if q else None))
        completed=[r for r in work if r['id']==verify and r['status']=='completed']
        end=by_time[10]
        if end and any(q and q['risk_closed'] and (not q['own_recheck']['passed'] or q['own_recheck']['task_id']!=verify or not all(c['passed'] for c in q['checks'])) for q in by_time.values()):
            violations.append(key+':closure-without-own-evidence')
        actual=next((r for r in run['intervention_public_feedback'] if r['task_id']==action),None)
        native=next(r for r in run['business_evaluation']['components']['instance_closure']['episodes'] if r['question_id']==key)
        require(native['first_verified_closed_at_s']==first and native['status_at_horizon']==(checkpoints[-1]['state'] if end else 'NOT_ASSESSED_AT_HORIZON'),
                'Native business closure disagrees with public evidence history')
        if end is None:obligation='NOT_OPENED'
        elif end['risk_closed']:obligation='VERIFIED_CURRENT'
        elif actual is None:obligation='ACTION_UNCONFIRMED' if any(r['id']==action for r in work) else 'NO_ACTION'
        elif actual['outcome']!='APPLIED':obligation='NO_EFFECT'
        elif completed:obligation='COMPLETED_RECHECK_NOT_CURRENTLY_VERIFIED'
        else:obligation='SUCCESS_AWAITING_OWN_VALID_RECHECK'
        out[key]=dict(opened=next((t for t,q in by_time.items() if q),None),first=first,at=checkpoints,
            rechecks_issued=sum(r['id']==verify for r in work),rechecks_completed=len(completed),
            right_censored=first is None,censor_time=10 if first is None else None,
            own_action=action,own_action_report=actual,own_recheck=verify,terminal_obligation=obligation)
    return out,violations


def score_arm(run, trace, balances):
    """Read endpoints and actual execution, never call a decision or facility function."""
    decisions=run['policy_public_decisions']
    program=run['inputs']['dispatch_program']
    policy=program['policy_program']
    work=run['work_records']
    require([d['frame']['as_of_s'] for d in decisions]==program['decision_times_s'],'Incomplete public clock')
    require(len(trace)==len(balances)+1 and trace[0]['time_s']==0 and trace[-1]['time_s']==10,'Incomplete physical trajectory')
    observed=[]
    balance_person=balance_tool=rate_person=rate_tool=Fraction(0)
    people_profile=[];tool_profile=[]
    task_workers={r['id']:[w['worker_id'] for w in r['crew']] for r in work}
    for i,b in enumerate(balances):
        snapshot=trace[i];start=b['start_s'];end=b['end_s']
        require(snapshot['time_s']==start and trace[i+1]['time_s']==end,'Native interval boundaries differ')
        it=snapshot['domains']['it_service']
        observed.append([start,end,it['demand'],it['delivered'],b['service_deficit_time_s'],b['demand_service_unit_s'],b['delivered_service_unit_s']])
        busy,tools=resource_rates(snapshot,task_workers,policy['workforce_profile']['shifts'])
        dt=Fraction(end)-Fraction(start)
        rate_person+=dt*busy;rate_tool+=dt*tools
        balance_person+=sum((Fraction(b[k]) for k in PERSON),Fraction(0))
        balance_tool+=Fraction(b['tool_occupation_tool_s'])
        segment(people_profile,start,end,busy);segment(tool_profile,start,end,tools)
    actual_service=service(observed)
    costs=run['business_evaluation']['components']['costs']
    summary=run['summary']
    # Native summaries round exact balance sums to binary64; check their own
    # accumulation contract as well as retaining exact saved balance contributions.
    require(math.fsum(b['service_deficit_time_s'] for b in balances)==summary['service_deficit_time_s']
        and all(math.fsum(b[k] for b in balances)==summary[k] for k in ('demand_service_unit_s','delivered_service_unit_s',*PERSON,'tool_occupation_tool_s')),
        'Saved balances disagree with native summary')
    require(costs['personnel_total']['value']==math.fsum(summary[k] for k in PERSON)
            and costs['actual']['tool_occupation_tool_s']['value']==summary['tool_occupation_tool_s'],'Native occupation endpoint differs')
    issued=[];violations=[]
    for decision in decisions:
        choice=decision['choice'];frame=decision['frame'];history=decision['history']
        if any(r['arrived_at_s']>frame['as_of_s'] for r in frame['evidence']['records']+history['work_feedback']+history['intervention_feedback']):
            violations.append('future-evidence')
        selected=choice['chosen_candidate_id']
        if selected is None:continue
        audit=next((a for a in choice['candidates'] if a['candidate_id']==selected),None)
        if audit is None or not audit['eligible'] or (choice['work_intention'] or {}).get('id')!=selected:
            violations.append('illegal-issuance:'+selected)
        issued.append((selected,frame['as_of_s']))
    if len(set(k for k,_ in issued))!=len(issued):violations.append('repeated-task')
    require(issued==[(r['id'],r['issued_at_s']) for r in work],'Recorded work differs from actual public issues')
    templates={t['id']:t for t in policy['templates']}
    charged={};fee_events=[]
    for key,t in issued:
        template,stage_slot=key.split('/')
        stage=stage_slot.split('-')[0]
        fee=Fraction(templates[template]['issue_costs'][stage])
        charged[key]=fee
        fee_events.append([t,key,str(fee)])
    fee=sum(charged.values(),Fraction(0))
    ledger=costs['admission']
    for key,amount in ledger['spent_or_reserved'].items():
        if amount>policy['resource_budget'][key] or ledger['remaining'][key]<0:violations.append('budget:'+key)
    require(ledger['terminal_report_refund'] is False and Fraction(costs['issue_fees']['value'])==fee and
            Fraction(ledger['spent_or_reserved']['cost'])==fee,'Issue costs disagree')
    qs,invalid=questions(run,decisions,work)
    violations.extend(invalid)
    return dict(status='COMPLETED',violations=violations,service=actual_service,
        native_summary={k:summary[k] for k in ('service_deficit_time_s','demand_service_unit_s','delivered_service_unit_s')},
        resources=dict(balance=list(map(str,(balance_person,balance_tool,fee))),rate=list(map(str,(rate_person,rate_tool,fee))),
            profiles=[people_profile,tool_profile,fee_events],actual_components=costs['actual'],admission=ledger),
        questions=qs,internal_policy_calls=len(decisions),semantic_sha256=digest(dict(decisions=decisions,work=work,
            intervention=run['intervention_private_audit'],trace=digest(trace),balances=digest(balances),questions=qs,
            service=actual_service,resources=[str(rate_person),str(rate_tool),str(fee)])))


def panel(results, condition_ids):
    """Keep every predeclared pair, including absent/failed arms, in the output table."""
    rows=[]
    for condition in condition_ids:
        data=results.get(condition,{})
        vh=None
        if all(data.get(arm,{}).get('status')=='COMPLETED' for arm in ('V','H')):
            vh=data['V']['semantic_sha256']==data['H']['semantic_sha256']
        contrasts={arm:compare_arms(data.get('V',{'status':'NOT_EXECUTED'}),data.get(arm,{'status':'NOT_EXECUTED'}))
                   for arm in ('D','K','P','H')}
        rows.append(dict(condition=condition,arms={arm:data.get(arm,{}).get('status','NOT_EXECUTED') for arm in ('V','D','K','H','P')},
                         consistency=vh,contrasts=contrasts))
    claims={}
    for arm in ('D','K','P','H'):
        pairs=[r['contrasts'][arm] for r in rows]
        clean=bool(pairs) and all(p['comparable'] and p['physical']['direction']!='NUMERIC_UNRESOLVED' for p in pairs) and all(r['consistency'] is True for r in rows)
        same=[p for p in pairs if p['comparable'] and p['physical']['direction']=='EQUAL']
        nonworse={'EQUAL','BETTER'}
        claims[arm]=dict(planned=len(pairs),compliant_pairs=sum(p['comparable'] for p in pairs),same_service=len(same),
            pure_service_improvement=(all(p['physical']['direction'] in nonworse for p in pairs) and
            any(p['physical']['components']==['BETTER','BETTER'] for p in pairs)) if clean else None,
            service_and_closure=(all(p['closure']['preserved'] and p['physical']['direction'] in nonworse for p in pairs) and
            any(p['service_gain'] for p in pairs)) if clean else None,
            resources_on_equal_service=(all(p['closure']['preserved'] and p['resources']['direction'] in nonworse for p in same)
              and any(p['same_service_resource_improvement'] for p in same)) if clean and all(p['resources']['direction']!='NUMERIC_UNRESOLVED' for p in same) else None)
    return dict(rows=rows,claims=claims)
