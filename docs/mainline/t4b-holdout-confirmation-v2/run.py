"""Invoke each registered facility at most once and preserve its terminal evidence."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import math
import os
import socket
import subprocess
import sys
import time

from context_t4b import (
    ACT, EPS, PK, PROTOCOL, SOURCES, bundle_inventory, check_runtime, check_sources,
    digest, groups, load_case, read, read_inputs, require, sha, slurm_id, write,
)


def reserve_certificate(case, metrics, certificate):
    if certificate.get("error"):
        return dict(certificate, status="UNRESOLVED", certified_min=None)
    lower = certificate["lower"]
    actions = certificate["plan"]
    chain = all(
        [int(t), task] in metrics["requests"]
        and any(w["task"] == task and w["outcome"] == "APPLIED" for w in metrics["writes"])
        and any(q["task"] == task[:-1]+"R" and q["execution"] and q["fields"] for q in metrics["paid"])
        for t, task in actions.items()
    )
    attained = lower is not None and chain and all(abs(metrics[k] - lower) <= EPS for k in ("L", "U"))
    return dict(certificate, status="ATTAINED" if attained else "UNRESOLVED", certified_min=lower if attained else None,
                own_execution_and_review=chain, native_L=metrics["L"], native_U=metrics["U"])


def maintenance_binding(run, events):
    trace = run["trace"]
    rows = []
    for event in events:
        if event["indicated"] or event["until"] <= event["at"]:
            continue
        contributions = []
        for left, right in zip(trace, trace[1:]):
            t = left["time_s"]
            dt = min(event["until"], right["time_s"]) - max(event["at"], t)
            if dt <= 0:
                continue
            service = left["domains"]["it_service"]
            demand = service["demand"]
            caps = service["capacities"]
            other = min(demand, *(v for k, v in caps.items() if k != "maintenance_support"))
            require(abs(service["delivered"] - min(other, caps["maintenance_support"])) <= EPS, "maintenance service envelope")
            if demand > 0:
                contributions.append(max(0.0, other-service["delivered"])*dt/demand)
        rows.append(dict(event, lost_L_at_cap=math.fsum(contributions)))
    return rows


def find_plan(case):
    from bounds import certificate_for

    try:
        return certificate_for(case)
    except (ValueError, TypeError, KeyError) as error:
        return dict(plan={}, lower=None, latest_best=None, error=type(error).__name__, proof="independent bound unavailable")


def run_position(group, attempt, key, role, lane):
    os.sched_setaffinity(0, {int(lane)})
    from bounds import information
    from frozen_worker import FrozenWorker
    from native_v3 import native_run
    from public_work import choose
    from run_panel import retain
    from score_saved import score

    plan = read(PROTOCOL)
    summary = read_inputs(plan)
    path = ACT/"jobs"/group/attempt
    authorized = read(path/"entry.json")
    require(authorized["job"] == slurm_id() and authorized["condition_sha256"] == os.environ["T4B_CONDITION_SHA"]
            and key in authorized["keys"] and role in authorized["roles"], "position and allocation are registered")
    case = load_case(key, summary)
    evidence = path/"positions"/key/role
    evidence.mkdir(parents=True)
    public = case["native"]["dispatch_program"]["public"]
    certificate = find_plan(case) if role == "ORACLE" else None
    diagnostics = information(case, None, None)["all_paid"] if role == "P" else ()
    bundle = bundle_inventory(plan).get(role)
    worker = FrozenWorker(role, bundle, evidence/"worker.stderr") if bundle else None
    entry = dict(job=slurm_id(), group=group, attempt=attempt, key=key, role=role, pid=os.getpid(), host=socket.gethostname(),
                 input=summary["conditions"][key]["sha256"], input_manifest=os.environ["T4B_CONDITION_SHA"], source=sha(SOURCES),
                 bundle=bundle[0] if bundle else None, public_config=digest(public),
                 worker_pid=worker.child.pid if worker else None)
    started = time.monotonic()
    done = False
    try:
        if worker:
            worker.start(public)
        write(evidence/"native-entry.json", entry)
        run, terminal = native_run(case, role, certificate["plan"] if certificate else {}, diagnostics,
                                   decider=worker.choose if worker else choose)
        done = True
    finally:
        if worker:
            worker.close(failed=not done)

    raw = evidence/"original.jsonl.gz"
    retain(raw, run, terminal)
    metrics = score(case, run, terminal, role)
    proposals = run["v3_proposals"]
    require(metrics["runtime"] == plan["fixed_identities"]["native_runtime_sha256"] and len(proposals) == metrics["clocks"] == 61
            and run["v3_received_maintenance"] == case["maintenance"], "returned runtime, parameters and dispatch clock")
    returned_samples = run["t3_unpurchased_evaluator_only"]
    require(len(returned_samples) == len(diagnostics) and all(x["fields"] is not None for x in returned_samples),
            "P-only evaluator observations")
    if worker:
        require(worker.child.pid != os.getpid() and worker.events == [[q["at"], q["view"], q["proposal"]] for q in proposals],
                "the simulator consumed the public responses")
    if role in ("B_COST", "V_COST_NOPROBE", "B"):
        require(not any(task.endswith("::I") for _, task in metrics["requests"]), "only the registered roles can probe")
    if role == "B_COST":
        require(not any(q["external_refusal"] for q in proposals), "B_cost proposed an inadmissible write")
    actions = [d["decision"]["request"] for d in run["policy_public_decisions"]
               if d["decision"]["request"] and d["decision"]["request"]["phase"] == "A"]
    require(all(right["at"] >= left["planned_end"] + case["maintenance"]["recovery"]
                for left, right in zip(actions, actions[1:])), "maintenance permit interval")
    returned = {k: metrics[k] for k in (
        "L", "U", "person", "tool", "fee", "integral_balances", "first", "checkpoints",
        "closure_changes", "requests", "refusals", "work", "paid", "writes", "curve", "clocks", "runtime",
    )}
    returned.update(entry=entry, raw_sha256=sha(raw), elapsed_s=time.monotonic()-started,
                    public_proposal=digest(worker.events) if worker else None,
                    public_ipc=digest(worker.ipc) if worker else None, diagnostics=returned_samples,
                    oracle=reserve_certificate(case, metrics, certificate) if certificate else None,
                    maintenance=maintenance_binding(run, run["v3_maintenance_events"]) if role == "V_COST" else [],
                    terminal_power_events=terminal["events"] if terminal and role in ("B", "V_COST") else [])
    write(evidence/"score.json", returned)
    print(key, role, "scored", flush=True)


def run_group(group, attempt):
    _, plan = check_sources()
    check_runtime()
    inputs = read_inputs(plan)
    roles = plan["panel"]["role_order"]
    keys = groups(plan)[group]
    bundle_inventory(plan, check_bytes=True)
    job = slurm_id()
    isolated = read(ACT/"isolation/result.json")
    require(isolated["condition_sha256"] == os.environ["T4B_CONDITION_SHA"] and isolated["author_job"] == inputs["author_job"]
            and isolated["facility_entries"] == 0 and len(isolated["witness"]) == 9, "same sealed input and zero-call guard")
    ledger = read(ACT/"registrations"/(group+"-"+attempt+".json"))
    require(ledger["job"] == job and ledger["group"] == group and ledger["attempt"] == attempt
            and ledger["conditions"] == os.environ["T4B_CONDITION_SHA"] and ledger["source"] == sha(SOURCES),
            "Slurm launch ledger")
    cpus = int(os.environ["SLURM_CPUS_PER_TASK"])
    slots = sorted(os.sched_getaffinity(0))
    require(cpus == ledger["cpus"] == len(roles) and len(slots) >= cpus, "registered processor lanes")
    if group.startswith("main-"):
        pilot = read(ACT/"pilot-budget.json")
        require(pilot["continue"] and pilot["conditions"] == ledger["conditions"]
                and pilot["main_minutes"] == ledger["minutes"], "pilot budget authorization")
    path = ACT/"jobs"/group/attempt
    path.mkdir(parents=True, exist_ok=False)
    write(path/"entry.json", dict(job=job, keys=keys, roles=roles, condition_sha256=ledger["conditions"], source=ledger["source"]))
    started = time.monotonic()

    def lane(item):
        index, role = item
        returns = []
        for key in keys:
            log = path/(key+"-"+role+".log")
            with log.open("x") as stream:
                rc = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "position", group, attempt,
                                     key, role, str(slots[index])], stdout=stream, stderr=subprocess.STDOUT, check=False).returncode
            result = path/"positions"/key/role
            returns.append(dict(key=key, role=role, exit_code=rc, entered=(result/"native-entry.json").is_file(),
                                scored=(result/"score.json").is_file()))
        return returns

    with ThreadPoolExecutor(max_workers=cpus) as pool:
        returns = [r for lane_records in pool.map(lane, enumerate(roles)) for r in lane_records]
    write(path/"terminal.json", dict(job=job, positions=returns, complete_wall_s=time.monotonic()-started,
                                    all_positions_entered=all(r["entered"] for r in returns),
                                    all_positions_scored=all(r["scored"] and r["exit_code"] == 0 for r in returns)))
    # Individual scientific failures are recorded by position. The other registered lanes still return.
    print(group, "entries", sum(r["entered"] for r in returns), "scores", sum(r["scored"] for r in returns), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "position":
        run_position(*sys.argv[2:])
    else:
        run_group(*sys.argv[1:])
