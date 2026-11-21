"""Independent evaluator of completed, native work/receipts, inventories, loss and typed closure."""
import math
from common import CLOCK,BIZ,H,digest,insist


def normal(kind,f,after):
    if f is None:return False
    if kind=='C':return abs(f['q']-.1)<=.001
    if kind=='N':return min(f['g'],f['e'])>=1
    if kind=='LC':return set(f['versions'])=={'SHARED_CONTACT'} and len(f['versions'])==2
    if kind=='LB':return bool(f['contact']) and bool(f['upstream'])
    if kind=='LG':return f['permitted'] and f['ready']
    if kind=='NR':return f['transfer_kW']>=f['group_kW']
    if kind=='NP':return f['running'] and f['controller_on'] and not f['latched'] and (after or f['automatic_restart'])
    if kind=='NC':return f['commissioned'] and not f['under_construction']
    raise ValueError(kind)


def independent_closure(sub,t,issued,work,paid,writes,fixed):
    sid=sub['id'];act=sid+'::A';after=act in issued
    def terminal(task):
        return next((q for q in work if q['task_id']==task and q['source_id']=='workforce-execution-report'
                    and q['origin_id']=='workforce:'+task and q['status']=='completed' and q['arrived_at_s']<=t),None)
    write=next((v for v in writes if v['task']==act and v['source']=='work-execution' and v['origin']=='write/'+act
                and v['outcome']=='APPLIED' and v['arrived']<=t),None)
    if after and not (write and terminal(act)):return 'OPEN'
    primary=sid+('::R' if after else '::I')
    usable=[]
    for r in paid:
        if (r['subject']!=sid or r['task'] not in (primary,sid+'::X') or r['arrived']>t or not r['fields']
            or r['source']!='onsite/'+sid or r['origin']!=r['task']+'@'+format(r['sampled'],'g')
            or r['worker']!=sub['worker'] or r['tool']!=sub['tool']):continue
        ack=terminal(r['task'])
        if not ack or ack['observed_at_s']!=r['sampled']:continue
        if after and (r['execution']!=write['execution'] or r['parent_epoch']!=write['epoch'] or
                      r['physical_epoch']!=write['epoch'] or r['issued']<max(write['arrived'],terminal(act)['arrived_at_s'])):continue
        if r['phase']=='X' and (r['parent']!=primary or not any(q['task']==primary for q in usable)):continue
        usable.append(r)
    if not any(q['task']==primary for q in usable):return 'OPEN'
    latest=max(usable,key=lambda q:q['sampled'])
    if not t<latest['until']:return 'OPEN_EXPIRED'
    if not normal(sub['key'],latest['fields'],after):return 'OPEN'
    for name in ([sid,'service'] if after else [sid]):
        samples=[q for q in fixed if q['field']==name and q['source']=='meter/'+name and
                 q['sampled']>=(write['at'] if after else 0) and q['arrived']<=t]
        last_bad=max([v['sampled'] for v in samples if not v['ok']]+[-1])
        times={v['sampled'] for v in samples if v['sampled']>last_bad and v['ok'] and t<v['until']}
        if not times or max(times)-min(times)<300:return 'OPEN'
    return 'PV' if after else 'NA'


def score(x,run,attached,role):
    from audit_v6_joint import physiology
    a=physiology(run);n=x['native'];prog=n['dispatch_program'];pub=prog['public']
    insist(run['source_config']==n['scenario'] and run['inputs']['dispatch_program']==prog and
           run['inputs']['boundary_events']==sorted(n['boundary_events'],key=lambda q:q['time_s']) and
           run['inputs']['maximum_step_s']==.25 and run['inputs']['duration_s']==H,'native input/clock binding')
    insist(a['continuous'] and a['conserved'] and all(abs(l-r)<1e-7 for l,r in zip(a['rate'],a['balance'])) and
           all(abs(l-r)<1e-7 for l,r in zip(a['physical_work'],a['native_work'])),'independent energy/mass/cost/service')
    dec=run['policy_public_decisions'];insist([d['view']['time'] for d in dec]==list(CLOCK),'61 clocks')
    work={w['id']:w for w in run['work_records']};feedback=run['workforce_public_feedback']
    paid=run['inspection_public_feedback'];writes=run['intervention_public_feedback']
    subs={s['id']:s for s in pub['subjects']};fixed=dec[-1]['view']['fixed'];issued=set();first={};checkpoints={};denials=[]
    changes=[];old_state=None;public_prefix=[];requests=[];duty=[]
    for d in dec:
        v=d['view'];t=v['time'];ch=d['decision']
        insist(set(v)=={'time','records','work','paid','writes','fixed','issued'},'public whitelist')
        for channel in ('records','paid','writes','fixed'):
            insist(all(r['arrived']<=t for r in v[channel]),'premature record')
        insist([r for r in prog['channel'] if r['arrived']<=t]==[r for r in v['records'] if r['kind']!='status'],'scoped public prefix')
        insist(v['work']==[r for r in feedback if r['arrived_at_s']<=t] and v['paid']==[r for r in paid if r['arrived']<=t]
               and v['writes']==[r for r in writes if r['arrived']<=t],'complete lawful publication')
        states={k:independent_closure(sub,t,issued,feedback,paid,writes,fixed) for k,sub in subs.items()}
        insist(states==ch['certificates'],'independent named certificates at '+str(t))
        if states!=old_state:changes.append([t,states]);old_state=states
        for k,state in states.items():
            if state in ('NA','PV'):first.setdefault(k,{}).setdefault(state,t)
        if t in BIZ:checkpoints[str(int(t))]=states
        req=ch['request'];public_prefix.append([t,digest(v),req['task'] if req else None])
        denials.extend([t,*row] for row in ch['refusals'])
        if req:
            task=req['task'];insist(task not in issued and task in work and req['at']==work[task]['issued_at_s']==t,'real once-only work')
            issued.add(task);requests.append([t,task]);s=subs[req['subject']]
            if req['phase']=='A':insist(s['write_window'][0]<=t<=req['planned_end']<s['write_window'][1],'write scope')
            if req['phase']=='R':
                insist(any(z['execution']==req['execution'] and z['epoch']==req['parent_epoch']
                    and z['arrived']<=t and z['outcome']=='APPLIED' for z in writes),'actual parent')
            if req['patrol_slot']:duty.append([t,req['patrol_slot'],task])
    insist(issued==set(work),'work/issuance closure')
    for q in paid:
        w=work[q['task']];insist(w['status']=='completed' and w['finished_at_s']==q['sampled'] and
               q['arrived']==q['sampled']+15 and q['until']==q['sampled']+pub['paid_ttl'],'paid sample timing')
    for q in writes:
        if q['outcome']=='APPLIED':
            w=work[q['task']];insist(w['status']=='completed' and w['finished_at_s']==q['at'] and
              q['execution']==q['task']+'@'+format(q['at'],'g'),'native write/work identity')
    if role=='P':insist(not requests and not paid and not writes and a['physical_work']==[0,0],'only existing protection')
    if role=='PERIODIC':
        expected=[f'{i}/{s}' for i in range(4) for s in pub['routes']]
        insist([z[1] for z in duty]==expected[:len(duty)],'periodic route order')
    if attached:insist(abs(attached['account']['residual_J'])<1e-7,'attached energy inventory')
    trace=run['trace'];curve=[]
    for l,r in zip(trace,trace[1:]):
        it=l['domains']['it_service'];demand,y=it['demand'],it['delivered'];start=l['time_s'];end=r['time_s']
        if curve and curve[-1][2:]==[demand,y]:curve[-1][1]=end
        else:curve.append([start,end,demand,y])
    return dict(L=a['rate'][0],U=a['rate'][1],integral_balances=a['balance'],person=a['physical_work'][0],tool=a['physical_work'][1],
        fee=len(requests),first=first,checkpoints=checkpoints,closure_changes=changes,requests=requests,refusals=denials,
        route=duty,work=[[w['id'],w['status'],w['issued_at_s'],w.get('finished_at_s')] for w in work.values()],
        paid=paid,writes=writes,first_loss=next((start for start,end,d,y in curve if y<d),None),curve=curve,
        fixed=fixed,public_prefix=public_prefix,attachment=attached,clocks=len(dec),runtime=run['code_identity']['source_tree_sha256'])
