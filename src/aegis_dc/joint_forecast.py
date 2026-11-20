"""Time-anchored joint physical hypotheses used only for ranking public options."""
from fractions import Fraction
from itertools import product
from math import isclose, sqrt
from .joint_evidence import observation, own_ack


def state_at(world, time, effects):
    cooling=world['cooling'];g=Fraction(world['g']);cleaned=None
    for task,at in sorted(effects.items(),key=lambda x:(x[1],x[0])):
        if at>time:continue
        if task.startswith('C/') and cooling=='F':
            cleaned=at if cleaned is None else min(cleaned,at)
        elif task.startswith('N/'):g=Fraction(1)
    q=.1 if cooling=='C0' or cleaned is not None else sqrt(1/340) if cooling=='F' else 0
    return cooling,cleaned,g,q


def signals(world,time,effects,window):
    cooling,cleaned,g,q=state_at(world,time,effects)
    enabled=(time<window[0] or cooling=='C0' or
             (cooling=='F' and cleaned is not None and time>=cleaned+2))
    s=Fraction(world['s']);a=Fraction(world['A'])
    requests=[2000000*int(enabled),100000*min(1,g),100000*min(1,s)]
    total=sum(requests);ratio=min(Fraction(1),a/total) if total else Fraction(1)
    e=min(g,ratio*requests[1]/100000)
    y=min(Fraction(1),int(enabled)*ratio,e,s,ratio*requests[2]/100000)
    return dict(q=q,g=g,e=e,lake=q*998,network=e,service=y)


def deficit(cfg,world,effects):
    a,b=cfg['forecast_window']
    breaks={a,b}
    for task,t in effects.items():
        if a<t<b:breaks.add(t)
        if task.startswith('C/') and a<t+2<b:breaks.add(t+2)
    t=sorted(breaks)
    return sum((Fraction(y-x)*(1-signals(world,x,effects,cfg['forecast_window'])['service'])
                for x,y in zip(t,t[1:])),Fraction(0))


def inside(value,interval):
    lo,hi=interval;v=float(value)
    # Compare the same zero-error physical value across binary64 and exact arithmetic.
    return (lo<=v or isclose(v,lo,rel_tol=2e-15,abs_tol=1e-15)) and (v<=hi or isclose(v,hi,rel_tol=2e-15,abs_tol=1e-15))


def support(cfg,view,prefix):
    groups={}
    disputed=False
    for issue in view['issued']:
        task=issue['task']
        if not task.endswith(('/I','/R')):continue
        category,fields=observation(cfg,view,task)
        if category=='CONFLICT':disputed=True
        if not fields:continue
        ack=own_ack(cfg,view,task)
        groups[('paid',task,ack['at'])]=list(fields.items())
    for row in view['fixed']:
        if row['until']<=view['time'] or row['interval'] is None:continue
        if row['source']!='fixed-'+row['field']:continue
        key=('fixed',row['source'],row['at'])
        groups.setdefault(key,[]).append((row['field'],row['interval']))
    # One coherent unresolved-outcome assignment across every sample in the history.
    tasks=sorted(prefix['pending'])
    compatible=[]
    for world in cfg['worlds']:
        for bits in product((False,True),repeat=len(tasks)):
            effects=dict(prefix['confirmed'])
            effects.update({task:prefix['pending'][task] for task,yes in zip(tasks,bits) if yes})
            if all(all(inside(sig[field],interval) for field,interval in data)
                   for (_,_,t),data in groups.items()
                   for sig in [signals(world,t,effects,cfg['forecast_window'])]):
                compatible.append(world);break
    return [] if disputed else compatible


def observe_branch(cfg,world,probe,time,effects):
    kind=probe.split('/')[0]
    simulated=signals(world,time,effects,cfg['forecast_window'])
    rights=cfg['types'][kind]['read']
    return tuple((f,str(simulated[f])) for f,period in sorted(rights.items())
                 if period and period[0]<=time<period[1])


def permits_correction(kind,signature):
    vals=dict(signature)
    if kind=='C':return 'q' in vals and float(vals['q'])<.08
    return 'g' in vals and 'e' in vals and Fraction(vals['g'])<1 and Fraction(vals['e'])<=Fraction(vals['g'])
