"""Independent, public-only engineering witnesses for the one T11 qualification allocation."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


SID = "N/n0"
METHODS = ("MYOPIC", "POMCP")
OUTPUT_FIELDS = {"decision", "timing"}
TREE_FIELDS = ("tree_ns", "leaf_ns", "tree_steps", "leaf_evaluations", "simulations", "nodes", "max_depth")
FROZEN_BUNDLE_SHA256 = "28811a22be4e30a34526448c8379a004a96fd951363c9eeb2eceecad947074cd"
FROZEN_PYTHON_SHA256 = "5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6"
FROZEN = {
    "common.py", "public_work.py",
    *(f"aegis_dc/{s}.py" for s in ("__init__", "joint_evidence", "joint_messages", "joint_resources")),
    *(f"aegis_risk_dispatch/{s}.py" for s in ("__init__", "belief", "knowledge", "planning", "policy", "worker")),
    "aegis_risk_dispatch/settings.json",
    *(f"aegis_action_cost/{s}.py" for s in ("__init__", "forecast", "permit", "planning", "worker")),
    "aegis_action_cost/rules.json",
}


def demand(condition, label):
    if not condition:
        raise AssertionError(label)


def packed(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(packed(obj)).hexdigest()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def static(*, distant=False, window=(0, 3601), budget=(360, 360, 6)):
    # 30 s service + 5 s access. A remote first job travels an additional 55 s.
    subject = dict(id=SID, key="N", interface="inspect-network", worker="engineer", tool="meter",
                   location="rack", start="office" if distant else "rack", expertise="network",
                   read_asset="network-meter", write_asset="network-control", operation="restore",
                   write_window=list(window), read_window=[0, 3600], renew_window=[3600, 3601],
                   allow_initial=True, review=True, primary=True)
    workforce = dict(access_check_s=5, basis="public engineering fixture", facility_id="fixture",
                     feedback_latency_s=15, id="crew", nominal_knowledge_id="declared", schema="fixture",
                     shifts={"engineer": [0, 3600]}, source_note="analytic fixture", time_unit="s",
                     walk_times_s={"hall": 55}, work_times_s={"inspect-network": 30})
    edge = {"id": "hall", "kind": "access", "from": "office", "to": "rack", "bidirectional": True,
            "requires_qualification_ids": ["network"]}
    return dict(subjects=[subject], workforce=workforce, clock=list(range(0, 3601, 60)),
                business_ticks=[900, 1800, 2700, 3600], routes=[SID], resources=list(budget),
                route_graph=[edge], fixed_epochs=list(range(0, 3600, 300)), fixed_ttl=720,
                paid_ttl=2100, latency=15, renew_at=1680)


def record(kind, sid, sampled, arrived, until, source, value, record_type=None):
    return dict(kind=kind, subject=sid, sampled=sampled, arrived=arrived, until=until, source=source,
                origin=f"{source}/{sid}@{sampled}", value=value, record_type=record_type, copied_from=None)


def history(now, alarm=None):
    rows = [record("order", SID, 0, 0, 3601, "work-desk", "OPEN/MAINT-1200")]
    if alarm is not None:
        # The network source plus an alarm arriving at 45 identifies an early defect.
        # At 80 a healthy and masked grid also remain possible under the frozen prior.
        rows += [record("prior", SID, 15, 30, 795, "configuration-register", "FILED", "revision_review"),
                 record("alarm", SID, 15, alarm, alarm + 600, "network-alarm", "ALARM")]
    return dict(time=now, records=rows, work=[], paid=[], writes=[], fixed=[], issued=[])


def job(phase, start, duration=35, parent=None, execution=None, epoch=None):
    return dict(task=f"{SID}::{phase}", subject=SID, phase=phase, at=start, planned_end=start + duration,
                worker="engineer", tool="meter", instance=SID, parent=parent, execution=execution,
                parent_epoch=epoch, patrol_slot=None)


def completed(view, req, fields=None):
    view["issued"].append(req)
    sid, task, end = req["subject"], req["task"], req["planned_end"]
    view["work"].append(dict(arrived_at_s=end + 15, observed_at_s=end, origin_id="workforce:" + task,
                             source_id="workforce-execution-report", task_id=task, status="completed",
                             location_id="rack", reason=None, coverage="complete", basis="public fixture"))
    if req["phase"] == "A":
        view["writes"].append(dict(task=task, subject=sid, operation="restore", at=end, arrived=end + 15,
                                   execution=f"{task}@{end}", epoch=1, source="work-execution",
                                   origin="write/" + task, outcome="APPLIED"))
    elif fields is not None:
        view["paid"].append(dict(task=task, subject=sid, phase=req["phase"], source="onsite/" + sid,
                                 origin=f"{task}@{end}", worker=req["worker"], tool=req["tool"],
                                 issued=req["at"], sampled=end, arrived=end + 15, until=end + 2100,
                                 parent=req["parent"], execution=req["execution"], parent_epoch=req["parent_epoch"],
                                 physical_epoch=req["parent_epoch"] or 0, fields=fields))


def choice_fixtures():
    quiet = history(1320)
    completed(quiet, job("I", 1200), {"g": 1.0, "e": 1.0})
    return {
        # The authenticated OK reports a sufficient grid. A is legal and costs work, and cannot help.
        "WAIT": (static(window=(1320, 1356)), quiet),
        # Taking I moves the crew to the rack. Only that crew can use the single later write slot.
        "I": (static(distant=True, window=(240, 277)), history(120, alarm=45)),
        # The certain correctable deficit and a write window closing before the next tick require A now.
        "A": (static(window=(120, 156)), history(120, alarm=45)),
    }


def run_worker(bundle, role, pub, views, *, reject=False):
    frozen = role == "V_COST"
    entry = bundle / ("aegis_action_cost/worker.py" if frozen else "worker.py")
    args = [sys.executable, "-I", "-B"]
    if frozen:
        args.append("-S")
    args += [str(entry), role]
    messages = [{"public": pub}, *({"view": v} for v in views), {"close": True}]
    env = dict(LANG="C.UTF-8", LC_ALL="C.UTF-8", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    outcome = subprocess.run(args, input=b"".join(packed(m) + b"\n" for m in messages),
                             capture_output=True, cwd=bundle, env=env, check=False)
    replies = [json.loads(line) for line in outcome.stdout.splitlines()]
    demand(replies and replies[0] == {"ready": True, "role": role}, f"{role} public handshake: "
           + outcome.stderr.decode("utf8", "replace")[-1000:])
    if reject:
        demand(outcome.returncode != 0 and len(replies) == 1, f"{role} accepted invalid public envelope")
        return outcome.returncode
    demand(outcome.returncode == 0 and len(replies) == len(messages) - 1, f"{role} reply count/exit: "
           + outcome.stderr.decode("utf8", "replace")[-1000:])
    for reply in replies[1:]:
        if not frozen:
            demand(set(reply) == OUTPUT_FIELDS, "new worker envelope")
            timing = reply["timing"]
            demand(all(type(timing[f]) is int and timing[f] >= 0 for f in
                       (*TREE_FIELDS, "effective_choices", "worker_wall_ns", "worker_cpu_ns")), "metric fields")
            demand(timing["worker_wall_ns"] >= timing["tree_ns"] + timing["leaf_ns"], "exclusive clocks")
            demand(timing["reason"] == reply["decision"]["rationale"]["reason"], "reason identity")
    return replies[1:]


def phase(decision):
    return decision["request"]["phase"] if decision["request"] else "WAIT"


def wait_inspect_act(bundle):
    details = {}
    for want, (pub, view) in choice_fixtures().items():
        for role in METHODS:
            reply, = run_worker(bundle, role, pub, [view])
            seen = phase(reply["decision"])
            demand(seen == want, f"{role} expected {want}, observed {seen}")
            demand(reply["timing"]["reason"] == "VALUE", "choice was forced by root guard")
            if role == "POMCP":
                demand(reply["timing"]["effective_choices"] >= 2, "value witness requires a genuine choice")
            details[role + "/" + want] = dict(phase=seen, public_sha256=digest({"public": pub, "view": view}),
                                               decision_sha256=digest(reply["decision"]))
    return details


def public_action_mask(bundle, gate):
    from baselines import elective_menu
    pub = static()
    done = history(120)
    completed(done, job("A", 0))
    completed(done, job("R", 60, parent=SID + "::A", execution=SID + "::A@35", epoch=1),
              {"g": 1.0, "e": 0.0})
    demand(gate.admit(pub, done, pub["subjects"][0], "I")[0] is not None, "I otherwise gate-admissible")
    demand(list(elective_menu(pub, done, gate)) == [None], "I after A and R")
    decisions = {}
    for role in (*METHODS, "V_COST"):
        reply, = run_worker(bundle, role, pub, [done])
        decision = reply if role == "V_COST" else reply["decision"]
        demand(phase(decision) == "WAIT", f"{role} issued after A/R")
        demand(all(row["first"] is None for row in decision["rationale"]["continuation_table"]),
               f"{role} exposed I after A/R")
        decisions[role] = digest(decision)
    pub = static()
    view = history(120)
    for sid in ("secondary", "expired", "copied", "unopened"):
        pub["subjects"].append(dict(pub["subjects"][0], id=sid, primary=sid != "secondary"))
        if sid != "unopened":
            view["records"].append(dict(view["records"][0], subject=sid, until=120 if sid == "expired" else 3601,
                                        copied_from="order-source" if sid == "copied" else None))
    demand(list(elective_menu(pub, view, gate)) == [None, (SID, "A"), (SID, "I")], "primary/live/original")
    pub = static()
    pub["subjects"][0]["read_window"] = [0, 156]
    view = history(120)
    demand(gate.admit(pub, view, pub["subjects"][0], "A")[0] is not None, "root write initially legal")
    demand(list(elective_menu(pub, view, gate)) == [None, (SID, "I")], "successful A must fit a subsequent R")
    return dict(done_before_I=decisions, primary_live_original=True, no_unschedulable_review=True)


def required_pending_refusal(bundle):
    due = history(60)
    completed(due, job("A", 0))
    pending = history(60)
    pending["issued"].append(job("I", 0, 90))
    renewal_pub = static()
    renewal_pub["subjects"][0]["renew_window"] = [1680, 3600]
    renewal = history(1680)
    completed(renewal, job("I", 1200), {"g": 1.0, "e": 1.0})
    exhausted = history(120)
    unsupported = history(120)
    # Two incompatible original readings with the same origin and sample time.
    meter = dict(field=SID, sampled=100, arrived=115, until=820, origin="meter/N@100", source="meter/" + SID)
    unsupported["fixed"] = [dict(meter, ok=True), dict(meter, ok=False)]
    notes = {}
    for role in METHODS:
        observations = {}
        for label, pub, view, want, reason in (
            ("own_review", static(), due, "R", "MANDATORY_OWN_WORK"),
            ("own_renewal", renewal_pub, renewal, "X", "MANDATORY_OWN_WORK"),
            ("pending_I", static(distant=True), pending, "WAIT", "AWAIT_OWN_PAID_RESULT"),
            ("zero_budget", static(budget=(0, 0, 0)), exhausted, "WAIT", None),
            ("conflict", static(), unsupported, "WAIT", "UNSUPPORTED_PUBLIC_EVIDENCE"),
        ):
            reply, = run_worker(bundle, role, pub, [view])
            decision, timing = reply["decision"], reply["timing"]
            demand(phase(decision) == want and (reason is None or timing["reason"] == reason), role + "/" + label)
            demand(timing["simulations"] == 0, "no tree for mandatory, pending, unsupported or exhausted root")
            if label == "own_review":
                req = decision["request"]
                demand((req["parent"], req["execution"], req["parent_epoch"]) ==
                       (SID + "::A", SID + "::A@35", 1), "review binding")
            if label == "own_renewal":
                demand(decision["request"]["parent"] == SID + "::I", "renewal binding")
            if label == "zero_budget":
                demand({(sid, p, r) for sid, p, r in decision["refusals"]} >=
                       {(SID, "A", "BUDGET"), (SID, "I", "BUDGET")}, "genuine gate refusals")
            observations[label] = dict(chosen=phase(decision), reason=timing["reason"], refusals=decision["refusals"])
        notes[role] = observations
    return notes


def one_intervention_voi(bundle):
    pub = static(distant=True, window=(240, 277))
    view = history(120, alarm=80)
    reply, = run_worker(bundle, "MYOPIC", pub, [view])
    rows = reply["decision"]["rationale"]["continuation_table"]
    inspect = next(row for row in rows if row["first"] == [SID, "I"])
    table = inspect["table"]
    demand(set(table) == {"CONFIG", "LIMIT", "UNKNOWN"}, "fixed report partition before demand")
    demand(table["CONFIG"]["continue_with"] == [SID] and table["LIMIT"]["continue_with"] == []
           and table["UNKNOWN"]["continue_with"] == [], "one common legal choice per report")
    demand(all(abs(x - y) < 1e-8 for x, y in zip(table["CONFIG"]["cost"], [0, 160, 3, 250], strict=True)),
           "CONFIG: 90 s inspection, 35 s write, 35 s review; no pre-demand loss")
    demand(table["UNKNOWN"]["probability"] == 1 / 32 and abs(sum(v["probability"] for v in table.values()) - 1) < 1e-9,
           "normalized UNKNOWN and report probabilities")
    demand(all(abs(inspect["vector"][j] - sum(v["probability"] * v["cost"][j] for v in table.values())) < 1e-8
               for j in range(4)), "mixture of conditional action values")
    # Two open eligible objects exercise the cardinality bound on direct and delayed continuations.
    twin_pub = static()
    twin_pub["subjects"].append(dict(twin_pub["subjects"][0], id="C/c0", key="C", allow_initial=True))
    twin_pub["routes"].append("C/c0")
    twin_view = history(120)
    twin_view["records"].append(dict(twin_view["records"][0], subject="C/c0", origin="order/C/c0"))
    twin, = run_worker(bundle, "MYOPIC", twin_pub, [twin_view])
    paired_rows = twin["decision"]["rationale"]["continuation_table"]
    demand({tuple(v["first"]) for v in paired_rows if v["first"]} >= {(SID, "A"), ("C/c0", "A")}, "two legal writes")
    for row in paired_rows:
        limit = 0 if row["first"] and row["first"][1] == "A" else 1
        demand(all(len(v["continue_with"]) <= limit for v in row["table"].values()), "elective A cap")
    return dict(report_table=table, selected=phase(reply["decision"]), two_work_orders=len(paired_rows))


class KnownReport:
    def __init__(self):
        self.draws = 0

    def random(self):
        self.draws += 1
        return 0.5


def shared_delivered_report(bundle, settings, gate):
    from aegis_risk_dispatch import belief
    from baselines import elective_menu, guard
    from pomcp import Trajectory
    pub = static(distant=True, window=(240, 277))
    view = history(120, alarm=80)
    after = deepcopy(view)
    weights, _ = belief.posterior(pub, view, settings)
    worlds = [w for w, _ in weights if w.family == "network" and w.cause == "defect"
              and w.alarm == "early" and w.grid == 0.25]
    left = next(w for w in worlds if w.demand == 600)
    right = next(w for w in worlds if w.demand == 1200)
    traces = []
    for world in (left, right):
        stream = KnownReport()
        path = Trajectory(pub, view, world, settings, gate, stream)
        request = elective_menu(pub, path.view, gate)[SID, "I"]
        demand(request["planned_end"] == 210, "public route and inspection duration")
        path.issue(request)
        before_delivery = path.advance(180)
        demand(not path.view["paid"] and not path.view["work"] and stream.draws == 0, "no prospective observation")
        demand(guard(pub, path.view, gate)[0] == "AWAIT_OWN_PAID_RESULT", "tree waits for own observation")
        delivered = path.advance(240)
        demand(stream.draws == 1 and len(path.view["paid"]) == 1, "one RNG draw for one delivered I")
        row = path.view["paid"][0]
        demand(row["task"] == SID + "::I" and row["source"] == "onsite/" + SID
               and row["sampled"] == 210 and row["arrived"] == 225, "shared report identity and calendar")
        from aegis_risk_dispatch.knowledge import decode
        demand(decode("N", row["fields"]) == "CONFIG", "informative report signature")
        menu = tuple(elective_menu(pub, path.view, gate))
        demand(menu == (None, (SID, "A")), "same admissible continuation after CONFIG")
        traces.append((before_delivery, delivered, deepcopy(path.view), menu))
    demand(traces[0] == traces[1] and view == after, "common public result/history and immutable input")
    decisions = {}
    for role in METHODS:
        left_reply, = run_worker(bundle, role, pub, [traces[0][2]])
        right_reply, = run_worker(bundle, role, pub, [traces[1][2]])
        demand(left_reply["decision"] == right_reply["decision"], role + ": shared reported history diverged")
        decisions[role] = digest(left_reply["decision"])
    return dict(worlds_differ_on="hypothetical demand at 600 versus 1200", common_phase="I",
                sampled=210, arrived=225, report="CONFIG", post_report_history=digest(traces[0][2]),
                same_cold_worker_decisions=decisions)


def simulated_silence(settings, gate):
    from aegis_risk_dispatch import belief
    from baselines import guard
    from pomcp import Trajectory, search
    pub, view = static(), history(0)
    weights, _ = belief.posterior(pub, view, settings)
    early = next(w for w, _ in weights if w.family == "network" and w.alarm == "early")
    late = next(w for w, _ in weights if w.family == "network" and w.alarm == "late")
    demand(belief.arrival_options(early) == {20, 45, 80}, "early hypothesis and dated alarm law")
    paths = []
    for world in (early, late):
        stream = KnownReport()
        trace = Trajectory(pub, view, world, settings, gate, stream)
        tokens = [trace.advance(t) for t in (60, 120)]
        demand(trace.view["records"] == view["records"] and not trace.view["fixed"] and stream.draws == 0,
               "no generated external free measurements")
        demand(guard(pub, trace.view, gate, has_support=True)[0] == "VALUE", "root-sampled hypothesis still supported")
        paths.append((tokens, deepcopy(trace.view)))
    demand(paths[0] == paths[1], "simulated silence split compatible histories")
    actual, _ = belief.posterior(pub, history(120), settings)
    support = {w for w, _ in actual}
    demand(early not in support and late in support, "actual observed 120 s silence retains its frozen likelihood")
    # Observe the unmodified search invocation in the fixture process. The frozen real-root
    # posterior's function code identifies calls even if a module bound an import alias.
    posterior_calls = []

    def observe_calls(frame, event, arg):
        if event == "call" and frame.f_code is belief.posterior.__code__:
            posterior_calls.append(frame.f_locals["view"]["time"])

    sys.setprofile(observe_calls)
    try:
        _, _, _, _, metrics = search(pub, view, weights, 1, settings, gate)
    finally:
        sys.setprofile(None)
    demand(metrics["simulations"] == 128 and metrics["max_depth"] >= 3, "actual tree crossed the silent 120s tick")
    demand(all(t == view["time"] for t in posterior_calls), "tree used real-channel silence below the root")
    return dict(root_supported=True, equal_simulated_histories=True, real_early_supported=False,
                real_late_supported=True, simulated_timestamps=[60, 120], real_posterior_call_times=posterior_calls)


def seed_replay(bundle):
    import pomcp
    pub, view = choice_fixtures()["I"]
    expected = int.from_bytes(hashlib.sha256(b"AegisDC/T11/POMCP/v1|" + packed({"public": pub, "view": view}))
                              .digest()[:16], "big")
    demand(pomcp.seed(pub, view) == expected, "canonical SHA-256 root seed")
    permuted = dict(reversed(list(view.items())))
    demand(pomcp.seed(pub, permuted) == expected, "object key insertion order changed the seed")
    alternative = deepcopy(pub)
    alternative["workforce"]["source_note"] = "夹具"
    alt_seed = int.from_bytes(hashlib.sha256(b"AegisDC/T11/POMCP/v1|" + packed({"public": alternative, "view": view}))
                              .digest()[:16], "big")
    demand(alt_seed != expected and pomcp.seed(alternative, view) == alt_seed, "canonical non-ASCII UTF-8")
    first, repeated = run_worker(bundle, "POMCP", pub, [view, permuted])
    cold, = run_worker(bundle, "POMCP", pub, [view])
    demand(first["decision"] == repeated["decision"] == cold["decision"], "fresh tree/cold worker seed replay")
    counters = ("tree_steps", "leaf_evaluations", "simulations", "nodes", "max_depth", "effective_choices")
    demand(all(len({row["timing"][key] for row in (first, repeated, cold)}) == 1 for key in counters),
           "deterministic search counters")
    branches = first["decision"]["rationale"]["continuation_table"]
    demand(sum(branch["visits"] for branch in branches) == 128 and all(branch["visits"] > 0 for branch in branches),
           "all admitted root edges visited, exactly 128 sequential simulations")
    return dict(seed_hex=f"{expected:032x}", replayed_decision=digest(first["decision"]),
                visits=[branch["visits"] for branch in branches])


def separate_leaf(bundle, settings, gate):
    from aegis_risk_dispatch import knowledge
    from pomcp import Trajectory
    pub, view = choice_fixtures()["I"]
    world = next(w for w, _ in knowledge.catalogue("ordinary") if w.family == "network"
                 and w.cause == "defect" and w.alarm == "early" and w.grid == 0.25)
    stream = KnownReport()
    path = Trajectory(pub, view, world, settings, gate, stream)
    req, _ = gate.admit(pub, view, pub["subjects"][0], "I")
    path.issue(req)
    path.advance(180)
    loss, person, fees = path.finish()
    demand(stream.draws == 1 and [r["phase"] for r in path.view["issued"]] == ["I"], "late leaf report cannot buy A")
    demand(person == 90 and fees == 1 and loss > 0, "late report only pays for I")

    rejected=history(120)
    previous=job("I",0,duration=90)
    rejected["issued"].append(previous)
    rejected["work"].append(dict(task_id=previous["task"],source_id="workforce-execution-report",
        observed_at_s=0,arrived_at_s=15,status="rejected",reason="DECLARED_TASK_ADMISSION_REFUSAL",
        location_id=None,origin_id="workforce:"+previous["task"],coverage="THIS_ISSUED_TASK_ONLY",
        basis="SYNTHETIC_FINITE_TIMED_EXECUTION_CHANNEL"))
    not_started=Trajectory(static(),rejected,world,settings,gate,KnownReport())
    _,person_zero,one_fee=not_started.finish()
    demand(person_zero==0 and one_fee==1 and len(not_started.view["issued"])==1,
           "immediate workforce rejection: no occupied time, one fee, no follow-up")

    # A rejected public-model intervention still consumes its 35 s and one issuance. A successful
    # intervention must complete a linked R. The 3600 s renewal grant cannot fit either X.
    plant = static()
    plant["subjects"][0].update(id="LB", key="LB", operation="restore_path")
    plant["subjects"].append(dict(plant["subjects"][0], id="LC", key="LC", primary=False,
                                  operation="correct_sensing", allow_initial=False))
    plant["routes"] = ["LB"]
    public = history(120)
    public["records"][0].update(subject="LB", origin="order/LB")
    branches = {}
    for cause, outcome, expected_phases, expected_cost in (
        ("legacy", "NO_EFFECT", ["A"], (35, 1)), ("path", "APPLIED", ["A", "R"], (70, 2)),
    ):
        world = next(w for w, _ in knowledge.catalogue("power_board") if w.cause == cause)
        path = Trajectory(plant, public, world, settings, gate, KnownReport())
        req, _ = gate.admit(plant, path.view, plant["subjects"][0], "A")
        path.issue(req)
        path.advance(180)
        loss, person, fees = path.finish()
        demand([r["phase"] for r in path.view["issued"]] == expected_phases and (person, fees) == expected_cost,
               f"{cause}: committed work once and only incurred obligations")
        receipt, = path.view["writes"]
        demand(receipt["outcome"] == outcome, "predicted write completion")
        if cause == "path":
            review = path.view["issued"][1]
            demand(review["parent"] == req["task"] and review["execution"] == receipt["execution"]
                   and review["parent_epoch"] == receipt["epoch"], "mandatory leaf review retains execution binding")
        branches[cause] = dict(outcome=outcome, issued=expected_phases, person=person, fees=fees, loss=loss)
    root, = run_worker(bundle, "POMCP", pub, [view])
    timing = root["timing"]
    demand(timing["simulations"] == 128 and 0 < timing["leaf_evaluations"] <= 128
           and 128 <= timing["tree_steps"] <= 512 and 1 <= timing["max_depth"] <= 4 and timing["nodes"] > 0,
           "registered root, transfer, depth and leaf budgets")
    demand(timing["leaf_ns"] > 0 and timing["tree_ns"] > 0, "separate measured tree and leaf intervals")
    return dict(immediate_workforce_rejection={"person":person_zero,"fees":one_fee,"follow_up":0},
                late_report_issued=["I"], late_report_person=90, late_report_fee=1,
                write_branches=branches, search={k: timing[k] for k in TREE_FIELDS})


def oat_single_change(bundle, gate):
    from aegis_action_cost import planning
    from aegis_risk_dispatch import policy
    import worker
    center, _ = worker.configuration(bundle, "MYOPIC")
    roots = {"lambda": ("versions", "V3"), "kappa": ("fee_in_person_seconds",),
             "match": ("fixed_match_probability",), "unknown": ("unknown_report_probability",)}
    levels = {"lambda": (0.5, 2), "kappa": (15, 60), "match": (0.85, 0.99), "unknown": (1 / 64, 1 / 16)}
    pub = static(distant=True, window=(240, 277))
    view = history(120, alarm=80)
    policy.choose_first = planning.choose_first
    details = {}
    for name, fields in roots.items():
        for label, value in zip(("low", "high"), levels[name], strict=True):
            role = name + "_" + label
            expected = deepcopy(center)
            target = expected if len(fields) == 1 else expected[fields[0]]
            target[fields[-1]] = value
            actual, _ = worker.configuration(bundle, role)
            demand(actual == expected, role + " changed more than its nominated setting")
            reference = policy.decide("V3", pub, view, expected, gate)
            observed, = run_worker(bundle, role, pub, [view])
            demand(digest(reference) == digest(observed["decision"]), role + " frozen dispatch mismatch")
            demand(all(observed["timing"][field] == 0 for field in TREE_FIELDS), "OAT was routed through tree search")
            details[role] = dict(parameter=".".join(fields), value=value, same_frozen_decision=digest(reference))
    return details


def private_ingress_rejected(bundle):
    pub = static()
    clean = history(120)
    premature = deepcopy(clean)
    premature["records"][0]["arrived"] = 121
    injected = dict(clean, evaluator_state="unregistered_fixture_field")
    return {role: {label: run_worker(bundle, role, pub, [bad], reject=True)
                   for label, bad in (("unknown_key", injected), ("prospective_record", premature))}
            for role in METHODS}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    job_id = os.environ.get("SLURM_JOB_ID")
    demand(job_id and sys.flags.isolated, "qualification requires the isolated interpreter in a Slurm allocation")
    bundle = args.bundle.resolve(strict=True)
    paths = list(bundle.rglob("*"))
    demand(not any(p.is_symlink() for p in paths), "symbolic link in public bundle")
    files = {p.relative_to(bundle).as_posix(): p for p in paths if p.is_file()}
    demand(set(files) == FROZEN | {"baselines.py", "pomcp.py", "worker.py"}, "public-only bundle allowlist")
    members = {name: file_sha(path) for name, path in files.items()}
    demand(digest({name: members[name] for name in FROZEN}) == FROZEN_BUNDLE_SHA256, "frozen public source identity")
    demand(file_sha(Path(sys.executable)) == FROZEN_PYTHON_SHA256, "frozen interpreter identity")
    sys.path.insert(0, str(bundle))
    from aegis_action_cost.permit import Gate
    import worker
    settings, rules = worker.configuration(bundle, "MYOPIC")
    gate = Gate(rules["exclusive_recovery_s"])
    checks = {
        "wait_inspect_act": lambda: wait_inspect_act(bundle),
        "public_action_mask": lambda: public_action_mask(bundle, gate),
        "required_pending_refusal": lambda: required_pending_refusal(bundle),
        "one_intervention_voi": lambda: one_intervention_voi(bundle),
        "shared_delivered_report": lambda: shared_delivered_report(bundle, settings, gate),
        "simulated_silence": lambda: simulated_silence(settings, gate),
        "seed_replay": lambda: seed_replay(bundle),
        "separate_leaf": lambda: separate_leaf(bundle, settings, gate),
        "oat_single_change": lambda: oat_single_change(bundle, gate),
        "private_ingress_rejected": lambda: private_ingress_rejected(bundle),
    }
    report = dict(source="public engineering fixtures", job=job_id, qualification_sha256=file_sha(Path(__file__)),
                  bundle_sha256=digest(members), frozen_public_bundle_sha256=FROZEN_BUNDLE_SHA256,
                  python_sha256=FROZEN_PYTHON_SHA256, native_runs=0, facility_calls=0, checks={}, failed=[])
    with args.output.open("x", encoding="utf-8") as output:
        for name, probe in checks.items():
            print(json.dumps({"check": name, "state": "started"}), flush=True)
            try:
                report["checks"][name] = {"passed": True, "observations": probe()}
            except Exception as exc:
                report["checks"][name] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
                report["failed"].append(name)
            print(json.dumps({"check": name, **report["checks"][name]}, sort_keys=True, allow_nan=False), flush=True)
        report["passed"] = not report["failed"]
        report["status"] = "PASS" if report["passed"] else "FAIL"
        json.dump(report, output, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
        output.write("\n")
    if not report["passed"]:
        raise SystemExit("Failed public qualifications: " + ", ".join(report["failed"]))


if __name__ == "__main__":
    main()
