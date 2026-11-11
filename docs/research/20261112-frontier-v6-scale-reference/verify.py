"""Independent decimal check of the comparison and its bound inputs."""

import argparse
import csv
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"), parse_float=D)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(actual, expected, label):
    if abs(D(actual) - expected) > D("1e-10"):
        raise ValueError(f"{label}: {actual} != {expected}")


def check_range(values, stats, label):
    ordered = sorted(values)
    n = len(ordered)
    center = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2
    for key, expected in zip(("min", "median", "max"), (ordered[0], center, ordered[-1])):
        check(stats[key], expected, f"{label}.{key}")
    return ordered[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_root", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("verification", type=Path)
    args = parser.parse_args()
    protocol = Path(__file__).with_name("protocol.json")
    spec, result = load(protocol), load(args.result)
    paths = {key: args.input_root / row["path"] for key, row in spec["inputs"].items()}
    if digest(protocol) != result["protocol"]["sha256"] or digest(protocol.with_name("analyze.py")) != result["script"]["sha256"]:
        raise ValueError("Executed analysis or protocol hash differs")
    for key, path in paths.items():
        if digest(path) != result["inputs"][key]["sha256"] or path.stat().st_size != result["inputs"][key]["bytes"]:
            raise ValueError(f"Input provenance mismatch: {key}")
    with paths["frontier_csv"].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ratios, deltas = [], []
    factor = D(231) * D("0.0254") ** 3 * spec["frontier"]["density_kg_m3"] / 60
    for row in rows:
        flows = [D(row[f"loop{k}_flow_gpm"]) for k in (1, 2, 3)]
        returns = [D(row[f"loop{k}_return_C"]) for k in (1, 2, 3)]
        total = sum(flows)
        ratios.append(total * factor / D(row["compute_power_MW"]))
        deltas.append(sum(q * t for q, t in zip(flows, returns)) / total - D(row["common_supply_C"]))
    field = result["frontier"]["stats"]
    ratio = "flow_per_compute_kg_s_per_MW"
    day_max = check_range(ratios, field[ratio], "frontier.flow_per_compute")
    check_range(deltas, field["delta_K"], "frontier.weighted_delta")
    with paths["v6_trace"].open(encoding="utf-8") as handle:
        first = json.loads(next(handle), parse_float=D)["domains"]
    params = {p["id"]: p["value"] for p in load(paths["v6_scenario"])["parameters"]}
    water, load_w = first["facility_cooling"], first["power"]["actual_powers_W"]["compute"]
    initial_ratio = water["internal_pump"]["volume_flow_m3_s"] * params["water_density"] / (load_w / 10**6)
    initial_delta = water["hot_temperature_K"] - water["internal_hx_outlet_K"]
    for key, expected in ((ratio, initial_ratio), ("delta_K", initial_delta)):
        for stat in ("min", "median", "max"):
            check(result["v6"]["stats"][key][stat], expected, f"V6.{key}.{stat}")
    check(result["comparison"]["flow_per_compute"]["v6_median_div_frontier_day_max"],
          initial_ratio / day_max, "V6 / Frontier maximum")
    for point, reference, reported in (
        (initial_ratio, ratios, result["comparison"]["flow_per_compute"]["position"]),
        (initial_delta, deltas, result["comparison"]["delta"]["delta_K"]),
    ):
        expected = ("BELOW_OBSERVED_DAY_RANGE" if point < min(reference) else
                    "ABOVE_OBSERVED_DAY_RANGE" if point > max(reference) else
                    "INTERSECTS_OBSERVED_DAY_RANGE")
        if reported != expected:
            raise ValueError("Reported comparison direction does not hold")
    receipt = {"status": "PASS", "method": "Decimal using exact US gallon geometry and volume-weighted return temperature",
               "checked_frontier_rows": len(rows), "v6_reference_snapshot_s": 0,
               "absolute_comparison_tolerance": "1e-10",
               "result_sha256": digest(args.result), "verification_script_sha256": digest(Path(__file__))}
    with args.verification.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
