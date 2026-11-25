"""The bounded descriptor/AST language shared by O and R; no facility dependency."""

from copy import deepcopy
from itertools import product
import hashlib
import json
import math

CELLS=("DIRECT_NEAR","ALARM_NEAR","ORDER_NEAR","DIRECT_FAR","ALARM_FAR","ORDER_FAR")
LEVELS=(0,30,60,120)
ZERO=(0,)*6
BASE={"op":"base"}
CATALOG=tuple(product(range(4),repeat=6))


def require(ok, why):
    if not ok:raise ValueError(why)


def canonical(x):
    return json.dumps(x,sort_keys=True,ensure_ascii=True,separators=(",",":"),allow_nan=False).encode()


def fingerprint(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def validate_levels(x):
    require(isinstance(x,(list,tuple)) and len(x)==len(CELLS) and
            all(type(v) is int and 0<=v<len(LEVELS) for v in x),"invalid policy descriptor")
    return tuple(x)


def policy_id(levels, design_sha, parent_bundle):
    return fingerprint({"design_sha256":design_sha,"parent_bundle_sha256":parent_bundle,"levels":validate_levels(levels)})


def changed(a,b):
    return [c for c,x,y in zip(CELLS,a,b,strict=True) if x!=y]


def macro(cell, direction):
    require(cell in CELLS and type(direction) is int and direction in (-1,1),"invalid credited edit")
    mate=CELLS[(CELLS.index(cell)+3)%6]
    return {"op":"emit_then","productions":[{"op":"step_pair","cells":[cell,mate],"step":direction},
            {"op":"step","cell":mate,"step":direction},{"op":"step","cell":cell,"step":direction}],"then":{"op":"base"}}


def roster(ast, incumbent, seen, round_no, k):
    """Enumerate the complete common grammar, preserving actual exclusion and macro evidence."""
    x=validate_levels(incumbent)
    require(x in seen and 1<=round_no<=4 and k==4,"unregistered search quantities/state")
    rotation=tuple((round_no-1+i)%6 for i in range(6))
    def order(y):
        edits=tuple(i for i,c in enumerate(rotation) if x[c]!=y[c])
        return (len(edits),sum(abs(a-b) for a,b in zip(x,y)),edits,tuple(y[c] for c in rotation))
    logs=[];emitted=[]
    if ast!=BASE:
        steps=ast["productions"]
        require(ast==macro(steps[0]["cells"][0],steps[0]["step"]),"unregistered proposal AST")
        for step in steps:
            v=list(x)
            cells=step["cells"] if step["op"]=="step_pair" else [step["cell"]]
            for c in cells:v[CELLS.index(c)]+=step["step"]
            candidate=tuple(v)
            if min(v)<0 or max(v)>3: reason="OUT_OF_RANGE"
            elif candidate in seen or candidate in emitted:reason="SEEN"
            else:
                emitted.append(candidate)
                reason="EMITTED"
            logs.append({"production":step,"levels":v,"result":reason})
    macro_set=set(emitted)
    ordered=sorted((y for y in CATALOG if y not in seen),key=order)
    final=(emitted+[y for y in ordered if y not in macro_set])[:k]
    require(len(final)==k and len(set(final))==k and not set(final)&seen,"insufficient structural proposals")
    return final,{"catalogue_size":len(CATALOG),"excluded_seen_count":len(seen),
                  "excluded_seen_sha256":fingerprint(sorted(seen)),"macro":logs,
                  "base_duplicate_levels_suppressed":[list(y) for y in ordered if y in macro_set]}


def rank_and_rewrite(arm, round_no, old, incumbent, baseline, candidates, returns):
    """Only complete admissible FIT packets are eligible. Tie at incumbent loss keeps it."""
    eligible=[i for i,p in enumerate(returns) if p["hard_violations"]==0]
    eligible.sort(key=lambda i:(returns[i]["L_sum_us"],returns[i]["person_sum_us"],candidates[i]))
    better=[i for i in eligible if returns[i]["L_sum_us"]<baseline["L_sum_us"]]
    winner=better[0] if better else None
    single=next((i for i in better if len(changed(incumbent,candidates[i]))==1),None)
    credit=None
    if single is not None:
        cell=changed(incumbent,candidates[single])[0];idx=CELLS.index(cell)
        direction=1 if candidates[single][idx]>incumbent[idx] else -1
        credit={"slot":single+1,"cell":cell,"direction":direction,"incumbent_L_sum_us":baseline["L_sum_us"],
                "candidate_L_sum_us":returns[single]["L_sum_us"],
                "candidate_minus_incumbent_L_sum_us":returns[single]["L_sum_us"]-baseline["L_sum_us"],
                "feedback_receipt":returns[single]["receipt"]}
    if round_no==4:return eligible,winner,old,"TERMINAL",None
    if arm=="O":return eligible,winner,old,"O_PROGRAM_FIXED",credit
    if credit is None:return eligible,winner,old,"NO_BENEFICIAL_SINGLE_EDIT",None
    new=macro(credit["cell"],credit["direction"])
    return eligible,winner,new,("SAME_PRODUCTION" if new==old else "INSTALLED_CREDITED_PRODUCTION"),credit


def public_decision(levels, pub, view, parent_call, gate, validate):
    """A child may choose an already-priced public branch after the original parent waits."""
    idx=validate_levels(levels)
    validate(pub,view)
    parent=parent_call(pub,view)
    why=parent.get("rationale",{})
    if idx==ZERO or parent["request"] is not None or why.get("reason")!="VALUE":return parent
    choices=why.get("continuation_table",[])
    wait=next((v for v in choices if v["first"] is None and v["admitted_continuation_plans"]>0),None)
    if wait is None:return parent
    now=view["time"]; options=[]
    subjects={s["id"]:s for s in pub["subjects"]}
    for branch in choices:
        first=branch["first"]
        if not first or first[1]!="A" or branch["admitted_continuation_plans"]<=0:continue
        sid=first[0]
        if sid not in pub["routes"] or sid not in subjects:continue
        s=subjects[sid]
        req,reason=gate.admit(pub,view,s,"A")
        if not req or reason!="ALLOW":continue
        orders=[r for r in gate.live(view,"order") if r["subject"]==sid]
        if not orders:continue
        paid=[r for r in gate.each_read(view,sid) if r["phase"]=="I" and r["arrived"]<=now<r["until"]
              and r["source"]=="onsite/"+sid and r["origin"]==r["task"]+"@"+format(r["sampled"],"g")
              and gate.actionable(s["key"],r["fields"])]
        fixed=[r for r in view["fixed"] if r["field"]==sid and r["source"]=="meter/"+sid and
               r["sampled"]<=r["arrived"]<=now and r["origin"]=="meter/"+s["key"]+"@"+format(r["sampled"],"g")]
        latest=[r for r in fixed if r["sampled"]==max(v["sampled"] for v in fixed)]
        bad_meter=bool(latest) and all(now<r["until"] and r["ok"] is False for r in latest)
        alarms=[r for r in gate.live(view,"alarm") if now>r["arrived"] and r["subject"] in (sid,"power-board","cooling-board")]
        evidence="DIRECT" if paid or bad_meter else "ALARM" if alarms else "ORDER"
        finish=req["planned_end"]
        slack=min(max(r["until"] for r in orders)-now,s["write_window"][1]-finish,
                  pub["workforce"]["shifts"][s["worker"]][1]-finish,3600-finish-pub["latency"])
        cell=evidence+("_NEAR" if slack<=180 else "_FAR")
        allowance=LEVELS[idx[CELLS.index(cell)]]
        if not all(math.isfinite(v) for v in (*wait["vector"],*branch["vector"])):continue
        gain=wait["vector"][0]-branch["vector"][0]
        extra=max(0,branch["vector"][3]-wait["vector"][3])
        if allowance and gain>0 and extra<=allowance:
            support=paid+(latest if bad_meter else []) if evidence=="DIRECT" else alarms if evidence=="ALARM" else orders
            options.append(((-gain,extra,slack,pub["routes"].index(sid),sid),req,cell,[r["origin"] for r in support]))
    if not options:return parent
    _,req,cell,support=min(options,key=lambda a:a[0])
    selected=deepcopy(parent);selected["request"]=req
    selected["rationale"].update(chosen=req["task"],winning_first=[req["subject"],"A"],
                                 t8_parent="WAIT",t8_cell=cell,t8_public_origins=support)
    return selected
