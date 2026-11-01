"""Frozen execution regression after extracting the same archived core.

Golden values came from the source commit named in evidence/migration.json.
Tests need only this repository and NumPy; they never import the old checkout.
The history callback is an interface stub, never a trained CVAE substitute.
"""
import inspect
import unittest
import numpy as np

from patrol_rsi.contracts import digest, strict_json, DeniedOnlineTrace
from patrol_rsi.reorder_execution import run_reorder
from patrol_rsi.correction_execution import execute_correction
from patrol_rsi.baseline_correction import Rule
from patrol_rsi.local_score import BASE_EXPRESSION

SPEC = {'seed': 41000, 'scenario': 'aux_feeder_loss+cdu_fouling',
        'duration_s': 180, 'fault_start_s': 335, 'noise_c': .2,
        'estimator': 'nominal'}

GOLDEN = {'nominal_T': {'process_fingerprint': 'c47ad5db649813b54470c1fa8afefdffca1a3541abab201a0820f75fd2859522',
               'action_sha256': '9cdd310bfe9b4a6b477bb1beef9a2f795a61ed201b588603e20f65e5443d1086',
               'measurements_sha256': 'b9f37707932e90bae3c2743cda3766a1848efc5a860108b825555ff29c306999',
               'assignments_sha256': '6313249ec0cec1443baf5538e5b51fa4487be4b4455aadb08372125feaeead9d',
               'exact_task_gaps_sha256': 'd3f9509f3fadad472cd70f319e025b064275f025d8e40e6e0e9bac4b0c22213d',
               'metrics': {'anomaly_segments': 6,
                           'confirmed_segments': 4,
                           'missed_segments': 2,
                           'miss_rate': 0.33333333333333337,
                           'consequence_weighted_censored_delay_s': 58.50731106967116,
                           'detected_only_mean_delay_s': 71.25,
                           'false_measured_confirmations': 0,
                           'completed_inspections': 1426,
                           'final_professional_coverage': 1.0,
                           'mean_overdue_fraction': 0.0,
                           'maximum_inspection_age_s': 305.0,
                           'travel_m': 11793.399999999992,
                           'service_s': 16670.0,
                           'idle_s': 3846.599999999998,
                           'public_return': -0.24989780921039118,
                           'invalid_assignments': 0,
                           'duplicate_reservations': 0,
                           'unserved_IT_kwh': 2.118460104716565,
                           'tasks_violating_exact_gap': 0,
                           'maximum_exact_gap_s': 310.0,
                           'maximum_exact_gap_ratio': 0.8,
                           'extra_checks': 0,
                           'completed_rounds_total': 136,
                           'current_round_unfinished_obligations': 62,
                           'unfinished_committed_tasks': 32,
                           'numeric_scoring_failures': 0,
                           'estimator_calls': 0,
                           'local_plan_count': 514,
                           'reordered_plans': 0,
                           'decision_points_with_alternative': 514}},
 'nominal_R': {'process_fingerprint': 'c47ad5db649813b54470c1fa8afefdffca1a3541abab201a0820f75fd2859522',
               'action_sha256': '6f1123e4484d560e46ad627b002e815bf5a2ff74ad11b1e843392336a5aef1e4',
               'measurements_sha256': 'a5e320c617662feeff29acc8f64aedd2ac03994d6d6847ac8b2eb87fe17f49f3',
               'assignments_sha256': 'b4373a36164375b996c695ca414ebfbca1f485174f39ecf1ed1ee3a0a15e571d',
               'exact_task_gaps_sha256': 'f15b0c1e16a637bfee260f7aecbb9b6adffd6d5a6a465cf6d68d364b42aa6e43',
               'metrics': {'anomaly_segments': 6,
                           'confirmed_segments': 4,
                           'missed_segments': 2,
                           'miss_rate': 0.33333333333333337,
                           'consequence_weighted_censored_delay_s': 60.7061423377738,
                           'detected_only_mean_delay_s': 72.5,
                           'false_measured_confirmations': 0,
                           'completed_inspections': 1448,
                           'final_professional_coverage': 1.0,
                           'mean_overdue_fraction': 0.0,
                           'maximum_inspection_age_s': 305.0,
                           'travel_m': 11664.799999999996,
                           'service_s': 16890.0,
                           'idle_s': 3755.199999999999,
                           'public_return': -0.2238985286598017,
                           'invalid_assignments': 0,
                           'duplicate_reservations': 0,
                           'unserved_IT_kwh': 2.118460104716565,
                           'tasks_violating_exact_gap': 0,
                           'maximum_exact_gap_s': 310.0,
                           'maximum_exact_gap_ratio': 0.8833333333333333,
                           'extra_checks': 0,
                           'completed_rounds_total': 136,
                           'current_round_unfinished_obligations': 40,
                           'unfinished_committed_tasks': 26,
                           'numeric_scoring_failures': 0,
                           'estimator_calls': 0,
                           'local_plan_count': 520,
                           'reordered_plans': 180,
                           'decision_points_with_alternative': 520}},
 'nominal_H': {'process_fingerprint': 'c47ad5db649813b54470c1fa8afefdffca1a3541abab201a0820f75fd2859522',
               'action_sha256': '354ace0fc979e3c2d6ce864e8463d86416dff038ccc0201f37d08ed6048fe3dc',
               'measurements_sha256': 'd04e381593c826c7c33af9648ccbb2852456c6f067e4703eda2188bfe8471764',
               'assignments_sha256': '994ee443fded64f5ca709073d5a7d572f19c6c8ed5e9898bf61ebee4c26a6eb3',
               'exact_task_gaps_sha256': 'b5790c79e7c5cc34b3154a2842a1f14262e5268a047121e96595d2184b23e397',
               'metrics': {'anomaly_segments': 6,
                           'confirmed_segments': 4,
                           'missed_segments': 2,
                           'miss_rate': 0.33333333333333337,
                           'consequence_weighted_censored_delay_s': 58.50731106967116,
                           'detected_only_mean_delay_s': 71.25,
                           'false_measured_confirmations': 0,
                           'completed_inspections': 1427,
                           'final_professional_coverage': 1.0,
                           'mean_overdue_fraction': 0.0,
                           'maximum_inspection_age_s': 305.0,
                           'travel_m': 11799.299999999992,
                           'service_s': 16680.0,
                           'idle_s': 3830.699999999998,
                           'public_return': -0.24958967783290723,
                           'invalid_assignments': 0,
                           'duplicate_reservations': 0,
                           'unserved_IT_kwh': 2.118460104716565,
                           'tasks_violating_exact_gap': 0,
                           'maximum_exact_gap_s': 310.0,
                           'maximum_exact_gap_ratio': 0.9333333333333333,
                           'extra_checks': 0,
                           'completed_rounds_total': 136,
                           'current_round_unfinished_obligations': 61,
                           'unfinished_committed_tasks': 31,
                           'numeric_scoring_failures': 0,
                           'estimator_calls': 0,
                           'local_plan_count': 514,
                           'reordered_plans': 2,
                           'decision_points_with_alternative': 514}},
 'history_stub_T': {'process_fingerprint': 'c47ad5db649813b54470c1fa8afefdffca1a3541abab201a0820f75fd2859522',
                    'action_sha256': '9cdd310bfe9b4a6b477bb1beef9a2f795a61ed201b588603e20f65e5443d1086',
                    'measurements_sha256': 'b9f37707932e90bae3c2743cda3766a1848efc5a860108b825555ff29c306999',
                    'assignments_sha256': '6313249ec0cec1443baf5538e5b51fa4487be4b4455aadb08372125feaeead9d',
                    'exact_task_gaps_sha256': 'd3f9509f3fadad472cd70f319e025b064275f025d8e40e6e0e9bac4b0c22213d',
                    'metrics': {'anomaly_segments': 6,
                                'confirmed_segments': 4,
                                'missed_segments': 2,
                                'miss_rate': 0.33333333333333337,
                                'consequence_weighted_censored_delay_s': 58.50731106967116,
                                'detected_only_mean_delay_s': 71.25,
                                'false_measured_confirmations': 0,
                                'completed_inspections': 1426,
                                'final_professional_coverage': 1.0,
                                'mean_overdue_fraction': 0.0,
                                'maximum_inspection_age_s': 305.0,
                                'travel_m': 11793.399999999992,
                                'service_s': 16670.0,
                                'idle_s': 3846.599999999998,
                                'public_return': -0.25051034686627965,
                                'invalid_assignments': 0,
                                'duplicate_reservations': 0,
                                'unserved_IT_kwh': 2.118460104716565,
                                'tasks_violating_exact_gap': 0,
                                'maximum_exact_gap_s': 310.0,
                                'maximum_exact_gap_ratio': 0.8,
                                'extra_checks': 0,
                                'completed_rounds_total': 136,
                                'current_round_unfinished_obligations': 62,
                                'unfinished_committed_tasks': 32,
                                'numeric_scoring_failures': 0,
                                'estimator_calls': 60,
                                'local_plan_count': 514,
                                'reordered_plans': 0,
                                'decision_points_with_alternative': 514},
                    'stub_input_sequence_sha256': '00b7a0a0f97f7ca5d814affa36de9f304d80886b190ef57ae38e9f7f001180a9'}}

class CoreMigrationTests(unittest.TestCase):
    def assert_frozen_episode(self, name, record, env):
        expected = GOLDEN[name]
        self.assertEqual(env.trace.fingerprint, expected['process_fingerprint'])
        self.assertEqual(record['action_sha256'], expected['action_sha256'])
        self.assertEqual(digest(record['inspection_events']), expected['measurements_sha256'])
        self.assertEqual(digest(record['assignments']), expected['assignments_sha256'])
        self.assertEqual(digest(record['exact_task_gaps']), expected['exact_task_gaps_sha256'])
        actual = {k: v for k, v in record['metrics'].items()
                  if k != 'history_estimator_inference_s'}
        self.assertEqual(actual, expected['metrics'])
        self.assertEqual(record['PPO_scoring_calls'], 0)
        self.assertEqual(actual['tasks_violating_exact_gap'], 0)

    def test_nominal_tour_is_archived_tour(self):
        record, env = run_reorder(SPEC, None, {'method': 'T'})
        self.assert_frozen_episode('nominal_T', record, env)

    def test_nominal_risk_order_is_archived_r(self):
        record, env = run_reorder(SPEC, None,
            {'method': 'expression', 'score_expression': BASE_EXPRESSION})
        self.assert_frozen_episode('nominal_R', record, env)

    def test_explicit_selector_preserves_correction_execution(self):
        record, env = execute_correction(SPEC, None,
            {'kind': 'correction', 'rule': Rule().to_dict()})
        self.assert_frozen_episode('nominal_H', record, env)

    def test_history_stub_preserves_inputs_and_refresh_schedule(self):
        observed = []
        def predictor(context):
            # Instrument only the caller's public clock; predictions use context only.
            clock = inspect.currentframe().f_back.f_locals['self'].clock
            observed.append({'time_s': float(clock), 'input_sha256': digest(context.tolist())})
            return 50. + 20. * context[:, 0].astype(float)
        record, env = run_reorder(dict(SPEC, estimator='history'), predictor, {'method': 'T'})
        self.assert_frozen_episode('history_stub_T', record, env)
        self.assertEqual([x['time_s'] for x in observed], list(range(30, 1801, 30)))
        self.assertEqual(digest(observed), GOLDEN['history_stub_T']['stub_input_sequence_sha256'])

    def test_model_weights_are_required_in_history_mode(self):
        with self.assertRaises(ValueError):
            run_reorder(dict(SPEC, estimator='history'), None, {'method': 'T'})

    def test_trace_guard_blocks_online_future_labels(self):
        with self.assertRaises(RuntimeError):
            _ = DeniedOnlineTrace().arrays

    def test_json_contract_still_rejects_duplicate_keys_and_nan(self):
        for raw in ('{"x": 1, "x": 2}', '{"x": NaN}', '{"x": 1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)


if __name__ == '__main__':
    unittest.main()
