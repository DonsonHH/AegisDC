"""Read saved rounds independently. Never invokes a policy, broker, panel or facility."""

from collections import Counter
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from fit_evidence import authenticated, dereference
from fit_program import canonical

NAMES = ("DIRECT_NEAR", "ALARM_NEAR", "ORDER_NEAR", "DIRECT_FAR", "ALARM_FAR", "ORDER_FAR")
ZERO = (0,)*6
BASE = {"op":"base"}


def insist(test, why):
    if not test: raise ValueError("readback: " + why)


def digest(obj):
    return sha256(canonical(obj)).hexdigest()


def expected_macro(cell, sign):
    mate = NAMES[(NAMES.index(cell)+3)%6]
    return {"op":"emit_then", "then":BASE, "productions":[{"op":"step_pair","cells":[cell,mate],"step":sign},
            {"op":"step","cell":mate,"step":sign},{"op":"step","cell":cell,"step":sign}]}


def independent_list(ast, center, seen, number):
    shift = (number-1)%6
    def ordering(vector):
        differences = tuple((i-shift)%6 for i,(x,y) in enumerate(zip(center,vector)) if x != y)
        return len(differences), sum(abs(y-x) for x,y in zip(center,vector)), sorted(differences), vector[shift:]+vector[:shift]
    stream = []
    if ast != BASE:
        for action in ast["productions"]:
            v = list(center)
            for cell in action.get("cells", [action.get("cell")]):
                v[NAMES.index(cell)] += action["step"]
            if all(0<=x<=3 for x in v) and tuple(v) not in seen and tuple(v) not in stream:
                stream.append(tuple(v))
    for candidate in sorted(product(range(4),repeat=6), key=ordering):
        if candidate not in seen and candidate not in stream: stream.append(candidate)
        if len(stream) == 4: break
    return stream


def read_case(root, summary, validate):
    root = Path(root)
    def obj(ref): return dereference(root, ref)
    def raw_file(path): return json.loads(path.read_bytes())
    def signer_event(ref, purpose):
        event = authenticated(obj(ref),summary["journal_key"])
        insist(event["purpose"]==purpose and event["context"]==summary["context"], "event purpose/context")
        return event
    def check_policy(p):
        insist(obj(p["bytes"])==p["levels"] and
            p["id"]==digest({"design_sha256":summary["design_sha256"],
                             "parent_bundle_sha256":summary["frozen"]["parent_bundle"],"levels":p["levels"]}),
            "descriptor identity")
    def packet(ref): return authenticated(obj(ref),summary["score_key"])
    def walk_refs(tree):
        if isinstance(tree,dict):
            if set(tree)=={"bytes","sha256","locator"}: obj(tree)
            else:
                for item in tree.values(): walk_refs(item)
        elif isinstance(tree,list):
            for x in tree: walk_refs(x)
    objects = list((root/"objects").iterdir())
    for f in objects:
        raw = f.read_bytes()
        insist(f.name==sha256(raw).hexdigest(), "object bytes")
        walk_refs(json.loads(raw))
    prior_event = None
    events = {}
    counts = Counter()
    for n, f in enumerate(sorted((root/"events").glob("*.json")),1):
        ref = raw_file(f)
        e = authenticated(obj(ref),summary["journal_key"])
        insist(f.name==f"{n:04}.json" and e["sequence"]==n and e["previous"]==prior_event and
               e["context"]==summary["context"],"event chain")
        events[ref["sha256"]]=e
        prior_event=ref["sha256"]
        counts[e["purpose"]] += 1
    parent = signer_event(summary["result"]["shared"],"shared-parent-return")["body"]["slot"]
    baseline = parent["fit_return"]
    arrivals = {(v["body"]["binding"]["arm"], v["body"]["binding"]["round"], v["body"]["binding"]["slot"]):v
                for v in events.values() if v["purpose"]=="return-to-broker"}
    insist(len(arrivals)==counts["return-to-broker"] and ("PARENT",0,0) in arrivals,"unique broker slots")
    pbody=arrivals["PARENT",0,0]["body"]
    pmeter=packet(pbody["meter"])
    insist(len(pmeter["attempts"])==parent["started_fit_n"] and pbody["meter"]==parent["attempts_receipt"],"single parent")
    if baseline:
        raw_parent=obj(pmeter["originals"])["rows"]
        insist(len(raw_parent)==48 and pbody["signed_packet"]==baseline["receipt"] and
               all(baseline[field]==sum(round(Fraction(Decimal(row[key]))*1_000_000) for row in raw_parent)
                   for key,field in [("L","L_sum_us"),("person","person_sum_us")]),"shared baseline cost and loss")
    locks = summary["result"]["dual_lock"]
    all_rounds, paid = {}, {}
    for arm in ("O","R"):
        seen, head, prior = {ZERO}, None, None
        scores = baseline
        arm_rows, marks = [], set()
        last_selected_id = None
        ended = False
        for r in range(1,5):
            rec = raw_file(root/"rounds"/f"{arm}-{r}.json")
            validate(rec)
            insist(rec["previous_record_sha256"]==head and rec["round"]==r and rec["arm"]==arm and
                   rec["terminal"]==(r==4) and rec["frozen"]==summary["frozen"] and
                   rec["registration_sha256"]==summary["registration_sha256"] and
                   rec["design_sha256"]==summary["design_sha256"],"round binding")
            temp=deepcopy(rec)
            stamp=signer_event(temp["audit"].pop("record_seal"),"round")
            insist(stamp["body"]["payload_sha256"]==digest(temp), "full signed record")
            insist(rec["status"]=="UNRUN" if ended else rec["status"]!="UNRUN", "stop suffix")
            head=digest(rec)
            insist(obj({"sha256":head,"bytes":len(canonical(rec)),"locator":"objects/"+head})==rec,"final record bytes")
            if prior and prior["after"] is not None and rec["before"] is not None:
                insist(rec["before"]==prior["after"],"state continuity")
            slots=rec["slots"]
            insist([s["slot"] for s in slots]==[1,2,3,4] and all(s["scheduled_fit_n"]==48 for s in slots),"reserved schedule")
            accounting=rec["accounting"]
            insist(accounting["scheduled_positions"]==192 and accounting["scheduled_proposals"]==4 and
                   accounting["started_positions"]==sum(s["started_fit_n"] for s in slots) and
                   accounting["complete_positions"]==sum(s["complete_fit_n"] for s in slots),"position arithmetic")
            order = [s["policy"] for s in slots if s["policy"] is not None]
            if order:
                start=rec["before"]; check_policy(start["incumbent"])
                center=tuple(start["incumbent"]["levels"])
                vectors=[tuple(p["levels"]) for p in order]
                insist(obj(start["program_bytes"])==start["ast"] and obj(start["seen_set_bytes"])==[list(x) for x in sorted(seen)]
                       and vectors==independent_list(start["ast"],center,seen,r),"independent prepaid list")
                reserve=signer_event(rec["audit"]["roster_seal_before_feedback"],"reserve-roster")
                insist(obj(reserve["body"]["ordered"])==order and reserve["body"]["starting_state"]==start,
                       "reserve before source")
                allocation=signer_event(accounting["allocations_receipt"],"allocation")["body"]
                barrier=signer_event(allocation["barrier"],"both-rosters-prepaid")
                insist(reserve["sequence"]<barrier["sequence"]<stamp["sequence"] and
                       barrier["body"]["receipts"][arm]==rec["audit"]["roster_seal_before_feedback"],"two-arm barrier")
                for p in order: check_policy(p)
            slot_cpu=[]
            for slot in slots:
                if not slot["attempts_receipt"]: continue
                met=packet(slot["attempts_receipt"])
                attempts=met["attempts"]
                arrival=arrivals[arm,r,slot["slot"]]
                insist(arrival["body"]["meter"]==slot["attempts_receipt"] and
                       barrier["sequence"]<arrival["sequence"]<stamp["sequence"],"registered physical return")
                slot_cpu.append(None if any(x["cpu_us"] is None for x in attempts) else sum(x["cpu_us"] for x in attempts))
                insist(len(attempts)==slot["started_fit_n"] and sum(x["complete"] for x in attempts)==slot["complete_fit_n"],
                       "meter starts/completions")
                result=slot["fit_return"]
                if result is None: continue
                insist(arrival["body"]["signed_packet"]==result["receipt"],"returned packet bytes")
                bind=met["binding"]
                insist(bind=={"context":summary["context"],"arm":arm,"round":r,"slot":slot["slot"],
                      "policy_id":slot["policy"]["id"],"roster_sha256":digest(order)}, "actual paid candidate")
                auth=packet(result["receipt"])
                originals=obj(met["originals"])
                insist(len(originals["rows"])==48 and originals["binding"]==bind==auth["binding"] and
                    set(auth["data"])=={"scheduled","completed","status","L_sum_us","person_sum_us","hard_violations"},
                    "score release layout")
                for key, field in [("L","L_sum_us"),("person","person_sum_us")]:
                    total=sum(round(Fraction(Decimal(row[key]))*1_000_000) for row in originals["rows"])
                    insist(total==auth["data"][field]==result[field],"per-row rounding and aggregation")
                insist(result["hard_violations"]==sum(x["hard_violations"] for x in originals["rows"]),"hard constraint total")
            if order:
                insist(slot_cpu==allocation["per_evaluated_slot_us"] and accounting["actual_process_cpu_us"]==
                       (None if None in slot_cpu else sum(slot_cpu)+allocation["controller_us"]),"actual CPU debit")
            if rec["status"]!="CLOSED":
                ended=True
            else:
                insist(scores and start["paid_score_receipt"]==scores["receipt"],"paid incumbent")
                insist(obj(rec["feedback"])=={"parent":scores["receipt"],"own_slots":[s["fit_return"]["receipt"] for s in slots]},
                       "arm-only feedback")
                rel=signer_event(rec["audit"]["score_release_receipt"],"release-own")
                both=events[rel["body"]["paired_complete"]]
                insist(all(arrivals[a,r,i]["sequence"]<both["sequence"] for a in ("O","R") for i in range(1,5)),
                       "all eight actual returns before release")
                insist(both["purpose"]=="paired-complete" and barrier["sequence"]<both["sequence"]<rel["sequence"]<stamp["sequence"],
                       "release only after paired closure")
                ranking=sorted((s for s in slots if not s["fit_return"]["hard_violations"]),
                    key=lambda s:(s["fit_return"]["L_sum_us"],s["fit_return"]["person_sum_us"],s["policy"]["levels"]))
                winners=[s for s in ranking if s["fit_return"]["L_sum_us"]<scores["L_sum_us"]]
                win=winners[0] if winners else None
                expect_slot=win["slot"] if win else None
                insist(rec["selection"]["ranked_eligible_slots"]==[s["slot"] for s in ranking] and
                       rec["selection"]["accepted_slot"]==expect_slot,"rank/strict gain")
                after=rec["after"]; check_policy(after["incumbent"])
                insist(after["incumbent"]==(win["policy"] if win else start["incumbent"]),"selected identity")
                req_ast=start["ast"]; rw=rec["rewrite"]
                credited=next((s for s in winners if sum(x!=y for x,y in zip(s["policy"]["levels"],center))==1),None)
                if credited and r<4:
                    ds=[v-i for v,i in zip(credited["policy"]["levels"],center)]
                    c=next(i for i,v in enumerate(ds) if v)
                    sign=1 if ds[c]>0 else -1
                    credit=rw["credit"]
                    insist(credit=={"slot":credited["slot"],"cell":NAMES[c],"direction":sign,
                        "incumbent_L_sum_us":scores["L_sum_us"],"candidate_L_sum_us":credited["fit_return"]["L_sum_us"],
                        "candidate_minus_incumbent_L_sum_us":credited["fit_return"]["L_sum_us"]-scores["L_sum_us"],
                        "feedback_receipt":credited["fit_return"]["receipt"]},"signed single-edit credit")
                    if arm=="R": req_ast=expected_macro(NAMES[c],sign)
                else: insist(rw["credit"] is None,"unearned credit")
                insist(after["ast"]==req_ast==obj(after["program_bytes"]),"bounded AST")
                patch=[] if req_ast==start["ast"] else [{"op":"replace","path":"","value":req_ast}]
                insist(rw["patch"]==obj(rw["patch_bytes"])==patch,"applied patch")
                if r>1:
                    prior_w=prior["next_witness"]; inc=rec["incoming_witness"]
                    new_slots=[s["slot"] for s in slots if s["policy"]["id"] not in prior_w["before_policy_ids"]]
                    insist(prior_w["after_roster"]["sha256"]==inc["predicted_after_roster"]==
                           inc["actual_prepaid_roster"]==digest(order) and inc["actually_paid_new_slots"]==new_slots,
                           "paid membership change")
                    marks.update((r,i) for i in new_slots)
                if win:
                    scores=win["fit_return"]
                    insist(after["incumbent_origin"]==dict(kind="PAID_SLOT",round=r,slot=win["slot"],
                        parent_policy_id=start["incumbent"]["id"],receipt=scores["receipt"]),"paid parent lineage")
                else: insist(after["incumbent_origin"]==start["incumbent_origin"],"retained origin")
                insist(after["paid_score_receipt"]==scores["receipt"],"selected score receipt")
                last_selected_id=after["incumbent"]["id"]
                seen.update(vectors)
                insist(obj(after["seen_set_bytes"])==[list(x) for x in sorted(seen)],"final seen set")
                if r<4:
                    w=rec["next_witness"]; center2=tuple(after["incumbent"]["levels"])
                    for x,stream,ids in [(start["ast"],w["before_roster"],w["before_policy_ids"]),
                                         (after["ast"],w["after_roster"],w["after_policy_ids"])]:
                        pp=obj(stream)
                        insist([tuple(p["levels"]) for p in pp]==independent_list(x,center2,seen,r+1) and
                               ids==[p["id"] for p in pp],"two structural counterfactuals")
                    li,ri=w["before_policy_ids"],w["after_policy_ids"]
                    label=("CHANGED_MEMBERSHIP" if set(li)!=set(ri) else "ORDER_ONLY" if li!=ri else
                           "EDITED_IDENTICAL_LIST" if start["ast"]!=after["ast"] else "NO_OP")
                    insist(w["classification"]==label,"mechanism classification")
            arm_rows.append(rec);prior=rec
        insist(summary["result"]["round_heads"][arm]==head,"final record head")
        selected={(x["round"],x["selection"]["accepted_slot"]) for x in arm_rows
                  if x["selection"] and x["selection"]["accepted_slot"] is not None}
        all_rounds[arm]=arm_rows
        paid[arm]={"selected_changed_slots":sorted([list(p) for p in marks&selected]),
            "actually_paid_changed_slots":sorted([list(p) for p in marks]),"last_selected_id":last_selected_id,
            "statuses":[x["status"] for x in arm_rows],"selected_slots":[x["selection"]["accepted_slot"] if x["selection"] else None for x in arm_rows],
            "rewrite_reasons":[x["rewrite"]["reason"] for x in arm_rows],
            "next_effects":[x["next_witness"]["classification"] if x["next_witness"] else None for x in arm_rows],
            "program_sha256":[x["after"]["program_bytes"]["sha256"] if x["after"] else None for x in arm_rows],
            "emitted":sum(x["accounting"]["emitted_proposals"] for x in arm_rows),
            "started":sum(x["accounting"]["started_positions"] for x in arm_rows),
            "completed":sum(x["accounting"]["complete_positions"] for x in arm_rows)}
    for o,r in zip(all_rounds["O"],all_rounds["R"]): insist(o["status"]==r["status"],"paired stop")
    insist(not locks if ended else bool(locks),"terminal lock condition")
    if locks:
        payload=signer_event(locks,"dual-fixture-or-study-lock")["body"]
        insist(payload["round_heads"]==summary["result"]["round_heads"] and
               all(payload["incumbents"][a]["id"]==paid[a]["last_selected_id"] for a in paid),"dual locked identities")
    return {"rounds":8,"objects":len(objects),"events":sum(counts.values()),"shared_started":parent["started_fit_n"],
            "shared_completed":parent["complete_fit_n"],"dual_lock":bool(locks),"arms":paid,"event_counts":dict(counts)}
