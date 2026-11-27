"""Read persisted T11-1 development outcomes in a Slurm allocation. No facility imports."""

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import fmean

import numpy as np


DESIGN_SHA = "6dae3a9992706974fb48eaa7bc03661b57b25726968ce9d152b60683e539112c"
CENTER = "V_COST"
ARCHIVED = ("P", "B", "V_COST_NOPROBE", CENTER)
BASELINES = ("MYOPIC", "POMCP")
ENDPOINTS = ("L", "U", "person", "tool", "fee")
PHASES = ("I", "A", "R", "X")
TICKS = ("900", "1800", "2700", "3600")
CLOSURES = ("NA", "PV")
CLOCK = tuple(range(0, 3601, 60))
EPS = 1e-7
REASONS = ("VALUE", "MANDATORY_OWN_WORK", "AWAIT_OWN_PAID_RESULT", "UNSUPPORTED_PUBLIC_EVIDENCE",
           "NO_COMPLETE_ADMITTED_BRANCH")
TIME_FIELDS = ("ipc_wall_ns", "worker_wall_ns", "worker_cpu_ns", "tree_ns", "leaf_ns",
               "request_serialization_ns", "response_parse_ns", "serialization_ns")
TREE_FIELDS = ("tree_steps", "leaf_evaluations", "simulations", "nodes", "max_depth", "root_action_count")
COUNT_FIELDS = (*PHASES, "refusals", "failed_work", "unfinished_work", "subjects",
                *(f"first_{t}" for t in CLOSURES),
                *(f"{t}_{tick}" for t in CLOSURES for tick in TICKS))
PAIR_FIELDS = (*ENDPOINTS, *COUNT_FIELDS)
VALID_STATES = {"NA", "PV", "OPEN", "OPEN_EXPIRED"}
NAMES = {"P": "既有保护 P", "B": "直接规则 B", "V_COST_NOPROBE": "V** 禁购初检",
         CENTER: "V** 中心", "MYOPIC": "短视 VoI", "POMCP": "有限预算 POMCP"}
FAMILY_NAMES = {"WATER_HEAT": "水侧／热", "NETWORK_POWER": "网络／供电", "RESERVE_TRANSFER": "备用切换",
                "COOLING_ACCESS": "冷却／通行", "LONDON": "伦敦式", "NETHERLANDS": "荷兰式"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def safe_label(value, fallback):
    """Unexpected exception text and absolute private paths never enter a delivery."""
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}", value):
        return value
    return fallback


def checked_object(path, hashes, issues):
    if not path.is_file():
        return {}
    data = path.read_bytes()
    hashes[path.name] = digest(data)
    try:
        value = json.loads(data)
        if isinstance(value, dict):
            return value
    except (ValueError, UnicodeDecodeError):
        pass
    issues.append("UNREADABLE_" + path.stem.upper().replace("-", "_"))
    return {}


def field_hash(record):
    return record.get("input_sha256", record.get("input"))


def identity(record, key, role, sha):
    return record.get("key") == key and record.get("role") == role and field_hash(record) == sha


def verified_references(root):
    directory = root / "references"
    registered = (directory / "design.json").read_bytes()
    require(digest(registered) == DESIGN_SHA, "Frozen design identity")
    design = json.loads(registered)
    panel = design["panel"]
    manifest_bytes = (directory / "original-dev-manifest.json").read_bytes()
    archive_bytes = (directory / "development.json.gz").read_bytes()
    require(digest(manifest_bytes) == panel["manifest_sha256"], "Development manifest identity")
    require(digest(archive_bytes) == panel["scores_sha256"], "Archived development score identity")
    manifest = json.loads(manifest_bytes)
    archive = json.loads(gzip.decompress(archive_bytes))
    order, hashes = manifest["order"], manifest["files"]
    require(len(set(order)) == len(order) == panel["N"] == 72 and set(order) == set(hashes),
            "72 unique registered conditions")
    require(manifest["input_archive"] == panel["archive_sha256"] and manifest["purpose"] == "dev",
            "Source archive and purpose")
    rows = archive["rows"]
    require([row["key"] for row in rows] == order == archive["inputs"]["order"] and archive["inputs"]["files"] == hashes,
            "Published archive binds the same ordered inputs")
    require(Counter(r["family"] for r in rows) == {f: 12 for f in panel["families"]} and
            Counter(r["duration"] for r in rows) == {0: 24, 600: 24, 1200: 24}, "Registered strata")
    archive_units = {}
    for role in ARCHIVED:
        entries = [item for item in archive["units"] if item["role"] == role]
        require(len(entries) == 72 and {e["key"]: e["input"] for e in entries} == hashes,
                "Archived role and per-condition identities: " + role)
        archive_units.update({(e["key"], role): e for e in entries})
    return design, hashes, rows, archive_units


def score_facts(record):
    """Extract only score/public work fields; allow partial accounting after a failed attempt."""
    facts, metrics, errors = {}, {}, []
    for field_name in ENDPOINTS:
        x = record.get(field_name)
        if numeric(x) and x >= 0 and (field_name != "L" or x <= 3600):
            metrics[field_name] = x
        elif field_name in record:
            errors.append("INVALID_" + field_name)
            if numeric(x):
                facts.setdefault("out_of_domain_as_recorded", {})[field_name] = x
    requests = record.get("requests")
    if isinstance(requests, list):
        if all(isinstance(a, list) and len(a) == 2 and numeric(a[0]) and a[0] in CLOCK and
               isinstance(a[1], str) and "::" in a[1] for a in requests):
            facts["requests"] = requests
            phase_counts = Counter(task.rsplit("::", 1)[1] for _, task in requests)
            metrics.update({p: phase_counts[p] for p in PHASES})
            if "fee" in metrics and metrics["fee"] != len(requests):
                errors.append("FEE_REQUEST_MISMATCH")
        else:
            errors.append("INVALID_REQUESTS")
    refusals = record.get("refusals")
    if isinstance(refusals, list):
        if all(isinstance(item, list) and len(item) >= 2 and isinstance(item[-1], str) for item in refusals):
            facts["refusal_reasons"] = dict(Counter(safe_label(item[-1], "OTHER") for item in refusals))
            metrics["refusals"] = len(refusals)
        else:
            errors.append("INVALID_REFUSALS")
    work = record.get("work")
    if isinstance(work, list):
        if all(isinstance(a, list) and len(a) == 4 and isinstance(a[0], str) and isinstance(a[1], str)
               and numeric(a[2]) and (a[3] is None or numeric(a[3])) for a in work):
            facts["work"] = work
            facts["work_status"] = dict(Counter(a[1] for a in work))
            # Frozen workforce records end in completed, rejected, or aborted. A terminal
            # timestamp also distinguishes a new named failure from a still-running task.
            failed = [a for a in work if a[1] != "completed" and (a[1] in {"rejected", "aborted"} or a[3] is not None)]
            metrics["failed_work"] = len(failed)
            metrics["unfinished_work"] = len(work) - sum(a[1] == "completed" for a in work) - len(failed)
        else:
            errors.append("INVALID_WORK")
    first = record.get("first")
    if isinstance(first, dict):
        if all(isinstance(pair, dict) and set(pair) <= set(CLOSURES) and
               all(numeric(t) and t in CLOCK for t in pair.values()) for pair in first.values()):
            facts["first"] = first
            metrics.update({f"first_{t}": sum(t in pair for pair in first.values()) for t in CLOSURES})
        else:
            errors.append("INVALID_FIRST")
    checkpoints = record.get("checkpoints")
    if isinstance(checkpoints, dict):
        clean = {}
        for tick in TICKS:
            states = checkpoints.get(tick)
            if isinstance(states, dict) and states and all(isinstance(s, str) and s in VALID_STATES for s in states.values()):
                clean[tick] = states
                for t in CLOSURES:
                    metrics[f"{t}_{tick}"] = sum(s == t for s in states.values())
            elif tick in checkpoints:
                errors.append("INVALID_CHECKPOINT_" + tick)
        if clean:
            facts["checkpoints"] = clean
        if "3600" in clean:
            subjects = set(clean["3600"])
            metrics["subjects"] = len(subjects)
            if any(set(s) != subjects for s in clean.values()) or set(facts.get("first", {})) - subjects:
                errors.append("CLOSURE_SUBJECT_MISMATCH")
    # These fields are optional in new controller returns. Do not infer a missing
    # physical outcome from a candidate refusal or from the policy's prediction.
    events = record.get("maintenance")
    if isinstance(events, list) and all(isinstance(e, dict) and isinstance(e.get("task"), str) and
            numeric(e.get("at")) and numeric(e.get("until")) for e in events):
        facts["inapplicable_applied"] = [e["task"] for e in events if e.get("indicated") is False]
        facts["harmful_periods"] = [[e["task"], e["at"], e["until"]] for e in events if e["until"] > e["at"]]
    writes = record.get("writes")
    if isinstance(writes, list) and all(isinstance(e, dict) and isinstance(e.get("outcome"), str) for e in writes):
        facts["write_outcomes"] = dict(Counter(safe_label(e["outcome"], "OTHER") for e in writes))
    if isinstance(record.get("locks"), list):
        facts["external_vetoes"] = len(record["locks"])
    if "first_loss" in record and (record["first_loss"] is None or numeric(record["first_loss"])):
        facts["first_loss_s"] = record["first_loss"]
    return facts, metrics, errors


@dataclass
class Unit:
    key: str
    role: str
    input_sha256: str
    source: str
    status: str = "UNSTARTED"
    legality: str = "UNOBSERVED"
    started: bool = False
    native_entry: bool = False
    score_present: bool = False
    job: str | None = None
    attempt: str | None = None
    complete_score: bool = False
    attributable: bool = False
    eligible: bool = False
    legal_L: float | None = None
    clocks: int | None = None
    failure: str | None = None
    elapsed_s: float | None = None
    startup_ns: int | None = None
    facts: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    hashes: dict = field(default_factory=dict)
    lineage: dict = field(default_factory=dict)
    timing: list = field(default_factory=list, repr=False)
    timing_records: int = 0
    timing_issues: list = field(default_factory=list)


def archived_unit(row, role, expected, registered):
    key = row["key"]
    arm = row["arms"][role]
    entry = arm["entry"]
    require(identity(entry, key, role, expected) and arm["clocks"] == len(CLOCK) and
            registered["score"] == arm["score_sha256"], "Archived score linkage: " + role + "/" + key)
    u = Unit(key, role, expected, "T4c_archived")
    u.facts, u.metrics, errors = score_facts(arm)
    require(not errors and all(k in u.metrics for k in PAIR_FIELDS), "Frozen score fields: " + role + "/" + key)
    u.status, u.legality, u.clocks = "ARCHIVED_COMPLETE", "CONFORMANT", len(CLOCK)
    u.job = str(entry.get("job")) if entry.get("job") is not None else None
    u.attempt = entry.get("attempt")
    u.started = u.native_entry = u.score_present = u.complete_score = u.attributable = u.eligible = True
    u.legal_L = u.metrics["L"]
    u.hashes["score.json"] = registered["score"]
    u.lineage = {k: registered[k] for k in ("raw", "IPC") if k in registered}
    return u


def read_call_lines(path, issues):
    """Keep valid prefix records and mark an interrupted or malformed JSON line."""
    records = []
    if not path.is_file():
        return records
    with path.open("rb") as fp:
        for line_no, line in enumerate(fp, start=1):
            try:
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                issues.append(f"INVALID_TIMING_LINE_{line_no}")
                break
            records.append(item)
    return records


def collect_timing(u, path):
    records = read_call_lines(path, u.timing_issues)
    u.timing_records = len(records)
    for index, item in enumerate(records):
        if (index >= len(CLOCK) or item.get("time") != CLOCK[index] or item.get("key", u.key) != u.key or
                item.get("role", u.role) != u.role or item.get("input_sha256", u.input_sha256) != u.input_sha256):
            u.timing_issues.append("TIMING_IDENTITY_OR_ORDER_AT_" + str(index))
            break
        clean = clean_call(item)
        if "ipc_wall_ns" not in clean:
            u.timing_issues.append("MISSING_IPC_AT_" + str(index))
        u.timing.append(clean)
    if u.complete_score and len(u.timing) != len(CLOCK):
        u.timing_issues.append("INCOMPLETE_61_CALL_TIMING")
    if path.is_file():
        u.hashes[path.name] = digest(path.read_bytes())


def clean_call(item):
    observed = {"reason": safe_label(item.get("reason"), "UNCLASSIFIED")}
    for name in (*TIME_FIELDS, *TREE_FIELDS):
        if numeric(item.get(name)) and item[name] >= 0:
            observed[name] = item[name]
    for name in ("effective_choices", "effective_actions"):
        if "root_action_count" not in observed and numeric(item.get(name)) and item[name] >= 0:
            observed["root_action_count"] = item[name]
    return observed


def new_unit(directory, key, role, expected):
    u = Unit(key, role, expected, "T11-1_new")
    records = {name: checked_object(directory / (name + ".json"), u.hashes, u.issues)
               for name in ("entry", "native-entry", "score", "failure")}
    entry, native, score, failure = (records[k] for k in ("entry", "native-entry", "score", "failure"))
    timing = directory / "timing.jsonl"
    if not u.hashes and not timing.is_file():
        return u
    u.started = True
    if entry.get("job") is not None:
        u.job = safe_label(str(entry["job"]), "UNKNOWN")
    if entry.get("attempt") is not None:
        u.attempt = safe_label(str(entry["attempt"]), "UNKNOWN")
    u.native_entry = "native-entry.json" in u.hashes
    u.score_present = "score.json" in u.hashes
    if "failure.json" in u.hashes:
        u.failure = safe_label(failure.get("category"), "UNCLASSIFIED_FAILURE")
    entries_ok = True
    for name, item in (("entry", entry), ("native-entry", native)):
        if not identity(item, key, role, expected):
            u.issues.append("MISSING_OR_MISMATCHED_" + name.upper().replace("-", "_"))
            entries_ok = False
    for name in ("job", "attempt", "pid"):
        if name in entry and name in native and entry[name] != native[name]:
            u.issues.append("ENTRY_IDENTITY_MISMATCH_" + name.upper())
            entries_ok = False
    score_id = identity(score, key, role, expected)
    embedded = score.get("entry")
    if embedded is not None and (not isinstance(embedded, dict) or not identity(embedded, key, role, expected)):
        score_id = False
    if "worker_pid" in native and "worker_pid" in score and native["worker_pid"] != score["worker_pid"]:
        score_id = False
    if u.score_present and not score_id:
        u.issues.append("SCORE_IDENTITY_UNRESOLVED")
    for name in ("raw_sha256", "IPC", "timing_sha256"):
        value = score.get(name)
        if isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value):
            u.lineage[name] = value
    u.attributable = entries_ok and (score_id if u.score_present else True)
    observed = failure.get("observed")
    actual = dict(observed) if isinstance(observed, dict) else {}
    actual.update(score)
    u.facts, u.metrics, errors = score_facts(actual)
    u.issues.extend(errors)
    if numeric(score.get("clocks")) and score["clocks"] in range(62):
        u.clocks = int(score["clocks"])
    elapsed = score.get("elapsed", score.get("elapsed_s", failure.get("elapsed_s")))
    if numeric(elapsed) and elapsed >= 0:
        u.elapsed_s = elapsed
    startup = native.get("worker_startup_ns", entry.get("worker_startup_ns"))
    if numeric(startup) and startup >= 0:
        u.startup_ns = startup
    hard = (score.get("conformant") is False or failure.get("hard_violation") is True or
            u.failure == "HARD_VIOLATION")
    u.legality = "HARD_VIOLATION" if hard else "UNRESOLVED"
    if entries_ok and score_id and u.clocks == len(CLOCK) and not hard and score.get("conformant") is True and not u.failure:
        u.legality = "CONFORMANT"
    if score and u.clocks != len(CLOCK):
        u.issues.append("INCOMPLETE_SCORED_CLOCKS")
    # Partial observations in a failure receipt can preserve real expenditure, never
    # fill gaps in a full-horizon score or qualify a compliant comparison.
    score_metrics, score_errors = u.metrics, errors
    if isinstance(observed, dict) and u.score_present:
        _, score_metrics, score_errors = score_facts(score)
    if u.score_present:
        u.issues.extend("MISSING_SCORE_" + n for n in PAIR_FIELDS if n not in score_metrics)
    u.complete_score = bool(score) and u.clocks == len(CLOCK) and all(n in score_metrics for n in PAIR_FIELDS) and not score_errors
    u.eligible = u.complete_score and u.legality == "CONFORMANT"
    if u.legality == "CONFORMANT":
        u.legal_L = u.metrics.get("L")
    if u.eligible:
        u.status = "COMPLETE_COMPLIANT"
    elif hard:
        u.status = "NONCOMPLIANT"
    elif u.failure:
        u.status = "FAILED_OR_UNRESOLVED"
    elif u.score_present:
        u.status = "INCOMPLETE_OR_UNRESOLVED_SCORE"
    else:
        u.status = "STARTED_WITHOUT_SCORE"
    collect_timing(u, timing)
    if "timing_sha256" in score and score["timing_sha256"] != u.hashes.get("timing.jsonl"):
        u.timing_issues.append("TIMING_DIGEST_MISMATCH")
        u.timing.clear()
    return u


def bootstrap_indices(rows, label, count):
    # Preserve the exact family order and within-family manifest row order of T4c.
    seed = int.from_bytes(hashlib.sha256(("AegisDC/T4c/paired/v1|" + label).encode()).digest()[:16], "big")
    rng = np.random.Generator(np.random.PCG64(seed))
    parts = []
    for family in sorted({r["family"] for r in rows}):
        ids = np.array([i for i, r in enumerate(rows) if r["family"] == family])
        parts.append(ids[rng.integers(0, len(ids), size=(count, len(ids)))])
    return np.concatenate(parts, axis=1)


def interval(values, draws):
    values = np.asarray(values, dtype=float)
    means = values[draws].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5], method="linear")
    return {"mean": float(values.mean()), "lo": float(lo), "hi": float(hi)}


def distribution(values):
    if not values:
        return {"n": 0, "mean": None, "median": None, "p95": None, "max": None}
    median, p95 = np.percentile(values, [50, 95], method="linear")
    return {"n": len(values), "mean": fmean(values), "median": float(median),
            "p95": float(p95), "max": max(values)}


def group_counts(units):
    return {"planned": len(units), "started": sum(u.started for u in units),
            "native_entry": sum(u.native_entry for u in units),
            "score_files": sum(u.score_present for u in units),
            "complete_scores_as_run": sum(u.complete_score for u in units),
            "compliant_pairable": sum(u.eligible for u in units),
            "hard_violations": sum(u.legality == "HARD_VIOLATION" for u in units),
            "started_legality_unresolved": sum(u.started and u.legality == "UNRESOLVED" for u in units),
            "started_missing_score_file": sum(u.started and not u.score_present for u in units),
            "failure_records": sum(u.failure is not None for u in units),
            "unstarted_gap": sum(u.status == "UNSTARTED_GAP" for u in units),
            "unexecuted_suffix": sum(u.status == "UNEXECUTED_SUFFIX" for u in units),
            "missing_entry_no_terminal_receipt": sum(u.status.startswith("NO_ENTRY_EVIDENCE") for u in units),
            "status_counts": dict(Counter(u.status for u in units)),
            "failure_categories": dict(Counter(u.failure for u in units if u.failure))}


def sum_dicts(units, key):
    total = Counter()
    have = 0
    for u in units:
        if key in u.facts:
            have += 1
            total.update(u.facts[key])
    return {"observed_units": have, "counts": dict(total)}


def absolute_summary(units):
    eligible = [u for u in units if u.eligible]
    attributable = [u for u in units if u.attributable]
    complete = len(eligible) == len(units)
    means = {k: fmean(u.metrics[k] for u in eligible) for k in PAIR_FIELDS} if complete else None
    as_run = {}
    for m in PAIR_FIELDS:
        values = [u.metrics[m] for u in attributable if m in u.metrics]
        as_run[m] = {"observed_units": len(values), "sum_observed": sum(values) if values else None}
    first_times = {t: distribution([times[t] for u in eligible for times in u.facts["first"].values() if t in times])
                   for t in CLOSURES}
    purchases = Counter(bought(u) for u in attributable)
    by_legality = []
    for state in ("CONFORMANT", "HARD_VIOLATION", "UNRESOLVED"):
        for identity_ok in (True, False):
            members = [u for u in units if u.started and u.legality == state and u.attributable == identity_ok]
            if not members:
                continue
            totals = {}
            for m in ENDPOINTS:
                known = [u.metrics[m] for u in members if m in u.metrics]
                totals[m] = {"n": len(known), "sum_observed": sum(known) if known else None}
            by_legality.append({"state": state, "attributable": identity_ok, "started": len(members), "metrics": totals})
    return {"source": units[0].source, "counts": group_counts(units), "compliant_full_scope_means": means,
            "compliant_full_scope_counts": {k: sum(u.metrics[k] for u in eligible) for k in COUNT_FIELDS} if complete else None,
            "purchase_yes": purchases["yes"], "purchase_known": purchases["yes"] + purchases["no"],
            "as_run_by_legality": by_legality,
            "qualified_first_times_s": first_times, "qualified_first_times_unit_denominator": len(eligible),
            "as_run_attributable": as_run, "observed_refusal_reasons": sum_dicts(attributable, "refusal_reasons"),
            "observed_work_status": sum_dicts(attributable, "work_status"),
            "observed_write_outcomes": sum_dicts(attributable, "write_outcomes"),
            "observed_external_vetoes": {"units": sum("external_vetoes" in u.facts for u in attributable),
                                         "total": sum(u.facts.get("external_vetoes", 0) for u in attributable)}}


def bought(unit):
    if unit.metrics.get("I", 0) > 0:
        return "yes"
    if unit.complete_score and "I" in unit.metrics:
        return "no"
    return "unknown"


def comparison_pairs(role, center_units, other_units):
    return list(zip(center_units, other_units, strict=True)) if role in BASELINES else list(zip(other_units, center_units, strict=True))


def pair_bounds(pairs):
    lower, upper = [], []
    for left, right in pairs:
        a, b = left.legal_L, right.legal_L
        lower.append((0 if a is None else a) - (3600 if b is None else b))
        upper.append((3600 if a is None else a) - (0 if b is None else b))
    return {"lo": fmean(lower), "hi": fmean(upper),
            "both_compliant_L_known": sum(a.legal_L is not None and b.legal_L is not None for a, b in pairs),
            "only_left_known": sum(a.legal_L is not None and b.legal_L is None for a, b in pairs),
            "only_right_known": sum(a.legal_L is None and b.legal_L is not None for a, b in pairs),
            "both_unknown": sum(a.legal_L is None and b.legal_L is None for a, b in pairs)}


def describe_pairs(pairs):
    good = [(a, b) for a, b in pairs if a.eligible and b.eligible]
    diffs = [a.metrics["L"] - b.metrics["L"] for a, b in good]
    return {"pairable": len(good), "L_lower_equal_higher": [sum(d < -EPS for d in diffs), sum(abs(d) <= EPS for d in diffs),
                                                           sum(d > EPS for d in diffs)],
            "raw_L_equal_rows": sum(a.metrics["L"] == b.metrics["L"] for a, b in good),
            "request_sequence_different_rows": sum(a.facts["requests"] != b.facts["requests"] for a, b in good),
            "person_different_rows": sum(a.metrics["person"] != b.metrics["person"] for a, b in good),
            "tool_different_rows": sum(a.metrics["tool"] != b.metrics["tool"] for a, b in good),
            "fee_different_rows": sum(a.metrics["fee"] != b.metrics["fee"] for a, b in good)}


def paired_summary(role, center_units, new_units, draws):
    pairs = comparison_pairs(role, center_units, new_units)
    desc = describe_pairs(pairs)
    complete = desc["pairable"] == len(pairs)
    estimates = ({m: interval([a.metrics[m] - b.metrics[m] for a, b in pairs], draws) for m in PAIR_FIELDS}
                 if complete else None)
    return {"left": pairs[0][0].role, "right": pairs[0][1].role, "planned": len(pairs), **desc,
            "compliant_full_scope": estimates, "L_identification_bounds": pair_bounds(pairs)}


def purchase_groups(role, centers, others):
    groups = defaultdict(list)
    for center, other in zip(centers, others, strict=True):
        a = bought(center) if center.attributable else "unknown"
        b = bought(other) if other.attributable else "unknown"
        groups[a, b].append((center, other) if role in BASELINES else (other, center))
    output = []
    for a in ("yes", "no", "unknown"):
        for b in ("yes", "no", "unknown"):
            pairs = groups[a, b]
            good = [(x, y) for x, y in pairs if x.eligible and y.eligible]
            output.append({"center_bought": a, "new_bought": b, "observed_class_n": len(pairs),
                           "compliant_pairable": len(good),
                           "conditional_delta": {m: fmean(x.metrics[m] - y.metrics[m] for x, y in good) for m in ENDPOINTS}
                           if good else None})
    return output


def make_scopes(rows, roles, design):
    groups = {"overall": rows}
    for family in design["panel"]["families"]:
        groups["family/" + family] = [r for r in rows if r["family"] == family]
    for duration in (0, 600, 1200):
        groups["duration/" + str(duration)] = [r for r in rows if r["duration"] == duration]
    result = {}
    for scope, subset in groups.items():
        by_role = {role: [r["units"][role] for r in subset] for role in (*ARCHIVED, *roles)}
        draws = bootstrap_indices(subset, scope, design["estimands"]["bootstrap"]["B"])
        result[scope] = {
            "n": len(subset),
            "absolute": {role: absolute_summary(units) for role, units in by_role.items()},
            "pairs": {r: paired_summary(r, by_role[CENTER], by_role[r], draws) for r in roles},
            "purchase_splits": {r: purchase_groups(r, by_role[CENTER], by_role[r]) for r in roles},
        }
    return result


def witnesses(rows, roles):
    events = []
    for row in rows:
        center = row["units"][CENTER]
        for role in roles:
            other = row["units"][role]
            if not other.eligible:
                continue
            for a, b in ((center, other), (other, center)):
                tasks_a = {task: t for t, task in a.facts["requests"]}
                tasks_b = {task: t for t, task in b.facts["requests"]}
                common = {"key": row["key"], "family": row["family"], "duration": row["duration"], "contrast": role,
                          "observed_role": a.role, "other_role": b.role, "observed_L": a.metrics["L"], "other_L": b.metrics["L"],
                          "observed_person": a.metrics["person"], "other_person": b.metrics["person"]}
                for task in sorted(set(tasks_b) - set(tasks_a)):
                    if task in b.facts.get("inapplicable_applied", []) and a.metrics["L"] <= b.metrics["L"] + EPS:
                        events.append(dict(common, kind="omitted_inapplicable_write_without_higher_L",
                                           subject_or_task=task, observed_value=None, other_value=tasks_b[task]))
                    elif task.endswith("::A") and a.metrics["L"] <= b.metrics["L"] + EPS:
                        events.append(dict(common, kind="omitted_write_without_higher_L", subject_or_task=task,
                                           observed_value=None, other_value=tasks_b[task]))
                for task in sorted(set(tasks_a) & set(tasks_b)):
                    if (task.endswith(("::A", "::R", "::X")) and tasks_a[task] > tasks_b[task] and
                            a.metrics["L"] > b.metrics["L"] + EPS):
                        events.append(dict(common, kind="later_same_work_with_higher_L", subject_or_task=task,
                                           observed_value=tasks_a[task], other_value=tasks_b[task]))
                for tick in TICKS:
                    for subject, before in b.facts["checkpoints"][tick].items():
                        after = a.facts["checkpoints"][tick].get(subject)
                        if before in CLOSURES and after in {"OPEN", "OPEN_EXPIRED"}:
                            events.append(dict(common, kind="lost_current_closure", subject_or_task=subject,
                                               observed_value=f"{tick}/{after}", other_value=f"{tick}/{before}"))
    return events


def by_reason(calls):
    grouped = {"ALL": calls}
    for reason in dict.fromkeys((*REASONS, *sorted({v["reason"] for v in calls}))):
        if reason != "ALL":
            grouped[reason] = [v for v in calls if v["reason"] == reason]
    # The historical worker updates VALUE to NO_COMPLETE_ADMITTED_BRANCH after
    # searching. Both paths measured an actual elective planning call.
    grouped["PLANNING_TOTAL"] = [v for v in calls if v["reason"] in {"VALUE", "NO_COMPLETE_ADMITTED_BRANCH"}]
    result = {}
    for reason, subset in grouped.items():
        durations = {}
        for k in TIME_FIELDS:
            ns = [v[k] for v in subset if k in v]
            durations[k] = {**distribution(ns), "total_ns": sum(ns) if ns else None,
                            "over_60s": sum(v > 60_000_000_000 for v in ns) if ns else None}
        counts = {}
        for k in TREE_FIELDS:
            vals = [v[k] for v in subset if k in v]
            counts[k] = {"n": len(vals), "total": sum(vals) if vals else None,
                         "maximum": max(vals) if vals else None}
        result[reason] = {"calls": len(subset), "timing_ns": durations, "tree_counts": counts}
    return result


def center_timing(root, rows):
    directory = root / "center-timing"
    issues, hashes = [], {}
    status = checked_object(directory / "status.json", hashes, issues)
    mode = status.get("mode")
    if mode not in ("isolated_worker_replay", "archived_online"):
        mode = "UNAVAILABLE"
    path = directory / "measurements.jsonl"
    records = read_call_lines(path, issues)
    if path.is_file():
        hashes[path.name] = digest(path.read_bytes())
    keys = {r["key"]: r["units"][CENTER].input_sha256 for r in rows}
    times = defaultdict(list)
    for item in records:
        key = item.get("key")
        if (not isinstance(key, str) or key not in keys or item.get("input_sha256", keys[key]) != keys[key] or
                item.get("validated", True) is not True):
            issues.append("CENTER_CALL_IDENTITY")
            break
        times[key].append(item.get("time"))
    full_series = all(times[k] == list(CLOCK) for k in keys) and len(records) == len(keys) * len(CLOCK)
    complete = (status.get("validated") is True and full_series and mode != "UNAVAILABLE" and not issues and
                all(numeric(i.get("ipc_wall_ns")) and i["ipc_wall_ns"] >= 0 and isinstance(i.get("reason"), str)
                    and i["reason"] for i in records))
    if not complete:
        issues.append("NO_COMPLETE_VALIDATED_CENTER_TIMING")
    startup_values = []
    if complete:
        start_map = status.get("startup_ns_by_key", {})
        if not isinstance(start_map, dict):
            start_map = {}
        start_map = dict(start_map)
        startup_path = directory / "startups.jsonl"
        for item in read_call_lines(startup_path, issues):
            key = item.get("key")
            if isinstance(key, str) and key in keys and item.get("input_sha256", keys[key]) == keys[key]:
                start_map[key] = item.get("worker_startup_ns", item.get("startup_ns"))
        if startup_path.is_file():
            hashes[startup_path.name] = digest(startup_path.read_bytes())
        startup_values = [v for k, v in start_map.items() if k in keys and numeric(v) and v >= 0]
    return {"source": mode, "validated_full_series": complete, "planned_calls": 4392,
            "returned_records": len(records), "clock_complete_units": sum(times[k] == list(CLOCK) for k in keys),
            "issues": list(dict.fromkeys(issues)), "input_receipts": hashes,
            "startup_ns": distribution(startup_values),
            "groups": by_reason([clean_call(v) for v in records] if complete else [])}


def timing_summary(root, rows, roles):
    result = {CENTER: center_timing(root, rows)}
    for role in roles:
        units = [r["units"][role] for r in rows]
        calls = [v for u in units if u.attributable for v in u.timing]
        result[role] = {"source": "new_online_as_run", "planned_calls": len(units) * len(CLOCK),
                        "returned_records": sum(u.timing_records for u in units), "included_calls": len(calls),
                        "clock_complete_units": sum(len(u.timing) == len(CLOCK) for u in units),
                        "timing_issue_positions": sum(bool(u.timing_issues) for u in units),
                        "startup_ns": distribution([u.startup_ns for u in units if u.startup_ns is not None and u.attributable]),
                        "groups": by_reason(calls)}
    return result


def interpret(role, p):
    vals = p["compliant_full_scope"]
    if vals is None:
        return {"case": "INDETERMINATE", "statement": "全板合规比较不可判。已归属的实耗、识别界及未执行后缀见表。",
                "claim": "单列资格状态，C1–C4 沿用原判。"}
    ci = vals["L"]
    if ci["hi"] < 0:
        wording = ("本开发面板上，完整续排的平均缺额低于只允许一次自选写入的短视规则。" if role == "MYOPIC" else
                   "在登记的预算、固定随机实现和四步树深下，V** 的平均缺额低于这项在线树规划器。")
        return {"case": "BASELINE_WORSE", "statement": wording,
                "claim": "C1 增列本项描述性服务比较，保留部分成立。H2 的信息获取解释及 C2–C4 沿用原判。"}
    if ci["lo"] > 0:
        return {"case": "BASELINE_BETTER", "statement": "在此开发面板和规定预算下，该基线的平均服务缺额较低。",
                "claim": "C1 增列复杂规划表现较差的反例；H1–H3 和 C1–C4 的原判保留。"}
    message = "本次配对比较未分出明确方向，区间包含零。"
    if p["raw_L_equal_rows"] == p["planned"]:
        message += (f" {p['planned']} 个位置的原始 L 逐项相同；其中派工时序有差异 {p['request_sequence_different_rows']} 行，"
                    f"人秒、工具秒及费用有差异的行数分别为 {p['person_different_rows']}、{p['tool_different_rows']}、"
                    f"{p['fee_different_rows']}。")
    return {"case": "NO_DIRECTION", "statement": message, "claim": "C1 记本对照未显示额外服务优势；C2–C4 沿用原判。"}


def activity_receipts(root, roles):
    hashes, issues = {}, []
    settled = checked_object(root / "science-settled.json", hashes, issues)
    stop = checked_object(root / "STOP.json", hashes, issues)
    pilot = checked_object(root / "pilot-projection.json", hashes, issues)
    halt = {}
    for k in ("cause", "label", "job"):
        if stop.get(k) is not None:
            halt[k] = safe_label(str(stop[k]), "OTHER")
    if isinstance(stop.get("utc"), str) and re.fullmatch(r"[0-9TZ:+.\- ]{10,40}", stop["utc"]):
        halt["utc"] = stop["utc"]
    projection = {"continue": pilot.get("continue") if isinstance(pilot.get("continue"), bool) else None}
    for key in ("roles", "per_role", "bounds", "projections"):
        block = pilot.get(key)
        if isinstance(block, dict):
            values = {}
            for role in roles:
                detail = block.get(role)
                if numeric(detail):
                    values[role] = detail
                elif isinstance(detail, dict):
                    values[role] = {k: v for k, v in detail.items() if numeric(v) and safe_label(k, "")}
            if values:
                projection["role_bounds"] = values
                break
    allocations = settled.get("allocations")
    return {"has_terminal_science_receipt": isinstance(settled.get("stopped"), bool), "stopped": settled.get("stopped"),
            "stop": halt or None, "pilot": projection, "allocation_records": len(allocations) if isinstance(allocations, (list, dict)) else None,
            "receipt_sha256": hashes, "read_issues": issues}


def build(root):
    design, hashes, archived, registrations = verified_references(root)
    roles = [*BASELINES, *design["parameters"]["oat_roles"]]
    activity = activity_receipts(root, roles)
    require(len(registrations) == len(ARCHIVED) * 72, "One historical unit per role and condition")
    families_seen = Counter()
    rows = []
    for index, orig in enumerate(archived):
        key, family = orig["key"], orig["family"]
        family_index = families_seen[family]
        families_seen[family] += 1
        units = {}
        for role in ARCHIVED:
            registered = registrations[key, role]
            require(registered["input"] == hashes[key], "Historical per-role input: " + role + "/" + key)
            units[role] = archived_unit(orig, role, hashes[key], registered)
        for role in roles:
            u = new_unit(root / "positions" / role / key, key, role, hashes[key])
            if u.complete_score and set(u.facts["checkpoints"]["3600"]) != set(units[CENTER].facts["checkpoints"]["3600"]):
                u.issues.append("CHECKPOINT_SUBJECT_ROSTER_MISMATCH")
                u.eligible, u.legal_L = False, None
                if u.legality != "HARD_VIOLATION":
                    u.legality, u.status = "UNRESOLVED", "INCOMPLETE_OR_UNRESOLVED_SCORE"
            units[role] = u
        rows.append({"key": key, "family": family, "duration": orig["duration"], "manifest_index": index + 1,
                     "batch": 1 + family_index // 2, "units": units})
    for batch in range(1, 7):
        batch_rows = [r for r in rows if r["batch"] == batch]
        require(len(batch_rows) == 12, "Twelve conditions per registered batch")
        for slot, row in enumerate(batch_rows, start=1):
            row["batch_slot"] = slot
    ordered = sorted(rows, key=lambda r: (r["batch"], r["batch_slot"]))
    for role in roles:
        last = max((i for i, r in enumerate(ordered) if r["units"][role].started), default=-1)
        for i, row in enumerate(ordered):
            u = row["units"][role]
            if not u.started:
                u.status = "UNEXECUTED_SUFFIX" if i > last else "UNSTARTED_GAP"
                if not activity["has_terminal_science_receipt"]:
                    u.status = "NO_ENTRY_EVIDENCE_SUFFIX" if i > last else "NO_ENTRY_EVIDENCE_GAP"
    scopes = make_scopes(rows, roles, design)
    data = {"schema": "T11-1-posthoc-development-readback-v1.1", "label": "事后补充、非确认",
            "program_sha256": digest(Path(__file__).read_bytes()),
            "activity": activity, "design_sha256": DESIGN_SHA, "development_manifest_sha256": design["panel"]["manifest_sha256"],
            "archived_scores_sha256": design["panel"]["scores_sha256"],
            "sample": {"planned_conditions": 72, "roles": roles, "planned_new_positions": 720,
                       "historical_absolute_roles": list(ARCHIVED), "native_horizon_s": 3600},
            "estimation": design["estimands"], "oat_parameters": design["parameters"],
            "scopes": scopes, "timing": timing_summary(root, rows, roles),
            "interpretation": {r: interpret(r, scopes["overall"]["pairs"][r]) for r in BASELINES}}
    return data, rows, roles, witnesses(rows, roles)


def compact(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


def tabular(path, headers, records):
    with path.open("x", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp, delimiter="\t", lineterminator="\n")
        writer.writerow(headers)
        for row in records:
            writer.writerow([compact(x) if isinstance(x, (dict, list)) else x for x in row])


def write_tables(directory, data, rows, roles, events):
    scopes = data["scopes"]
    header = ["key", "role", "family", "duration", "manifest_index", "batch", "batch_slot", "input_sha256", "status",
              "legality", "started_evidence", "native_entry", "score_file", "complete_score", "attributable", "pairable",
              "legal_L", "scored_clocks", "timing_records", "timing_prefix_calls", "failure_category", "issues",
              "timing_issues", "elapsed_s", "worker_startup_ns", "job", "attempt", *ENDPOINTS, "L_horizon_percent", *COUNT_FIELDS]
    positions = []
    with (directory / "position-details.jsonl").open("x", encoding="utf-8") as fp:
        for row in rows:
            for role in (*ARCHIVED, *roles):
                u = row["units"][role]
                pct = None if "L" not in u.metrics else 100 * u.metrics["L"] / 3600
                values = [u.key, role, row["family"], row["duration"], row["manifest_index"], row["batch"],
                          row["batch_slot"], u.input_sha256, u.status, u.legality, u.started, u.native_entry,
                          u.score_present, u.complete_score, u.attributable, u.eligible, u.legal_L, u.clocks,
                          u.timing_records if role in roles else None, len(u.timing) if role in roles else None,
                          u.failure, u.issues, u.timing_issues, u.elapsed_s, u.startup_ns, u.job, u.attempt,
                          *[u.metrics.get(m) for m in ENDPOINTS],
                          pct, *[u.metrics.get(m) for m in COUNT_FIELDS]]
                if role in roles:
                    positions.append(values)
                detail = dict(zip(header, values, strict=True))
                detail.update(source=u.source, public_score_details=u.facts, receipts_sha256=u.hashes,
                              lineage_as_recorded=u.lineage)
                fp.write(compact(detail) + "\n")
    tabular(directory / "positions.tsv", header, positions)
    contrast_rows, absolute_rows, split_rows = [], [], []
    for scope, block in scopes.items():
        for role, result in block["pairs"].items():
            paired = result["compliant_full_scope"] or {}
            bounds = result["L_identification_bounds"]
            for m in PAIR_FIELDS:
                est = paired.get(m, {})
                l_fields = [bounds["lo"], bounds["hi"], *result["L_lower_equal_higher"]] if m == "L" else [None] * 5
                contrast_rows.append([scope, role, result["left"], result["right"], block["n"], result["pairable"], m,
                                      est.get("mean"), est.get("lo"), est.get("hi"), *l_fields])
            for grp in block["purchase_splits"][role]:
                diff = grp["conditional_delta"] or {}
                split_rows.append([scope, role, block["n"], grp["center_bought"], grp["new_bought"], grp["observed_class_n"],
                                   grp["compliant_pairable"], *[diff.get(m) for m in ENDPOINTS]])
        for role, absolute in block["absolute"].items():
            counts = absolute["counts"]
            full = absolute["compliant_full_scope_means"] or {}
            for m in PAIR_FIELDS:
                obs = absolute["as_run_attributable"][m]
                full_count = (absolute["compliant_full_scope_counts"] or {}).get(m)
                absolute_rows.append([scope, role, absolute["source"], block["n"], counts["compliant_pairable"], m, full.get(m),
                                      full_count, obs["observed_units"], obs["sum_observed"]])
    tabular(directory / "scope-contrasts.tsv",
            ["scope", "comparison", "left", "right", "planned", "pairable", "endpoint", "mean", "ci025", "ci975",
             "L_bound_lo", "L_bound_hi", "left_L_lower", "L_tie_eps", "left_L_higher"], contrast_rows)
    tabular(directory / "scope-absolute.tsv", ["scope", "role", "source", "planned", "compliant", "endpoint",
            "full_compliant_mean", "full_compliant_count_if_event", "as_run_observed_units", "as_run_sum_observed"], absolute_rows)
    tabular(directory / "purchase-splits.tsv", ["scope", "comparison", "planned", "center_bought", "new_bought", "class_n",
            "compliant_pairable", *["conditional_mean_delta_" + m for m in ENDPOINTS]], split_rows)
    event_fields = ("contrast", "kind", "key", "family", "duration", "observed_role", "other_role", "subject_or_task",
                    "observed_value", "other_value", "observed_L", "other_L", "observed_person", "other_person")
    tabular(directory / "witnesses.tsv", event_fields, ([e[k] for k in event_fields] for e in events))
    time_rows = []
    for role, group in data["timing"].items():
        v = group["startup_ns"]
        time_rows.append([role, group["source"], "POSITION_STARTUP", "worker_startup_ns", None, v["n"], v["median"],
                          v["p95"], v["max"], None, None])
        for reason, val in group["groups"].items():
            for m, v in val["timing_ns"].items():
                time_rows.append([role, group["source"], reason, m, val["calls"], v["n"], v["median"], v["p95"], v["max"],
                                  v["total_ns"], v["over_60s"]])
            for m, v in val["tree_counts"].items():
                time_rows.append([role, group["source"], reason, m, val["calls"], v["n"], None, None,
                                  v["maximum"], v["total"], None])
    tabular(directory / "timing.tsv", ["role", "source", "reason", "metric", "observed_calls", "measured", "median",
            "p95", "max", "total", "above_60s_for_duration"], time_rows)


def fmt(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def name(role):
    return NAMES.get(role, role).replace("**", "\\*\\*")


def ci(p, m):
    full = p["compliant_full_scope"]
    if full is None:
        return "不可判"
    x = full[m]
    return f"{fmt(x['mean'])} [{fmt(x['lo'])}, {fmt(x['hi'])}]"


def bounds_text(p):
    x = p["L_identification_bounds"]
    return f"[{fmt(x['lo'])}, {fmt(x['hi'])}]"


def table(lines, header, body):
    def md(row):
        return "| " + " | ".join("—" if v is None else str(v).replace("|", "\\|").replace("\n", " ") for v in row) + " |"
    lines += ["", md(header), md(["---"] * len(header))]
    lines.extend(md(row) for row in body)
    lines.append("")


def panel_markdown(data, roles, events):
    all_ = data["scopes"]["overall"]
    absolute, pairs = all_["absolute"], all_["pairs"]
    counts = [absolute[r]["counts"] for r in roles]
    started = sum(c["started"] for c in counts)
    complete = sum(c["compliant_pairable"] for c in counts)
    missing = sum(c["unexecuted_suffix"] for c in counts)
    unsettled = sum(c["missing_entry_no_terminal_receipt"] for c in counts)
    lines = ["# T11-1　在线规划与单因素敏感性开发面板", "",
             f"**事后补充、非确认。** 六族 72 个既有开发条件，每个新角色预定 72 个位置。"
             f"本次 720 个新位置中，有启动记录 {started}，完整合规可配对 {complete}，确认未执行后缀 {missing}，"
             f"缺启动记录且无终态回执 {unsettled}。"
             "中心 V\\*\\* 的配对分数来自已归档的 T4c 原运行。", "",
             "## 两项在线规划比较", "",
             "差值均为中心 V\\*\\* 减指定基线。ΔL 为 3,600 秒窗内的归一化服务缺额差，负值表示中心策略的服务缺额较低。"
             "每条件等权，同一范围的十项比较共用 10,000 次族内整条件重抽索引。方括号为双侧 95% 边际百分位区间。"
             "识别界按原分母纳入未知的合规结果，允许其 L 取 0 到 3,600 秒。"]
    table(lines, ["基线", "合规对／预定", "ΔL 秒 [95%]", "ΔU [95%]", "较低／平／较高¹", "Δ人秒 [95%]", "Δ工具秒 [95%]",
                  "Δ费用 [95%]", "全分母 ΔL 识别界"],
          ([name(r), f"{p['pairable']}/{p['planned']}", ci(p, "L"), ci(p, "U"), "/".join(map(str, p["L_lower_equal_higher"])),
            ci(p, "person"), ci(p, "tool"), ci(p, "fee"), bounds_text(p)] for r in BASELINES for p in [pairs[r]]))
    lines.append("¹ 方向按具备合规完整评分的配对计算，平局容差为 10⁻⁷。端点含零时保留不确定性。")
    for role, outcome in data["interpretation"].items():
        lines += ["", f"**{name(role)}。** " + outcome["statement"].replace("**", "\\*\\*") + " " + outcome["claim"]]
    lines += ["", "## 绝对缺额、工时与关闭", "",
              "前四行由归档开发得分取得。随后十行由各自独立的新运行取得。L/窗为归一化需求缺额占一小时的百分比，"
              "U 采用原服务单位秒。费用为原生发行费单位。全板缺少完整合规得分时，绝对均值一栏留空。"]
    table(lines, ["角色", "合规／72", "L 秒", "L/窗", "U", "人秒", "工具秒", "费用", "购买初检行／可判行"],
          ([name(r), f"{a['counts']['compliant_pairable']}/72", fmt(v.get("L")),
            fmt(100 * v["L"] / 3600) + "%" if "L" in v else "—", *[fmt(v.get(m)) for m in ENDPOINTS[1:]],
            purchase_summary(data, r)] for r in (*ARCHIVED, *roles) for a in [absolute[r]]
           for v in [a["compliant_full_scope_means"] or {}]))
    lines += ["检查 I、处置 A、本人复核 R、续检 X 均按真实发行计数。NA 为免处置且有证据关闭，PV 为处置后经本人复核关闭。"
              "“首达”按工单与关闭类型各计一次，其时间中位数只用实际首达的工单。四个快照依次对应 900、1,800、2,700、3,600 秒。"]
    op_rows = []
    for role in (CENTER, *roles):
        a = absolute[role]
        c = a["compliant_full_scope_counts"]
        def seq(fields):
            return "/".join(str(c[f]) for f in fields) if c is not None else "—"
        timings = a["qualified_first_times_s"]
        op_rows.append([name(role), seq(("subjects",)), seq(PHASES), seq(("refusals", "failed_work", "unfinished_work")),
                        seq(("first_NA", "first_PV")), "/".join(fmt(timings[t]["median"], 0) for t in CLOSURES),
                        seq(f"NA_{t}" for t in TICKS), seq(f"PV_{t}" for t in TICKS)])
    table(lines, ["角色", "工单", "I/A/R/X", "拒绝／失败工单／未完工单", "首达 NA/PV 工单", "首达中位秒¹ NA/PV",
                  "当前 NA 四时点", "当前 PV 四时点"], op_rows)
    lines.append("¹ 若有缺分，首达时间一列仍可显示来自完整合规位置的已观测事件。每类型的分子、分母及首次时刻全表见"
                 " [analysis.json](analysis.json) 和 [position-details.jsonl](position-details.jsonl)。")
    lines += ["", "## 四个参数的低侧与高侧", "",
              "每次只改变一个决策参数，低、高两侧均与同一归档中心配对。此表差值为变体减中心，负 ΔL 表示变体缺额较低。"
              "两侧结果限定固定设计的适用范围，原 H1–H3、事故及递归改进主张沿用已接受版本。"]
    oat_rows = []
    pars = data["oat_parameters"]
    for j, parameter in enumerate(pars["names"]):
        for side, role, idx in zip(("低", "高"), pars["oat_roles"][2*j:2*j+2], (0, 2), strict=True):
            p = pairs[role]
            oat_rows.append([parameter, side, pars["grid"][j][idx], pars["centre"][j], f"{p['pairable']}/72", ci(p, "L"),
                             "/".join(map(str, p["L_lower_equal_higher"])), ci(p, "person"), ci(p, "fee"), bounds_text(p)])
    table(lines, ["参数", "侧", "试值", "中心", "合规／预定", "变体 ΔL [95%]", "较低／平／较高", "Δ人秒 [95%]",
                  "Δ费用 [95%]", "ΔL 识别界"], oat_rows)
    lines += ["## 族与公开维护时长", "",
              "每族原分母 12，每档维护时长原分母 24。组内的边际区间描述该组的比较。"
              "分层、购买行为及单因素变体均保留在登记的全板比较之外。"]
    stratum_rows = []
    for s, g in data["scopes"].items():
        if s == "overall":
            continue
        kind, value = s.split("/")
        label = FAMILY_NAMES.get(value, value) if kind == "family" else "维护 " + value + " 秒"
        line = [label, g["n"], fmt(g["absolute"][CENTER]["compliant_full_scope_means"]["L"])]
        for r in BASELINES:
            a = g["absolute"][r]["compliant_full_scope_means"] or {}
            p = g["pairs"][r]
            line.extend([p["pairable"], fmt(a.get("L")), ci(p, "L") if p["compliant_full_scope"] else "不可判，界 " + bounds_text(p)])
        stratum_rows.append(line)
    table(lines, ["范围", "预定", "中心 L 秒", "短视合规对", "短视 L 秒", "中心−短视 ΔL", "POMCP 合规对", "POMCP L 秒",
                  "中心−POMCP ΔL"], stratum_rows)
    lines.append("十项对比在全部十个范围的端点、区间和绝对量列于 [scope-contrasts.tsv](scope-contrasts.tsv) 与"
                 " [scope-absolute.tsv](scope-absolute.tsv)。[购买联合分组](purchase-splits.tsv) 同列中心与新角色是否实际发行过 I、"
                 "无法判定的行及可配对行；其组内均差仅作行为描述。")
    lines += ["", "## 失败、拒绝与未执行位置", "",
              "启动以位置级执行痕迹计，原生入口与完整得分分列。合法拒绝、已中止或未完成的现场工单按真实后果入账。"
              "经证实的硬违规和合法性未决的分数只列实际执行记录。以下资源总量采用能归属到该位置的实测记录，"
              "带分母的实耗可包含未走完的尝试。每一项显示“已观察和／有该量的位置数”。"]
    activity = data["activity"]
    if activity["stop"]:
        cause = activity["stop"].get("cause", "OTHER")
        meaning = "试点耗时投影触发停交" if cause == "pilot_projection_stop" else cause
        lines.append("全包停交回执记为 " + meaning + "。原计划位置、已启动作业和停交后的剩余批次分别计数。")
    if not activity["has_terminal_science_receipt"]:
        lines.append("本次读回未取得科学作业终态回执。尚无位置记录的行保留在原分母内，执行终态待核。")
    ledger_rows = []
    for r in roles:
        a = absolute[r]
        c = a["counts"]
        costs = a["as_run_attributable"]
        def actual(m):
            return f"{fmt(costs[m]['sum_observed'])}/{costs[m]['observed_units']}"
        ledger_rows.append([r, c["started"], c["native_entry"], c["complete_scores_as_run"], c["compliant_pairable"],
                            c["hard_violations"], c["started_legality_unresolved"], c["failure_records"],
                            c["unstarted_gap"], c["unexecuted_suffix"], actual("person"), actual("tool"), actual("fee")])
    table(lines, ["角色（各 72）", "启动", "原生入口", "完整得分", "合规对", "硬违规", "启动后合法性未决", "失败回执",
                  "中间未启动", "未执行后缀", "实耗人秒／n", "实耗工具秒／n", "实际费用／n"], ledger_rows)
    lines.append("逐位置状态、失败类别和缺失字段见 [positions.tsv](positions.tsv)。各角色未执行后缀按冻结批次和批内次序确定。"
                 "具名工单终态、拒绝类别、关闭快照、逐件回执摘要和实际得分见 [position-details.jsonl](position-details.jsonl)。")
    diagnostics = []
    for r in roles:
        for g in absolute[r]["as_run_by_legality"]:
            if g["state"] != "CONFORMANT":
                quantities = [f"{fmt(g['metrics'][m]['sum_observed'])}/{g['metrics'][m]['n']}" for m in ENDPOINTS]
                diagnostics.append([r, g["state"], "已核对" if g["attributable"] else "仅位置目录", g["started"], *quantities])
    if diagnostics:
        lines.append("以下为未合规或合法性未决尝试的实际诊断量。身份未核对时只按尝试目录列记。每格给已观察总量／有该量的位置数。")
        table(lines, ["预定角色", "资格", "身份归属", "启动位置", "L 秒／n", "U／n", "人秒／n", "工具秒／n", "费用／n"],
              diagnostics)
    lines += ["", "## 实际派工与关闭的逐条件见证", "",
              "按清单顺序展示每类第一条可核对的两臂差异。缺额与派工同时变化只显示两条实际轨迹的关系。"]
    witness_types = {"omitted_inapplicable_write_without_higher_L": "省去原生判为不适用的写入，L 未升",
                     "omitted_write_without_higher_L": "少发同名写入，L 未升",
                     "later_same_work_with_higher_L": "同名 A/R/X 较晚发行且 L 较高",
                     "lost_current_closure": "同一工单在相同时点失去有效关闭"}
    witness_rows = []
    for kind, label in witness_types.items():
        matches = [e for e in events if e["kind"] == kind]
        if matches:
            e = matches[0]
            witness_rows.append([label, len(matches), e["key"], e["contrast"], e["observed_role"] + "／" + e["other_role"],
                                 e["subject_or_task"], str(e["observed_value"] if e["observed_value"] is not None else "未发") +
                                 "／" + str(e["other_value"]), fmt(e["observed_L"]) + "／" + fmt(e["other_L"])])
        else:
            witness_rows.append([label, 0, "未取得", "—", "—", "—", "—", "—"])
    table(lines, ["现象", "事件数¹", "条件", "对比", "两侧角色", "工单", "时刻或关闭状态", "两侧 L 秒"], witness_rows)
    lines.append("¹ 同一条件可出现在多个角色、工单或时点。完整事件列表见 [witnesses.tsv](witnesses.tsv)。")
    lines += ["", "## 每次真实决定与树内计算", "",
              "外层 IPC 墙时从发送一次请求到解析完整返回。新角色按实际返回且可归属的调用计时，包括已启动未完成位置上可核对的前缀。"
              "工人 CPU、工人墙时、序列化、冷启动和树／叶耗时以各自时钟单列。服务窗口为 3,600 秒，相邻真实决策点为 60 秒。"]
    center = data["timing"][CENTER]
    labels = {"isolated_worker_replay": "同版公开工人专用重放", "archived_online": "归档逐点在线测量",
              "UNAVAILABLE": "缺少合格来源", "new_online_as_run": "新运行在线"}
    if center["validated_full_series"]:
        lines.append(f"中心来源为{labels[center['source']]}，经验证共 72 × 61 个时点。")
    else:
        lines.append(f"中心未取得完整逐点计时，读回 {center['returned_records']}/4,392 条，覆盖完整时钟的位置为"
                     f" {center['clock_complete_units']}/72。中心延迟各栏留空。")
    timing_rows = []
    def ms(x):
        return fmt(None if x is None else x / 1e6, 3)
    for role in (CENTER, *roles):
        info = data["timing"][role]
        stats = info["groups"]["ALL"]["timing_ns"]
        ipc = stats["ipc_wall_ns"]
        cpu = stats["worker_cpu_ns"]
        startup = info["startup_ns"]
        timing_rows.append([name(role), labels[info["source"]], f"{ipc['n']}/{info['planned_calls']}", ms(ipc["median"]),
                            ms(ipc["p95"]), ms(ipc["max"]), ipc["over_60s"], f"{ms(cpu['median'])} / {cpu['n']}",
                            f"{ms(startup['median'])} / {startup['n']}"])
    table(lines, ["角色", "计时来源", "有效 IPC／预定", "中位 ms", "P95 ms", "最大 ms", ">60 秒次数", "CPU 中位 ms／n",
                  "启动中位 ms／n"], timing_rows)
    pomcp = data["timing"]["POMCP"]["groups"]
    tree_rows = []
    for reason, g in pomcp.items():
        if reason != "ALL" and not g["calls"]:
            continue
        tm, counts_ = g["timing_ns"], g["tree_counts"]
        tree_rows.append([reason, g["calls"], counts_["simulations"]["total"], counts_["tree_steps"]["total"],
                          counts_["leaf_evaluations"]["total"], counts_["max_depth"]["maximum"],
                          ms(tm["tree_ns"]["median"]), ms(tm["tree_ns"]["p95"]), ms(tm["leaf_ns"]["median"]),
                          ms(tm["leaf_ns"]["p95"])])
    table(lines, ["POMCP 调用类型", "次数", "模拟", "树转移", "叶评价", "最大深度", "独占树中位 ms", "独占树 P95 ms",
                  "叶中位 ms", "叶 P95 ms"], tree_rows)
    lines.append("每角色及原因的中位数、P95、最大值、总耗时、超过 60 秒次数及实测分母见 [timing.tsv](timing.tsv)。"
                 "PLANNING_TOTAL 合并进入自选搜索的 VALUE 及搜索后无可排分支两类，与各原因行重叠。"
                 "树转移与叶点评价各自计数，合计上限分别为 2,248,704 与 562,176。")
    lines += ["", "## 论文主张与证据出处", "",
              "C1 成本感知调度与可选付费初检仍为部分成立；C2 两类事故机制的合成验证仍为部分成立；"
              "C3 登记的迁移优势不成立；C4 递归改写的独立增量未建立。本页两项基线的增补措辞见首表。"
              "历史确认检验、事故频率与工程工时的原证据边界继续适用。"
              " [登记的四种情况](https://github.com/DonsonHH/AegisDC/blob/c41ab91096c25399b24193f652dbb8b0b9d39ebd/docs/mainline/t11-eswa-revision/t11-1/interpretation-before-run.md)"
              " · [冻结协议](https://github.com/DonsonHH/AegisDC/blob/e3484fd1967164bfb3fe7b5d9c0309e513e95444/docs/mainline/t11-eswa-revision/protocol-freeze.json)"
              " · [原主张表](https://github.com/DonsonHH/AegisDC/blob/e3484fd1967164bfb3fe7b5d9c0309e513e95444/docs/mainline/t11-eswa-revision/claims-v2.md)",
              "", "原 T4d 同输入 B_cost 的绝对量和机制敏感性已在既有材料单列。此次取得的结果只对六族已消耗开发条件作事后说明。"
              " [原开发族均值](https://github.com/DonsonHH/AegisDC/blob/e3484fd1967164bfb3fe7b5d9c0309e513e95444/docs/mainline/t11-eswa-revision/risk-family-means.tsv)"]
    return "\n".join(lines) + "\n"


def purchase_summary(data, role):
    absolute = data["scopes"]["overall"]["absolute"][role]
    return f"{absolute['purchase_yes']}/{absolute['purchase_known']}"


def emit(root, data, rows, roles, events):
    out = root / "analysis"
    with tempfile.TemporaryDirectory(prefix=".t11-1-analysis-", dir=root) as folder:
        staging = Path(folder)
        write_tables(staging, data, rows, roles, events)
        (staging / "analysis.json").write_text(compact(data) + "\n", encoding="utf-8")
        (staging / "panel.md").write_text(panel_markdown(data, roles, events), encoding="utf-8")
        files = sorted(staging.iterdir())
        seal = staging / "SHA256SUMS.txt"
        seal.write_text("".join(f"{digest(f.read_bytes())}  {f.name}\n" for f in files), encoding="utf-8")
        files.append(seal)
        out.mkdir(exist_ok=True)
        for f in files:
            dest = out / f.name
            if dest.exists():
                require(dest.read_bytes() == f.read_bytes(), "Refuse to overwrite different readback: " + f.name)
        # Link only complete files. A colliding writer cannot replace existing evidence.
        for f in files:
            dest = out / f.name
            if not dest.exists():
                os.link(f, dest)
        require(all((out / f.name).read_bytes() == f.read_bytes() for f in files), "Published analysis bytes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activity", type=Path, required=True)
    args = parser.parse_args()
    require(os.environ.get("SLURM_JOB_ID"), "Offline scientific readback requires its assigned Slurm allocation")
    require(args.activity.is_absolute() and args.activity.is_dir(), "Absolute existing activity directory")
    data, rows, roles, events = build(args.activity)
    emit(args.activity, data, rows, roles, events)
    print("T11-1 development readback sealed: 72 registered conditions x 10 new roles", flush=True)


if __name__ == "__main__":
    main()
