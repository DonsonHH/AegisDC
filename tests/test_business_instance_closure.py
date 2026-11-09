"""A dynamic question closes only after its own paid action/recheck and evidence."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class BusinessInstanceClosureTests(unittest.TestCase):
    def test_own_action_and_recheck_plus_two_condition_service_samples_close_at_5_5(self):
        descriptor = json.loads((ROOT / 'tests/fixtures/39c-instance-closure-16.json').read_bytes())
        fixture = json.loads((ROOT / descriptor['base_fixture']).read_bytes())
        dispatch = fixture['dispatch_program']
        dispatch['decision_times_s'] = descriptor['decision_times_s']
        dispatch['intervention_program']['bindings'][0]['setting'] = descriptor['filter_setting']
        dispatch['policy_program']['intervention_declaration'] = deepcopy(dispatch['intervention_program'])
        sensor_fixture = json.loads((ROOT / descriptor['sensor_template']).read_bytes())
        sensors = deepcopy(sensor_fixture['replay_inputs']['dispatch_program']['sensor_program'])
        profile = sensors['profile']
        profile['ledger']['id'] = '39c-instance-closure-fixed-registry'
        profile['ledger']['sources'] = [row for row in profile['ledger']['sources'] if row['id'] in ['intake-flow-record', 'joint-service-record']]
        profile['ledger']['observables'] = [row for row in profile['ledger']['observables'] if row['id'] in ['lake_mass_flow', 'service_delivered_rate']]
        profile['measurements'] = [row for row in profile['measurements'] if row['id'] in ['lake-flow', 'joint-service-meter']]
        for row in profile['measurements']:
            row['phase_s'] = descriptor['fixed_phase_s']
            row['period_s'] = descriptor['fixed_period_s']
        profile['channels'] = [row for row in profile['channels'] if row['measurement_id'] in ['lake-flow', 'joint-service-meter']]
        for row in profile['channels']:
            row['delay_s'] = descriptor['fixed_delay_s']
            row['validity_s'] = descriptor['fixed_validity_s']
        for field in ('biases', 'noise_bounds', 'dropout_probabilities'):
            sensors['realization'][field] = {key: value for key, value in sensors['realization'][field].items() if key in ['lake-flow', 'joint-service-meter']}
        dispatch['sensor_program'] = sensors
        dispatch['closure_program'] = dict(schema='aegisdc-instance-closure-program-v1',
            profile=dict(schema='aegisdc-instance-closure-profile-v1', id='39c-instance-closure-16',
                facility_id=fixture['model']['id'], nominal_knowledge_id=dispatch['nominal_knowledge']['id'],
                basis='synthetic_assumption', time_unit='s',
                source_note='Own completed action/recheck plus finite sampled condition and service criteria.',
                rules=[deepcopy(descriptor['rule'])]),
            intervention_declaration=deepcopy(dispatch['intervention_program']), intervention_feedback=[])
        business = dict(schema='aegisdc-business-instance-closure-evaluation-v1', id='39c-instance-endpoint-16',
            facility_id=fixture['model']['id'], basis='synthetic_assumption', time_unit='s',
            source_note='Private endpoint extraction only after actual dynamic-instance assessment.',
            episodes=[dict(id='cooling-instance-event-01', question_id='cooling-direct/question-0',
                task_id='cooling-direct/action-0', opened_at_s=0, source_note='First actual public work-order instance; no invented probability.')])
        output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        def save(name, value):
            if output is not None:
                with (output / name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                    stream.write('\n')
        save('frozen-call-input.json', dict(model=fixture['model'], dispatch_program=dispatch, business_program=business,
            duration_s=descriptor['duration_s'], step_s=descriptor['step_s'], boundary_events=[]))
        self.facility_calls = 1
        result = simulate_scenario(fixture['model'], duration_s=descriptor['duration_s'], step_s=descriptor['step_s'],
            dispatch_program=dispatch, business_program=business)
        self.returned_decisions = len(result['policy_public_decisions'])
        if output is not None:
            save_run(result, output / 'actual-run')
        save('business-result.json', result['business_evaluation'])
        save('actual-instance-summary.json', dict(code_identity=result['code_identity'], summary=result['summary'],
            work_records=result['work_records'], resource_ledger=result['policy_public_resource_ledger'],
            intervention_feedback=result['intervention_public_feedback'],
            decisions=[dict(at_s=row['frame']['as_of_s'], choice=row['choice']) for row in result['policy_public_decisions']]))
        episode = result['business_evaluation']['episodes'][0]
        self.assertEqual(episode['actual_action_completed_at_s'], 3.25)
        self.assertEqual(episode['action_report_arrived_at_s'], 3.75)
        self.assertEqual(episode['first_verified_closed_at_s'], 5.5)
        self.assertEqual(episode['status_at_horizon'], 'VERIFIED_CLOSED')
        self.assertFalse(episode['closure_right_censored'])
        self.assertTrue(all(row['status'] != 'VERIFIED_CLOSED' for row in episode['assessments'] if row['as_of_s'] < 5.5))
        decisions = result['policy_public_decisions']
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in decisions], ['cooling-direct/action-0', 'cooling-direct/recheck-0', None, None, None, None])
        tasks = {row['id']: row for row in result['work_records']}
        self.assertEqual(tasks['cooling-direct/recheck-0']['completed_at_s'], 5)
        self.assertNotIn('cooling-direct/inspect-0', tasks)
        at_close = next(row for row in decisions if row['frame']['as_of_s'] == 5.5)
        closed = at_close['choice']['question_lifecycle']['questions'][0]
        self.assertEqual((closed['question_id'], closed['task_id'], closed['recheck_task_id']),
            ('cooling-direct/question-0', 'cooling-direct/action-0', 'cooling-direct/recheck-0'))
        self.assertEqual(closed['status'], 'VERIFIED_CLOSED')
        self.assertTrue(closed['own_recheck']['passed'])
        self.assertEqual(closed['own_recheck']['record_id'], 'flow-after-clean')
        self.assertTrue(all(row['genuine_sample_count'] == 2 and row['span_s'] == 1 for row in closed['checks']))
        self.assertIsNone(at_close['choice']['questions'][0]['fault_probability'])
        self.assertTrue(at_close['choice']['questions'][0]['risk_closed'])
        self.assertEqual(self.returned_decisions, 6)


if __name__ == '__main__':
    unittest.main()
