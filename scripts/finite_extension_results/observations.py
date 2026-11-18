"""Evidence extracted from saved segments, views, requests and receipts only."""
from collections import Counter
from fractions import Fraction
import hashlib
import json

ARMS = ("I", "D", "P")
KINDS = {"constructor": "constructor_attempts", "plant": "plant_entry_calls",
         "policy": "policy_calls", "scorer": "scorer_calls"}
VIEW = set("view_schema time pre_open pending terminal_failure phase records receipts history attempted known_epoch certificate context".split())
CONTEXT = set("permissions compatible window available read_reserve verify_reserve acquisition_plans chain_reserve chain_finish chain_resource_end read_parameters_known chain_parameters_known".split())
PRIVATE = set("condition_id condition_label common tF tR next_event next_private_event family ready exec_fault approval commit verification guard work_mode calendar".split())


def insist(ok, message):
    if not ok:
        raise ValueError(message)


def norm(value):
    if isinstance(value, Fraction):
        return value.numerator if value.denominator == 1 else str(value)
    if isinstance(value, dict):
        return {k: norm(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [norm(v) for v in value]
    return value


def canonical(value):
    return json.dumps(norm(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def equal(actual, expected, why):
    insist(canonical(actual) == canonical(expected), why)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def check_public_tree(value):
    if isinstance(value, dict):
        insist(not PRIVATE.intersection(value), "Private field in delivered policy arguments")
        for child in value.values():
            check_public_tree(child)
    elif isinstance(value, list):
        for child in value:
            check_public_tree(child)


def contiguous(sequence, start, end, state):
    if sequence and sequence[-1]["end"] == start and sequence[-1]["state"] == state:
        sequence[-1]["end"] = end
    else:
        sequence.append(dict(start=start, end=end, state=state))


def integrals(config, audit, run):
    """Integrate the *frozen* demand and actual delivery, separately tally occupancy."""
    demand = [(Fraction(t), Fraction(v)) for t, v in config["demand"]]
    cursor = loss = unserved = energy = ups = Fraction(0)
    by_action, by_stage, starts, ends = Counter(), Counter(), {}, {}
    supplies, states, isolations = [], [], []
    reservation_conflict = False
    for segment in audit["segments"]:
        a, b = Fraction(segment["start"]), Fraction(segment["end"])
        insist(a == cursor and a < b <= config["H"], "Non-contiguous saved trajectory")
        cursor = b
        delivered, power = Fraction(segment["service"]), Fraction(segment["power"])
        boundaries = [a, *(t for t, _ in demand if a < t < b), b]
        for left, right in zip(boundaries, boundaries[1:]):
            d = next(v for t, v in reversed(demand) if t <= left)
            insist(d == segment["demand"] and 0 <= delivered <= d, "Reported/frozen demand or service")
            unserved += (right-left)*(d-delivered)
            if d:
                loss += (right-left)*(d-delivered)/d
        energy += (b-a)*power
        if segment["source"] == "UPS":
            ups += (b-a)*power
        contiguous(supplies, a, b, segment["source"])
        contiguous(states, a, b, [segment[k] for k in ("source", "power", "demand", "service", "device", "isolated")])
        if segment["isolated"]:
            contiguous(isolations, a, b, True)
        if segment["occupied"]:
            action, phase = segment["work_action"], segment["work_stage"]
            by_action[action] += b-a
            by_stage[phase] += b-a
            starts.setdefault(action, a)
            ends[action] = b
            reservation_conflict |= any(a < y and x < b for x, y in config["calendar"])
    insist(cursor == audit["time"] == config["H"], "Full H window required for saved valid score")
    occupied = sum(by_action.values(), Fraction(0))
    equal([loss,unserved,energy,ups], [audit[k] for k in ("L","U","load_energy","ups_energy")], "Plant integrals differ")
    equal(Fraction(config["E0"])-ups,audit["E"],"UPS energy balance")
    for name in ("person","tool"):
        budget=audit["budgets"][name]
        equal(budget["spent"],occupied,"Spent ledger")
        equal(Fraction(budget["available"]),Fraction(budget["limit"])-occupied-Fraction(budget["reserved"]),"Available budget")
    queue = unstarted = Fraction(0)
    proposal = None
    grant = audit["internal_approval"]
    for request in run["requests"]:
        action=request["payload"]["action"]
        time=Fraction(request["time"])
        if action=="FIX_CTRL":
            proposal=time
        if request["reply"]["status"]=="ADMITTED":
            if action in starts:
                origin=Fraction(grant["decided_at"]) if action=="FIX_CTRL" else time
                queue+=starts[action]-origin
            else:
                unstarted+=Fraction(run["stop"]["time"])-time
    approval_wait = 0 if proposal is None else None if grant is None else Fraction(grant["decided_at"])-proposal
    costs=dict(person_seconds=occupied,tool_seconds=occupied,resource_queue_seconds=queue,
               approval_wait_seconds=approval_wait,unstarted_observed_wait_seconds=unstarted,
               observed_stop_time=run["stop"]["time"],request_count=len(run["requests"]),policy_call_count=len(run["public_trace"]))
    reserves={"FIX_CTRL":config["prep"]+config["commit_work"]+config["exit_work"],"VERIFY_CTRL":config["verify_work"]+config["exit_work"]}
    exceeded=any(ends[k]-start > reserves.get(k,config["read_work"]+config["exit_work"]) for k,start in starts.items())
    resource_ok={"within_budget":occupied<=config["budget"],"external_reservations_clear":not reservation_conflict,"reserved_exit_honored":not exceeded}
    score=run["score"]
    for name,val in {"L":loss,"U":unserved,"work_by_action":by_action,"work_by_stage":by_stage,
                     "load_energy":energy,"ups_energy":ups,**costs}.items():
        equal(val,score[name],"Score/independent saved integration: "+name)
    for name,ok in resource_ok.items():
        equal(ok,score["hard_constraints"][name],"Reconstructed resource constraint: "+name)
    return norm(dict(L=loss,U=unserved,energy=energy,ups_energy=ups,ending_UPS=audit["E"],costs=costs,
                     work_by_action=by_action,work_by_stage=by_stage,supply=supplies,service_states=states,
                     load_isolation=isolations,violated_constraints=[k for k,v in score["hard_constraints"].items() if not v]))


def proof_of_stage(audit,run):
    requested=[r["payload"]["action"] for r in run["requests"]]
    execs=[r for r in audit["receipts"] if r["record_kind"]=="EXECUTION_RECEIPT"]
    parents={(r["execution_id"],r["target_config_epoch"]):r for r in execs if r["status"]=="EXECUTED_UNVERIFIED"}
    obs=audit["observations"];verified=[r for r in obs if r["action"]=="VERIFY_CTRL"]
    valid_parents = None if not verified else all((r["parent_execution_id"],r["config_epoch"]) in parents for r in verified)
    prepared=any(s["work_action"]=="FIX_CTRL" and s["work_stage"]=="PREPARING" and s["end"]>s["start"] for s in audit["segments"])
    grant=audit["internal_approval"];commit=audit["commit_result"];verify=audit["verification_result"]
    probe_stages={"PASS":"VERIFIED","FAIL":"VERIFICATION_FAILED","INCONCLUSIVE":"VERIFY_INCONCLUSIVE","ABORTED":"VERIFY_ABORTED"}
    if run["arm"]=="P":stage="BACKGROUND_ONLY"
    elif audit["phase"]=="EXITING" and audit["resource_overrun"]:stage="EXIT_INCOMPLETE"
    elif verify in probe_stages:stage=probe_stages[verify]
    elif commit=="FAIL":stage="COMMIT_FAILED"
    elif parents:stage="EXECUTED_UNVERIFIED"
    elif grant and grant["decision"]=="DENY":stage="APPROVAL_DENIED"
    elif "FIX_CTRL" in requested:stage="NOT_IMPLEMENTED"
    elif requested:stage="INSPECTION_STOP"
    else:stage="NO_ACTION"
    read_ids={r["record_id"] for f in run["public_trace"] for r in f["view"]["records"] if r["action"].startswith("READ_")}
    reached=dict(stage=stage,fix_requested="FIX_CTRL" in requested,approved=bool(grant and grant["decision"]=="APPROVE"),
                 preparation_started=prepared,commit_result=commit,commit_attempted=commit in ("FAIL","SUCCESS"),
                 verification_requested="VERIFY_CTRL" in requested,verification_result=verify,
                 verification_published=bool(verified),verification_parent_valid=valid_parents,
                 read_results_published=sum(r["action"].startswith("READ_") for r in obs),read_records_visible_to_policy=len(read_ids))
    equal(reached,run["reached"],"Stage did not match receipts/requests/observations/segments")
    return reached,execs,verified


def observe_arm(raw,config,slot,arm,public_decisions):
    run=raw["arms"][arm];audit=run["final_audit"]
    equal(audit["original_input"],config,"Arm input binding")
    measured=integrals(config,audit,run)
    reached,execs,probes=proof_of_stage(audit,run)
    trace=run["public_trace"]
    calls=[c for c in raw["calls"] if c["arm"]==arm]
    policy=[c for c in calls if c["kind"]=="policy"]
    insist(len(trace)==len(policy)<=20,"Arm call cap/ledger")
    repeats=0
    for call,frame in zip(policy,trace):
        view=call["arguments"]["public_view"]
        equal(call["arguments"],dict(treatment=arm,public_view=frame["view"]),"Policy argument binding")
        equal(call["actual"],frame["decision"],"Policy decision binding")
        insist(set(view)==VIEW and set(view["context"])==CONTEXT and view["view_schema"]=="aegisdc-e14-public-v2","v2 envelope")
        check_public_tree(view)
        insist(slot not in canonical(view) and type(view["time"]) is int and view["time"]==frame["time"],"Clock/label")
        t=view["time"];insist(view["pre_open"] and 0<=t<config["H"] and (config["tF"] is None or t<config["tF"]),"PRE timing")
        for record in view["records"]:
            insist(Fraction(record["available_at"])<=t<Fraction(record["expires_at"]),"Record availability")
        for receipt in view["receipts"]:
            insist(Fraction(receipt["available_at"])<=t,"Receipt availability")
        key=(arm,digest(view));decision=canonical(frame["decision"])
        if key in public_decisions:
            repeats+=1
            equal(public_decisions[key],decision,"Different choice on identical arm and public packet")
        else:public_decisions[key]=decision
    for request in run["requests"]:
        payload=request["payload"]
        if payload["action"]=="VERIFY_CTRL":
            view=trace[request["frame_index"]]["view"]
            insist(any(r.get("execution_id")==payload["execution_id"] and r.get("target_config_epoch")==payload["target_config_epoch"]
                       and r.get("status")=="EXECUTED_UNVERIFIED" and r["available_at"]<=request["time"] for r in view["receipts"]),"Own arrived VERIFY identity")
    cutoff=min(config["window"][1],config["grant_expiry"],config["H"] if config["tF"] is None else config["tF"])
    for r in execs:
        if r["status"]=="EXECUTED_UNVERIFIED":
            insist(r["committed_at"]<cutoff,"Successful commit at/after cut-off")
    verify_status={"PASS":"VERIFIED_FOR_TARGET","FAIL":"VERIFY_FAILED","INCONCLUSIVE":"INCONCLUSIVE"}
    if audit["verification_result"] in verify_status:
        insist(any(r["status"]==verify_status[audit["verification_result"]] and r["available_at"]<min(
            config["window"][1],config["H"] if config["tF"] is None else config["tF"]) for r in probes)
            and reached["verification_parent_valid"],"Verification state versus actual probe/identity")
    equal(audit["recoveries"],run["score"]["recoveries"],"Archived recovery episodes")
    censored=[e for e in audit["recoveries"] if e.get("right_censored")]
    stop=run["stop"]
    last=next((f for f in reversed(trace) if f["time"]==stop["time"]),None)
    negatives=[]
    if slot in ("A01","A02","B01") and arm=="I" and last:
        which,value=("READ_CONFIG","REVISED_LOCAL") if slot=="A02" else ("READ_POS",1)
        negatives=[r for r in last["view"]["records"] if r["action"]==which and r["status"]=="KNOWN" and r["value"]==value]
    return dict(**measured,stage=reached["stage"],reached=reached,stop=stop,
                requests=[dict(action=r["payload"]["action"],mode=r["payload"].get("mode"),time=r["time"],reply=r["reply"]["status"],
                               execution_id=r["payload"].get("execution_id"),target_epoch=r["payload"].get("target_config_epoch")) for r in run["requests"]],
                grant=grant_summary(audit["internal_approval"]),execution_receipts=execs,verify_records=probes,
                observations=[{k:r[k] for k in ("action","status","value","observed_at","available_at","expires_at")} for r in audit["observations"]],
                negative_record_at_stop=negatives,final_family=audit["family"],final_epoch=audit["epoch"],
                initial_G=raw["initial_private_audits"][arm]["g_state"],final_G=audit["g_state"],
                final_vA=audit["vA"],final_device=audit["device"],recoveries=audit["recoveries"],right_censored=censored,
                service_recovery_status=("RIGHT_CENSORED_AT_H" if censored else "RECOVERED_WITHIN_WINDOW" if audit["recoveries"] else "NO_RECORDED_SERVICE_OUTAGE"),
                fault_restore_events=[e for e in audit["events"] if e["event"] in ("fault","restore")],
                calls=dict(Counter(c["kind"] for c in calls)),identical_public_packet_matches=repeats,
                policy_trace_sha256=digest(trace),hard_constraints=run["score"]["hard_constraints"],
                trace_status=run["score"]["trace_status"],last_policy_decision=None if not trace else trace[-1]["decision"]["action"])


def grant_summary(grant):
    if grant is None:return None
    return {k:grant.get(k) for k in ("decision","decided_at","available_at","receiver_role","grant_id")}
