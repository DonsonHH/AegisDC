import unittest
import numpy as np

from patrol_rsi.facility import FacilityConfig
from patrol_rsi.facility_observation import inspection_tasks
from patrol_rsi.measurement_state import MeasurementState


def packet(t):
    return {'time_s': float(t), 'temperature_indices': np.array([0]), 'temperature_c': np.array([50.]),
        'public_requested_it_kw': np.full(128, 200.), 'public_delivered_it_kw': np.full(128, 200.),
        'pod_pump_command': np.ones(16), 'primary_supply_c': 25., 'secondary_supply_c': np.full(16, 35.),
        'flow_pod_indices': np.array([0]), 'flow_pod_kg_s': np.array([48.])}


def event(value, t=495.):
    return {'agent': 0, 'task': 1, 'kind': 'thermal', 'index': 1, 'time_s': t,
        'role': 'thermal', 'calibrated': True, 'access': 'external_sensing',
        'measurement': {'rack_index': 1, 'temperature_c': value}, 'alarm': value > 65.}


class StateIsolationTests(unittest.TestCase):
    def make(self):
        c = FacilityConfig()
        return MeasurementState(c, inspection_tasks(c), lambda x: np.full(128, 80.))

    def test_masked_measurement_cannot_change_frames_alarm_or_policy_state(self):
        a, b, visible = self.make(), self.make(), self.make()
        for t in range(5, 496, 5):
            ea = [event(50.)] if t == 495 else []
            eb = [event(95.)] if t == 495 else []
            a.advance(packet(t), ea, blocked=(0, 1, 495.))
            b.advance(packet(t), eb, blocked=(0, 1, 495.))
            visible.advance(packet(t), ea)
        self.assertEqual(a.view(), b.view())
        self.assertNotIn(1, a.qualified)
        self.assertEqual(visible.qualified[1]['value'], 50.)
        self.assertAlmostEqual(visible.temperatures()[1], 50.)
        self.assertNotEqual(a.temperatures()[1], visible.temperatures()[1])
        self.assertEqual(visible.frame_times[-4:], [390., 420., 450., 480.])
        frozen = [v.copy() for v in visible.frames]
        visible.advance(packet(500), [])
        for old, new in zip(frozen, visible.frames):
            np.testing.assert_array_equal(old, new)
        visible.advance(packet(505), [])
        visible.advance(packet(510), [])
        self.assertEqual(visible.frame_times[-4:], [420., 450., 480., 510.])
        self.assertLess(visible.frames[-1][1, 0], 1.)

    def test_flow_reference_affects_future_related_thermal_estimate_not_past(self):
        a, b = self.make(), self.make()
        e = dict(agent=13, task=132, kind='cooling', index=1, time_s=5.,
            role='cooling', calibrated=True, access='external_sensing',
            measurement={'pod_index': 1, 'pod_flow_kg_s': 24.}, alarm=True)
        a.advance(packet(5), [e])
        b.advance(packet(5), [e], blocked=(13, 132, 5.))
        self.assertEqual(a.view()['nominal_temperature_c'], b.view()['nominal_temperature_c'])
        self.assertGreater(a.project_temperatures(60)[8], b.project_temperatures(60)[8])
        self.assertEqual(a.last_update['visible_references'][0]['prior_same_time_nominal'], 48.)
        self.assertEqual(a.last_update['visible_references'][0]['residual'], -24.)

    def test_real_flow_update_can_change_candidate_value_and_next_task(self):
        from patrol_rsi.measurement_workflow import MeasurementWorkflow, rank_candidates, choose_followup
        a, b = self.make(), self.make()
        public = packet(5)
        public['temperature_indices'] = np.array([8,16])
        public['temperature_c'] = np.array([80.,82.])
        flow = dict(agent=13, task=132, kind='cooling', index=1, time_s=5., role='cooling',
                    calibrated=True, access='external_sensing', measurement={'pod_index': 1, 'pod_flow_kg_s': 24.}, alarm=True)
        a.advance(public, [flow])
        b.advance(public, [flow], blocked=(13,132,5.))
        geometry = [dict(task=j, kind='thermal', pod=j//8, completion_cost_s=30.,
                         lead_s=100., shift_s=10., weight=1.) for j in (8,16)]
        old = rank_candidates(b, geometry, MeasurementWorkflow())
        new = rank_candidates(a, geometry, MeasurementWorkflow())
        self.assertEqual(choose_followup(old, MeasurementWorkflow(), None)['task'],16)
        self.assertEqual(choose_followup(new, MeasurementWorkflow(), True)['task'],8)


if __name__ == '__main__':
    unittest.main()
