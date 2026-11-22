"""U sees paired paid development returns, immutable descriptors and its previous search state."""
from copy import deepcopy
import hashlib
import math
from statistics import mean

import numpy as np

from .space import batch_anchor, check, descriptor_id, initial

MEASURES = ("L","person","tool","fee")


def roots(space,u,track):
    parent=initial(space,track)
    batch=[dict(operator=op,theta=batch_anchor(space,track,patch)) for op,patch in
           zip(u["proposal"]["first_batch"][track],u["proposal"]["first_batch_levels"][track],strict=True)]
    return dict(track=track,round=1,parent=parent,incumbent=descriptor_id(parent),
                proposals=batch,seen=[descriptor_id(parent),*(descriptor_id(p["theta"]) for p in batch)],
                credit={op:{"n":0,"sum":0.0} for op in u["proposal"]["operators"][track]},
                no_gain=0,history=[],terminal=None)


def mutation(space,u,track,parent,op,rng):
    theta=deepcopy(parent)
    names=u["proposal"]["mutation_groups"][op]
    kinds=space["action_kinds"]
    for name in names:
        if name in theta["global"]:
            levels=space["global_parameters"][name]["levels"]
            possibilities=[v for v in levels if v!=theta["global"][name]]
            theta["global"][name]=possibilities[int(rng.integers(len(possibilities)))]
        else:
            n=len(kinds) if rng.random()<u["proposal"]["all_subjects_probability"] else int(rng.choice(u["proposal"]["edited_subject_counts"]))
            chosen=[kinds[int(i)] for i in rng.choice(len(kinds),size=n,replace=False)]
            for k in chosen:
                levels=[v for v in space["subject_parameters"][name]["levels"] if v!=theta["subjects"][k][name]]
                theta["subjects"][k][name]=levels[int(rng.integers(len(levels)))]
    check(space,track,theta)
    return theta


def next_batch(space,u,track,parent,credits,seen,round_no):
    pref=u["proposal"]
    order=pref["operators"][track]
    total=sum(z["n"] for z in credits.values())
    rng=np.random.Generator(np.random.PCG64(int.from_bytes(
        hashlib.sha256(f'{pref["generator_seed_text"]}|{track}|{round_no}'.encode()).digest()[:16],"big")))
    def expected(op):
        entry=credits[op]
        return entry["sum"]/max(1,entry["n"])+u["exploration_s"]*math.sqrt(math.log(1+total)/(1+entry["n"]))
    ranked=sorted(order,key=lambda x:(-expected(x),order.index(x)))
    batch=[]
    for index in range(u["candidates_per_round"]):
        for tries in range(pref["max_unique_attempts"]):
            op=order[int(rng.integers(len(order)))] if rng.random()<pref["random_probability"] else ranked[(index+tries)%len(ranked)]
            theta=mutation(space,u,track,parent,op,rng)
            token=descriptor_id(theta)
            if token not in seen:
                batch.append(dict(operator=op,theta=theta))
                seen.add(token)
                break
        else:
            return None
    return batch


def update(space,u,state,feedback):
    tracked=state["track"]
    seen=set(state["seen"])
    parent=state["incumbent"]
    options=state["proposals"]
    descriptors={descriptor_id(q["theta"]):q for q in options}
    keep=deepcopy(state)
    enough=u["minimum_successful_fit_cases"]
    if set(feedback)!={parent,*descriptors}:
        raise ValueError("Unexpected paid feedback descriptor")
    fit_identity=set(feedback[parent])
    valid=True
    for scores in feedback.values():
        if set(scores)!=fit_identity or len(scores)!=enough:
            raise ValueError("Fit pair identities")
        if any(not r["paid"] or r["status"]!="SCORED" for r in scores.values()):
            valid=False
    if not valid:
        keep["terminal"]="INCOMPLETE_PAID_PANEL"
        keep["history"].append(dict(round=state["round"],status="INCOMPLETE_PAID_PANEL",
                                    incumbent=parent,charged=sum(len(x) for x in feedback.values())))
        return keep
    totals={arm:{k:mean(vals[key][k] for key in sorted(fit_identity)) for k in MEASURES}
            for arm,vals in feedback.items()}
    selection=min(descriptors,key=lambda k:(totals[k]["L"],totals[k]["person"],totals[k]["tool"],totals[k]["fee"],k))
    chosen=parent
    for key,p in descriptors.items():
        label=p["operator"]
        credit=keep["credit"][label]
        credit["n"]+=1
        credit["sum"]+=max(u["proposal"]["credit_floor_s"],totals[parent]["L"]-totals[key]["L"])
    if totals[parent]["L"]-totals[selection]["L"]>=u["objective"]["min_gain_s"]:
        chosen=selection
        keep["parent"]=descriptors[selection]["theta"]
        keep["no_gain"]=0
    else:
        keep["no_gain"]+=1
    keep["incumbent"]=chosen
    keep["history"].append(dict(round=state["round"],status="PAID_COMPLETE",incumbent=chosen,
                                previous=parent,initial_or_prior_paid_metrics=totals[parent],scores=totals))
    if state["round"]>=u["fit_rounds"] or keep["no_gain"]>=u["patience_rounds"]:
        keep["terminal"]="ROUNDS_COMPLETE" if state["round"]>=u["fit_rounds"] else "PATIENCE"
        return keep
    round_no=state["round"]+1
    keep["round"]=round_no
    batch=next_batch(space,u,tracked,keep["parent"],keep["credit"],seen,round_no)
    if batch is None:
        keep["terminal"]="REGISTERED_NEIGHBORHOOD_EXHAUSTED"
    else:
        keep["proposals"]=batch
        keep["seen"]=sorted(seen)
    return keep
