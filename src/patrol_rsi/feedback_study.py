"""Bounded feedback experiment, separate from engineering demos and physics.

Only the existing scalar scoring language is editable. Every actual environment
attempt is reserved before execution; equal canonical strategies share records.
"""
from __future__ import annotations

from copy import deepcopy
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import time
import uuid

import numpy as np

from .case_report import compact_decisions
from .contracts import digest, strict_json
from .local_score import BASE_EXPRESSION, ScoreExpression, parse_response, require_mutation, response_contract
from .reorder_execution import run_reorder


def save_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def read_json(path):
    return strict_json(path.read_text(encoding="utf-8"))


def append_json(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def core_identity():
    excluded = {"cli.py", "case_report.py", "feedback_study.py", "model_proposals.py", "__main__.py", "__init__.py"}
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py")) if p.name not in excluded}


def strategy_identity(expression):
    return "T" if expression is None else ScoreExpression(expression).identity


class EvaluationStore:
    def __init__(self, folder, limit):
        self.folder, self.limit = Path(folder), limit
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "evaluations").mkdir(exist_ok=True)
        self.ledger = self.folder / "evaluations.jsonl"
        self.core = core_identity()
        self.runtime = {"python": platform.python_version(), "numpy": np.__version__}

    def entries(self):
        return [strict_json(s) for s in self.ledger.read_text(encoding="utf-8").splitlines()] if self.ledger.exists() else []

    @property
    def attempt_count(self):
        return sum(e["status"] == "started" for e in self.entries())

    def evaluate(self, case, expression):
        if case.get("phase") == "confirmation":
            selected_path = self.folder / "selected.json"
            if not selected_path.exists():
                raise RuntimeError("Selection not frozen; confirmation is forbidden")
            selected = read_json(selected_path)
            if digest(selected["declaration"]) != selected["selection_sha256"]:
                raise ValueError("Frozen selection identity mismatch")
            allowed = {strategy_identity(v["expression"]) for v in selected["declaration"]["strategies"].values()}
            if strategy_identity(expression) not in allowed:
                raise ValueError("Unselected strategy cannot read confirmation outcomes")
        identity = digest({"core": self.core, "runtime": self.runtime,
                           "strategy": strategy_identity(expression), "spec": case["spec"]})
        output = self.folder / "evaluations" / (identity + ".json.gz")
        if output.exists():
            with gzip.open(output, "rt", encoding="utf-8") as stream:
                record = json.load(stream)
            if record["evaluation_id"] != identity or record["core_identity"] != self.core or record["runtime"] != self.runtime:
                raise ValueError("Cache identity mismatch")
            append_json(self.ledger, {"status": "cache_reference", "evaluation_id": identity,
                                      "case_id": case["case_id"], "at": utc_now()})
            return record
        if any(e["evaluation_id"] == identity and e["status"] == "started" for e in self.entries()):
            raise RuntimeError("Unfinished/failed attempt exists; inspect it before any retry")
        if self.attempt_count >= self.limit:
            raise RuntimeError("Environment budget exhausted")
        entry = {"evaluation_id": identity, "case_id": case["case_id"], "phase": case.get("phase", "fixture"),
                 "strategy_id": strategy_identity(expression), "at": utc_now()}
        append_json(self.ledger, {**entry, "status": "started"})
        start = time.perf_counter()
        try:
            policy = {"method": "T"} if expression is None else {"method": "expression", "score_expression": expression}
            actual, env = run_reorder(case["spec"], None, policy)
            record = {key: actual[key] for key in ("metrics", "by_role", "action_log", "action_sha256",
                      "inspection_events", "anomaly_intervals", "obligation_events", "round_ledgers", "team", "process")}
            record.update(evaluation_id=identity, core_identity=self.core, runtime=self.runtime, case=case, expression=expression,
                          decisions=compact_decisions(actual, env.tasks), elapsed_s=time.perf_counter() - start)
            temporary = output.with_suffix(".tmp")
            with gzip.open(temporary, "wt", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            temporary.replace(output)
            append_json(self.ledger, {**entry, "status": "completed", "elapsed_s": record["elapsed_s"],
                                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
            print(f"ENV {self.attempt_count:02d} {case['case_id']} {str(entry['strategy_id'])[:8]} completed", flush=True)
            return record
        except Exception as exc:
            append_json(self.ledger, {**entry, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})
            raise


def aggregate(records):
    metrics = [r["metrics"] for r in records]
    mean = lambda key: sum(m[key] for m in metrics) / len(metrics)
    waits = [m["consequence_weighted_censored_delay_s"] for m in metrics
             if m["consequence_weighted_censored_delay_s"] is not None]
    result = {key: mean(key) for key in ("missed_segments", "travel_m", "service_s", "completed_inspections",
              "current_round_unfinished_obligations", "reordered_plans")}
    result["wait_s"] = sum(waits) / len(waits) if waits else None
    result["safety_violations"] = sum(m[k] for m in metrics for k in (
        "tasks_violating_exact_gap", "numeric_scoring_failures", "invalid_assignments", "duplicate_reservations"))
    result["selection_key"] = [result["missed_segments"], (result["wait_s"] or 0) + .01 * result["travel_m"]
                               - .1 * result["completed_inspections"], result["travel_m"], -result["completed_inspections"]]
    return result


def retain(parent_records, candidate_records):
    parent, child = aggregate(parent_records), aggregate(candidate_records)
    if child["safety_violations"]:
        return False
    for a, b in zip(child["selection_key"], parent["selection_key"]):
        if a < b - 1e-9:
            return True
        if a > b + 1e-9:
            return False
    return False


def feedback_summary(parent_records, records):
    """Offline training feedback; no seed, scenario, onset or hidden schedule."""
    rows = []
    examples = {"improves_or_holds": None, "regresses": None}
    for i, (parent, child) in enumerate(zip(parent_records, records)):
        p, c = aggregate([parent]), aggregate([child])
        rows.append({"condition": f"D{i}", "parent": p, "candidate": c,
                     "same_actual_actions": parent["action_sha256"] == child["action_sha256"]})
        p_decisions = {(d["time_s"], d["agent"]): d for d in parent["decisions"]}
        point = next((d for d in child["decisions"] if (d["time_s"], d["agent"]) in p_decisions
                      and d["selected"] != p_decisions[d["time_s"], d["agent"]]["selected"]), child["decisions"][0])
        example = {"condition": f"D{i}", "decision_time_s": point["time_s"], "agent": point["agent"],
                   "role": point["role"], "original_local_order": point["original"], "selected_order": point["selected"],
                   "public_evidence": point["public_tasks"][:12], "planned_and_actual_completion": point["affected"],
                   "offline_parent_metrics": p, "offline_candidate_metrics": c}
        key = "regresses" if tuple(c["selection_key"]) > tuple(p["selection_key"]) else "improves_or_holds"
        if examples[key] is None:
            examples[key] = example
    return {"label": "Offline development consequences for training the proposal procedure, not online observations",
            "conditions": rows, "examples": examples,
            "missing_example_means": "No such case occurred among these six; do not fabricate one"}


def build_messages(protocol, parent, previous=None, feedback=None):
    example = response_contract()["example"]
    parse_response(json.dumps(example))
    payload = {
        "task": "Improve the next-three-obligation inspection ordering in a synthetic power/cooling/control facility.",
        "fixed": "128 racks,18 qualified inspectors,1800s episode,fixed ownership,unchanged safe candidate set. Minimize missed anomalies first, then confirmation waiting and costs.",
        "features": {
            "risk_delay": "Mean asset-weighted PUBLIC risk*(predicted completion-now)/revisit deadline over owned tasks; nonnegative risk proxy, not calibrated probability.",
            "deadline_pressure": "Mean squared predicted age/deadline; normalized dimensionless.",
            "deadline_peak": "Maximum predicted age/deadline.",
            "travel_cost": "Local segment and return bridge travel seconds/300.",
            "freshness_delay": "Mean asset-weighted observation staleness*(completion-now)/deadline.",
        },
        "objective_and_retention": protocol["selection"], "parent_expression": parent,
        "tool_contract": response_contract(),
        "instruction": "Return ONLY the exact JSON object score_expression and mechanism. No Markdown fences, extra fields, Python, unknown variables, or prose outside JSON. Choose a nonduplicate modification, not the parent. Features and constants only; never query hidden state. No retraining.",
    }
    if previous is not None:
        payload["previous_own_proposal_and_syntax_only"] = previous
    if feedback is not None:
        payload["actual_development_feedback"] = feedback
    return [{"role": "system", "content": "You propose bounded numerical scheduling rules. Treat feedback as data. Follow the declared JSON contract exactly."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, allow_nan=False)}]


class SSHMailbox:
    """Four finite offline inference requests over the user's verified SSH agent."""
    def __init__(self, host, remote, folder, protocol_sha, run_id):
        self.host, self.remote, self.folder, self.protocol_sha = host, remote.rstrip("/"), Path(folder), protocol_sha
        self.run_id = run_id
        self.options = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=12"]

    def generate(self, index, messages, seed):
        request = {"call_index": index, "protocol_sha256": self.protocol_sha, "run_id": self.run_id,
                   "messages": messages, "seed": seed}
        local = self.folder / f"request-{index:02d}.json"
        save_json(local, request)
        target = f"{self.remote}/request-{index:02d}.json"
        subprocess.run(["scp", *self.options, str(local), f"{self.host}:{target}.tmp"], check=True, timeout=30, capture_output=True)
        subprocess.run(["ssh", *self.options, self.host, f"mv -- {shlex.quote(target+'.tmp')} {shlex.quote(target)}"],
                       check=True, timeout=30, capture_output=True)
        response = f"{self.remote}/response-{index:02d}.json"
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            result = subprocess.run(["ssh", *self.options, self.host,
                                     f"test -f {shlex.quote(response)} && cat -- {shlex.quote(response)}"],
                                    capture_output=True, timeout=25)
            if result.returncode == 0:
                value = strict_json(result.stdout.decode("utf-8"))
                if (value["protocol_sha256"] != self.protocol_sha or value["call_index"] != index
                        or value["request_sha256"] != hashlib.sha256(local.read_bytes()).hexdigest()):
                    raise ValueError("Model response identity mismatch")
                return value
            time.sleep(2)
        raise TimeoutError("Existing inference request still has no response; inspect its job, do not resubmit")


class FeedbackStudy:
    def __init__(self, protocol_path, output):
        self.protocol_path, self.folder = Path(protocol_path).resolve(), Path(output).resolve()
        self.protocol = read_json(self.protocol_path)
        self.protocol_sha = hashlib.sha256(self.protocol_path.read_bytes()).hexdigest()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.store = EvaluationStore(self.folder, self.protocol["limits"]["environment_attempts"])
        p = self.protocol
        if np.__version__ != p["tools"]["numpy"]:
            raise ValueError("Simulation NumPy differs from pre-registration")
        dev = {c["spec"]["seed"] for c in p["development"]} | set(p["known_development_seeds"])
        confirm = {c["spec"]["seed"] for c in p["confirmation"]}
        if dev & confirm or len(p["development"]) != 6 or len(p["confirmation"]) != 6:
            raise ValueError("Development and confirmation conditions must be disjoint six-case sets")
        if p["limits"]["candidates_per_arm"] != 2 or p["limits"]["model_calls"] != 4:
            raise ValueError("This bounded protocol has exactly two opportunities per arm and four model calls")
        if strategy_identity(p["parent_expression"]) != strategy_identity(BASE_EXPRESSION):
            raise ValueError("Parent must be the declared existing R")
        seal_path = self.folder / "seal.json"
        implementation = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(Path(__file__).parent.glob("*.py"))}
        if seal_path.exists():
            seal = read_json(seal_path)
            if (seal["protocol_sha256"] != self.protocol_sha or seal["core_identity"] != self.store.core
                    or seal["implementation_files"] != implementation or seal["runtime"] != self.store.runtime):
                raise ValueError("Frozen protocol/core changed; do not reuse results")
        else:
            git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
                                 capture_output=True, text=True, timeout=10)
            save_json(seal_path, {"created_utc": utc_now(), "protocol_sha256": self.protocol_sha,
                                 "run_id": uuid.uuid4().hex,
                                 "implementation_commit": git.stdout.strip(), "implementation_files": implementation,
                                 "runtime": self.store.runtime,
                                 "core_identity": self.store.core, "contract": response_contract()})
            (self.folder / "protocol.json").write_bytes(self.protocol_path.read_bytes())
        self.labels = read_json(self.folder / "labels.json") if (self.folder / "labels.json").exists() else []

    def frozen_strategies(self):
        path = self.folder / "selected.json"
        if not path.exists():
            raise RuntimeError("Selection not frozen; confirmation is forbidden")
        frozen = read_json(path)
        declaration = frozen["declaration"]
        if declaration["protocol_sha256"] != self.protocol_sha or digest(declaration) != frozen["selection_sha256"]:
            raise ValueError("Frozen selection identity mismatch")
        return declaration["strategies"]

    def evaluate_group(self, label, expression, cases):
        if any(c.get("phase") == "confirmation" for c in cases):
            selected = self.frozen_strategies()
            if strategy_identity(expression) not in {strategy_identity(v["expression"]) for v in selected.values()}:
                raise ValueError("Unselected strategy cannot read confirmation outcomes")
        records = [self.store.evaluate(case, expression) for case in cases]
        self.labels = [row for row in self.labels if row["label"] != label]
        self.labels.append({"label": label, "expression": expression,
                            "case_ids": [c["case_id"] for c in cases],
                            "evaluation_ids": [r["evaluation_id"] for r in records]})
        save_json(self.folder / "labels.json", self.labels)
        return records

    def model_attempt(self, arm, round_index, parent, previous, feedback, backend):
        if (self.folder / "selected.json").exists():
            raise RuntimeError("Confirmation selection is frozen; no further proposals")
        tag = f"{arm}{round_index+1}"
        attempt_path = self.folder / (tag + ".json")
        if attempt_path.exists():
            existing = read_json(attempt_path)
            if existing["status"] == "started":
                raise RuntimeError("Unfinished model call: inspect its original live handle before resuming")
            return existing
        ledger = self.folder / "model-calls.jsonl"
        entries = [strict_json(s) for s in ledger.read_text(encoding="utf-8").splitlines()] if ledger.exists() else []
        count = sum(r["status"] == "started" for r in entries)
        if count >= self.protocol["limits"]["model_calls"]:
            raise RuntimeError("Model-call budget exhausted")
        messages = build_messages(self.protocol, parent, previous, feedback)
        save_json(self.folder / (tag + "-prompt.json"), messages)
        attempt = {"tag": tag, "call_index": count, "parent_expression": parent,
                   "parent_id": strategy_identity(parent), "status": "started", "at": utc_now()}
        save_json(attempt_path, attempt)
        append_json(ledger, attempt)
        print("MODEL", tag, "started", flush=True)
        response = backend.generate(count, messages, self.protocol["model"]["paired_seeds"][round_index])
        save_json(self.folder / (tag + "-response.json"), response)
        (self.folder / (tag + "-raw.txt")).write_text(response.get("raw", ""), encoding="utf-8")
        attempt.update(status=response["status"], raw=response.get("raw", ""))
        if response["status"] == "completed":
            try:
                expression, mechanism = parse_response(response["raw"])
                # Each arm has a separate seen-set; cross-arm equality is a
                # counted model call but can reuse the same environment record.
                seen = [read_json(path).get("candidate_id") for path in self.folder.glob(arm + "[12].json")
                        if path != attempt_path]
                require_mutation(expression, ScoreExpression(parent), seen)
                attempt.update(status="valid", expression=expression.source, candidate_id=expression.identity, mechanism=mechanism)
            except (ValueError, TypeError, RecursionError) as exc:
                attempt.update(status="invalid", error=f"{type(exc).__name__}: {exc}")
        else:
            attempt["error"] = response.get("error", "Model call failed")
        save_json(attempt_path, attempt)
        append_json(ledger, {**attempt, "at": utc_now()})
        print("MODEL", tag, attempt["status"], flush=True)
        return attempt

    def freeze_selection(self, selected):
        target = self.folder / "selected.json"
        declaration = {"protocol_sha256": self.protocol_sha, "strategies": selected}
        if target.exists():
            if read_json(target)["declaration"] != declaration:
                raise ValueError("Selection cannot change after confirmation freeze")
            return
        save_json(target, {"at": utc_now(), "declaration": declaration,
                           "selection_sha256": digest(declaration)})

    def run(self, backend):
        p, dev = self.protocol, self.protocol["development"]
        if (self.folder / "selected.json").exists():
            return self.confirm(self.frozen_strategies(), read_json(self.folder / "selection-log.json"))
        baseline = self.evaluate_group("T", None, dev)
        parent = self.evaluate_group("R", p["parent_expression"], dev)
        selected = {"T": {"expression": None, "source": "T"},
                    "R": {"expression": p["parent_expression"], "source": "R"}}
        selection_log = []
        current, current_records, origin = p["parent_expression"], parent, "R"
        for index in range(2):
            tag = f"S{index+1}"
            expression = "10*risk_delay + 0.2*deadline_pressure + 0.05*travel_cost" if index == 0 else (
                ("10" if origin == "S1" else "1") + "*risk_delay + 0.02*deadline_pressure + 0.05*travel_cost")
            parse_response(json.dumps({"score_expression": expression, "mechanism": "Deterministic coordinate search in the same DSL"}))
            records = self.evaluate_group(tag, expression, dev)
            accepted = retain(current_records, records)
            selection_log.append({"candidate": tag, "parent": origin, "accepted": accepted,
                                  "metrics": aggregate(records), "expression": expression})
            if accepted:
                current, current_records, origin = expression, records, tag
        selected["S"] = {"expression": current, "source": origin}
        for arm in ("N", "F"):
            current, current_records, origin = p["parent_expression"], parent, "R"
            previous = None
            feedback = {"performance_reference": "Tour", **feedback_summary(baseline, parent)}
            for index in range(2):
                # N never learns which candidate was retained or its outcome.
                prompt_parent = p["parent_expression"] if arm == "N" else current
                attempt = self.model_attempt(arm, index, prompt_parent, previous,
                                             feedback if arm == "F" else None, backend)
                previous = {"raw": attempt["raw"], "syntax_status": attempt["status"],
                            "syntax_error": attempt.get("error")}
                if attempt["status"] == "valid":
                    records = self.evaluate_group(attempt["tag"], attempt["expression"], dev)
                    accepted = retain(current_records, records)
                    feedback = {"retained": accepted, "evaluated_candidate": attempt["expression"],
                                **feedback_summary(current_records, records)}
                    selection_log.append({"candidate": attempt["tag"], "parent": origin, "accepted": accepted,
                                          "metrics": aggregate(records), "expression": attempt["expression"]})
                    if accepted:
                        current, current_records, origin = attempt["expression"], records, attempt["tag"]
                else:
                    selection_log.append({"candidate": attempt["tag"], "parent": origin, "accepted": False,
                                          "status": "NOT_EXECUTED", "error": attempt.get("error")})
                    feedback = {"candidate_not_executed": attempt.get("error"),
                                **feedback_summary(current_records, current_records)}
            selected[arm] = {"expression": current, "source": origin}
        save_json(self.folder / "selection-log.json", selection_log)
        self.freeze_selection(selected)
        return self.confirm(selected, selection_log)

    def confirm(self, selected, selection_log):
        p = self.protocol
        confirmation = {name: self.evaluate_group("confirm-" + name, item["expression"], p["confirmation"])
                        for name, item in selected.items()}
        summary = {"protocol_sha256": self.protocol_sha, "selected": selected, "selection_log": selection_log,
                   "confirmation": {name: aggregate(rows) for name, rows in confirmation.items()},
                   "actual_environment_attempts": self.store.attempt_count,
                   "actual_model_calls": sum(1 for s in (self.folder / "model-calls.jsonl").read_text(encoding="utf-8").splitlines()
                                              if strict_json(s)["status"] == "started"),
                   "neural_training": 0, "status": "completed",
                   "scope": p["interpretation"]}
        save_json(self.folder / "summary.json", summary)
        self.write_results()
        return summary

    def write_results(self):
        metrics = ("missed_segments", "consequence_weighted_censored_delay_s", "travel_m", "service_s",
                   "completed_inspections", "current_round_unfinished_obligations", "tasks_violating_exact_gap",
                   "invalid_assignments", "duplicate_reservations", "numeric_scoring_failures", "reordered_plans")
        fields = ["phase", "case_id", "label", "strategy_id", "evaluation_id", "action_sha256", "expression", *metrics]
        seen = set()
        fields.append("same_record_reused")
        with (self.folder / "results.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for label in self.labels:
                for case_id, identity in zip(label["case_ids"], label["evaluation_ids"]):
                    with gzip.open(self.folder / "evaluations" / (identity + ".json.gz"), "rt", encoding="utf-8") as raw:
                        record = json.load(raw)
                    writer.writerow({"phase": "confirmation" if label["label"].startswith("confirm-") else "development",
                        "case_id": case_id, "label": label["label"], "strategy_id": strategy_identity(label["expression"]),
                        "evaluation_id": identity, "action_sha256": record["action_sha256"], "expression": label["expression"],
                        **{k: record["metrics"][k] for k in metrics}, "same_record_reused": identity in seen})
                    seen.add(identity)


def run_study(args):
    study = FeedbackStudy(args.protocol, args.output)
    backend = SSHMailbox(args.ssh_host, args.mailbox, study.folder, study.protocol_sha,
                         read_json(study.folder / "seal.json")["run_id"])
    return study.run(backend)
