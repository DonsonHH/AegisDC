import unittest
import numpy as np

from patrol_rsi.facility import CoupledFacility, FacilityConfig
from patrol_rsi.process import phased_trace
from patrol_rsi.risk_response import ResponseTask, run_response
from patrol_rsi.reorder_execution import run_reorder
from patrol_rsi.event_validation import paired, bootstrap_mean

SPEC = dict(seed=0, scenario='aux_feeder_loss+cdu_fouling', duration_s=180,
            fault_start_s=335, noise_c=.2, estimator='nominal', control='feedback', resources='provisioned')


class EventValidationTests(unittest.TestCase):
    def test_pairing_reports_gains_losses_and_rejects_different_processes(self):
        import copy
        a = {'process_sha256':'same','anomaly_intervals':[
            dict(task_id='a',onset_s=0,end_s=10,detected=True),
            dict(task_id='b',onset_s=0,end_s=10,detected=False)],
            'metrics':dict(travel_m=100,service_s=10,completed_inspections=10)}
        b = copy.deepcopy(a)
        for row in b['anomaly_intervals']:row['detected'] = not row['detected']
        result = paired(a,b)
        self.assertEqual((result['gained'],result['lost'],result['net']),(1,1,0))
        b['process_sha256']='different'
        with self.assertRaises(ValueError):paired(a,b)
        self.assertEqual(bootstrap_mean([1]*12,5)['percentile95'],[1.,1.])

    def test_synthetic_false_cue_does_not_change_physics_or_measurement(self):
        clean = dict(SPEC, scenario='healthy')
        noisy = dict(clean, public_risk_pulses=[dict(task=0,start_s=10,end_s=40,risk=.5)])
        a, b = ResponseTask(clean), ResponseTask(noisy)
        self.assertEqual(a.trace.fingerprint, b.trace.fingerprint)
        b.clock = 10
        b.observe_response_risk()
        self.assertEqual(b.risk_episodes.pending[0]['initial_public_risk'], .5)
        self.assertEqual(a.trace.measurement(a.tasks[0],1), b.trace.measurement(b.tasks[0],1))

    def test_every_rack_is_selectable_without_changing_load_realization(self):
        baseline = CoupledFacility(seed=7)
        for rack in range(128):
            plant = CoupledFacility(FacilityConfig(fault_rack=rack), seed=7, scenario='coldplate_fouling')
            np.testing.assert_array_equal(plant.rated_kw, baseline.rated_kw)
            np.testing.assert_array_equal(plant._phase, baseline._phase)
            self.assertEqual(np.flatnonzero(plant._faults(300)['coldplate'] < 1).tolist(), [rack])
        plant = CoupledFacility(FacilityConfig(fault_rack=77), seed=7, scenario='aux_feeder_loss')
        self.assertEqual(np.flatnonzero(plant._faults(300)['aux_feed'] < 1).tolist(), [9])

    def test_bad_locations_fail_and_trace_cache_separates_locations(self):
        for rack in [-1, 128, True, 2.5]:
            with self.assertRaises(ValueError):
                FacilityConfig(fault_rack=rack)
        a = phased_trace(0, 'coldplate_fouling', 180, 335, 0)
        b = phased_trace(0, 'coldplate_fouling', 180, 335, 1)
        self.assertNotEqual(a.fingerprint, b.fingerprint)
        self.assertIs(a, phased_trace(0, 'coldplate_fouling', 180, 335, 0))

    def test_zero_extra_budget_reproduces_tour_and_positive_cap_is_enforced(self):
        tour, _ = run_reorder(SPEC, None, {'method':'T'})
        zero, _ = run_response(SPEC, extra_visit_budget=0)
        self.assertEqual(tour['action_log'], zero['action_log'])
        limited, _ = run_response(SPEC, extra_visit_budget=1)
        self.assertEqual(limited['response_config']['extra_dispatched'], 1)
        self.assertEqual(limited['metrics']['tasks_violating_exact_gap'], 0)

    def test_permutation_preserves_profession_owner_and_values_but_moves_targets(self):
        env = ResponseTask(SPEC, risk_permutation_seed=123)
        mapping = env.risk_source_for_target
        self.assertEqual(sorted(mapping.tolist()), list(range(len(env.tasks))))
        for agent in env.agents:
            self.assertEqual(set(mapping[agent['tour']]), set(agent['tour']))
            if len(agent['tour']) > 1:
                self.assertTrue(all(mapping[j] != j for j in agent['tour']))
        risks = np.zeros(len(env.tasks)); risks[0] = .7
        env.public_risk = lambda: (risks, np.zeros(128))
        env.clock = 10
        env.observe_response_risk()
        event = env.risk_episodes.events[-1]
        self.assertEqual(event['signal_source_task'], 0)
        self.assertNotEqual(event['task'], 0)
        self.assertEqual(event['initial_public_risk'], .7)
        record, _ = run_response(SPEC, extra_visit_budget=2, risk_permutation_seed=123)
        self.assertLessEqual(record['response_config']['extra_dispatched'], 2)
        self.assertEqual(record['metrics']['tasks_violating_exact_gap'], 0)


if __name__ == '__main__':
    unittest.main()
