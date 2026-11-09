"""Censoring, no-human work and expired verification at the facility interface."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class BusinessClosureQualificationTests(unittest.TestCase):
    def run_case(self, case_id):
        declaration = json.loads((ROOT / 'tests/fixtures/39c-closure-qualification-02.json').read_bytes())
        variant = next(row for row in declaration['cases'] if row['id'] == case_id)
        fixture = json.loads((ROOT / declaration['base_fixture']).read_bytes())
        dispatch = fixture['replay_inputs']['dispatch_program']
        if variant['policy'] is not None:
            dispatch['policy_program']['policy'] = variant['policy']
            if variant['policy'] == 'no_human':
                dispatch['policy_program']['options'] = {}
        if variant['append_decision_at_s'] is not None:
            dispatch['decision_times_s'].append(variant['append_decision_at_s'])
        if variant['decision_times_s'] is not None:
            dispatch['decision_times_s'] = deepcopy(variant['decision_times_s'])
        if variant['postaction_validity_s'] is not None:
            for channel in dispatch['sensor_program']['profile']['channels']:
                if channel['id'] in {'flow-transfer', 'joint-service-transfer'}:
                    channel['validity_s'] = variant['postaction_validity_s']
            dispatch['policy_program']['evidence_projection']['background_sensor_profile'] = deepcopy(
                dispatch['sensor_program']['profile'])
        fixture['business_program']['id'] += '-' + case_id
        output = None
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) / case_id
            output.mkdir()
            with (output / 'frozen-call-input.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(dict(fixture=fixture, duration_s=variant['duration_s'], maximum_step_s=.01),
                          stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
        self.facility_calls = 1
        replay = fixture['replay_inputs']
        result = simulate_scenario(fixture['model'], duration_s=variant['duration_s'], step_s=.01,
            work_requests=replay['work_requests'], boundary_events=replay['exogenous_events'],
            action_commands=replay['action_commands'], dispatch_program=dispatch,
            business_program=fixture['business_program'])
        self.returned_decisions = len(result['policy_public_decisions'])
        if output is not None:
            save_run(result, output / 'actual-run')
            with (output / 'business-result.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(result['business_evaluation'], stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
        return result, result['business_evaluation']['episodes'][0]

    def test_no_human_preserves_unconfirmed_and_missing_action_endpoints(self):
        result, event = self.run_case('no-human')
        self.assertEqual(result['work_records'], [])
        self.assertIsNone(event['actual_action_completed_at_s'])
        self.assertIsNone(event['action_report_arrived_at_s'])
        self.assertIsNone(event['first_verified_closed_at_s'])
        self.assertIsNone(event['time_to_first_verified_closed_s'])
        self.assertTrue(event['closure_right_censored'])
        self.assertEqual(event['closure_censor_at_s'], 8.5)
        self.assertEqual(event['latest_assessed_status'], 'OPEN_UNCONFIRMED')
        self.assertEqual(event['status_at_horizon'], 'NOT_ASSESSED_AT_HORIZON')
        self.assertEqual(self.returned_decisions, 8)

    def test_expired_evidence_reopens_current_assessment_but_preserves_first_closure(self):
        _, event = self.run_case('expiry-reopens')
        self.assertEqual(event['first_verified_closed_at_s'], 8.5)
        self.assertFalse(event['closure_right_censored'])
        self.assertEqual(event['last_assessed_at_s'], 10)
        self.assertEqual(event['status_at_horizon'], 'ACTION_COMPLETED_PENDING_VERIFICATION')
        self.assertFalse(event['assessments'][-1]['risk_closed'])
        self.assertEqual(self.returned_decisions, 9)

    def test_window_ends_before_second_arrival_and_closure_is_right_censored(self):
        _, event = self.run_case('window-censored')
        self.assertEqual(event['actual_action_completed_at_s'], 6)
        self.assertEqual(event['action_report_arrived_at_s'], 6.5)
        self.assertIsNone(event['first_verified_closed_at_s'])
        self.assertIsNone(event['time_to_first_verified_closed_s'])
        self.assertTrue(event['closure_right_censored'])
        self.assertEqual(event['closure_censor_at_s'], 8)
        self.assertEqual(event['status_at_horizon'], 'ACTION_COMPLETED_PENDING_VERIFICATION')
        self.assertEqual(self.returned_decisions, 8)


if __name__ == '__main__':
    unittest.main()
