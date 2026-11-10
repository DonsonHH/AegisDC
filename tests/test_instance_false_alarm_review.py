"""A reviewed false alarm requires an instance-bound dossier at both evidence clocks."""

import json
import os
from pathlib import Path
import unittest

from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import EvidenceLedger, RECORD_FIELDS

ROOT = Path(__file__).resolve().parents[1]


def false_alarm_input():
    data = json.loads((ROOT / 'tests/fixtures/39c-two-instance-public-seed-21.json').read_bytes())
    frame, history, closure = data['frame'], data['history'], data['closure_program']
    history['question_instances'].append(dict(
        id='cooling-direct/question-1', template_id='cooling-direct', slot=1,
        origin_id='cooling-second-origin-20', trigger_record_id='cooling-second-origin-20',
        opened_at_s=5.5))
    closure['schema'] = 'aegisdc-instance-closure-program-v2'
    profile = closure['profile']
    profile['schema'] = 'aegisdc-instance-closure-profile-v2'
    profile['authorizations'] = [dict(
        id='false-alarm-authority-31', source_id='false-alarm-reviewer-31',
        question_ids=['cooling-direct/question-1'], dispositions=['FALSE_ALARM'],
        starts_at_s=0, expires_at_s=10, basis='synthetic_assumption',
        source_note='Synthetic management review authority, not physical equipment control.')]
    profile['review_channels'] = [dict(
        id='false-alarm-channel-31', question_id='cooling-direct/question-1',
        source_id='false-alarm-reviewer-31', target_id='intake_pump',
        observable_id='false-alarm-disposition-31', authorization_id='false-alarm-authority-31',
        record_id='false-alarm-review-31')]
    support_ids = ['flow-review-31-6', 'flow-review-31-7',
                   'service-review-31-6', 'service-review-31-7']
    profile['false_alarm_reviews'] = [dict(
        review_record_id='false-alarm-review-31', question_id='cooling-direct/question-1',
        original_record_id='cooling-second-origin-20', supporting_record_ids=support_ids,
        rationale='Finite review of this original suspicion against condition and service readings; no fault-cause or restoration claim.')]
    snapshot = frame['evidence']
    static = snapshot['static_knowledge']
    static['observables'].append(dict(
        id='false-alarm-disposition-31', quantity='category', value_type='text', unit='1'))
    static['sources'].append(dict(
        id='false-alarm-reviewer-31', kind='human_report', basis='synthetic_assumption',
        target_ids=['intake_pump'], observable_ids=['false-alarm-disposition-31'],
        dependency_group=None, source_note='Declared finite review source.'))
    records = [{key: row[key] for key in sorted(RECORD_FIELDS)} for row in snapshot['records']]
    for time in (6, 7):
        for prefix, source, target, observable, unit, value in (
            ('flow', 'intake-flow-record', 'intake_pump', 'lake_mass_flow', 'kg/s', 99.8),
            ('service', 'joint-service-record', 'critical_service', 'service_delivered_rate', '1', 1)
        ):
            identifier = f'{prefix}-review-31-{time}'
            records.append(dict(
                id=identifier, source_id=source, target_id=target, observable_id=observable,
                unit=unit, value=value, observed_at_s=time, arrived_at_s=time + .25,
                valid_until_s=10, quality=dict(status='bounded', error_bound=0,
                    note='Hand-specified finite reading, no field calibration.'),
                provenance=dict(origin_id=identifier, copied_from_record_id=None)))
    records.append(dict(
        id='false-alarm-review-31', source_id='false-alarm-reviewer-31', target_id='intake_pump',
        observable_id='false-alarm-disposition-31', unit='1', value='FALSE_ALARM',
        observed_at_s=7.5, arrived_at_s=7.75, valid_until_s=10,
        quality=dict(status='reported', error_bound=None, note='Explicit original-record and evidence review.'),
        provenance=dict(origin_id='false-alarm-review-31', copied_from_record_id=None)))
    ledger = dict(schema='aegisdc-evidence-ledger-v1', id=snapshot['ledger_id'],
                  facility_id=frame['facility_id'], basis='synthetic_assumption', time_unit='s',
                  **static, records=records)
    frame['as_of_s'] = 8
    frame['evidence'] = EvidenceLedger(ledger).snapshot(8)
    return data


class InstanceFalseAlarmReviewTests(unittest.TestCase):
    def test_instance_dossier_closes_management_only_with_support_at_both_clocks(self):
        data = false_alarm_input()
        output = os.environ.get('AEGIS_ENGINEERING_RESULT_DIR')

        def save(name, value):
            if output:
                with (Path(output) / name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False, sort_keys=True)
                    stream.write('\n')

        save('frozen-public-call-input.json', data)
        self.public_choice_calls = 1
        choice = choose_work(data['frame'], data['program'], data['history'],
                             intervention_declaration=data['program']['intervention_declaration'],
                             closure_program=data['closure_program'])
        save('actual-public-choice.json', choice)
        question = next(row for row in choice['question_lifecycle']['questions']
                        if row['question_id'] == 'cooling-direct/question-1')
        self.assertEqual(question['status'], 'FALSE_ALARM_REVIEWED')
        self.assertIs(question['question_closed'], True)
        self.assertIs(question['risk_closed'], False)
        self.assertIs(question['physical_restoration_claim'], False)
        self.assertIs(question['own_recheck']['passed'], False)
        self.assertEqual(question['disposition_record_ids'], ['false-alarm-review-31'])
        self.assertEqual(question['supporting_record_ids'],
                         ['flow-review-31-6', 'flow-review-31-7',
                          'service-review-31-6', 'service-review-31-7'])
        evaluation, = question['review_evaluations']
        self.assertEqual(evaluation['original_record_id'], 'cooling-second-origin-20')
        self.assertEqual((evaluation['review_at_s'], evaluation['current_at_s']), (7.5, 8))
        self.assertIs(evaluation['passed'], True)
        self.assertTrue(all(row['passed'] for row in evaluation['review_checks']))
        self.assertTrue(all(row['passed'] for row in evaluation['current_checks']))
        self.assertFalse(any(row['prerequisites_met'] for row in choice['stage_gates']
                             if row['task_id'].endswith('-1')))


if __name__ == '__main__':
    unittest.main()
