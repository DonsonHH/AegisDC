"""Actual management endpoints keep current selection, historical evidence and physics apart."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class InstanceManagementQualificationTests(unittest.TestCase):
    def test_expiry_history_escalation_and_actual_evidence_false_alarm_clocks(self):
        spec = json.loads((ROOT/'tests/fixtures/39c-instance-management-qualification-52.json').read_bytes())
        base = json.loads((ROOT/spec['base_input']).read_bytes())
        output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        self.facility_calls = self.completed_native_horizons = self.returned_decisions = 0
        self.completed_native_duration_s = 0
        rows, identity = [], None

        def save(directory, name, value):
            if directory is not None:
                with (directory/name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, indent=2, allow_nan=False)
                    stream.write('\n')

        try:
            for case in spec['cases']:
                row = dict(case=case, passed=False)
                rows.append(row)
                with self.subTest(case=case):
                    data = deepcopy(base)
                    dispatch = data['dispatch_program']
                    ledger = dispatch['evidence_ledger']
                    profile = dispatch['closure_program']['profile']
                    grant = profile['authorizations'][0]
                    review = next(r for r in ledger['records'] if r['id'] == 'accept-risk-instance1-21')
                    data['business_program']['id'] = 'management52-' + case
                    if case == 'accepted-then-expired':
                        grant['expires_at_s'] = spec['accepted_then_expired_at_s']
                    elif case == 'historical-only':
                        grant['expires_at_s'] = spec['historical_only_authority_expires_at_s']
                        review['observed_at_s'] = spec['historical_only_observed_at_s']
                        review['arrived_at_s'] = spec['historical_only_arrived_at_s']
                    elif case == 'escalation-priority':
                        source, observable, authority = 'escalation-source-52', 'escalation-disposition-52', 'escalation-authority-52'
                        ledger['sources'].append(dict(id=source, kind='human_report', basis='synthetic_assumption',
                            target_ids=['intake_pump'], observable_ids=[observable], dependency_group=None,
                            source_note='Independent synthetic management escalation source.'))
                        ledger['observables'].append(dict(id=observable, quantity='category', value_type='text', unit='1'))
                        escalation = deepcopy(review)
                        escalation.update(id=spec['escalation_record_id'], source_id=source, observable_id=observable, value='ESCALATE',
                            provenance=dict(origin_id=spec['escalation_record_id'], copied_from_record_id=None))
                        ledger['records'].append(escalation)
                        profile['authorizations'].append(dict(id=authority, source_id=source,
                            question_ids=['cooling-direct/question-1'], dispositions=['ESCALATE'], starts_at_s=0, expires_at_s=8,
                            basis='synthetic_assumption', source_note='Management escalation only, not physical authority.'))
                        profile['review_channels'].insert(0, dict(id='escalation-channel-52', question_id='cooling-direct/question-1',
                            source_id=source, target_id='intake_pump', observable_id=observable,
                            authorization_id=authority, record_id=spec['escalation_record_id']))
                    elif case == 'evidence-reviewed-false-alarm':
                        data['duration_s'] = spec['false_alarm_duration_s']
                        dispatch['decision_times_s'].extend(spec['false_alarm_extra_decisions_s'])
                        grant.update(dispositions=['FALSE_ALARM'], expires_at_s=10)
                        review.update(id=spec['false_alarm_record_id'], value='FALSE_ALARM',
                            observed_at_s=spec['false_alarm_review_at_s'], arrived_at_s=spec['false_alarm_review_at_s'], valid_until_s=10,
                            provenance=dict(origin_id=spec['false_alarm_record_id'], copied_from_record_id=None))
                        profile['review_channels'][0]['record_id'] = spec['false_alarm_record_id']
                        profile['false_alarm_reviews'] = [dict(review_record_id=spec['false_alarm_record_id'],
                            question_id='cooling-direct/question-1', original_record_id='cooling-second-origin-20',
                            supporting_record_ids=deepcopy(spec['false_alarm_support_ids']),
                            rationale='Review this original suspicion against the actually produced post-opening flow and service samples.')]
                    else:
                        self.fail('Undeclared qualification case')
                    directory = output/case if output is not None else None
                    if directory is not None:
                        directory.mkdir()
                    save(directory, 'frozen-call-input.json', data)
                    self.facility_calls += 1
                    result = simulate_scenario(**data)
                    self.completed_native_horizons += 1
                    self.completed_native_duration_s += result['summary']['duration_s']
                    self.returned_decisions += len(result['policy_public_decisions'])
                    identity = result['code_identity']
                    if directory is not None:
                        save_run(result, directory/'actual-run')
                    evaluation = result['business_evaluation']
                    save(directory, 'business-result.json', evaluation)
                    public = [dict(at_s=d['frame']['as_of_s'], lifecycle=d['choice']['question_lifecycle'])
                              for d in result['policy_public_decisions']]
                    save(directory, 'public-lifecycle.json', public)
                    episodes = {e['question_id']:e for e in evaluation['episodes']}
                    first, second = (episodes['cooling-direct/question-'+str(i)] for i in (0, 1))
                    for event in (first, second):
                        self.assertEqual(event['assessments'], [q for d in public for q in d['lifecycle']['questions']
                                         if q['question_id'] == event['question_id']])
                    self.assertEqual(first['first_verified_closed_at_s'], 5.5)
                    self.assertEqual(second['opened_at_s'], 5.75)
                    for field in ('actual_action_completed_at_s', 'action_report_arrived_at_s',
                                  'actual_recheck_completed_at_s', 'recheck_report_arrived_at_s', 'first_verified_closed_at_s'):
                        self.assertIsNone(second[field], field)
                    self.assertFalse(second['assessments'][-1]['risk_closed'])
                    self.assertFalse(second['assessments'][-1]['physical_restoration_claim'])
                    self.assertEqual([w['id'] for w in result['work_records']], ['cooling-direct/action-0','cooling-direct/recheck-0'])
                    current = second['management_disposition_assessments']
                    history = second['historical_disposition_assessments']
                    if case in ('accepted-then-expired', 'historical-only'):
                        self.assertEqual(second['status_at_horizon'], 'OPEN_UNCONFIRMED')
                        expected_first = 5.75 if case == 'accepted-then-expired' else None
                        self.assertEqual(second['first_risk_accepted_at_s'], expected_first)
                        self.assertEqual(second['first_question_closed_at_s'], expected_first)
                        self.assertEqual([r['evaluated_at_s'] for r in current], [5.75] if case == 'accepted-then-expired' else [])
                        self.assertEqual(len(history), 1)
                        self.assertEqual(history[0]['evaluated_at_s'], 6)
                        self.assertEqual(history[0]['observed_at_s'], 5.75 if case == 'accepted-then-expired' else 5.8125)
                        self.assertEqual(history[0]['arrived_at_s'], 5.75 if case == 'accepted-then-expired' else 5.875)
                        self.assertEqual(history[0]['status_at_arrival'], 'RISK_ACCEPTED')
                        self.assertTrue(history[0]['question_closed_at_arrival'])
                        self.assertFalse(history[0]['risk_closed_at_arrival'])
                    elif case == 'escalation-priority':
                        self.assertEqual(second['first_escalated_at_s'], 5.75)
                        self.assertIsNone(second['first_risk_accepted_at_s'])
                        self.assertIsNone(second['first_question_closed_at_s'])
                        self.assertEqual(second['status_at_horizon'], 'ESCALATED')
                        self.assertEqual(len(current), 4)
                        for clock in (5.75, 6):
                            group = {r['disposition']:r for r in current if r['evaluated_at_s'] == clock}
                            self.assertEqual(set(group), {'ACCEPT_RISK', 'ESCALATE'})
                            self.assertFalse(group['ACCEPT_RISK']['selected_at_evaluation'])
                            self.assertTrue(group['ESCALATE']['selected_at_evaluation'])
                        self.assertEqual(history, [])
                    else:
                        self.assertEqual(second['first_false_alarm_reviewed_at_s'], 7.5)
                        self.assertEqual(second['first_question_closed_at_s'], 7.5)
                        self.assertIsNone(second['first_risk_accepted_at_s'])
                        self.assertIsNone(second['first_escalated_at_s'])
                        self.assertEqual(second['status_at_horizon'], 'FALSE_ALARM_REVIEWED')
                        self.assertEqual([r['evaluated_at_s'] for r in current], [7.5, 8])
                        review_rows = [(assessment, review_check) for assessment in second['assessments']
                                       for review_check in assessment.get('review_evaluations', [])]
                        self.assertEqual(len(review_rows), 2)
                        for assessment, review_check in review_rows:
                                self.assertTrue(review_check['passed'])
                                self.assertEqual(review_check['review_at_s'], 7.5)
                                self.assertEqual(review_check['current_at_s'], assessment['as_of_s'])
                                for check in review_check['review_checks'] + review_check['current_checks']:
                                    self.assertEqual(check['genuine_sample_count'], 2)
                                    self.assertEqual(check['span_s'], 1)
                        self.assertEqual(history, [])
                        self.assertEqual(len(public), 11)
                    if case != 'evidence-reviewed-false-alarm':
                        self.assertEqual(len(public), 7)
                    row.update(passed=True, duration_s=result['summary']['duration_s'], returned_decisions=len(public),
                        second_episode=second, first_verified_closed_at_s=first['first_verified_closed_at_s'])
        finally:
            save(output, 'qualification.json', rows)
            if identity is not None:
                save(output, 'actual-execution-summary.json', dict(code_identity=identity,
                    facility_calls=self.facility_calls, completed_horizons=self.completed_native_horizons,
                    completed_duration_s=self.completed_native_duration_s, returned_decisions=self.returned_decisions))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r['passed'] for r in rows))


if __name__ == '__main__':
    unittest.main()
