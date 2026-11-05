"""Nonfixed producers tested through emitted records and ledger14 snapshots."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import subprocess
import sys
import os
import tempfile

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


def detection_registry():
    value = registry()
    value['observables'].append(dict(id='hot_reported', quantity='binary', value_type='boolean', unit='1'))
    value['sources'].append(dict(id='handheld-threshold-probe', kind='handheld', basis='synthetic_assumption',
        target_ids=['immersion'], observable_ids=['hot_reported'], dependency_group=None,
        source_note='Declared synthetic threshold inspection, not a field diagnosis.'))
    return value


def detection_model(**changes):
    value = dict(schema='aegisdc-handheld-model-v1', id='declared-threshold-model', kind='binary_detection',
        signal_id='immersion.coolant_temperature', unit='1', threshold=300, threshold_unit='K',
        sensitivity=.8, false_positive_rate=.1,
        quality_note='Declared performance assumption, no per-sample truth certificate.',
        basis='synthetic_assumption', source_note='Sensitivity/FPR apply to the declared signal threshold, not a full fault label.')
    value.update(changes)
    return value


def profile_document(base=None, models=None):
    return dict(schema='aegisdc-nonfixed-profile-v1', registry=registry() if base is None else base,
                models=[] if models is None else models)


def producer_plan(**changes):
    value = dict(schema='aegisdc-nonfixed-plan-v1', reported_records=[], external_records=[], completion_requests=[])
    value.update(changes)
    return value


def model_binding(model=None):
    return dict(source_id='handheld-thermometer',target_id='immersion',observable_id='temperature',
                instrument_id='declared-thermometer',model=numeric_model() if model is None else model)


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



    def test_false_positive_and_false_negative_keep_the_same_declared_quality_and_origin(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer, SavedRunSignals
        private = SavedRunSignals(ROOT / 'evidence/mainline/engineering/13-replay/capture-04/combined-episode-CLI/trajectory')
        token = completion(source_id='handheld-threshold-probe', observable_id='hot_reported',
            planned_started_at_s=65.5, planned_completed_at_s=97.5, started_at_s=65.5, completed_at_s=97.5,
            arrival_latency_s=0, valid_until_s=120, coverage=[dict(target_id='immersion', observable_id='hot_reported')])
        realization = dict(seed=19, bias=0, noise_half_width=0)
        missed = NonfixedEvidenceProducer(detection_registry())
        missed_record = missed.publish_completion(token, model=detection_model(threshold=290, sensitivity=0),
            private_signals=private, realization=realization, as_of_s=97.5)
        false_alarm = NonfixedEvidenceProducer(detection_registry())
        false_record = false_alarm.publish_completion(token, model=detection_model(threshold=310, false_positive_rate=1),
            private_signals=private, realization=realization, as_of_s=97.5)
        self.assertIs(missed_record['value'], False)  # true saved signal299.8049 >=290, missed by declared detector
        self.assertIs(false_record['value'], True)   # saved signal299.8049 <310, false positive under declared model
        self.assertEqual(missed_record['quality'], false_record['quality'])
        self.assertEqual(missed_record['quality']['status'], 'reported')
        self.assertEqual(missed_record['provenance'], false_record['provenance'])
        self.assertEqual(missed_record['id'], false_record['id'])
        self.assertTrue(missed.private_audit()['events'][0]['latent_signal_above_threshold'])
        self.assertFalse(false_alarm.private_audit()['events'][0]['latent_signal_above_threshold'])
        ledger = EvidenceLedger(detection_registry());ledger.ingest(missed_record)
        public = json.dumps(ledger.snapshot(97.5))
        for forbidden in ('latent_signal', 'private_draw', 'private_source', 'seed', 'false_negative', 'false_positive'):
            self.assertNotIn(forbidden, public)



    def test_declared_indeterminate_completion_records_null_without_reading_private_data(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer, SavedRunSignals
        producer = NonfixedEvidenceProducer(registry())
        model = numeric_model();model.pop('reported_error_bound');model.update(kind='unknown',
            quality_note='Declared indeterminate observation; no usable value, not a normal reading.')
        private = SavedRunSignals(ROOT / 'missing-private-run-is-never-read')
        self.assertIsNone(producer.publish_completion(completion(), model=model, private_signals=private,
            realization=None, as_of_s=1))
        record = producer.publish_completion(completion(), model=model, private_signals=private,
            realization=None, as_of_s=1.25)
        self.assertIsNone(record['value'])
        self.assertEqual(record['quality'], dict(status='unknown', error_bound=None, note=model['quality_note']))
        ledger = EvidenceLedger(registry());ledger.ingest(record)
        self.assertEqual(ledger.snapshot(1.25)['current_record_ids'], [])
        self.assertEqual(ledger.snapshot(1.25)['records'][0]['availability'], 'missing')
        self.assertIsNone(producer.private_audit()['events'][0]['private_source'])



    def test_world_callbacks_cannot_replace_the_authorized_saved_signal_boundary(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer
        class UndeclaredWorldCallback:
            called = False
            def sample_at(self, *args, **kwargs):
                self.called = True
                raise AssertionError('An undeclared world callback was executed')
        callback = UndeclaredWorldCallback();producer = NonfixedEvidenceProducer(registry())
        realization = dict(seed=1, bias=0, noise_half_width=0)
        self.assertIsNone(producer.publish_completion(completion(), model=numeric_model(),
            private_signals=callback, realization=realization, as_of_s=0))
        with self.assertRaises(ValueError):
            producer.publish_completion(completion(), model=numeric_model(),
                private_signals=callback, realization=realization, as_of_s=2)
        self.assertFalse(callback.called)



    def test_query_count_does_not_redraw_or_refresh_a_completed_observation(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer, SavedRunSignals
        producer = NonfixedEvidenceProducer(registry())
        signals = SavedRunSignals(ROOT / 'evidence/mainline/engineering/13-replay/capture-04/combined-episode-CLI/trajectory')
        realization = dict(seed=31, bias=0, noise_half_width=.25)
        one = producer.publish_completion(completion(), model=numeric_model(), private_signals=signals,
            realization=realization, as_of_s=1.25)
        two = producer.publish_completion(completion(), model=numeric_model(), private_signals=signals,
            realization=realization, as_of_s=1000)
        self.assertEqual(one, two)
        ledger = EvidenceLedger(registry())
        self.assertEqual(ledger.ingest(one), 'ADDED')
        self.assertEqual(ledger.ingest(two), 'ALREADY_PRESENT')
        self.assertEqual(ledger.snapshot(1000)['records'][0]['availability'], 'expired')
        self.assertEqual(ledger.snapshot(1000)['current_record_ids'], [])

    def test_public_quality_is_not_recomputed_from_a_private_calibration_mismatch(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer, SavedRunSignals
        signals = SavedRunSignals(ROOT / 'evidence/mainline/engineering/13-replay/capture-04/combined-episode-CLI/trajectory')
        correct = NonfixedEvidenceProducer(registry());wrong = NonfixedEvidenceProducer(registry())
        a = correct.publish_completion(completion(), model=numeric_model(), private_signals=signals,
            realization=dict(seed=7,bias=0,noise_half_width=0), as_of_s=2)
        b = wrong.publish_completion(completion(), model=numeric_model(), private_signals=signals,
            realization=dict(seed=7,bias=5,noise_half_width=0), as_of_s=2)
        self.assertAlmostEqual(b['value']-a['value'], 5)
        self.assertEqual(a['quality'], b['quality'])
        self.assertEqual(a['provenance'], b['provenance'])
        self.assertFalse(wrong.private_audit()['events'][0]['declared_bound_contains_signal'])

    def test_private_access_state_and_source_fingerprints_do_not_become_record_fields(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer, SavedRunSignals
        blocked = SavedRunSignals(ROOT / 'evidence/mainline/engineering/11-coupled/fixtures-b135ecff-01/gate-before-arrival')
        normal = SavedRunSignals(ROOT / 'evidence/mainline/engineering/13-replay/capture-04/normal-600s/trajectory')
        token = completion(planned_started_at_s=120, planned_completed_at_s=121,
            started_at_s=120, completed_at_s=121, arrival_latency_s=.5, valid_until_s=130)
        a = NonfixedEvidenceProducer(registry());b = NonfixedEvidenceProducer(registry())
        realization = dict(seed=5,bias=0,noise_half_width=.25)
        for producer, private in [(a,blocked),(b,normal)]:
            self.assertIsNone(producer.publish_completion(token,model=numeric_model(),private_signals=private,
                realization=realization,as_of_s=121))
        left = a.publish_completion(token,model=numeric_model(),private_signals=blocked,realization=realization,as_of_s=121.5)
        right = b.publish_completion(token,model=numeric_model(),private_signals=normal,realization=realization,as_of_s=121.5)
        self.assertEqual(left,right)  # same authorized T despite private gate states differing
        self.assertNotEqual(a.private_audit()['events'][0]['private_source']['run_sha256'],
                            b.private_audit()['events'][0]['private_source']['run_sha256'])
        x=EvidenceLedger(registry());y=EvidenceLedger(registry());x.ingest(left);y.ingest(right)
        self.assertEqual(x.snapshot(121.5),y.snapshot(121.5))

    def test_coverage_and_exact_saved_coordinate_never_forward_peek(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer, SavedRunSignals
        producer = NonfixedEvidenceProducer(registry())
        missing = SavedRunSignals(ROOT / 'missing-private-input')
        self.assertIsNone(producer.publish_completion(completion(coverage=[]),model=numeric_model(),
            private_signals=missing,realization=dict(seed=1,bias=0,noise_half_width=0),as_of_s=10))
        signals = SavedRunSignals(ROOT / 'evidence/mainline/engineering/13-replay/capture-04/combined-episode-CLI/trajectory')
        with self.assertRaisesRegex(ValueError,'No exact saved point'):
            producer.publish_completion(completion(planned_started_at_s=65.5,planned_completed_at_s=97.49999999999999,
                started_at_s=65.5,completed_at_s=97.49999999999999,arrival_latency_s=.5,valid_until_s=120),
                model=numeric_model(),private_signals=signals,realization=dict(seed=1,bias=0,noise_half_width=0),as_of_s=98)
        self.assertEqual(producer.private_audit()['events'],[])

    def test_positive_latency_below_one_ulp_is_never_rounded_to_early_delivery(self):
        from aegis_dc.nonfixed_evidence import NonfixedEvidenceProducer, SavedRunSignals
        import math
        producer=NonfixedEvidenceProducer(registry());model=numeric_model();model.pop('reported_error_bound');model.update(kind='unknown')
        token=completion(arrival_latency_s=1e-17)
        private=SavedRunSignals(ROOT/'unread-private-input')
        self.assertIsNone(producer.publish_completion(token,model=model,private_signals=private,realization=None,as_of_s=1))
        later=math.nextafter(1,math.inf)
        record=producer.publish_completion(token,model=model,private_signals=private,realization=None,as_of_s=later)
        self.assertEqual(record['observed_at_s'],1)
        self.assertEqual(record['arrived_at_s'],later)



    def test_executable_session_supports_history_and_manual_without_fixed_sources(self):
        from aegis_dc.nonfixed_evidence import NonfixedSession
        base = registry();base['sources']=[s for s in base['sources'] if s['kind'] not in {'fixed_sensor','control_record'}]
        manual = declared_record(id='manual-negative',source_id='operator-report',observable_id='vibration_reported',
            value=False,observed_at_s=1,arrived_at_s=2,valid_until_s=20,
            quality=dict(status='reported',error_bound=None,note='Declared negative report, not backend truth.'))
        plan=producer_plan(reported_records=[declared_record(),manual])
        session=NonfixedSession(profile_document(base),plan,private_signals=None)
        self.assertEqual([r['id'] for r in session.snapshot(9)['records']],['manual-negative'])
        at10=session.snapshot(10)
        self.assertEqual(at10['current_record_ids'],['manual-negative'])
        self.assertEqual({r['id']:r['availability'] for r in at10['records']},
                         {'manual-negative':'current','maintenance-negative':'expired'})
        self.assertFalse(any(s['kind']=='fixed_sensor' for s in at10['static_knowledge']['sources']))
        descriptors=session.public_models()
        self.assertEqual(descriptors['schema'],'aegisdc-nonfixed-public-models-v1')
        history=next(x for x in descriptors['source_time_models'] if x['source_id']=='maintenance-log')
        self.assertEqual(history['time_model'],'HISTORICAL_CONTEXT_ONLY')
        self.assertNotIn('seed',json.dumps(descriptors))



    def test_invalid_model_and_completion_tags_are_typed_validation_refusals(self):
        from aegis_dc.nonfixed_evidence import NonfixedSession
        broken = numeric_model();broken['kind']=[]
        with self.assertRaises(ValueError):
            NonfixedSession(profile_document(models=[model_binding(broken)]),producer_plan())
        plan=producer_plan(completion_requests=[dict(completion=completion(status=[]),
            model_id=numeric_model()['id'],realization=dict(seed=1,bias=0,noise_half_width=0))])
        with self.assertRaises(ValueError):
            NonfixedSession(profile_document(models=[model_binding()]),plan)



    def test_standalone_CLI_publishes_only_the_snapshot_and_refuses_output_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);profile=folder/'profile.json';plan=folder/'plan.json';output=folder/'fresh-result'
            profile.write_text(json.dumps(profile_document()),encoding='utf-8')
            plan.write_text(json.dumps(producer_plan(reported_records=[declared_record()])),encoding='utf-8')
            command=[sys.executable,'-B','-X','utf8','-m','aegis_dc.nonfixed_evidence','--profile',str(profile),
                     '--plan',str(plan),'--as-of','10','--output',str(output)]
            environment=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
            result=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)
            public=json.loads(result.stdout)
            self.assertEqual(public,json.loads((output/'public-snapshot.json').read_text(encoding='utf-8')))
            self.assertEqual(public['schema'],'aegisdc-evidence-snapshot-v1')
            self.assertEqual(public['records'][0]['age_s'],30)
            self.assertEqual(public['current_record_ids'],[])
            for key in ('seed','private_source','private_audit','input_sha256','world'):
                self.assertNotIn(key,public)
            before={p.relative_to(output).as_posix():p.read_bytes() for p in output.rglob('*') if p.is_file()}
            refused=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(refused.returncode,2)
            self.assertEqual(before,{p.relative_to(output).as_posix():p.read_bytes() for p in output.rglob('*') if p.is_file()})



    def test_session_and_CLI_keep_completion_audit_out_of_public_messages(self):
        from aegis_dc.nonfixed_evidence import NonfixedSession, SavedRunSignals
        profile=profile_document(models=[model_binding()])
        token=completion(planned_started_at_s=65.5,planned_completed_at_s=97.49999999999999,
            started_at_s=65.5,completed_at_s=97.5,arrival_latency_s=.5,valid_until_s=120)
        plan=producer_plan(completion_requests=[dict(completion=token,model_id=numeric_model()['id'],
            realization=dict(seed=913,bias=0,noise_half_width=0))])
        private_dir=ROOT/'evidence/mainline/engineering/13-replay/capture-04/combined-episode-CLI/trajectory'
        session=NonfixedSession(profile,plan,private_signals=SavedRunSignals(private_dir))
        self.assertEqual(session.snapshot(97.5)['records'],[])
        after=session.snapshot(98)
        self.assertEqual(after['records'][0]['value'],299.80494269918245)
        self.assertNotIn('realization',json.dumps(session.public_models()))
        self.assertNotIn('seed',json.dumps(session.public_models()))
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);p=folder/'profile.json';r=folder/'private-plan.json';p.write_text(json.dumps(profile),encoding='utf-8');r.write_text(json.dumps(plan),encoding='utf-8')
            command=[sys.executable,'-B','-X','utf8','-m','aegis_dc.nonfixed_evidence','--profile',str(p),'--plan',str(r),
                '--private-run',str(private_dir),'--as-of','98','--output',str(folder/'output')]
            result=subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),after)
            audit=json.loads((folder/'output/private-audit.json').read_text(encoding='utf-8'))
            self.assertEqual(audit['events'][0]['private_realization']['seed'],913)
            self.assertNotIn('cf9b3390',result.stdout)
            self.assertNotIn('run_sha256',result.stdout)

    def test_CLI_preserves_large_integer_decision_time_without_binary64_cast(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);p=folder/'profile.json';r=folder/'plan.json';p.write_text(json.dumps(profile_document()),encoding='utf-8');r.write_text(json.dumps(producer_plan(reported_records=[declared_record()])),encoding='utf-8')
            result=subprocess.run([sys.executable,'-B','-X','utf8','-m','aegis_dc.nonfixed_evidence','--profile',str(p),
                '--plan',str(r),'--as-of','9007199254740993','--output',str(folder/'output')],cwd=ROOT,
                env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)
            public=json.loads(result.stdout)
            self.assertEqual(public['as_of_s'],9007199254740993)
            self.assertEqual(public['records'][0]['age_s'],9007199254741013)



    def test_external_channel_records_cannot_bypass_the_handheld_completion_gate(self):
        from aegis_dc.nonfixed_evidence import NonfixedSession
        ungated = declared_record(id='not-a-completed-measurement',source_id='handheld-thermometer',target_id='immersion',
            observable_id='temperature',unit='K',value=300,observed_at_s=0,arrived_at_s=0,valid_until_s=10,
            quality=dict(status='bounded',error_bound=.5,note='An externally asserted handheld result without a token.'))
        with self.assertRaisesRegex(ValueError,'completion|nonfixed|upstream'):
            NonfixedSession(profile_document(),producer_plan(external_records=[ungated]))


if __name__ == '__main__':
    unittest.main()
