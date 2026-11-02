import unittest
from patrol_rsi.model_proposals import enforce_input_budget


class ModelInputBudgetTests(unittest.TestCase):
    def test_identical_input_cap_is_enforced_before_generation(self):
        enforce_input_budget(4096, {'max_input_tokens':4096})
        with self.assertRaises(ValueError):enforce_input_budget(4097, {'max_input_tokens':4096})
        with self.assertRaises(ValueError):enforce_input_budget(1, {'max_input_tokens':True})
        enforce_input_budget(5000, {})  # historical protocols retain their old behavior


if __name__ == '__main__':unittest.main()
