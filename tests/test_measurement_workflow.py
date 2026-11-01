import unittest

from patrol_rsi.measurement_workflow import MeasurementWorkflow, choose_first, choose_followup
from patrol_rsi.multistep_proposal import compile_compact


class MeasurementWorkflowTests(unittest.TestCase):
    def test_missing_data_without_evidence_does_not_trigger_diagnostic_check(self):
        row = dict(task=1, kind='thermal', pod=0, information_age_factor=1., diagnostic_evidence=0.,
            weight=1., lead_s=60., completion_cost_s=20., affected_safe_tasks=[2], already_alarm=False)
        self.assertIsNone(choose_first([row]))
        row['diagnostic_evidence'] = .2
        self.assertEqual(choose_first([row])['task'], 1)

    def test_normal_measurement_can_return_to_tour_and_model_edit_is_bounded(self):
        row = dict(task=2, value=-.1, rank=1, already_alarm=False)
        self.assertIsNone(choose_followup([row], MeasurementWorkflow(), None))
        row['value'] = .1
        self.assertEqual(choose_followup([row], MeasurementWorkflow(), None)['task'], 2)
        self.assertIsNone(choose_followup([row], MeasurementWorkflow(normal_followup='return_tour'), False))
        child, envelope = compile_compact('{"changes":{"dependency_evidence":"own_only"},"mechanism":"Use direct evidence."}', MeasurementWorkflow())
        self.assertEqual(child.dependency_evidence, 'own_only')
        with self.assertRaises(ValueError):
            compile_compact('{"changes":{"K":3},"mechanism":"More budget"}', MeasurementWorkflow())
