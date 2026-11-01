import unittest
import numpy as np

from patrol_rsi.coverage_plan import ReturnPlan, InfeasibleCoverage, exact_task_gaps
from patrol_rsi.facility_observation import InspectionTask
from patrol_rsi.inspection_contracts import ServiceEvidence, assess_capability


class LineGraph:
    def path(self, a, b):
        return abs(a[0] - b[0]), (a, b)


def small_plan(deadline=100):
    tasks = [InspectionTask(str(i), 'thermal', i, 'thermal', 10., (i * 10., 0.)) for i in range(3)]
    return ReturnPlan(LineGraph(), tasks, [0, 1, 2], np.full(3, deadline)), tasks


class ReturnCertificateTests(unittest.TestCase):
    def test_checks_entire_return_round_not_only_candidate(self):
        plan, _ = small_plan()
        last = np.array([40., 0., 0.])
        result = plan.check(55, (0., 0.), last, 1, candidate=0)
        self.assertFalse(result['ok'])
        self.assertEqual(result['failed_task'], 2)
        self.assertTrue(plan.check(55, (0., 0.), last, 1, candidate=1)['ok'])

    def test_exact_deadline_boundary_and_cursor_update(self):
        plan, _ = small_plan()
        last = np.array([40., 0., 0.])
        accepted = plan.check(50, (0., 0.), last, 1, candidate=0)
        self.assertTrue(accepted['ok'])
        self.assertEqual(accepted['minimum_projected_slack_s'], 0)
        self.assertEqual(accepted['cursor_after'], 1)
        next_task = plan.check(50, (0., 0.), last, 1, candidate=1)
        self.assertEqual(next_task['cursor_after'], 2)

    def test_rejects_long_cycle_and_initial_backlog(self):
        with self.assertRaises(InfeasibleCoverage):
            small_plan(60)
        plan, _ = small_plan()
        self.assertFalse(plan.check(95, (0., 0.), np.full(3, -1.), 0)['ok'])
        self.assertTrue(plan.check(5, (0., 0.), np.full(3, -1.), 0)['ok'])
        with self.assertRaises(ValueError):
            plan.check(5, (0., 0.), np.full(3, -1.), 0, candidate=99)

    def test_exact_gaps_include_head_and_episode_tail(self):
        _, tasks = small_plan()
        events = [{'task': 0, 'time_s': 15.}, {'task': 0, 'time_s': 255.}]
        maxima, records = exact_task_gaps(tasks, events, horizon=300)
        self.assertEqual(maxima[0], 240)
        self.assertEqual(maxima[1], 300)
        self.assertEqual(records[0]['completion_times_s'], [15, 255])




class CapabilityTests(unittest.TestCase):
    def packet(self, clock, delivered):
        return {'time_s': clock, 'public_requested_it_kw': np.full(8, 100.),
                'public_delivered_it_kw': np.full(8, delivered)}

    def test_power_gap_not_voltage_current_or_unvalidated_temperature(self):
        self.assertFalse(assess_capability('ac_voltage', 'calibrated_voltage_measurement',
            calibrated=True, channel_available=True)['completes_task'])
        self.assertFalse(assess_capability('branch_current', 'calibrated_requested_and_delivered_power',
            calibrated=True, channel_available=True)['completes_task'])
        self.assertFalse(assess_capability('thermal_reference', 'apparent_ir_reference',
            calibrated=True, channel_available=True)['completes_task'])
        self.assertFalse(assess_capability('thermal_reference', 'validated_remote_temperature',
            calibrated=False, channel_available=True)['completes_task'])
        self.assertTrue(assess_capability('thermal_reference', 'validated_remote_temperature',
            calibrated=True, channel_available=True)['completes_task'])

    def test_confirmation_persistence_and_recovery_are_distinct(self):
        monitor = ServiceEvidence(1, calibrated=True)
        self.assertEqual(monitor.update(self.packet(5, 50)), [])
        self.assertEqual(monitor.update(self.packet(10, 50)), [])
        first = monitor.update(self.packet(15, 50))
        self.assertEqual(first[0]['kind'], 'new_measured_alert')
        self.assertFalse(first[0]['root_cause_diagnosed'])
        for t in range(20, 80, 5):
            monitor.update(self.packet(t, 50))
        self.assertEqual(monitor.events[-1]['kind'], 'persistent_recheck')
        for t in (80, 85, 90):
            monitor.update(self.packet(t, 100))
        self.assertEqual(monitor.events[-1]['kind'], 'recovery_confirmation')

    def test_unknown_calibration_missing_channels_and_time_gaps(self):
        monitor = ServiceEvidence(1)
        for t in (5, 10, 15):
            self.assertEqual(monitor.update(self.packet(t, 0)), [])
        self.assertEqual(monitor.events, [])
        with self.assertRaises(ValueError):
            monitor.update(self.packet(25, 50))
        with self.assertRaises(ValueError):
            ServiceEvidence(1, calibrated=True).update(
                {'time_s': 5, 'public_requested_it_kw': np.full(4, 100), 'public_delivered_it_kw': np.zeros(4)})


if __name__ == '__main__':
    unittest.main()
