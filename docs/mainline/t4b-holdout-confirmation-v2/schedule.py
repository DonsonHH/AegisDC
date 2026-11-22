"""Submit the frozen panel to Slurm and account for every reservation."""
from collections import Counter
import fcntl
import math
import os
import shlex
import subprocess
import sys

from context_t4b import ACT, PK, PROTOCOL, SOURCES, check_sources, groups, read, read_inputs, require, sha, write

FIELDS = ("JobID", "JobName%40", "State", "ExitCode", "ElapsedRaw", "AllocCPUS", "TimelimitRaw",
          "TotalCPU", "Start", "End", "NodeList")
ACTIVE = {"PENDING", "RUNNING", "CONFIGURING", "COMPLETING", "SUSPENDED", "RESIZING", "REQUEUED", "REQUEUE_HOLD"}
RETRYABLE = {"NODE_FAIL", "BOOT_FAIL", "PREEMPTED", "REVOKED", "TIMEOUT"}


def ledger():
    return sorted((read(p) for p in (ACT/"registrations").glob("*.json")), key=lambda r: int(r["job"]))


def slurm_rows(records):
    if not records:
        return {}
    ids = ",".join(r["job"] for r in records)
    out = subprocess.check_output(
        ["sacct", "-X", "-n", "-P", "-j", ids, "-o", ",".join(FIELDS)], text=True,
    )
    return {values[0]: dict(zip(FIELDS, values, strict=True)) for line in out.splitlines()
            if (values := line.split("|"))[0] in ids.split(",")}


def state(row):
    return (row["State"].split() or ["UNKNOWN"])[0].rstrip("+")


def terminal(row):
    return row is not None and state(row) not in ACTIVE | {"UNKNOWN"} and row["End"] not in ("", "Unknown", "None")


def spent(records):
    return sum(r["seconds"] for r in records)


def digest_option():
    return os.environ.get("T4B_CONDITION_SHA")


def batch_path(record):
    return ACT/"jobs"/record["group"]/record["attempt"]


def budget():
    _, plan = check_sources()
    inputs = read_inputs(plan)
    records = ledger()
    rows = slurm_rows(records)
    pilots = []
    for group in list(groups(plan))[:6]:
        attempts = [q for q in records if q["group"] == group]
        require(attempts and all(terminal(rows.get(r["job"])) for r in attempts), "pilot not terminal")
        last = attempts[-1]
        path = batch_path(last)/"terminal.json"
        complete = False
        wall = None
        if path.is_file() and state(rows[last["job"]]) == "COMPLETED":
            proof = read(path)
            require(proof["job"] == last["job"] and len(proof["positions"]) == 10, "complete pilot registration")
            complete = proof["all_positions_entered"]
            wall = proof["complete_wall_s"]
        pilots.append(dict(group=group, job=last["job"], complete=complete, wall_s=wall))
    measured = max(r["wall_s"] for r in pilots) if all(r["complete"] for r in pilots) else None
    minutes = None if measured is None else math.ceil((2*(1.2*measured+8)+6)/60)
    present = {r["group"] for r in records}
    require(not any(g.startswith("main-") for g in present), "budget is sealed before the suffix")
    future = 69
    report_jobs = plan["slurm"]["overhead_jobs"][2]
    used = spent(records)
    projected = None if minutes is None else used+future*10*minutes*60+report_jobs["cpus"]*report_jobs["wall_minutes"]*60
    count = len(records)+future+1
    limit = plan["slurm"]["projection"]
    go = minutes is not None and projected <= limit["max_reserved_cpu_s"] and count <= limit["max_jobs"]
    output = dict(schema="T4b-actual-pilot-budget", conditions=digest_option(), author_job=inputs["author_job"], pilots=pilots,
                  complete_wall_s=measured, main_minutes=minutes, prior_reservations=used, projected_jobs=count,
                  projected_reserved_cpu_s=projected, continue_=go)
    output["continue"] = output.pop("continue_")
    write(ACT/"pilot-budget.json", output)
    print(output, flush=True)


def resources(group, plan, records, accounted):
    spec = plan["slurm"]
    roster = groups(plan)
    overhead = {"author": 0, "isolation": 1, "analysis": 2}
    if group in overhead:
        envelope = spec["overhead_jobs"][overhead[group]]
        script = {"author": "author.py", "isolation": "public_guard.py", "analysis": "readback.py"}[group]
        if group == "author":
            require(not records, "one-time authoring allocation")
        if group == "analysis":
            require(all(terminal(accounted.get(r["job"])) for r in records), "retrieve after all submitted study jobs are terminal")
        return envelope["cpus"], envelope["wall_minutes"], ("5G" if group == "analysis" else "2G"), script
    require(group in roster, "registered allocation")
    if group.startswith("pilot-"):
        reg = spec["pilot"]
        return reg["cpus_per_job"], reg["wall_minutes_per_job"], "16G", "run.py"
    gate = read(ACT/"pilot-budget.json")
    require(gate["continue"] and gate["conditions"] == digest_option(), "budget gate is closed")
    reg = spec["remainder"]
    return reg["cpus_per_job"], gate["main_minutes"], "16G", "run.py"


def allocation(job):
    info = subprocess.check_output(["scontrol", "show", "job", "-o", job], text=True)
    fields = dict(item.split("=", 1) for item in info.split() if "=" in item)
    day, sep, value = fields["TimeLimit"].partition("-")
    clock = value if sep else day
    hour, minute, second = map(int, clock.split(":"))
    require(second == 0, "whole-minute Slurm allocation")
    total_minutes = (int(day)*1440 if sep else 0) + hour*60 + minute
    return int(fields["NumCPUs"]), total_minutes


def submit_one(group, retry, plan, path):
    records = ledger()
    rows = slurm_rows(records) if retry or group == "analysis" else {}
    prior = [r for r in records if r["group"] == group]
    require(retry == bool(prior), "unsettled or duplicate job")
    if prior:
        require(group in groups(plan) and all(terminal(rows.get(r["job"])) for r in prior), "only a terminal scientific allocation may be reconsidered")
        last = prior[-1]
        row = rows[last["job"]]
        folder = batch_path(last)
        require(state(row) in RETRYABLE and not any(folder.glob("positions/*/*/native-entry.json"))
                and not any(folder.glob("positions/*/*/score.json")) and not any(folder.glob("positions/*/*/original.jsonl.gz"))
                and not (folder/"terminal.json").exists() and last["conditions"] == digest_option(), "retry requires a pre-facility Slurm failure and the same input")
    if group != "author":
        read_inputs(plan)
    if group in groups(plan):
        require((ACT/"isolation/result.json").is_file(), "public witness complete")
    attempt = f"a{len(prior)+1}"
    cpus, minutes, mem, script = resources(group, plan, records, rows)
    seconds = cpus*minutes*60
    limits = plan["slurm"]["projection"]
    readback = plan["slurm"]["overhead_jobs"][2]
    terminal_reservation = 0 if group == "analysis" else readback["cpus"]*readback["wall_minutes"]*60
    require(len(records)+1+bool(terminal_reservation) <= limits["max_jobs"]
            and spent(records)+seconds+terminal_reservation <= limits["max_reserved_cpu_s"], "Slurm allocation budget")
    if retry and group.startswith("main-"):
        pending = len([g for g in groups(plan) if not any(x["group"] == g for x in records)])
        require(len(records)+pending+2 <= limits["max_jobs"] and spent(records)+(1+pending)*seconds+terminal_reservation
                <= limits["max_reserved_cpu_s"], "retry plus original remaining suffix exceeds budget")
    record = dict(group=group, attempt=attempt, cpus=cpus, minutes=minutes, seconds=seconds, mem=mem,
                  conditions=digest_option(), source=sha(SOURCES), registration=os.environ["T4B_REG_REV"],
                  condition_publication=os.environ.get("T4B_CONDITION_REV"), retry_of=prior[-1]["job"] if prior else None)
    if group in groups(plan):
        record["keys"] = groups(plan)[group]
    launched = [sys.executable, "-B", str(PK/script)]
    if script == "run.py":
        launched.extend([group, attempt])
    env = {k: os.environ[k] for k in ("T4B_SOURCE_SHA", "T4B_REG_REV", "T4B_CONDITION_SHA", "T4B_CONDITION_REV") if k in os.environ}
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    wrap = "umask 077 && exec " + shlex.join(["env", *(k+"="+v for k,v in env.items()), *launched])
    cmd = ["sbatch", "--hold", "--no-requeue", "--parsable", "--partition=cu", "--nodes=1", "--ntasks=1",
           "--cpus-per-task="+str(cpus), "--time="+str(minutes), "--mem="+mem, "--job-name=T4b-"+group+"-"+attempt,
           "--output="+str(ACT/"logs/%j.out"), "--error="+str(ACT/"logs/%j.err"), "--wrap="+wrap]
    pending_path = path/(group+"-"+attempt+".intent")
    write(pending_path, dict(record, command=cmd))
    job = subprocess.check_output(cmd, text=True).strip().split(";")[0]
    record["job"] = job
    write(path/(group+"-"+attempt+".json"), record)
    pending_path.unlink()
    require(allocation(job) == (cpus, minutes), "held job allocation differs from registration")
    subprocess.run(["scontrol", "release", job], check=True)
    print(group, attempt, job, cpus, minutes, flush=True)


def main():
    mode = sys.argv[1]
    if mode == "status":
        records = ledger()
        rows = slurm_rows(records)
        states = Counter(rows.get(r["job"], {}).get("State", "NO_ACCOUNTING_RETURN_YET") for r in records)
        print(len(records), "jobs,", spent(records), "reserved CPU seconds", dict(states))
        for r in records:
            row = rows.get(r["job"], {})
            if mode == "status" and (len(sys.argv) > 2 or not terminal(row or None) or state(row) != "COMPLETED"):
                print(r["group"], r["attempt"], r["job"], row.get("State"), row.get("ElapsedRaw"), row.get("ExitCode"))
    elif mode == "budget":
        budget()
    else:
        _, plan = check_sources()
        path = ACT/"registrations"
        path.mkdir(exist_ok=True)
        with (path/".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            require(not any(path.glob("*.intent")), "resolve prior Slurm submission outcome before submitting again")
            for group in sys.argv[2:]:
                submit_one(group, mode == "retry", plan, path)


if __name__ == "__main__":
    main()
