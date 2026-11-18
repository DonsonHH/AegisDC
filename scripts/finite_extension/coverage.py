"""Coverage predicates evaluated only on an archived row at later execution."""
from fractions import Fraction


def reached(slot,common,actual,negative):
    i,d=[actual["arms"][a] for a in ("I","D")]
    runs=(i,d)
    def verified(r):return r["reached"]["verification_result"]=="PASS" and r["reached"]["verification_parent_valid"] is True
    def committed(r):return r["reached"]["commit_result"]=="SUCCESS"
    def stopped(r,reason):return r["stop"]["reason"]==reason
    def no_action(r,act):return act not in r["requested_actions"]
    def acquired(r,act):return any(rec["action"]==act and rec["status"]=="KNOWN" for frame in r["public_trace"] for rec in frame["view"]["records"])
    def touched(r,stage):return any(s["work_stage"]==stage and s["end"]!=s["start"] for s in r["final_audit"]["segments"])
    def offline(r):return any(s["isolated"] for s in r["final_audit"]["segments"])
    if slot in ("A01","A02","B01"):
        return negative(i,slot) and verified(d) and (slot!="B01" or offline(d))
    if slot in ("A03","B02"):
        return all(verified(r) for r in runs) and (slot!="B02" or all(offline(r) for r in runs))
    if slot=="B03":return all(r["reached"]["stage"]=="EXIT_INCOMPLETE" and offline(r) and r["final_audit"]["resource_overrun"] for r in runs)
    if slot=="C01":return any(x["action"]=="READ_POS" and x["status"]=="NO_RESULT" for x in i["final_audit"]["observations"]) and acquired(i,"READ_VOLT") and acquired(i,"READ_CONFIG")
    if slot=="D01":return stopped(d,"INFEASIBLE") and no_action(d,"FIX_CTRL") and verified(i)
    if slot=="E03":
        return all(r["reached"]["approved"] and touched(r,"IMPLEMENTING") and r["reached"]["commit_result"]=="NOT_ATTEMPTED" and
                   any(z.get("status")=="NOT_IMPLEMENTED" for z in r["final_audit"]["receipts"]) for r in runs)
    stages={"E01":"APPROVAL_DENIED","E02":"COMMIT_FAILED","E04":"VERIFICATION_FAILED","E05":"VERIFY_INCONCLUSIVE"}
    if slot in stages:
        return all(r["reached"]["stage"]==stages[slot] and (slot not in ("E04","E05") or r["reached"]["verification_parent_valid"] is True) for r in runs)
    if slot in ("F01","F02"):
        return all(verified(r) and r["final_audit"]["g_state"]=="FAILED" and not any(s["source"]=="G" for s in r["final_audit"]["segments"]) for r in runs)
    if slot.startswith("G"):
        arm=d if slot in ("G01","G02","G03") else i
        return arm["reached"]["approved"] and touched(arm,"PREPARING") and committed(arm)==(slot in ("G03","G06"))
    if slot in ("H01","H02"):
        return acquired(i,"READ_POS") and acquired(i,"READ_VOLT") and (acquired(i,"READ_CONFIG") if slot=="H02" else stopped(i,"INSUFFICIENT_INFORMATION") and no_action(i,"READ_CONFIG"))
    if slot.startswith(("H","J")):
        arm=d if slot in ("H03","H04","J01","J02") else i
        prefix=arm is d or all(acquired(i,a) for a in ("READ_POS","READ_VOLT","READ_CONFIG"))
        return prefix and (verified(arm) if slot in ("H04","H06","J02","J04") else stopped(arm,"INFEASIBLE") and no_action(arm,"FIX_CTRL"))
    if slot.startswith("K"):
        waited=all(Fraction(r["score"]["resource_queue_seconds"])>0 for r in runs)
        return waited and (all(verified(r) for r in runs) if slot=="K01" else i["reached"]["approved"] and not committed(i) and committed(d) and stopped(i,"ENV_PRE_CUTOFF"))
    if slot.startswith("L"):
        required_a=1 if slot=="L01" else 0
        return all(r["final_audit"]["vA"]==required_a and not r["final_audit"]["pre_open"] and all(t<common["tF"] for t in r["policy_times"]) for r in runs)
    return None  # Old-return engineering fixture; no new research coverage assigned.
