"""Reproduce T7 design arithmetic from public Git blobs. No facility or seed input."""

import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
from decimal import Decimal
from fractions import Fraction
from math import sqrt
from pathlib import Path
from statistics import mean, variance

from scipy.stats import nct, t


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
T4B = "3487276af9e9759357771d16eb45feceaa3c948a"
T3 = "85af7e48b60e61dc453456b5b7bc73ab832900b5"
OLD = "docs/mainline/t4b-holdout-confirmation-v2/"
T3_RESULTS = "docs/mainline/t3-prior-information-v2/development-result.json.gz"
RELEASE = "docs/mainline/v6-stage-three-cold-launch-v1/launch-manifest.json"
SCORES = OLD + "results.json.gz"
INDEX = OLD + "condition-summary.json"
PUBLIC_INPUTS = {
    SCORES: "cc1ad6ada702738e1e5c3662f4d041c40231a72f8d40e738ef8abccafe02c136",
    INDEX: "745b99b439bd8267817768010d04e0eec157fd235515f911c7623038990e1504",
    T3_RESULTS: "ffcaa80539129ac56c9ef754310b563de365d6a6e7bf38243e4e98307e41b766",
}
FAMILIES = ("LONDON", "NETHERLANDS")
COMPARATORS = {"HA": "P", "HB": "ALARM", "HC": "P"}
BLOCK = 12


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def git(*args, stdin=None):
    return subprocess.check_output(["git", *args], cwd=ROOT, input=stdin)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pinned_json(revision, name, expected):
    data = git("show", revision + ":" + name)
    require(sha(data) == expected, "historical SHA-256 mismatch: " + name)
    if name.endswith(".gz"):
        data = gzip.decompress(data)
    return json.loads(data, parse_float=Decimal)


def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def effects(row, hypothesis):
    comparison = COMPARATORS[hypothesis]
    scores = row["arms"]
    method = Fraction(scores["V_COST"]["L"])
    control = Fraction(scores[comparison]["L"])
    require(method >= 0 and control >= 0, "negative archived deficit: " + row["key"])
    if hypothesis == "HC":
        return Fraction(int(method > 0) - int(control > 0))
    return method - control


def paired_history(archive, index):
    history = {}
    for family in FAMILIES:
        rows = [row for row in archive["rows"] if row["family"] == family]
        keys = [row["key"] for row in rows]
        entries = [index["conditions"][key] for key in keys]
        require(len(set(keys)) == len(keys) == 24, "historical family denominator")
        require(sorted(e["draw"] for e in entries) == list(range(24)), "historical draws")
        require(all(e["family"] == family and e["block"] == e["draw"] // BLOCK for e in entries),
                "archived block assignment")
        history[family] = {}
        for hypothesis in COMPARATORS:
            differences = [effects(row, hypothesis) for row in rows]
            block_means = [mean(d for d, e in zip(differences, entries) if e["block"] == block)
                           for block in (0, 1)]
            row_variance = variance(differences)
            block_variance = variance(block_means)
            history[family][hypothesis] = {
                "n": len(rows),
                "mean": str(mean(differences)),
                "better_equal_worse": [sum(d < 0 for d in differences),
                                       sum(d == 0 for d in differences),
                                       sum(d > 0 for d in differences)],
                "block_means": [str(x) for x in block_means],
                "paired_row_variance": str(row_variance),
                "block_mean_variance": str(block_variance),
                "row_scale_planning_variance": str(max(row_variance, BLOCK * block_variance)),
            }
    return history


def plan(history, registration):
    alpha = registration["inference"]["familywise_alpha"]
    power = registration["power"]
    candidates = []
    selected = None
    for size in range(2 * BLOCK, power["max_conditions_per_family"] + 1, BLOCK):
        df = size // BLOCK - 1
        critical = t.isf(alpha / (2 * len(COMPARATORS)), df)
        probabilities = {}
        for hypothesis in COMPARATORS:
            strata = [history[family][hypothesis] for family in FAMILIES]
            delta = mean(Fraction(s["mean"]) for s in strata)
            total_variance = sum(Fraction(s["row_scale_planning_variance"]) for s in strata)
            require(total_variance > 0, "undefined planning variance: " + hypothesis)
            se = sqrt(float(total_variance / (4 * size)))
            # The registered superiority direction is negative, including in planning.
            probabilities[hypothesis] = float(nct.sf(critical, df, -float(delta) / se))
        union_bound = max(0.0, 1 - sum(1 - p for p in probabilities.values()))
        if selected is None and union_bound >= power["target_joint_planning_power"]:
            selected = size
        candidates.append({
            "conditions_per_family": size,
            "df": df,
            "directional_marginal_power": {k: round(v, 8) for k, v in probabilities.items()},
            "joint_union_lower_bound": round(union_bound, 8),
        })
    return {
        "source_revision": T4B,
        "public_planning_inputs_sha256": {p: PUBLIC_INPUTS[p] for p in (SCORES, INDEX)},
        "units": {"HA": "seconds", "HB": "seconds", "HC": "proportion"},
        "prior_by_family": history,
        "grid": candidates,
        "selected_conditions_per_family": selected,
    }


def verify_pins(revision, pins, check_files=False):
    names = sorted(pins)
    refs = "".join(revision + ":" + p + "\n" for p in names).encode()
    batch = io.BytesIO(git("cat-file", "--batch", stdin=refs))
    for path in names:
        header = batch.readline().split()
        require(len(header) == 3 and header[1] == b"blob", "missing Git blob: " + path)
        content = batch.read(int(header[2]))
        require(batch.read(1) == b"\n" and sha(content) == pins[path],
                "pinned bytes differ: " + revision + ":" + path)
        if check_files:
            require((ROOT / path).read_bytes() == content, "checkout bytes differ: " + path)
    require(not batch.read(), "unexpected trailing Git output")


def verify_baseline(r, checkout_bytes):
    base = r["baseline"]
    require(base["revision"] == T4B, "baseline revision")
    old = pinned_json(T4B, base["run_manifest"], base["run_manifest_sha256"])
    source = pinned_json(T4B, base["source_manifest"], base["source_manifest_sha256"])
    fixed = old["fixed_identities"]
    release = pinned_json(T4B, RELEASE, fixed["path_sha256"][RELEASE])
    require(release["core_revision"] == base["native_revision"] == fixed["native_core"],
            "native revision")
    for role, bundle in base["arm_bundles"].items():
        require(role in fixed["public_bundles"][bundle]["roles"], "policy bundle: " + role)
    pins = {}
    for group in (source["files"], fixed["path_sha256"], fixed["slice57_sha256"],
                  release["core_files"]):
        for path, digest in group.items():
            require(path not in pins or pins[path] == digest, "conflicting source pin: " + path)
            pins[path] = digest
    verify_pins(base["native_revision"], release["core_files"])
    verify_pins(T4B, pins)
    verify_pins("HEAD", pins, checkout_bytes)
    extras = PUBLIC_INPUTS | {base["source_manifest"]: base["source_manifest_sha256"]}
    verify_pins("HEAD", extras, checkout_bytes)
    print(f"PASS source bytes: T4b {len(source['files'])}, native {len(release['core_files'])}, "
          f"{len(pins)} distinct; frozen parameters, policies and scorer match")
    custody = pinned_json(T4B, OLD + "holdout-registration-v3.json",
                          source["files"][OLD + "holdout-registration-v3.json"])
    public_digests = {v["sha256"] for v in custody["seeds"].values()}
    public_digests.update(custody["superseded_commitments"][k]["sha256"] for k in ("H1", "H2"))
    public_digests.add(custody["legacy_commitment"]["sha256"])
    new_digest = r["custody"]["sha256"]
    require(re.fullmatch("[0-9a-f]{64}", new_digest) and new_digest not in public_digests,
            "H3 public commitment format or reuse of a registered commitment")
    require(r["custody"]["executor_has_seed_file"] is False and
            all(type(v) is int and v == 0 for v in r["at_registration"].values()), "stage boundary")
    print("PASS H3 public digest format and distinctness from five historical commitments")


def verify_references(archive, history):
    expected = {
        ("LONDON", "HA"): ("-625/2", [15, 9, 0]),
        ("LONDON", "HB"): ("-585/2", [14, 10, 0]),
        ("NETHERLANDS", "HA"): ("-850", [12, 12, 0]),
        ("NETHERLANDS", "HB"): ("-21485/24", [14, 10, 0]),
    }
    for (family, test), target in expected.items():
        prior = history[family][test]
        require((prior["mean"], prior["better_equal_worse"]) == target, "task reference: " + family + test)
    require([(h["id"], h["decision"]) for h in archive["hypotheses"]] ==
            [("H1", "MET"), ("H2", "MET"), ("H3", "MET")], "historical T4b decisions")
    require(round(archive["hypotheses"][0]["comparison"]["metrics"]["L"]["mean"], 2)
            == Decimal("-343.90"), "historical T4b H1")
    t3 = pinned_json(T3, T3_RESULTS, PUBLIC_INPUTS[T3_RESULTS])
    representatives = {r["key"]: r for r in t3["rows"] if r["key"] in ("5-01", "6-02")}
    for key, notice, latest in (("5-01", 60, 720), ("6-02", 120, 540)):
        row = representatives[key]
        require(set(row["arms"]) == {"P", "ORACLE", "PERIODIC", "ALARM"} and
                row["arms"]["PERIODIC"]["L"] == 0, "T3 observed arms: " + key)
        paid = row["info"]["paid"]
        require(row["info"]["paid_is_counterfactual_opportunity"] and (paid[3], paid[0]) == (0, 50)
                and (row["info"]["prior"][0], row["latest"]) == (notice, latest), "T3 timing: " + key)
    print("PASS task references: four archived incident contrasts, T4b decisions and two T3 cases")


def verify_checkout():
    folder = HERE.relative_to(ROOT).as_posix()
    members = git("ls-tree", "-r", "--name-only", "HEAD", "--", folder).decode().splitlines()
    require(folder + "/registration.json" in members, "registration has not been committed")
    for member in members:
        require((ROOT / member).read_bytes() == git("show", "HEAD:" + member), "package bytes: " + member)
    commit = git("log", "-1", "--format=%H", "HEAD", "--", folder + "/registration.json").decode().strip()
    message = git("show", "-s", "--format=%B", commit).decode()
    digest = sha((HERE / "registration.json").read_bytes())
    require("Registration-SHA256: " + digest in message.splitlines(), "registration SHA in commit message")
    require((HERE / "contamination.md").is_file(), "missing contamination disclosure")
    print(f"PASS fresh checkout: {len(members)} package files, all historical pins, registration hash trailer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true", help="verify the public stage-zero package")
    actions.add_argument("--power", action="store_true", help="print the historical design ledger as JSON")
    parser.add_argument("--checkout-bytes", action="store_true", help="also verify actual clean-checkout bytes")
    args = parser.parse_args()
    require(not args.checkout_bytes or args.check, "--checkout-bytes requires --check")
    reg_data = (HERE / "registration.json").read_bytes()
    r = json.loads(reg_data)
    archive = pinned_json(T4B, SCORES, PUBLIC_INPUTS[SCORES])
    index = pinned_json(T4B, INDEX, PUBLIC_INPUTS[INDEX])
    history = paired_history(archive, index)
    power = plan(history, r)
    if args.power:
        sys.stdout.buffer.write(json_bytes(power))
        return
    verify_baseline(r, args.checkout_bytes)
    verify_references(archive, history)
    panel = r["panel"]
    n = power["selected_conditions_per_family"]
    require(n is not None and n == panel["conditions_per_family"] == BLOCK * panel["blocks_per_family"],
            "sample size vs planned grid")
    require(panel["families"] == list(FAMILIES) and panel["family_weights"] == [0.5, 0.5]
            and panel["conditions_per_block"] == BLOCK and panel["frozen_family_indices_zero_based"] == [4, 5],
            "panel family/block identities")
    require(set(panel["role_order"]) == set(r["baseline"]["arm_bundles"]) and
            panel["total_planned_positions"] == len(panel["role_order"]) * panel["total_conditions"]
            and panel["total_conditions"] == len(FAMILIES) * n, "paired panel denominators")
    ep = r["endpoints"]
    require([(h["id"], h["comparator"], h["outcome"]) for h in ep["primary"]] ==
            [("HA", "P", "L"), ("HB", "ALARM", "L"), ("HC", "P", "event")], "primary estimands")
    require((ep["event"]["field"], ep["event"]["operator"], ep["event"]["threshold"]) == ("L", ">", 0)
            and r["inference"]["adjustment"] == "Holm step-down", "event or multiplicity")
    require(json_bytes(power) == (HERE / r["power"]["ledger"]).read_bytes(), "power ledger bytes")
    selected = next(x for x in power["grid"] if x["conditions_per_family"] == n)
    print(f"PASS power: 48 historical rows; {n}/family, {panel['total_conditions']} conditions, "
          f"{panel['total_planned_positions']} planned positions; joint planning bound {selected['joint_union_lower_bound']:.6f}")
    if args.checkout_bytes:
        verify_checkout()
    print("Registration-SHA256:", sha(reg_data))
    print("PASS stage 0 only; this checker reads public objects and starts no research jobs")


if __name__ == "__main__":
    main()
