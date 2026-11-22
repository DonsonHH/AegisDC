"""Predict the joint service deficit in a hypothesized world, before the plant is called."""
from functools import lru_cache
from aegis_risk_dispatch import knowledge as k


def locally_needed(world,kind,t,prior):
    if kind=='C':return k.facts(world,t,prior)[0]
    if kind=='N':return k.facts(world,t,prior)[1]<1
    if kind in ('LC','LB','LG'):
        closed,corrected,_,_=k.london(world,t,prior)
        if kind=='LC':return not corrected
        if kind=='LB':return not closed and world.cause=='path'
        return not closed and world.cause!='path' and 'LG' not in prior
    group,cap,_,handover,commissioned,pump,returned,_=k.dutch(world,t,prior)
    if kind=='NR':return group>cap
    if kind=='NP':return returned and not pump
    if kind=='NC':return handover and not commissioned
    raise ValueError(kind)


@lru_cache(maxsize=32768)
def loss(world,applied,duration,capacity):
    if not duration or not applied:return k.loss(world,applied)
    previous={}
    segments=list(k.curve(world,applied))
    for kind,t in sorted(applied,key=lambda z:z[1]):
        if not locally_needed(world,kind,t,previous):
            # The native joint service is the minimum across constraints, with no loss at zero demand.
            begin=max(t,world.demand);end=min(3600,t+duration)
            if begin<end:segments.append((begin,end,1-capacity))
        previous[kind]=t
    knots=sorted({t for a,b,_ in segments for t in (a,b)})
    return sum((b-a)*max((v for x,y,v in segments if x<=a<y),default=0)
               for a,b in zip(knots,knots[1:]))
