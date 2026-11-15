"""Uniform private scoring; independent of plant integration and policy choice."""
from fractions import Fraction
import json


def number(x):
    if type(x) not in (int,str):raise ValueError('Exact numeric encoding required')
    return Fraction(x)


def encode(x):
    if isinstance(x,Fraction):return x.numerator if x.denominator==1 else str(x)
    if isinstance(x,dict):return {k:encode(v) for k,v in x.items()}
    if isinstance(x,list):return [encode(v) for v in x]
    return x


def score_arm(audit,run,isolation_ok,frozen_input):
    """Score saved private segments, never call a model or select an action."""
    c=frozen_input;H=number(c['H']);end=number(audit['time']);P=number(c['P'])
    demand_plan=[(number(t),number(d)) for t,d in c['demand']]
    if not demand_plan or demand_plan[0][0]!=0 or any(d not in (0,1) for _,d in demand_plan) or any(demand_plan[i][0]>=demand_plan[i+1][0] for i in range(len(demand_plan)-1)):
        raise ValueError('Invalid frozen demand schedule')
    cursor=Fraction(0);loss=unserved=load=ups=occupied=Fraction(0)
    chronological=True;bounds=True;labels=True;calendar_clear=True;demand_matches=True;service_defined=True
    by_action={};by_stage={};starts={}
    for s in audit['segments']:
        a,b=number(s['start']),number(s['end']);dt=b-a
        chronological=chronological and a==cursor and b>a and b<=H;cursor=b
        power,reported_demand,service=number(s['power']),number(s['demand']),number(s['service'])
        bounds=bounds and reported_demand in (0,1) and power in (0,P)
        bounds=bounds and ((s['source'] is None and power==0 and service==0) or (s['source'] in ('A','B','G','UPS') and power==P))
        bounds=bounds and (s['device']=='OFF' if power==0 else s['device'] in ('BOOTING','RUNNING'))
        # The exogenous demand is authoritative, not the plant's report. Split
        # even a malformed constant segment at every frozen demand boundary.
        cuts=sorted({a,b}|{t for t,_ in demand_plan if a<t<b})
        for x,y in zip(cuts,cuts[1:]):
            demand=next(d for t,d in reversed(demand_plan) if t<=x)
            demand_matches=demand_matches and reported_demand==demand
            service_defined=service_defined and 0<=service<=demand
            bounds=bounds and 0<=service<=demand and service==(demand if s['device']=='RUNNING' and power>0 else 0)
            loss+=(y-x)*(demand-service)/demand if demand else 0
            unserved+=(y-x)*(demand-service)
        load+=dt*power
        if s['source']=='UPS':ups+=dt*power
        action,stage=s['work_action'],s['work_stage']
        if s['occupied']:
            occupied+=dt
            labels=labels and action in ('READ_POS','READ_VOLT','READ_CONFIG','FIX_CTRL','VERIFY_CTRL') and stage in ('READING','VERIFYING','PREPARING','IMPLEMENTING','EXITING')
            by_action[action]=by_action.get(action,Fraction(0))+dt;by_stage[stage]=by_stage.get(stage,Fraction(0))+dt;starts.setdefault(action,a)
            calendar_clear=calendar_clear and not any(max(a,number(x))<min(b,number(y)) for x,y in c['calendar'])
        else:labels=labels and action is None and stage is None
    complete=chronological and cursor==end==H
    status='COMPLETE' if complete else 'INCOMPLETE_TRACE' if chronological and cursor==end and end<H else 'INVALID_TRACE'
    agrees=(loss==number(audit['L']) and unserved==number(audit['U']) and load==number(audit['load_energy']) and ups==number(audit['ups_energy']))
    queue_wait=Fraction(0);unstarted_wait=Fraction(0);clock_ok=True
    grant=audit['internal_approval'];fix_requests=[]
    authorization=True
    for r in run['requests']:
        action=r['payload']['action'];requested=number(r['time'])
        if action=='FIX_CTRL':fix_requests.append(r)
        if r['reply']['status']!='ADMITTED':continue
        view=run['public_trace'][r['frame_index']]['view'];perm=view['context']['permissions']
        if action.startswith('READ_'):allowed=perm['read']=='ALLOW'
        elif action=='VERIFY_CTRL':allowed=perm['read']=='ALLOW' and perm['verify']=='ALLOW'
        else:allowed=perm['propose']=='ALLOW' and (r['payload']['mode']!='DIRECT' or perm['direct']=='ALLOW')
        authorization=authorization and allowed
        if action in starts:
            origin=requested
            if action=='FIX_CTRL':
                if grant is None or grant['decision']!='APPROVE':authorization=False
                else:origin=number(grant['decided_at'])
            wait=starts[action]-origin;clock_ok=clock_ok and wait>=0;queue_wait+=wait
        else:
            wait=number(run['stop']['time'])-requested;clock_ok=clock_ok and wait>=0;unstarted_wait+=wait
    approval_wait=0 if not fix_requests else None if grant is None else number(grant['decided_at'])-number(fix_requests[0]['time'])
    if approval_wait is not None:clock_ok=clock_ok and approval_wait>=0
    budget=number(c['budget'])
    ledger_ok=number(audit['spent'])==occupied
    for name in ('person','tool'):
        ledger=audit['budgets'][name]
        ledger_ok=ledger_ok and number(ledger['limit'])==budget and number(ledger['spent'])==occupied
        ledger_ok=ledger_ok and number(ledger['available'])==budget-number(ledger['spent'])-number(ledger['reserved'])
    frozen_matches=json.dumps(audit['original_input'],sort_keys=True)==json.dumps(c,sort_keys=True)
    constraints=dict(full_window=complete,trace_chronological=chronological,service_and_power_bounds=bounds,frozen_input_matches=frozen_matches,reported_demand_matches=demand_matches,
                     energy_nonnegative=number(audit['E'])>=0,energy_balance=number(c['E0'])-number(audit['E'])==ups,
                     model_report_agrees=agrees,work_labels_valid=labels,budget_ledger_agrees=ledger_ok,
                     within_budget=occupied<=budget,external_reservations_clear=calendar_clear,
                     reserved_exit_honored=not audit['resource_overrun'],clock_costs_nonnegative=clock_ok,
                     authorization_respected=authorization,runner_contract=not run['errors'],instance_isolation=isolation_ok)
    return encode(dict(trace_status=status,L=loss if complete and service_defined else None,U=unserved if complete and service_defined else None,
                       load_energy=load,ups_energy=ups,person_seconds=occupied,tool_seconds=occupied,
                       resource_queue_seconds=queue_wait,approval_wait_seconds=approval_wait,
                       unstarted_observed_wait_seconds=unstarted_wait,observed_stop_time=run['stop']['time'],
                       work_by_action=by_action,work_by_stage=by_stage,request_count=len(run['requests']),
                       policy_call_count=len(run['public_trace']),recoveries=audit['recoveries'],
                       reported_demand_matches=demand_matches,model_report_agrees=agrees,hard_constraints=constraints,hard_constraints_ok=all(constraints.values())))
