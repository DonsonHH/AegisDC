"""Plan complete public branches, preserving paid prefix, worker/tool location and review obligations."""
from collections import defaultdict
from copy import deepcopy
from heapq import heappop, heappush
from .joint_evidence import action_feedback, instances, observation, own_ack


def transit(cfg, start, target, quals):
    if start is None or target is None:return None
    queue=[(0,(),start)];best={}
    while queue:
        cost,steps,here=heappop(queue)
        if here in best:continue
        best[here]=cost
        if here==target:return list(steps)
        for edge in cfg['routes']:
            if not set(edge['requires']).issubset(quals):continue
            there=edge['b'] if edge['a']==here else edge['a'] if edge['bidirectional'] and edge['b']==here else None
            if there is not None and there not in best:
                heappush(queue,(cost+edge['travel'],steps+(edge['travel'],),there))
    return None


def duration(cfg, pose, typ):
    w,tool=typ['worker'],typ['tool']
    first=transit(cfg,pose.get(w),pose.get(tool),cfg['qualification'][w])
    second=transit(cfg,pose.get(tool),typ['location'],cfg['qualification'][w])
    if first is None or second is None or typ['qualification'] not in cfg['qualification'][w]:return None
    path=first+second
    return sum(path)+max(1,len(path))*cfg['gate']+typ['work_s']


def public_prefix(cfg,view):
    now=view['time'];pose=deepcopy(cfg['pose']);free=defaultdict(float)
    issued={r['task']:r for r in view['issued']}
    debit=sum(cfg['deadline']-r['release'] for r in issued.values())
    facts={};pending={};reviews={};continued={};checks_waiting=[]
    for task,row in sorted(issued.items(),key=lambda x:(x[1]['at'],x[0])):
        typ=cfg['types'][task.split('/')[0]]
        ack=own_ack(cfg,view,task)
        for obj in (typ['worker'],typ['tool']):
            if ack:
                pose[obj]=ack['location'] if ack['status']=='completed' else None
                free[obj]=ack['arrived']
            else:
                free[obj]=max(row['planned_ack'],now)
                # Predicted position on the conditional success branch only.
        if task.endswith('/I') and (not ack or (ack['status']=='completed' and not any(r['task']==task for r in view['paid']))):
            checks_waiting.append(task)
            continued[task]=row.get('contingent',[])
        if not task.endswith('/A'):continue
        feedback=action_feedback(cfg,view,task)
        review=task[:-1]+'R'
        if feedback:
            if feedback['outcome']=='APPLIED':
                facts[task]=feedback['at']
                if review not in issued:reviews[review]=(feedback['at'],feedback['arrived'],max(feedback['arrived'],ack['arrived']))
        elif not ack or ack['status']=='completed':
            pending[task]=row['planned_end']
            if review not in issued:
                reviews[review]=(row['planned_end'],row['planned_ack'],max(now,row['planned_ack']))
    return dict(issued=issued,pose=pose,free=dict(free),debit=[debit,debit,len(issued)*cfg['fee']],
                confirmed=facts,pending=pending,reviews=reviews,waiting=checks_waiting,contingent=continued)


def opportunity(cfg, action_finish, sample, arrival):
    epochs=[x for x in cfg['fixed_epochs'] if x>=action_finish]
    return any(b-a>=1 and (t:=max(arrival,b+cfg['latency']))<=cfg['horizon']
               and t<a+cfg['fixed_ttl'] and t<sample+cfg['paid_ttl']
               for i,a in enumerate(epochs) for b in epochs[i+1:])


def schedule(cfg,view,sequence,*,conditional_positive=(),prefix=None):
    """Earliest public ticks, mandatory reviews first. All hypothetical jobs carry their own costs."""
    p=public_prefix(cfg,view) if prefix is None else prefix
    now=view['time'];opens=instances(cfg,view);issued=dict(p['issued'])
    pose=dict(p['pose']);free=dict(p['free']);reviews=dict(p['reviews'])
    for task in issued:
        ack=own_ack(cfg,view,task)
        if ack is None:
            typ=cfg['types'][task.split('/')[0]]
            for obj in (typ['worker'],typ['tool']):
                pose[obj]=typ['location']
    debit=list(p['debit']);work=[0,0,0];steps=[];queue=list(sequence);blocked_until=now
    last=max([now]+[r['planned_ack'] for task,r in issued.items() if not own_ack(cfg,view,task)])
    reason=None
    for tick in cfg['clock']:
        if tick<now:continue
        if not queue and not reviews:break
        ready=sorted(k for k,(_,_,ready_at) in reviews.items() if ready_at<=tick)
        task=ready[0] if ready else queue[0] if queue and tick>=blocked_until else None
        if task is None:continue
        instance,phase=task.rsplit('/',1);kind=instance.split('/')[0]
        if instance not in opens or task in issued:
            reason='UNKNOWN_OR_REPEATED';break
        typ=cfg['types'][kind];worker,tool=typ['worker'],typ['tool']
        if tick<max(free.get(worker,0),free.get(tool,0),cfg['shift'][worker][0]):continue
        dt=duration(cfg,pose,typ)
        if dt is None:
            reason='UNATTESTED_OR_UNREACHABLE';break
        finish=tick+dt;arrived=finish+cfg['latency']
        if finish>min(cfg['deadline'],cfg['shift'][worker][1]) or arrived>cfg['horizon']:
            reason='DEADLINE';break
        if phase=='A':
            lo,hi=typ['write']
            if tick<lo:continue
            if finish>=hi:reason='WRITE_WINDOW';break
            if typ['require_probe']:
                cert,_=observation(cfg,view,instance+'/I')
                live=cert in ('CONFIG_LIMIT_CURRENT','MIXED_LIMIT_CURRENT','LOW_FLOW') and any(
                    r['task']==instance+'/I' and tick<r['until'] for r in view['paid'])
                simulated=instance in conditional_positive and any(r['task']==instance+'/I'
                    and r['planned_ack']<=tick<r['planned_end']+cfg['paid_ttl'] for r in steps)
                if not (live or simulated):reason='OWN_POSITIVE_REQUIRED';break
        else:
            if not any(window and window[0]<=tick and finish<window[1] for window in typ['read'].values()):
                reason='READ_WINDOW';break
        release=reviews[task][1] if phase=='R' else opens[instance]
        if phase=='R' and not opportunity(cfg,reviews[task][0],finish,arrived):
            reason='NO_CERTIFICATE_TIME';break
        row=dict(task=task,at=tick,release=release,planned_end=finish,planned_ack=arrived)
        issued[task]=row;steps.append(row)
        for obj in (worker,tool):
            free[obj]=arrived;pose[obj]=typ['location']
        delta=cfg['deadline']-release
        debit[0]+=delta;debit[1]+=delta;debit[2]+=cfg['fee']
        work[0]+=dt;work[1]+=dt;work[2]+=cfg['fee'];last=max(last,arrived)
        if phase=='R':del reviews[task]
        else:
            queue.pop(0)
            if phase=='A':reviews[instance+'/R']=(finish,arrived,arrived)
            if phase=='I':blocked_until=arrived
    if reason is None and (queue or reviews):reason='NO_LEGAL_SLOT'
    if reason is None and any(x>y for x,y in zip(debit,cfg['caps'])):reason='RESOURCE_CAP'
    return dict(admitted=reason is None,reason=reason,steps=steps,required=debit,work=work,last=last)
