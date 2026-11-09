"""Expired authority at the current review time cannot accept an instance risk."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.dispatch_policy import choose_work
from aegis_dc.evidence_ledger import EvidenceLedger, RECORD_FIELDS

ROOT = Path(__file__).resolve().parents[1]


class InstanceReviewAuthorityExpiryTests(unittest.TestCase):
    def test_expired_current_authority_does_not_close_question(self):
        seed = json.loads((ROOT / 'tests/fixtures/39c-two-instance-public-seed-21.json').read_bytes())
        frame = deepcopy(seed['frame'])
        program = deepcopy(seed['program'])
        history = deepcopy(seed['history'])
        closure = deepcopy(seed['closure_program'])
        closure['schema'] = 'aegisdc-instance-closure-program-v2'
        profile = closure['profile']
        profile['schema'] = 'aegisdc-instance-closure-profile-v2'
        profile['authorizations'] = [dict(id='expiry-risk-owner-25', source_id='expiry-review-owner-25',
            question_ids=['cooling-direct/question-1'], dispositions=['ACCEPT_RISK'], starts_at_s=0,
            expires_at_s=7, basis='synthetic_assumption',
            source_note='Finite synthetic management authority for expiry-boundary qualification.')]
        profile['review_channels'] = [dict(id='expiry-review-channel-25',
            question_id='cooling-direct/question-1', source_id='expiry-review-owner-25',
            target_id='intake_pump', observable_id='expiry-disposition-25',
            authorization_id='expiry-risk-owner-25', record_id='accept-risk-expiry-25')]
        profile['false_alarm_reviews'] = []

        snapshot = frame['evidence']
        static = deepcopy(snapshot['static_knowledge'])
        static['observables'].append(dict(id='expiry-disposition-25', quantity='category',
            value_type='text', unit='1'))
        static['sources'].append(dict(id='expiry-review-owner-25', kind='human_report',
            basis='synthetic_assumption', target_ids=['intake_pump'],
            observable_ids=['expiry-disposition-25'], dependency_group=None,
            source_note='Synthetic authority evidence for a public-interface expiry negative.'))
        records = [{key: row[key] for key in RECORD_FIELDS} for row in snapshot['records']]
        records.append(dict(id='accept-risk-expiry-25', source_id='expiry-review-owner-25',
            target_id='intake_pump', observable_id='expiry-disposition-25', unit='1',
            value='ACCEPT_RISK', observed_at_s=5.5, arrived_at_s=5.5, valid_until_s=8,
            quality=dict(status='reported', error_bound=None, note='Synthetic disposition; still current at expiry check.'),
            provenance=dict(origin_id='accept-risk-expiry-25', copied_from_record_id=None)))
        ledger = dict(schema='aegisdc-evidence-ledger-v1', id=snapshot['ledger_id'],
            facility_id=frame['facility_id'], basis='synthetic_assumption', time_unit='s',
            **static, records=records)
        frame['as_of_s'] = 7
        frame['evidence'] = EvidenceLedger(ledger).snapshot(7)
        history['question_instances'].append(dict(id='cooling-direct/question-1',
            template_id='cooling-direct', slot=1, origin_id='cooling-second-origin-20',
            trigger_record_id='cooling-second-origin-20', opened_at_s=5.5))

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

        reviewed = next(row for row in choice['question_lifecycle']['questions']
                        if row['question_id'] == 'cooling-direct/question-1')
        self.assertEqual(frame['as_of_s'], 7)
        self.assertEqual(reviewed['status'], 'OPEN_UNCONFIRMED')
        self.assertFalse(reviewed['question_closed'])
        self.assertFalse(reviewed['risk_closed'])
        self.assertEqual(reviewed['disposition_record_ids'], [])
        self.assertFalse(reviewed['physical_restoration_claim'])


if __name__ == '__main__':
    unittest.main()
