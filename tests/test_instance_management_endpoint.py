"""Private instance endpoints preserve actual public management and physical clocks."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class InstanceManagementEndpointTests(unittest.TestCase):
    def test_own_physical_closure_and_new_management_acceptance_keep_evidence_and_clocks(self):
        base = json.loads((ROOT/'tests/fixtures/39c-instance-management-51.json').read_bytes())
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
            for case in ('private-v2', 'wrong-recheck-slot', 'legacy-private-v1-refusal'):
                row = dict(case=case, passed=False)
                rows.append(row)
                with self.subTest(case=case):
                    data = deepcopy(base)
                    if case == 'wrong-recheck-slot':
                        data['business_program']['episodes'][1]['recheck_task_id'] = 'cooling-direct/recheck-0'
                    elif case == 'legacy-private-v1-refusal':
                        data['business_program']['schema'] = 'aegisdc-business-instance-closure-evaluation-v1'
                        for event in data['business_program']['episodes']:
                            del event['recheck_task_id']
                    directory = output/case if output is not None else None
                    if directory is not None:
                        directory.mkdir()
                    save(directory, 'frozen-call-input.json', data)
                    self.facility_calls += 1
                    try:
                        result = simulate_scenario(**data)
                    except ValueError as error:
                        if case == 'private-v2':
                            raise
                        expected = ('Business event must bind one declared public question/action/recheck rule'
                                    if case == 'wrong-recheck-slot' else
                                    'Instance endpoints require the matching public instance closure workflow')
                        row['actual_error'] = str(error)
                        self.assertEqual(str(error), expected)
                        row['passed'] = True
                        continue
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
                    self.assertEqual(case, 'private-v2', 'A guarded input unexpectedly completed')
                    self.assertEqual(evaluation['schema'], 'aegisdc-business-instance-closure-result-v2')
                    self.assertEqual(evaluation['visibility'], 'PRIVATE_EVALUATOR_ONLY')
                    episodes = {e['question_id']:e for e in evaluation['episodes']}
                    first = episodes['cooling-direct/question-0']
                    second = episodes['cooling-direct/question-1']
                    for event in (first, second):
                        expected = [deepcopy(q) for d in public for q in d['lifecycle']['questions']
                                    if q['question_id'] == event['question_id']]
                        self.assertEqual(event['assessments'], expected)
                    self.assertEqual(first['actual_action_completed_at_s'], 3.25)
                    self.assertEqual(first['action_report_arrived_at_s'], 3.75)
                    self.assertEqual(first['actual_recheck_completed_at_s'], 5)
                    self.assertEqual(first['recheck_report_arrived_at_s'], 5.5)
                    self.assertEqual(first['first_verified_closed_at_s'], 5.5)
                    self.assertEqual(first['first_question_closed_at_s'], 5.5)
                    self.assertIsNone(first['first_risk_accepted_at_s'])
                    self.assertEqual(first['management_disposition_assessments'], [])
                    self.assertEqual(second['opened_at_s'], 5.75)
                    self.assertEqual(second['recheck_task_id'], 'cooling-direct/recheck-1')
                    for name in ('actual_action_completed_at_s', 'action_report_arrived_at_s',
                                 'actual_recheck_completed_at_s', 'recheck_report_arrived_at_s',
                                 'first_verified_closed_at_s', 'first_escalated_at_s',
                                 'first_false_alarm_reviewed_at_s'):
                        self.assertIsNone(second[name], name)
                    self.assertEqual(second['first_risk_accepted_at_s'], 5.75)
                    self.assertEqual(second['first_question_closed_at_s'], 5.75)
                    self.assertTrue(second['closure_right_censored'])
                    self.assertFalse(second['assessments'][-1]['risk_closed'])
                    self.assertFalse(second['assessments'][-1]['physical_restoration_claim'])
                    self.assertFalse(second['assessments'][-1]['own_recheck']['passed'])
                    reviews = second['management_disposition_assessments']
                    self.assertEqual([r['evaluated_at_s'] for r in reviews], [5.75, 6])
                    for review in reviews:
                        self.assertEqual(review['record_id'], 'accept-risk-instance1-21')
                        self.assertEqual(review['observed_at_s'], 5.75)
                        self.assertEqual(review['arrived_at_s'], 5.75)
                        self.assertEqual(review['disposition'], 'ACCEPT_RISK')
                        self.assertEqual(review['status_at_evaluation'], 'RISK_ACCEPTED')
                        self.assertTrue(review['selected_at_evaluation'])
                    self.assertEqual(second['historical_disposition_assessments'], [])
                    self.assertEqual([r['id'] for r in result['work_records']],
                                     ['cooling-direct/action-0', 'cooling-direct/recheck-0'])
                    self.assertEqual(len(public), 7)
                    row.update(passed=True, episodes=evaluation['episodes'], duration_s=6, returned_decisions=7)
        finally:
            save(output, 'qualification.json', rows)
            if identity is not None:
                save(output, 'actual-execution-summary.json', dict(code_identity=identity,
                    facility_calls=self.facility_calls, completed_horizons=self.completed_native_horizons,
                    completed_duration_s=self.completed_native_duration_s, returned_decisions=self.returned_decisions))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row['passed'] for row in rows))


if __name__ == '__main__':
    unittest.main()
