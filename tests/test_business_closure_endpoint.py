"""Actual facility work, arrived evidence and verified closure are distinct endpoints."""
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class BusinessClosureEndpointTests(unittest.TestCase):
    def test_actual_action_is_not_closed_until_two_arrived_verification_samples(self):
        fixture = json.loads((ROOT / 'tests/fixtures/39c-actual-closure-endpoint.json').read_text(encoding='utf-8'))
        inputs = fixture['replay_inputs']
        self.facility_calls = 1
        result = simulate_scenario(fixture['model'], duration_s=10, step_s=.01,
            work_requests=inputs['work_requests'], boundary_events=inputs['exogenous_events'],
            action_commands=inputs['action_commands'], dispatch_program=inputs['dispatch_program'],
            business_program=fixture['business_program'])
        self.returned_decisions = len(result['policy_public_decisions'])
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR'])
            save_run(result, output / 'actual-run')
            with (output / 'business-result.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(result['business_evaluation'], stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
        evaluation = result['business_evaluation']
        self.assertEqual(evaluation['visibility'], 'PRIVATE_EVALUATOR_ONLY')
        self.assertEqual(evaluation['diagnosis_and_prevention']['status'], 'NOT_DEFINED_FOR_THIS_PROGRAM_VERSION')
        self.assertEqual(evaluation['window_end_s'], 10)
        episode = evaluation['episodes'][0]
        self.assertEqual(episode['id'], 'cooling-endpoint-01')
        self.assertEqual(episode['actual_action_completed_at_s'], 6)
        self.assertEqual(episode['action_report_arrived_at_s'], 6.5)
        self.assertEqual(episode['first_verified_closed_at_s'], 8.5)
        self.assertEqual(episode['time_to_first_verified_closed_s'], 8.5)
        self.assertFalse(episode['closure_right_censored'])
        self.assertEqual(episode['last_assessed_at_s'], 8.5)
        self.assertEqual(episode['status_at_horizon'], 'NOT_ASSESSED_AT_HORIZON')
        before = [row for row in episode['assessments'] if row['as_of_s'] < 8.5]
        self.assertTrue(before)
        self.assertTrue(all(row['status'] != 'VERIFIED_CLOSED' for row in before))
        at_report = next(row for row in episode['assessments'] if row['as_of_s'] == 6.5)
        self.assertEqual(at_report['status'], 'ACTION_COMPLETED_PENDING_VERIFICATION')
        final = episode['assessments'][-1]
        self.assertEqual(final['status'], 'VERIFIED_CLOSED')
        self.assertTrue(final['supporting_record_ids'])
        self.assertEqual(self.returned_decisions, 8)


if __name__ == '__main__':
    unittest.main()
