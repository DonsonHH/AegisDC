"""Typed, time-local public messages and instance certificates for the joint opt-in policy."""
from copy import deepcopy
from itertools import combinations


def require(condition, message):
    if not condition:
        raise ValueError(message)


def at_time(view, t):
    """Return a detached prefix. In particular, never expose a future revocation date."""
    out={'time':t}
    for channel in ('orders','work','writes','paid','fixed'):
        out[channel]=[deepcopy(r) for r in view[channel] if r['arrived']<=t and r['at']<=r['arrived']]
    for row in out['orders']:
        if row['revoked_at'] is not None and row['revoked_at']>t:
            row['revoked_at']=None
    out['issued']=[deepcopy(r) for r in view['issued'] if r['at']<=t]
    return out


def instances(cfg, view):
    """Open only on a lawful public decision tick; retain the stable original once opened."""
    opened={}
    for row in sorted(view['orders'],key=lambda r:(r['arrived'],r['origin'],r['id'])):
        if row['copied_from'] is not None or row['observable']!='problem_reported' or row['value'] is not True:
            continue
        for kind,typ in cfg['types'].items():
            if (row['desk'],row['target'])!=(typ['desk'],typ['target']):
                continue
            if '/' in row['origin']:
                raise ValueError('Unsafe joint source identity')
            stop=row['until'] if row['revoked_at'] is None else min(row['until'],row['revoked_at'])
            first=next((t for t in cfg['clock'] if row['arrived']<=t<stop and t<=view['time']),None)
            key=kind+'/'+row['origin']
            if first is not None and key not in opened and sum(k.startswith(kind+'/') for k in opened)<typ['max_origins']:
                opened[key]=first
    return opened


def own_ack(cfg, view, task):
    typ=cfg['types'][task.split('/')[0]]
    issued=next((x for x in view['issued'] if x['task']==task),None)
    if issued is None:
        return None
    return next((r for r in view['work'] if r['task']==task and r['origin']=='workforce:'+task
                 and r['at']>=issued['at'] and (r['worker'],r['tool'])==(typ['worker'],typ['tool'])
                 and (r['status']!='completed' or r['location']==typ['location'])),None)


def action_feedback(cfg, view, task):
    ack=own_ack(cfg,view,task)
    if not ack:
        return None
    op=cfg['types'][task.split('/')[0]]['operation']
    return next((r for r in view['writes'] if r['task']==task and r['operation']==op and r['at']==ack['at']
                 and r['origin']=='intervention:'+task and (r['outcome']=='NO_EFFECT' or
                 (r['outcome']=='APPLIED' and ack['status']=='completed'))),None)


def observation(cfg, view, task):
    kind,origin,phase=task.split('/')
    now=view['time']
    typ=cfg['types'][kind]
    rows=[r for r in view['paid'] if r['task']==task and r['instance']==kind+'/'+origin and r['phase']==phase
          and r['target']==typ['target'] and r['source']=='onsite-'+kind]
    if rows and not any(now<r['until'] for r in rows):
        return 'EXPIRED',{}
    ack=own_ack(cfg,view,task)
    if ack is None or ack['status']!='completed' or not rows:
        return 'PENDING',{}
    if any(r['at']!=ack['at'] or r['bundle']!=f"{task}@{ack['at']:g}" for r in rows):
        return 'UNKNOWN',{}
    fields={}
    for r in rows:
        if r['until']<=now or r['interval'] is None:
            continue
        right=typ['read'].get(r['field'])
        if right is None or not right[0]<=r['at']<right[1]:
            continue
        low,high=r['interval']
        if low>high or low<0 or r['unit']!=('m3/s' if r['field']=='q' else '1'):
            return 'UNKNOWN',{}
        if r['field'] in fields:
            old=fields[r['field']]
            low,high=max(low,old[0]),min(high,old[1])
            if low>high:
                return 'CONFLICT',{}
        fields[r['field']]=(low,high)
    if kind=='C':
        if 'q' not in fields:return 'UNKNOWN',fields
        lo,hi=fields['q']
        if .099<=lo and hi<=.101:return 'LOCAL_ADEQUATE',fields
        if hi<.08:return 'LOW_FLOW',fields
        return 'UNKNOWN',fields
    if 'e' not in fields:return 'UNKNOWN',fields
    e=fields['e']
    if 'g' not in fields:
        return ('EFFECTIVE_LOW_CAUSE_UNKNOWN' if e[1]<1 else 'UNKNOWN'),fields
    g=fields['g']
    if g[0]>=1 and e[0]>=1:return 'LOCAL_ADEQUATE',fields
    if g[0]>=1 and e[1]<1:return 'SUPPLY_LIMIT_CURRENT',fields
    if g[1]<1 and e[1]<g[0]:return 'MIXED_LIMIT_CURRENT',fields
    if g[1]<1 and g[0]==g[1]==e[0]==e[1]:return 'CONFIG_LIMIT_CURRENT',fields
    return 'UNKNOWN',fields


def stable_fixed(cfg, view, kind, start):
    field='lake' if kind=='C' else 'network' if kind=='N' else 'service'
    low,high=(99.7,99.9) if field=='lake' else (1,float('inf'))
    rows=[r for r in view['fixed'] if r['field']==field and r['source']=='fixed-'+field and start<=r['at']]
    live={r['at'] for r in rows if view['time']<r['until'] and r['interval'] is not None
          and low<=r['interval'][0]<=r['interval'][1]<=high}
    bad=[r['at'] for r in rows if r['interval'] is None or not low<=r['interval'][0]<=r['interval'][1]<=high]
    return any(b-a>=1 and not any(a<=t<=view['time'] for t in bad) for a,b in combinations(sorted(live),2))


def certificate(cfg,view,instance,opened):
    kind=instance.split('/')[0];action=instance+'/A'
    issued={r['task']:r for r in view['issued']}
    if action not in issued:
        state,_=observation(cfg,view,instance+'/I')
        if state=='EXPIRED':return 'OPEN_EXPIRED'
        if state=='LOCAL_ADEQUATE' and stable_fixed(cfg,view,kind,opened):
            return 'NO_ACTION_CURRENT'
        return 'OPEN'
    write=action_feedback(cfg,view,action);review=issued.get(instance+'/R')
    if not write or write['outcome']!='APPLIED' or not review:
        return 'OPEN'
    ack=own_ack(cfg,view,action)
    if review['at']<max(write['arrived'],ack['arrived']):
        return 'OPEN'
    state,_=observation(cfg,view,instance+'/R')
    if state=='EXPIRED':return 'OPEN_EXPIRED'
    if state=='LOCAL_ADEQUATE' and all(stable_fixed(cfg,view,k,write['at']) for k in (kind,'service')):
        return 'POST_ACTION_VERIFIED_CURRENT'
    return 'OPEN'
