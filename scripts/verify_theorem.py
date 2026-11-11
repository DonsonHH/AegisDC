"""Exact arithmetic for the 39r inspection boundary; no simulator imports."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = Path("docs/mainline/39r-ups-a1-stage2-breakeven-v1.json")
ORIGINAL = Path("evidence/mainline/engineering/39r-ups-a1-stage2-breakeven-v1/result.json")
DELIVERY = Path("evidence/mainline/engineering/39r-ups-a1-stage3-verification-v1/result.json")
SPEC_SHA = "965b54958da61eb3fb0360bc3f350da7c3eab8e5e31ea20e26470df98d4954ad"
ORIGINAL_SHA = "92aa8d52260703e1749dbf314a89cd4b65671547def28c9fda4376ad57370e7c"
ZERO, ONE = Fraction(0), Fraction(1)
GRID = tuple(Fraction(i, 100) for i in range(101))
GRID_SET = frozenset(GRID)
INPUTS = ("s", "t", "u0", "u1", "q_i", "q_r", "d_r", "d_fp", "k")


def require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class Interval:
    lo: Fraction
    hi: Fraction
    left: bool = True
    right: bool = True

    def __post_init__(self):
        require(ZERO <= self.lo <= self.hi <= ONE, "Interval must lie in [0,1]")
        require(self.lo < self.hi or self.left and self.right, "Empty interval")

    def contains(self, p):
        return (self.lo < p or self.left and p == self.lo) and (
            p < self.hi or self.right and p == self.hi
        )

    def intersect(self, other):
        lo, hi = max(self.lo, other.lo), min(self.hi, other.hi)
        left = self.contains(lo) and other.contains(lo)
        right = self.contains(hi) and other.contains(hi)
        if lo > hi or lo == hi and not (left and right):
            return None
        return Interval(lo, hi, left, right)

    def __str__(self):
        if self.lo == self.hi:
            return "{" + str(self.lo) + "}"
        return f"{'[' if self.left else '('}{self.lo},{self.hi}{']' if self.right else ')'}"

    @classmethod
    def parse(cls, text):
        if text.startswith("{") and text.endswith("}"):
            p = Fraction(text[1:-1])
            return cls(p, p)
        require(text[0] in "[(" and text[-1] in ")]", f"Invalid frozen interval: {text}")
        lo, hi = map(Fraction, text[1:-1].split(","))
        return cls(lo, hi, text[0] == "[", text[-1] == "]")


UNIT = Interval(ZERO, ONE)


@dataclass(frozen=True)
class Inputs:
    s: Fraction
    t: Fraction
    u0: Fraction
    u1: Fraction
    q_i: Fraction
    q_r: Fraction
    d_r: Fraction
    d_fp: Fraction
    k: Fraction
    g: int = 1

    def __post_init__(self):
        for name in INPUTS[:6]:
            require(ZERO <= getattr(self, name) <= ONE, f"{name} must be in [0,1]")
        for name in INPUTS[6:]:
            require(getattr(self, name) >= ZERO, f"{name} must be nonnegative")
        require(self.g in (0, 1), "g must be the frozen binary branch gate (0 or 1)")

    @property
    def report_probabilities(self):
        return (1 - self.u0) * self.s, (1 - self.u1) * (1 - self.t)

    def endpoints(self, r_a, d_a):
        a, b = self.report_probabilities
        return d_a - self.g * b * self.d_fp - self.k, self.g * a * self.q_i - r_a - self.k

    def inspection_loss(self, p):
        # Independently sum report leaves with the unit gap (off=1, on=0).
        off_unresolved = self.u0
        off_reported_on = (1 - self.u0) * (1 - self.s)
        off_failed_or_blocked = (1 - self.u0) * self.s * (1 - self.g * self.q_i)
        on_reported_off_loss = (1 - self.u1) * (1 - self.t) * self.g * self.d_fp
        return p * (off_unresolved + off_reported_on + off_failed_or_blocked) + (1 - p) * on_reported_off_loss + self.k


def strict_win(alpha, beta):
    if max(alpha, beta) <= 0:
        return None
    if min(alpha, beta) > 0:
        return UNIT
    root = alpha / (alpha - beta)
    return Interval(ZERO, root, True, False) if alpha > 0 else Interval(root, ONE, False, True)


def clipped_win(endpoints, domain=UNIT):
    win = strict_win(*endpoints)
    return None if win is None else win.intersect(domain)


def pair_result(inputs, domain=UNIT, reason=None):
    if reason:
        return {"status": "NOT_COMPARABLE", "reason": reason, "domain": str(domain),
                "alpha": None, "beta": None, "strict_win_interval": None, "has_strict_win": None, "tie_region": None}
    alpha, beta = inputs.endpoints(inputs.q_r, inputs.d_r)
    win = clipped_win((alpha, beta), domain)
    if domain == UNIT:
        require((win is not None) == (max(alpha, beta) > 0), "Endpoint criterion disagrees with interval")
    root = alpha / (alpha - beta) if alpha != beta else None
    tie = domain if alpha == beta == 0 else Interval(root, root) if root is not None and domain.contains(root) else None
    return {"status": "COMPARABLE", "domain": str(domain), "alpha": alpha, "beta": beta,
            "slope": beta - alpha, "strict_win_interval": str(win) if win else None,
            "has_strict_win": win is not None, "tie_region": str(tie) if tie else None}


def sign(margin):
    return "WIN" if margin > 0 else "LOSE" if margin < 0 else "TIE"


def direct_margin(inputs, p):
    return p * (1 - inputs.q_r) + (1 - p) * inputs.d_r - inputs.inspection_loss(p)


def check_direct(inputs, domain=UNIT):
    result = pair_result(inputs, domain)
    alpha, beta = result["alpha"], result["beta"]
    win = clipped_win((alpha, beta), domain)
    probes = set(GRID) | {domain.lo, domain.hi, (domain.lo + domain.hi) / 2}
    if alpha != beta:
        probes.add(alpha / (alpha - beta))
    observed = False
    for p in sorted(x for x in probes if domain.contains(x)):
        margin = direct_margin(inputs, p)
        require(margin == (1 - p) * alpha + p * beta, f"Branch loss disagrees at p={p}")
        require((margin > 0) == bool(win and win.contains(p)), f"Wrong strict interval at p={p}")
        observed |= margin > 0
    if domain == UNIT:
        require(observed == result["has_strict_win"], "Full grid disagrees with nonempty criterion")
    return result


def read_frozen(path, expected_sha):
    raw = (ROOT / path).read_bytes()
    require(sha256(raw).hexdigest() == expected_sha, f"Frozen source hash mismatch: {path.as_posix()}")
    return json.loads(raw)


def verify_row(index, row, reference):
    z = {key: value if isinstance(value, bool) else Fraction(value)
         for key, value in (reference | row["parameters"]).items()}
    q = z["success"]
    timely = z["direct_time_over_deadline"] + z["check_extra_time_over_deadline"] < 1
    g = int(timely and z["inspection_branch_authorized"])
    worst = z["inspect_person_over_cap"] + g * z["restore_person_over_cap"]
    can_inspect = worst <= 1
    available = {"defer": True, "escalate": z["escalate_person_over_cap"] <= 1,
                 "direct": z["direct_authorized"] and z["direct_time_over_deadline"] < 1
                 and z["restore_person_over_cap"] <= 1}
    legal = [name for name, allowed in available.items() if allowed]
    x = Inputs(z["sensitivity"], z["specificity"], z["unresolved_off"], z["unresolved_on"],
               q, q, z["direct_downtime_over_gap"], z["false_positive_downtime_over_gap"],
               z["check_charge_over_gap"], g)
    effects = {"defer": (ZERO, ZERO), "escalate": (q * z["escalation_timely_reach"], ZERO),
               "direct": (q, x.d_r)}
    a, b = x.report_probabilities
    expected = {"positive_if_off": str(a), "positive_if_on": str(b), "timely": timely,
                "authorized_and_timely": bool(g), "eligible_no_inspection": legal,
                "inspection_eligible": can_inspect, "inspection_worst_person_over_cap": str(worst),
                "expected_inspect_person_over_cap_at_p0": str(z["inspect_person_over_cap"] + g * b * z["restore_person_over_cap"]),
                "expected_inspect_person_over_cap_slope": str(g * (a - b) * z["restore_person_over_cap"]),
                "conditional_success_over_off": {"inspect": str(g * a * q), **{n: str(v[0]) for n, v in effects.items()}},
                "active_disturbance_over_gap": {"inspect": str(g * b * x.d_fp), **{n: str(v[1]) for n, v in effects.items()}}}
    for key, value in expected.items():
        require(row[key] == value, f"v1 row {index}: {key} disagrees")

    def reason(name):
        if name != "all" and not available[name]:
            return "COMPARATOR_INELIGIBLE"
        return None if can_inspect else "INSPECTION_OVER_PERSON_TIME_CAP"

    ends = {name: x.endpoints(*v) for name, v in effects.items()}
    win = {name: strict_win(*v) if reason(name) is None else None for name, v in ends.items()}
    win["all"] = UNIT if can_inspect else None
    for name in legal:
        win["all"] = win["all"].intersect(win[name]) if win["all"] and win[name] else None

    archives = row["comparisons"]
    spans = {name: [(label, Interval.parse(s)) for label, regions in record["regions"].items() for s in regions]
             for name, record in archives.items()}
    cuts = {ZERO, ONE} | {p for table in spans.values() for _, r in table for p in (r.lo, r.hi)}
    for name, (alpha, beta) in ends.items():
        record = archives[name]
        require(alpha == Fraction(record["advantage_over_gap_at_p0"])
                and beta - alpha == Fraction(record["advantage_over_gap_slope"]), f"v1 row {index}: {name} endpoints")
        if beta != alpha:
            root = alpha / (alpha - beta)
            if UNIT.contains(root):
                cuts.add(root)
    ordered = sorted(cuts)
    probes = cuts | set(GRID) | {(lo + hi) / 2 for lo, hi in zip(ordered, ordered[1:])}
    grid_counts = {name: Counter() for name in archives}
    for p in sorted(probes):
        loss = x.inspection_loss(p)
        margins = {name: p * (1 - r) + (1 - p) * d - loss for name, (r, d) in effects.items()}
        for name, (alpha, beta) in ends.items():
            require(margins[name] == (1 - p) * alpha + p * beta, f"v1 row {index}: {name} branch loss at {p}")
        margins["all"] = min(margins[name] for name in legal)
        for name, regions in spans.items():
            label = reason(name) or sign(margins[name])
            require([tag for tag, region in regions if region.contains(p)] == [label],
                    f"v1 row {index}: {name} stored region at {p}")
            require((label == "WIN") == bool(win[name] and win[name].contains(p)),
                    f"v1 row {index}: {name} exact win interval at {p}")
            if p in GRID_SET:
                grid_counts[name][label] += 1
    for name, counts in grid_counts.items():
        require(dict(counts) == archives[name]["grid_counts"], f"v1 row {index}: {name} grid totals")
    direct = pair_result(x, reason=reason("direct"))
    if direct["status"] == "COMPARABLE":
        require((grid_counts["direct"]["WIN"] > 0) == direct["has_strict_win"], f"v1 row {index}: direct grid criterion")
    return {"v1_row": index, "kind": row["kind"], "regime": row["regime"], "parameter_overrides": row["parameters"],
            "g": g, "inspection_eligible": can_inspect, "eligible_no_inspection": legal, "direct": direct,
            "all_legal_comparison_status": "COMPARABLE" if can_inspect else "NOT_COMPARABLE",
            "strict_win_vs_best_legal": str(win["all"]) if win["all"] else None,
            "grid_counts": {name: dict(c) for name, c in grid_counts.items()}, "exact_probe_points": len(probes)}


def verify_examples():
    inverse = Inputs(Fraction(3, 4), ONE, ZERO, ZERO, ONE, Fraction(1, 2), ZERO, ZERO, ZERO)
    priced_inputs = Inputs(**(asdict(inverse) | {"k": Fraction(1, 4)}))
    free = check_direct(inverse)
    priced = check_direct(priced_inputs)
    require((free["alpha"], free["beta"], free["strict_win_interval"]) == (ZERO, Fraction(1, 4), "(0,1]"),
            "Inverse example without charge disagrees")
    require((priced["beta"], priced["has_strict_win"], priced["tie_region"]) == (ZERO, False, "{1}"),
            "p=1 tie was counted as a win")
    left, right = Fraction(1, 4), Fraction(3, 4)
    domains = (Interval(ZERO, left), Interval(left, right, False, False), Interval(right, ONE))
    cells = [check_direct(inverse, domains[0]), pair_result(inverse, domains[1], "COMPARATOR_INELIGIBLE"),
             check_direct(inverse, domains[2])]
    wins = [cell["strict_win_interval"] for cell in cells if cell["has_strict_win"]]
    require(wins == ["(0,1/4]", "[3/4,1]"], "Piecewise feasible domain was not respected")
    require(cells[1]["has_strict_win"] is None and cells[1]["alpha"] is None,
            "An unavailable comparison was scored")
    return {"inverse_zero_charge": {"inputs": asdict(inverse), **free},
            "inverse_charge_1_over_4": {"inputs": asdict(priced_inputs), **priced},
            "piecewise_unavailable_direct": {"inputs": asdict(inverse), "cells": cells, "strict_win_intervals": wins,
                                             "not_comparable_intervals": [str(domains[1])]}}


def verify_v1():
    spec, original = read_frozen(SPEC, SPEC_SHA), read_frozen(ORIGINAL, ORIGINAL_SHA)
    require(original["frozen_spec"] == spec and original["frozen_spec_sha256"] == SPEC_SHA, "Freeze binding disagrees")
    rows = original["analysis"]["parameter_rows"]
    require(len(rows) == 83 and spec["p_grid_divisions"] == 100, "Unexpected v1 coverage")
    results = [verify_row(i, row, spec["reference"]) for i, row in enumerate(rows, 1)]
    comparable = [row for row in results if row["direct"]["status"] == "COMPARABLE"]
    return {"schema": "aegisdc-ups-stage3-verification-v1", "status": "PASS_EXACT_ARITHMETIC_ONLY",
            "runtime": "Python 3.11+ standard library, fractions.Fraction",
            "command": f"python -B scripts/verify_theorem.py verify-v1 --check {DELIVERY.as_posix()}",
            "sources": {"frozen_spec": {"path": SPEC.as_posix(), "sha256": SPEC_SHA},
                        "v1_result": {"path": ORIGINAL.as_posix(), "sha256": ORIGINAL_SHA},
                        "verifier": {"path": "scripts/verify_theorem.py", "sha256": sha256(Path(__file__).read_bytes()).hexdigest()}},
            "coverage": {"v1_rows": len(results), "grid_points_per_row": len(GRID),
                         "v1_row_prior_grid_points": len(results) * len(GRID),
                         "v1_exact_probe_points_including_grid": sum(r["exact_probe_points"] for r in results),
                         "comparable_direct_rows": len(comparable), "non_comparable_direct_rows": len(results) - len(comparable),
                         "strict_win_direct_rows": sum(r["direct"]["has_strict_win"] for r in comparable),
                         "analytic_examples": 3},
            "accounting": {"arithmetic_attempts": 1, "facility_entries": 0, "policy_calls": 0,
                           "model_calls": 0, "registered_research_runs": 0},
            "scope": "Frozen synthetic rows and analytic examples; no field estimates or simulator acceptance",
            "rows": results, "examples": verify_examples()}


def fraction_arg(value):
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise argparse.ArgumentTypeError("expected a fraction or finite decimal") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    pair = modes.add_parser("pair", help="Compare inspection with one fixed direct action")
    for name in INPUTS:
        pair.add_argument("--" + name.replace("_", "-"), dest=name, type=fraction_arg, required=True)
    pair.add_argument("--g", choices=(0, 1), type=int, default=1, help="Binary check-after-report branch gate")
    pair.add_argument("--direct-ineligible", action="store_true")
    pair.add_argument("--inspection-ineligible", action="store_true")
    v1 = modes.add_parser("verify-v1", help="Recompute frozen v1 and the three analytic examples")
    target = v1.add_mutually_exclusive_group()
    target.add_argument("--write", type=Path, help="Create a new result file (never overwrite)")
    target.add_argument("--check", type=Path, help="Compare against a saved result byte for byte")
    args = parser.parse_args()
    try:
        if args.mode == "pair":
            inputs = Inputs(*(getattr(args, key) for key in INPUTS), g=args.g)
            reason = ("COMPARATOR_INELIGIBLE" if args.direct_ineligible else
                      "INSPECTION_INELIGIBLE" if args.inspection_ineligible else None)
            result = pair_result(inputs, reason=reason) if reason else check_direct(inputs)
            print(json.dumps({"inputs": asdict(inputs), **result}, indent=2, default=str))
            return
        result = verify_v1()
        raw = (json.dumps(result, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
        if args.write:
            with args.write.open("xb") as stream:
                stream.write(raw)
        elif args.check:
            require(args.check.read_bytes() == raw, f"Saved result does not match: {args.check}")
        else:
            print(raw.decode("utf-8"), end="")
            return
        print(json.dumps({"status": result["status"], **result["coverage"]}, sort_keys=True))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")


if __name__ == "__main__":
    main()
