"""Independent decision-time examples at the public evidence ledger seam."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def example():
    return {
        'schema': 'aegisdc-evidence-ledger-v1', 'id': 'literal-ledger',
        'facility_id': 'literal-synthetic-facility', 'basis': 'synthetic_assumption',
        'time_unit': 's', 'entity_ids': ['plate_hx'],
        'observables': [{'id': 'temperature', 'quantity': 'temperature', 'value_type': 'number', 'unit': 'K'}],
        'sources': [{'id': 'fixed-temperature', 'kind': 'fixed_sensor',
                     'basis': 'synthetic_assumption',
                     'target_ids': ['plate_hx'], 'observable_ids': ['temperature'],
                     'dependency_group': None, 'source_note': 'Sparse declared fixture instrument.'}],
        'records': [{'id': 'r-temperature', 'source_id': 'fixed-temperature',
                     'target_id': 'plate_hx', 'observable_id': 'temperature', 'unit': 'K',
                     'value': 300, 'observed_at_s': 1, 'arrived_at_s': 2, 'valid_until_s': 5,
                     'quality': {'status': 'bounded', 'error_bound': .5,
                                 'note': 'Declared synthetic absolute bound, not field calibration.'},
                     'provenance': {'origin_id': 'origin-temperature-1', 'copied_from_record_id': None}}],
    }


class EvidenceLedgerTests(unittest.TestCase):
    def test_record_arrives_at_exact_time_and_one_ULP_future_is_hidden(self):
        from aegis_dc.evidence_ledger import EvidenceLedger
        ledger = EvidenceLedger(example())
        before = ledger.snapshot(math.nextafter(2, -math.inf))
        self.assertEqual(before['records'], [])
        self.assertEqual(before['current_record_ids'], [])
        at = ledger.snapshot(2)
        self.assertEqual(at['current_record_ids'], ['r-temperature'])
        self.assertEqual(at['records'][0]['value'], 300)
        self.assertEqual(at['records'][0]['age_s'], 1)
        self.assertEqual(ledger.snapshot(5)['current_record_ids'], [])
        self.assertEqual(ledger.snapshot(5)['records'][0]['availability'], 'expired')

    def test_late_arrival_does_not_refresh_old_observation_and_missing_is_auditable(self):
        from aegis_dc.evidence_ledger import EvidenceLedger
        document = example()
        document['records'][0].update(observed_at_s=-100, arrived_at_s=4, valid_until_s=-90)
        missing = deepcopy(document['records'][0])
        missing.update(id='missing', observed_at_s=3, arrived_at_s=3, valid_until_s=8, value=None)
        missing['quality'] = {'status': 'unknown', 'error_bound': None, 'note': 'No reading received.'}
        missing['provenance']['origin_id'] = 'origin-missing'
        document['records'].append(missing)
        snapshot = EvidenceLedger(document).snapshot(4)
        self.assertEqual(snapshot['current_record_ids'], [])
        self.assertEqual([(row['id'], row['availability'], row['age_s']) for row in snapshot['records']],
                         [('missing', 'missing', 1), ('r-temperature', 'expired', 104)])
        self.assertEqual(snapshot['records'][0]['quality']['status'], 'unknown')

    def test_received_copies_keep_known_origin_before_original_arrives_or_exists(self):
        from aegis_dc.evidence_ledger import EvidenceLedger
        document = example()
        original = document['records'][0]
        original.update(id='original', arrived_at_s=6)
        for identifier, arrival in [('work-order-1', 2), ('work-order-2', 3)]:
            copy = deepcopy(original)
            copy.update(id=identifier, arrived_at_s=arrival)
            copy['provenance']['copied_from_record_id'] = 'original'
            document['records'].append(copy)
        without_original = deepcopy(document)
        without_original['records'] = without_original['records'][1:]
        snapshot = EvidenceLedger(document).snapshot(3)
        self.assertEqual(snapshot, EvidenceLedger(without_original).snapshot(3))
        self.assertEqual(snapshot['correlation_groups'], [
            {'kind': 'reported_origin', 'origin_id': 'origin-temperature-1',
             'record_ids': ['work-order-1', 'work-order-2']},
            {'kind': 'reported_copy_reference', 'copied_from_record_id': 'original',
             'record_ids': ['work-order-1', 'work-order-2']}])
        self.assertEqual(snapshot['records'][0]['provenance']['copied_from_record_id'], 'original')
        self.assertEqual(snapshot['independence'], 'NOT_ESTABLISHED')

    def test_future_conflict_cannot_change_earlier_snapshot_even_one_ULP_before_arrival(self):
        from aegis_dc.evidence_ledger import EvidenceLedger
        baseline = example()
        baseline['sources'].append(dict(baseline['sources'][0], id='handheld', kind='handheld'))
        document = deepcopy(baseline)
        contradiction = deepcopy(document['records'][0])
        contradiction.update(id='opposite', source_id='handheld', value=310, arrived_at_s=4)
        contradiction['provenance']['origin_id'] = 'origin-handheld'
        document['records'].append(contradiction)
        before = math.nextafter(4, -math.inf)
        self.assertEqual(EvidenceLedger(document).snapshot(before), EvidenceLedger(baseline).snapshot(before))
        snapshot = EvidenceLedger(document).snapshot(4)
        self.assertEqual(snapshot['conflicts'], [
            {'record_ids': ['opposite', 'r-temperature'], 'target_id': 'plate_hx',
             'observable_id': 'temperature', 'observed_at_s': 1, 'kind': 'disjoint_declared_bounds'}])
        # Sequential readings are not contradictions about one observation epoch.
        document['records'][1]['observed_at_s'] = 2
        self.assertEqual(EvidenceLedger(document).snapshot(4)['conflicts'], [])

    def test_unknown_quality_and_source_dependency_remain_explicit_without_truth_claim(self):
        from aegis_dc.evidence_ledger import EvidenceLedger
        document = example()
        document['sources'][0]['dependency_group'] = 'same-calibration'
        document['sources'].append(dict(document['sources'][0], id='second-fixed'))
        second = deepcopy(document['records'][0])
        second.update(id='uncertain', source_id='second-fixed', value=350)
        second['quality'] = {'status': 'unknown', 'error_bound': None, 'note': 'Calibration unavailable.'}
        second['provenance']['origin_id'] = 'different-observation'
        document['records'].append(second)
        snapshot = EvidenceLedger(document).snapshot(2)
        self.assertEqual(snapshot['records'][1]['quality']['status'], 'unknown')
        self.assertEqual(snapshot['conflicts'][0]['kind'], 'different_reported_values')
        self.assertEqual(snapshot['correlation_groups'], [
            {'kind': 'declared_source_dependency', 'dependency_group': 'same-calibration',
             'record_ids': ['r-temperature', 'uncertain']}])

    def test_closed_schema_refuses_invalid_units_types_times_and_private_payloads(self):
        from aegis_dc.evidence_ledger import EvidenceLedger
        cases = [
            ('schema', 'unknown-v0'), ('time_unit', 'h'), ('entity_ids', ['plate_hx', 'plate_hx']),
            ('basis', 'live_truth'), ('records.0.value', True), ('records.0.value', math.nan),
            ('records.0.value', lambda: 'private plant'), ('records.0.arrived_at_s', True),
            ('records.0.arrived_at_s', 0), ('records.0.observed_at_s', math.inf),
            ('records.0.valid_until_s', 1), ('records.0.unit', 'degC'),
            ('records.0.quality.error_bound', -1), ('records.0.quality.status', 'certain_truth'),
            ('records.0.target_id', 'private_unregistered_asset'), ('records.0.source_id', 'no-source'),
            ('records.0.provenance.origin_id', ''), ('sources.0.kind', 'plant_state'),
            ('sources.0.target_ids', ['private_unregistered_asset']),
            ('observables.0.unit', 'W'), ('observables.0.value_type', 'python_object'),
            ('sources.0.kind', []), ('sources.0.basis', []), ('observables.0.quantity', []),
            ('observables.0.value_type', []), ('records.0.quality.status', []),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=repr(value)):
                document = example()
                owner = document
                parts = path.split('.')
                for part in parts[:-1]:
                    owner = owner[int(part)] if isinstance(owner, list) else owner[part]
                owner[parts[-1]] = value
                with self.assertRaises(ValueError):
                    EvidenceLedger(document)
        document = example()
        document['private_state'] = {'temperature': 300}
        with self.assertRaises(ValueError):
            EvidenceLedger(document)
        for instant in (True, None, math.inf, math.nan, '2'):
            with self.subTest(as_of=instant), self.assertRaises(ValueError):
                EvidenceLedger(example()).snapshot(instant)

    def test_numeric_zero_negative_binary_false_and_missing_are_distinct(self):
        from aegis_dc.evidence_ledger import EvidenceLedger
        document = example()
        document['observables'] = [
            {'id': 'temperature', 'quantity': 'temperature_offset', 'value_type': 'number', 'unit': 'K'},
            {'id': 'alarm', 'quantity': 'binary', 'value_type': 'boolean', 'unit': '1'}]
        document['sources'][0]['observable_ids'].append('alarm')
        prototype = document['records'].pop()
        for identifier, value, observable in [('zero', 0, 'temperature'), ('negative', -2, 'temperature'),
                                                ('false', False, 'alarm'), ('absent', None, 'temperature')]:
            row = deepcopy(prototype)
            row.update(id=identifier, value=value, observable_id=observable,
                       unit='1' if observable == 'alarm' else 'K')
            row['provenance']['origin_id'] = identifier
            if observable == 'alarm' or value is None:
                row['quality'] = {'status': 'unknown', 'error_bound': None, 'note': 'No calibrated quality.'}
            document['records'].append(row)
        result = EvidenceLedger(document).snapshot(2)
        self.assertEqual(result['current_record_ids'], ['false', 'negative', 'zero'])
        self.assertEqual([row['value'] for row in result['records']], [None, False, -2, 0])
        invalid = deepcopy(document)
        invalid['records'][2]['value'] = 0
        with self.assertRaises(ValueError):
            EvidenceLedger(invalid)

    def test_ingest_is_idempotent_conflicting_ID_is_atomic_and_snapshots_are_detached(self):
        from aegis_dc.evidence_ledger import EvidenceLedger, validate_ledger
        document = example()
        ledger = EvidenceLedger(document)
        unchanged = ledger.snapshot(2)
        self.assertEqual(ledger.ingest(deepcopy(document['records'][0])), 'ALREADY_PRESENT')
        conflicting = deepcopy(document['records'][0])
        conflicting['value'] = 301
        with self.assertRaisesRegex(ValueError, 'duplicate record id'):
            ledger.ingest(conflicting)
        self.assertEqual(ledger.snapshot(2), unchanged)
        new = deepcopy(document['records'][0])
        new.update(id='new', arrived_at_s=3)
        new['provenance']['origin_id'] = 'new-origin'
        self.assertEqual(ledger.ingest(new), 'ADDED')
        new['value'] = -999
        document['records'][0]['value'] = -999
        changed_snapshot = ledger.snapshot(3)
        changed_snapshot['records'][0]['quality']['status'] = 'corrupted'
        changed_snapshot['static_knowledge']['sources'][0]['target_ids'].clear()
        self.assertEqual([row['value'] for row in ledger.snapshot(3)['records']], [300, 300])
        validated = validate_ledger(example())
        validated['records'][0]['value'] = -1
        self.assertEqual(ledger.snapshot(2), unchanged)
        duplicates = example()
        duplicates['records'].append(deepcopy(duplicates['records'][0]))
        self.assertEqual(len(EvidenceLedger(duplicates).snapshot(2)['records']), 1)

    def test_custom_objects_and_cycles_are_rejected_without_executing_copy_hooks(self):
        from aegis_dc.evidence_ledger import EvidenceLedger
        executed = []

        class PrivateObject:
            def __deepcopy__(self, memo):
                executed.append('private callback')
                return 123

        document = example()
        document['records'][0]['value'] = PrivateObject()
        with self.assertRaises(ValueError):
            EvidenceLedger(document)
        self.assertEqual(executed, [])
        cyclic = example()
        cyclic['records'][0]['value'] = cyclic
        with self.assertRaises(ValueError):
            EvidenceLedger(cyclic)

    def test_loader_and_actual_CLI_return_only_snapshot_and_refuse_overwrite(self):
        from aegis_dc.evidence_ledger import load_ledger
        environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_file, output = directory / 'input.json', directory / 'out'
            input_file.write_text(json.dumps(example()), encoding='utf-8')
            command = [sys.executable, '-X', 'utf8', '-m', 'aegis_dc', 'evidence',
                       '--ledger', str(input_file), '--as-of', '2', '--output', str(output)]
            done = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            expected = load_ledger(input_file).snapshot(2)
            self.assertEqual(json.loads(done.stdout), expected)
            saved = (output / 'snapshot.json').read_bytes()
            self.assertEqual(json.loads(saved), expected)
            refused = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2)
            self.assertIn('exists', refused.stderr)
            self.assertEqual((output / 'snapshot.json').read_bytes(), saved)
            input_file.write_text('{"schema":1,"schema":2}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
                load_ledger(input_file)

    def test_full_V6_static_fixture_is_sparse_and_has_independent_literal_outcomes(self):
        from aegis_dc.evidence_ledger import load_ledger
        fixture = ROOT / 'configs/full-facility-evidence-v1.json'
        document = json.loads(fixture.read_text(encoding='utf-8'))
        v6 = json.loads((ROOT / 'configs/full-facility-mainline-reserve-v6.json').read_text(encoding='utf-8'))
        self.assertEqual(document['facility_id'], v6['id'])
        self.assertEqual(document['entity_ids'], [entity['id'] for entity in v6['entities']])
        fixed = [source for source in document['sources'] if source['kind'] == 'fixed_sensor']
        self.assertEqual([source['id'] for source in fixed], ['point_temperature', 'point_flow', 'point_power'])
        self.assertEqual(len({target for source in fixed for target in source['target_ids']}), 3)
        self.assertEqual({source['kind'] for source in document['sources']},
                         {'asset_record', 'maintenance_history', 'fixed_sensor', 'human_report',
                          'work_order', 'control_record', 'handheld'})
        ledger = load_ledger(fixture)
        self.assertEqual(ledger.snapshot(11)['current_record_ids'],
                         ['design-rating', 'maintenance-history', 'human-false', 'control-offline', 'copy-before-alarm'])
        self.assertEqual(ledger.snapshot(math.nextafter(18, -math.inf))['conflicts'], [])
        result = ledger.snapshot(18)
        self.assertEqual([row['record_ids'] for row in result['conflicts']],
                         [['alarm-t10', 'handheld-conflict'], ['copy-before-alarm', 'handheld-conflict']])
        self.assertEqual(len(result['current_record_ids']), 7)
        self.assertEqual(ledger.snapshot(26)['current_record_ids'], ['design-rating', 'maintenance-history'])

    def test_visible_copy_with_mismatched_origin_is_related_and_cycle_is_reported_only_when_visible(self):
        from aegis_dc.evidence_ledger import EvidenceLedger
        document = example()
        a = document['records'][0]
        a['provenance']['copied_from_record_id'] = 'b'
        b = deepcopy(a)
        b.update(id='b', arrived_at_s=3)
        b['provenance'] = {'origin_id': 'different-claimed-origin', 'copied_from_record_id': a['id']}
        document['records'].append(b)
        before = EvidenceLedger(document).snapshot(math.nextafter(3, -math.inf))
        no_b = deepcopy(document)
        no_b['records'].pop()
        self.assertEqual(before, EvidenceLedger(no_b).snapshot(before['as_of_s']))
        self.assertEqual(before['provenance_issues'], [])
        after = EvidenceLedger(document).snapshot(3)
        self.assertIn({'kind': 'visible_copy_link', 'record_ids': ['b', 'r-temperature']},
                      after['correlation_groups'])
        self.assertEqual(after['provenance_issues'], [
            {'kind': 'copy_origin_mismatch', 'record_ids': ['b', 'r-temperature']},
            {'kind': 'visible_copy_cycle', 'record_ids': ['b', 'r-temperature']}])


if __name__ == '__main__':
    unittest.main()
