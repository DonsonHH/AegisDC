"""An explanatory view must preserve execution and distinguish what was known."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from patrol_rsi.case_report import collect_case, render_html, run_explanation
from patrol_rsi.reorder_execution import run_reorder


class CaseReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "configs/coupled-example.json").read_text(encoding="utf-8"))
        cls.spec = dict(config["spec"])
        cls.spec.pop("episode_horizon_s")
        cls.spec["duration_s"] = cls.spec.pop("fault_duration_s")
        cls.progress = []
        cls.data, cls.records, cls.envs = collect_case(
            cls.spec, lambda name, status, error=None: cls.progress.append((name, status)))

    def test_readonly_capture_does_not_change_actions_or_measurements(self):
        for name, method in (("tour", "T"), ("risk", "expression")):
            plain, _ = run_reorder(self.spec, None, {"method": method})
            self.assertEqual(plain["action_log"], self.records[name]["action_log"])
            self.assertEqual(plain["inspection_events"], self.records[name]["inspection_events"])
            self.assertEqual(plain["metrics"], self.records[name]["metrics"])

    def test_frames_and_truth_are_aligned_but_unobserved_is_not_zero(self):
        self.assertEqual(self.data["offline_only"]["time_s"], list(range(5, 1801, 5)))
        for method in self.data["methods"].values():
            frames = method["public_frames"]
            self.assertEqual([f["time_s"] for f in frames], list(range(5, 1801, 5)))
            self.assertIsNone(frames[0]["last_temperature_c"][1])
            self.assertIsNone(frames[0]["remote_temperature_c"][1])
            self.assertIsNotNone(frames[0]["remote_temperature_c"][0])
            self.assertEqual(len(frames[0]["thermal_risk"]), 128)
            self.assertNotIn("offline_only", frames[0])
        self.assertEqual(self.progress, [("tour", "started"), ("tour", "completed"),
                                         ("risk", "started"), ("risk", "completed")])

    def test_actual_completion_claims_match_the_obligation_ledger(self):
        for name, method in self.data["methods"].items():
            self.assertEqual(method["metrics"], self.records[name]["metrics"])
            actual = {(e["agent"], e["task_id"], e["time_s"])
                      for e in self.records[name]["inspection_events"]}
            for decision in method["decisions"]:
                for row in decision["affected"]:
                    when = row["actual_completion_s"]
                    if when is not None:
                        self.assertIn((decision["agent"], row["task"], when), actual)
                        # Only the submitted segment is committed. Later local
                        # plans may change the predicted baseline continuation.
                        if row["task"] in decision["selected"]:
                            self.assertAlmostEqual(when, row["selected_prediction_s"])
            self.assertEqual(method["metrics"]["tasks_violating_exact_gap"], 0)
        np.testing.assert_array_equal(self.envs["tour"].trace.arrays["rack_temperature_c"],
                                      self.envs["risk"].trace.arrays["rack_temperature_c"])

    def test_html_is_self_contained_and_does_not_execute_data_as_markup(self):
        html = render_html({"example": "</script><script>alert(1)</script>"})
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertIn("\\u003c/script>", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("__CASE_DATA__", html)
        self.assertFalse(self.data["neural_inference"])
        self.assertEqual(self.data["LLM_calls"], 0)

    def test_other_scenarios_cannot_be_mislabeled_as_auxiliary_power_loss(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report"
            args = SimpleNamespace(config=str(root / "configs/demo.json"), output=str(output))
            with self.assertRaisesRegex(ValueError, "aux_feeder_loss only"):
                run_explanation(args)
            self.assertFalse(output.exists())

    def test_failed_execution_is_counted_without_claiming_a_second_run(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report"
            args = SimpleNamespace(config=None, output=str(output))
            with patch("patrol_rsi.case_report.run_observed", side_effect=RuntimeError("fixture failure")):
                with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                    run_explanation(args)
            receipt = json.loads((output / "attempts.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(len(receipt["attempts"]), 1)
            self.assertEqual(receipt["attempts"][0]["status"], "failed")
            self.assertEqual(receipt["attempts"][0]["name"], "tour")


if __name__ == "__main__":
    unittest.main()
