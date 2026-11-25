"""Run the two authorized original-input development groups inside Slurm."""

from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

from tables import ROSTER, describe


HERE = Path(__file__).resolve().parent
BASE = Path("/share/home/renly/renly-patrol-rsi/mainline")
ACT = BASE / "T7-incident-counterfactual-stage1-v1"
SOURCE = BASE / "T4b-holdout-confirmation-v2/source"
OLD = SOURCE / "docs/mainline"
T3 = OLD / "t3-prior-information-v2"
CORE = BASE / "V6-cold-launch-release-v1/source"
PREVIOUS = BASE / "T3-prior-information-v2-20261121"
BUNDLE = BASE / "T4c-action-cost-development-v3/public-only"
ROLE = "V_COST"


def need(ok, why):
    if not ok:
        raise ValueError(why)


def read(path):
    return json.loads(path.read_bytes())


def packed(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(v):
    return hashlib.sha256(packed(v)).hexdigest()


def sha(path):
    with path.open("rb") as fp:
        return hashlib.file_digest(fp, "sha256").hexdigest()


def write(path, v):
    with path.open("xb") as dst:
        dst.write(packed(v) + b"\n")
        dst.flush()
        os.fsync(dst.fileno())


def bindings(full):
    need(HERE == ACT / "source" and os.environ.get("SLURM_JOB_ID"), "registered Slurm location")
    spec = read(HERE / "execution.json")
    need(sha(HERE / "execution.json") == os.environ["T7_EXEC_SHA"] and len(os.environ["T7_EXEC_REV"]) == 40,
         "published execution identity")
    for name, pin in spec["stage_files"].items():
        need(sha(HERE / name) == pin, "new execution file: " + name)
    checks = read(HERE / "compatibility.json")
    need(checks["status"] == "PASS" and [r["key"] for r in checks["handshakes"]] == ROSTER, "compatibility roster")
    need(sha(Path(sys.executable)) == spec["python_sha256"], "native interpreter")
    if full:
        for path, pin in spec["host_files"].items():
            need(sha(SOURCE / path) == pin, "frozen host source: " + path)
        release = read(SOURCE / spec["launch_manifest"])
        need(release["core_tree"] == spec["core_tree"] and release["core_revision"] == spec["core_revision"],
             "registered native release")
        for name, pin in release["core_files"].items():
            need(sha(CORE / name) == pin, "native source: " + name)
        members = spec["public_members"]
        need({f.relative_to(BUNDLE).as_posix() for f in BUNDLE.rglob("*") if f.is_file()} == set(members),
             "public-only directory membership")
        need(digest(members) == checks["public_bundle_sha256"] and
             all(sha(BUNDLE / name) == pin for name, pin in members.items()), "original public worker")
        need(sha(PREVIOUS / "development-inputs/manifest.json") == checks["input_manifest_sha256"] and
             sha(PREVIOUS / "development-result.json.gz") == spec["t3_results_sha256"], "sealed original roster/scores")
        for record in checks["handshakes"]:
            need(sha(PREVIOUS / "development-inputs" / (record["key"] + ".json")) == record["input_sha256"],
                 "original row bytes: " + record["key"])
    return spec, {r["key"]: r for r in checks["handshakes"]}


def decision_evidence(tick):
    view, answer = tick["view"], tick["decision"]
    why = answer["rationale"]
    return {"at": view["time"], "request": answer["request"], "public_view_sha256": digest(view),
            "reason": why["reason"], "winning_first": why["winning_first"],
            "posterior_groups": why["posterior"]["groups"], "visible_records": view["records"],
            "visible_fixed": view["fixed"], "visible_paid": view["paid"], "visible_writes": view["writes"]}


def read_receipts(score, ticks, pub):
    issues = {t["decision"]["request"]["task"]: t for t in ticks if t["decision"]["request"]}
    subjects = {s["id"]: s for s in pub["subjects"]}
    receipts = []
    for q in score["paid"]:
        req = issues[q["task"]]["decision"]["request"]
        task, kind = q["task"], subjects[q["subject"]]
        need((q["issued"], q["subject"], q["phase"]) == (req["at"], req["subject"], req["phase"])
             and q["worker"] == kind["worker"] and q["tool"] == kind["tool"]
             and q["source"] == "onsite/" + q["subject"] and q["origin"] == task + "@" + format(q["sampled"], "g"),
             "dated paid receipt identity: " + task)
        if q["phase"] == "R":
            need(q["execution"] == req["execution"] and q["parent_epoch"] == req["parent_epoch"] and
                 q["execution"] is not None, "own verification identity: " + task)
        first_seen = next((t["view"]["time"] for t in ticks if q in t["view"]["paid"]), None)
        expected = next((t["view"]["time"] for t in ticks if t["view"]["time"] >= q["arrived"]), None)
        need(first_seen == expected, "first public decision containing the receipt")
        receipts.append(dict(q, first_visible_tick=first_seen))
    return sorted(receipts, key=lambda q: (q["arrived"], q["task"])), issues


def one(group, key, cpu):
    spec, rows = bindings(False)
    job = os.environ["SLURM_JOB_ID"]
    gate = read(ACT / group / "start.json")
    need(key in gate["keys"] and gate["job"] == job and cpu in gate["cpu_ids"], "row outside active group")
    os.sched_setaffinity(0, {cpu})
    folder = ACT / group / key
    folder.mkdir()
    start = time.monotonic()
    source = PREVIOUS / "development-inputs" / (key + ".json")
    identity = sha(source)
    need(identity == rows[key]["input_sha256"], "original input at dispatch")
    case = read(source)
    pub = case["native"]["dispatch_program"]["public"]
    need(digest(pub) == rows[key]["public_sha256"] and "maintenance" not in case, "unaltered T3 public config")
    sys.path[:0] = list(map(str, (OLD / "t4c-action-cost-v3", OLD / "t4a-public-risk-v1", T3, CORE / "src", CORE / "scripts")))
    from isolation_v3 import Child
    import native
    import public_work
    from run_panel import retain
    from score_saved import score
    need(Path(native.__file__).resolve() == T3 / "native.py" and Path(public_work.__file__).resolve() == T3 / "public_work.py",
         "original T3 execution modules")
    with (folder / "ipc.jsonl").open("xb") as wire:
        class LoggedChild(Child):
            def message(self, value):
                wire.write(packed({"send": value}) + b"\n")
                wire.flush()
                answer = super().message(value)
                wire.write(packed({"return": answer}) + b"\n")
                wire.flush()
                return answer

        child = LoggedChild(ROLE, folder / "worker.stderr")
        failed = True
        try:
            child.start(pub)
            entry = {"job": job, "key": key, "input_sha256": identity, "role": ROLE, "cpu": cpu,
                     "host_pid": os.getpid(), "worker_pid": child.child.pid, "bundle_sha256": spec["public_bundle_sha256"],
                     "public_sha256": child.static, "execution_revision": os.environ["T7_EXEC_REV"],
                     "execution_sha256": os.environ["T7_EXEC_SHA"]}
            write(folder / "entry.json", entry)
            with patch.object(native, "choose", child.choose):
                run, terminal = native.native_run(case, ROLE)
            retain(folder / "original.jsonl.gz", run, terminal)
            failed = False
        finally:
            child.close(failed=failed)
            wire.write(packed({"worker_exit": child.child.returncode}) + b"\n")
    ticks = run["policy_public_decisions"]
    need(not run["t3_unpurchased_evaluator_only"] and run["code_identity"]["source_tree_sha256"] == spec["core_tree"],
         "original runtime without evaluator probes")
    actual = [[d["view"]["time"], digest(d["view"]), digest(d["decision"])] for d in ticks]
    need(child.events == actual and [a[0] for a in actual] == list(range(0, 3601, 60)), "actual IPC vs all native decisions")
    scored = score(case, run, terminal, ROLE)
    write(folder / "score.json", scored)
    issued = [d for d in ticks if d["decision"]["request"]]
    for d in issued:
        req = d["decision"]["request"]
        checked, reason = public_work.admit(pub, d["view"], public_work.entries(pub)[req["subject"]], req["phase"], req["patrol_slot"])
        need(checked == req and reason == "ALLOW", "actual T3 admission: " + req["task"])
    paid, issues = read_receipts(scored, ticks, pub)
    result = dict(entry, status="SCORED", L=scored["L"], U=scored["U"], person=scored["person"],
                  tool=scored["tool"], fee=scored["fee"], requests=scored["requests"], paid=paid, public_decisions=len(ticks))
    if key in ("5-01", "6-02"):
        target = {"5-01": "LB", "6-02": "NP"}[key]
        wanted = issued[:1] + [d for d in issued if d["decision"]["request"]["phase"] == "I"][:1]
        valid = [q for q in paid if q["fields"] is not None]
        for q in valid[:1] + [q for q in valid if q["subject"] == target and q["phase"] == "I"][:1]:
            wanted.append(issues[q["task"]])
        result["decision_evidence"] = {d["decision"]["request"]["task"]: decision_evidence(d) for d in wanted}
    result["files_sha256"] = {n: sha(folder / n) for n in ("entry.json", "ipc.jsonl", "worker.stderr", "original.jsonl.gz", "score.json")}
    result["elapsed_s"] = time.monotonic() - start
    result["row_cpu_s"] = time.process_time()
    other = resource.getrusage(resource.RUSAGE_CHILDREN)
    result["worker_cpu_s"] = other.ru_utime + other.ru_stime
    result["rss_kib_host_worker"] = [resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, other.ru_maxrss]
    write(folder / "result.json", result)


def launch(group, key, cpu):
    path = ACT / group / (key + ".log")
    with path.open("xb") as log:
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "unit", group, key, str(cpu)],
                                stdout=log, stderr=subprocess.STDOUT)
    return key, result.returncode


def group_run(group):
    spec, _ = bindings(True)
    need(group in ("pilot", "batch"), "unregistered group")
    job = os.environ["SLURM_JOB_ID"]
    cpus = int(os.environ["SLURM_CPUS_PER_TASK"])
    keys = ROSTER[:1] if group == "pilot" else ROSTER[1:]
    if group == "pilot":
        need(cpus == 1, "one pilot CPU")
    else:
        budget = read(ACT / "batch-budget.json")
        pilot = read(ACT / "pilot/terminal.json")
        need(sha(ACT / "batch-budget.json") == os.environ["T7_BATCH_SHA"] and budget["pilot_job"] == pilot["job"]
             and budget["pilot_terminal_sha256"] == sha(ACT / "pilot/terminal.json") and pilot["status"] == "COMPLETE"
             and cpus == budget["cpus"] and budget["reserved_cpu_s"] <= budget["twice_projected_cpu_s"], "pilot/batch gate")
    ids = sorted(os.sched_getaffinity(0))[:cpus]
    need(len(ids) == cpus and 1 <= cpus <= 8, "allocated CPU affinity")
    out = ACT / group
    out.mkdir()
    write(out / "start.json", {"job": job, "group": group, "keys": keys, "cpu_ids": ids,
                               "execution_revision": os.environ["T7_EXEC_REV"], "execution_sha256": os.environ["T7_EXEC_SHA"]})
    exits = {}
    with ThreadPoolExecutor(max_workers=cpus) as workers:
        for offset in range(0, len(keys), cpus):
            wave = keys[offset:offset + cpus]
            futures = [workers.submit(launch, group, key, cpu) for key, cpu in zip(wave, ids)]
            exits.update(f.result() for f in futures)
            if any(exits[k] for k in wave):
                break
    saved = {}
    for key in keys:
        path = out / key / "result.json"
        if path.exists():
            saved[key] = read(path)
    status = "COMPLETE" if set(saved) == set(keys) and not any(exits.values()) else "INCOMPLETE"
    write(out / "terminal.json", {"job": job, "status": status, "planned": keys, "exit_codes": exits,
                                  "facility_entries": [k for k in keys if (out / k / "entry.json").is_file()],
                                  "scored": list(saved), "not_launched": [k for k in keys if k not in exits],
                                  "result_sha256": {k: sha(out / k / "result.json") for k in saved}})
    if group == "batch":
        saved[ROSTER[0]] = read(ACT / "pilot" / ROSTER[0] / "result.json")
        archive = PREVIOUS / "development-result.json.gz"
        need(sha(archive) == spec["t3_results_sha256"], "comparison archive")
        with gzip.open(archive, "rb") as fp:
            baseline = json.load(fp)
        write(out / "comparison.json", describe(baseline, saved))
    write(out / "public-return.json", {"terminal": read(out / "terminal.json"), "returns": saved})
    print(job, group, status, len(saved), flush=True)
    need(status == "COMPLETE", "failed development group; no retry")


if __name__ == "__main__":
    if sys.argv[1] == "group" and len(sys.argv) == 3:
        group_run(sys.argv[2])
    elif sys.argv[1] == "unit" and len(sys.argv) == 5:
        try:
            one(sys.argv[2], sys.argv[3], int(sys.argv[4]))
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            sys.exit(1)
    else:
        raise SystemExit("use the registered Slurm group")
