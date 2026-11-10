"""Whole-facility cost qualification without dropping unfinished or shared activity."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario
from test_workforce_dispatch import fixture as crew_fixture, task as crew_task, program as crew_program

ROOT = Path(__file__).resolve().parents[1]


class CostBoundaryQualificationTests(unittest.TestCase):
    def test_completed_unfinished_no_human_rejection_and_shared_queue_costs(self):
        descriptor = json.loads((ROOT/'tests/fixtures/39c-cost-qualification-45.json').read_bytes())
        base = json.loads((ROOT/descriptor['base_input']).read_bytes())
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
            for case in descriptor['cases']:
                row = dict(case=case['id'], passed=False)
                rows.append(row)
                with self.subTest(case=case['id']):
                    data = deepcopy(base)
                    data['business_program']['schema'] = 'aegisdc-business-cost-evaluation-v2'
                    data['business_program']['id'] += '-' + case['id']
                    data['duration_s'] = case['duration_s']
                    data['boundary_events'] = [r for r in data['boundary_events'] if r['time_s'] <= case['duration_s']]
                    data['dispatch_program']['decision_times_s'] = case.get('decision_times_s', [])
                    if case['id'] == 'no-human':
                        data['dispatch_program']['policy_program']['policy'] = 'no_human'
                    if case['id'] == 'rejected':
                        model, profile, gateway = crew_fixture()
                        data.update(scenario=model, work_program=crew_program(profile,
                            (gateway.next_frame(), crew_task('unqualified', ('worker_it',)))))
                        del data['dispatch_program']
                        data['boundary_events'] = []
                    elif case['id'] == 'shared-queue':
                        model, profile, gateway = crew_fixture((0, .25, .5))
                        intentions = [crew_task('holder', ('worker_cooling',), 'plate_hx'),
                                      crew_task('queued-a', ('worker_control',), 'internal_water'),
                                      crew_task('queued-b', ('worker_control',), 'intake_pump')]
                        data.update(scenario=model, work_program=crew_program(profile,
                            *((gateway.next_frame(), intention) for intention in intentions)))
                        del data['dispatch_program']
                        data['boundary_events'] = []
                    directory = output/case['id'] if output is not None else None
                    if directory is not None:
                        directory.mkdir()
                    save(directory, 'frozen-call-input.json', data)
                    self.facility_calls += 1
                    result = simulate_scenario(**data)
                    self.completed_native_horizons += 1
                    self.completed_native_duration_s += result['summary']['duration_s']
                    self.returned_decisions += len(result.get('policy_public_decisions', []))
                    identity = result['code_identity']
                    if directory is not None:
                        save_run(result, directory/'actual-run')
                    costs = result['business_evaluation']
                    save(directory, 'business-result.json', costs)
                    row.update(costs=costs, duration_s=result['summary']['duration_s'],
                               returned_decisions=len(result.get('policy_public_decisions', [])))
                    for path, expected in case['expected'].items():
                        actual = costs
                        for part in path.split('.'):
                            actual = actual[part]
                        self.assertEqual(actual, expected, path)
                    attribution = costs['failure_attribution']
                    self.assertTrue(all(value for value in attribution['reconciliation'].values()))
                    if case['id'] == 'shared-queue':
                        joint, = attribution['shared_queue_costs']
                        self.assertEqual(joint['task_ids'], ['queued-a', 'queued-b'])
                        self.assertEqual(joint['worker_ids'], ['worker_control'])
                        self.assertEqual(joint['actual']['queue_wait_person_s']['value'], .5)
                        by_id = {r['task_id']: r for r in attribution['per_task']}
                        self.assertEqual(by_id['queued-a']['actual']['queue_wait_person_s']['value'], .25)
                        self.assertEqual(by_id['queued-b']['actual']['queue_wait_person_s']['value'], 0)
                        self.assertEqual(len(attribution['unfinished_task_ids']), 3)
                    elif case['id'] == 'no-human':
                        self.assertEqual(attribution['per_task'], [])
                        self.assertEqual(attribution['shared_queue_costs'], [])
                    else:
                        task, = attribution['per_task']
                        self.assertEqual(task['status_at_horizon'], case['task_status'])
                        if case['id'] == 'rejected':
                            self.assertIsNone(task['issue_fee']['value'])
                        else:
                            self.assertEqual(task['issue_fee']['value'], 1)
                    row['passed'] = True
        finally:
            save(output, 'qualification.json', rows)
            if identity is not None:
                save(output, 'actual-execution-summary.json', dict(code_identity=identity, cases=rows,
                    facility_calls=self.facility_calls, completed_horizons=self.completed_native_horizons,
                    completed_duration_s=self.completed_native_duration_s, returned_decisions=self.returned_decisions))
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row['passed'] for row in rows))


if __name__ == '__main__':
    unittest.main()
