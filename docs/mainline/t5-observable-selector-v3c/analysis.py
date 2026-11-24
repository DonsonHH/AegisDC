"""Cross-fitted development estimates. No facility or private-state imports."""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from math import isfinite
from statistics import mean

import numpy as np
from selector import select

ROLES=tuple(f"Q{i:02}" for i in range(1,49))+("B_COST","V_COST","M","M_HOT","MAIN-U-1","MAIN-U-2","MAIN-U-3","MAIN-R-1","MAIN-R-2","MAIN-R-3")
FAMILIES=("WATER_HEAT","NETWORK_POWER","RESERVE_TRANSFER","COOLING_ACCESS","LONDON","NETHERLANDS")


def need(ok,message):
    if not ok:
        raise ValueError(message)


def winner(keys,losses,roles=ROLES):
    need(keys and all(isfinite(losses[k][l]) for k in keys for l in roles),"complete finite comparison")
    return min(roles,key=lambda r:sum(Fraction(losses[k][r]) for k in keys))


def fit(keys,cells,losses,roles=ROLES):
    w=winner(keys,losses,roles)
    groups={}
    for k in keys:
        groups.setdefault(cells[k],[]).append(k)
    return dict(winner=w,cells={c:winner(ks,losses,roles) for c,ks in groups.items() if len(ks)>=2},
                training_counts={c:len(ks) for c,ks in groups.items()})


def interval(rows,field,sides,stage):
    delta=np.asarray([[r[field] for r in rows if r["family"]==f] for f in FAMILIES],dtype=float)
    need(delta.shape==(6,6) and np.isfinite(delta).all(),"six paired values in each of six families")
    salt="AegisDC/T5-v3c/paired/"+stage+"/v1"
    rng=np.random.Generator(np.random.PCG64(int.from_bytes(sha256(salt.encode("ascii")).digest(),"big")))
    draw=rng.integers(0,6,(10000,6,6))
    boot=delta[np.arange(6)[None,:,None],draw].mean(axis=(1,2))
    return dict(mean=float(delta.mean()),lower=None if sides==1 else float(np.quantile(boot,.025,method="linear")),
                upper=float(np.quantile(boot,.95 if sides==1 else .975,method="linear")),sides=sides,repetitions=10000)


def aggregate(rows):
    return {a:mean(r[a] for r in rows) for a in ("S_gap","W_gap","F_gap","delta")}


def development(order,cases,cell_tuples):
    losses={k:{l:cases[k]["arms"][l]["L"] for l in ROLES} for k in order}
    minima={k:cases[k]["minimum"]["certified_min"] for k in order}
    need(all(t is not None and isfinite(t) for t in minima.values()),"all 36 certified bounds")
    cells={k:"|".join(cell_tuples[k]) for k in order}
    rows=[];directions={}
    for left,right in (("A","B"),("B","A")):
        tag=left+"→"+right;train=[k for k in order if cases[k]["half"]==left];test=[k for k in order if cases[k]["half"]==right]
        need(len(train)==len(test)==18 and set(train).isdisjoint(test),"opposite halves")
        locked=fit(train,cells,losses)
        eval_counts=Counter(cells[k] for k in test)
        report={}
        for c in sorted(set(eval_counts)|set(locked["training_counts"])):
            n=locked["training_counts"].get(c,0)
            report[c]=dict(training=n,evaluation=eval_counts[c],chosen=locked["cells"].get(c,locked["winner"]),fallback=n<2)
        oracle_family={f:winner([k for k in train if cases[k]["family"]==f],losses) for f in FAMILIES}
        for k in test:
            f=cases[k]["family"];s=select(locked,cell_tuples[k]);w=locked["winner"];g=oracle_family[f];l=losses[k]
            rows.append(dict(key=k,direction=tag,cell=cells[k],family=f,selector=s,whole=w,informed=g,
                        fallback=report[cells[k]]["fallback"],lower=minima[k],S_L=l[s],W_L=l[w],F_L=l[g],
                        S_gap=l[s]-minima[k],W_gap=l[w]-minima[k],F_gap=l[g]-minima[k],delta=l[s]-l[w]))
        subset=[r for r in rows if r["direction"]==tag]
        directions[tag]=dict(whole=locked["winner"],cells=report,family_reference=oracle_family,means=aggregate(subset),
                             fallback_cells=sum(x["fallback"] for x in report.values()),
                             evaluation_fallback_cells=sum(x["fallback"] and x["evaluation"]>0 for x in report.values()),
                             fallback_rows=sum(r["fallback"] for r in subset))
    primary=interval(rows,"delta",1,"stage0")
    return dict(gate1="PASS" if primary["upper"]<0 else "FAIL_STOP",primary=primary,means=aggregate(rows),directions=directions,
                families={f:aggregate([r for r in rows if r["family"]==f]) for f in FAMILIES},rows=rows,
                family_reference_from_request=120.37,whole_reference_from_request=226.01)
