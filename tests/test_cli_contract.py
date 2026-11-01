"""The public entry point must not mislabel fixture runs or accept unsafe input."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from patrol_rsi.cli import compare_candidate, frozen_estimator, load_demo, run_example, status


class EntryPointTests(unittest.TestCase):
    def test_status_keeps_engineering_and_research_separate(self):
        self.assertEqual(status()["新研究实验"], "NOT_RUN")
        self.assertEqual(status()["默认策略"], "Tour")

    def test_missing_checkpoint_never_becomes_a_neural_demo(self):
        predictor, info = frozen_estimator(None, None)
        self.assertIsNone(predictor)
        self.assertFalse(info["neural_inference"])
        with self.assertRaises(ValueError):
            frozen_estimator(None, "fake-sha")

    def test_episode_horizon_and_fault_duration_cannot_be_confused(self):
        args = SimpleNamespace(config=None, cvae_checkpoint=None, cvae_sha256=None)
        internal, _, _ = load_demo(args)
        self.assertEqual(internal["duration_s"], 180)
        self.assertEqual(internal["fault_start_s"], 335)
        config = json.loads((Path(__file__).resolve().parents[1] / "configs/demo.json").read_text(encoding="utf-8"))
        config["spec"]["episode_horizon_s"] = 180
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid-horizon.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            args.config = str(path)
            with self.assertRaisesRegex(ValueError, "1800-second"):
                load_demo(args)

    def test_invalid_proposal_is_recorded_before_any_simulation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = root / "invalid.json"
            candidate.write_text('{"source_weights": [1, 1, 1, 1]}', encoding="utf-8")
            args = SimpleNamespace(config=None, cvae_checkpoint=None, cvae_sha256=None,
                                   candidate=str(candidate), output=str(root / "run"))
            with self.assertRaises(ValueError):
                run_example(args, proposal=True)
            receipt = json.loads((root / "run/attempts.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["attempts"], [])
            self.assertEqual(receipt["LLM_calls"], 0)

    def test_example_cannot_claim_savings_from_doing_less_work(self):
        p = {"metrics": {"missed_segments": 1, "consequence_weighted_censored_delay_s": 30.,
             "travel_m": 100., "completed_inspections": 50, "tasks_violating_exact_gap": 0,
             "numeric_scoring_failures": 0}}
        c = {"metrics": dict(p["metrics"], travel_m=90., completed_inspections=49)}
        result = compare_candidate(p, c)
        self.assertEqual(result["illustrative_decision"], "keep_parent")
        self.assertEqual(result["formal_default"], "Tour")


if __name__ == "__main__":
    unittest.main()
