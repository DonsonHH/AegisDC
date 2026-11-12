"""One copy-only qualification of the public reader, comparator and CLI."""

import argparse
from contextlib import redirect_stdout, redirect_stderr
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from aegis_dc.plant import simulate_scenario
from aegis_dc.replay import AttemptReadError, compare_attempts, execution_source_identity, read_attempt


ROOT = Path(__file__).resolve().parents[5]
RUN = "trajectory/run.json"
TERMINAL = "attempt.json"
FROZEN = "frozen-inputs.json"
LEGACY = {
    "v1": "evidence/mainline/engineering/13-replay/capture-02/causal-baseline",
    "v2": "evidence/mainline/engineering/27-full-loop/capture-20261107-02/original",
}
RECEIPT_57 = "evidence/mainline/engineering/39c-development/slice-57/result.json"
DELETE = object()
COST = ("business_evaluation", "components", "costs", "computation")
DIAGNOSTIC = ("business_evaluation", "components", "diagnostic")
SAVED_RESULT_ERROR = "Saved business result differs from re-extracted private endpoints"


def read(path):
    return json.loads(path.read_bytes())


def save(path, value, mode="w"):
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def inventory(path):
    return {file.relative_to(path).as_posix(): file_hash(file)
            for file in sorted(path.rglob("*")) if file.is_file()}


def replace_at(path, value):
    def edit(document):
        parent = document
        for key in path[:-1]:
            parent = parent[key]
        if value is DELETE:
            del parent[path[-1]]
        else:
            parent[path[-1]] = value
    return edit


def cost_audit(run):
    return run["business_evaluation"]["components"]["costs"]["computation"]


def edit_timing(value, *, partial_is_consistent=False):
    def edit(run):
        audit = run["policy_computation_audit"]
        copied = cost_audit(run)["audit_record_details"]
        measurement = cost_audit(run)["selector_elapsed_ns"]
        if value is DELETE:
            del audit[0]["elapsed_ns"], copied[0]["elapsed_ns"]
            if partial_is_consistent:
                measurement.update(value=None, status="NOT_RECORDED", records_with_timing=len(audit) - 1)
        else:
            audit[0]["elapsed_ns"] = copied[0]["elapsed_ns"] = value
            measurement["value"] = sum(row["elapsed_ns"] for row in audit)
    return edit


class NativeEntryBlocked(KeyboardInterrupt):
    """Abort the entire suite before any body of simulate_scenario can run."""


class NegativeReplayQualification(unittest.TestCase):
    def mutated_copy(self, name, source, relative, edit):
        folder = self.output / "cases" / name
        shutil.copytree(self.origins[source], folder)
        artifact = folder / relative
        before = file_hash(artifact)
        value = read(artifact)
        edit(value)
        save(artifact, value)
        after = file_hash(artifact)
        self.assertNotEqual(before, after)
        terminal = folder / TERMINAL
        if relative != TERMINAL:
            record = read(terminal)
            self.assertIn(relative, record["artifacts"])
            record["artifacts"][relative] = after
            if relative == FROZEN:
                record["inputs_sha256"] = digest(value)
            save(terminal, record)
            self.assertEqual(read(terminal)["artifacts"][relative], file_hash(artifact))
        identity = dict(source=source, artifact=relative, original_artifact_sha256=before,
                        mutated_artifact_sha256=after, mutated_attempt_sha256=file_hash(terminal),
                        artifact_hash_refreshed=relative != TERMINAL)
        return folder, identity

    def refuse(self, name, group, source, relative, edit, stage, artifact, message, *, comparison=False, readable=False):
        with self.subTest(case=name):
            folder, mutation = self.mutated_copy(name, source, relative, edit)
            if readable:
                self.assertEqual(read_attempt(folder)["record"]["status"], "COMPLETED")
            row = dict(case=name, group=group, api="compare_attempts" if comparison else "read_attempt",
                       mutation=mutation, copy_readable_before_pair_check=readable,
                       expected=dict(stage=stage, artifact=artifact, message_fragment=message))
            self.cases.append(row)
            try:
                if comparison:
                    compare_attempts(self.origins["record"], folder)
                else:
                    read_attempt(folder)
            except AttemptReadError as error:
                row["observed"] = dict(stage=error.stage, artifact=error.artifact, message=str(error))
            else:
                row["observed"] = dict(status="ACCEPTED_UNEXPECTEDLY")
                self.fail("A semantically invalid copy was accepted")
            self.assertEqual((row["observed"]["stage"], row["observed"]["artifact"]), (stage, artifact))
            self.assertIn(message, row["observed"]["message"])
            row["passed"] = True
            return folder

    def mismatch(self, name, edit, masked_values):
        with self.subTest(case=name):
            folder, mutation = self.mutated_copy(name, "replay", RUN, edit)
            self.assertEqual(read_attempt(folder)["record"]["status"], "COMPLETED")
            result = compare_attempts(self.origins["record"], folder)
            row = dict(case=name, group="timing", api="compare_attempts", mutation=mutation,
                       expected=dict(status="SEMANTIC_MISMATCH", replay_masked_values=masked_values),
                       observed=dict(status=result["status"], strict_values_match=result["strict_values_match"],
                                     timing=result["timing"], semantic_sha256=result["semantic_sha256"]))
            self.cases.append(row)
            self.assertEqual(result["status"], "SEMANTIC_MISMATCH")
            self.assertFalse(result["strict_values_match"])
            self.assertEqual(result["timing"]["original_masked_values"], 34)
            self.assertEqual(result["timing"]["replay_masked_values"], masked_values)
            row["passed"] = True

    def cli_refusal(self, name, arguments, stage, retained):
        with self.subTest(case=name):
            destination = self.output / name
            stdout, stderr = StringIO(), StringIO()
            with patch.object(sys, "argv", ["aegis_dc", *arguments, "--output", str(destination)]), \
                    redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(SystemExit) as stopped:
                runpy.run_module("aegis_dc", run_name="__main__")
            (self.output / f"{name}.stdout").write_text(stdout.getvalue(), encoding="utf-8")
            (self.output / f"{name}.stderr").write_text(stderr.getvalue(), encoding="utf-8")
            record = json.loads(stdout.getvalue())
            row = dict(case=name, group="cli", api=f"python -m aegis_dc {arguments[0]}",
                       expected=dict(exit_code=1, status="FAILED", execution_kind="NOT_STARTED", stage=stage),
                       observed=dict(exit_code=stopped.exception.code, status=record["status"],
                                     execution_kind=record["execution_kind"], stage=record["failure"]["stage"]),
                       terminal_sha256=file_hash(destination / TERMINAL))
            self.cases.append(row)
            self.assertEqual(row["expected"], row["observed"])
            self.assertEqual(read(destination / TERMINAL), record)
            self.assertIsNone(read_attempt(destination)["run"])
            self.assertFalse((destination / "trajectory").exists())
            row["retained_artifact_sha256"] = {}
            for relative, original in retained.items():
                saved = destination / relative
                self.assertEqual(saved.read_bytes(), original.read_bytes())
                row["retained_artifact_sha256"][relative] = file_hash(saved)
            row["passed"] = True

    def test_saved_attempts_refuse_invalid_envelopes_and_nonexact_replays(self):
        self.output.joinpath("cases").mkdir()
        for source, schema in (("v1", "v1"), ("v2", "v2")):
            control = read_attempt(self.origins[source])
            self.assertEqual(control["record"]["status"], "COMPLETED")
            self.assertEqual(control["inputs"]["schema"], f"aegisdc-facility-replay-inputs-{schema}")
            self.controls[source] = control["record_sha256"]
        control = compare_attempts(self.origins["record"], self.origins["replay"])
        self.assertEqual(control["status"], "EXACT_REPLAY_SEMANTICS_MATCH")
        self.assertEqual(control["semantic_sha256"]["original"], self.expected_semantic_sha256)
        self.controls["57-R1_pair_semantic_sha256"] = control["semantic_sha256"]["original"]

        for field in ("business_program", "dispatch_program"):
            self.refuse(f"missing_frozen_{field}", "missing", "replay", FROZEN, replace_at((field,), DELETE),
                        "frozen_input", FROZEN, "closed versioned facility replay inputs contract")
            self.refuse(f"missing_actual_{field}", "missing", "replay", RUN, replace_at(("inputs", field), DELETE),
                        "trajectory_business_program", RUN, "differ from the frozen attempt")
        self.refuse("missing_saved_business_result", "missing", "replay", RUN,
                    replace_at(("business_evaluation",), DELETE), "trajectory_business_result", RUN, "business_evaluation")

        self.refuse("legacy_v1_injected_frozen_program", "injection", "v1", FROZEN, replace_at(("business_program",), {}),
                    "frozen_input", FROZEN, "closed versioned facility replay inputs contract")
        self.refuse("legacy_v2_injected_saved_result", "injection", "v2", RUN, replace_at(("business_evaluation",), {}),
                    "trajectory_business_program", RUN, "Legacy replay inputs cannot carry")
        self.refuse("legacy_v2_injected_submitted_program", "injection", "v2", "inputs.json",
                    replace_at(("business_program",), {}), "submitted_input", "inputs.json", "Legacy submitted inputs")

        self.refuse("wrong_derived_work_program", "mismatch", "replay", RUN,
                    replace_at(("inputs", "work_program", "id"), "wrong-saved-work-program"),
                    "trajectory_business_program", RUN, "differ from the frozen attempt", comparison=True)
        self.refuse("wrong_interpreter_pair", "mismatch", "replay", TERMINAL,
                    replace_at(("source_identity", "python", "version"), "different-frozen-interpreter"),
                    "comparison_source", TERMINAL, "interpreter identity differs", comparison=True, readable=True)
        self.refuse("wrong_original_link", "mismatch", "replay", TERMINAL,
                    replace_at(("replay_of", "attempt_sha256"), "0" * 64),
                    "comparison_origin", TERMINAL, "linked by exact replay", comparison=True, readable=True)
        self.refuse("wrong_request_window", "mismatch", "replay", "request.json", replace_at(("duration_s",), 5.5),
                    "request", "request.json", "Request effective duration_s differs", comparison=True)
        wrong_component = self.refuse("wrong_component_program", "mismatch", "replay", RUN,
                                      replace_at((*DIAGNOSTIC, "program_id"), "wrong-saved-diagnostic"),
                                      "trajectory_business_result", RUN, SAVED_RESULT_ERROR, comparison=True)
        self.refuse("wrong_component_source", "mismatch", "replay", RUN,
                    replace_at((*DIAGNOSTIC, "execution_code_identity", "git_commit"), "0" * 40),
                    "trajectory_business_result", RUN, SAVED_RESULT_ERROR, comparison=True)

        for name, value in (("negative", -1), ("float", 1.25), ("bool", True)):
            self.refuse(f"invalid_ns_{name}", "timing", "replay", RUN, edit_timing(value),
                        "trajectory_business_result", RUN, "must be a nonnegative integer", comparison=True)
        self.refuse("wrong_raw_timing_copy", "timing", "replay", RUN,
                    replace_at((*COST, "audit_record_details", 0, "elapsed_ns"), 0),
                    "trajectory_business_result", RUN, SAVED_RESULT_ERROR, comparison=True)
        self.refuse("wrong_aggregate", "timing", "replay", RUN, replace_at((*COST, "selector_elapsed_ns", "value"), 0),
                    "trajectory_business_result", RUN, SAVED_RESULT_ERROR, comparison=True)
        self.refuse("partial_timing_with_stale_aggregate", "timing", "replay", RUN, edit_timing(DELETE),
                    "trajectory_business_result", RUN, SAVED_RESULT_ERROR, comparison=True)
        self.mismatch("valid_partial_coverage_cannot_compare_equal", edit_timing(DELETE, partial_is_consistent=True), 31)
        self.mismatch("timing_named_leaf_outside_allowlist_is_strict", replace_at(("summary", "elapsed_ns"), 17), 34)

        bad_inputs = self.output / "cases" / "missing_frozen_business_program" / FROZEN
        model = self.origins["record"] / "scenario-input.json"
        self.cli_refusal("cli_record_missing_program", ["record", "--model", str(model), "--inputs", str(bad_inputs)],
                         "validate_inputs", {"submitted-inputs.json": bad_inputs, "submitted-scenario.json": model})
        if wrong_component is not None:
            self.cli_refusal("cli_replay_invalid_component", ["replay", "--attempt", str(wrong_component)],
                             "replay_origin.trajectory_business_result",
                             {f"origin/{name}": wrong_component / name for name in (TERMINAL, "declaration.json", "lifecycle.jsonl", RUN)})
        self.assertEqual(len(self.cases), 24)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--57-r1-originals", dest="originals", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prior = read(ROOT / RECEIPT_57)
    phase = prior["execution_revision_57_r1"]
    origins = {"record": args.originals / "recorded", "replay": args.originals / "replayed",
               **{name: ROOT / relative for name, relative in LEGACY.items()}}
    before = {role: inventory(path) for role, path in origins.items()}
    for role in ("record", "replay"):
        pinned = phase["recorded_pair"][role]
        expected = {**pinned["manifest"]["artifacts"], TERMINAL: pinned["file"]["sha256"]}
        if before[role] != expected:
            raise ValueError(f"Saved 57-R1 {role} bytes differ from the committed receipt")
    source = execution_source_identity()
    if source["implementation_has_changes"] is not False:
        raise ValueError("The frozen execution runtime is not clean")
    args.output.mkdir(exist_ok=False)
    test = NegativeReplayQualification("test_saved_attempts_refuse_invalid_envelopes_and_nonexact_replays")
    test.output, test.origins, test.cases, test.controls = args.output, origins, [], {}
    test.expected_semantic_sha256 = phase["semantic_comparison"]["semantic_sha256"]["original"]
    blocked, result = [], None

    def zero_facility_guard(frame, event, value):
        if event == "call" and frame.f_code is simulate_scenario.__code__:
            blocked.append("simulate_scenario")
            raise NativeEntryBlocked("Facility entry is outside the authorized zero-entry budget")

    sys.setprofile(zero_facility_guard)
    try:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([test]))
    except NativeEntryBlocked as error:
        print(str(error), file=sys.stderr)
    finally:
        sys.setprofile(None)
    unchanged = {role: before[role] == inventory(path) for role, path in origins.items()}
    source_unchanged = source == execution_source_identity()
    ok = (not blocked and result is not None and result.wasSuccessful() and result.testsRun == 1
          and not result.skipped and len(test.cases) == 24 and all(row.get("passed") for row in test.cases)
          and all(unchanged.values()) and source_unchanged)
    status = "PASS_ZERO_FACILITY_NEGATIVE_QUALIFICATION" if ok else "FAILED_NEGATIVE_QUALIFICATION"
    save(args.output / "qualification.json", dict(status=status, selected_tests=1, terminal_tests=0 if result is None else result.testsRun,
         failures=None if result is None else len(result.failures), errors=None if result is None else len(result.errors),
         skips=None if result is None else len(result.skipped), case_count=len(test.cases), passed_cases=sum(
             bool(row.get("passed")) for row in test.cases), controls=test.controls, cases=test.cases,
         facility_entries_budget=0, facility_entries=0, blocked_facility_calls=len(blocked), model_calls=0,
         training_calls=0, registered_research_trials=0, source_identity=source, source_unchanged=source_unchanged,
         originals_unchanged=unchanged, input_attempt_hashes={name: value[TERMINAL] for name, value in before.items()},
         prior_receipt_sha256=file_hash(ROOT / RECEIPT_57), test_sha256=file_hash(Path(__file__))), "x")
    print(status, flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
