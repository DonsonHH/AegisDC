"""Read a declared, single-load field record and compare fixed eligible strategies."""
import argparse
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path
import re

if __package__:
    from . import verify_theorem_v1 as exact
else:
    import verify_theorem_v1 as exact


SCHEMA = "aegisdc-ups-field-record-v1"
ACTIONS = ("defer", "escalate", "direct", "inspect")
RATES = ("a", "b", "q_I", "q_R", "r_E")
LOSSES = ("d_R", "d_FP", "d_E", "k")
GATES = ("direct_authorized", "direct_resource_feasible", "inspection_resource_feasible",
         "restore_after_report_authorized", "escalation_resource_feasible")
TIMES = ("decision_at", "deadline_at", "direct_completion_at", "report_available_at", "conditional_completion_at")
ROOT_FIELDS = ("schema", "record_id", "asset_id", "basis", "evidence_refs", "legal_actions",
               "fixed_over_prior", "leaf_gap_s", "parameters", "gates", "timestamps")
NUMBER_TEXT = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+|[0-9]+/[0-9]+)")
ZERO, ONE = F(0), F(1)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def object_fields(value, fields, name):
    require(isinstance(value, dict), f"{name} must be an object")
    unknown = sorted(value.keys() - set(fields))
    require(not unknown, f"Unknown fields in {name}: {', '.join(unknown)}")
    return value


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def invalid_constant(value):
    raise ValueError(f"Non-finite number: {value}")


def number(value, name, minimum=None, maximum=None):
    if value is None:
        return None
    require(type(value) in (int, Decimal, str), f"{name} must be a number, fraction string, or null")
    if isinstance(value, str):
        require(len(value) <= 64 and NUMBER_TEXT.fullmatch(value), f"{name} must use finite decimal or fraction text")
    if isinstance(value, Decimal):
        require(value.is_finite() and abs(value.as_tuple().exponent) <= 1000, f"{name} has an unsupported decimal scale")
    try:
        result = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"Invalid exact number in {name}") from exc
    require(minimum is None or result >= minimum, f"{name} must be >= {minimum}")
    require(maximum is None or result <= maximum, f"{name} must be <= {maximum}")
    return result


def flag(value, name):
    require(value is None or type(value) is bool, f"{name} must be boolean or null")
    return value


def timestamp(value, name):
    if value is None:
        return None
    require(isinstance(value, str) and re.search(r"T.*(?:Z|[+-][0-9]{2}:[0-9]{2})$", value),
            f"{name} must be a timestamp with an explicit offset")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp in {name}") from exc
    require(result.utcoffset() is not None, f"{name} must specify an offset")
    return result


def parse_record(raw):
    record = object_fields(json.loads(raw, parse_float=Decimal, parse_constant=invalid_constant,
                                      object_pairs_hook=unique_object), ROOT_FIELDS, "record")
    require(record.get("schema") == SCHEMA, f"schema must be {SCHEMA}")
    for key in ("record_id", "asset_id"):
        value = record.get(key)
        require(value is None or isinstance(value, str) and value.strip(), f"{key} must be nonempty text or null")
    require(record.get("basis") in (None, "DECLARED_FIXTURE", "FIELD_RECORD"), "Unknown basis")
    refs = record.get("evidence_refs", [])
    require(isinstance(refs, list) and all(isinstance(x, str) and x.strip() for x in refs), "Invalid evidence_refs")
    actions = record.get("legal_actions")
    if actions is not None:
        require(isinstance(actions, list) and all(x in ACTIONS for x in actions), "Unknown legal action")
        require(len(set(actions)) == len(actions), "Duplicate legal action")
    params = object_fields(record.get("parameters", {}), RATES + LOSSES, "parameters")
    gates = object_fields(record.get("gates", {}), GATES, "gates")
    times = object_fields(record.get("timestamps", {}), TIMES, "timestamps")
    parsed_times = {k: timestamp(times.get(k), "timestamps." + k) for k in TIMES}
    start, end = parsed_times["decision_at"], parsed_times["deadline_at"]
    require(start is None or end is None or start < end, "decision_at must be before deadline_at")
    for name in TIMES[2:]:
        actual = parsed_times[name]
        require(start is None or actual is None or start <= actual, f"{name} precedes decision_at")
    report, finish = parsed_times["report_available_at"], parsed_times["conditional_completion_at"]
    require(report is None or finish is None or report <= finish, "Conditional completion precedes the available report")
    return {**record, "fixed_over_prior": flag(record.get("fixed_over_prior"), "fixed_over_prior"),
            "leaf_gap_s": number(record.get("leaf_gap_s"), "leaf_gap_s"), "evidence_refs": refs,
            "parameters": {k: number(params.get(k), "parameters." + k, ZERO, ONE if k in RATES else None)
                           for k in RATES + LOSSES},
            "gates": {k: flag(gates.get(k), "gates." + k) for k in GATES}, "timestamps": parsed_times}


def decision(conditions):
    failures = [reason for value, reason, _ in conditions if value is False]
    missing = sorted({p for value, _, paths in conditions if value is None for p in paths})
    if failures:
        return {"status": "INELIGIBLE", "reasons": failures, "missing_inputs": []}
    return {"status": "UNKNOWN" if missing else "ELIGIBLE", "reasons": [], "missing_inputs": missing}


def eligibility(record):
    actions, gates, times = record.get("legal_actions"), record["gates"], record["timestamps"]

    def legal(name):
        return (None if actions is None else name in actions, "ACTION_NOT_DECLARED_LEGAL", ["legal_actions"])

    def gate(name, reason):
        return gates[name], reason, ["gates." + name]

    def before(name):
        names = (name, "deadline_at")
        missing = ["timestamps." + k for k in names if times[k] is None]
        return (None if missing else times[name] < times["deadline_at"], "DEADLINE_NOT_MET", missing)

    offered = {
        "defer": decision([legal("defer")]),
        "escalate": decision([legal("escalate"), gate("escalation_resource_feasible", "RESOURCE_LIMIT")]),
        "direct": decision([legal("direct"), gate("direct_authorized", "DIRECT_AUTHORIZATION_ABSENT"),
                            gate("direct_resource_feasible", "RESOURCE_LIMIT"), before("direct_completion_at")]),
        "inspect": decision([legal("inspect"), gate("inspection_resource_feasible", "RESOURCE_LIMIT")]),
    }
    restore = decision([gate("restore_after_report_authorized", "POST_REPORT_AUTHORIZATION_ABSENT"),
                        before("report_available_at"), before("conditional_completion_at")])
    return offered, restore


@dataclass(frozen=True)
class Quantity:
    value: F | None
    missing: tuple[str, ...] = ()


def multiply(*quantities):
    if any(x.value == ZERO for x in quantities):
        return Quantity(ZERO)
    missing = tuple(sorted({p for x in quantities for p in x.missing}))
    if missing:
        return Quantity(None, missing)
    value = ONE
    for x in quantities:
        value *= x.value
    return Quantity(value)


def difference(left, right, cost):
    missing = tuple(sorted(set(left.missing + right.missing + cost.missing)))
    return Quantity(None, missing) if missing else Quantity(left.value - right.value - cost.value)


def effects(params, restore, action):
    def param(name):
        value = params[name]
        return Quantity(value, ("parameters." + name,) if value is None else ())

    g = {"ELIGIBLE": ONE, "INELIGIBLE": ZERO, "UNKNOWN": None}[restore["status"]]
    gate = Quantity(g, tuple(restore["missing_inputs"]))
    r_i = multiply(gate, param("a"), param("q_I"))
    d_i = multiply(gate, param("b"), param("d_FP"))
    r_a, d_a = {"defer": (Quantity(ZERO), Quantity(ZERO)),
                "escalate": (param("r_E"), param("d_E")),
                "direct": (param("q_R"), param("d_R"))}[action]
    return (difference(d_a, d_i, param("k")), difference(r_i, r_a, param("k"))), r_i


def one_missing_boundary(params, restore, action, missing):
    if len(missing) != 1 or not missing[0].startswith("parameters."):
        return None
    name = missing[0].split(".", 1)[1]
    domain_hi = ONE if name in RATES else None
    ends0, _ = effects({**params, name: ZERO}, restore, action)
    ends1, _ = effects({**params, name: ONE}, restore, action)
    if any(x.value is None for x in ends0 + ends1):
        return None
    # Each endpoint is affine in one parameter with all other inputs fixed.
    # No strict win exists exactly where both endpoint margins are nonpositive.
    lo, hi = ZERO, domain_hi
    empty = False
    for x, y in zip(ends0, ends1):
        slope = y.value - x.value
        if slope > 0:
            root = -x.value / slope
            hi = root if hi is None else min(hi, root)
        elif slope < 0:
            lo = max(lo, -x.value / slope)
        elif x.value > 0:
            empty = True
    empty = empty or (hi is not None and lo > hi)
    whole = not empty and lo == ZERO and hi == domain_hi
    def bounds(low, high):
        return f"[{low},{high}]" if high is not None else f"[{low},infinity)"
    return {"parameter": missing[0], "admissible_parameter_range": bounds(ZERO, domain_hi),
            "no_strict_win_parameter_range": None if empty else bounds(lo, hi),
            "could_flip_nonempty_strict_win": not empty and not whole,
            "scope": "Existence of a strict win somewhere in [0,1], not a recommendation at an observed prior"}


def pending(status, missing=()):
    return {"status": status, "strict_win_interval": None, "has_strict_win": None,
            "missing_inputs": sorted(set(missing))}


def compare(record, digest):
    offered, restore = eligibility(record)
    params = record["parameters"]
    fixed, gap = record["fixed_over_prior"], record["leaf_gap_s"]
    positive_gap = None if gap is None else gap > 0
    core = [k for k in ("asset_id", "basis", "fixed_over_prior", "leaf_gap_s") if record.get(k) is None]
    core += ["timestamps." + k for k in ("decision_at", "deadline_at") if record["timestamps"][k] is None]
    if record.get("basis") == "FIELD_RECORD" and not record["evidence_refs"]:
        core.append("evidence_refs")
    outside = fixed is False or positive_gap is False
    inspect = offered["inspect"]
    comparisons = {}
    for action in ACTIONS[:-1]:
        other = offered[action]
        if outside:
            comparisons[action] = pending("OUTSIDE_MODEL")
        elif "INELIGIBLE" in (inspect["status"], other["status"]):
            comparisons[action] = pending("NOT_COMPARABLE")
        elif core or "UNKNOWN" in (inspect["status"], other["status"]):
            comparisons[action] = pending("INSUFFICIENT_INPUT", core + inspect["missing_inputs"] + other["missing_inputs"])
        else:
            (alpha, beta), _ = effects(params, restore, action)
            missing = sorted(set(alpha.missing + beta.missing))
            if missing:
                comparisons[action] = {**pending("INSUFFICIENT_INPUT", missing),
                    "alpha": alpha.value, "beta": beta.value,
                    "missing_effects": {"alpha": list(alpha.missing), "beta": list(beta.missing)},
                    "single_missing_boundary": one_missing_boundary(params, restore, action, missing)}
            else:
                win = exact.strict_win(alpha.value, beta.value)
                root = alpha.value / (alpha.value - beta.value) if alpha.value != beta.value else None
                tie = exact.UNIT if alpha.value == beta.value == ZERO else (
                    exact.Interval(root, root) if root is not None and exact.UNIT.contains(root) else None)
                comparisons[action] = {"status": "COMPARABLE", "alpha": alpha.value, "beta": beta.value,
                    "strict_win_interval": str(win) if win else None, "has_strict_win": win is not None,
                    "tie_region": str(tie) if tie else None, "missing_inputs": []}
    legal = [name for name in ACTIONS[:-1] if offered[name]["status"] == "ELIGIBLE"]
    missing = sorted({p for r in comparisons.values() for p in r["missing_inputs"]} | set(core))
    if outside:
        best = pending("OUTSIDE_MODEL")
    elif inspect["status"] == "INELIGIBLE":
        best = pending("NOT_COMPARABLE")
    elif missing:
        best = pending("INSUFFICIENT_INPUT", missing)
    elif not legal:
        best = pending("NOT_COMPARABLE")
    else:
        win = exact.UNIT
        for action in legal:
            interval = comparisons[action]["strict_win_interval"]
            win = win.intersect(exact.Interval.parse(interval)) if win and interval else None
        best = {"status": "COMPARABLE", "eligible_actions": legal, "strict_win_interval": str(win) if win else None,
                "has_strict_win": win is not None, "missing_inputs": []}

    direct = comparisons["direct"]
    _, r_i = effects(params, restore, "direct")
    premises = {
        "both_eligible": False if "INELIGIBLE" in (inspect["status"], offered["direct"]["status"])
                         else True if inspect["status"] == offered["direct"]["status"] == "ELIGIBLE" else None,
        "fixed_over_prior": fixed, "positive_leaf_gap": positive_gap,
        "direct_disturbance_zero": None if params["d_R"] is None else params["d_R"] == ZERO,
        "q_R_at_least_r_I": None if r_i.value is None or params["q_R"] is None else params["q_R"] >= r_i.value,
        "charge_nonnegative": None if params["k"] is None else True,
    }
    dominance = direct["status"] if direct["status"] in ("NOT_COMPARABLE", "OUTSIDE_MODEL") else (
        "SATISFIED" if not core and all(premises.values()) else
        "NOT_SATISFIED" if any(x is False for x in premises.values()) else "INSUFFICIENT_INPUT")
    return {"schema": "aegisdc-ups-field-comparison-v1", "status": best["status"], "record_sha256": digest,
            "record_id": record.get("record_id"), "asset_id": record.get("asset_id"), "basis": record.get("basis"),
            "scope": "Declared auxiliary-loss comparison, not authorization or a site instruction",
            "eligibility": offered, "conditional_restore": restore, "comparisons": comparisons,
            "best_no_inspection": best, "missing_inputs": missing,
            "direct_dominance": {"status": dominance, "premises": premises,
                "conclusion": "NO_STRICT_WIN_VS_DIRECT_FOR_AUXILIARY_LOSS" if dominance == "SATISFIED" else None}}


def main(argv):
    parser = argparse.ArgumentParser(prog="verify_theorem.py field", description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        raw = args.input.read_bytes()
        result = compare(parse_record(raw), sha256(raw).hexdigest())
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Invalid field record: {exc}\n")
    print(json.dumps(result, indent=2, default=str, ensure_ascii=True))
