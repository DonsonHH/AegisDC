"""Public observation-producer examples; no plant execution or policy trial."""
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest


def example_profile():
    return {
        'schema': 'aegisdc-sparse-channels-v1',
        'ledger': {
            'schema': 'aegisdc-evidence-ledger-v1', 'id': 'declared-probe-ledger',
            'facility_id': 'literal-facility', 'basis': 'synthetic_assumption', 'time_unit': 's',
            'entity_ids': ['immersion'],
            'observables': [{'id': 'coolant_temperature', 'quantity': 'temperature',
                             'value_type': 'number', 'unit': 'K'}],
            'sources': [{'id': 'temperature-probe', 'kind': 'fixed_sensor',
                         'basis': 'synthetic_assumption', 'target_ids': ['immersion'],
                         'observable_ids': ['coolant_temperature'], 'dependency_group': None,
                         'source_note': 'Declared instrument model, not field calibration.'}],
            'records': [],
        },
        'measurements': [{'id': 'temperature-measurement', 'signal': 'coolant_temperature',
                          'target_id': 'immersion', 'period_s': 1, 'phase_s': 0, 'enabled': True,
                          'input_range': [270, 350], 'declared_bias_bound': 1,
                          'declared_noise_bound': 0, 'quantization_bound': 1e-9,
                          'declared_dropout_probability': 0, 'calibration_group': None}],
        'channels': [{'id': 'temperature-packet', 'measurement_id': 'temperature-measurement',
                      'source_id': 'temperature-probe', 'observable_id': 'coolant_temperature',
                      'transform': 'identity', 'threshold': None, 'delay_s': 2,
                      'validity_s': 5, 'quality_mode': 'bounded'}],
    }


def example_realization():
    return {'schema': 'aegisdc-private-observation-realization-v1', 'seed': 7,
            'biases': {'temperature-measurement': .5},
            'noise_bounds': {'temperature-measurement': 0},
            'dropout_probabilities': {'temperature-measurement': 0}}


def example_trace():
    return {'schema': 'aegisdc-observation-private-trace-v1', 'facility_id': 'literal-facility',
            'entity_ids': ['immersion'],
            'points': [dict(time_s=t, domains={'equipment_environment': {
                'refrigerant': {'temperature_K': value}}}) for t, value in [(0, 300), (1, 302), (2, 304)]],
            'private_metadata': {'fault_case': 'must-never-enter-dispatch'}}


class SparseObservationChannelTests(unittest.TestCase):
    def test_literal_signal_bias_and_delivery_delay_form_legal_evidence(self):
        from aegis_dc.sensor_channels import sample_trace
        from aegis_dc.evidence_ledger import EvidenceLedger
        produced = sample_trace(example_profile(), example_trace(), example_realization())
        ledger = EvidenceLedger(produced['ledger'])
        self.assertEqual(ledger.snapshot(2)['records'][0]['value'], 300.5)
        at_three = ledger.snapshot(3)
        self.assertEqual([r['value'] for r in at_three['records']], [300.5, 302.5])
        self.assertEqual(at_three['records'][1]['observed_at_s'], 1)
        self.assertEqual(at_three['records'][1]['arrived_at_s'], 3)
        self.assertEqual(at_three['records'][1]['age_s'], 2)
        self.assertEqual(at_three['records'][1]['valid_until_s'], 6)
        self.assertEqual(produced['state_visibility'], 'PRIVATE_EVALUATOR_ONLY')

    def test_cached_poll_does_not_redraw_noise_and_future_signal_does_not_change_past(self):
        from aegis_dc.sensor_channels import sample_trace
        from aegis_dc.evidence_ledger import EvidenceLedger
        profile = example_profile()
        profile['measurements'][0]['period_s'] = .5
        realization = example_realization()
        realization['biases']['temperature-measurement'] = 0
        realization['noise_bounds']['temperature-measurement'] = 1
        produced = sample_trace(profile, example_trace(), realization)
        records = produced['ledger']['records']
        self.assertNotEqual(records[0]['value'], 300)
        self.assertEqual(records[0]['value'], records[1]['value'])
        self.assertEqual(records[0]['provenance'], records[1]['provenance'])
        self.assertNotEqual(records[0]['id'], records[1]['id'])
        self.assertEqual(records[1]['observed_at_s'], 0)
        self.assertEqual(records[1]['arrived_at_s'], 2.5)
        self.assertEqual(produced, sample_trace(profile, example_trace(), realization))
        changed = example_trace()
        changed['points'][2]['domains']['equipment_environment']['refrigerant']['temperature_K'] = 330
        changed['private_metadata']['fault_case'] = 'different-private-future'
        before = EvidenceLedger(produced['ledger']).snapshot(2.5)
        later = sample_trace(profile, changed, realization)
        self.assertEqual(before, EvidenceLedger(later['ledger']).snapshot(2.5))
        another = deepcopy(realization)
        another['seed'] = 8
        second = sample_trace(profile, example_trace(), another)
        self.assertNotEqual(records[0]['value'], second['ledger']['records'][0]['value'])
        self.assertEqual(produced['public_model'], second['public_model'])

    def test_disabled_or_dropped_fixed_input_never_becomes_zero_and_history_still_works(self):
        from aegis_dc.sensor_channels import sample_trace
        from aegis_dc.evidence_ledger import EvidenceLedger
        profile = example_profile()
        realization = example_realization()
        realization['dropout_probabilities']['temperature-measurement'] = 1
        produced = sample_trace(profile, example_trace(), realization)
        self.assertEqual([row['value'] for row in produced['ledger']['records']], [None, None, None])
        self.assertTrue(all(row['quality']['status'] == 'unknown'
                            for row in produced['ledger']['records']))
        ledger = EvidenceLedger(produced['ledger'])
        self.assertEqual(ledger.snapshot(10)['current_record_ids'], [])
        profile['measurements'][0]['enabled'] = False
        profile['ledger']['sources'].append(dict(profile['ledger']['sources'][0], id='history',
                                                 kind='maintenance_history'))
        no_fixed = sample_trace(profile, example_trace(), realization)
        self.assertEqual(no_fixed['ledger']['records'], [])
        historical = dict(id='historical-reading', source_id='history', target_id='immersion',
                          observable_id='coolant_temperature', unit='K', value=299,
                          observed_at_s=-10, arrived_at_s=-5, valid_until_s=None,
                          quality={'status': 'unknown', 'error_bound': None, 'note': 'Historical report.'},
                          provenance={'origin_id': 'past-report', 'copied_from_record_id': None})
        ledger = EvidenceLedger(no_fixed['ledger'])
        self.assertEqual(ledger.ingest(historical), 'ADDED')
        self.assertEqual(ledger.snapshot(0)['current_record_ids'], ['historical-reading'])

    def test_reported_control_cache_keeps_its_sample_time_noise_and_shared_origin(self):
        from aegis_dc.sensor_channels import sample_trace
        profile = example_profile()
        profile['ledger']['entity_ids'].append('local_controller')
        profile['ledger']['observables'] += [
            dict(id='reported_temperature', quantity='temperature', value_type='number', unit='K'),
            dict(id='temperature_valid', quantity='binary', value_type='boolean', unit='1')]
        profile['ledger']['sources'].append(dict(id='control-log', kind='control_record',
            basis='synthetic_assumption', target_ids=['local_controller'],
            observable_ids=['reported_temperature', 'temperature_valid'], dependency_group=None,
            source_note='Authorized reported controller fields, not actual temperature or bias.'))
        profile['measurements'].append(dict(profile['measurements'][0], id='control-measurement',
            signal='controller_temperature', target_id='local_controller', period_s=.5))
        for identifier, observable, transform, quality in [
                ('control-temperature', 'reported_temperature', 'identity', 'unknown'),
                ('control-validity', 'temperature_valid', 'validity', 'reported')]:
            profile['channels'].append(dict(profile['channels'][0], id=identifier,
                measurement_id='control-measurement', source_id='control-log', observable_id=observable,
                transform=transform, quality_mode=quality, delay_s=1))
        trace = example_trace()
        trace['entity_ids'].append('local_controller')
        for point in trace['points']:
            point['domains']['control_monitoring'] = {'local_measurement': dict(
                sampled_at_s=0 if point['time_s'] < 2 else 2,
                temperature_K=290, temperature_valid=point['time_s'] < 2)}
        realization = example_realization()
        realization['biases']['control-measurement'] = 0
        realization['noise_bounds']['control-measurement'] = 1
        realization['dropout_probabilities']['control-measurement'] = 0
        result = sample_trace(profile, trace, realization)
        temperatures = [row for row in result['ledger']['records']
                        if row['observable_id'] == 'reported_temperature']
        self.assertEqual([row['observed_at_s'] for row in temperatures], [0, 0, 0, 0, 2])
        self.assertEqual(len({row['value'] for row in temperatures[:4]}), 1)
        self.assertTrue(289 <= temperatures[0]['value'] <= 291)
        self.assertEqual(len({row['provenance']['origin_id'] for row in temperatures[:4]}), 1)
        self.assertEqual(len({row['id'] for row in temperatures[:4]}), 4)
        self.assertTrue(all(row['quality']['status'] == 'unknown' for row in temperatures))
        self.assertIsNone(temperatures[-1]['value'])
        validity = [row for row in result['ledger']['records'] if row['observable_id'] == 'temperature_valid']
        self.assertIs(validity[-1]['value'], False)
        self.assertEqual(validity[-1]['provenance'], temperatures[-1]['provenance'])

    def test_threshold_packets_share_measurement_root_and_private_bias_does_not_relabel_quality(self):
        from aegis_dc.sensor_channels import sample_trace
        from aegis_dc.evidence_ledger import EvidenceLedger
        profile = example_profile()
        profile['measurements'][0]['calibration_group'] = 'temperature-calibration'
        profile['ledger']['sources'][0]['dependency_group'] = 'temperature-calibration'
        profile['ledger']['observables'].append(dict(id='coolant_hot', quantity='binary', value_type='boolean', unit='1'))
        profile['ledger']['sources'].append(dict(profile['ledger']['sources'][0], id='probe-alarm',
                                                 observable_ids=['coolant_hot']))
        profile['channels'].append(dict(profile['channels'][0], id='alarm-packet', source_id='probe-alarm',
            observable_id='coolant_hot', transform='above', threshold=305, delay_s=1, quality_mode='reported'))
        realization = example_realization()
        realization['biases'] = {'temperature-calibration': 10}
        false_positive = sample_trace(profile, example_trace(), realization)
        alarm = next(row for row in false_positive['ledger']['records'] if row['observable_id'] == 'coolant_hot')
        numeric = next(row for row in false_positive['ledger']['records'] if row['observable_id'] == 'coolant_temperature')
        self.assertIs(alarm['value'], True)  # Literal signal 300 K is below 305 K.
        self.assertEqual(numeric['value'], 310)
        self.assertEqual(alarm['provenance'], numeric['provenance'])
        self.assertEqual(EvidenceLedger(false_positive['ledger']).snapshot(1)['current_record_ids'], ['alarm-packet:0'])
        changed = example_trace()
        for point in changed['points']:
            point['domains']['equipment_environment']['refrigerant']['temperature_K'] = 315
        changed['private_metadata']['fault_case'] = 'fault-present-but-not-an-observation'
        realization['biases']['temperature-calibration'] = -20
        false_negative = sample_trace(profile, changed, realization)
        other_alarm = next(row for row in false_negative['ledger']['records'] if row['observable_id'] == 'coolant_hot')
        other_numeric = next(row for row in false_negative['ledger']['records'] if row['observable_id'] == 'coolant_temperature')
        self.assertIs(other_alarm['value'], False)
        self.assertEqual(other_numeric['value'], 295)
        self.assertEqual(numeric['quality'], other_numeric['quality'])
        self.assertEqual(false_positive['public_model'], false_negative['public_model'])
        self.assertTrue(false_positive['private_audit'][0]['declared_bound_violated'])
        self.assertTrue(false_negative['private_audit'][0]['declared_bound_violated'])

    def test_closed_profile_refuses_invalid_clocks_coverage_units_and_private_parameters(self):
        from aegis_dc.sensor_channels import validate_channel_profile, sample_trace
        mutations = [
            ('measurements.0.period_s', 0), ('measurements.0.phase_s', -1),
            ('measurements.0.enabled', 1), ('measurements.0.signal', 'private_fault_label'),
            ('measurements.0.target_id', 'uncovered-secret-target'),
            ('measurements.0.input_range', [350, 270]),
            ('measurements.0.declared_bias_bound', -1),
            ('measurements.0.declared_noise_bound', True),
            ('measurements.0.quantization_bound', 0),
            ('measurements.0.declared_dropout_probability', 1.1),
            ('channels.0.delay_s', -1), ('channels.0.validity_s', 0),
            ('channels.0.transform', 'read_actual_fault'), ('channels.0.quality_mode', 'certain_truth'),
            ('channels.0.source_id', 'unregistered-source'),
            ('ledger.observables.0.unit', 'degC')]
        for path, value in mutations:
            with self.subTest(path=path):
                profile = example_profile()
                owner = profile
                parts = path.split('.')
                for part in parts[:-1]:
                    owner = owner[int(part)] if isinstance(owner, list) else owner[part]
                owner[parts[-1]] = value
                with self.assertRaises(ValueError):
                    validate_channel_profile(profile)
        private_in_public = example_profile()
        private_in_public['actual_bias'] = 10
        with self.assertRaises(ValueError):
            validate_channel_profile(private_in_public)
        missing_realization = example_realization()
        missing_realization['biases'].clear()
        with self.assertRaises(ValueError):
            sample_trace(example_profile(), example_trace(), missing_realization)
        trace = example_trace()
        trace['points'][1]['time_s'] = 0
        with self.assertRaises(ValueError):
            sample_trace(example_profile(), trace, example_realization())

    def test_public_model_requires_empty_registry_and_does_not_expose_or_share_private_data(self):
        from aegis_dc.sensor_channels import public_model, sample_trace
        profile = example_profile()
        output = sample_trace(profile, example_trace(), example_realization())
        encoded = json.dumps(output['public_model'], sort_keys=True)
        for hidden in ('seed', 'private_bias', 'private_metadata', 'fault_case', 'private_signal'):
            self.assertNotIn(hidden, encoded)
        self.assertEqual(output['public_model']['ledger']['records'], [])
        queued = deepcopy(profile)
        queued['ledger']['records'] = deepcopy(output['ledger']['records'])
        with self.assertRaises(ValueError):
            public_model(queued)
        output['public_model']['ledger']['sources'][0]['target_ids'].clear()
        output['ledger']['records'][0]['value'] = -1000
        self.assertEqual(sample_trace(profile, example_trace(), example_realization())['ledger']['records'][0]['value'], 300.5)

    def test_arrival_rounds_up_and_expired_cached_reading_is_not_refreshed(self):
        from aegis_dc.sensor_channels import sample_trace
        from aegis_dc.evidence_ledger import EvidenceLedger
        profile = example_profile()
        profile['measurements'][0]['phase_s'] = .6
        profile['channels'][0].update(delay_s=.1, validity_s=.25)
        trace = example_trace()
        trace['points'] = [trace['points'][0]]
        trace['points'].append(dict(time_s=.6, domains={'equipment_environment': {
            'refrigerant': {'temperature_K': 303}}}))
        trace['points'].append(dict(time_s=1.6, domains={'equipment_environment': {
            'refrigerant': {'temperature_K': 304}}}))
        result = sample_trace(profile, trace, example_realization())
        arrival = math.nextafter(.7, math.inf)
        first = result['ledger']['records'][0]
        self.assertEqual(first['arrived_at_s'], arrival)
        ledger = EvidenceLedger(result['ledger'])
        self.assertEqual(ledger.snapshot(.7)['records'], [])
        self.assertEqual(ledger.snapshot(arrival)['current_record_ids'], ['temperature-packet:0'])
        # A 1 s polling delay reports the old .6 s observation after expiry.
        profile['channels'][0]['delay_s'] = 1
        late = EvidenceLedger(sample_trace(profile, trace, example_realization())['ledger']).snapshot(1.6)
        self.assertEqual(late['current_record_ids'], [])
        self.assertEqual(late['records'][0]['availability'], 'expired')
        self.assertEqual(late['records'][0]['age_s'], 1)


if __name__ == '__main__':
    unittest.main()
