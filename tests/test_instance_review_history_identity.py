"""Historical review projection must preserve the actual instance opening identity."""

import json
import os
from pathlib import Path
import unittest

from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import EvidenceLedger, RECORD_FIELDS

ROOT = Path(__file__).resolve().parents[1]


class InstanceReviewHistoryIdentityTests(unittest.TestCase):
    def test_preopening_review_cannot_recreate_an_earlier_instance(self):
        data = json.loads((ROOT / 'tests/fixtures/39c-two-instance-public-seed-21.json').read_bytes())
        frame, policy, history, closure = (
            data[key] for key in ('frame', 'program', 'history', 'closure_program')
        )
        frame['as_of_s'] = 6
        history.update(issued=[], work_feedback=[], question_instances=[], intervention_feedback=[])
        closure.update(schema='aegisdc-instance-closure-program-v2', intervention_feedback=[])
        profile = closure['profile']
        profile.update(schema='aegisdc-instance-closure-profile-v2', false_alarm_reviews=[])
        question_id = 'cooling-direct/question-0'
        record_id = 'review-before-actual-opening-29'
        source_id = 'review-owner-29'
        observable_id = 'review-disposition-29'
        profile['authorizations'] = [dict(
            id='authority-29', source_id=source_id, question_ids=[question_id],
            dispositions=['ESCALATE'], starts_at_s=0, expires_at_s=4,
            basis='synthetic_assumption', source_note='Synthetic authority expires before first dispatch.')]
        profile['review_channels'] = [dict(
            id='channel-29', question_id=question_id, source_id=source_id,
            target_id='intake_pump', observable_id=observable_id,
            authorization_id='authority-29', record_id=record_id)]
        snapshot = frame['evidence']
        static = snapshot['static_knowledge']
        static['sources'].append(dict(
            id=source_id, kind='human_report', basis='synthetic_assumption',
            target_ids=['intake_pump'], observable_ids=[observable_id], dependency_group=None,
            source_note='Synthetic review that predates the actual question instance.'))
        static['observables'].append(dict(
            id=observable_id, quantity='category', value_type='text', unit='1'))
        records = [{key: row[key] for key in sorted(RECORD_FIELDS)}
                   for row in snapshot['records'] if row['id'] != 'flow-after-clean']
        old_trigger = next(row for row in records if row['id'] == 'cooling-claim-0')
        old_trigger['valid_until_s'] = 4
        new_trigger = next(row for row in records if row['id'] == 'cooling-second-origin-20')
        new_trigger.update(observed_at_s=5.5, arrived_at_s=6)
        records.append(dict(
            id=record_id, source_id=source_id, target_id='intake_pump', observable_id=observable_id,
            unit='1', value='ESCALATE', observed_at_s=2, arrived_at_s=2, valid_until_s=8,
            quality=dict(status='reported', error_bound=None, note='Not a decision on a future problem.'),
            provenance=dict(origin_id=record_id, copied_from_record_id=None)))
        ledger = dict(schema='aegisdc-evidence-ledger-v1', id=snapshot['ledger_id'],
                      facility_id=frame['facility_id'], basis='synthetic_assumption',
                      time_unit='s', **static, records=records)
        frame['evidence'] = EvidenceLedger(ledger).snapshot(6)
        output = os.environ.get('AEGIS_ENGINEERING_RESULT_DIR')

        def save(name, value):
            if output:
                with (Path(output) / name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False, sort_keys=True)
                    stream.write('\n')

        save('frozen-public-call-input.json', data)
        self.public_choice_calls = 1
        choice = choose_work(frame, policy, history,
                             intervention_declaration=policy['intervention_declaration'],
                             closure_program=closure)
        save('actual-public-choice.json', choice)
        self.assertEqual(len(choice['question_instances']), 1)
        actual = choice['question_instances'][0]
        self.assertEqual((actual['id'], actual['origin_id'], actual['trigger_record_id'], actual['opened_at_s']),
                         (question_id, 'cooling-second-origin-20', 'cooling-second-origin-20', 6))
        reviewed = choice['question_lifecycle']['questions'][0]
        self.assertEqual(reviewed['status'], 'OPEN_UNCONFIRMED')
        self.assertIs(reviewed['question_closed'], False)
        self.assertEqual(reviewed['disposition_record_ids'], [])
        self.assertEqual(reviewed.get('historical_dispositions', []), [],
                         'A review before the actual problem opening must not manufacture history')


if __name__ == '__main__':
    unittest.main()
