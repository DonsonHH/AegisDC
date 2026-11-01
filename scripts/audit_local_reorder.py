"""Independent recorded-ledger and whole-continuation arithmetic, no policy rerun."""
import math
from itertools import permutations

import numpy as np

from patrol_rsi.aisles import build_agents
from audit_m111 import distance


def need(value,message):
    if not value:raise RuntimeError('Reorder audit: '+message)


def close(a,b):return abs(float(a)-float(b))<=1e-8


def audit_reorder(record,env):
    agents=build_agents(env.graph,'provisioned');tasks=env.tasks
    tours=[list(a['tour']) for a in agents]
    remaining=[list(v) for v in tours];committed=[[] for _ in agents];rounds=[0]*len(agents)
    busy={};last={j:0. for j in range(len(tasks))};settled=[]
    def duration(position,j):
        raw=distance(env.graph,tuple(position),tasks[j].position_m)
        return float(raw),float(math.ceil((raw+tasks[j].service_s)/5.-1e-10)*5.)
    def proof(now,position,left,order,tour):
        seq=list(order)+[j for j in left if j not in order]+tour
        virtual={j:last[j] for j in tour};times=[];dues=[];walk=[];first={};slack=float('inf')
        for j in seq:
            d,cost=duration(position,j);now+=cost;due=virtual[j]+env.deadlines[j]
            if now>due+1e-9:return {'ok':False,'failed_task':j,'finish_s':now,'due_s':due}
            times.append(now);dues.append(float(due));walk.append(d);first.setdefault(str(j),now)
            slack=min(slack,due-now);virtual[j]=now;position=tasks[j].position_m
        period=sum(duration(tasks[a].position_m,b)[1] for a,b in zip(tour[-1:]+tour[:-1],tour))
        need(all(period<=env.deadlines[j]+1e-9 for j in tour),'restored repeated period')
        return {'ok':True,'completion_s':times,'due_s':dues,'first_completion_s':first,
            'segment_and_bridge_travel_s':sum(walk[:len(order)+1]),'minimum_slack_s':slack,'restored_period_s':period}
    def compare(stored,expected):
        need(stored['ok']==expected['ok'],'candidate safety status')
        if expected['ok']:
            for key in ('completion_s','due_s'):
                need(len(stored[key])==len(expected[key]) and all(close(a,b) for a,b in zip(stored[key],expected[key])),key)
            for key in ('segment_and_bridge_travel_s','minimum_slack_s','restored_period_s'):need(close(stored[key],expected[key]),key)
            need(all(close(stored['first_completion_s'][k],v) for k,v in expected['first_completion_s'].items()),'first future completion')
        elif 'failed_task' in expected:
            need(stored['failed_task']==expected['failed_task'] and close(stored['finish_s'],expected['finish_s']) and close(stored['due_s'],expected['due_s']),'rejected delayed task')
    timeline=[]
    for e in record['inspection_events']:timeline.append((e['time_s'],0,e['agent'],e))
    for d in record['local_decisions']:timeline.append((d['time_s'],1,d['agent'],d))
    for d in record['local_dispatches']:timeline.append((d['dispatch_time_s'],2,d['agent'],d))
    checks=0
    for time_s,kind,i,item in sorted(timeline,key=lambda v:v[:3]):
        tour=tours[i]
        if kind==0:
            j=item['task'];pending=busy.pop(i)
            need(pending['task']==j and pending['round_id']==rounds[i],'completion matches inflight round')
            need(committed[i] and committed[i][0]==j and j in remaining[i],'no duplicate/omitted settlement')
            need(close(pending['certificate']['segment_completion_s'][0],time_s),'actual vs certified completion')
            settled.append({'agent':i,'round_id':rounds[i],'task':j,'time_s':time_s})
            committed[i].pop(0);remaining[i].remove(j);last[j]=float(time_s)
            if not remaining[i]:
                need(not committed[i],'round boundary');rounds[i]+=1;remaining[i]=list(tour)
        elif kind==1:
            need(i not in busy and not committed[i],'new plan only at free uncommitted boundary')
            need(item['round_id']==rounds[i] and item['remaining_before']==remaining[i],'actual remaining ledger')
            window=remaining[i][:3]
            need(item['window']==window and {tuple(c['order']) for c in item['candidates']}==set(permutations(window)),'complete local permutation space')
            snapshot={v['task']:v for v in item['public_tasks']}
            for c in item['candidates']:
                expected=proof(time_s,agents[i]['position'],remaining[i],c['order'],tour)
                compare(c['certificate'],expected);checks+=1
                if expected['ok']:
                    f=c['features'];risk=pressure=fresh=0.;peak=0.
                    for j in tour:
                        row=snapshot[j];finish=expected['first_completion_s'][str(j)];deadline=env.deadlines[j]
                        need(close(row['last_check_s'],last[j] if last[j] else -1.) or close(row['last_check_s'],last[j]),'public inspection age')
                        ratio=(finish-last[j])/deadline;delay=(finish-time_s)/deadline
                        risk+=row['weight']*row['risk']*delay;pressure+=ratio*ratio;fresh+=row['weight']*row['freshness']*delay;peak=max(peak,ratio)
                    calculated={'risk_delay':risk/len(tour),'deadline_pressure':pressure/len(tour),'deadline_peak':peak,
                        'travel_cost':expected['segment_and_bridge_travel_s']/300.,'freshness_delay':fresh/len(tour)}
                    need(set(f)==set(calculated) and all(close(f[k],v) for k,v in calculated.items()),'public aggregate arithmetic')
            chosen=next(c for c in item['candidates'] if c['order']==item['selected_order'])
            need(chosen['certificate']['ok'],'selected permutation certified')
            committed[i]=list(item['selected_order'])
        else:
            j=item['task']
            need(i not in busy and committed[i] and committed[i][0]==j,'dispatch committed head')
            need(item['round_id']==rounds[i] and item['remaining_before']==remaining[i] and item['committed_before']==committed[i],'dispatch ledger identity')
            need(tuple(item['position'])==agents[i]['position'],'dispatch true position')
            need(j in tour and tasks[j].required_role==agents[i]['role'] and tasks[j].access=='external_sensing','ownership/profession/access')
            compare(item['certificate'],proof(time_s,agents[i]['position'],remaining[i],committed[i],tour))
            need(item['certificate']['segment_completion_s'][0]<=1800.+1e-9,'no unfinished physical service past horizon')
            busy[i]=item
        if kind==0:agents[i]['position']=tasks[item['task']].position_m
    need(not busy,'all actual assignments completed')
    need(sorted(settled,key=lambda x:(x['time_s'],x['agent']))==sorted(record['obligation_events'],key=lambda x:(x['time_s'],x['agent'])),'complete obligation event log')
    for i,stored in enumerate(record['round_ledgers']):
        need(stored['round_id']==rounds[i] and stored['remaining']==remaining[i] and stored['committed']==committed[i] and stored['inflight'] is None,'terminal ledger')
        actual=[(e['round_id'],e['task']) for e in settled if e['agent']==i]
        need(len(actual)==len(set(actual)),'one settlement per round task')
        need(stored['settled_obligations']==[list(v) for v in actual],'all settled keys')
        for round_id in range(rounds[i]):need({j for r,j in actual if r==round_id}==set(tours[i]),'no skipped round tasks')
    gaps=[]
    for j in range(len(tasks)):
        times=[0.]+[e['time_s'] for e in record['inspection_events'] if e['task']==j]+[1800.]
        gap=max(b-a for a,b in zip(times,times[1:]));gaps.append(gap)
        need(gap<=env.deadlines[j]+1e-9,'all true initial/intermediate/terminal gaps')
    need(record['metrics']['extra_checks']==0,'no inserted discretionary checks')
    return {'passed':True,'independent_candidate_proofs':checks,'actual_obligation_settlements':len(settled),
        'no_omitted_or_duplicate_round_obligations':True,'actual_maximum_gap_s':max(gaps)}
