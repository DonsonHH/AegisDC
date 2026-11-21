"""T3 public-only timing, certificates and three status-quo baseline decisions."""
from common import H,CLOCK,BIZ,next_tick


def key(subject,phase):return subject+'::'+phase


def entries(pub):return {s['id']:s for s in pub['subjects']}


def ack(view,task):
    return next((r for r in view['work'] if r['task_id']==task and r['status'] in ('completed','rejected','aborted')),None)


def applied(view,s):
    return next((r for r in view['writes'] if r['task']==key(s,'A') and r['outcome']=='APPLIED'),None)


def each_read(view,s):
    return [r for r in view['paid'] if r['subject']==s and r['fields'] is not None and
            r['source']=='onsite/'+s and (a:=ack(view,r['task'])) and a['status']=='completed' and a['observed_at_s']==r['sampled']]


def adequate(k,f,acted=False):
    if k=='C':return .099<=f['q']<=.101
    if k=='N':return f['g']>=1 and f['e']>=1
    if k=='LC':return f['versions']==['SHARED_CONTACT','SHARED_CONTACT']
    if k=='LB':return bool(f['contact'] and f['upstream'])
    if k=='LG':return f['ready'] and f['permitted']
    if k=='NR':return f['group_kW']<=f['transfer_kW']
    if k=='NP':return f['controller_on'] and f['running'] and not f['latched'] and (acted or f['automatic_restart'])
    if k=='NC':return f['commissioned'] and not f['under_construction']
    raise ValueError(k)


def actionable(k,fields):
    if k=='C':return fields['q']<.08
    if k=='N':return fields['g']<1 and fields['e']<=fields['g']
    if k=='LB':return not fields['contact'] and fields['released']
    if k=='NP':return fields['latched'] and fields['power_returned']
    if k=='NC':return not fields['commissioned'] and fields['handover']
    return not adequate(k,fields)


def certificate(sub,view):
    now=view['time'];s=sub['id'];acted=key(s,'A') in {r['task'] for r in view['issued']}
    action=applied(view,s) if acted else None
    if acted and not action:return 'OPEN'
    rows=each_read(view,s);phase='R' if acted else 'I'
    initial=next((r for r in rows if r['phase']==phase and (not acted or
        r['execution']==action['execution'] and r['parent_epoch']==r['physical_epoch']==action['epoch'] and r['issued']>=action['arrived'])),None)
    if not initial:return 'OPEN'
    valid=[r for r in rows if r==initial or (r['phase']=='X' and r['parent']==initial['task'] and
            r['execution']==initial['execution'] and r['parent_epoch']==initial['parent_epoch'] and (not acted or r['physical_epoch']==action['epoch']))]
    proof=max(valid,key=lambda r:r['sampled'])
    if now>=proof['until']:return 'OPEN_EXPIRED'
    if not adequate(sub['key'],proof['fields'],acted):return 'OPEN'
    start=action['at'] if acted else 0
    for field in ([s,'service'] if acted else [s]):
        vals=[r for r in view['fixed'] if r['field']==field and r['source']=='meter/'+field and r['sampled']>=start]
        latest_bad=max((r['sampled'] for r in vals if not r['ok']),default=-1)
        times=sorted({r['sampled'] for r in vals if r['ok'] and r['sampled']>latest_bad and r['until']>now})
        if len(times)<2 or times[-1]-times[0]<300:return 'OPEN'
    return 'PV' if acted else 'NA'


def duration(pub,sub,location):
    from aegis_dc.joint_resources import transit
    pf=pub['workforce'];edges=[dict(a=e['from'],b=e['to'],requires=e['requires_qualification_ids'],
        travel=pf['walk_times_s'][e['id']],bidirectional=e['bidirectional']) for e in pub['route_graph']]
    path=transit({'routes':edges},location,sub['location'],[sub['expertise']])
    if path is None:return None
    return sum(path)+max(len(path),1)*pf['access_check_s']+pf['work_times_s'][sub['interface']]


def live(view,kind):
    now=view['time']
    return [r for r in view['records'] if r['kind']==kind and r['copied_from'] is None and r['arrived']<=now<r['until']]


def admit(pub,view,s,phase,slot=None):
    now=view['time'];task=key(s['id'],phase);issued={r['task']:r for r in view['issued']}
    if not any(r['subject']==s['id'] for r in live(view,'order')):return None,'ORDER'
    if task in issued:return None,'ONCE'
    loc=s['start']
    for prior in issued.values():
        if (s['worker']==prior['worker'] or s['tool']==prior['tool']):
            msg=ack(view,prior['task'])
            if not msg or msg['status']!='completed' or not msg['location_id']:return None,'RESOURCE'
            loc=msg['location_id']
    dt=duration(pub,s,loc)
    if dt is None:return None,'ACCESS'
    finish=now+dt;arr=finish+pub['latency'];shift=pub['workforce']['shifts'][s['worker']]
    if not shift[0]<=now<finish<=shift[1] or arr>H:return None,'TIME'
    window=s['write_window'] if phase=='A' else s['renew_window'] if phase=='X' else s['read_window']
    if not window[0]<=now<=finish<window[1]:return None,'SCOPE_WINDOW'
    parent=None;execution=None;epoch=None;sid=s['id']
    if phase=='I' and not s['allow_initial']:return None,'NO_INITIAL_READ'
    if phase=='A':
        if not s['primary']:return None,'NO_ACTION'
        if s['key']=='NC' and not any(r['subject']==sid and r['value']=='HANDOVER_RELEASED' for r in live(view,'release')):
            return None,'NO_HANDOVER_RELEASE'
        if s['key']=='NP' and not any(r['value']=='POWER_RETURNED' for r in live(view,'status')):return None,'NO_RETURN_RECEIPT'
        nxt=next_tick(arr)
        if nxt is None or nxt+pub['workforce']['access_check_s']+pub['workforce']['work_times_s'][s['interface']]+pub['latency']>H:
            return None,'NO_REVIEW_TIME'
    if phase=='R':
        a=applied(view,sid);w=ack(view,key(sid,'A'))
        if not a or not w or w['status']!='completed':return None,'OWN_ACTION'
        parent=a['task'];execution=a['execution'];epoch=a['epoch']
    if phase=='X':
        if now<pub['renew_at']:return None,'EARLY_RENEWAL'
        acted=key(sid,'A') in issued;typ='R' if acted else 'I'
        prior=next((r for r in each_read(view,sid) if r['phase']==typ and adequate(s['key'],r['fields'],acted)),None)
        if not prior:return None,'NO_PRIOR_OWN_PROOF'
        a=applied(view,sid)
        if acted and (not a or prior['execution']!=a['execution'] or prior['parent_epoch']!=a['epoch']):return None,'STALE_PARENT'
        parent=prior['task'];execution=prior['execution'];epoch=prior['parent_epoch']
    obligations={r['subject'] for r in issued.values() if r['phase']=='A'}-{r['subject'] for r in issued.values() if r['phase']=='R'}
    if phase=='R':obligations.discard(sid)
    if phase=='A':obligations.add(sid)
    spent=sum(r['planned_end']-r['at'] for r in issued.values());reserve=len(obligations)*35
    if any(spent+dt+reserve>n for n in pub['resources'][:2]) or len(issued)+1+len(obligations)>pub['resources'][2]:
        return None,'BUDGET'
    return dict(task=task,subject=sid,phase=phase,at=now,planned_end=finish,worker=s['worker'],tool=s['tool'],
                instance=sid,parent=parent,execution=execution,parent_epoch=epoch,patrol_slot=slot),'ALLOW'


def choose(pub,view,role,plan):
    now=view['time'];units=entries(pub);done={r['task'] for r in view['issued']};options=[]
    if role in ('ORACLE','ENGINEERING') and now in plan:
        sid,phase=plan[now].rsplit('::',1);options.append((sid,phase,None))
    if role!='P':
        for s in pub['routes']:
            if key(s,'A') in done and key(s,'R') not in done:options.append((s,'R',None))
    if role=='ALARM':
        for note in live(view,'alarm'):
            if now>note['arrived']:
                route=pub['routes'] if note['subject'] in ('power-board','cooling-board') else [note['subject']]
                options.extend((sid,'A',None) for sid in route if sid in units and key(sid,'A') not in done)
    if role=='PERIODIC':
        for sid in pub['routes']:
            fields=next((r['fields'] for r in each_read(view,sid) if r['phase']=='I' and r['until']>now),None)
            if fields and actionable(units[sid]['key'],fields) and key(sid,'A') not in done:options.append((sid,'A',None))
    if role!='P' and now>=pub['renew_at']:
        for sid in pub['routes']:
            if key(sid,'X') not in done:options.append((sid,'X',None))
    if role=='PERIODIC':
        visits={r['patrol_slot']:r for r in view['issued'] if r['patrol_slot']}
        stop=False
        for cycle in range(4):
            if now<cycle*900:break
            for sid in pub['routes']:
                slot=f'{cycle}/{sid}'
                if slot in visits:
                    if ack(view,visits[slot]['task']) is None:stop=True;break
                    continue
                phase='I' if units[sid]['allow_initial'] and key(sid,'I') not in done else 'V'+str(cycle)
                options.append((sid,phase,slot));stop=True;break
            if stop:break
    req=None;denied=[]
    for sid,phase,slot in options:
        req,status=admit(pub,view,units[sid],phase,slot)
        if req:break
        denied.append([sid,phase,status])
    return dict(request=req,refusals=denied,certificates={s:certificate(u,view) for s,u in units.items()})
