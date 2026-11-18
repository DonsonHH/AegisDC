"""Fixed, post-return analysis. This module has no facility/policy/scorer imports."""
from fractions import Fraction
from common import ARMS
import run_london_public_development as report
from coverage import reached


def coalesce_service(segments):
    result=[]
    for s in segments:
        state=tuple(s[k] for k in ("source","power","demand","service","device","isolated"))
        if result and result[-1][2]==state and result[-1][1]==s["start"]:
            result[-1][1]=s["end"]
        else:
            result.append([s["start"],s["end"],state])
    return result


def hidden_keys(payload):
    if isinstance(payload,list):
        return any(hidden_keys(v) for v in payload)
    return isinstance(payload,dict) and (any(k in payload for k in ("work_mode","calendar")) or any(hidden_keys(v) for v in payload.values()))


def check_public_action(frame):
    payload=frame.get("payload")
    if not payload or frame["reply"]["status"]!="ADMITTED":return True
    view=frame["view"];ctx=view["context"];action=payload["action"]
    if action!="FIX_CTRL":
        return ctx["acquisition_plans"][action]["admissible"] is True
    needed=["propose","read","verify"] + (["direct"] if payload["mode"]=="DIRECT" else [])
    if not (all(ctx["permissions"][k]=="ALLOW" for k in needed) and ctx["compatible"]=="ALLOW"
            and Fraction(ctx["available"])>=Fraction(ctx["chain_reserve"])
            and Fraction(ctx["chain_finish"])<ctx["window"][1] and Fraction(ctx["chain_resource_end"])<=ctx["window"][1]):
        return False
    if payload["mode"]=="DIRECT":return True
    time=Fraction(view["time"])
    records={r["record_id"]:r for r in view["records"] if r["status"]=="KNOWN" and r["receiver_role"]=="AUDITOR"
             and r["problem_id"]=="q-1" and r["maintenance_epoch"]=="m0" and Fraction(r["available_at"])<=time<Fraction(r["expires_at"])}
    ids=payload["evidence_ids"]
    return all(k in records for k in ids) and {records[k]["action"]:records[k]["value"] for k in ids}=={"READ_POS":0,"READ_VOLT":1,"READ_CONFIG":"LEGACY_LINE"}


def legal_negative(arm,slot):
    action,value=("READ_POS",1) if slot in ("A01","B01") else ("READ_CONFIG","REVISED_LOCAL")
    for frame in arm["public_trace"]:
        t=Fraction(frame["time"]);view=frame["view"]
        for record in view["records"]:
            if (record["action"]==action and record["status"]=="KNOWN" and record["value"]==value
                    and record["receiver_role"]=="AUDITOR" and record["problem_id"]=="q-1" and record["maintenance_epoch"]=="m0"
                    and record["target"]==("feeder-B" if action=="READ_POS" else "ctrl-1")
                    and (action!="READ_CONFIG" or record["config_epoch"]==view["known_epoch"])
                    and Fraction(record["available_at"])<=t<Fraction(record["expires_at"])):
                return True
    return False


def inspect(slot,common,actual):
    findings=report.inspect_result(actual,common,slot)
    mechanisms=[]
    for arm in ARMS:
        run=actual["arms"][arm]
        for frame in run["public_trace"]:
            if hidden_keys(frame["view"]):findings.append("PRIVATE_FIELD:"+arm)
            if not check_public_action(frame):findings.append("INADMISSIBLE_ACTION:"+arm)
        a=run.get("final_audit") or {}
        for receipt in a.get("receipts",[]):
            if receipt.get("status")=="EXECUTED_UNVERIFIED":
                cutoff=min(common["window"][1],common["grant_expiry"],common["H"] if common["tF"] is None else common["tF"])
                if not Fraction(receipt["committed_at"])<Fraction(cutoff):findings.append("COMMIT_AT_OR_AFTER_CUTOFF:"+arm)
        if run["reached"].get("verification_parent_valid") is False:findings.append("VERIFICATION_IDENTITY:"+arm)
    i=actual["arms"]["I"];p=actual["arms"]["P"]
    if common["work_mode"]=="ONLINE" and i["reached"]["commit_result"]!="SUCCESS" and i["final_audit"] and p["final_audit"]:
        same=coalesce_service(i["final_audit"]["segments"])==coalesce_service(p["final_audit"]["segments"])
        mechanisms.append(dict(check="F4_I_P_service_path",matched=same))
        if not same:findings.append("F4_SERVICE_MECHANISM")
    row=report.summarize(slot,actual,findings)
    scores=row["arms"]
    row["P_background"]={"delta_L_I_minus_P":report.diff(scores["I"]["L"],scores["P"]["L"]),
        "delta_costs_I_minus_P":{k:report.diff(scores["I"]["costs"][k],scores["P"]["costs"][k]) for k in report.COSTS}}
    valid=row["valid_comparison"]
    row["finite_propositions"]=dict(
        F1_counterexample=(Fraction(row["delta_L_D_minus_I"])>0) if valid else None,
        F3_counterexample=(Fraction(row["P_background"]["delta_L_I_minus_P"])<0) if valid else None,
        F4=mechanisms,F5_technical_findings=findings,F2=None)
    if slot in ("A01","A02"):
        tied=scores["I"]["L"]==scores["D"]["L"] and valid
        row["finite_propositions"]["F2"]=dict(legal_negative=legal_negative(i,slot),
            short_circuit_without_FIX=not i["reached"]["fix_requested"] and i["stop"]["reason"]=="NO_ACTION_CURRENT_SCOPE",
            same_service=bool(tied) if valid else None,
            less_person_and_tool=all(Fraction(row["delta_costs_I_minus_D"][k])<0 for k in ("person_seconds","tool_seconds")) if tied else None)
    row["assigned_stage_observed"]=reached(slot,common,actual,legal_negative) if not findings else None
    return row
