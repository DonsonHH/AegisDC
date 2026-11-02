"""Public experiment contracts: counted execution, isolation, and frozen testing."""
import json
from pathlib import Path
import tempfile
from copy import deepcopy
import unittest
import subprocess
from unittest.mock import patch

from patrol_rsi.feedback_study import EvaluationStore, FeedbackStudy, SSHMailbox, build_messages, retain, save_json
from patrol_rsi.model_proposals import completed_request, sha_file
from patrol_rsi.local_score import BASE_EXPRESSION


class EvaluationBudgetTests(unittest.TestCase):
    def test_numeric_scoring_failure_is_a_rejected_outcome_not_a_lost_campaign(self):
        case = {"case_id": "numeric-fixture", "spec": {"seed": 0, "scenario": "healthy",
                "duration_s": 900, "fault_start_s": 335, "noise_c": .2,
                "estimator": "nominal", "control": "feedback", "resources": "provisioned"}}
        with tempfile.TemporaryDirectory() as folder:
            store = EvaluationStore(Path(folder), limit=1)
            record = store.evaluate(case, "safe_div(deadline_pressure,0)*10")
            self.assertGreater(record["metrics"]["numeric_scoring_failures"], 0)
            self.assertEqual(record["metrics"]["invalid_assignments"], 0)
            self.assertTrue(any(d["numeric_error"] for d in record["decisions"]))
            self.assertEqual(store.attempt_count, 1)

    def test_cache_does_not_spend_another_trial_and_limit_stops_execution(self):
        case = {"case_id": "fixture", "spec": {"seed": 41000, "scenario": "healthy",
                "duration_s": 900, "fault_start_s": 335, "noise_c": .2,
                "estimator": "nominal", "control": "feedback", "resources": "provisioned"}}
        with tempfile.TemporaryDirectory() as folder:
            store = EvaluationStore(Path(folder), limit=1)
            first = store.evaluate(case, BASE_EXPRESSION)
            second = store.evaluate(case, BASE_EXPRESSION)
            self.assertEqual(first["evaluation_id"], second["evaluation_id"])
            self.assertEqual(store.attempt_count, 1)
            other = {**case, "spec": {**case["spec"], "seed": 41001}}
            with self.assertRaisesRegex(RuntimeError, "Environment budget"):
                store.evaluate(other, BASE_EXPRESSION)
            self.assertEqual(store.attempt_count, 1)
            rows = [json.loads(s) for s in (Path(folder) / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([r["status"] for r in rows], ["started", "completed", "cache_reference"])


class FeedbackIsolationTests(unittest.TestCase):
    def test_interrupted_state_replacement_preserves_the_previous_valid_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            save_json(path, {"status": "started"})
            with patch.object(Path, "replace", side_effect=OSError("fixture interrupted replace")):
                with self.assertRaisesRegex(OSError, "interrupted replace"):
                    save_json(path, {"status": "completed"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "started"})

    def test_stale_mailbox_response_cannot_become_a_new_model_proposal(self):
        with tempfile.TemporaryDirectory() as folder:
            backend = SSHMailbox("fixture-host", "/fixture", folder, "protocol-sha", "fresh-run")
            old = {"protocol_sha256": "protocol-sha", "call_index": 0, "request_sha256": "old-request",
                   "status": "completed", "raw": "old reply"}
            outputs = [subprocess.CompletedProcess([], 0, b"", b""),
                       subprocess.CompletedProcess([], 0, b"", b""),
                       subprocess.CompletedProcess([], 0, json.dumps(old).encode(), b"")]
            with patch("subprocess.run", side_effect=outputs):
                with self.assertRaisesRegex(ValueError, "response identity mismatch"):
                    backend.generate(0, [{"role": "user", "content": "new prompt"}], 1)

    def test_worker_reuses_only_verified_completed_calls(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            request = {"call_index": 0, "protocol_sha256": "p", "run_id": "run", "messages": []}
            path = folder / "request-00.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            response = {"protocol_sha256": "p", "call_index": 0, "request_sha256": sha_file(path), "status": "completed"}
            (folder / "response-00.json").write_text(json.dumps(response), encoding="utf-8")
            self.assertEqual(completed_request(folder, 0, "p")["run_id"], "run")
            (folder / "started-01.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "started-only"):
                completed_request(folder, 1, "p")

    def test_no_feedback_prompt_does_not_reveal_outcomes_or_retention(self):
        protocol = {"selection": {"rule": "fixed utility"}}
        n = build_messages(protocol, BASE_EXPRESSION, {"raw": "previous proposal", "syntax_status": "valid"})
        f = build_messages(protocol, BASE_EXPRESSION, feedback={"actual_wait_s": 123.45, "retained": True})
        self.assertNotIn("actual_development_feedback", json.loads(n[1]["content"]))
        self.assertNotIn("123.45", str(n))
        self.assertIn("123.45", str(f))
        self.assertNotIn("confirmation_outcomes", str(n))
        self.assertNotIn("fault_start_s", str(n))

    def test_confirmation_requires_a_frozen_selection_and_then_proposals_stop(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            study = FeedbackStudy(root / "configs/feedback-study.json", Path(folder))
            # Never use real confirmation seeds in a red-before-green test.
            placeholder = {"case_id": "confirmation-fixture", "phase": "confirmation", "spec": {
                "seed": 0, "scenario": "healthy", "duration_s": 900, "fault_start_s": 335,
                "noise_c": .2, "estimator": "nominal", "control": "feedback", "resources": "provisioned"}}
            with self.assertRaisesRegex(RuntimeError, "Selection not frozen"):
                study.evaluate_group("early", BASE_EXPRESSION, [placeholder])
            selected = {name: {"expression": BASE_EXPRESSION, "source": "R"} for name in ["T", "R", "S", "N", "F"]}
            study.freeze_selection(selected)
            with self.assertRaisesRegex(RuntimeError, "no further proposals"):
                study.model_attempt("F", 0, BASE_EXPRESSION, None, None, None)
            changed = {**selected, "F": {"expression": "10*risk_delay", "source": "F1"}}
            with self.assertRaisesRegex(ValueError, "Selection cannot change"):
                study.freeze_selection(changed)

    def test_safety_and_misses_have_priority_over_small_cost_savings(self):
        def record(missed=0, wait=50, travel=1000, completed=100, violation=0):
            return {"metrics": {"missed_segments": missed, "consequence_weighted_censored_delay_s": wait,
                "travel_m": travel, "completed_inspections": completed, "service_s": 1000,
                "current_round_unfinished_obligations": 0, "reordered_plans": 1,
                "tasks_violating_exact_gap": violation, "numeric_scoring_failures": 0,
                "invalid_assignments": 0, "duplicate_reservations": 0}}
        parent = [record()]
        self.assertFalse(retain(parent, [record(wait=55, travel=900, completed=110)]))
        self.assertTrue(retain(parent, [record(wait=48, travel=1100)]))
        self.assertFalse(retain(parent, [record(wait=0, travel=0, missed=1)]))
        self.assertFalse(retain(parent, [record(wait=0, travel=0, violation=1)]))

    def test_completed_study_resumes_without_new_proposals_or_evaluations(self):
        root = Path(__file__).resolve().parents[1]
        protocol = json.loads((root / "configs/feedback-study.json").read_text(encoding="utf-8"))
        # These synthetic healthy fixtures never use any research confirmation
        # seed. Equal conditions intentionally exercise alias/caching behavior.
        for phase, seed in (("development", 0), ("confirmation", 1)):
            for case in protocol[phase]:
                case["spec"].update(seed=seed, scenario="healthy", duration_s=900)
        class FixtureBackend:
            calls = 0
            def generate(self, index, messages, seed):
                self.calls += 1
                rules = ["2*risk_delay + 0.2*deadline_pressure + 0.05*travel_cost",
                         "3*risk_delay + 0.2*deadline_pressure + 0.05*travel_cost",
                         "4*risk_delay + 0.2*deadline_pressure + 0.05*travel_cost",
                         "5*risk_delay + 0.2*deadline_pressure + 0.05*travel_cost"]
                return {"status": "completed", "raw": json.dumps({"score_expression": rules[index],
                        "mechanism": "Deterministic unit fixture, not a real model call"})}
        backend = FixtureBackend()
        with tempfile.TemporaryDirectory() as folder:
            protocol_path = Path(folder) / "protocol-input.json"
            protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
            study = FeedbackStudy(protocol_path, Path(folder) / "run")
            result = study.run(backend)
            attempts = study.store.attempt_count
            self.assertEqual(backend.calls, 4)
            self.assertEqual(result["status"], "completed")
            resumed = FeedbackStudy(protocol_path, Path(folder) / "run")
            resumed.run(backend)
            self.assertEqual(backend.calls, 4)
            self.assertEqual(resumed.store.attempt_count, attempts)
            self.assertEqual(len(resumed.labels), 13)


if __name__ == "__main__":
    unittest.main()
