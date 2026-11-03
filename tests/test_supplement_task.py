"""Behavior checks for the new benchmark boundary; no research results here."""
import unittest

import numpy as np

from patrol_rsi.contracts import DeniedOnlineTrace
from patrol_rsi.supplement_task import SupplementTask, from_grid, to_grid


SPEC={'seed':900001,'noise_c':.2,'scenario':'healthy','control':'feedback','resources':'provisioned',
      'fault_rack':0,'fault_start_s':150,'duration_s':180,'estimator':'nominal'}


class BenchmarkBoundaryTests(unittest.TestCase):
    def test_discrete_grid_keeps_declared_rack_identity(self):
        grid=to_grid(np.arange(128))
        self.assertEqual(grid.shape,(8,16))
        self.assertEqual(grid[0,0],0)
        self.assertEqual(grid[4,0],64)
        self.assertEqual(grid[7,15],127)
        np.testing.assert_array_equal(from_grid(grid),np.arange(128))

    def test_zero_extra_budget_keeps_routine_and_masks_event(self):
        env=SupplementTask(SPEC,'fifo');env.extra_visit_budget=0
        head=env.agents[0]['tour'][0];target=env.agents[0]['tour'][1]
        risks=np.zeros(len(env.tasks));risks[target]=1
        env.risk_episodes.observe(env.clock,risks)
        choices=env.choose()
        self.assertEqual(choices[0],head)
        ids,_,_=env.options(0,set())
        self.assertNotIn(target,ids)
        env.step(choices)
        self.assertEqual(env.extra_dispatched,0)

    def test_public_candidate_features_are_informative_without_truth_access(self):
        env=SupplementTask(SPEC,'fifo');trace=env.trace;env.trace=DeniedOnlineTrace()
        try:
            rows=[r for r in env.candidate_rows(0,set()) if r['certificate']['ok'] and r['budget_allowed']]
            features=env.public_candidate_features(0,rows,set())
            self.assertEqual(features.shape[1],21)
            self.assertAlmostEqual(float(features[0,0]),5/300,places=6)
            self.assertAlmostEqual(float(features[0,1]),10/300,places=6)
            self.assertEqual(features[0,9],1)
            self.assertEqual(features[0,17],1)
            self.assertEqual(features[0,19],1)
        finally:env.trace=trace

    def test_predictor_runs_at_every_endpoint_and_fresh_measurements_correct_it(self):
        seen=[]
        def predictor(public,nominal):
            self.assertEqual(public.shape,(57,8,16));self.assertEqual(nominal.shape,(128,))
            seen.append(public.copy());return nominal+100
        env=SupplementTask(SPEC,'tour',predictor)
        self.assertEqual(len(seen),1)
        self.assertEqual(env.current_history[0],env.state.observer.last_temperature[0])
        self.assertGreater(env.current_history[1],100)
        for _ in range(3):env.step(env.choose())
        self.assertEqual(env.clock,20)
        self.assertEqual(len(seen),4)
        self.assertEqual(env.estimator_calls,4)

    def test_external_uncommitted_action_is_rejected(self):
        env=SupplementTask(SPEC,'fifo');choices=env.choose();choices[0]=None
        with self.assertRaisesRegex(ValueError,'committed'):env.step(choices)

    def test_duplicate_choose_cannot_duplicate_dispatch_ledger(self):
        env=SupplementTask(SPEC,'fifo');choices=env.choose();count=len(env.dispatches)
        with self.assertRaisesRegex(RuntimeError,'executed'):env.choose()
        self.assertEqual(len(env.dispatches),count)
        env.step(choices)


if __name__=='__main__':unittest.main()
