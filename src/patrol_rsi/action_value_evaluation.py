"""Frozen OOF diagnostics, honest Pareto pair coverage, no scalar business utility."""
from itertools import combinations
import math
import numpy as np

from .action_value_learning import weights,HEADS
from .action_value_data import objective,dominates


def head_errors(rows,predictions):
    out={}
    for h,name in enumerate(HEADS):
        items=[(r,p) for r,p in zip(rows,predictions) if r['y'][h] is not None]
        def measure(items):
            if not items:return {'n':0,'mae':None,'rmse':None}
            w=weights([r for r,_ in items]);error=np.asarray([p[h]-r['y'][h] for r,p in items])
            return {'n':len(items),'mae':float(np.sum(w*abs(error))),'rmse':float(np.sqrt(np.sum(w*error**2)))}
        changed=[(r,p) for r,p in items if abs(r['y'][h])>1e-9]
        signs={}
        sign=lambda v:-1 if v<-1e-9 else 1 if v>1e-9 else 0
        for r,p in items:
            key=f"{sign(r['y'][h])}->{sign(p[h])}";signs[key]=signs.get(key,0)+1
        out[name]={'all_valid':measure(items),'changed_labels':measure(changed),'direction_counts':signs}
    return out


def pair_rankings(rows,predictions):
    roots={r['root_id'] for r in rows};by_id={r['sample_id']:p for r,p in zip(rows,predictions)};out={}
    for method in ('ridge','zero','H'):
        pairs=[];counts={'correct':0,'reversed':0,'undistinguished':0}
        for root in sorted(roots):
            own=[r for r in rows if r['root_id']==root]
            for a,b in combinations(own,2):
                av,bv=objective(a['y']),objective(b['y'])
                if dominates(bv,av):a,b=b,a
                elif not dominates(av,bv):continue
                if method=='H':
                    difference=a['H_preference']-b['H_preference']
                    result='correct' if difference>1e-9 else 'reversed' if difference<-1e-9 else 'undistinguished'
                else:
                    pa=by_id[a['sample_id']] if method=='ridge' else [0.]*4
                    pb=by_id[b['sample_id']] if method=='ridge' else [0.]*4
                    if a['y'][1] is None:pa=[pa[0],None,pa[2],pa[3]];pb=[pb[0],None,pb[2],pb[3]]
                    va,vb=objective(pa),objective(pb)
                    result='correct' if dominates(va,vb) else 'reversed' if dominates(vb,va) else 'undistinguished'
                counts[result]+=1;pairs.append({'group_id':a['group_id'],'root_id':root,'result':result})
        if pairs:
            w=weights(pairs);mass={name:float(sum(ww for p,ww in zip(pairs,w) if p['result']==name)) for name in counts}
            coverage=mass['correct']+mass['reversed']
            summary={'comparable_pairs':len(pairs),'raw_counts':counts,'weighted_mass':mass,'ordered_coverage':coverage,
                'conditional_accuracy':mass['correct']/coverage if coverage else None,'all_comparable_correct_fraction':mass['correct'],
                'undistinguished_fraction':mass['undistinguished']}
        else:summary={'comparable_pairs':0,'raw_counts':counts,'ordered_coverage':None,'conditional_accuracy':None,'all_comparable_correct_fraction':None}
        out[method]=summary
    return out
