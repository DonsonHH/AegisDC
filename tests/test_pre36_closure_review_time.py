"""A review uses its own evidence clock and still needs valid current checks."""
from copy import deepcopy
import unittest

from test_verified_closure import fixture, reframe


def review_fixture():
    _, program, ledger, nominal = fixture()
    program['intervention_feedback'] = []
    ledger['observables'].append(dict(id='cooling-review', quantity='category', value_type='text', unit='1'))
    ledger['sources'].append(dict(id='authorized-reviewer', kind='human_report', basis='synthetic_assumption',
        target_ids=['intake_pump'], observable_ids=['cooling-review'], dependency_group=None,
        source_note='Declared research review channel.'))
    ledger['records'].append(dict(id='false-alarm-review', source_id='authorized-reviewer', target_id='intake_pump',
        observable_id='cooling-review', unit='1', value='FALSE_ALARM', observed_at_s=5.5, arrived_at_s=5.75,
        valid_until_s=10, quality=dict(status='reported', error_bound=None, note='Finite evidence-bound review.'),
        provenance=dict(origin_id='review-fa', copied_from_record_id=None)))
    program['profile']['review_channels'] = [dict(id='cooling-disposition', question_id='cooling',
        source_id='authorized-reviewer', target_id='intake_pump', observable_id='cooling-review', authorization_id='risk-owner')]
    program['profile']['authorizations'] = [dict(id='risk-owner', source_id='authorized-reviewer', question_ids=['cooling'],
        dispositions=['FALSE_ALARM'], starts_at_s=0, expires_at_s=10, basis='synthetic_assumption',
        source_note='Explicit synthetic review authority.')]
    program['profile']['false_alarm_reviews'] = [dict(review_record_id='false-alarm-review', question_id='cooling',
        supporting_record_ids=['service-review-4','service-review-5','verify-flow-4','verify-flow-5'],
        rationale='Original finite condition and service records support this review.')]
    return program, ledger, nominal


def add_fresh_current_records(ledger):
    originals = [r for r in ledger['records'] if r['id'] in {'service-review-4','verify-flow-4'}]
    for observed in (6, 7):
        for original in originals:
            row = deepcopy(original)
            row.update(id=original['source_id']+'-fresh-'+str(observed), observed_at_s=observed,
                arrived_at_s=observed+.25, valid_until_s=10)
            row['provenance'] = dict(origin_id=row['id'], copied_from_record_id=None)
            ledger['records'].append(row)


def add_adverse_record(ledger, observed, arrived, valid_until):
    row = deepcopy(next(r for r in ledger['records'] if r['id']=='verify-flow-5'))
    row.update(id='adverse-flow', value=.01, observed_at_s=observed, arrived_at_s=arrived, valid_until_s=valid_until)
    row['provenance'] = dict(origin_id='adverse-flow-origin', copied_from_record_id=None)
    ledger['records'].append(row)


class ReviewTimeEvidenceTests(unittest.TestCase):
    def test_expired_now_support_remains_valid_at_review_when_current_evidence_is_fresh(self):
        from aegis_dc.verified_closure import assess_closure
        program, ledger, nominal = review_fixture()
        for row in ledger['records']:
            if row['id']!='false-alarm-review':row['valid_until_s']=6
        add_fresh_current_records(ledger)
        frame = reframe(ledger, nominal, 7.5)
        before = deepcopy((frame, program))
        question = assess_closure(frame, program)['questions'][0]
        self.assertTrue(all(c['passed'] for c in question['review_evaluations'][0]['review_checks']))
        self.assertTrue(all(c['passed'] for c in question['review_evaluations'][0]['current_checks']))
        self.assertEqual(question['status'], 'FALSE_ALARM_REVIEWED')
        self.assertFalse(question['risk_closed'])
        self.assertEqual((frame, program), before)

    def test_omitted_counterevidence_known_at_review_cannot_be_erased_by_later_expiry(self):
        from aegis_dc.verified_closure import assess_closure
        program, ledger, nominal = review_fixture()
        add_adverse_record(ledger, 5.25, 5.3, 6)
        question = assess_closure(reframe(ledger, nominal, 7.5), program)['questions'][0]
        review = question['review_evaluations'][0]
        self.assertFalse(all(c['passed'] for c in review['review_checks']))
        self.assertTrue(all(c['passed'] for c in review['current_checks']))
        self.assertFalse(question['question_closed'])
        self.assertNotEqual(question['status'], 'FALSE_ALARM_REVIEWED')

    def test_later_counterevidence_does_not_rewrite_review_but_still_blocks_current_closure(self):
        from aegis_dc.verified_closure import assess_closure
        program, ledger, nominal = review_fixture()
        add_adverse_record(ledger, 6.25, 6.3, 10)
        question = assess_closure(reframe(ledger, nominal, 7.5), program)['questions'][0]
        review = question['review_evaluations'][0]
        self.assertTrue(all(c['passed'] for c in review['review_checks']))
        self.assertFalse(all(c['passed'] for c in review['current_checks']))
        self.assertFalse(question['question_closed'])
        self.assertFalse(question['risk_closed'])


if __name__=='__main__':unittest.main()
