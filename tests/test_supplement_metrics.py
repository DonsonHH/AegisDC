import unittest

import numpy as np

from patrol_rsi.supplement_metrics import temperature_metrics, weighted_age


class SupplementalMetricTests(unittest.TestCase):
    def test_weighted_error_and_r_squared_have_literal_reference_values(self):
        result = temperature_metrics([[1, 3]], [[0, 2]], [1, 3], [[False, True]])
        self.assertEqual(result['all'], {'count': 2, 'rmse_c': 1., 'weighted_rmse_c': 1., 'r2': 0.})
        self.assertEqual(result['not_fresh']['count'], 1)
        self.assertIsNone(result['not_fresh']['r2'])

    def test_weighted_error_uses_rack_weight_on_every_endpoint(self):
        result = temperature_metrics([[2, 2], [0, 2]], [[0, 2], [0, 2]], [3, 1], np.zeros((2, 2), bool))
        self.assertAlmostEqual(result['all']['rmse_c'], 1.)
        self.assertAlmostEqual(result['all']['weighted_rmse_c'], np.sqrt(1.5))

    def test_constant_target_and_empty_not_fresh_are_na(self):
        result = temperature_metrics([[1, 1]], [[1, 1]], [1, 1], [[True, True]])
        self.assertIsNone(result['all']['r2'])
        self.assertEqual(result['not_fresh'], {'count': 0, 'rmse_c': None, 'weighted_rmse_c': None, 'r2': None})

    def test_age_includes_both_boundary_intervals(self):
        record = {'asset_weights': [1], 'deadlines_s': [300],
                  'exact_task_gaps': [{'task': 0, 'completion_times_s': [300, 600, 900, 1200, 1500]}]}
        self.assertAlmostEqual(weighted_age(record), .5)

    def test_misaligned_or_nonfinite_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            temperature_metrics([[float('nan')]], [[1]], [1], [[False]])
        with self.assertRaises(ValueError):
            temperature_metrics([[1, 2]], [[1]], [1], [[False]])


if __name__ == '__main__':
    unittest.main()
