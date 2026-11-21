"""Declared finite *public* design prior and prediction of full-hour service/possible reports."""
from collections import defaultdict, namedtuple
from functools import lru_cache
from itertools import product
import math

H = 3600
World = namedtuple('World', 'family cause context alarm inlet demand grid fault')
HEALTHY = {'normal','safe'}


def _add(bank, family, cause, context, alarm, mass, inlets=(0,), demands=(0,), grids=(1,), faults=(0,)):
    weight = mass / (len(inlets)*len(demands)*len(grids)*len(faults))
    for t,d,g,f in product(inlets,demands,grids,faults):
        bank[World(family,cause,context,alarm,t,d,g,f)] += weight


@lru_cache(maxsize=3)
def catalogue(architecture):
    bank=defaultdict(float)
    if architecture=='ordinary':
        for family in ('water','access','network','reserve'):
            for cause,alarm in [('normal','usual'),('masked','usual'),('defect','early'),('defect','late')]:
                for variant in range(3):
                    twin=family=='network' and variant==0 and (cause=='masked' or alarm=='early')
                    context='routine' if twin else 'ordinary'
                    onset=(60,120,180) if family in ('water','access') and cause!='normal' else (0,)
                    demand=(600,) if twin else (600,900,1200) if family=='network' else (0,)
                    grid=(.25,) if twin and cause=='defect' else (.25,.5) if family in ('network','reserve') and cause=='defect' else (1,)
                    faults=(1200,1500,1800) if family=='reserve' and cause!='normal' else (0,)
                    _add(bank,family,cause,context,'paired' if twin else alarm,1/48,onset,demand,grid,faults)
    else:
        power=architecture=='power_board'
        # Multiplicities marginalize the twelve physical/information combinations in the design.
        # No realized design index, random seed or case-to-action map is present.
        cases=[('normal','ordinary','late'),('normal','routine','late'),('safe','ordinary','early'),
               ('legacy' if power else 'overload','routine','late'),
               ('path' if power else 'latch','routine','late'),
               ('legacy' if power else 'compound','ordinary','early'),
               ('legacy' if power else 'compound','silent','late'),
               ('legacy' if power else 'compound','delayed','late'),
               ('legacy' if power else 'compound','ordinary','late'),
               ('legacy' if power else 'overload','ordinary','late'),
               ('path' if power else 'handover','ordinary','late'),
               ('slow' if power else 'short_capacity','ordinary','late')]
        for cause,context,alarm in cases:
            _add(bank,architecture,cause,context,alarm,1/12,faults=(0,) if cause=='normal' else (1500,1800))
    return tuple(bank.items())


def architecture(pub):
    types={s['key'] for s in pub['subjects']}
    if 'LC' in types:return 'power_board'
    if 'NR' in types:return 'cooling_board'
    return 'ordinary'


def _at(effects,kind,t):
    return effects.get(kind,math.inf)<=t


def facts(w,t,e):
    """Expected local state at sample time under a hypothesized world and its timed actions."""
    heat=w.family in ('water','access') and w.cause!='normal' and w.inlet<=t and not w.inlet<=e.get('C',-1)<=t
    g=1 if _at(e,'N',t) else w.grid
    demand=(t>=w.demand)
    outage=w.family=='reserve' and w.cause!='normal' and w.fault<=t<w.fault+300
    effective=0 if outage or not demand else min(g,.25 if w.family=='network' and w.cause=='masked' else 1)
    return heat,g,effective


def london(w,t,e):
    ordinary=w.cause in HEALTHY
    closed=ordinary or (w.cause=='path' and _at(e,'LB',t))
    corrected=ordinary or _at(e,'LC',t)
    in_fault=bool(w.fault and w.fault<=t<w.fault+600)
    pre=e.get('LG',math.inf)
    automatic=max(w.fault,e.get('LC',math.inf)) if not ordinary else w.fault
    if not w.fault:automatic=math.inf
    # An automatic request exists only while the sensed board requires a spare.
    start=min(pre,automatic if in_fault and not closed else math.inf)
    ready=w.cause!='path' and t>=start+(360 if w.cause=='slow' else 60)
    return closed,corrected,ready,in_fault


def dutch(w,t,e):
    capacity=45 if w.cause=='short_capacity' else 120 if w.cause in ('normal','safe','latch','handover') else 70
    relocated=_at(e,'NR',t)
    group=60 if relocated else 100
    auto=w.cause in ('normal','safe','overload')
    handover=w.cause in ('normal','safe','handover')
    commissioned=w.cause in HEALTHY or (handover and _at(e,'NC',t))
    active=bool(w.fault and t>=w.fault)
    returned=active and t>=w.fault+120
    restart=e.get('NP',math.inf)
    pump=not active or (returned and (auto or (w.cause!='handover' and w.fault+120<=restart<=t)))
    tripped=active and not returned and (60 if _at(e,'NR',w.fault) else 100)>capacity
    return group,capacity,auto,handover,commissioned,pump,returned,tripped


def sample(w,k,t,e):
    heat,g,n=facts(w,t,e)
    if k=='C':return 'LOW' if heat else 'OK'
    if k=='N':return 'CONFIG' if g<1 else 'LIMIT' if n<1 else 'OK'
    if k in ('LC','LB','LG'):
        closed,corrected,ready,_=london(w,t,e)
        if k=='LC':return 'CONTACT' if corrected else 'UPSTREAM'
        if k=='LB':return 'CLOSED' if closed else 'RELEASED' if w.cause=='path' else 'ISOLATED'
        return 'READY' if ready else 'IDLE'
    group,cap,auto,hand,comm,pump,returned,_=dutch(w,t,e)
    if k=='NR':return 'TOO_SMALL' if cap<60 else 'OVER' if group>cap else 'OK'
    if k=='NC':return 'COMMISSIONED' if comm else 'HANDOVER' if hand else 'IN_WORKS'
    if k=='NP':return ('AUTO' if auto else 'MANUAL')+('/RUN' if pump else '/LATCH')+('/RETURN' if returned else '')
    raise ValueError(k)


def decode(k,f):
    if not f:return 'UNKNOWN'
    if k=='C':return 'LOW' if f['q']<.08 else 'OK' if .099<=f['q']<=.101 else 'UNKNOWN'
    if k=='N':return 'CONFIG' if f['g']<1 else 'LIMIT' if f['e']<1 else 'OK'
    if k=='LC':
        v=set(f['versions'])
        return 'CONTACT' if v=={'SHARED_CONTACT'} else 'UPSTREAM' if v=={'SHARED_UPSTREAM'} else 'UNKNOWN'
    if k=='LB':return 'CLOSED' if f['contact'] and f['upstream'] else 'RELEASED' if f['released'] else 'ISOLATED'
    if k=='LG':return 'READY' if f['ready'] and f['permitted'] else 'IDLE'
    if k=='NR':return 'TOO_SMALL' if f['transfer_kW']<60 else 'OVER' if f['group_kW']>f['transfer_kW'] else 'OK'
    if k=='NC':return 'COMMISSIONED' if f['commissioned'] else 'HANDOVER' if f['handover'] else 'IN_WORKS'
    if k=='NP':return ('AUTO' if f['automatic_restart'] else 'MANUAL')+('/RUN' if f['running'] else '/LATCH')+('/RETURN' if f['power_returned'] else '')
    return 'UNKNOWN'


def add_interval(rows,start,end,fraction=1):
    a=max(0,start);b=min(H,end)
    if a<b and fraction>0:rows.append((a,b,fraction))


@lru_cache(maxsize=16384)
def curve(w, effect_tuple):
    e=dict(effect_tuple);r=[];f=w.family
    if f in ('water','access'):
        if w.cause=='masked':add_interval(r,0,H)
        elif w.cause=='defect':
            trip=w.inlet+900
            clean=e.get('C',math.inf)
            if not w.inlet<=clean<=trip:add_interval(r,trip,clean+120 if clean>trip else H,.625)
    elif f in ('network','reserve'):
        if w.cause=='masked' and f=='network':add_interval(r,w.demand,H,.75)
        if w.grid<1:add_interval(r,w.demand,e.get('N',H),1-w.grid)
        if f=='reserve' and w.fault:add_interval(r,w.fault,w.fault+300)
    elif f=='power_board' and w.cause not in HEALTHY:
        tf=w.fault;restore=tf+600
        if w.cause=='path':restore=min(restore,max(tf,e.get('LB',math.inf)))
        else:
            lag=360 if w.cause=='slow' else 60
            restore=min(restore,max(tf,e.get('LG',math.inf)+lag),max(tf,e.get('LC',math.inf))+lag)
        expiry=tf+(120 if w.cause=='slow' else 180)
        if restore>expiry:add_interval(r,expiry,restore+120)
    elif f=='cooling_board' and w.fault:
        tf=w.fault;tr=tf+120
        _,_,auto,hand,_,_,_,tripped=dutch(w,tf,e)
        if tripped:add_interval(r,tf,tr)
        if w.cause not in HEALTHY:
            restored=tr if auto else math.inf
            if hand:restored=min(restored,e.get('NC',math.inf))
            if w.cause!='handover' and e.get('NP',-1)>=tr:restored=min(restored,e['NP'])
            if restored>tf+300:add_interval(r,tf+300,restored+60)
    return tuple(r)


@lru_cache(maxsize=16384)
def loss(w,effect_tuple):
    segments=curve(w,effect_tuple)
    knots=sorted({t for a,b,v in segments for t in (a,b)})
    return sum((b-a)*max(v for x,y,v in segments if x<=a<y)
               for a,b in zip(knots,knots[1:]) if any(x<=a<y for x,y,_ in segments))


def fixed(w,k,t,e):
    if k=='service':
        return t>=w.demand and not any(a<=t<b and v>0 for a,b,v in curve(w,tuple(sorted(e.items()))))
    if k in ('C','N'):
        heat,_,n=facts(w,t,e)
        return not heat if k=='C' else n>=1
    if k in ('LC','LB','LG'):
        closed,_,ready,infault=london(w,t,e)
        if k=='LB':return closed
        if k=='LG':return ready
        expiry=w.fault+(120 if w.cause=='slow' else 180)
        return not infault or closed or ready or t<expiry
    _,_,_,_,commissioned,pump,_,tripped=dutch(w,t,e)
    return not tripped if k=='NR' else pump if k=='NP' else commissioned


def write_success(w,k,t):
    if k=='LB':return w.cause=='path'
    if k=='NC':return w.cause in ('normal','safe','handover')
    if k=='NP':return bool(w.fault and t>=w.fault+120 and w.cause not in ('normal','safe','overload','handover'))
    return True
