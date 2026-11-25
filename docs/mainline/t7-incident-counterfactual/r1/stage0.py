"""Verify or print the r1 registration materials using only public, archived inputs."""

import argparse
from copy import deepcopy
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[2]
PARENT_REV = "51ddd5784ceeaff1b26d3cec28920f6e86e08453"
PARENT_HASH = "cc1d69e07769df3783965883036b4d7f431a5ddcda0703fc356899166d04d787"
PACKAGE = ("registration.json", "power.json", "field-differences.md", "README.md", "stage0.py")
ABSENT = object()


def require(ok, label):
    if not ok:
        raise ValueError(label)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def load_parent():
    parent_path = PARENT.relative_to(ROOT).as_posix()
    data = git("show", f"{PARENT_REV}:{parent_path}/registration.json")
    require(sha(data) == PARENT_HASH, "parent registration SHA-256")
    reg = json.loads(data)
    script = PARENT / "stage0.py"
    require(sha(script.read_bytes()) == reg["companion_sha256"][script.name], "parent planning code")
    spec = importlib.util.spec_from_file_location("t7_original_stage0", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, reg


def power_grid(v0, parent, reg):
    ledger_path = (PARENT / "power.json").relative_to(ROOT).as_posix()
    original = git("show", f"{PARENT_REV}:{ledger_path}")
    require(sha(original) == parent["companion_sha256"]["power.json"], "original planning ledger")
    ledger = json.loads(original)
    scenarios = []
    for multiplier in reg["power"]["reported_effect_multipliers"]:
        scaled = deepcopy(ledger["prior_by_family"])
        for stratum in scaled.values():
            for endpoint in stratum.values():
                endpoint["mean"] = str(Fraction(endpoint["mean"]) * Fraction(str(multiplier)))
        # The frozen calculator reads the means and the original row-scale variances.
        # Its selection is based on unrounded powers, before building the display grid.
        result = v0.plan(scaled, reg)
        if multiplier == 1:
            require(result["grid"] == ledger["grid"], "unit multiplier must reproduce the entire original grid")
        scenarios.append({"effect_multiplier": multiplier, "grid": result["grid"],
                          "first_eligible_conditions_per_family": result["selected_conditions_per_family"]})
    chosen = next(s for s in scenarios if s["effect_multiplier"] == reg["power"]["effect_multiplier"])
    return {"source_revision": PARENT_REV, "source": ledger_path, "source_sha256": sha(original),
            "historical_inputs_by_family": ledger["prior_by_family"], "units": ledger["units"],
            "scenarios": scenarios, "planning_effect_multiplier": chosen["effect_multiplier"],
            "selected_conditions_per_family": chosen["first_eligible_conditions_per_family"]}


def leaves(value, path=""):
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from leaves(child, path + "/" + key)
    else:
        yield path, value


def show_value(v):
    if v is ABSENT:
        return "—"
    if isinstance(v, str):
        return v.replace("|", "\\|")
    return json.dumps(v, ensure_ascii=False, allow_nan=False)


def compare_fields(parent, reg):
    old, new = dict(leaves(parent)), dict(leaves(reg))
    power_prefix = "规划效应为各族各端点历史配对均值的 0.75 倍，历史方差取值沿用原登记。"
    planned = {
        "/panel/blocks_per_family": 5, "/panel/conditions_per_family": 60, "/panel/total_conditions": 120,
        "/panel/total_planned_positions": 600, "/panel/order": old["/panel/order"].replace("0..47", "0..59"),
        "/inference/resampling": old["/inference/resampling"].replace("四", "五"),
        "/inference/standard_error": old["/inference/standard_error"].replace("g=4", "g=5"),
        "/inference/raw_p": old["/inference/raw_p"].replace("仅有四块每族", "仅有五块每族"),
        "/power/selection": power_prefix + old["/power/selection"],
        "/power/effect_multiplier": 0.75, "/power/reported_effect_multipliers": [1, 0.75, 0.5],
    }
    for path, value in planned.items():
        require(new.get(path) == value, "sample-size field: " + path)
    groups = {"样本量及相应数字": [], "重合敏感性": [], "阶段 1 开发来源": [], "版本登记": []}
    additions = {"overlap_sensitivity": "重合敏感性", "stage1_development": "阶段 1 开发来源", "revision": "版本登记"}
    for path in sorted(old.keys() | new.keys()):
        left, right = old.get(path, ABSENT), new.get(path, ABSENT)
        if left is not ABSENT and right is not ABSENT and json.dumps(left) == json.dumps(right):
            continue
        if path in planned:
            group = "样本量及相应数字"
        else:
            group = additions.get(path.split("/")[1])
            require(group and left is ABSENT, "change outside the amendment: " + path)
        groups[group].append((path, left, right))
    require(all(groups.values()) and len(groups["样本量及相应数字"]) == len(planned), "missing amendment fields")
    lines = ["# r1 与原登记的逐字段差异", "",
             "以原登记提交 `51ddd578` 为准，按 JSON 路径比较。数组作一个有序字段。"
             "表中“—”表示原登记没有该字段。未列字段逐值相同。", ""]
    for heading, rows in groups.items():
        lines += ["## " + heading, "", "| 字段 | 原值 | r1 值 |", "|---|---|---|"]
        lines += [f"| `{path}` | {show_value(left)} | {show_value(right)} |" for path, left, right in rows]
        lines.append("")
    lines += ["三项修订以外的研究字段差异为 **0**。版本登记单列。", ""]
    return "\n".join(lines).encode(), {k: len(v) for k, v in groups.items()}


def operative_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return sha(data.encode())


def archived_cases(rev, path, expected_archive, manifest, *, t3=False, operative_map_sha256=None):
    raw = git("show", rev + ":" + path)
    require(sha(raw) == expected_archive, "archived input bytes: " + path)
    seen = []
    incident = {}
    operative_map = {}
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as lines:
        for line in lines:
            record = json.loads(line)
            key, case = (record["key"], record["value"]) if t3 else record
            # T3 preserves field order in UTF-8. T4c sorts keys and uses ASCII.
            data = json.dumps(case, sort_keys=not t3, ensure_ascii=not t3,
                              separators=(",", ":"), allow_nan=False)
            require(sha((data + "\n").encode()) == manifest["files"][key], "archived row identity: " + key)
            seen.append(key)
            if operative_map_sha256 is not None:
                operative_map[key] = operative_hash({k: case[k] for k in ("native", "attachment", "maintenance")})
            if case["evaluation"]["family"] in ("LONDON", "NETHERLANDS"):
                incident[key] = (set(case), case["evaluation"]["cell"],
                                 {r["value"] for r in case["native"]["dispatch_program"]["channel"]
                                  if r["kind"] == "order"})
    order = manifest["definitions"]["order"] if t3 else manifest["order"]
    require(seen == order and len(set(seen)) == len(manifest["files"]) == 72, "historical development roster")
    if operative_map_sha256 is not None:
        require(operative_hash(operative_map) == operative_map_sha256, "archived T4c operative identity map")
    return incident


def check_sources(v0, reg, checkout):
    plan = reg["stage1_development"]
    source = plan["t3"]
    folder = source["directory"] + "/"
    t3_pins = {folder + name: source[field] for name, field in (
        ("generator_v2.py", "generator_sha256"), (source["parameters"], "parameters_sha256"),
        ("freeze.json", "freeze_sha256"), (source["manifest"], "manifest_sha256"),
        (source["archive"], "archive_sha256"))}
    v0.verify_pins(v0.T3, t3_pins)
    v0.verify_pins("HEAD", t3_pins, checkout)
    t3_manifest = v0.pinned_json(v0.T3, folder + source["manifest"], source["manifest_sha256"])
    settings = v0.pinned_json(v0.T3, folder + source["parameters"], source["parameters_sha256"])
    require(source["revision"] == v0.T3 and source["public_development_seed"] == t3_manifest["seed"]
            == settings["development_seed"] and t3_manifest["zipped"] == source["archive_sha256"]
            and t3_manifest["freeze"] == source["freeze_sha256"], "T3 parameters and archive binding")
    t3_cases = archived_cases(v0.T3, folder + source["archive"], source["archive_sha256"], t3_manifest, t3=True)
    overlap = reg["overlap_sensitivity"]
    historical = overlap["historical_reference"]
    dev = overlap["development_reference"]
    policy = plan["policy"]
    require(historical["revision"] == dev["revision"] == policy["reference_revision"] == v0.T4B
            and historical["path"] == v0.INDEX and historical["sha256"] == v0.PUBLIC_INPUTS[v0.INDEX],
            "T4b reference identities")
    index = v0.pinned_json(v0.T4B, historical["path"], historical["sha256"])["conditions"]
    for prefix, family in (("5", "LONDON"), ("6", "NETHERLANDS")):
        required = {f"{prefix}-{i:02}" for i in range(1, 25)}
        actual = {k for k, r in index.items() if r["family"] == family}
        require(actual == required and all(len(bytes.fromhex(index[k]["operative_sha256"])) == 32 for k in actual),
                "T4b operative reference set: " + family)
    old_pins = {dev["manifest"]: dev["manifest_sha256"], dev["archive"]: dev["archive_sha256"],
                policy["freeze"]: policy["freeze_sha256"], policy["public_rules"]: policy["public_rules_sha256"]}
    v0.verify_pins(v0.T4B, old_pins)
    v0.verify_pins("HEAD", old_pins, checkout)
    dev_manifest = v0.pinned_json(v0.T4B, dev["manifest"], dev["manifest_sha256"])
    require(dev_manifest["input_archive"] == dev["archive_sha256"], "T4c development input manifest")
    dev_cases = archived_cases(v0.T4B, dev["archive"], dev["archive_sha256"], dev_manifest,
                               operative_map_sha256=dev["operative_map_sha256"])
    freeze = v0.pinned_json(v0.T4B, policy["freeze"], policy["freeze_sha256"])
    require(policy["role"] == freeze["role"] == "V_COST" and policy["bundle"] == "t4c_v3" and
            policy["bundle_sha256"] == freeze["public_bundle_sha256"], "frozen V_COST public bundle")
    roster = {f"{p}-{k:02}" for p in (5, 6) for k in range(1, 13)}
    require(set(t3_cases) == set(dev_cases) == roster and
            all(fields == {"native", "attachment", "evaluation"} and orders == {"OPEN"}
                for fields, _, orders in t3_cases.values()), "T3 original case schema")
    require(set(source["representative_input_sha256"]) == {"5-01", "6-02"}, "T3 representative roster")
    for key, digest in source["representative_input_sha256"].items():
        require(digest == t3_manifest["files"][key] and digest != dev_manifest["files"][key] and
                t3_cases[key][1] != dev_cases[key][1] and "maintenance" in dev_cases[key][0],
                "original representative vs same-named T4c case: " + key)
    print("PASS overlap references: T4b 24 + 24; all 72 T4c input hashes and the operative map match")
    print("PASS development sources: 24 original T3 incident rows; both named cases distinct from T4c; V_COST pinned")


def verify_delivery(v0, reg, parent, checkout):
    old_root = PARENT.relative_to(ROOT).as_posix()
    directory = HERE.relative_to(ROOT).as_posix()
    old_pins = {old_root + "/" + k: v for k, v in parent["companion_sha256"].items()}
    old_pins[old_root + "/registration.json"] = PARENT_HASH
    require((reg["revision"]["parent_commit"], reg["revision"]["parent_path"], reg["revision"]["parent_sha256"])
            == (PARENT_REV, old_root + "/registration.json", PARENT_HASH), "parent lineage")
    v0.verify_pins(PARENT_REV, old_pins)
    v0.verify_pins("HEAD", old_pins, checkout)
    print(f"PASS parent registration and all {len(old_pins)} original files match 51ddd578")
    seal_data = (HERE / "delivery.json").read_bytes()
    seal = json.loads(seal_data)
    require(set(seal["files_sha256"]) == set(PACKAGE), "r1 package inventory")
    for name, expected in seal["files_sha256"].items():
        require(sha((HERE / name).read_bytes()) == expected, "r1 package bytes: " + name)
    digest = seal["files_sha256"]["registration.json"]
    if checkout:
        anchor = git("log", "-1", "--format=%H", "HEAD", "--", directory + "/registration.json").decode().strip()
        require(anchor, "r1 registration is not committed")
        pins = {directory + "/" + k: v for k, v in seal["files_sha256"].items()}
        pins[directory + "/delivery.json"] = sha(seal_data)
        for rev in (anchor, "HEAD"):
            members = git("ls-tree", "-r", "--name-only", rev, "--", directory).decode().splitlines()
            require(set(members) == set(pins), "r1 commit inventory: " + rev)
            v0.verify_pins(rev, pins, True)
        message = git("show", "-s", "--format=%B", anchor).decode().splitlines()
        require("Registration-SHA256: " + digest in message and
                "Delivery-SHA256: " + sha(seal_data) in message, "commit hash trailers")
        print(f"PASS checkout bytes: {len(pins)} r1 files match the release commit and HEAD; both SHA-256 trailers match")
    print("Registration-SHA256:", digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--power", action="store_true")
    action.add_argument("--diff", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--checkout-bytes", action="store_true")
    args = parser.parse_args()
    require(not args.checkout_bytes or args.check, "--checkout-bytes requires --check")
    v0, parent = load_parent()
    reg = json.loads((HERE / "registration.json").read_bytes())
    diff, counts = compare_fields(parent, reg)
    if args.diff:
        sys.stdout.buffer.write(diff)
        return
    plan = power_grid(v0, parent, reg)
    if args.power:
        sys.stdout.buffer.write(v0.json_bytes(plan))
        return
    require(diff == (HERE / "field-differences.md").read_bytes() and
            v0.json_bytes(plan) == (HERE / "power.json").read_bytes(), "field diff or planning grid drift")
    table = []
    for rows in zip(*(s["grid"] for s in plan["scenarios"]), strict=True):
        size, df = rows[0]["conditions_per_family"], rows[0]["df"]
        bounds = " | ".join(f"{r['joint_union_lower_bound']:.6f}" for r in rows)
        table.append(f"| {size} | {df + 1} | {df} | {bounds} |")
    require("\n".join(table) in (HERE / "README.md").read_text("utf-8").replace("**", ""),
            "displayed power table vs archived arithmetic")
    print(f"PASS field comparison: {sum(counts.values())} changed or added leaves including publication metadata; "
          "no differences outside the three scientific amendments and provenance")
    n = plan["selected_conditions_per_family"]
    panel = reg["panel"]
    require(n == panel["conditions_per_family"] == 60 and n == panel["blocks_per_family"] * v0.BLOCK and
            n * 2 == panel["total_conditions"] and n * 2 * len(panel["role_order"]) == panel["total_planned_positions"],
            "selected sample and planned positions")
    print("PASS power: 3 effect multipliers x 7 eligible sizes; unit-scale grid reproduces v0; "
          f"0.75 selects {n}/family, df=4, 120 conditions, 600 planned positions")
    v0.verify_baseline(reg, args.checkout_bytes)
    check_sources(v0, reg, args.checkout_bytes)
    verify_delivery(v0, reg, parent, args.checkout_bytes)
    print("PASS registration only: archive checks and design arithmetic; no facility, jobs or H2/H3 seed access")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
