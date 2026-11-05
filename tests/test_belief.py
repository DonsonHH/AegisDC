"""Public decision frame and belief CLI behavior for the V6 engineering question."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aegis_dc.decision_view import DecisionGateway


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'configs'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def inputs(records=(), times=(0,), model=None):
    nominal = read(CONFIG / 'full-facility-decision-v1/public-nominal.json')
    if model is None:
        model = read(CONFIG / 'full-facility-belief-model-v1.json')
    ledger = read(CONFIG / 'full-facility-sensor-channels-v1.json')['ledger']
    nonfixed = read(CONFIG / 'full-facility-nonfixed-evidence-v1.json')['registry']
    common = read(CONFIG / 'full-facility-decision-v1/common-ledger.json')
    observables = {row['id']: row for row in ledger['observables']}
    observables.update({row['id']: row for row in nonfixed['observables']})
    observables.update({row['id']: row for row in common['observables']})
    ledger['id'] = model['scope']['ledger_id']
    ledger['observables'] = list(observables.values())
    sources = {row['id']: row for row in common['sources'] + ledger['sources'] + nonfixed['sources']}
    ledger['sources'] = list(sources.values())
    ledger['records'] = list(records)
    plan = read(CONFIG / 'full-facility-decision-v1/public-plan.json')
    plan['decision_times_s'] = list(times)
    return nominal, ledger, plan, model


def frames(records=(), times=(0,), model=None):
    nominal, ledger, plan, model = inputs(records, times, model)
    gateway = DecisionGateway(nominal, ledger, plan)
    return [gateway.next_frame() for _ in times], model


class TestBeliefUpdates(unittest.TestCase):
    def test_absence_of_evidence_predicts_nonzero_cause_probabilities(self):
        from aegis_dc.belief import infer_belief

        decision_frames, model = frames(times=(0, 9.999, 10))
        first, just_before, next_epoch = [infer_belief(frame, model) for frame in decision_frames]
        self.assertEqual(first['status'], 'PRIOR_PREDICTION')
        self.assertEqual(first['posterior'], {'nominal': .6, 'cooling-limited': .2,
                                             'power-limited': .1, 'other': .1})
        self.assertEqual(just_before['posterior'], first['posterior'])
        self.assertEqual(next_epoch['posterior'], {'nominal': .51, 'cooling-limited': .2,
                                                  'power-limited': .15, 'other': .14})
        self.assertEqual(next_epoch['facility_id'], model['facility_id'])
        self.assertEqual(len(next_epoch['domain_ids']), 8)
        self.assertEqual(next_epoch['scope_id'], model['scope']['id'])
        self.assertEqual(next_epoch['information_updates'], [])
        self.assertEqual(next_epoch['physical_actions'], [])

    def test_late_alarm_updates_observation_epoch_and_expiry_remains_historical(self):
        from aegis_dc.belief import infer_belief

        alarm = record('alarm', 'coolant-alarm-packet', 'immersion', 'coolant_hot_reported',
                       '1', True, observed=1, arrived=11, valid_until=15)
        decision_frames, model = frames([alarm], times=(10, 11, 15))
        before, late, expired = [infer_belief(frame, model) for frame in decision_frames]
        self.assertEqual(before['posterior']['cooling-limited'], .2)
        self.assertEqual(before['record_audit'], [])
        self.assertEqual(late['posterior']['cooling-limited'], 27 / 70)
        self.assertNotEqual(late['posterior']['cooling-limited'], 160 / 297)
        self.assertEqual(late['information_updates'], ['alarm'])
        self.assertEqual(late['record_audit'][0]['observation_epoch'], 0)
        self.assertEqual(late['record_audit'][0]['arrived_at_s'], 11)
        self.assertEqual(late['record_audit'][0]['availability'], 'current')
        self.assertEqual(late['status'], 'UPDATED')
        self.assertEqual(expired['posterior'], late['posterior'])
        self.assertEqual(expired['record_audit'][0]['availability'], 'expired')


    def test_copy_before_root_never_counts_and_late_root_counts_once(self):
        from aegis_dc.belief import infer_belief

        root = hot('root', True, observed=1, arrived=11)
        copied = hot('copy', True, observed=1, arrived=9, origin='root', parent='root')
        decision_frames, model = frames([root, copied], times=(10, 11))
        before, after = [infer_belief(frame, model) for frame in decision_frames]
        self.assertEqual(before['posterior']['cooling-limited'], .2)
        self.assertEqual(before['record_audit'][0]['disposition'], 'copy_root_unavailable')
        self.assertEqual(after['posterior']['cooling-limited'], 27 / 70)
        self.assertEqual(after['information_updates'], ['root'])
        self.assertEqual(after['record_audit'][0]['disposition'], 'copy_not_a_factor')
        reordered, _ = frames([copied, root], times=(11,))
        self.assertEqual(after, infer_belief(reordered[0], model))

    def test_latest_representative_replaces_repeat_and_unmodeled_dependence_is_deferred(self):
        from aegis_dc.belief import infer_belief

        early = hot('early', True, observed=1, arrived=1)
        late = hot('late', False, observed=10, arrived=11)
        vibration = record('vibration', 'operator-report', 'filter', 'vibration_reported',
                           '1', True, observed=9, arrived=10)
        decision_frames, model = frames([early, late, vibration], times=(10, 11))
        before, after = [infer_belief(frame, model) for frame in decision_frames]
        self.assertEqual(before['information_updates'], ['early'])
        self.assertEqual(after['information_updates'], ['late'])
        self.assertAlmostEqual(after['posterior']['cooling-limited'], 40 / 703)
        self.assertEqual({row['record_id']: row['disposition'] for row in after['record_audit']},
                         {'early': 'channel_representative_already_used', 'late': 'used',
                          'vibration': 'dependence_not_modeled'})

    def test_late_visible_link_can_remove_a_previously_eligible_factor(self):
        from aegis_dc.belief import infer_belief

        alarm = hot('alarm', True, observed=1, arrived=11)
        power = low_power('power', 0, observed=10, arrived=11)
        bridge = record('bridge', 'coolant-probe-record', 'immersion', 'coolant_temperature',
                        'K', 310, observed=10, arrived=12, error_bound=1, origin='power', parent='power')
        decision_frames, model = frames([alarm, power, bridge], times=(11, 12))
        before, after = [infer_belief(frame, model) for frame in decision_frames]
        self.assertEqual(before['information_updates'], ['alarm', 'power'])
        self.assertAlmostEqual(before['posterior']['power-limited'], 171 / 412)
        self.assertEqual(after['information_updates'], ['alarm'])
        self.assertEqual(after['posterior']['cooling-limited'], 27 / 70)
        self.assertEqual({row['record_id']: row['disposition'] for row in after['record_audit']}['power'],
                         'shared_provenance')

    def test_model_envelope_is_declared_sensitivity_and_conflict_is_explicit(self):
        from aegis_dc.belief import infer_belief

        decision_frames, model = frames([hot('alarm', True, observed=1, arrived=11)], times=(11,))
        frame = decision_frames[0]
        baseline = infer_belief(frame, model)
        self.assertEqual(baseline['assumption_envelope']['cooling-limited'], [61 / 210, 27 / 70])
        self.assertEqual(baseline['envelope_basis'], 'MIN_MAX_ACROSS_DECLARED_MODEL_VARIANTS')

        model['variants'][0]['positive_likelihood']['fixed-hot'] = [0, 0, 0, 0]
        partial = infer_belief(frame, model)
        self.assertEqual(partial['status'], 'PARTIAL_MODEL_CONFLICT')
        self.assertEqual(partial['impossible_observation_epoch_by_variant'], {'reference': 0})
        self.assertIsNone(partial['posterior'])
        self.assertIsNone(partial['assumption_envelope'])
        self.assertEqual(partial['positive_support_by_variant']['reference'], [])
        self.assertEqual(len(partial['positive_support_by_variant']['weaker-discrimination']), 4)
        model['variants'][1]['positive_likelihood']['fixed-hot'] = [0, 0, 0, 0]
        self.assertEqual(infer_belief(frame, model)['status'], 'MODEL_CONFLICT')

    def test_display_rounding_cannot_turn_positive_path_support_into_model_conflict(self):
        from aegis_dc.belief import infer_belief

        alarm = hot('alarm', True, observed=1, arrived=1)
        decision_frames, model = frames([alarm], times=(1,))
        model['variants'][0]['prior'] = [.5, .1, .3, .1]
        model['variants'][0]['positive_likelihood']['fixed-hot'] = [1, 5e-324, 1, 1]
        result = infer_belief(decision_frames[0], model)
        self.assertEqual(result['posterior']['cooling-limited'], 0.0)
        self.assertIn('cooling-limited', result['positive_support_by_variant']['reference'])
        self.assertEqual(result['status'], 'UPDATED')

    def test_ambiguous_bin_does_not_take_an_independence_slot(self):
        from aegis_dc.belief import infer_belief

        vibration = record('vibration', 'operator-report', 'filter', 'vibration_reported',
                           '1', True, observed=9, arrived=10)
        handheld = record('handheld', 'handheld-thermometer', 'immersion', 'temperature',
                          'K', 305, observed=9, arrived=10, error_bound=1)
        decision_frames, model = frames([vibration, handheld], times=(10,))
        result = infer_belief(decision_frames[0], model)
        self.assertEqual(result['information_updates'], ['vibration'])
        self.assertEqual(result['record_audit'][0]['disposition'], 'threshold_straddled')
        self.assertAlmostEqual(result['posterior']['cooling-limited'], 48 / 155)

    def test_unusable_records_remain_auditable_and_never_set_missing_to_zero(self):
        from aegis_dc.belief import infer_belief

        expired = hot('expired', True, observed=1, arrived=10, valid_until=10)
        missing = hot('missing', None, observed=1, arrived=10)
        unknown = hot('unknown', True, observed=1, arrived=10, quality='unknown')
        old = hot('old', True, observed=-1, arrived=10)
        flow = record('flow', 'intake-flow-record', 'intake_pump', 'lake_mass_flow',
                      'kg/s', 0, observed=1, arrived=10, error_bound=0)
        decision_frames, model = frames([expired, missing, unknown, old, flow], times=(10,))
        result = infer_belief(decision_frames[0], model)
        self.assertEqual(result['status'], 'PRIOR_PREDICTION')
        self.assertEqual(result['posterior']['cooling-limited'], .2)
        self.assertEqual({row['record_id']: row['disposition'] for row in result['record_audit']},
                         {'expired': 'expired_before_arrival', 'missing': 'missing',
                          'unknown': 'unknown_quality', 'old': 'before_scope', 'flow': 'unsupported_channel'})

    def test_frame_scope_admission_preserves_replicates_and_refuses_forged_truth(self):
        from aegis_dc.belief import infer_belief

        now = hot('now', True, observed=1, arrived=10)
        future = hot('later', False, observed=12, arrived=13)
        first, model = frames([now], times=(10,))
        second, _ = frames([now, future], times=(10,))
        self.assertEqual(infer_belief(first[0], model), infer_belief(second[0], model))
        frame = deepcopy(first[0])
        frame['private_seed'] = 5
        with self.assertRaisesRegex(ValueError, 'closed contract'):
            infer_belief(frame, model)
        frame = deepcopy(first[0])
        frame['evidence']['records'][0]['arrived_at_s'] = 11
        with self.assertRaisesRegex(ValueError, 'consistent current snapshot'):
            infer_belief(frame, model)

        replicate = deepcopy(model)
        replicate['scope'].update(id='replicate-two', ledger_id='ledger-two')
        with self.assertRaisesRegex(ValueError, 'scope differs'):
            infer_belief(first[0], replicate)
        separate, _ = frames(times=(10,), model=replicate)
        self.assertEqual(infer_belief(separate[0], replicate)['scope_id'], 'replicate-two')
        end, _ = frames(times=(250,))
        with self.assertRaisesRegex(ValueError, 'outside the declared belief scope'):
            infer_belief(end[0], model)

    def test_conflicting_roots_are_visible_and_deferred(self):
        from aegis_dc.belief import infer_belief

        left = hot('left', True, observed=1, arrived=10)
        right = hot('right', False, observed=1, arrived=11)
        decision_frames, model = frames([left, right], times=(10, 11))
        before, after = [infer_belief(frame, model) for frame in decision_frames]
        self.assertEqual(before['information_updates'], ['left'])
        self.assertEqual(after['information_updates'], [])
        self.assertEqual(after['posterior']['cooling-limited'], .2)
        self.assertEqual([item['disposition'] for item in after['record_audit']], ['conflicting_reports'] * 2)
        self.assertEqual(after['reported_conflicts'][0]['record_ids'], ['left', 'right'])

    def test_cli_consumes_only_closed_frame_and_model_and_prints_detached_belief(self):
        from aegis_dc.belief import infer_belief

        decision_frames, model = frames([hot('alarm', True, observed=1, arrived=11)], times=(11,))
        frame = decision_frames[0]
        before = deepcopy(frame)
        result = infer_belief(frame, model)
        self.assertEqual(frame, before)
        with tempfile.TemporaryDirectory() as directory:
            frame_path, model_path = Path(directory) / 'frame.json', Path(directory) / 'model.json'
            frame_path.write_text(json.dumps(frame), encoding='utf-8')
            model_path.write_text(json.dumps(model), encoding='utf-8')
            command = [sys.executable, '-B', '-X', 'utf8', '-m', 'aegis_dc.belief',
                       '--frame', str(frame_path), '--model', str(model_path)]
            options = dict(cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True)
            completed = subprocess.run(command, **options)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode('utf-8'))
            self.assertEqual(json.loads(completed.stdout), result)
            frame_path.write_text(json.dumps(dict(frame, private_world='unsafe')), encoding='utf-8')
            refused = subprocess.run(command, **options)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(refused.stdout, b'')

    def test_pairwise_independence_cannot_authorize_a_third_joint_factor(self):
        from aegis_dc.belief import infer_belief

        decision_frames, model = frames()
        model['independent_pairs'].extend([['fixed-hot', 'handheld-hot'],
                                          ['fixed-low-power', 'handheld-hot']])
        with self.assertRaisesRegex(ValueError, 'at most one'):
            infer_belief(decision_frames[0], model)

    def test_model_requires_registered_channel_bindings_even_without_readings(self):
        from aegis_dc.belief import infer_belief

        decision_frames, model = frames()
        channel = model['channels'][1]
        for changes in ({'source_id': 'unknown-source'}, {'observable_id': 'unknown-observable'},
                        {'unit': 'banana'}, {'target_id': 'immersion'},
                        {'source_id': 'unknown-source', 'observable_id': 'unknown-observable', 'unit': 'banana'}):
            with self.subTest(changes=changes):
                edited = deepcopy(model)
                edited['channels'][1] = dict(channel, **changes)
                with self.assertRaises(ValueError):
                    infer_belief(decision_frames[0], edited)

def record(identifier, source, target, observable, unit, value, *, observed, arrived,
           valid_until=None, origin=None, parent=None, error_bound=None, quality=None):
    status = quality or ('unknown' if value is None else 'bounded' if error_bound is not None else 'reported')
    return dict(id=identifier, source_id=source, target_id=target, observable_id=observable,
                unit=unit, value=value, observed_at_s=observed, arrived_at_s=arrived,
                valid_until_s=valid_until, quality=dict(status=status, error_bound=error_bound,
                note='Declared engineering fixture record.'), provenance=dict(
                    origin_id=origin or identifier, copied_from_record_id=parent))


def hot(identifier, value, **times):
    return record(identifier, 'coolant-alarm-packet', 'immersion', 'coolant_hot_reported', '1', value, **times)


def low_power(identifier, value, **times):
    return record(identifier, 'rectifier-meter-record', 'rectifier', 'rectifier_input_power', 'W',
                  value, error_bound=0, **times)
