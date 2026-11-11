"""Read only the pinned Frontier projection and one archived V6 engineering run."""

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    with path.open("rb") as handle:
        sha = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": sha}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def num(value):
    result = float(value)
    require(math.isfinite(result), f"Non-finite input: {value!r}")
    return result


def summarize(data):
    return {key: {"min": min(vals), "median": median(vals), "max": max(vals)}
            for key, vals in data.items()}


def frontier(paths, spec):
    config = spec["frontier"]
    receipt = read_json(paths["frontier_receipt"])
    name = paths["frontier_csv"].name
    require(receipt["artifacts"][name] == identity(paths["frontier_csv"]),
            "Frontier projection disagrees with its receipt")
    start = datetime.fromisoformat(config["date"])
    step = timedelta(seconds=config["sample_interval_s"])
    factor = config["us_gallon_m3"] / 60
    data, heat_residuals = defaultdict(list), []
    with paths["frontier_csv"].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == config["samples"], "Frontier sample count mismatch")
    for i, row in enumerate(rows):
        require(row["slot_status"] == "OBSERVED" and
                datetime.fromisoformat(row["timestamp"]) == start + i * step,
                f"Unmatched Frontier row {i + 1}")
        power = num(row["compute_power_MW"])
        require(power > 0, f"Nonpositive Frontier compute denominator at row {i + 1}")
        supply = num(row["common_supply_C"])
        masses, deltas, heats = [], [], []
        for k in (1, 2, 3):
            q = num(row[f"loop{k}_flow_gpm"])
            require(q >= 0, f"Negative branch flow at Frontier row {i + 1}")
            mass = q * factor * config["density_kg_m3"]
            delta = num(row[f"loop{k}_return_C"]) - supply
            heat = num(row[f"loop{k}_published_heat_MW"])
            formula = (q * config["workbook_rounded_gallon_m3"] / 60 *
                       config["density_kg_m3"] * config["specific_heat_J_kg_K"] * max(delta, 0) / 1e6)
            masses.append(mass)
            deltas.append(delta)
            heats.append(heat)
            heat_residuals.append(abs(formula - heat))
            data[f"loop{k}_flow_m3_s"].append(q * factor)
            data[f"loop{k}_delta_K"].append(delta)
        total = math.fsum(masses)
        require(total > 0, f"No Frontier cooling flow at row {i + 1}")
        data["compute_MW"].append(power)
        data["flow_m3_s"].append(total / config["density_kg_m3"])
        data["mass_flow_kg_s"].append(total)
        data["flow_per_compute_kg_s_per_MW"].append(total / power)
        data["delta_K"].append(math.fsum(m * dt for m, dt in zip(masses, deltas)) / total)
        data["heat_per_compute"].append(math.fsum(heats) / power)
    return {"records": len(rows), "first": rows[0]["timestamp"], "last": rows[-1]["timestamp"],
            "stats": summarize(data),
            "heat_formula_check": {"pairs": len(heat_residuals),
                                   "max_abs_residual_MW": max(heat_residuals)}}


def nominal_v6(paths, spec):
    config = spec["v6"]
    run = read_json(paths["v6_run"])
    scenario = read_json(paths["v6_scenario"])
    require(run["facility_id"] == scenario["id"] == config["facility_id"]
            and run["status"] == "ENGINEERING_FIXTURE_COMPLETED" and run["engineering_fixture"],
            "Wrong V6 run class")
    require(run["inputs"]["duration_s"] == config["duration_s"] and
            run["inputs"]["maximum_step_s"] == config["maximum_step_s"] and
            not run["inputs"]["boundary_events"] and not run["inputs"]["work_requests"],
            "V6 is not the declared nominal run")
    source = run["code_identity"]
    require(source["git_commit"] == config["runtime_revision"] and not source["implementation_has_changes"] and
            all(source["files"][path] == sha for path, sha in config["runtime_file_sha256"].items()),
            "V6 runtime identity mismatch")
    for key in ("v6_scenario", "v6_trace"):
        path = paths[key]
        require(run["artifacts"][path.name]["sha256"] == identity(path)["sha256"],
                f"V6 manifest mismatch: {path.name}")
    params = {p["id"]: p["value"] for p in scenario["parameters"]}
    density, cp = num(params["water_density"]), num(params["water_specific_heat"])
    data, times, mass_residuals, heat_residuals = defaultdict(list), [], [], []
    with paths["v6_trace"].open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            domains = row["domains"]
            cooling, power, service = (domains[key] for key in ("facility_cooling", "power", "it_service"))
            require(power["primary_cooling_active"] and not power["reserve_cooling_connected"] and
                    service["demand"] == service["delivered"] == config["service_demand"],
                    f"V6 non-nominal archived snapshot at {row['time_s']}")
            flow = num(cooling["internal_pump"]["volume_flow_m3_s"])
            mass = num(cooling["internal_mass_flow_kg_s"])
            delta = num(cooling["hot_temperature_K"]) - num(cooling["internal_hx_outlet_K"])
            compute = num(power["actual_powers_W"]["compute"]) / 1e6
            heat = num(cooling["plate_hx_heat_W"])
            require(flow > 0 and mass > 0 and compute > 0, "Nonpositive V6 cooling or compute input")
            times.append(num(row["time_s"]))
            mass_residuals.append(abs(flow * density - mass))
            heat_residuals.append(abs(mass * cp * delta - heat))
            data["compute_MW"].append(compute)
            data["flow_m3_s"].append(flow)
            data["mass_flow_kg_s"].append(mass)
            data["flow_per_compute_kg_s_per_MW"].append(mass / compute)
            data["delta_K"].append(delta)
            data["heat_per_compute"].append(heat / (compute * 1e6))
    require(len(times) == config["snapshots"] == run["artifacts"]["private-state.jsonl"]["records"]
            and times == sorted(times) and times[0] == 0 and times[-1] == config["duration_s"],
            "V6 snapshot extent mismatch")
    return {"snapshots": len(times), "first_s": times[0], "last_s": times[-1],
            "density_kg_m3": density, "specific_heat_J_kg_K": cp, "stats": summarize(data),
            "internal_water_mass_flow_formula_max_abs_residual_kg_s": max(mass_residuals),
            "plate_hx_enthalpy_formula_max_abs_residual_W": max(heat_residuals),
            "archived_whole_run_energy_residual_J": run["summary"]["whole_run_energy_residual_J"]}


def position(value, reference):
    if value["min"] > reference["max"]:
        return "ABOVE_OBSERVED_DAY_RANGE"
    if value["max"] < reference["min"]:
        return "BELOW_OBSERVED_DAY_RANGE"
    return "INTERSECTS_OBSERVED_DAY_RANGE"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_root", type=Path, help="Root of the pinned Git input paths")
    parser.add_argument("output", type=Path, help="New result JSON path")
    args = parser.parse_args()
    protocol = Path(__file__).with_name("protocol.json")
    spec = read_json(protocol)
    paths = {key: args.input_root / row["path"] for key, row in spec["inputs"].items()}
    for key, path in paths.items():
        require(identity(path) == {f: spec["inputs"][key][f] for f in ("bytes", "sha256")},
                f"Pinned input changed: {key}")
    obs, sim = frontier(paths, spec), nominal_v6(paths, spec)
    ref, val = obs["stats"], sim["stats"]
    ratio = "flow_per_compute_kg_s_per_MW"
    comparison = {
        "flow_per_compute": {"position": position(val[ratio], ref[ratio]),
                             "v6_median_div_frontier_day_median": val[ratio]["median"] / ref[ratio]["median"],
                             "v6_median_div_frontier_day_max": val[ratio]["median"] / ref[ratio]["max"]},
        "delta": {key: position(val["delta_K"], ref[key])
                  for key in ("delta_K", "loop1_delta_K", "loop2_delta_K", "loop3_delta_K")}
    }
    result = {"status": spec["scope"], "protocol_id": spec["id"],
              "protocol": identity(protocol), "script": identity(Path(__file__)),
              "input_git_revision": spec["input_git_revision"], "inputs": spec["inputs"],
              "frontier": obs, "v6": sim, "comparison": comparison,
              "new_facility_runs": 0, "registered_research_runs": 0, "field_calibration": "PENDING"}
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"frontier_records": obs["records"], "v6_snapshots": sim["snapshots"], **comparison}))


if __name__ == "__main__":
    main()
