"""Produce annual context from the unchanged Frontier workbook and audited reader."""

import argparse
import bisect
import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(path):
    with path.open("rb") as handle:
        sha = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": sha}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def percentile(ordered, p):
    index = (len(ordered) - 1) * p
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (index - lo) * (ordered[hi] - ordered[lo])


def summarize(annual, day):
    a, d = sorted(annual), sorted(day)
    qa = {key: percentile(a, p) for key, p in (("p10", .1), ("p50", .5), ("p90", .9))}
    qd = {key: percentile(d, p) for key, p in (("p10", .1), ("p50", .5), ("p90", .9))}
    return {"annual": qa, "day": qd,
            "day_median_annual_rank_pct": 100 * bisect.bisect_right(a, qd["p50"]) / len(a)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_root", type=Path)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    protocol = Path(__file__).with_name("protocol.json")
    spec = load(protocol)
    workbook = identity(args.workbook)
    require(workbook == {k: spec["workbook"][k] for k in ("bytes", "sha256")}, "Workbook changed")
    paths = {k: args.input_root / rec["path"] for k, rec in spec["inputs"].items()}
    for key, path in paths.items():
        require(identity(path) == {k: spec["inputs"][key][k] for k in ("bytes", "sha256")}, f"Input changed: {key}")
    environment = {"python": sys.version.split()[0], "openpyxl": version("openpyxl"), "matplotlib": version("matplotlib")}
    require(environment == spec["reader_environment"], "Reader environment changed")
    module_spec = importlib.util.spec_from_file_location("pinned_frontier_reader", paths["pilot_reader"])
    reader = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(reader)
    pilot = load(paths["pilot_protocol"])
    rows, info = reader.read_source(args.workbook, pilot)
    window, heat, layout = pilot["window"], pilot["heat_arithmetic"], pilot["layout"]
    start, end = (datetime.fromisoformat(window[key]) for key in ("annual_start", "annual_end_exclusive"))
    step = timedelta(seconds=window["nominal_grid_seconds"])
    grid = {start + i * step for i in range((end - start) // step)}
    dates = sorted(stamp for stamp in rows if start <= stamp < end)
    buckets, _ = reader.nearby_grid(dates, start, grid, step, window["proximity_diagnostic_seconds"])
    support = {"nominal_slots": len(grid), "matched_slots": len(buckets), "no_nearby_slots": len(grid - buckets.keys())}
    require(support == spec["expected_clock_support"], "Audited time support changed")
    excluded, annual, day = Counter(), defaultdict(list), defaultdict(list)
    keys = {"compute_power_MW", "common_supply_C"}
    loops = layout["loops"]
    keys |= {loop[k] for loop in loops for k in ("flow", "return", "waste_heat")}
    factor = heat["density_kg_m3"] * heat["us_gal_m3"] / 60
    for point, matches in sorted(buckets.items()):
        if len(matches) != 1 or len(rows[matches[0]]) != 1:
            excluded["AMBIGUOUS_SLOT"] += 1
            continue
        values = rows[matches[0]][0][1]
        if any(values[key] is None for key in keys):
            excluded["MISSING_OR_INVALID_METRIC_INPUT"] += 1
            continue
        power = values["compute_power_MW"]
        if power <= 0:
            excluded["NONPOSITIVE_COMPUTE_POWER"] += 1
            continue
        flows = [values[loop["flow"]] for loop in loops]
        if min(flows) < 0:
            excluded["NEGATIVE_BRANCH_FLOW"] += 1
            continue
        flow = math.fsum(flows)
        if flow <= 0:
            excluded["NONPOSITIVE_TOTAL_FLOW"] += 1
            continue
        returns = [values[loop["return"]] for loop in loops]
        metrics = {"flow_per_compute_kg_s_per_MW": flow * factor / power,
                   "delta_K": math.fsum(f * t for f, t in zip(flows, returns)) / flow - values["common_supply_C"],
                   "heat_per_compute": math.fsum(values[loop["waste_heat"]] for loop in loops) / power}
        for key, value in metrics.items():
            annual[key].append(value)
            if point.date().isoformat() == spec["day"]:
                day[key].append(value)
    original = load(paths["a2_day_result"])["frontier"]
    n_annual, n_day = len(annual["delta_K"]), len(day["delta_K"])
    require(n_annual + sum(excluded.values()) == support["matched_slots"], "Eligibility counts do not close")
    require(n_day == original["records"] == 144, "Audited A2 day support changed")
    metrics = {key: summarize(values, day[key]) for key, values in annual.items()}
    for key, summary in metrics.items():
        require(math.isclose(summary["day"]["p50"], original["stats"][key]["median"], abs_tol=1e-10, rel_tol=0),
                f"Published day median changed: {key}")
    result = {"status": spec["scope"], "protocol": identity(protocol), "script": identity(Path(__file__)),
              "input_git_revision": spec["input_git_revision"], "inputs": spec["inputs"], "workbook": workbook,
              "environment": environment, "clock_support": support, "reader_clock_audit": info,
              "excluded_from_matched_slots": dict(excluded), "annual_records": n_annual,
              "day": spec["day"], "day_records": n_day, "a2_day_medians_reproduced": True, "metrics": metrics,
              "field_calibration": "PENDING", "new_facility_runs": 0, "registered_research_runs": 0}
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"annual_records": n_annual, "day_records": n_day, "excluded": dict(excluded), "metrics": metrics}))


if __name__ == "__main__":
    main()
