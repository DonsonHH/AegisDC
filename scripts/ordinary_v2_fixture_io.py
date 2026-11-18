"""Decode the frozen engineering literals and independently project actual archived records."""
from copy import deepcopy

from aegis_dc.ordinary import policy
from aegis_dc.ordinary.episode import Bindings
from aegis_dc.ordinary.selection import Panels


def base_fixture(f, changes=None):
    b = f["base_rows"]
    keys = f["panel_keys"]
    common = {k:dict(complete=True, **b["default"]) for k in keys}
    for k,delta in b["overrides"].items():
        common[k].update(delta)
    refs = {a:deepcopy(common) for a in ("I","D","P")}
    for k,delta in b["reference_D_overrides"].items():
        refs["D"][k].update(delta)
    column = deepcopy(common)
    for k,row in column.items():
        row.update(frames=[],requests=[],work_by_action={})
        delta=(changes or {}).get(k,{})
        for arm in ("I","D"):
            refs[arm][k].update(delta.get(arm,{}))
        row.update({s:deepcopy(v) for s,v in delta.items() if s not in ("frames","I","D")})
        for i,event in enumerate(delta.get("frames",[])):
            v = deepcopy(f["views"][event["view"]])
            sub = event["submitted"]
            payload = reply = None
            if sub:
                action = sub["action"]
                payload = dict(action=action, request_id="rq-"+str(1+len(v["attempted"])),
                               problem_id="q-1", target="feeder-B" if action in ("READ_POS","READ_VOLT") else "ctrl-1")
                if sub["mode"]:
                    payload["mode"]=sub["mode"]
                reply = {"status":sub["reply"]}
                row["requests"].append(dict(time=v["time"],frame_index=i,payload=payload,reply=reply))
            row["frames"].append(dict(time=v["time"],view=v,decision={s:event[s] for s in ("action","mode","reason")},
                                      payload=payload,reply=reply))
    return Panels(keys,refs),column


def interface(f, case, log):
    v = deepcopy(f["views"][case["view"]])
    try:
        policy.descriptor(case["descriptor"],policy.ENGINEERING)
        policy.validate_public(v)
        if not v["pre_open"]:
            return {"status":"ENV_PRE_CUTOFF"}
        if case["op"] == "binding":
            received, foreign = object(), object()
            ledger = Bindings(received)
            for req in case["requests"]:
                ledger.admitted(req)
            v = ledger.receive(received if case["published_by"] == case["receiver"] else foreign,v)
        log.event("pure_policy_call",unit=case["id"],descriptor=case["descriptor"])
        d = policy.act(case["descriptor"],v,purpose=policy.ENGINEERING)
        out = {k:d[k] for k in ("action","mode")}
        if case["op"] == "binding" and d["action"] == policy.VERIFY:
            req = policy.request_for(case["descriptor"],d,v,4)
            ledger.check_payload(req)
            out["parent"] = [req["execution_id"],req["target_config_epoch"]]
        return out
    except ValueError as exc:
        log.event("pure_rejection",unit=case["id"],error=repr(exc))
        return {"status":"REJECT"}


def episode_projection(raw):
    run,audit,score=raw["run"],raw["final"],raw["score"]
    arrivals=audit["observations"]
    reads=[[r["action"],r["observed_at"],r["available_at"],r["value"]] for r in arrivals if r["action"].startswith("READ_")]
    verify=[r for r in arrivals if r["action"]=="VERIFY_CTRL"]
    receipts=[r for r in audit["receipts"] if r["record_kind"]=="EXECUTION_RECEIPT"]
    ex=receipts[-1] if receipts else {}
    supplies=[]; exits=[]
    for seg in audit["segments"]:
        start,end=seg["start"],seg["end"]
        if supplies and supplies[-1][2]==seg["source"] and supplies[-1][1]==start:
            supplies[-1][1]=end
        else:
            supplies.append([start,end,seg["source"]])
        if seg["work_stage"]=="EXITING":
            action=seg["work_action"]
            if exits and exits[-1][2]==action and exits[-1][1]==start:
                exits[-1][1]=end
            else:
                exits.append([start,end,action])
    payloads=[r["payload"] for r in run["requests"]]
    identifiers=[i for p in payloads for i in p.get("evidence_ids",[])]
    observation=verify[-1] if verify else None
    return dict(requests=[[r["time"],r["payload"]["action"],r["payload"].get("mode")] for r in run["requests"]],
                final_time=audit["time"],stop_time=run["stop"]["time"],stage=raw["reached"]["stage"],
                stop=run["stop"]["reason"],closed=raw["closed"],L=score["L"],U=score["U"],
                person_seconds=score["person_seconds"],tool_seconds=score["tool_seconds"],
                work_by_stage=score["work_by_stage"],supply=supplies,
                approved_at=(audit["internal_approval"] or {}).get("decided_at"),
                committed_at=ex.get("committed_at"),execution_available_at=ex.get("available_at"),
                verification=None if observation is None else [observation["observed_at"],observation["available_at"],
                              observation["parent_execution_id"],observation["config_epoch"]],
                exits=exits,evidence_ids=identifiers,violations=sorted(k for k,v in score["hard_constraints"].items() if not v),
                calls=raw["counts"],config_epoch=audit["epoch"],diagnostics=reads)
