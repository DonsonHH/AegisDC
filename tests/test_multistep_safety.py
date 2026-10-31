import unittest
import numpy as np

from patrol_rsi.coverage_plan import ReturnPlan
from patrol_rsi.facility_observation import InspectionTask
from patrol_rsi.multistep_safety import certify_dispatch


class LineGraph:
    def path(self, a, b):
        return abs(a[0] - b[0]), (a, b)


class CumulativeSafetyTests(unittest.TestCase):
    def test_first_safe_does_not_authorize_unsafe_second_detour(self):
        tasks = [InspectionTask(str(i), 'thermal', i, 'thermal', 10., (i * 10., 0.)) for i in range(3)]
        plan = ReturnPlan(LineGraph(), tasks, [0, 1, 2], np.array([120., 100., 100.]))
        agent = dict(role='thermal', task=None, allowed=[0, 1, 2], position=(0., 0.))
        first = certify_dispatch(plan, agent, 0, 50., np.array([40., 0., 0.]), 1, set(), 2)
        self.assertEqual(first['candidate_finish_s'], 60.)
        with self.assertRaises(ValueError):
            certify_dispatch(plan, agent, 2, 60., np.array([60., 0., 0.]), 1, set(), 1)
        # The second candidate would have looked safe before the first detour.
        self.assertTrue(certify_dispatch(plan, agent, 2, 50., np.array([40., 0., 0.]), 1, set(), 2)['ok'])
        for changed_agent, reserved, remaining in [
            (dict(agent, role='cooling'), set(), 2), (agent, {0}, 2), (agent, set(), 0),
        ]:
            with self.assertRaises(ValueError):
                certify_dispatch(plan, changed_agent, 0, 50., np.array([40., 0., 0.]), 1, reserved, remaining)


if __name__ == '__main__':
    unittest.main()
