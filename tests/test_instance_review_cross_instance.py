"""A disposition bound to one problem instance cannot close its sibling instance."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import EvidenceLedger, RECORD_FIELDS

ROOT = Path(__file__).resolve().parents[1]


class InstanceReviewCrossInstanceTests(unittest.TestCase):
    def test_disposition_is_limited_to_its_exact_instance(self):
        seed = json.loads((ROOT / 'tests/fixtures/39c-two-instance-public-seed-21.json').read_bytes())
        frame = deepcopy(seed['frame'])
        program = deepcopy(seed['program'])
        history = deepcopy(seed['history'])
        closure = deepcopy(seed['closure_program'])
        first_question = 'cooling-direct/question-0'
        second_question = 'cooling-direct/question-1'
        first_stages = {'cooling-direct/action-0', 'cooling-direct/recheck-0'}

        history['issued'] = [row for row in history['issued'] if row['candidate_id'] not in first_stages]
        history['work_feedback'] = [row for row in history['work_feedback'] if row['task_id'] not in first_stages]
        history['intervention_feedback'] = []
        closure['schema'] = 'aegisdc-instance-closure-program-v2'
        closure['profile']['schema'] = 'aegisdc-instance-closure-profile-v2'
        closure['intervention_feedback'] = []
        closure['profile']['authorizations'] = [dict(
            id='cross-instance-owner-27', source_id='cross-instance-review-source-27',
            question_ids=[first_question], dispositions=['ACCEPT_RISK'], starts_at_s=0,
            expires_at_s=8, basis='synthetic_assumption',
            source_note='Finite synthetic authority for exactly one problem instance.')]
        closure['profile']['review_channels'] = [dict(
            id='cross-instance-channel-27', question_id=first_question,
            source_id='cross-instance-review-source-27', target_id='intake_pump',
            observable_id='cross-instance-disposition-27',
            authorization_id='cross-instance-owner-27', record_id='accept-risk-question-0-27')]
        closure['profile']['false_alarm_reviews'] = []

        snapshot = frame['evidence']
        static = deepcopy(snapshot['static_knowledge'])
        static['observables'].append(dict(id='cross-instance-disposition-27', quantity='category',
            value_type='text', unit='1'))
        static['sources'].append(dict(id='cross-instance-review-source-27', kind='human_report',
            basis='synthetic_assumption', target_ids=['intake_pump'],
            observable_ids=['cross-instance-disposition-27'], dependency_group=None,
            source_note='Synthetic management record for exact-instance scope qualification.'))
        records = [{key: row[key] for key in RECORD_FIELDS} for row in snapshot['records']]
        records.append(dict(id='accept-risk-question-0-27', source_id='cross-instance-review-source-27',
            target_id='intake_pump', observable_id='cross-instance-disposition-27', unit='1',
            value='ACCEPT_RISK', observed_at_s=5.5, arrived_at_s=5.5, valid_until_s=8,
            quality=dict(status='reported', error_bound=None, note='Synthetic instance-scoped disposition.'),
            provenance=dict(origin_id='accept-risk-question-0-27', copied_from_record_id=None)))
        ledger = dict(schema='aegisdc-evidence-ledger-v1', id=snapshot['ledger_id'],
            facility_id=frame['facility_id'], basis='synthetic_assumption', time_unit='s',
            **static, records=records)
        frame['evidence'] = EvidenceLedger(ledger).snapshot(5.5)

        output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        def save(name, value):
            if output is not None:
                with (output / name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                    stream.write('\n')

        save('frozen-public-call-input.json', dict(frame=frame, program=program,
            history=history, closure_program=closure))
        self.public_choice_calls = 1
        choice = choose_work(frame, program, history,
            intervention_declaration=program['intervention_declaration'], closure_program=closure)
        save('actual-public-choice.json', choice)

        questions = {row['question_id']: row for row in choice['question_lifecycle']['questions']}
        accepted = questions[first_question]
        sibling = questions[second_question]
        self.assertEqual(accepted['status'], 'RISK_ACCEPTED')
        self.assertTrue(accepted['question_closed'])
        self.assertFalse(accepted['risk_closed'])
        self.assertEqual(accepted['disposition_record_ids'], ['accept-risk-question-0-27'])
        self.assertEqual(sibling['status'], 'OPEN_UNCONFIRMED')
        self.assertFalse(sibling['question_closed'])
        self.assertFalse(sibling['risk_closed'])
        self.assertEqual(sibling['disposition_record_ids'], [])
        self.assertFalse(sibling['physical_restoration_claim'])
        self.assertEqual(accepted['template_id'], sibling['template_id'])
        templates = {row['id']: row for row in program['templates']}
        accepted_target = templates[accepted['template_id']]['task']['target_id']
        sibling_target = templates[sibling['template_id']]['task']['target_id']
        self.assertEqual(accepted_target, 'intake_pump')
        self.assertEqual(sibling_target, accepted_target)


if __name__ == '__main__':
    unittest.main()
