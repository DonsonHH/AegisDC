"""Preregistered opposite-half selection, recovery and rank-transfer estimators."""
from itertools import combinations, product
import hashlib
import numpy as np


def interval(values):
    lo,hi=np.percentile(values,[5,95],method="linear")
    return dict(mean=float(np.mean(values)),lo=float(lo),hi=float(hi))


def ordered_ranks(values):
    x=np.asarray(values,dtype=float)
    ordered=np.argsort(x,kind="stable")
    ranks=np.empty_like(x)
    start=0
    while start<len(ordered):
        finish=start+1
        while finish<len(ordered) and x[ordered[finish]]==x[ordered[start]]:
            finish+=1
        ranks[ordered[start:finish]]=(start+1+finish)/2
        start=finish
    return ranks


def spearman(left,right):
    a,b=ordered_ranks(left),ordered_ranks(right)
    if np.ptp(a)==0 or np.ptp(b)==0:
        return None
    return float(np.corrcoef(a,b)[0,1])


def winners(selection, groups):
    # Sorting numeric indices fixes ties by original accepted label, independent of the evaluated half.
    sorted_groups=np.sort(groups,axis=1)
    return np.take_along_axis(sorted_groups,np.argmin(selection[sorted_groups],axis=1)[:,None],axis=1)[:,0]


def selected_subsets(a,b,family_ids,sizes):
    result={}
    families=sorted(set(family_ids))
    for size in sizes:
        menus=[list(combinations([i for i,f in enumerate(family_ids) if f==fam],size)) for fam in families]
        scored=[]
        choices=[]
        for cells in product(*menus):
            ids=[i for cell in cells for i in cell]
            means=a[:,ids].mean(axis=1)
            first=int(np.argmin(means))
            choices.append(first)
            scored.append(float(b[first]))
        result[str(size*len(families))]=dict(subsets=len(scored),target_L=interval(scored),
            winners={str(k):choices.count(k) for k in sorted(set(choices))})
    return result


def verdict(r6,r24):
    if r6 is None or r24 is None:
        return "INDETERMINATE"
    if r6>=0.8:
        return "TOO_EASY"
    if r6<0.6 and r24>=r6+0.15:
        return "SEARCH_HEADROOM"
    return "UNCERTAIN"


def curves(mean_a,mean_b,base,oracle,settings,rng):
    n=len(mean_a)
    permutations=np.array([rng.permutation(n) for _ in range(settings["repetitions"])])
    both_valid=all(oracle[h] is not None and base[h] is not None and base[h]>oracle[h] for h in ("A","B"))
    answer={};samples={}
    for k in settings["k"]:
        bag=permutations[:,:k]
        take_a=winners(mean_a,bag)
        take_b=winners(mean_b,bag)
        test_b=mean_b[take_a];test_a=mean_a[take_b]
        values={}
        for direction,h,v in (("A_to_B","B",test_b),("B_to_A","A",test_a)):
            denom=None if oracle[h] is None or base[h] is None else base[h]-oracle[h]
            values[direction]=dict(target_L=interval(v),denominator=denom,
                 recovered=None if denom is None or denom<=0 else interval((base[h]-v)/denom))
        pooled=(test_a+test_b)/2
        fractions=None
        if both_valid:
            fractions=((base["A"]-test_a)+(base["B"]-test_b))/((base["A"]-oracle["A"])+(base["B"]-oracle["B"]))
            samples[k]=fractions
        values["pooled"]=dict(target_L=interval(pooled),recovered=interval(fractions) if fractions is not None else None)
        answer[str(k)]=values
    gain=interval(samples[24]-samples[6]) if 6 in samples and 24 in samples else None
    r6=answer.get("6",{}).get("pooled",{}).get("recovered")
    r24=answer.get("24",{}).get("pooled",{}).get("recovered")
    status=verdict(r6["mean"] if r6 else None,r24["mean"] if r24 else None)
    return dict(curves=answer,delta_24_minus_6=gain,decision=status,
                permutation_sha256=hashlib.sha256(permutations.astype("<i4").tobytes()).hexdigest())


def selfcheck():
    a=np.array([1.,1.,2.])
    b=np.array([9.,4.,3.])
    bags=np.array([[1,0],[2,1],[2,0]])
    assert list(winners(a,bags))==[0,1,0] and list(winners(b,bags))==[1,2,2]
    assert np.allclose(ordered_ranks([3,1,1]),[3,1.5,1.5])
    assert spearman([4,4,4],[1,2,3]) is None and abs(spearman([1,2,3],[3,2,1])+1)<1e-12
    assert verdict(0.8,0.8)=="TOO_EASY" and verdict(0.60,1)=="UNCERTAIN" and verdict(0.50,0.65)=="SEARCH_HEADROOM"
    assert verdict(None,0.8)=="INDETERMINATE"
    trial=curves(a,b,{"A":5,"B":12},{"A":1,"B":2},dict(k=[3],repetitions=7),np.random.default_rng(14))
    g=trial["curves"]["3"]
    assert g["A_to_B"]["target_L"]["mean"]==9 and g["B_to_A"]["target_L"]["mean"]==2
    assert abs(g["pooled"]["recovered"]["mean"]-6/14)<1e-12
    return {"one_sided_selection":True,"tie_order":True,"average_ranks":True,"pooled_denominator":True,"branch_boundaries":True}
