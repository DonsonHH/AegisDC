"""Shared minute admission using only arrived public records and actual native work receipts."""
from aegis_dc.joint_evidence import at_time, instances, observation
from aegis_dc.joint_messages import own_ack, action_feedback
from aegis_dc.joint_resources import duration, public_prefix


def live_sources(view, topic):
    now = view['time']
    result = {}
    for row in view['orders']:
        end = row['until'] if row['revoked_at'] is None else min(row['until'],row['revoked_at'])
        if row['observable']!=topic or not row['value'] or not row['arrived']<=now<end or row['copied_from'] is not None:
            continue
        key=(row['desk'],row['origin'])
        result.setdefault(key,row)
    return list(result.values())


def admit(cfg,view,task,duty=False):
    now=view['time'];kind,origin,phase=task.split('/')
    typ=cfg['types'][kind]; opened=instances(cfg,view);pre=public_prefix(cfg,view)
    instance=kind+'/'+origin
    if instance not in opened and not duty:return None,'NO_OPEN_ORDER'
    if task in pre['issued']:return None,'ALREADY_ISSUED'
    if typ['worker'] in pre['locked'] or typ['tool'] in pre['locked']:return None,'RESOURCE_HELD'
    d=duration(cfg,pre['pose'],typ)
    if d is None:return None,'ACCESS_UNKNOWN'
    end=now+d;ack=end+cfg['latency']
    if not (cfg['shift'][typ['worker']][0]<=now and end<=cfg['shift'][typ['worker']][1] and ack<=cfg['horizon']):
        return None,'HORIZON_OR_SHIFT'
    if phase=='R':
        parent=instance+'/A';w=own_ack(cfg,view,parent);a=action_feedback(cfg,view,parent)
        if not (w and w['status']=='completed' and a and a['outcome']=='APPLIED'):return None,'OWN_WRITE_PENDING'
    if phase=='A':
        if not typ['write'][0]<=now<=end<typ['write'][1]:return None,'WRITE_WINDOW'
        if typ['require_probe'] and observation(cfg,view,instance+'/I')[0] not in ('LOW_FLOW','CONFIG_LIMIT_CURRENT','MIXED_LIMIT_CURRENT'):
            return None,'OWN_POSITIVE_REQUIRED'
    if phase in ('I','R') and not all(g and g[0]<=now<=end<g[1] for g in typ['read'].values()):
        return None,'READ_WINDOW'
    # All modes use the same upper bound on physical time charged and outstanding reviews.
    issued=view['issued']; used=sum(r['planned_end']-r['at'] for r in issued)
    reviews={r['task'][:-1]+'R' for r in issued if r['task'].endswith('/A')}
    reviews-=set(r['task'] for r in issued)
    reviews.discard(task)
    if phase=='A':
        next_tick=next((t for t in cfg['clock'] if t>=ack),None)
        if next_tick is None or next_tick+cfg['gate']+typ['work_s']+cfg['latency']>cfg['horizon']:
            return None,'NO_REVIEW_TIME'
        reviews.add(instance+'/R')
    reserve=sum(cfg['gate']+cfg['types'][k.split('/')[0]]['work_s'] for k in reviews)
    if any(used+d+reserve>cap for cap in cfg['caps'][:2]) or (len(issued)+1+len(reviews))*cfg['fee']>cfg['caps'][2]:
        return None,'BUDGET'
    return dict(task=task,at=now,release=opened.get(instance,now),planned_end=end,planned_ack=ack),'ADMITTED'


def engineering_choice(cfg,view):
    t=view['time']; attempts=[]; chosen=None
    targets={0:['C/c0/I'],60:['C/c1/I','N/n0/I'],120:['C/c1/I'],180:['C/c1/I']}.get(t,[])
    for task in targets:
        chosen,reason=admit(cfg,view,task)
        attempts.append([task,reason])
        if chosen:break
    return dict(request=chosen,admissions=attempts,opened=sorted(instances(cfg,view)),
                active_alarms=sorted(r['origin'] for r in live_sources(view,'alarm')),
                paid_state={name:observation(cfg,view,name)[0] for name in ('C/c0/I','N/n0/I')})
