"""Bound single-lane FIT position cost using the saved launch order and slot timer."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bounds(study, package):
    sys.path.insert(0, str(package / "r1"))
    from fit_evidence import authenticated, dereference

    evidence = study / "evidence"
    case = read(evidence / "case.json")
    envelope = read(study / "execution-recovery.json")
    key = case["score_key"]
    require(hashlib.sha256(bytes.fromhex(key)).hexdigest() ==
            envelope["signer_fingerprints"]["evaluator"], "evaluator identity")
    groups = defaultdict(list)
    units = defaultdict(list)
    for group in sorted((study / "positions").iterdir()):
        meter = authenticated(dereference(evidence, read(group / "closed.json")["meter"]), key)
        physical = dereference(evidence, meter["physical"])
        binding = meter["binding"]
        require(physical["binding"] == binding and binding["context"] == case["context"],
                "signed slot context")
        arm = binding["arm"]
        timers = physical["physical"]
        require(len(timers) == 48 and {row["ordinal"] for row in timers} == set(range(1, 49))
                and not physical["unlaunched"], "complete slot")
        lanes = defaultdict(list)
        for row in timers:
            unit = group / f"{row['ordinal']:02}"
            launch = read(unit / "launch.json")
            entry = read(unit / "broker-entry.json")
            finished = (unit / "physical-terminal.json").stat().st_mtime_ns
            require(row["complete"] and launch["ordinal"] == entry["ordinal"] == row["ordinal"]
                    and launch["lane"] == entry["cpu"]
                    and launch["time_ns"] <= entry["started_ns"] <= finished, "position timing and affinity")
            lanes[entry["cpu"]].append((launch["time_ns"], finished, row["supervisor_share_us"]))
        require(len(lanes) == (24 if arm == "PARENT" else 48), "allocated lanes")
        elapsed = physical["elapsed_ns"]
        first_launch = min(t[0] for lane in lanes.values() for t in lane)
        # The first launch follows the signed slot timer's start. The broker only
        # releases a CPU lane after wait4 returns and the physical terminal exists.
        last_upper = first_launch + elapsed
        for lane in lanes.values():
            lane.sort()
            for i, (start, terminal, supervisor_us) in enumerate(lane):
                next_start = lane[i + 1][0] if i + 1 < len(lane) else last_upper
                require(start <= terminal <= next_start, "position fits lane window")
                upper_ns = next_start - start + supervisor_us * 1000
                require(upper_ns <= 180_000_000_000, "position CPU bound")
                units[arm].append((terminal - start, upper_ns))
        groups[arm].append(elapsed)
    require({a: len(v) for a, v in units.items()} == {"PARENT": 48, "O": 768, "R": 768},
            "all physical positions")
    return {
        "scope": "Saved single-lane start/terminal timings, authenticated whole-slot clocks and charged supervisor shares.",
        "unit": "nanoseconds",
        "per_position_cap_ns": 180_000_000_000,
        "arms": {arm: {
            "slots": len(groups[arm]),
            "positions": len(units[arm]),
            "max_signed_slot_wall_ns": max(groups[arm]),
            "max_recorded_launch_to_terminal_ns": max(t[0] for t in units[arm]),
            "max_position_cpu_upper_bound_ns": max(t[1] for t in units[arm]),
        } for arm in ("PARENT", "O", "R")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("study", "package", "output"):
        parser.add_argument("--" + argument, required=True, type=Path)
    args = parser.parse_args()
    result = bounds(args.study, args.package)
    with args.output.open("xb") as file:
        file.write((json.dumps(result, indent=2) + "\n").encode())
    print("PASS 1,584 single-lane position bounds from retained timestamps")
