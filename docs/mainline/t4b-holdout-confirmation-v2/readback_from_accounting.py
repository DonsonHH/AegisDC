"""Run the frozen analysis with terminal Slurm records captured on the login node."""
import csv
from pathlib import Path
import sys

from context_t4b import ACT, PK, check_sources, read, require, sha, slurm_id
import schedule

GROUP = "analysis-recovery"


def terminal_snapshot(records, authorization):
    path = ACT/"readback-terminal.psv"
    require(sha(path) == authorization["terminal_snapshot_sha256"], "accounting snapshot bytes")
    with path.open(encoding="utf8", newline="") as stream:
        values = {row["JobID"]:row for row in csv.DictReader(stream, delimiter="|")}
    expected = {r["job"] for r in records if r["group"] != GROUP}
    require(set(values) == expected and all(schedule.terminal(r) for r in values.values()), "same set of terminal jobs")
    failed = values[authorization["failed_job"]]
    require(failed["State"] == "FAILED" and failed["ExitCode"] == "1:0"
            and sha(ACT/"logs"/(authorization["failed_job"]+".err")) == authorization["original_error_log_sha256"],
            "retained query failure")
    return values


def submit(authorization):
    plan = check_sources()[1]
    records = schedule.ledger()
    terminal_snapshot(records, authorization)
    require(not (ACT/"results.json.gz").exists() and not (ACT/"headline.json").exists(), "unused saved-only output paths")
    require(not any(r["group"] == GROUP for r in records), "one saved-only recovery")
    resources = plan["slurm"]["overhead_jobs"][2]
    require(len(records)+1 <= plan["slurm"]["projection"]["max_jobs"] and
            schedule.spent(records)+resources["cpus"]*resources["wall_minutes"]*60 <= plan["slurm"]["projection"]["max_reserved_cpu_s"],
            "recovery counts against the original limits")
    schedule.resources = lambda group, *_: (
        resources["cpus"], resources["wall_minutes"], "5G", Path(__file__).name
    )
    sys.argv[:] = [sys.argv[0], "submit", GROUP]
    schedule.main()


def main():
    authorization = read(PK/"readback-recovery.json")
    require(sha(Path(__file__)) == authorization["wrapper_sha256"]
            and sha(PK/"readback.py") == authorization["frozen_readback_sha256"], "recovery and frozen analysis identity")
    if len(sys.argv) == 2 and sys.argv[1] == "submit":
        submit(authorization)
        return
    import readback

    records = schedule.ledger()
    require([r["job"] for r in records if r["group"] == GROUP] == [slurm_id()], "registered saved-only recovery allocation")
    snapshot = terminal_snapshot(records, authorization)
    # The frozen analyser still evaluates its own planned roles, bounds and bootstrap.
    readback.slurm_rows = lambda records: snapshot
    readback.main()


if __name__ == "__main__":
    main()
