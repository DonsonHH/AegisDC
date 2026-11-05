"""Public observation-producer examples; no plant execution or policy trial."""
from copy import deepcopy
import json
import math
import hashlib
import tempfile
import zipfile
import os
import subprocess
import sys
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

    def test_sparse_mass_flow_and_power_signals_preserve_zero_without_reading_other_assets(self):
        from aegis_dc.sensor_channels import sample_trace
        from aegis_dc.evidence_ledger import EvidenceLedger
        profile = example_profile()
        profile['ledger']['entity_ids'] += ['intake_pump', 'rectifier', 'uncovered-asset']
        realization = example_realization()
        for name, signal, target, quantity, unit in [
                ('flow', 'lake_mass_flow', 'intake_pump', 'mass_flow', 'kg/s'),
                ('power', 'rectifier_input_power', 'rectifier', 'power', 'W')]:
            profile['ledger']['observables'].append(dict(id=name, quantity=quantity, value_type='number', unit=unit))
            profile['ledger']['sources'].append(dict(profile['ledger']['sources'][0], id=name + '-probe',
                                                     target_ids=[target], observable_ids=[name]))
            profile['measurements'].append(dict(profile['measurements'][0], id=name, signal=signal,
                target_id=target, input_range=[0, 10000000], declared_bias_bound=0,
                declared_noise_bound=0, quantization_bound=0))
            profile['channels'].append(dict(profile['channels'][0], id=name + '-packet', measurement_id=name,
                source_id=name + '-probe', observable_id=name, delay_s=0))
            realization['biases'][name] = 0
            realization['noise_bounds'][name] = 0
            realization['dropout_probabilities'][name] = 0
        trace = example_trace()
        trace['entity_ids'] = list(reversed(profile['ledger']['entity_ids']))
        for point, flow, power in zip(trace['points'], [0, 10, 20], [100, 0, 50]):
            point['domains']['facility_cooling'] = {'lake_mass_flow_kg_s': flow}
            point['domains']['power'] = {'rectifier_input_W': power}
            point['domains']['uncovered-asset'] = {'private_health': 'failed-but-unmeasured'}
        result = sample_trace(profile, trace, realization)
        at_one = EvidenceLedger(result['ledger']).snapshot(1)
        self.assertEqual([(row['observable_id'], row['value']) for row in at_one['records']],
                         [('flow', 0), ('power', 100), ('flow', 10), ('power', 0)])
        self.assertNotIn('uncovered-asset', {row['target_id'] for row in result['ledger']['records']})

    def test_saved_run_loader_keeps_original_identity_and_refuses_changed_member(self):
        from aegis_dc.sensor_channels import load_saved_trace, sample_trace
        from patrol_rsi.contracts import digest
        scenario = {'id': 'literal-facility', 'entities': [{'id': 'immersion'}]}
        trace = example_trace()['points']
        raw = {'scenario.json': (json.dumps(scenario) + '\n').encode(),
               'private-state.jsonl': ''.join(json.dumps(row) + '\n' for row in trace).encode(),
               'balances.jsonl': b'{"start_s":0,"end_s":1}\n{"start_s":1,"end_s":2}\n'}
        manifest = dict(schema='aegisdc-engineering-facility-run-v1', status='ENGINEERING_FIXTURE_COMPLETED',
            state_visibility='PRIVATE_PLANT_EVALUATOR_ONLY', scenario_sha256=digest(scenario),
            code_identity={'git_commit': '0' * 40, 'files': {'literal-carrier': '0' * 64}},
            inputs={'duration_s': 2, 'maximum_step_s': 1},
            artifacts={name: dict(sha256=hashlib.sha256(data).hexdigest(),
                                  **({'records': len(data.splitlines())} if name.endswith('.jsonl') else {}))
                       for name, data in raw.items()})
        raw['run.json'] = (json.dumps(manifest) + '\n').encode()
        with tempfile.TemporaryDirectory(prefix='aegisdc-observation-loader-') as temporary:
            directory = Path(temporary).resolve()
            self.assertTrue(directory.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            good, bad = directory / 'literal-carrier.zip', directory / 'changed.zip'
            with zipfile.ZipFile(good, 'x') as archive:
                for name, data in raw.items():
                    archive.writestr(name, data)
            loaded = load_saved_trace(good)
            self.assertEqual(loaded['private_metadata']['original_code_identity']['git_commit'], '0' * 40)
            self.assertEqual(loaded['private_metadata']['original_archive_sha256'], hashlib.sha256(good.read_bytes()).hexdigest())
            self.assertEqual(sample_trace(example_profile(), loaded, example_realization())['ledger']['records'][0]['value'], 300.5)
            with zipfile.ZipFile(bad, 'x') as archive:
                for name, data in raw.items():
                    archive.writestr(name, data + b' ' if name == 'private-state.jsonl' else data)
            with self.assertRaises(ValueError):
                load_saved_trace(bad)

    def test_exact_poll_budget_bounds_iterations_and_collapsed_clocks_are_refused(self):
        # The original immutable-source799 red was stopped by root after three
        # iterations of an exact one-tick plan. It is archived, not run here.
        from aegis_dc.sensor_channels import sample_trace
        profile = example_profile()
        profile['measurements'][0].update(phase_s=1, period_s=2 ** -100)
        trace = example_trace()
        trace['points'] = [dict(time_s=1, domains={'equipment_environment': {
            'refrigerant': {'temperature_K': 300}}})]
        result = sample_trace(profile, trace, example_realization())
        self.assertEqual(len(result['ledger']['records']), 1)
        self.assertEqual(result['private_audit'][0]['poll_index'], 0)
        self.assertEqual(result['ledger']['records'][0]['value'], 300.5)
        profile['measurements'][0]['period_s'] = 2 ** -55
        trace['points'].append(dict(time_s=math.nextafter(1, math.inf), domains=deepcopy(trace['points'][0]['domains'])))
        with self.assertRaisesRegex(ValueError, 'coordinates.*collapse'):
            sample_trace(profile, trace, example_realization())
        profile['measurements'][0].update(phase_s=0, period_s=2 ** -100)
        with self.assertRaisesRegex(ValueError, 'budget'):
            sample_trace(profile, example_trace(), example_realization())

    def test_actual_private_CLI_and_public_model_mode_refuse_existing_outputs(self):
        root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, PYTHONPATH=str(root / 'src'))
        with tempfile.TemporaryDirectory(prefix='aegisdc-observation-cli-') as temporary:
            folder = Path(temporary).resolve()
            self.assertTrue(folder.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            for name, value in [('profile', example_profile()), ('trace', example_trace()), ('realization', example_realization())]:
                (folder / (name + '.json')).write_text(json.dumps(value), encoding='utf-8')
            output = folder / 'produced'
            command = [sys.executable, '-X', 'utf8', '-m', 'aegis_dc.sensor_channels', 'sample',
                       '--profile', str(folder / 'profile.json'), '--trace', str(folder / 'trace.json'),
                       '--realization', str(folder / 'realization.json'), '--output', str(output)]
            done = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(done.stdout)['state_visibility'], 'PRIVATE_EVALUATOR_ONLY')
            original = (output / 'production-private.json').read_bytes()
            produced = json.loads(original)
            self.assertEqual(produced['ledger']['records'][0]['value'], 300.5)
            public = json.loads((output / 'public-model.json').read_text(encoding='utf-8'))
            self.assertEqual(public['ledger']['records'], [])
            model = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'aegis_dc.sensor_channels',
                                    'model', '--profile', str(folder / 'profile.json')], cwd=root,
                                   env=environment, capture_output=True, text=True)
            self.assertEqual(model.returncode, 0, model.stderr)
            self.assertEqual(json.loads(model.stdout), public)
            refused = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual((output / 'production-private.json').read_bytes(), original)

    def test_primary_V6_profile_declares_sparse_fixed_and_reported_control_channels(self):
        from aegis_dc.sensor_channels import load_channel_profile
        root = Path(__file__).resolve().parents[1]
        profile = load_channel_profile(root / 'configs/full-facility-sensor-channels-v1.json')
        v6 = json.loads((root / 'configs/full-facility-mainline-reserve-v6.json').read_text(encoding='utf-8'))
        self.assertEqual(profile['ledger']['facility_id'], v6['id'])
        self.assertEqual(profile['ledger']['entity_ids'], [row['id'] for row in v6['entities']])
        self.assertEqual(profile['ledger']['records'], [])
        self.assertEqual(len(profile['measurements']), 4)
        fixed = [row for row in profile['measurements'] if row['signal'] != 'controller_temperature']
        self.assertEqual({row['target_id'] for row in fixed}, {'immersion', 'intake_pump', 'rectifier'})
        self.assertTrue(all(row['enabled'] for row in fixed))
        self.assertEqual({row['kind'] for row in profile['ledger']['sources']}, {'fixed_sensor', 'control_record'})
        self.assertEqual(len(profile['channels']), 6)


if __name__ == '__main__':
    unittest.main()
