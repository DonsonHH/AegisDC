"""Author declared ticket17 inputs; no plant state or fault schedule is read."""
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'configs/full-facility-nonfixed-evidence-v1.json'
PLAN = 'configs/full-facility-nonfixed-private-plan-v1.json'
RUNBOOK = 'docs/mainline/17-nonfixed-runbook.json'
PRIVATE_RUN = 'evidence/mainline/engineering/13-replay/capture-04/combined-episode-CLI/trajectory'
PAIRED_RUNS = [
    'evidence/mainline/engineering/11-coupled/fixtures-b135ecff-01/gate-before-arrival',
    'evidence/mainline/engineering/13-replay/capture-04/normal-600s/trajectory',
]


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def build(root=ROOT):
    registry = json.loads((root / 'configs/full-facility-evidence-v1.json').read_text(encoding='utf-8'))
    registry['id'] = 'V6-nonfixed-engineering-v1'
    registry['records'] = []
    registry['observables'].append(dict(id='hot_reported', quantity='binary', value_type='boolean', unit='1'))
    registry['sources'].append(dict(id='handheld-threshold-probe', kind='handheld', basis='synthetic_assumption',
        target_ids=['immersion'], observable_ids=['hot_reported'], dependency_group='declared-handheld-session',
        source_note='Synthetic threshold-device fixture; coverage is the named coolant signal only.'))
    numeric = dict(schema='aegisdc-handheld-model-v1', id='coolant-numeric', kind='numeric',
        signal_id='immersion.coolant_temperature', unit='K', reported_error_bound=.5,
        quality_note='Declared synthetic bound; per-sample error and field calibration are not certified.',
        basis='synthetic_assumption', source_note='Synthetic instrument model, not a site instrument specification.')
    unknown = {k:v for k,v in numeric.items() if k != 'reported_error_bound'}
    unknown.update(id='coolant-indeterminate', kind='unknown', quality_note='Declared indeterminate inspection; value remains missing.')
    binary = dict(schema='aegisdc-handheld-model-v1', id='threshold-miss', kind='binary_detection',
        signal_id='immersion.coolant_temperature', unit='1', threshold=290, threshold_unit='K',
        sensitivity=0, false_positive_rate=.1,
        quality_note='Declared synthetic threshold detection performance; no per-sample truth certificate.',
        basis='synthetic_assumption', source_note='Deterministic endpoint fixture for sensitivity/FPR behavior, not an accuracy estimate.')
    false_alarm = deepcopy(binary)
    false_alarm.update(id='threshold-false-alarm', threshold=310, sensitivity=.8, false_positive_rate=1)

    def binding(model, instrument, observable='temperature', source='handheld-thermometer'):
        return dict(source_id=source, target_id='immersion', observable_id=observable, instrument_id=instrument, model=model)

    profile = dict(schema='aegisdc-nonfixed-profile-v1', registry=registry, models=[
        binding(numeric, 'declared-thermometer'), binding(unknown, 'declared-indeterminate-probe'),
        binding(binary, 'declared-miss-probe', 'hot_reported', 'handheld-threshold-probe'),
        binding(false_alarm, 'declared-false-alarm-probe', 'hot_reported', 'handheld-threshold-probe')])

    def record(identifier, source, target, observable, unit, value, observed, arrived, expiry, quality,
               origin=None, copied=None):
        return dict(id=identifier, source_id=source, target_id=target, observable_id=observable, unit=unit,
            value=value, observed_at_s=observed, arrived_at_s=arrived, valid_until_s=expiry, quality=quality,
            provenance=dict(origin_id=origin or 'declared-'+identifier, copied_from_record_id=copied))

    reported = dict(status='reported', error_bound=None, note='Declared unconfirmed claim, not a backend fault label.')
    bounded = dict(status='bounded', error_bound=.5, note='Copied declared bound; a second message is not an independent sample.')
    reports = [
        record('asset-zero', 'asset-register', 'rectifier', 'nameplate_power', 'W', 0, -100, -50, None,
               dict(status='bounded', error_bound=0, note='Explicit synthetic zero rating, not missing data.')),
        record('late-history', 'maintenance-log', 'filter', 'maintenance_reported', '1', False, -20, 10, 0, reported),
        record('manual-negative', 'operator-report', 'filter', 'vibration_reported', '1', False, 1, 2, 120, reported),
        record('manual-unknown', 'operator-report', 'filter', 'vibration_reported', '1', None, 3, 4, 120,
               dict(status='unknown', error_bound=None, note='Unconfirmed report has no usable value.')),
        record('copy-first', 'work-order-inbox', 'immersion', 'temperature', 'K', 310, 20, 30, 110, bounded,
               origin='carried-shared-alarm-root', copied='alarm-later'),
    ]
    external = [record('alarm-later', 'point_temperature', 'immersion', 'temperature', 'K', 310, 20, 80, 110,
                       bounded, origin='carried-shared-alarm-root')]

    def completion(identifier, model, instrument, *, source='handheld-thermometer', observable='temperature',
                   started=65.5, completed=97.5, planned=97.49999999999999, latency=.5, status='COMPLETED',
                   qualified=True, coverage=True):
        token = dict(schema='aegisdc-producer-completion-v1', origin='DECLARED_PRODUCER_FIXTURE', id=identifier,
            source_id=source, target_id='immersion', observable_id=observable, instrument_id=instrument,
            qualification_declared=qualified, planned_started_at_s=started, planned_completed_at_s=planned,
            started_at_s=started, completed_at_s=completed, status=status,
            coverage=[dict(target_id='immersion', observable_id=observable)] if coverage else [],
            arrival_latency_s=latency, valid_until_s=120,
            provenance=dict(origin_id='declared-inspection-session', copied_from_record_id=None),
            basis='synthetic_assumption', source_note='Typed producer fixture only; travel/skills/resources and real execution await21/22.')
        return dict(completion=token, model_id=model,
                    realization=None if model=='coolant-indeterminate' else dict(seed=913, bias=0, noise_half_width=0))

    requests = [completion('completed-numeric', 'coolant-numeric', 'declared-thermometer'),
        completion('completed-indeterminate', 'coolant-indeterminate', 'declared-indeterminate-probe',
                   started=49, completed=50, planned=50, latency=.25),
        completion('detector-miss', 'threshold-miss', 'declared-miss-probe', source='handheld-threshold-probe', observable='hot_reported'),
        completion('detector-false-alarm', 'threshold-false-alarm', 'declared-false-alarm-probe', source='handheld-threshold-probe', observable='hot_reported')]
    for status in ('ABORTED', 'REJECTED', 'INCOMPLETE'):
        requests.append(completion('no-result-'+status.lower(), 'coolant-numeric', 'declared-thermometer', status=status, completed=None))
    requests.extend([completion('no-result-unqualified', 'coolant-numeric', 'declared-thermometer', qualified=False),
                     completion('no-result-uncovered', 'coolant-numeric', 'declared-thermometer', coverage=False)])
    plan = dict(schema='aegisdc-nonfixed-plan-v1', reported_records=reports, external_records=external, completion_requests=requests)
    book = dict(schema='aegisdc-nonfixed-runbook-v1', classification='ENGINEERING_NOT_RESEARCH',
        profile=PROFILE, private_plan=PLAN, private_saved_run=PRIVATE_RUN, paired_private_runs=PAIRED_RUNS,
        saved_run_interpretation=dict(physical_source_commit='cf9b33900d8f349b9a8145c042bbffe03503c858',
            historical_maximum_step_s=1.0, historical_duration_s=240.0,
            adapter_sampling='EXACT_SAVED_POINT_AT_EFFECTIVE_COMPLETION',
            new_physics_execution=False, numerical_domain_qualification=False, professional_execution_connected=False),
        snapshots=[dict(id=name, as_of_s=time, current_record_ids=ids) for name,time,ids in [
            ('before-report',1,['asset-zero']), ('negative-report',2,['asset-zero','manual-negative']),
            ('late-history',10,['asset-zero','manual-negative']), ('copy-first',30,['asset-zero','manual-negative','copy-first']),
            ('before-completion',97.5,['asset-zero','manual-negative','copy-first','alarm-later']),
            ('before-arrival',97.99999999999999,['asset-zero','manual-negative','copy-first','alarm-later']),
            ('arrived',98,['asset-zero','manual-negative','copy-first','alarm-later','completed-numeric','detector-false-alarm','detector-miss']),
            ('expired',120,['asset-zero'])]],
        literal_checks=dict(start_time_s=65.5, start_temperature_K=306.33863056744127,
            raw_planned_completion_s=97.49999999999999, effective_completion_s=97.5,
            completion_temperature_K=299.80494269918245, arrival_time_s=98,
            arrival_temperature_K=299.7638719034682, late_history_age_at_10_s=30,
            detector_miss=False, detector_false_alarm=True, registered_research_trials=0),
        CLI=[dict(id='arrived', expected_exit=0),dict(id='before-arrival', expected_exit=0),
             dict(id='no-fixed', expected_exit=0),dict(id='ungated-handheld', expected_exit=1),
             dict(id='overwrite', expected_exit=2)],
        deferred=['professional path/skills/tool/resource execution21/22','risk/posterior18',
                  'action effects23','registered comparison30+','AI/RSI eligibility38+'])
    return {PROFILE:profile, PLAN:plan, RUNBOOK:book}


if __name__ == '__main__':
    for name, value in build().items():
        (ROOT/name).write_bytes(encoded(value))
