"""Frozen public evidence qualification for instance-level false-alarm review."""

from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import EvidenceLedger, RECORD_FIELDS
from test_instance_false_alarm_review import false_alarm_input


CASES = (
    ('supported_review', 'FALSE_ALARM_REVIEWED', 0, None),
    ('missing_dossier', 'OPEN_UNCONFIRMED', 0, None),
    ('wrong_original', 'OPEN_UNCONFIRMED', 0, None),
    ('late_support', 'OPEN_UNCONFIRMED', 0, None),
    ('unknown_service', 'OPEN_UNCONFIRMED', 0, None),
    ('short_span', 'OPEN_UNCONFIRMED', 0, None),
    ('shared_origin', 'OPEN_UNCONFIRMED', 0, None),
    ('copied_support', 'OPEN_UNCONFIRMED', 0, None),
    ('expired_support', 'OPEN_UNCONFIRMED', 1, None),
    ('review_counterevidence', 'OPEN_UNCONFIRMED', 0, None),
    ('current_counterevidence', 'OPEN_UNCONFIRMED', 1, None),
    ('expired_authority', 'OPEN_UNCONFIRMED', 1, None),
    ('not_yet_authorized', 'OPEN_UNCONFIRMED', 0, None),
    ('copied_review', 'OPEN_UNCONFIRMED', 0, None),
    ('disputed_review', 'OPEN_UNCONFIRMED', 0, None),
    ('wrong_review_source', 'OPEN_UNCONFIRMED', 0, None),
    ('not_arrived_review', 'OPEN_UNCONFIRMED', 0, None),
    ('unknown_review', 'OPEN_UNCONFIRMED', 0, None),
    ('scope_mismatch', None, 0, 'Instance review source or question exceeds authority'),
    ('reused_channel_record', None, 0, 'Instance review record bindings must be unique'),
    ('blank_rationale', None, 0, 'Instance dossier rationale must be nonempty text'),
    ('duplicate_support', None, 0, 'Duplicate Instance false-alarm support IDs'),
    ('escalation_precedence', 'ESCALATED', 0, None),
    ('acceptance_precedence', 'RISK_ACCEPTED', 0, None),
)


def qualification_input(name):
    data = false_alarm_input()
    frame, profile = data['frame'], data['closure_program']['profile']
    snapshot = frame['evidence']
    records = [{key: row[key] for key in sorted(RECORD_FIELDS)} for row in snapshot['records']]
    by_id = {row['id']: row for row in records}
    flow = by_id['flow-review-31-7']
    review = by_id['false-alarm-review-31']
    dossier = profile['false_alarm_reviews'][0]
    grant = profile['authorizations'][0]
    if name == 'missing_dossier':
        profile['false_alarm_reviews'] = []
    elif name == 'wrong_original':
        dossier['original_record_id'] = 'cooling-claim-0'
    elif name == 'late_support':
        flow['arrived_at_s'] = 7.6
    elif name == 'unknown_service':
        row = by_id['service-review-31-7']
        row['value'] = None
        row['quality'] = dict(status='unknown', error_bound=None, note='No established measurement.')
    elif name == 'short_span':
        for identifier in ('flow-review-31-7', 'service-review-31-7'):
            by_id[identifier].update(observed_at_s=6.5, arrived_at_s=6.75)
    elif name in ('shared_origin', 'copied_support'):
        flow['provenance']['origin_id'] = 'flow-review-31-6'
        if name == 'copied_support':
            flow['provenance']['copied_from_record_id'] = 'flow-review-31-6'
    elif name == 'expired_support':
        by_id['flow-review-31-6']['valid_until_s'] = 8
        flow['valid_until_s'] = 8
    elif name in ('review_counterevidence', 'current_counterevidence'):
        row = deepcopy(flow)
        row.update(id='adverse-flow-33', value=70,
                   observed_at_s=7.25 if name == 'review_counterevidence' else 7.75,
                   arrived_at_s=7.5 if name == 'review_counterevidence' else 8,
                   valid_until_s=7.75 if name == 'review_counterevidence' else 10)
        row['provenance'] = dict(origin_id=row['id'], copied_from_record_id=None)
        records.append(row)
    elif name == 'expired_authority':
        grant['expires_at_s'] = 8
    elif name == 'not_yet_authorized':
        grant['starts_at_s'] = 7.6
    elif name in ('copied_review', 'disputed_review'):
        other = deepcopy(review)
        other['id'] = 'other-review-33'
        other['provenance'] = dict(origin_id='other-review-33', copied_from_record_id=None)
        if name == 'copied_review':
            review['provenance'] = dict(origin_id=other['id'], copied_from_record_id=other['id'])
        else:
            other['value'] = 'KEEP_OPEN'
        records.append(other)
    elif name == 'wrong_review_source':
        other = deepcopy(next(row for row in snapshot['static_knowledge']['sources']
                              if row['id'] == review['source_id']))
        other['id'] = 'unbound-review-source-33'
        snapshot['static_knowledge']['sources'].append(other)
        review['source_id'] = other['id']
    elif name == 'not_arrived_review':
        review['arrived_at_s'] = 8.5
    elif name == 'unknown_review':
        review['value'] = None
        review['quality'] = dict(status='unknown', error_bound=None, note='No reported disposition.')
    elif name == 'scope_mismatch':
        grant['question_ids'] = ['cooling-direct/question-0']
    elif name == 'reused_channel_record':
        other = deepcopy(profile['review_channels'][0])
        other['id'] = 'duplicate-record-channel-33'
        profile['review_channels'].append(other)
    elif name == 'blank_rationale':
        dossier['rationale'] = ' '
    elif name == 'duplicate_support':
        dossier['supporting_record_ids'].append(dossier['supporting_record_ids'][0])
    elif name in ('escalation_precedence', 'acceptance_precedence'):
        disposition = 'ESCALATE' if name == 'escalation_precedence' else 'ACCEPT_RISK'
        grant['dispositions'].append(disposition)
        other = deepcopy(review)
        other.update(id='higher-priority-review-33', value=disposition,
                     observed_at_s=7.6, arrived_at_s=7.85)
        other['provenance'] = dict(origin_id=other['id'], copied_from_record_id=None)
        records.append(other)
        channel = deepcopy(profile['review_channels'][0])
        channel.update(id='higher-priority-channel-33', record_id=other['id'])
        profile['review_channels'].insert(0, channel)
    elif name != 'supported_review':
        raise ValueError('Unknown frozen qualification case')
    ledger = dict(schema='aegisdc-evidence-ledger-v1', id=snapshot['ledger_id'],
                  facility_id=frame['facility_id'], basis='synthetic_assumption',
                  time_unit='s', **snapshot['static_knowledge'], records=records)
    frame['evidence'] = EvidenceLedger(ledger).snapshot(8)
    return data


class InstanceReviewQualificationTests(unittest.TestCase):
    def test_declared_review_evidence_and_authority_boundaries(self):
        inputs = [dict(case=name, input=qualification_input(name)) for name, _, _, _ in CASES]
        outcomes = []
        output = os.environ.get('AEGIS_ENGINEERING_RESULT_DIR')

        def save(name, value):
            if output:
                with (Path(output) / name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False, sort_keys=True)
                    stream.write('\n')

        save('frozen-public-call-input.json', inputs)
        self.public_choice_calls = 0
        try:
            for row, (name, expected, history_count, refusal) in zip(inputs, CASES):
                with self.subTest(case=name):
                    data = row['input']
                    self.public_choice_calls += 1
                    try:
                        choice = choose_work(data['frame'], data['program'], data['history'],
                            intervention_declaration=data['program']['intervention_declaration'],
                            closure_program=data['closure_program'])
                    except ValueError as error:
                        outcomes.append(dict(case=name, refused=True, error=str(error)))
                        self.assertIsNotNone(refusal)
                        self.assertIn(refusal, str(error))
                        continue
                    outcomes.append(dict(case=name, refused=False, choice=choice))
                    self.assertIsNone(refusal)
                    question = next(q for q in choice['question_lifecycle']['questions']
                                    if q['question_id'] == 'cooling-direct/question-1')
                    self.assertEqual(question['status'], expected)
                    self.assertEqual(question['question_closed'], expected in
                                     ('FALSE_ALARM_REVIEWED', 'RISK_ACCEPTED'))
                    self.assertIs(question['risk_closed'], False)
                    self.assertIs(question['physical_restoration_claim'], False)
                    self.assertEqual(len(question.get('historical_dispositions', [])), history_count)
                    if expected == 'OPEN_UNCONFIRMED':
                        self.assertEqual(question['disposition_record_ids'], [])
                    if name == 'review_counterevidence':
                        evaluation, = question['review_evaluations']
                        self.assertFalse(all(c['passed'] for c in evaluation['review_checks']))
                        self.assertTrue(all(c['passed'] for c in evaluation['current_checks']))
                    if name in ('expired_support', 'current_counterevidence'):
                        evaluation, = question['review_evaluations']
                        self.assertTrue(all(c['passed'] for c in evaluation['review_checks']))
                        self.assertFalse(all(c['passed'] for c in evaluation['current_checks']))
        finally:
            save('actual-public-choice.json', outcomes)
        self.assertEqual(self.public_choice_calls, len(CASES))


if __name__ == '__main__':
    unittest.main()
