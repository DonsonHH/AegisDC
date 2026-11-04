"""Algebraic reader diagnostics only; never full-facility research evidence."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from numerical_refinement_checks import epoch_compare

LIMITS = dict(temperature_K=.05, pressure_Pa=1000, heat_W=25000,
              service_deficit_time_s=.001, unserved_service_unit_s=.001,
              resource_time_s=.001, switch_time_s=.001)


def jumps(times, values, identities=None, extra_times=()):
    identities = identities or [['reserve_transition', 'ups', 'supplying']]
    points = sorted(set([0., 3., *times, *extra_times]))
    return dict(times=points, series={'condenser_W': [next((value for t, value in reversed(list(zip(times, values))) if t <= x), 0.) for x in points]},
                events=[dict(identity=identity, time_s=t) for identity, t in zip(identities, times)],
                metrics={'service_deficit_time_s': 0.}, literal_checks_pass=True)


class NumericalEpochAlignmentTests(unittest.TestCase):
    def test_eight_ulp_same_epoch_jump_has_zero_epoch_error_and_retains_causal_raw_peak(self):
        unit = math.ulp(1.)
        actual = jumps([1.], [2000000.], extra_times=[1. - 4 * unit])
        reference = jumps([1. + 8 * unit], [2000000.])
        compared = epoch_compare(actual, reference, LIMITS)
        self.assertEqual(compared['maximum_absolute_series_error']['condenser_W'], 0.)
        self.assertEqual(compared['raw_causal']['maximum_absolute_series_error']['condenser_W'], 2000000.)
        self.assertEqual(compared['alignment']['changed_epoch_groups'], 1)
        self.assertEqual(compared['alignment']['total_window_duration_s'], 8 * unit)
        self.assertEqual(compared['maximum_switch_time_error_s'], 8 * unit)
        self.assertEqual(compared['alignment']['excluded_union_points'], 2)

    def test_nine_ulp_jump_is_not_aligned_and_keeps_the_large_value_error(self):
        unit = math.ulp(1.)
        compared = epoch_compare(jumps([1.], [2000000.]), jumps([1. + 9*unit], [2000000.]), LIMITS)
        self.assertEqual(compared['alignment']['changed_epoch_groups'], 0)
        self.assertEqual(compared['maximum_absolute_series_error']['condenser_W'], 2000000.)
        self.assertFalse(compared['within_predeclared_limits'])

    def test_adjacent_eight_ulp_chain_cannot_roll_into_a_sixteen_ulp_group(self):
        unit = math.ulp(1.)
        ids = [['reserve_transition', 'cooling', 'switching'], ['reserve_transition', 'cooling', 'active']]
        compared = epoch_compare(jumps([1., 1.+8*unit], [1000000., 2000000.], ids),
                                 jumps([1.+8*unit, 1.+16*unit], [1000000., 2000000.], ids), LIMITS)
        self.assertEqual(compared['alignment']['changed_epoch_groups'], 0)
        self.assertTrue(all(row['reason'] == 'INTERVENING_DISTINCT_EVENT' for row in compared['alignment']['blocked_groups']))
        self.assertGreater(compared['maximum_absolute_series_error']['condenser_W'], 25000)

    def test_near_distinct_event_retains_its_temporary_different_right_limit(self):
        unit = math.ulp(1.)
        ids = [['reserve_transition', 'ups', 'supplying'], ['boundary', 'power', 'drop'], ['boundary', 'power', 'reset']]
        actual = jumps([1., 1.+9*unit, 1.+20*unit], [1000000., 2000000., 2000000.], ids)
        reference = jumps([1.+8*unit, 1.+9*unit, 1.+20*unit], [1000000., 3000000., 2000000.], ids)
        compared = epoch_compare(actual, reference, LIMITS)
        self.assertEqual(compared['alignment']['changed_epoch_groups'], 1)
        self.assertEqual(compared['maximum_absolute_series_error']['condenser_W'], 1000000.)
        self.assertFalse(compared['within_predeclared_limits'])

    def test_unmatched_event_identity_disables_alignment_even_with_equal_values(self):
        actual = jumps([1.], [2000000.], [['reserve_transition', 'ups', 'supplying']])
        reference = jumps([1.], [2000000.], [['reserve_transition', 'generator', 'supplying']])
        compared = epoch_compare(actual, reference, LIMITS)
        self.assertFalse(compared['event_sequence_match'])
        self.assertEqual(compared['alignment']['changed_epoch_groups'], 0)
        self.assertFalse(compared['within_predeclared_limits'])

    def test_different_mode_order_cannot_be_retimed_into_agreement(self):
        ids = [['PLC', 'protected'], ['PLC', 'normal']]
        actual = jumps([1., 2.], [0., 2000000.], ids)
        reference = jumps([1., 2.], [0., 2000000.], list(reversed(ids)))
        compared = epoch_compare(actual, reference, LIMITS)
        self.assertFalse(compared['event_sequence_match'])
        self.assertFalse(compared['within_predeclared_limits'])

    def test_a_real_second_of_switching_difference_is_not_hidden(self):
        compared = epoch_compare(jumps([1.], [2000000.]), jumps([2.], [2000000.]), LIMITS)
        self.assertEqual(compared['maximum_switch_time_error_s'], 1.)
        self.assertEqual(compared['alignment']['changed_epoch_groups'], 0)
        self.assertEqual(compared['maximum_absolute_series_error']['condenser_W'], 2000000.)
        self.assertFalse(compared['within_predeclared_limits'])


if __name__ == '__main__':
    unittest.main()
