"""Normalize dated, grouped public evidence against an ex ante joint design prior."""
from collections import defaultdict
from . import knowledge as model


def effects(pub,view,project=False):
    kinds={s['id']:s['key'] for s in pub['subjects']}
    writes={r['task']:r for r in view['writes']}
    out={}
    for q in view['issued']:
        if q['phase']!='A':continue
        received=writes.get(q['task'])
        if received and received['outcome']=='APPLIED':out[kinds[q['subject']]]=received['at']
        elif project and not received:
            # This is a forecast; later branch scoring still imposes the world's physical success conditions.
            if not any(w['task_id']==q['task'] and w['status'] in ('aborted','rejected') for w in view['work']):
                out[kinds[q['subject']]]=q['planned_end']
    return out


def collected(pub,view):
    now=view['time'];subject={s['id']:s['key'] for s in pub['subjects']}
    roots={};fixed={};paid={};conflicts=[]
    for r in view['records']:
        if r['kind']=='order' or r['copied_from'] is not None or not r['arrived']<=now<r['until']:continue
        k=(r['kind'],r['origin'],r['sampled'])
        if k in roots and (r['value'],r['subject'])!=(roots[k]['value'],roots[k]['subject']):conflicts.append(str(k))
        roots.setdefault(k,r)
    for r in view['fixed']:
        if not r['arrived']<=now<r['until'] or r['source']!='meter/'+r['field']:continue
        k='service' if r['field']=='service' else subject.get(r['field'])
        if k is None or r['origin']!=f"meter/{k}@{r['sampled']:g}":continue
        old=fixed.get(k)
        if old and r['sampled']==old['sampled'] and r['ok']!=old['ok']:conflicts.append(r['origin'])
        if old is None or r['sampled']>old['sampled']:fixed[k]=r
    completed={q['task_id']:q for q in view['work'] if q['status']=='completed'}
    for r in view['paid']:
        sid=r['subject'];a=completed.get(r['task']);fields=r['fields']
        if (not fields or a is None or r['source']!='onsite/'+sid or a['observed_at_s']!=r['sampled'] or
            r['origin']!=f"{r['task']}@{r['sampled']:g}" or not r['arrived']<=now<r['until']):continue
        k=subject[sid];code=model.decode(k,fields)
        if code=='UNKNOWN':continue
        old=paid.get(k)
        if old and r['sampled']==old[0] and code!=old[1]:conflicts.append(r['origin'])
        if old is None or r['sampled']>old[0]:paid[k]=(r['sampled'],code,r['origin'])
    return list(roots.values()),fixed,paid,conflicts


def arrival_options(w):
    if w.family in ('power_board','cooling_board'):return {360} if w.alarm=='early' else {990}
    if w.alarm=='paired':return {80}
    if w.alarm=='late':return {415} if w.family in ('water','access') else {235}
    return {20,45,80} if w.alarm=='early' else {20,80,250}


def posterior(pub,view,settings):
    base=model.catalogue(model.architecture(pub));t=view['time'];known=effects(pub,view)
    rec,fixed,paid,conflicts=collected(pub,view)
    priors=[r for r in rec if r['kind']=='prior'];alarms=[r for r in rec if r['kind']=='alarm']
    releases=[r for r in rec if r['kind']=='release'];returns=[r for r in rec if r['kind']=='status']
    typed={s['id']:s['key'] for s in pub['subjects']}
    weight=[];law=settings['channels']
    for w,mass in base:
        if conflicts:break
        ch=law[w.family];by_source={(r[0],r[1]):r for r in ch}
        if any((r.get('record_type'),r['source']) not in by_source for r in priors):continue
        prob=mass
        for j,(kind,source,pd,pn,at,delay,ttl) in enumerate(ch):
            arrival=at+delay+(960 if w.context=='delayed' else 0)
            pk=(0 if w.context=='silent' else 1 if w.context=='routine' and j==0 else pn if w.cause in model.HEALTHY else pd)
            present=any(r.get('record_type')==kind and r['source']==source and r['sampled']==at for r in priors)
            if present:
                if not arrival<=t<at+ttl:prob=0;break
                prob*=pk
            elif arrival<=t<at+ttl:prob*=1-pk
        if prob==0:continue
        if alarms:
            topic={'water':'C/c0','access':'C/c0','network':'N/n0','reserve':'N/n0',
                   'power_board':'power-board','cooling_board':'cooling-board'}[w.family]
            times=arrival_options(w)
            if any(r['subject']!=topic or r['arrived'] not in times for r in alarms):continue
            prob/=len(times)  # one source event; copies are never extra observations
        if releases and w.family=='cooling_board':
            hand=w.cause in ('normal','safe','handover')
            if any((r['value']=='HANDOVER_RELEASED')!=hand for r in releases):continue
        if returns and (w.family!='cooling_board' or any(r['sampled']!=w.fault+120 or not w.fault for r in returns)):continue
        if any(model.sample(w,k,at,known)!=val for k,(at,val,_) in paid.items()):continue
        if any(model.write_success(w,typed[r['subject']],r['at'])!=(r['outcome']=='APPLIED') for r in view['writes']):continue
        if fixed:
            # Measurements share the plant and its bottleneck. One mixture factor, without multiplying aliases or derived service by component factors.
            matches=sum(model.fixed(w,k,r['sampled'],known)==r['ok'] for k,r in fixed.items())
            reliability=settings['fixed_match_probability']
            prob*=(1-reliability)+(2*reliability-1)*matches/len(fixed)
        if prob>0:weight.append((w,prob))
    total=sum(q for _,q in weight)
    weights=[(w,q/total) for w,q in weight] if total else []
    causes=defaultdict(float);problem={}
    for w,q in weights:causes[w.family+'/'+w.cause]+=q
    opened={r['subject'] for r in view['records'] if r['kind']=='order' and r['arrived']<=t<r['until'] and r['copied_from'] is None}
    for s in pub['subjects']:
        if s['id'] not in opened:continue
        local=defaultdict(float);reasons=defaultdict(float)
        for w,q in weights:
            local[model.sample(w,s['key'],t,known)]+=q
            relevant=(s['key']=='C' and w.family in ('water','access') or
                      s['key']=='N' and w.family in ('network','reserve') or
                      w.family in ('power_board','cooling_board'))
            reasons[w.family+'/'+w.cause if relevant else 'other-domain-or-background']+=q
        problem[s['id']]={'causes':dict(sorted(reasons.items())),'predicted_local_reports':dict(sorted(local.items()))}
    evidence=dict(records=sorted({r['origin'] for r in rec}),fixed=sorted({r['origin'] for r in fixed.values()}),
                  paid=sorted(v[2] for v in paid.values()),conflicts=conflicts)
    return weights,dict(causes=dict(sorted(causes.items())),per_open_subject=problem,groups=evidence,
                        supported_worlds=len(weights),prior_worlds=len(base),model_conflict=not bool(weights))
