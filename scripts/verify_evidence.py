"""Recompute the curated historical evidence without fitting or running a patrol.

The retained source bytes are checked before reading their contents.  Model
predictions use the saved coefficients; all labels remain offline evaluation
data.  PASS means the retained evidence is intact and its arithmetic agrees,
not that a learning policy or RSI has demonstrated a gain.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import csv
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import sys


SOURCE_COMMIT = "f2c20b3a642ff1df9426e523614d3da9a5cf1129"
DATASET_SHA = "8d38eee50e64e526bfb23e5427a1f37e6c6bd5412f057347eb5c3217dfabb98a"
HEADS = ("missed", "wait_s", "travel_m", "completed")
GROUPS = (41000, 41001, 42000, 42001)
EPS = 1e-9


class EvidenceError(ValueError):
    """The retained evidence failed an explicit identity or arithmetic check."""


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def close(actual, expected, label, tolerance=1e-8):
    require(math.isfinite(actual) and math.isclose(
        actual, expected, rel_tol=tolerance, abs_tol=tolerance),
        f"{label}: got {actual!r}, expected {expected!r}")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def group_weights(rows):
    """Equal weight per underlying seed, root, then retained action/pair."""
    roots = defaultdict(set)
    counts = Counter()
    for row in rows:
        roots[row["group_id"]].add(row["root_id"])
        counts[row["group_id"], row["root_id"]] += 1
    return [1 / len(roots) / len(roots[r["group_id"]]) /
            counts[r["group_id"], r["root_id"]] for r in rows]


def objective(values):
    return [values[0], *([] if values[1] is None else [values[1]]),
            values[2], -values[3]]


def dominates(left, right):
    return (all(a <= b + EPS for a, b in zip(left, right)) and
            any(a < b - EPS for a, b in zip(left, right)))


def saved_prediction(model, features):
    require(len(features) == len(model["scale"]) == 36, "Prediction shape")
    return [math.fsum(value / scale * coefficient for value, scale, coefficient
                     in zip(features, model["scale"], head["coefficient"]))
            for head in model["heads"]]


def verify_manifest(root):
    manifest = read_json(root / "evidence/provenance.json")
    require(manifest["source_commit"] == SOURCE_COMMIT, "Source snapshot changed")
    entries = manifest["files"]
    require(len(entries) == manifest["original_file_count"] == 20,
            "Expected 20 retained original files")
    seen = set()
    for item in entries:
        relative = Path(item["path"])
        require(not relative.is_absolute() and ".." not in relative.parts and
                relative.parts[0] == "evidence", "Unsafe evidence path")
        require(item["path"] not in seen, "Duplicate provenance entry")
        seen.add(item["path"])
        path = root / relative
        require(path.resolve().is_relative_to((root / "evidence").resolve()),
                "Evidence path escapes the package")
        require(path.is_file(), f"Missing original: {relative}")
        raw = path.read_bytes()
        require(len(raw) == item["bytes"], f"Size mismatch: {relative}")
        require(hashlib.sha256(raw).hexdigest() == item["sha256"],
                f"SHA-256 mismatch: {relative}")
        require(item["source_commit"] == SOURCE_COMMIT, "Mixed source snapshots")
    require(sum(item["bytes"] for item in entries) ==
            manifest["original_bytes"] == 3181579, "Retained byte count")
    return manifest


def error_metrics(rows, predictions):
    result = {}
    for column, head in enumerate(HEADS):
        valid = [(r, p) for r, p in zip(rows, predictions) if r["y"][column] is not None]
        weights = group_weights([r for r, _ in valid])
        errors = [p[column] - r["y"][column] for r, p in valid]
        result[head] = {"n": len(valid),
                        "mae": math.fsum(w * abs(e) for w, e in zip(weights, errors)),
                        "rmse": math.sqrt(math.fsum(w * e * e for w, e in zip(weights, errors)))}
    return result


def verify_action_value(root):
    folder = root / "evidence/action_value"
    dataset = read_json(folder / "dataset.json")
    seal = read_json(folder / "dataset-seal.json")
    contract = read_json(folder / "contract.json")
    protocol = read_json(folder / "protocol.json")
    require(hashlib.sha256((folder / "dataset.json").read_bytes()).hexdigest() ==
            seal["dataset_sha256"] == DATASET_SHA, "Dataset seal identity")
    rows = dataset["samples"]
    require(len(rows) == seal["sample_count"] == 144, "Sample count")
    require(dataset["feature_names"] == contract["feature_names"] and
            len(contract["feature_names"]) == 36, "Feature contract")
    require(tuple(dataset["heads"]) == HEADS, "Output head contract")
    require(sorted({r["group_id"] for r in rows}) == list(GROUPS), "Underlying seed groups")
    require(len({r["sample_id"] for r in rows}) == 144, "Duplicate sample identity")
    require(len({r["case_id"] for r in rows}) == 12 and
            len({r["process_fingerprint"] for r in rows}) == 12, "Process identities")
    declarations = {r["case_id"]: r for r in protocol["development"]}
    require(len(declarations) == 12, "Twelve declared development conditions")
    for row in rows:
        declaration = declarations[row["case_id"]]
        require(row["group_id"] == declaration["group_id"] and
                row["process_fingerprint"] == declaration["expected_fingerprint"] and
                declaration["partition"] == "development", "Declared development identity")
    require({v["kind"] for r in rows for v in r["root_public_state"].values()} ==
            {"thermal"}, "Historical professional coverage changed")
    by_root = defaultdict(list)
    for row in rows:
        by_root[row["root_id"]].append(row)
        require(len(row["x"]) == 36 and all(math.isfinite(x) for x in row["x"]),
                "Finite public feature vector")
        require(row["wait_valid"] == (row["y"][1] is not None), "Healthy wait mask")
        require(row["execution_signature"] == dataset["execution_signature"], "Execution identity")
    require(len(by_root) == seal["root_count"] == 24, "Root count")
    for own in by_root.values():
        require(len(own) == 6 and len({tuple(r["order"]) for r in own}) == 6,
                "Every retained root needs six unique legal actions")
        original = [r for r in own if r["original"]]
        require(len(original) == 1, "One original order per root")
        require(all(x == 0 for x in original[0]["x"]) and
                all(y is None or y == 0 for y in original[0]["y"]), "Original zero anchor")

    tours = read_json(folder / "tours-complete.json")
    branches = read_json(folder / "branches-complete.json")
    require(len(tours["rows"]) == 12 and len(branches["groups"]) == 24,
            "Historical completion receipts")
    branch_rows = [r for group in branches["groups"] for r in group["rows"]]
    require(len(branch_rows) == 144, "Historical branch receipt count")
    require(all(len(group["rows"]) == 6 for group in branches["groups"]),
            "Six receipts per frozen root")
    require(tours["execution_signature"] == branches["execution_signature"] ==
            dataset["execution_signature"], "Tour/branch execution signatures")
    require({r["record_sha256"] for r in branch_rows} ==
            {r["record_sha256"] for r in rows}, "Dataset/branch record identities")
    require(hashlib.sha256((folder / "branches-complete.json").read_bytes()).hexdigest() ==
            dataset["branch_receipts_sha256"], "Branch receipt binding")

    attempts = [json.loads(line) for line in (folder / "fit-attempts.jsonl").read_text().splitlines() if line]
    require(len(attempts) == 4 and {a["fold"] for a in attempts} == set(range(4)), "Four historical fits")
    models = {}
    for fold, group in enumerate(GROUPS):
        model = read_json(folder / "models" / f"fold-{fold}.json")
        attempt = next(a for a in attempts if a["fold"] == fold)
        require(attempt["heldout_group"] == group and attempt["dataset_sha256"] == DATASET_SHA and
                attempt["fit_signature"] == model["fit_signature"], "Historical fit ledger binding")
        train = [r for r in rows if r["group_id"] != group]
        require(model["heldout_group"] == group and model["training_groups"] ==
                [g for g in GROUPS if g != group], "Held-out seed leaked into training")
        require(set(model["training_roots"]) == {r["root_id"] for r in train} and
                model["train_row_count"] == len(train) == 108, "Training root separation")
        require(model["dataset_sha256"] == DATASET_SHA and
                model["feature_names"] == dataset["feature_names"], "Model/data binding")
        require(model["lambda"] == 1 and model["fit_intercept"] is False and
                model["centering"] is False, "Frozen model identity")
        require([h["name"] for h in model["heads"]] == list(HEADS) and
                all(h["status"] == "ridge_fitted" and len(h["coefficient"]) == 36
                    for h in model["heads"]), "Four fitted output heads")
        require(all(math.isfinite(x) and x > 0 for x in model["scale"]), "Finite positive scales")
        weights = group_weights(train)
        for j in range(36):
            mean = math.fsum(w * r["x"][j] for w, r in zip(weights, train))
            scale = math.sqrt(math.fsum(w * (r["x"][j] - mean) ** 2 for w, r in zip(weights, train)))
            close(model["mean"][j], mean, "Train-only mean")
            close(model["scale"][j], scale if scale > 1e-12 else 1, "Train-only scale")
        models[group] = model

    predictions = [saved_prediction(models[r["group_id"]], r["x"]) for r in rows]
    table = read_csv(folder / "actions.csv")
    require(len(table) == len(rows), "CSV row count")
    table_by_id = {(r["root_id"], tuple(ast.literal_eval(r["action_order"]))): r for r in table}
    require(len(table_by_id) == 144, "CSV action uniqueness")
    maximum_difference = 0.0
    for row, prediction in zip(rows, predictions):
        saved = table_by_id[row["root_id"], tuple(row["order"])]
        require(saved["record_sha256"] == row["record_sha256"], "CSV record identity")
        for j, head in enumerate(HEADS):
            expected = float(saved["OOF_" + head])
            close(prediction[j], expected, "Saved out-of-fold prediction")
            maximum_difference = max(maximum_difference, abs(prediction[j] - expected))

    predictions_by_id = dict(zip((r["sample_id"] for r in rows), predictions))
    categories = Counter()
    pairs = []
    cost_actions = []
    for own in by_root.values():
        original = next(r for r in own if r["original"])
        alternatives = [r for r in own if not r["original"]]
        base = objective(original["y"])
        gains = [r for r in alternatives if dominates(objective(r["y"]), base)]
        if gains:
            categories["cost_improvement"] += 1
            for row in gains:
                close(row["y"][2], -1.6, "Cost-only travel saving")
                require(row["y"][0] == row["y"][3] == 0 and row["y"][1] in (None, 0),
                        "Historical gain type changed")
                require(not dominates(objective(predictions_by_id[row["sample_id"]]),
                                      objective(predictions_by_id[original["sample_id"]])),
                        "Cost-only gain was not reliably identified by ridge")
                cost_actions.append(row["sample_id"])
        elif all(dominates(base, objective(r["y"])) for r in alternatives):
            categories["all_worse"] += 1
        else:
            categories["tradeoff"] += 1
        for left, right in combinations(own, 2):
            if dominates(objective(right["y"]), objective(left["y"])):
                left, right = right, left
            elif not dominates(objective(left["y"]), objective(right["y"])):
                continue
            lp = list(predictions_by_id[left["sample_id"]])
            rp = list(predictions_by_id[right["sample_id"]])
            if left["y"][1] is None:
                lp[1] = rp[1] = None
            status = ("correct" if dominates(objective(lp), objective(rp)) else
                      "reversed" if dominates(objective(rp), objective(lp)) else "undistinguished")
            pairs.append({"group_id": left["group_id"], "root_id": left["root_id"], "status": status})
    require(dict(categories) == {"cost_improvement": 13, "tradeoff": 8, "all_worse": 3},
            "Root consequence categories")
    require(len(cost_actions) == 13, "Thirteen cost-only actions")
    counts = Counter(p["status"] for p in pairs)
    require(dict(counts) == {"correct": 109, "reversed": 9, "undistinguished": 186}, "Pairwise ranks")
    pair_weights = group_weights(pairs)
    mass = {s: math.fsum(w for p, w in zip(pairs, pair_weights) if p["status"] == s) for s in counts}
    coverage = mass["correct"] + mass["reversed"]
    rankings = {"comparable_pairs": len(pairs), "raw_counts": dict(counts),
                "ordered_coverage": coverage, "conditional_accuracy": mass["correct"] / coverage,
                "all_comparable_correct_fraction": mass["correct"]}
    errors = error_metrics(rows, predictions)
    zero_errors = error_metrics(rows, [[0] * 4 for _ in rows])
    for head in HEADS[:3]:
        require(errors[head]["mae"] > zero_errors[head]["mae"] and
                errors[head]["rmse"] > zero_errors[head]["rmse"], "Negative error conclusion changed")
    require(errors["completed"]["mae"] < zero_errors["completed"]["mae"] and
            errors["completed"]["rmse"] > zero_errors["completed"]["rmse"], "Completion-head tradeoff")
    worst = max(((r, p) for r, p in zip(rows, predictions) if r["y"][1] is not None),
                key=lambda item: abs(item[1][1] - item[0]["y"][1]))
    risk_index = dataset["feature_names"].index("advance_public_risk")
    ratio = worst[0]["x"][risk_index] / models[42001]["training_feature_max"][risk_index]
    require(worst[0]["group_id"] == 42001 and worst[0]["y"][1] == 0, "Worst extrapolation identity")
    close(worst[1][1], 913.875552, "Extreme wait prediction", 1e-6)
    close(ratio, 309.376955, "Feature extrapolation ratio", 1e-6)
    return {"samples": 144, "roots": 24, "processes": 12, "underlying_seed_groups": 4,
            "historical_rollout_receipts": 156, "historical_fits": 4, "professions": ["thermal"],
            "categories": dict(categories), "cost_actions": 13, "prediction_max_absolute_difference": maximum_difference,
            "oof_errors": errors, "zero_baseline_errors": zero_errors, "ridge_rankings": rankings,
            "worst_wait_prediction_s": worst[1][1], "worst_wait_actual_s": 0,
            "feature_extrapolation_ratio": ratio, "online_policy_evaluated": False}


def mean_metric(rows, name):
    values = [float(r[name]) for r in rows if r[name] != ""]
    return math.fsum(values) / len(values) if values else None


def verify_prior_results(root):
    local = read_csv(root / "evidence/local_reorder/results.csv")
    require(len(local) == 72 and len({r["record_sha256"] for r in local}) == 66,
            "Local reorder labels and cached records must remain distinct")
    metric_names = ("missed_segments", "consequence_weighted_censored_delay_s",
                    "travel_m", "completed_inspections")
    selected = [r for r in local if r["partition"] == "confirmation" and r["method"] == "selected_Q"]
    reference = [r for r in local if r["partition"] == "confirmation" and r["method"] == "R"]
    require(len(selected) == len(reference) == 6, "Six frozen confirmation conditions")
    changes = {k: mean_metric(selected, k) - mean_metric(reference, k) for k in metric_names}
    for k, expected in zip(metric_names, (0, 0.159603, 695.2, -18.166667)):
        close(changes[k], expected, "Local reorder confirmation delta", 1e-5)
    correction = read_csv(root / "evidence/baseline_correction/results.csv")
    require(len(correction) == 42, "Correction method rows")
    by_case = {(r["method"], r["case_id"]): r for r in correction}
    for case in sorted({r["case_id"] for r in correction}):
        for method in ("C1", "C2"):
            for key in (*metric_names, "service_s"):
                require(by_case[method, case][key] == by_case["T", case][key],
                        "Historical C1/C2 results must remain equal to Tour")
    parent = [r for r in correction if r["method"] == "H"]
    child = [r for r in correction if r["method"] == "C1"]
    correction_changes = {k: mean_metric(child, k) - mean_metric(parent, k)
                          for k in ("travel_m", "completed_inspections", "service_s")}
    for k, expected in zip(correction_changes, (-2.033333333, -0.333333333, -3.333333333)):
        close(correction_changes[k], expected, "Correction work/cost tradeoff", 1e-7)
    interventions = read_csv(root / "evidence/baseline_correction/interventions.csv")
    require(len(interventions) == 6 and all(r["H_would_change_at_frozen_Tour_state"] == "False"
                                          for r in interventions), "Intervention coverage limitation")
    return {"local_reorder_label_rows": 72, "local_reorder_unique_record_ids": 66,
            "local_reorder_confirmation_Q_minus_R": changes,
            "correction_C1_C2_metrics_equal_Tour": True, "correction_C1_minus_H": correction_changes,
            "correction_interventions_cover_H_active_decisions": False}


def verify_qwen_history(root):
    """Bind four historical raw outputs to evaluated rules and the C1->C2 parent."""
    folder = root / "evidence/qwen_history"
    responses = [read_json(folder / f"call-{i:02d}-response.json") for i in range(4)]
    generated = []
    for response in responses:
        require(response["output_tokens"] > 0 and response["seconds"] > 0,
                "Historical response metadata")
        proposal = json.loads(response["raw_response"])
        require(isinstance(proposal.pop("mechanism"), str), "Historical mechanism text")
        generated.append(proposal)
    rows = read_csv(root / "evidence/baseline_correction/results.csv")
    evaluated = {}
    policy_ids = {}
    for method in ("H", "C1", "C2"):
        own = [r for r in rows if r["method"] == method]
        require(len(own) == 6 and len({r["policy_id"] for r in own}) == 1,
                "Six actual historical candidate evaluations")
        rules = [json.loads(r["rule"]) for r in own]
        require(all(rule == rules[0] for rule in rules), "Frozen candidate rule identity")
        evaluated[method] = rules[0]
        policy_ids[method] = own[0]["policy_id"]
    require(generated[0] == generated[1] == evaluated["H"],
            "First two historical replies were duplicate parent rules")
    require(generated[2] == evaluated["C1"] and generated[3] == evaluated["C2"],
            "Raw generated rules must match actual evaluated C1/C2")
    child = read_json(folder / "C2-proposal.json")
    require(child["rule"] == evaluated["C2"] and child["raw_repaired"] is False and
            child["parent_policy_id"] == policy_ids["C1"], "Actual C1 to C2 parent binding")
    require(child["response_sha256"] == hashlib.sha256(
        (folder / "call-03-response.json").read_bytes()).hexdigest(), "C2 original response binding")
    return {"historical_raw_responses": 4, "duplicate_H_replies": 2,
            "actual_evaluated_candidates": ["C1", "C2"], "conditions_per_candidate": 6,
            "C2_parent_policy_id": child["parent_policy_id"],
            "raw_output_matches_evaluated_rule": True,
            "outcome": "C1 and C2 metrics equal Tour; independent task or recursive gain not established.",
            "scope": "Saved replies, parent identity and evaluation CSV cross-check; no new generation and no complete prompt/feedback replay."}


def verify(root: Path) -> dict:
    """Return a deterministic summary; raise on corrupt/missing/inconsistent evidence."""
    root = Path(root).resolve()
    manifest = verify_manifest(root)
    return {"schema": "curated-evidence-verification-v1", "evidence_integrity": "PASS",
            "research_gain": "NOT_ESTABLISHED", "source_commit": SOURCE_COMMIT,
            "verified_original_files": manifest["original_file_count"],
            "verified_original_bytes": manifest["original_bytes"],
            "action_value": verify_action_value(root), "prior_results": verify_prior_results(root),
            "historical_qwen": verify_qwen_history(root),
            "scope": {"new_research_rollouts": 0, "new_model_fits": 0, "new_llm_calls": 0,
                      "all_156_raw_trajectories_replayed": False,
                      "meaning": "Retained identities, saved predictions and statistics verified offline; no policy or RSI gain claim."}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Optionally write the small successful verification receipt")
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (EvidenceError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print(json.dumps({"evidence_integrity": "FAIL", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        target = args.output.resolve()
        protected = {args.root.resolve() / entry["path"] for entry in
                     read_json(args.root / "evidence/provenance.json")["files"]}
        protected.add(args.root.resolve() / "evidence/provenance.json")
        if target in protected:
            print("Refusing to overwrite retained evidence or provenance", file=sys.stderr)
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
