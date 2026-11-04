"""Independent non-event amplitude counterexamples; no physical simulation."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from numerical_alignment_v3 import epoch_compare
from test_numerical_alignment import jumps, LIMITS


class NumericalAmplitudeGuardTests(unittest.TestCase):
    def case(self, *, closed=False, key='condenser_W', baseline=0., jump=2000000., peak=5000000.):
        unit = math.ulp(1.)
        extra = [1.+8*unit] if closed else [1.+4*unit, 1.+8*unit]
        actual = jumps([1.], [jump], extra_times=extra)
        reference = jumps([1.+8*unit], [jump])
        actual['series'] = {key: [baseline, jump, peak, jump] if closed else [baseline, jump, peak, jump, jump]}
        reference['series'] = {key: [baseline, jump, jump]}
        return actual, reference

    def test_open_interval_post_event_five_MW_peak_is_retained(self):
        actual, reference = self.case()
        result = epoch_compare(actual, reference, LIMITS)
        self.assertGreaterEqual(result['maximum_absolute_series_error']['condenser_W'], 3000000.)
        self.assertFalse(result['within_predeclared_limits'])

    def test_closed_high_endpoint_five_MW_right_value_cannot_disappear_until_three_seconds(self):
        actual, reference = self.case(closed=True)
        result = epoch_compare(actual, reference, LIMITS)
        self.assertGreaterEqual(result['maximum_absolute_series_error']['condenser_W'], 3000000.)
        self.assertFalse(result['within_predeclared_limits'])

    def test_continuous_temperature_open_peak_is_retained(self):
        actual, reference = self.case(key='solid_K', baseline=300., jump=300., peak=300.1)
        result = epoch_compare(actual, reference, LIMITS)
        self.assertAlmostEqual(result['maximum_absolute_series_error']['solid_K'], .1, delta=1e-12)
        self.assertFalse(result['within_predeclared_limits'])

    def test_continuous_temperature_closed_endpoint_is_retained(self):
        actual, reference = self.case(closed=True, key='solid_K', baseline=300., jump=300., peak=300.1)
        result = epoch_compare(actual, reference, LIMITS)
        self.assertAlmostEqual(result['maximum_absolute_series_error']['solid_K'], .1, delta=1e-12)
        self.assertFalse(result['within_predeclared_limits'])

    def test_pressure_non_event_two_kPa_peak_is_retained(self):
        actual, reference = self.case(key='pressure_Pa', baseline=800000., jump=800000., peak=802000.)
        result = epoch_compare(actual, reference, LIMITS)
        self.assertGreaterEqual(result['maximum_absolute_series_error']['pressure_Pa'], 2000.)
        self.assertFalse(result['within_predeclared_limits'])

    def test_a_genuine_post_event_value_between_the_two_jump_limits_is_retained(self):
        actual, reference = self.case(peak=1000000.)
        result = epoch_compare(actual, reference, LIMITS)
        self.assertGreaterEqual(result['maximum_absolute_series_error']['condenser_W'], 1000000.)
        self.assertFalse(result['within_predeclared_limits'])

    def test_constant_post_event_non_event_rows_do_not_create_a_spike(self):
        actual, reference = self.case(peak=2000000.)
        result = epoch_compare(actual, reference, LIMITS)
        self.assertEqual(result['maximum_absolute_series_error']['condenser_W'], 0.)
        self.assertTrue(result['within_predeclared_limits'])

    def test_an_existing_larger_outside_window_error_is_not_reduced(self):
        unit=math.ulp(1.)
        actual=jumps([1.],[0.],extra_times=[1.+8*unit,2.])
        reference=jumps([1.+8*unit],[0.],extra_times=[2.])
        actual['series']={'solid_K':[300.,300.,300.1,301.,300.]}
        reference['series']={'solid_K':[300.,300.,300.,300.]}
        result=epoch_compare(actual,reference,LIMITS)
        self.assertAlmostEqual(result['maximum_absolute_series_error']['solid_K'],1.)
        self.assertFalse(result['within_predeclared_limits'])

    def test_paired_event_side_error_remains_a_lower_bound(self):
        actual,reference=self.case(key='solid_K',baseline=300.,jump=300.2,peak=300.1)
        reference['series']['solid_K']=[300.,300.,300.]
        result=epoch_compare(actual,reference,LIMITS)
        self.assertAlmostEqual(result['maximum_absolute_series_error']['solid_K'],.2,delta=1e-12)
        self.assertFalse(result['within_predeclared_limits'])


if __name__ == '__main__':
    unittest.main()
