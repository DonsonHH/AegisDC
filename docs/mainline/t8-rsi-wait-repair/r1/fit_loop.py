"""Matched FIT control loop. The only scoring dependency is an injected paid-slot broker."""

from time import process_time_ns

from fit_broker import ARM_US, CONTROLLER_US, ROWS, open_packet
from fit_evidence import authenticated
from fit_program import BASE, ZERO, changed, policy_id, rank_and_rewrite, require, roster, validate_levels

ARMS = ("O", "R")
ROUNDS = 4
SLOTS = 4


def clock_us():
    return process_time_ns() // 1000


def empty_slot(i):
    return dict(slot=i, status="UNRUN", policy=None, parent_policy_id=None, changed_cells=None,
                scheduled_fit_n=ROWS, started_fit_n=0, complete_fit_n=0, fit_return=None,
                attempts_receipt=None, failure_reason="not started")


def policy(levels, design_sha, frozen, store):
    return {"id": policy_id(levels, design_sha, frozen["parent_bundle"]), "levels": list(levels),
            "bytes": store.put(levels)}


def state(ast, incumbent, origin, score, seen, store):
    return dict(ast=ast, program_bytes=store.put(ast), incumbent=incumbent, incumbent_origin=origin,
                paid_score_receipt=score["receipt"], seen_set_bytes=store.put(sorted(seen)))


def slot_binding(context, arm, r, slot, p, commitment):
    return {"context": context, "arm": arm, "round": r, "slot": slot, "policy_id": p["id"],
            "roster_sha256": commitment}


def collect(slot, binding, broker, journal):
    store = journal.store
    meter, packet = broker.evaluate(binding, tuple(slot["policy"]["levels"]))
    receipt = authenticated(store.get(meter), broker.authority)
    require(receipt["binding"] == binding, "meter does not bind paid slot")
    attempts = receipt["attempts"]
    require(len(attempts) <= ROWS and [a["ordinal"] for a in attempts] == list(range(1, len(attempts)+1)),
            "invalid physical position sequence")
    slot.update(attempts_receipt=meter, status=receipt["status"], failure_reason=receipt["reason"],
                started_fit_n=len(attempts), complete_fit_n=sum(a["complete"] for a in attempts))
    cpu = None if any(a["cpu_us"] is None for a in attempts) else sum(a["cpu_us"] for a in attempts)
    journal.seal("return-to-broker", {"binding":binding, "meter":meter,
                                     "signed_packet":None if packet is None else store.put(packet)})
    if packet is not None:
        try:
            require(slot["complete_fit_n"] == ROWS and receipt["status"] == "COMPLETE", "partial meter")
            result = open_packet(packet, binding, broker.authority, store)
            slot.update(fit_return=result, status="HARD_VIOLATION" if result["hard_violations"] else "COMPLETE")
        except Exception as exc:
            slot.update(status="FAILED", failure_reason="invalid paid packet: " + type(exc).__name__ + " " + str(exc))
    elif receipt["status"] == "COMPLETE":
        slot.update(status="FAILED", failure_reason="missing paid packet")
    return cpu


def next_roster_witness(old, new, new_state, r, seen, design_sha, frozen, journal):
    store = journal.store
    incumbent = tuple(new_state["incumbent"]["levels"])
    common = store.put({"incumbent": new_state["incumbent"]["id"], "seen": new_state["seen_set_bytes"],
                        "round": r+1, "slots": SLOTS, "remaining_slots": (ROUNDS-r)*SLOTS,
                        "interpreter": frozen["search_interpreter"], "resource_envelope": frozen["resource_envelope"]})
    streams = []
    for ast in (old, new):
        candidates, _ = roster(ast, incumbent, seen, r+1, SLOTS)
        streams.append([policy(v, design_sha, frozen, store) for v in candidates])
    before, after = streams
    left, right = [[p["id"] for p in seq] for seq in streams]
    membership, ordered = set(left) != set(right), left != right
    if membership: kind = "CHANGED_MEMBERSHIP"
    elif ordered: kind = "ORDER_ONLY"
    elif new != old: kind = "EDITED_IDENTICAL_LIST"
    else: kind = "NO_OP"
    result = dict(next_round=r+1, common_inputs=common, before_roster=store.put(before), after_roster=store.put(after),
                  before_policy_ids=left, after_policy_ids=right, ordered_difference=ordered,
                  membership_difference=membership, classification=kind)
    return {**result, "audit_receipt": journal.seal("next-structure-only", result)}


def empty_record(arm, r, prev, registration_sha, design_sha, frozen):
    return dict(schema="AegisDC.T8.r0.round.v1", registration_sha256=registration_sha, design_sha256=design_sha,
                arm=arm, round=r, terminal=r==ROUNDS, status="UNRUN", previous_record_sha256=prev, frozen=frozen,
                before=None, after=None, slots=[empty_slot(i) for i in range(1,SLOTS+1)], feedback=None, selection=None,
                rewrite=dict(reason="UNRUN",credit=None,patch=[],patch_bytes=None), incoming_witness=None,
                next_witness=None, accounting=dict(scheduled_proposals=SLOTS,emitted_proposals=0,
                scheduled_positions=SLOTS*ROWS,started_positions=0,complete_positions=0,actual_process_cpu_us=0,
                allocations_receipt=None), audit=dict(catalogue_and_exclusions=None,roster_seal_before_feedback=None,
                score_release_receipt=None,sandbox_and_read_receipt=None), stop=None)


def prepare(record, live, journal):
    store = journal.store
    before = live["state"]
    record.update(before=before, status="INCOMPLETE")
    levels = tuple(before["incumbent"]["levels"])
    proposed, diag = roster(before["ast"], levels, live["seen"], record["round"], SLOTS)
    cat = store.put(diag)
    proposals = [policy(v, record["design_sha256"], record["frozen"], store) for v in proposed]
    for slot, descriptor in zip(record["slots"], proposals):
        slot.update(policy=descriptor, parent_policy_id=before["incumbent"]["id"],
                    changed_cells=changed(levels, descriptor["levels"]))
    ordered = store.put(proposals)
    record["accounting"]["emitted_proposals"] = len(proposals)
    record["audit"]["catalogue_and_exclusions"] = cat
    record["audit"]["roster_seal_before_feedback"] = journal.seal("reserve-roster", {
        "arm":record["arm"], "round":record["round"], "ordered":ordered, "starting_state":before,
        "frozen":record["frozen"], "exclusions":cat, "slots":store.put(record["slots"]),
        "reserved_positions":SLOTS*ROWS})
    return ordered


def check_issued(slot, seen, design_sha, frozen, store):
    p = slot["policy"]
    try:
        vector = validate_levels(p["levels"])
        require(store.get(p["bytes"])==list(vector) and p["id"]==policy_id(vector,design_sha,frozen["parent_bundle"]),
                "compiled identity disagrees with reservation")
    except (ValueError, KeyError, TypeError) as exc:
        return "INVALID_DESCRIPTOR", str(exc)
    if vector in seen:
        return "DUPLICATE_POSTCOMMIT", "duplicate in prepaid arm"
    return None


def decide(record, live, journal):
    store = journal.store
    slots = record["slots"]
    before = record["before"]
    arm, r = record["arm"], record["round"]
    vectors = [tuple(s["policy"]["levels"]) for s in slots]
    packets = [s["fit_return"] for s in slots]
    incumbent = tuple(before["incumbent"]["levels"])
    ranked, winner, new, reason, credit = rank_and_rewrite(arm, r, before["ast"], incumbent, live["score"], vectors, packets)
    record["feedback"] = store.put({"parent":before["paid_score_receipt"], "own_slots":[x["receipt"] for x in packets]})
    ranking = [i+1 for i in ranked]
    record["selection"] = dict(ranked_eligible_slots=ranking, accepted_slot=None if winner is None else winner+1,
        decision="RETAIN_INCUMBENT" if winner is None else "STRICT_L_GAIN", rank_evidence=store.put({
            "starting_L":live["score"]["L_sum_us"], "ranked":ranking, "own_feedback":record["feedback"]}))
    patch = [] if new == before["ast"] else [{"op":"replace","path":"","value":new}]
    record["rewrite"] = dict(reason=reason,credit=credit,patch=patch,patch_bytes=store.put(patch))
    selected, origin = before["incumbent"], before["incumbent_origin"]
    if winner is not None:
        selected, live["score"] = slots[winner]["policy"], packets[winner]
        origin = dict(kind="PAID_SLOT", round=r, slot=winner+1, parent_policy_id=before["incumbent"]["id"],
                      receipt=live["score"]["receipt"])
    live["seen"].update(vectors)
    after = state(new, selected, origin, live["score"], live["seen"], store)
    record.update(after=after, status="CLOSED")
    live["state"] = after
    if r < ROUNDS:
        record["next_witness"] = next_roster_witness(before["ast"], new, after, r, live["seen"],
                                                     record["design_sha256"], record["frozen"], journal)


def incoming(record, previous, ordered, journal):
    predicted = previous["next_witness"]
    require(ordered == predicted["after_roster"], "successor differs from prepaid prediction")
    before_ids = set(predicted["before_policy_ids"])
    paid = [s["slot"] for s in record["slots"] if s["complete_fit_n"] == ROWS and
            s["fit_return"] is not None and s["policy"]["id"] not in before_ids]
    witness = dict(previous_record=record["previous_record_sha256"], predicted_after_roster=predicted["after_roster"]["sha256"],
                   actual_prepaid_roster=ordered["sha256"], matches=True, actually_paid_new_slots=paid)
    record["incoming_witness"] = {**witness, "audit_receipt":journal.seal("compare-paid-roster", witness)}


def keep_stop(record, reason, started, journal):
    status = "INCOMPLETE" if started else "UNRUN"
    record.update(status=status, selection=None, feedback=None, after=None, next_witness=None,
                  rewrite=dict(reason=status,credit=None,patch=[],patch_bytes=None),
                  stop={"reason":reason,"evidence":journal.seal("stop",{"reason":reason,"arm":record["arm"],"round":record["round"]})})


def run_fit(journal, broker, registration_sha, design_sha, frozen, validate, access_receipt):
    """Runs both registered arms or leaves the incomplete round and its entire suffix."""
    store = journal.store
    shared = policy(ZERO, design_sha, frozen, store)
    baseline = empty_slot(1)
    baseline["policy"] = shared
    prepaid = journal.seal("shared-parent-reservation", {"policy":shared,"rows":ROWS,"fit_commitment":frozen["fit_commitment"]})
    binding = slot_binding(journal.context, "PARENT", 0, 0, shared, prepaid["sha256"])
    base_cpu = collect(baseline, binding, broker, journal)
    baseline_ref = journal.seal("shared-parent-return", {"slot":baseline,"cpu_us":base_cpu})
    reason = None if baseline["status"] == "COMPLETE" else "invalid or missing shared paid parent"
    live, histories, heads = {}, {a:[] for a in ARMS}, dict.fromkeys(ARMS)
    used = dict.fromkeys(ARMS,0)
    if not reason:
        score = baseline["fit_return"]
        origin = {"kind":"PARENT_BASELINE","receipt":score["receipt"]}
        for arm in ARMS:
            live[arm] = {"score":score,"seen":{ZERO},"state":state(BASE,shared,origin,score,{ZERO},store)}
    for r in range(1, ROUNDS+1):
        records = {a:empty_record(a,r,heads[a],registration_sha,design_sha,frozen) for a in ARMS}
        active = reason is None
        if active:
            control, meters, ordered = {}, {a:[] for a in ARMS}, {}
            for a, rec in records.items():
                start = clock_us()
                ordered[a] = prepare(rec,live[a],journal)
                control[a] = clock_us()-start
            if r == 1: require(ordered["O"] == ordered["R"], "first rosters disagree")
            barrier = journal.seal("both-rosters-prepaid", {"round":r,"receipts":{
                a:v["audit"]["roster_seal_before_feedback"] for a,v in records.items()}})
            for a, rec in records.items():
                last = histories[a][-1] if r>1 else None
                if last and ordered[a] != last["next_witness"]["after_roster"]:
                    reason = "prior predicted roster mismatch"
                if control[a] > CONTROLLER_US: reason = "proposal work exceeded CPU cap"
            for a, rec in records.items():
                paid_seen = set(live[a]["seen"])
                for slot in rec["slots"]:
                    if reason: break
                    defect = check_issued(slot,paid_seen,design_sha,frozen,store)
                    if defect:
                        slot["status"], reason = defect
                        slot["failure_reason"] = reason
                        break
                    paid_seen.add(tuple(slot["policy"]["levels"]))
                    binding = slot_binding(journal.context,a,r,slot["slot"],slot["policy"],ordered[a]["sha256"])
                    cpu = collect(slot,binding,broker,journal)
                    meters[a].append(cpu)
                    if slot["fit_return"] is None or cpu is None:
                        reason = slot["failure_reason"] or "unknown CPU account"
            if not reason:
                # No arm gets feedback or decides until all eight full returns are validated.
                release = journal.seal("paired-complete", {"round":r,"both_rosters":barrier,
                    "own_packet_commitments":{a:store.put([s["fit_return"]["receipt"] for s in rec["slots"]])["sha256"]
                                              for a,rec in records.items()}})
            for a, rec in records.items():
                start = clock_us()
                if not reason:
                    rec["audit"]["score_release_receipt"] = journal.seal("release-own",{
                        "arm":a,"round":r,"paired_complete":release["sha256"],
                        "packets":[s["fit_return"]["receipt"] for s in rec["slots"]]})
                    if r>1: incoming(rec,histories[a][-1],ordered[a],journal)
                    decide(rec,live[a],journal)
                rec["audit"]["sandbox_and_read_receipt"] = access_receipt
                control[a] += clock_us()-start
                cpu = None if None in meters[a] else sum(meters[a]) + control[a]
                accounting = rec["accounting"]
                accounting.update(started_positions=sum(s["started_fit_n"] for s in rec["slots"]),
                    complete_positions=sum(s["complete_fit_n"] for s in rec["slots"]),actual_process_cpu_us=cpu,
                    allocations_receipt=journal.seal("allocation",{"arm":a,"round":r,"controller_us":control[a],
                    "per_evaluated_slot_us":meters[a],"position_cap_us":180_000_000,"controller_cap_us":CONTROLLER_US,
                    "reserved_slots":SLOTS,"reserved_positions":SLOTS*ROWS,"barrier":barrier}))
                if cpu is not None: used[a] += cpu
                if control[a] > CONTROLLER_US or used[a] > ARM_US: reason = "control/arm CPU cap"
        if reason:
            for rec in records.values():
                keep_stop(rec,reason,active or (r==1 and not live),journal)
        for a, rec in records.items():
            heads[a] = journal.round(rec,validate)
            histories[a].append(rec)
    locked = None if reason else journal.seal("dual-fixture-or-study-lock",{
        "round_heads":heads,"incumbents":{a:live[a]["state"]["incumbent"] for a in ARMS}})
    return {"context":journal.context,"shared":baseline_ref,"stop":reason,"round_heads":heads,"dual_lock":locked}
