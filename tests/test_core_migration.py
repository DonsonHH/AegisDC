"""Portable regression against the original engine, not newly accepted outputs.

The gzip fixture contains every original process value, completed measurement,
metric, anomaly interval, and public history input. Shapes, dtypes, masks,
actions, dispatches, event times and other discrete fields remain exact.
Continuous float64 values allow rtol=1e-12, atol=1e-10; float32 history values
allow at most two ULPs, with discrete feature columns still exact. Every run
prints its observed maximum differences and their paths, including on failure.
No original checkout or trained CVAE is needed to run these engineering tests.
"""
import copy
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import unittest
import numpy as np

from patrol_rsi.contracts import digest, strict_json, DeniedOnlineTrace
from patrol_rsi.reorder_execution import run_reorder
from patrol_rsi.correction_execution import execute_correction
from patrol_rsi.baseline_correction import Rule
from patrol_rsi.local_score import BASE_EXPRESSION
from patrol_rsi.inspection_metrics import task_labels

SPEC = {'seed': 41000, 'scenario': 'aux_feeder_loss+cdu_fouling',
        'duration_s': 180, 'fault_start_s': 335, 'noise_c': .2,
        'estimator': 'nominal'}

REFERENCE_PATH = Path(__file__).parent / 'fixtures' / 'core-reference.json.gz'
REFERENCE_SHA256 = '6690ea03a9322a483448b9dd05cf4eeadb6b149a062e61938f37d6619ae8a96d'
SOURCE_COMMIT = 'f2c20b3a642ff1df9426e523614d3da9a5cf1129'
FLOAT64_RTOL, FLOAT64_ATOL = 1e-12, 1e-10
FLOAT32_MAX_ULPS = 2


class NumericComparison:
    """Check every value and report actual error; never compare rounded hashes."""
    def __init__(self):
        self.values = self.differences = 0
        self.maximum_absolute = {'value': 0., 'path': None}
        self.maximum_relative = {'value': 0., 'path': None}
        self.maximum_allowed_fraction = {'value': 0., 'path': None}
        self.maximum_float32_ulps = {'value': 0, 'path': None}

    def _maximum(self, record, values, path):
        if values.size:
            flat = int(np.argmax(values))
            index = np.unravel_index(flat, values.shape)
            value = float(values.flat[flat])
            if record['path'] is None or value > record['value']:
                record.update(value=value, path=path + ''.join(f'[{i}]' for i in index))

    def compare(self, actual, expected, path, *, float32=False):
        actual, expected = np.asarray(actual), np.asarray(expected)
        if actual.shape != expected.shape:
            raise AssertionError(f'{path}: shape {actual.shape} != {expected.shape}')
        # The entire original fixture is finite. NaN/Inf must never pass a tolerance.
        if not np.isfinite(actual).all() or not np.isfinite(expected).all():
            raise AssertionError(f'{path}: nonfinite numeric value')
        difference = np.abs(actual.astype(np.float64) - expected.astype(np.float64))
        relative = difference / np.maximum(np.abs(expected.astype(np.float64)), np.finfo(np.float64).tiny)
        self.values += difference.size
        self.differences += int(np.count_nonzero(difference))
        self._maximum(self.maximum_absolute, difference, path)
        self._maximum(self.maximum_relative, relative, path)
        if float32:
            if actual.dtype != np.dtype('float32') or expected.dtype != np.dtype('float32'):
                raise AssertionError(f'{path}: float32 history dtype required')
            def ordered_bits(value):
                bits = value.view(np.uint32).astype(np.int64)
                magnitude = bits & 0x7fffffff
                return np.where(bits & 0x80000000, -magnitude, magnitude)
            ulps = np.abs(ordered_bits(actual) - ordered_bits(expected))
            self._maximum(self.maximum_float32_ulps, ulps, path)
            fraction = ulps / FLOAT32_MAX_ULPS
        else:
            fraction = difference / (FLOAT64_ATOL + FLOAT64_RTOL * np.abs(expected))
        self._maximum(self.maximum_allowed_fraction, fraction, path)
        if np.any(fraction > 1):
            flat = int(np.argmax(fraction))
            index = np.unravel_index(flat, fraction.shape)
            raise AssertionError(
                f'{path}{index}: actual={actual.flat[flat]!r}, reference={expected.flat[flat]!r}; '
                f'absolute_difference={difference.flat[flat]:.17g}; '
                f'fraction_of_allowed_error={fraction.flat[flat]:.17g}')

    def report(self):
        return dict(values=self.values, differing_values=self.differences,
                    maximum_absolute=self.maximum_absolute,
                    maximum_relative=self.maximum_relative,
                    maximum_allowed_fraction=self.maximum_allowed_fraction,
                    maximum_float32_ulps=self.maximum_float32_ulps)


class CoreMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compressed = REFERENCE_PATH.read_bytes()
        if hashlib.sha256(compressed).hexdigest() != REFERENCE_SHA256:
            raise AssertionError('Original-engine reference artifact identity changed')
        cls.reference = json.loads(gzip.decompress(compressed))
        if cls.reference['source_commit'] != SOURCE_COMMIT or cls.reference['specification'] != SPEC:
            raise AssertionError('Original-engine source/configuration identity changed')

    def assert_event(self, actual, expected, path, comparison):
        self.assertEqual(set(actual), set(expected), path)
        # Target identities, role, calibrated/access flags, alarm, service time,
        # completion time, and evidence transition remain bit-for-bit discrete.
        self.assertEqual({k: v for k, v in actual.items() if k != 'measurement'},
                         {k: v for k, v in expected.items() if k != 'measurement'}, path)
        for key, value in expected.items():
            if key != 'measurement':
                self.assertIs(type(actual[key]), type(value), f'{path}.{key}')
        self.assertEqual(set(actual['measurement']), set(expected['measurement']), path)
        for key, value in expected['measurement'].items():
            observed = actual['measurement'][key]
            if isinstance(value, float):
                comparison.compare(observed, value, f'{path}.measurement.{key}')
            else:
                self.assertIs(type(observed), type(value), path)
                self.assertEqual(observed, value, path)

    def assert_frozen_episode(self, name, record, env):
        expected = self.reference['cases'][name]
        self.assertEqual(record['action_sha256'], expected['action_sha256'])
        self.assertEqual(digest(record['action_log']), expected['action_sha256'])
        self.assertEqual(digest(record['assignments']), expected['assignments_sha256'])
        self.assertEqual(digest(record['exact_task_gaps']), expected['exact_task_gaps_sha256'])
        actual = {k: v for k, v in record['metrics'].items()
                  if k != 'history_estimator_inference_s'}
        comparisons = {key: NumericComparison() for key in ('process', 'measurements', 'metrics', 'interval_weights')}
        try:
            self.assertEqual(set(env.trace.arrays), set(self.reference['process_arrays']))
            for key, frozen in self.reference['process_arrays'].items():
                observed = env.trace.arrays[key]
                self.assertEqual(observed.dtype.str, frozen['dtype'], key)
                self.assertEqual(list(observed.shape), frozen['shape'], key)
                comparisons['process'].compare(observed, frozen['values'], f'process.{key}')
                if key == 'process_scalars':
                    np.testing.assert_array_equal(observed[:, 0], np.asarray(frozen['values'])[:, 0])
            labels = task_labels(env)[0]
            frozen = self.reference['task_label_mask']
            self.assertEqual(labels.dtype.str, frozen['dtype'])
            self.assertEqual(list(labels.shape), frozen['shape'])
            np.testing.assert_array_equal(labels, frozen['values'])
            self.assertEqual(len(record['inspection_events']), len(expected['inspection_events']))
            for i, (observed, frozen) in enumerate(zip(record['inspection_events'], expected['inspection_events'])):
                self.assert_event(observed, frozen, f'inspection_events[{i}]', comparisons['measurements'])
            self.assertEqual(set(actual), set(expected['metrics']))
            for key, frozen in expected['metrics'].items():
                if isinstance(frozen, float) and key not in ('maximum_inspection_age_s', 'maximum_exact_gap_s', 'service_s'):
                    comparisons['metrics'].compare(actual[key], frozen, f'metrics.{key}')
                else:
                    self.assertIs(type(actual[key]), type(frozen), key)
                    self.assertEqual(actual[key], frozen, key)
            self.assertEqual(digest(record['by_role']), digest(expected['by_role']))
            self.assertEqual(len(record['anomaly_intervals']), len(expected['anomaly_intervals']))
            for i, (observed, frozen) in enumerate(zip(record['anomaly_intervals'], expected['anomaly_intervals'])):
                self.assertEqual(set(observed), set(frozen))
                self.assertEqual({k: v for k, v in observed.items() if k != 'weight'},
                                 {k: v for k, v in frozen.items() if k != 'weight'})
                for key, value in frozen.items():
                    if key != 'weight':
                        self.assertIs(type(observed[key]), type(value), f'anomaly_intervals[{i}].{key}')
                comparisons['interval_weights'].compare(observed['weight'], frozen['weight'], f'anomaly_intervals[{i}].weight')
        finally:
            print('migration_numeric ' + json.dumps({'case': name, 'actual_process_fingerprint': env.trace.fingerprint,
                  'reference_process_fingerprint': self.reference['process_fingerprint'],
                  'comparisons': {key: value.report() for key, value in comparisons.items()}}, sort_keys=True), flush=True)
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
        observed, contexts = [], []
        def predictor(context):
            # Instrument only the caller's public clock; predictions use context only.
            clock = inspect.currentframe().f_back.f_locals['self'].clock
            observed.append(float(clock))
            contexts.append(context.copy())
            return 50. + 20. * context[:, 0].astype(float)
        record, env = run_reorder(dict(SPEC, estimator='history'), predictor, {'method': 'T'})
        self.assert_frozen_episode('history_stub_T', record, env)
        expected = self.reference['cases']['history_stub_T']
        self.assertEqual(observed, expected['history_call_times'])
        self.assertEqual(observed, list(range(30, 1801, 30)))
        actual, frozen = np.stack(contexts), expected['history_inputs']
        self.assertEqual(actual.dtype.str, frozen['dtype'])
        self.assertEqual(list(actual.shape), frozen['shape'])
        reference = np.asarray(frozen['values'], dtype=frozen['dtype'])
        # Each of the four frames has exact age, observed/verified masks and
        # static coordinates. Only continuous physical features use ULP tolerance.
        exact_columns = [14 * frame + feature for frame in range(4) for feature in (1, 2, 9, 11, 12, 13)]
        np.testing.assert_array_equal(actual[:, :, exact_columns], reference[:, :, exact_columns])
        comparison = NumericComparison()
        try:
            comparison.compare(actual, reference, 'history_inputs', float32=True)
        finally:
            print('migration_numeric ' + json.dumps({'case': 'history_stub_T', 'public_history_inputs': comparison.report()}, sort_keys=True), flush=True)

    def test_numeric_comparator_accepts_roundoff_and_rejects_corruption(self):
        reference = np.array([48.83686475581137], dtype=np.float64)
        NumericComparison().compare(np.nextafter(reference, np.inf), reference, 'roundoff')
        for invalid in (reference + 1e-6, np.array([np.nan]), np.array([np.inf])):
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                NumericComparison().compare(invalid, reference, 'corruption')
        reference32 = np.array([.125], dtype=np.float32)
        one_ulp = np.nextafter(reference32, np.float32(np.inf))
        NumericComparison().compare(one_ulp, reference32, 'float32_roundoff', float32=True)
        three_ulps = np.nextafter(np.nextafter(one_ulp, np.float32(np.inf)), np.float32(np.inf))
        with self.assertRaises(AssertionError):
            NumericComparison().compare(three_ulps, reference32, 'float32_corruption', float32=True)

    def test_event_comparator_rejects_alarm_time_schema_and_measurement_changes(self):
        expected = self.reference['cases']['nominal_T']['inspection_events'][0]
        alarm, time, missing, measurement, alarm_type = (copy.deepcopy(expected) for _ in range(5))
        alarm['alarm'] = not alarm['alarm']
        time['time_s'] += 1e-12
        del missing['role']
        measurement['measurement']['temperature_c'] += 1e-6
        alarm_type['alarm'] = int(alarm_type['alarm'])
        for invalid in (alarm, time, missing, measurement, alarm_type):
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                self.assert_event(invalid, expected, 'event', NumericComparison())

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
