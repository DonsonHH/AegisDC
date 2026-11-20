"""One public, resource-constrained choice over a joint world distribution."""
from copy import deepcopy
from fractions import Fraction
from itertools import permutations, product
from .joint_evidence import action_feedback, certificate, instances, observation, own_ack, require
from .joint_forecast import deficit, observe_branch, permits_correction, support
from .joint_resources import public_prefix, schedule


def validate(cfg):
    require(set(cfg)==set('schema method types worlds horizon deadline clock forecast_window caps gate latency paid_ttl fixed_ttl fee fixed_epochs fixed_on pose qualification shift routes'.split()),'Closed joint public program')
    require(cfg['schema']=='aegisdc-joint-problem-policy-v1' and cfg['method'] in
        ('J','B','HOLD','N_PROBE','N_DIRECT','C_DIRECT','C_CHECK'),'Joint token')
    require(cfg['clock']==sorted(set(cfg['clock'])) and cfg['clock'][0]==0 and cfg['clock'][-1]==cfg['horizon'],'Joint clock')
    require(len(cfg['caps'])==3 and all(x>=0 for x in cfg['caps']),'Resource dimensions')
    roots=set()
    for w in cfg['worlds']:
        require(set(w)=={'origin','anchor','cooling','g','A','s','mass'} and w['anchor']==0 and
                w['cooling'] in ('C0','F','O') and w['origin'] not in roots and Fraction(w['mass'])>0,'Joint original world')
        roots.add(w['origin'])
    if cfg['method'] in ('J','B'):
        require(sum(Fraction(w['mass']) for w in cfg['worlds'])==1,'Single normalized public world table')


def average(worlds,fn):
    mass=sum(Fraction(w['mass']) for w in worlds)
    return sum(Fraction(w['mass'])*fn(w) for w in worlds)/mass


def scores(cfg,worlds,prefix,plan):
    effects={**prefix['confirmed'],**prefix['pending']}
    effects.update({r['task']:r['planned_end'] for r in plan['steps'] if r['task'].endswith('/A')})
    loss=average(worlds,lambda w:deficit(cfg,w,effects))
    return (loss,*map(Fraction,plan['work']),Fraction(plan['last']))


def tie(sequence):
    return (bool(sequence),tuple(sequence))


def short(task):
    return task.split('/')[0]+'.'+task.rsplit('/',1)[1] if task else 'W'


def choose(cfg,view):
    validate(cfg)
    require(set(view)=={'time','orders','issued','work','writes','paid','fixed'} and view['time'] in cfg['clock'],'Public view')
    require(all(r['arrived']<=view['time'] for k in ('orders','work','writes','paid','fixed') for r in view[k]),'Future feedback')
    opens=instances(cfg,view);pre=public_prefix(cfg,view)
    worlds=support(cfg,view,pre)
    action_ids=sorted(k+'/A' for k in opens if k+'/A' not in pre['issued'])
    probe_ids=sorted(k+'/I' for k in opens if k+'/I' not in pre['issued'] and k+'/A' not in pre['issued'])
    sequences=[()]+[(a,) for a in action_ids]+list(permutations(action_ids,2))
    root=dict(debit=pre['debit'],confirmed=sorted(pre['confirmed']),pending=sorted(pre['pending']),
        obligations=sorted(pre['reviews']),reserved_review=sum(cfg['deadline']-v[1] for v in pre['reviews'].values()),
        contingent=pre['contingent'],issued=[r['task'] for r in view['issued']],pose=pre['pose'],
        support=sorted(w['origin'] for w in worlds))
    projected={}
    for bits in product((False,True),repeat=len(pre['pending'])):
        effects=dict(pre['confirmed'])
        yes=[k for k,b in zip(sorted(pre['pending']),bits) if b]
        effects.update({k:pre['pending'][k] for k in yes})
        if worlds:projected[','.join(yes)]=str(average(worlds,lambda w:deficit(cfg,w,effects)))
    root['W_conditional']=projected
    trial=lambda seq,positive=():schedule(cfg,view,seq,conditional_positive=positive,prefix=pre)
    base=trial([])
    alternatives=[];protected=[]
    def record(seq,plan,vector,branches=None):
        row=dict(sequence=list(seq),admitted=plan['admitted'],reason=plan['reason'],required=plan['required'],
                 steps=plan['steps'],score=[str(v) for v in vector] if vector is not None else None)
        if branches is not None:row['branches']=branches
        alternatives.append(row)
        return row
    def result(row):
        steps=row.get('steps',[]) if row else []
        first=steps[0] if row and row['admitted'] and steps and steps[0]['at']==view['time'] else None
        if first and first['task'].endswith('/R'):
            action=first['task'][:-1]+'A'
            received=action_feedback(cfg,view,action)
            if not received or received['outcome']!='APPLIED':
                first=None
        if first:
            typ=cfg['types'][first['task'].split('/')[0]]
            if any(not own_ack(cfg,view,t) and
                   any(typ[k]==cfg['types'][t.split('/')[0]][k] for k in ('worker','tool')) for t in pre['issued']):
                first=None
        reservation=deepcopy(row.get('branches',[])) if row else []
        if first:
            first=deepcopy(first)
            if first['task'].endswith('/I'):first['contingent']=reservation
        return dict(request=first,choice=short(first['task'] if first else None),prefix=root,alternatives=alternatives,
            selected=row,certificates={k:certificate(cfg,view,k,t) for k,t in opens.items()},
            reason='ZERO_SUPPORT' if cfg['method'] in ('J','B') and not worlds else 'PUBLIC_PLAN')
    wait=record((),base,scores(cfg,worlds,pre,base) if worlds else None)
    if base['steps'] and base['steps'][0]['at']==view['time'] and base['steps'][0]['task'].endswith('/R') and base['admitted']:
        return result(wait)
    if pre['waiting']:return result(wait)
    method=cfg['method']
    if method not in ('J','B'):
        task=None
        if method=='C_CHECK':task=next((k for k in probe_ids if k.startswith('C/')),None)
        elif method in ('C_DIRECT','N_DIRECT'):task=next((k for k in action_ids if k.startswith(method[0]+'/')),None)
        elif method=='N_PROBE':
            task=next((k for k in probe_ids if k.startswith('N/')),None)
            if task is None:
                task=next((a for a in action_ids if a.startswith('N/') and
                    observation(cfg,view,a[:-1]+'I')[0] in ('CONFIG_LIMIT_CURRENT','MIXED_LIMIT_CURRENT')),None)
        if task is not None:
            proposed=trial([task]);entry=record((task,),proposed,None)
            if proposed['admitted']:return result(entry)
        return result(wait)
    if not worlds or not base['admitted']:return result(wait)
    direct=[]
    for seq in sequences:
        plan=base if not seq else trial(seq)
        vector=scores(cfg,worlds,pre,plan) if plan['admitted'] else None
        row=wait if not seq else record(seq,plan,vector)
        if vector is not None:direct.append((vector,tie(seq),row))
    best_direct=min(direct,key=lambda item:item[:2])
    options=list(direct)
    for probe in probe_ids:
        one=trial([probe])
        if not one['admitted']:continue
        acquisition=next(r for r in one['steps'] if r['task']==probe)
        effects={**pre['confirmed'],**pre['pending']}
        groups={}
        for world in worlds:
            signature=observe_branch(cfg,world,probe,acquisition['at'],acquisition['planned_end'],effects)
            groups.setdefault(signature,[]).append(world)
        branches=[];vectors=[];continuations=set();improves=False
        for signature,group in sorted(groups.items()):
            positive=[probe.rsplit('/',1)[0]] if permits_correction(probe.split('/')[0],signature) else []
            feasible=[]
            for seq in sequences:
                path=one if not seq else trial([probe,*seq],positive)
                if path['admitted']:
                    vector=scores(cfg,group,pre,path)
                    feasible.append((vector,tie(seq),seq,path))
            vector,_,seq,path=min(feasible,key=lambda item:item[:2])
            improves |= vector[0]<scores(cfg,group,pre,one)[0]
            mass=sum(Fraction(w['mass']) for w in group)
            vectors.append((mass,vector));continuations.add(seq)
            branches.append(dict(observation=[list(x) for x in signature],continuation=list(seq),
                required=path['required'],steps=path['steps'],score=[str(v) for v in vector]))
        mass=sum(m for m,_ in vectors)
        vector=tuple(sum(m*v[i] for m,v in vectors)/mass for i in range(4))+(max(v[-1] for _,v in vectors),)
        row=record((probe,),one,vector,branches)
        # No conclusion or refusal releases only the unissued contingent branch.
        row['unknown_branch']='WAIT_AND_KEEP_EXISTING_OWN_REVIEWS'
        if method=='J':options.append((vector,tie((probe,)),row))
        elif len(continuations)>1 and improves:
            dt=acquisition['planned_end']-acquisition['at']
            protected.append(((dt,dt,cfg['fee'],acquisition['planned_ack'],probe),row))
    if method=='B':
        if best_direct[0][0]<Fraction(wait['score'][0]):return result(best_direct[2])
        return result(min(protected,key=lambda x:x[0])[1] if protected else wait)
    return result(min(options,key=lambda item:item[:2])[2])
