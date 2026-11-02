"""Public experiment contracts: counted execution, isolation, and frozen testing."""
import json
from pathlib import Path
import tempfile
from copy import deepcopy
import unittest

from patrol_rsi.feedback_study import EvaluationStore, FeedbackStudy, build_messages, retain
from patrol_rsi.local_score import BASE_EXPRESSION


class EvaluationBudgetTests(unittest.TestCase):
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
