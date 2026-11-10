"""Joint actual cost/closure/diagnostic qualifications include positive rendezvous."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario
from patrol_rsi.contracts import digest

ROOT = Path(__file__).resolve().parents[1]


class CompositeBusinessQualificationTests(unittest.TestCase):
    def test_crew_no_human_and_nonempty_service_boundary_keep_joint_denominators(self):
        spec = json.loads((ROOT/'tests/fixtures/39c-composite-qualification-54.json').read_bytes())
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
                    if case == 'crew-rendezvous':
                        dispatch['policy_program']['templates'][0]['action_task']['crew'].append(
                            dict(worker_id='worker_control', qualification_id='qualified_cooling_inspection'))
                        data['duration_s'] = spec['crew_duration_s']
                        dispatch['decision_times_s'] = sorted(dispatch['decision_times_s'] + spec['crew_extra_decisions_s'])
                    elif case == 'no-human':
                        dispatch['policy_program']['policy'] = 'no_human'
                    elif case == 'service-unqualified':
                        data['boundary_events'] = deepcopy(spec['service_boundaries'])
                    else:
                        self.fail('Undeclared qualification case')
                    business = data['business_program']
                    diagnostic = business['components']['diagnostic']
                    diagnostic['events'][0]['timing']['sample_times_s'] = sorted(set(dispatch['decision_times_s'] +
                        [b['time_s'] for b in data['boundary_events']]))
                    reference = diagnostic['reference']
                    for name, value in dict(scenario_sha256=data['scenario'], boundary_events_sha256=data['boundary_events'],
                        nominal_knowledge_sha256=dispatch['nominal_knowledge'], ledger_sha256=dispatch['evidence_ledger'],
                        workforce_profile_sha256=dispatch['policy_program']['workforce_profile'],
                        inspection_profile_sha256=dispatch['inspection_program']['profile']).items():
                        reference[name] = digest(value)
                    normalized = sorted((dict(b, time_s=float(b['time_s']), value=float(b['value']))
                                         for b in data['boundary_events']), key=lambda b:b['time_s'])
                    business['run_binding'] = dict(scenario_sha256=digest(data['scenario']), dispatch_program_sha256=digest(dispatch),
                        boundary_events_sha256=digest(normalized), action_commands_sha256=digest([]),
                        duration_s=float(data['duration_s']), maximum_step_s=data['step_s'])
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
                    joint = result['business_evaluation']
                    save(directory, 'business-result.json', joint)
                    public = result['policy_public_decisions']
                    save(directory, 'public-decisions.json', public)
                    save(directory, 'actual-summary.json', dict(summary=result['summary'], work_records=result['work_records']))
                    self.assertEqual(joint['run_binding'], business['run_binding'])
                    self.assertEqual(joint['business_program_sha256'], digest(business))
                    for name, component in joint['components'].items():
                        self.assertEqual(component['window_end_s'], data['duration_s'])
                        self.assertEqual(component['facility_id'], data['scenario']['id'])
                        self.assertEqual(component['execution_code_identity'], result['code_identity'])
                        self.assertEqual(joint['component_program_sha256'][name], digest(business['components'][name]))
                    diagnostic = joint['components']['diagnostic']
                    event, = diagnostic['events']
                    self.assertEqual(event['first_corroborated_fault_report_at_s'], 0.5)
                    self.assertEqual(event['reference_opportunity']['status'], 'ELIGIBLE')
                    self.assertEqual(diagnostic['counts']['eligible_fault_matured'], 1)
                    self.assertEqual(diagnostic['counts']['timely_confirmed_fault'], 1)
                    self.assertEqual(diagnostic['prevention_effect']['status'], 'NOT_IDENTIFIED_NO_PAIRED_COUNTERFACTUAL')
                    episodes = {e['question_id']:e for e in joint['components']['instance_closure']['episodes']}
                    old, new = (episodes['cooling-direct/question-'+str(i)] for i in (0, 1))
                    for question_id, episode in episodes.items():
                        self.assertEqual(episode['assessments'], [q for d in public for q in d['choice']['question_lifecycle']['questions']
                                         if q['question_id'] == question_id])
                    self.assertEqual(new['first_risk_accepted_at_s'], 5.75)
                    self.assertIsNone(new['actual_action_completed_at_s'])
                    self.assertIsNone(new['actual_recheck_completed_at_s'])
                    self.assertIsNone(new['first_verified_closed_at_s'])
                    self.assertFalse(new['assessments'][-1]['risk_closed'])
                    self.assertFalse(new['assessments'][-1]['physical_restoration_claim'])
                    cost = joint['components']['costs']
                    self.assertTrue(all(cost['failure_attribution']['reconciliation'].values()))
                    self.assertTrue(cost['failure_attribution']['issue_fee_reconciled'])
                    self.assertNotIn('joint53-private', json.dumps(public))
                    tasks = {w['id']:w for w in result['work_records']}
                    if case == 'crew-rendezvous':
                        self.assertEqual(len(public), 11)
                        self.assertEqual(tasks['cooling-direct/action-0']['work_started_at_s'], 3.25)
                        self.assertEqual(tasks['cooling-direct/action-0']['completed_at_s'], 4.25)
                        self.assertEqual(old['action_report_arrived_at_s'], 4.75)
                        self.assertEqual(tasks['cooling-direct/recheck-0']['work_started_at_s'], 5)
                        self.assertEqual(old['actual_recheck_completed_at_s'], 6)
                        self.assertEqual(old['recheck_report_arrived_at_s'], 6.5)
                        self.assertEqual(old['first_verified_closed_at_s'], 6.5)
                        expected = dict(worker_travel_person_s=5, worker_work_person_s=3, worker_wait_person_s=1.75,
                            access_check_person_s=0.75, rendezvous_wait_person_s=1, queue_wait_person_s=0,
                            tool_occupation_tool_s=5.5, tool_work_tool_s=2)
                        self.assertAlmostEqual(cost['personnel_total']['value'], 9.75)
                        self.assertEqual(cost['issue_fees']['value'], 2)
                    elif case == 'no-human':
                        self.assertEqual(len(public), 8)
                        self.assertEqual(tasks, {})
                        self.assertIsNone(old['first_verified_closed_at_s'])
                        self.assertIsNone(old['actual_action_completed_at_s'])
                        self.assertIsNone(old['actual_recheck_completed_at_s'])
                        self.assertEqual(old['status_at_horizon'], 'OPEN_UNCONFIRMED')
                        expected = dict.fromkeys(cost['actual'], 0)
                        self.assertEqual(cost['personnel_total']['value'], 0)
                        self.assertEqual(cost['issue_fees']['value'], 0)
                    else:
                        self.assertEqual(len(public), 8)
                        self.assertIsNone(old['first_verified_closed_at_s'])
                        self.assertEqual(old['status_at_horizon'], 'SYMPTOM_RETREATED_PENDING_VERIFICATION')
                        self.assertTrue(old['assessments'][-1]['own_recheck']['passed'])
                        service = next(c for c in old['assessments'][-1]['checks'] if c['role'] == 'service')
                        self.assertFalse(service['passed'])
                        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 3.5)
                        self.assertEqual([b['time_s'] for b in data['boundary_events']], [2, 1])
                        self.assertEqual([b['time_s'] for b in result['inputs']['boundary_events']], [1, 2])
                        self.assertNotEqual(joint['run_binding']['boundary_events_sha256'], digest(data['boundary_events']))
                        self.assertEqual(joint['run_binding']['boundary_events_sha256'], digest(result['inputs']['boundary_events']))
                        self.assertEqual(business['components']['diagnostic']['reference']['boundary_events_sha256'], digest(data['boundary_events']))
                        temporal = event['temporal_endpoints']['service_loss_reference']
                        self.assertEqual(temporal['sample_at_s'], 1)
                        self.assertEqual(temporal['previous_non_event_sample_at_s'], 0.5)
                        self.assertEqual(temporal['lead_s'], 0.5)
                        self.assertEqual(temporal['transition_lead_interval_s'], [0, 0.5])
                        self.assertEqual(temporal['attribution'], 'WHOLE_FACILITY_NOT_CAUSE_ATTRIBUTED')
                        expected = dict(worker_travel_person_s=2, worker_work_person_s=2, worker_wait_person_s=0.5,
                            access_check_person_s=0.5, rendezvous_wait_person_s=0, queue_wait_person_s=0,
                            tool_occupation_tool_s=4.5, tool_work_tool_s=2)
                        self.assertEqual(cost['issue_fees']['value'], 2)
                    for key, value in expected.items():
                        self.assertAlmostEqual(cost['actual'][key]['value'], value, msg=key)
                    if case != 'no-human':
                        self.assertEqual(set(tasks), {'cooling-direct/action-0', 'cooling-direct/recheck-0'})
                    row.update(passed=True, duration_s=data['duration_s'], returned_decisions=len(public),
                        first_own_close_at_s=old['first_verified_closed_at_s'], first_management_accept_at_s=new['first_risk_accepted_at_s'],
                        personnel_total=cost['personnel_total'], actual=cost['actual'])
        finally:
            save(output, 'qualification.json', rows)
            if identity is not None:
                save(output, 'actual-execution-summary.json', dict(code_identity=identity,
                    facility_calls=self.facility_calls, completed_horizons=self.completed_native_horizons,
                    completed_duration_s=self.completed_native_duration_s, returned_decisions=self.returned_decisions))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r['passed'] for r in rows))


if __name__ == '__main__':
    unittest.main()
