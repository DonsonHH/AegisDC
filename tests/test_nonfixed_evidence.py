"""Nonfixed producers tested through emitted records and ledger14 snapshots."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from aegis_dc.evidence_ledger import EvidenceLedger

ROOT = Path(__file__).resolve().parents[1]


def registry():
    value = json.loads((ROOT / 'configs/full-facility-evidence-v1.json').read_text(encoding='utf-8'))
    value['records'] = []
    return value


def declared_record(**changes):
    value = dict(id='maintenance-negative', source_id='maintenance-log', target_id='filter',
        observable_id='maintenance_reported', unit='1', value=False,
        observed_at_s=-20, arrived_at_s=10, valid_until_s=0,
        quality=dict(status='reported', error_bound=None, note='An old declared negative claim; not current telemetry or truth.'),
        provenance=dict(origin_id='carried-maintenance-origin', copied_from_record_id=None))
    value.update(changes)
    return value


def completion(**changes):
    value = dict(schema='aegisdc-producer-completion-v1', origin='DECLARED_PRODUCER_FIXTURE',
        id='completion-temperature', source_id='handheld-thermometer', target_id='immersion', observable_id='temperature',
        instrument_id='declared-thermometer', qualification_declared=True,
        planned_started_at_s=0, planned_completed_at_s=1, started_at_s=0, completed_at_s=1,
        status='COMPLETED', coverage=[dict(target_id='immersion', observable_id='temperature')],
        arrival_latency_s=.25, valid_until_s=5,
        provenance=dict(origin_id='carried-inspection-origin', copied_from_record_id=None),
        basis='synthetic_assumption', source_note='Producer-fixture declaration, not M1 work or professional22 execution.')
    value.update(changes)
    return value


def numeric_model():
    return dict(schema='aegisdc-handheld-model-v1', id='declared-temperature-model', kind='numeric',
        signal_id='immersion.coolant_temperature', unit='K', reported_error_bound=.5,
        quality_note='Declared instrument bound; not calibrated field truth.', basis='synthetic_assumption',
        source_note='Synthetic hand-held model, actual private bias/noise recorded separately.')


class NonfixedEvidenceTests(unittest.TestCase):
    def test_late_history_keeps_its_old_time_and_expiry_in_the_real_ledger(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer
        producer = NonfixedEvidenceProducer(registry())
        message = declared_record()
        self.assertIsNone(producer.publish_report(message, as_of_s=9))
        record = producer.publish_report(message, as_of_s=10)
        self.assertEqual(record, message)
        ledger = EvidenceLedger(registry())
        self.assertEqual(ledger.ingest(record), 'ADDED')
        snapshot = ledger.snapshot(10)
        self.assertEqual(snapshot['current_record_ids'], [])
        self.assertEqual(snapshot['records'][0]['age_s'], 30)
        self.assertEqual(snapshot['records'][0]['availability'], 'expired')
        source = next(row for row in producer.source_descriptions() if row['source_id']=='maintenance-log')
        self.assertEqual(source['time_model'], 'HISTORICAL_CONTEXT_ONLY')
        self.assertEqual(source['independence'], 'NOT_ESTABLISHED')


    def test_completion_status_and_availability_gate_precede_any_private_sample(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer, SavedRunSignals
        producer = NonfixedEvidenceProducer(registry())
        private = SavedRunSignals(ROOT / 'deliberately-missing-private-run')
        realization = dict(seed=17, bias=0, noise_half_width=.25)
        for status in ('INCOMPLETE', 'ABORTED', 'REJECTED'):
            with self.subTest(status=status):
                self.assertIsNone(producer.publish_completion(completion(status=status, completed_at_s=None),
                    model=numeric_model(), private_signals=private, realization=realization, as_of_s=100))
        self.assertIsNone(producer.publish_completion(completion(qualification_declared=False),
            model=numeric_model(), private_signals=private, realization=realization, as_of_s=100))
        for time in (.5, 1, 1.2499999999999998):
            self.assertIsNone(producer.publish_completion(completion(), model=numeric_model(),
                private_signals=private, realization=realization, as_of_s=time))
        with self.assertRaises(ValueError):
            producer.publish_completion(dict(id='old-work', status='completed',
                effect='ENGINEERING_WORK_RECORD_ONLY_NO_REPAIR_OR_EVIDENCE'), model=numeric_model(),
                private_signals=private, realization=realization, as_of_s=100)



    def test_same_V6_measurement_uses_completion_point_after_a_changing_interval(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer, SavedRunSignals
        producer = NonfixedEvidenceProducer(registry())
        private = SavedRunSignals(ROOT / 'evidence/mainline/engineering/13-replay/capture-04/combined-episode-CLI/trajectory')
        token = completion(planned_started_at_s=65.5, planned_completed_at_s=97.49999999999999,
            started_at_s=65.5, completed_at_s=97.5, arrival_latency_s=.5, valid_until_s=120)
        realization = dict(seed=17, bias=0, noise_half_width=0)
        self.assertIsNone(producer.publish_completion(token, model=numeric_model(), private_signals=private,
            realization=realization, as_of_s=97.5))
        record = producer.publish_completion(token, model=numeric_model(), private_signals=private,
            realization=realization, as_of_s=98)
        # Literals come from the frozen cf9 combined240 saved trajectory, not the producer.
        self.assertEqual(record['value'], 299.80494269918245)
        self.assertNotEqual(record['value'], 306.33863056744127)  # physical value at start65.5
        self.assertNotEqual(record['value'], 299.7638719034682)   # physical value at delivery98
        self.assertEqual(record['observed_at_s'], 97.5)
        self.assertEqual(record['arrived_at_s'], 98)
        self.assertEqual(record['quality'], dict(status='bounded', error_bound=.5, note=numeric_model()['quality_note']))
        self.assertEqual(record['provenance'], token['provenance'])
        self.assertEqual(set(record), {'id','source_id','target_id','observable_id','unit','value',
            'observed_at_s','arrived_at_s','valid_until_s','quality','provenance'})
        ledger = EvidenceLedger(registry());ledger.ingest(record)
        self.assertEqual(ledger.snapshot(98)['records'][0]['age_s'], .5)
        audit = producer.private_audit()['events'][0]
        self.assertEqual(audit['raw_planned_completed_at_s'], 97.49999999999999)
        self.assertEqual(audit['effective_completed_at_s'], 97.5)
        self.assertEqual(audit['source_sample_at_s'], 97.5)
        self.assertEqual(audit['private_source']['code_identity']['git_commit'], 'cf9b33900d8f349b9a8145c042bbffe03503c858')



    def test_manual_negative_missing_and_unconfirmed_quality_are_not_truth_inference(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer
        producer = NonfixedEvidenceProducer(registry())
        ledger = EvidenceLedger(registry())
        for identifier, value in [('negative', False), ('uncertain', None)]:
            message = declared_record(id=identifier, source_id='operator-report', observable_id='vibration_reported',
                value=value, observed_at_s=1, arrived_at_s=2, valid_until_s=10,
                quality=dict(status='unknown', error_bound=None, note='Unconfirmed declared report, regardless of hidden condition.'))
            emitted = producer.publish_report(message, as_of_s=2)
            ledger.ingest(emitted)
            self.assertEqual(emitted['quality'], message['quality'])
        records = {r['id']:r for r in ledger.snapshot(2)['records']}
        self.assertIs(records['negative']['value'], False)
        self.assertEqual(records['negative']['availability'], 'current')
        self.assertIsNone(records['uncertain']['value'])
        self.assertEqual(records['uncertain']['availability'], 'missing')

    def test_work_order_carries_a_future_alarm_root_without_private_chain_lookup(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer
        producer = NonfixedEvidenceProducer(registry());ledger = EvidenceLedger(registry())
        copy = declared_record(id='copy-first', source_id='work-order-inbox', target_id='immersion',
            observable_id='temperature', unit='K', value=310, observed_at_s=1, arrived_at_s=2, valid_until_s=20,
            quality=dict(status='bounded', error_bound=.5, note='Copied declared claim, not an independent sample.'),
            provenance=dict(origin_id='carried-shared-root', copied_from_record_id='alarm-later'))
        ledger.ingest(producer.publish_report(copy, as_of_s=2));first = ledger.snapshot(2)
        self.assertEqual(first['records'][0]['provenance'], copy['provenance'])
        self.assertEqual(first['provenance_issues'], [])
        alarm = deepcopy(copy);alarm.update(id='alarm-later', source_id='point_temperature', arrived_at_s=10,
            provenance=dict(origin_id='carried-shared-root', copied_from_record_id=None))
        ledger.ingest(alarm)
        self.assertEqual(ledger.snapshot(2), first)
        received = ledger.snapshot(10)
        self.assertEqual(received['independence'], 'NOT_ESTABLISHED')
        group = next(g for g in received['correlation_groups'] if g['kind']=='reported_origin')
        self.assertEqual(group['record_ids'], ['alarm-later','copy-first'])


if __name__ == '__main__':
    unittest.main()
