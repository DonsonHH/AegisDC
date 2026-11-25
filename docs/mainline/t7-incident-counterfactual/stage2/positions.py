"""Execute each registered native position once; publication gates all five roles."""

from concurrent.futures import ThreadPoolExecutor
from itertools import product
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback

from study import ACT, FAMILIES, HERE, KEYS, PK, ROLES, digest, need, packed, publish, read, save, sha, stage, verified_release


def dutch_window(case, role, ticks, terminal, score):
    if case["evaluation"]["family"] != "NETHERLANDS" or role not in ("V_COST", "B"):
        return None
    from aegis_action_cost.permit import Gate
    cfg = case["attachment"]
    fault, restored = cfg["fault_at"], cfg["restore_at"]
    if fault is None:
        return {"fault": None}
    span_loss = math.fsum(max(0, min(restored,b)-max(fault,a))*max(0,d-y)/d for a,b,d,y in score["curve"] if d > 0)
    effect = next((w["at"] for w in score["writes"] if w["task"] == "NR::A" and w["outcome"] == "APPLIED"), None)
    result = {"fault": fault, "restored": restored, "tripped": any(e["t"] == fault and e.get("tripped") is True
              for e in terminal["events"]), "transfer_loss": span_loss, "effective_NR": effect}
    if role == "V_COST":
        pub = case["native"]["dispatch_program"]["public"]
        subject = next(s for s in pub["subjects"] if s["id"] == "NR")
        gate = Gate(case["maintenance"]["recovery"])
        legal = []
        for tick in ticks:
            v, answer = tick["view"], tick["decision"]
            if v["time"] >= fault:
                break
            allowed, _ = gate.admit(pub, v, subject, "A")
            if allowed and allowed["planned_end"] < fault:
                request = answer["request"]
                legal.append({"time": v["time"], "actual": request["task"] if request else "WAIT",
                              "view_sha256": digest(v), "reason": answer.get("rationale",{}).get("reason")})
        result.update(legal_NR_ticks=legal, later_pump=[w for w in score["writes"] if w["task"] == "NP::A"],
                      valid_pre_fault_initial_reads=[q["task"] for q in score["paid"] if q["phase"] == "I"
                                                     and q["fields"] is not None and q["arrived"] < fault])
    return result


def one(group, key, role, cpu):
    job = os.environ["SLURM_JOB_ID"]
    spec, _ = stage(False)
    release = verified_release()
    gate = read(ACT / group / "start.json")
    need(gate["job"] == job and [key, role] in gate["positions"] and cpu in gate["cpu_ids"], "position outside allocation")
    os.sched_setaffinity(0, {cpu})
    folder = ACT / group / (key + "-" + role)
    folder.mkdir()
    start = time.monotonic()
    source = ACT / "inputs" / (key + ".json")
    item = read(ACT / "pre-score/input-manifest.json")["conditions"][key]
    need(sha(source) == item["sha256"], "registered input row " + key)
    case = read(source)
    from context_t4b import bundle_inventory
    from frozen_worker import FrozenWorker
    from native_v3 import native_run
    from bounds import information
    from score_saved import score
    from run_panel import retain
    public = case["native"]["dispatch_program"]["public"]
    binding = bundle_inventory(read(PK / "run-manifest.json"))[role]
    need(binding[0] == spec["role_bundles"][role], "frozen public bundle")
    diagnostics = information(case, None, None)["all_paid"] if role == "P" else ()
    with (folder / "ipc.jsonl").open("xb") as wire:
        class RecordedWorker(FrozenWorker):
            def message(self, value):
                wire.write(packed({"send": value}) + b"\n")
                wire.flush()
                answer = super().message(value)
                wire.write(packed({"return": answer}) + b"\n")
                wire.flush()
                return answer

        child = RecordedWorker(role, binding, folder / "worker.stderr")
        failed = True
        try:
            child.start(public)
            entry = {"job": job, "group": group, "key": key, "role": role, "host_pid": os.getpid(),
                     "worker_pid": child.child.pid, "input_sha256": item["sha256"], "bundle_sha256": binding[0],
                     "execution_revision": os.environ["T7_EXEC_REV"], "input_publication": release["publication_commit"]}
            save(folder / "entry.json", entry)
            run, terminal = native_run(case, role, {}, diagnostics, decider=child.choose)
            retain(folder / "original.jsonl.gz", run, terminal)
            failed = False
        finally:
            child.close(failed=failed)
            wire.write(packed({"worker_exit": child.child.returncode}) + b"\n")
    metrics = score(case, run, terminal, role)
    ticks, proposals = run["policy_public_decisions"], run["v3_proposals"]
    need(metrics["runtime"] == spec["native_runtime_sha256"] and len(proposals) == metrics["clocks"] == 61
         and run["v3_received_maintenance"] == case["maintenance"], "native runtime, clock and maintenance return")
    need(child.child.pid != os.getpid() and child.events == [[q["at"], q["view"], q["proposal"]] for q in proposals],
         "isolated IPC agrees with the native proposal stream")
    need(len(run["t3_unpurchased_evaluator_only"]) == len(diagnostics)
         and all(q["fields"] is not None for q in run["t3_unpurchased_evaluator_only"]), "private evaluator projections")
    acts = [d["decision"]["request"] for d in ticks if d["decision"]["request"] and d["decision"]["request"]["phase"] == "A"]
    need(all(b["at"] >= a["planned_end"] + case["maintenance"]["recovery"] for a,b in zip(acts,acts[1:])),
         "frozen admission interval")
    if role == "B":
        need(not any(task.endswith("::I") for _,task in metrics["requests"]), "original B proposal")
    need(all(math.isfinite(metrics[m]) and metrics[m] >= 0 for m in ("L","U","person","tool","fee")), "nonfinite or negative score")
    save(folder / "score.json", metrics)
    result = dict(entry, status="SCORED", L=metrics["L"], U=metrics["U"], person=metrics["person"], tool=metrics["tool"],
                  fee=metrics["fee"], decisions=metrics["clocks"], first_request=metrics["requests"][:1],
                  dutch_window=dutch_window(case, role, ticks, terminal, metrics),
                  ipc_digest=digest(child.ipc), proposal_digest=digest(child.events),
                  elapsed_s=time.monotonic()-start, rss_host_worker_kib=[resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                                                       resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss])
    result["files_sha256"] = {n: sha(folder / n) for n in ("entry.json","original.jsonl.gz","score.json","ipc.jsonl","worker.stderr")}
    save(folder / "result.json", result)


def launch(group, position, cpu):
    key, role = position
    with (ACT / group / (key + "-" + role + ".log")).open("xb") as fp:
        child = subprocess.run([sys.executable, "-B", str(HERE / "positions.py"), "unit", group, key, role, str(cpu)],
                               stdout=fp, stderr=subprocess.STDOUT)
    return key + "-" + role, child.returncode


def group_scores(group):
    term = read(ACT / group / "terminal.json")
    result = {}
    for key, role in term["positions"]:
        path = ACT / group / (key+"-"+role) / "result.json"
        if path.is_file():
            need(sha(path) == term["result_sha256"][key+"-"+role], "group result identity")
            result.setdefault(key, {})[role] = read(path)
    return result


def mechanism_report(scores):
    rows = []
    for key in KEYS:
        if not key.startswith("6-"):
            continue
        v = scores.get(key,{}).get("V_COST")
        b = scores.get(key,{}).get("B")
        f, g = (s.get("dutch_window") if s else None for s in (v,b))
        if f is None:
            rows.append({"key": key, "wait_failure": None, "paired_B_witness": None})
            continue
        if f["fault"] is None:
            rows.append({"key": key, "fault": None, "wait_failure": False, "paired_B_witness": False if g else None})
            continue
        last = f["legal_NR_ticks"][-1] if f["legal_NR_ticks"] else None
        late = f["effective_NR"] is None or f["effective_NR"] >= f["fault"]
        failing = bool(last and late and f["tripped"] and f["transfer_loss"] > 1e-7)
        waited = bool(failing and last["actual"] == "WAIT")
        b_witness = None if not g else bool(failing and g["effective_NR"] is not None and g["effective_NR"] < f["fault"]
                        and not g["tripped"] and f["transfer_loss"]-g["transfer_loss"] > 1e-7)
        rows.append({"key": key, "fault": f["fault"], "restored": f["restored"], "last_legal": last,
                     "wait_failure": waited, "paired_B_witness": b_witness, "V_NR_effect": f["effective_NR"],
                     "B_NR_effect": g["effective_NR"] if g else None, "V_transfer_L": f["transfer_loss"],
                     "B_transfer_L": g["transfer_loss"] if g else None, "later_pump": f["later_pump"],
                     "exact_late_no_effect_without_initial": bool(waited and not f["valid_pre_fault_initial_reads"]
                               and any(w["at"] >= f["fault"] and w["outcome"] == "NO_EFFECT" for w in f["later_pump"]))})
    return {"planned": 60, "rows": rows, "assessable": sum(r["wait_failure"] is not None for r in rows),
            "wait_failure": sum(r["wait_failure"] is True for r in rows),
            "B_assessable":sum(r["paired_B_witness"] is not None for r in rows),
            "paired_B_witness":sum(r["paired_B_witness"] is True for r in rows),
            "wait_with_B_witness":sum(r["wait_failure"] is True and r["paired_B_witness"] is True for r in rows),
            "exact_late_no_effect_without_initial":sum(r.get("exact_late_no_effect_without_initial", False) for r in rows)}


def run_group(group):
    spec, reg = stage(True)
    job = os.environ["SLURM_JOB_ID"]
    cpus = int(os.environ["SLURM_CPUS_PER_TASK"])
    need(group in ("pilot","batch"), "registered group required")
    if group == "pilot":
        from panel import make_panel
        need(cpus == 5, "pilot CPU binding")
        make_panel(reg)
        deadline = time.monotonic()+270
        while not (ACT / "score-release.json").exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("pre-score publication did not arrive; no facility call")
            time.sleep(1)
        keys = KEYS[:1]
    else:
        budget = read(ACT / "batch-budget.json")
        pilot = read(ACT / "pilot/terminal.json")
        need(sha(ACT / "batch-budget.json") == os.environ["T7_BATCH_SHA"] and pilot["status"] == "COMPLETE"
             and budget["pilot_terminal_sha256"] == sha(ACT / "pilot/terminal.json") and pilot["job"] == budget["pilot_job"]
             and cpus == budget["cpus"] and budget["reserved_cpu_s"] <= budget["twice_projected_cpu_s"], "batch resource gate")
        keys = KEYS[1:]
    release = verified_release()
    ids = sorted(os.sched_getaffinity(0))[:cpus]
    need(len(ids) == cpus and 1 <= cpus <= 50, "registered CPU allocation")
    out = ACT / group
    out.mkdir()
    positions = list(product(keys, ROLES))
    save(out / "start.json", {"job": job, "positions": positions, "cpu_ids": ids, "input_publication": release["publication_commit"]})
    exits = {}
    with ThreadPoolExecutor(max_workers=cpus) as pool:
        for n in range(0,len(positions),cpus):
            wave = positions[n:n+cpus]
            futures = [pool.submit(launch, group, p, c) for p,c in zip(wave,ids)]
            exits.update(f.result() for f in futures)
            if any(exits[k+"-"+r] for k,r in wave):
                break
    entered, ends = [], {}
    for k,r in positions:
        name = k+"-"+r
        if (out/name/"entry.json").exists():
            entered.append(name)
        if (out/name/"result.json").exists():
            ends[name] = sha(out/name/"result.json")
    status = "COMPLETE" if len(ends)==len(positions) and not any(exits.values()) else "INCOMPLETE"
    publish(out/"terminal.json", {"job":job,"status":status,"positions":positions,"exit_codes":exits,"entries":entered,
            "result_sha256":ends,"not_launched":[k+"-"+r for k,r in positions if k+"-"+r not in exits]})
    scores = group_scores(group)
    publish(out/"saved.json", scores)
    if group == "batch" or status != "COMPLETE":
        if group == "batch":
            scores.update(group_scores("pilot"))
        from estimands import all_results
        manifest = read(ACT/"pre-score/input-manifest.json")
        ledger = read(ACT/"pre-score/overlap-ledger.json")
        publish(out/"analysis.json", all_results(manifest, ledger, scores))
        publish(out/"mechanisms.json", mechanism_report(scores))
    print(group,job,status,len(entered),len(ends),flush=True)
    need(status == "COMPLETE", "registered group failed; original suffix retained")


if __name__ == "__main__":
    if sys.argv[1] == "group" and len(sys.argv) == 3:
        run_group(sys.argv[2])
    elif sys.argv[1] == "unit" and len(sys.argv) == 6:
        try:
            one(sys.argv[2],sys.argv[3],sys.argv[4],int(sys.argv[5]))
        except Exception:
            traceback.print_exc()
            sys.exit(1)
    else:
        raise SystemExit("use registered group inside Slurm")
