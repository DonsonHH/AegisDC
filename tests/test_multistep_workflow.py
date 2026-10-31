import unittest

from patrol_rsi.multistep_workflow import Workflow, compile_edit, select_follow_up
from patrol_rsi.multistep_execution import WorkflowRuntime, measurement_information


class WorkflowContractTests(unittest.TestCase):
    def test_model_edit_changes_executable_branch_and_cannot_change_budget(self):
        parent = Workflow()
        child = compile_edit(parent, {
            'schema': 'workflow-edit-v1', 'parent_sha256': parent.sha256,
            'changes': {'after_normal': 'return_tour'},
            'mechanism': 'After a normal reference, preserve tour obligations.',
        })
        self.assertNotEqual(child.sha256, parent.sha256)
        self.assertEqual(child.after_normal, 'return_tour')
        with self.assertRaises(ValueError):
            compile_edit(parent, {
                'schema': 'workflow-edit-v1', 'parent_sha256': parent.sha256,
                'changes': {'budget': 3}, 'mechanism': 'Increase budget',
            })

    def test_new_measurement_changes_which_profession_is_selected(self):
        candidates = [
            dict(task=5, pod=2, kind='cooling', rank_signal=0., weight=1.,
                 lead_s=30., eta_ratio=.1, age_ratio=.5, already_alarm=False),
            dict(task=8, pod=3, kind='thermal', rank_signal=.5, weight=1.,
                 lead_s=80., eta_ratio=.1, age_ratio=.7, already_alarm=False),
        ]
        event = dict(task=2, pod=2, kind='thermal', alarm=True, time_s=100.)
        self.assertEqual(select_follow_up(Workflow(), candidates, event, 100.)['task'], 5)
        self.assertEqual(select_follow_up(Workflow(), candidates, dict(event, alarm=False), 100.)['task'], 8)
        self.assertIsNone(select_follow_up(Workflow(after_normal='return_tour'), candidates,
                                         dict(event, alarm=False), 100.))
        with self.assertRaises(ValueError):
            select_follow_up(Workflow(), candidates, event, 95.)

    def test_pending_reference_cannot_trigger_a_second_check(self):
        runtime = WorkflowRuntime(Workflow())
        choices = runtime.choose({'time_s': 100.}, [], {1: 3}, [], 1, True)
        self.assertEqual(choices, {1: 3})
        self.assertTrue(runtime.frames[-1]['waiting_for_measurement'])
        self.assertIsNone(runtime.frames[-1]['selected'])

    def test_qualified_flow_can_duplicate_an_existing_remote_quantity(self):
        before = dict(kind='cooling', pod=2, flow={'available': True, 'time_s': 90., 'value': 30.},
                      qualified={'available': False})
        event = dict(index=2, time_s=100.)
        info = measurement_information(before, event, dict(time_s=100., flow_pod_indices=[2], flow_pod_kg_s=[31.]))
        self.assertTrue(info['first_qualified_for_task'])
        self.assertTrue(info['contemporaneous_remote_same_quantity'])
        self.assertEqual(info['remote_time_s'], 100.)
        self.assertEqual(info['prior_same_quantity']['time_s'], 90.)


if __name__ == '__main__':
    unittest.main()
