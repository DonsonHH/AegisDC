"""One actual facility result supplies diagnostic, instance and cost endpoints."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario
from patrol_rsi.contracts import digest

ROOT = Path(__file__).resolve().parents[1]


class CompositeBusinessEndpointTests(unittest.TestCase):
    def test_same_native_run_binds_diagnosis_closure_costs_and_rejects_mixed_inputs(self):
        base = json.loads((ROOT/'tests/fixtures/39c-composite-endpoint-53.json').read_bytes())
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
            for case in ('joint', 'step-binding-mismatch', 'extra-component', 'legacy-diagnostic-v2-refusal'):
                row = dict(case=case, passed=False)
                rows.append(row)
                with self.subTest(case=case):
                    data = deepcopy(base)
                    if case == 'step-binding-mismatch':
                        data['business_program']['run_binding']['maximum_step_s'] = 0.02
                    elif case == 'extra-component':
                        data['business_program']['components']['other'] = deepcopy(data['business_program']['components']['costs'])
                    elif case == 'legacy-diagnostic-v2-refusal':
                        data['business_program'] = deepcopy(data['business_program']['components']['diagnostic'])
                        data['business_program']['schema'] = 'aegisdc-business-diagnostic-evaluation-v2'
                        for event in data['business_program']['events']:
                            del event['timing']
                    directory = output/case if output is not None else None
                    if directory is not None:
                        directory.mkdir()
                    save(directory, 'frozen-call-input.json', data)
                    self.facility_calls += 1
                    try:
                        result = simulate_scenario(**data)
                    except ValueError as error:
                        if case == 'joint':
                            raise
                        messages = dict(step_binding_mismatch='Composite run binding differs from actual execution inputs',
                            extra_component='Declare exactly diagnostic, instance_closure and costs components',
                            legacy_diagnostic_v2_refusal='Declare a separate public diagnostic profile')
                        row['actual_error'] = str(error)
                        self.assertEqual(str(error), messages[case.replace('-', '_')])
                        row['passed'] = True
                        continue
                    self.completed_native_horizons += 1
                    self.completed_native_duration_s += result['summary']['duration_s']
                    self.returned_decisions += len(result['policy_public_decisions'])
                    identity = result['code_identity']
                    if directory is not None:
                        save_run(result, directory/'actual-run')
                    joint = result['business_evaluation']
                    save(directory, 'business-result.json', joint)
                    public = result['policy_public_decisions']
                    save(directory, 'public-decisions.json', public)
                    self.assertEqual(case, 'joint', 'A guarded input unexpectedly completed')
                    self.assertEqual(joint['schema'], 'aegisdc-business-composite-result-v1')
                    self.assertEqual(joint['visibility'], 'PRIVATE_EVALUATOR_ONLY')
                    self.assertEqual(joint['run_binding'], data['business_program']['run_binding'])
                    self.assertEqual(joint['business_program_sha256'], digest(data['business_program']))
                    self.assertEqual(set(joint['components']), {'diagnostic', 'instance_closure', 'costs'})
                    for name, component in joint['components'].items():
                        self.assertEqual(component['program_id'], data['business_program']['components'][name]['id'])
                        self.assertEqual(component['facility_id'], result['facility_id'])
                        self.assertEqual(component['window_end_s'], 6)
                        self.assertEqual(component['execution_code_identity'], result['code_identity'])
                        self.assertEqual(joint['component_program_sha256'][name], digest(data['business_program']['components'][name]))
                    diagnostic = joint['components']['diagnostic']
                    self.assertEqual(diagnostic['schema'], 'aegisdc-business-diagnostic-result-v3')
                    event, = diagnostic['events']
                    self.assertEqual(event['initial_truth'], 'FAULT')
                    self.assertEqual(event['first_corroborated_fault_report_at_s'], 0.5)
                    first_frame = next(d['frame'] for d in public if d['frame']['as_of_s'] == 0.5)
                    sample = next(r for r in first_frame['evidence']['records'] if r['id'] == 'flow-transfer:0')
                    self.assertEqual((sample['observed_at_s'], sample['arrived_at_s'], sample['unit']), (0, 0.5, 'kg/s'))
                    self.assertEqual(event['initial_private_value'], sample['value'])
                    self.assertEqual(diagnostic['counts']['eligible_fault_matured'], 1)
                    self.assertEqual(diagnostic['counts']['timely_confirmed_fault'], 1)
                    self.assertEqual(diagnostic['counts']['missed_fault_confirmation'], 0)
                    self.assertIsNone(diagnostic['rates']['false_positive_state_events']['value'])
                    timing = event['temporal_endpoints']
                    self.assertEqual(timing['fault_reference']['status'], 'PRESENT_AT_FIRST_SAMPLE')
                    self.assertTrue(timing['fault_reference']['left_censored'])
                    self.assertIsNone(timing['fault_reference']['lead_s'])
                    self.assertEqual(timing['service_loss_reference']['status'], 'NOT_OBSERVED_BY_LAST_SAMPLE')
                    self.assertTrue(timing['service_loss_reference']['right_censored'])
                    self.assertEqual(timing['service_loss_reference']['lead_lower_bound_if_later_event_s'], 5.5)
                    self.assertEqual(timing['intervention_deadline_reference']['lead_s'], 5.5)
                    self.assertEqual(diagnostic['prevention_effect']['status'], 'NOT_IDENTIFIED_NO_PAIRED_COUNTERFACTUAL')
                    episode = {e['question_id']:e for e in joint['components']['instance_closure']['episodes']}
                    old, new = (episode['cooling-direct/question-'+str(i)] for i in (0, 1))
                    self.assertEqual(old['actual_action_completed_at_s'], 3.25)
                    self.assertEqual(old['action_report_arrived_at_s'], 3.75)
                    self.assertEqual(old['actual_recheck_completed_at_s'], 5)
                    self.assertEqual(old['recheck_report_arrived_at_s'], 5.5)
                    self.assertEqual(old['first_verified_closed_at_s'], 5.5)
                    self.assertEqual(new['first_risk_accepted_at_s'], 5.75)
                    self.assertIsNone(new['first_verified_closed_at_s'])
                    self.assertIsNone(new['actual_action_completed_at_s'])
                    self.assertIsNone(new['actual_recheck_completed_at_s'])
                    self.assertFalse(new['assessments'][-1]['risk_closed'])
                    for name, value in episode.items():
                        self.assertEqual(value['assessments'], [q for d in public for q in d['choice']['question_lifecycle']['questions']
                                         if q['question_id'] == name])
                    cost = joint['components']['costs']
                    self.assertEqual(cost['schema'], 'aegisdc-business-cost-result-v2')
                    for key, value in dict(worker_travel_person_s=2, worker_work_person_s=2, worker_wait_person_s=0.5,
                        access_check_person_s=0.5, rendezvous_wait_person_s=0, queue_wait_person_s=0,
                        tool_occupation_tool_s=4.5, tool_work_tool_s=2).items():
                        self.assertAlmostEqual(cost['actual'][key]['value'], value)
                    self.assertAlmostEqual(cost['personnel_total']['value'], 4.5)
                    self.assertEqual(cost['issue_fees']['value'], 2)
                    self.assertTrue(all(cost['failure_attribution']['reconciliation'].values()))
                    self.assertTrue(cost['failure_attribution']['issue_fee_reconciled'])
                    self.assertEqual([r['id'] for r in result['work_records']], ['cooling-direct/action-0','cooling-direct/recheck-0'])
                    self.assertEqual(len(public), 8)
                    self.assertEqual(result['summary']['service_deficit_time_s'], 0)
                    self.assertNotIn('joint53-private', json.dumps(public))
                    row.update(passed=True, duration_s=6, returned_decisions=8,
                        first_confirmation_at_s=0.5, first_own_close_at_s=5.5, first_management_accept_at_s=5.75)
                    save(directory, 'actual-summary.json', dict(summary=result['summary'], work_records=result['work_records'],
                        component_program_sha256=joint['component_program_sha256']))
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
