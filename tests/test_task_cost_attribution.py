"""A safety-aborted task retains actual occupation and its issued fee."""
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class TaskCostAttributionTests(unittest.TestCase):
    def test_actual_safety_abort_keeps_its_elapsed_cost_and_issued_fee(self):
        data = json.loads((ROOT/'tests/fixtures/39c-task-cost-abort-44.json').read_bytes())
        output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None

        def save(name, obj):
            if output is not None:
                with (output/name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(obj, stream, indent=2, allow_nan=False)
                    stream.write('\n')

        save('frozen-call-input.json', data)
        self.facility_calls = 1
        result = simulate_scenario(**data)
        self.completed_native_horizons = 1
        self.completed_native_duration_s = result['summary']['duration_s']
        self.returned_decisions = len(result['policy_public_decisions'])
        if output is not None:
            save_run(result, output/'actual-run')
        costs = result['business_evaluation']
        save('business-result.json', costs)
        save('actual-execution-summary.json', dict(code_identity=result['code_identity'], summary=result['summary'],
            work_records=result['work_records'], resource_ledger=result['policy_public_resource_ledger'],
            computation_audit=result['policy_computation_audit']))
        self.assertEqual(costs['schema'], 'aegisdc-business-cost-result-v2')
        task, = result['work_records']
        self.assertEqual(task['status'], 'aborted')
        self.assertEqual(task['finished_at_s'], .75)
        attributed = costs['failure_attribution']
        self.assertEqual(attributed['status'], 'ACTUAL_TRACE_WITH_SHARED_QUEUE_COSTS')
        self.assertEqual(attributed['failure_task_ids'], ['network-case/inspect-0'])
        row, = attributed['per_task']
        self.assertEqual(row['task_id'], 'network-case/inspect-0')
        self.assertEqual(row['status_at_horizon'], 'aborted')
        expected = dict(worker_travel_person_s=0, worker_work_person_s=.5, worker_wait_person_s=.25,
                        access_check_person_s=.25, rendezvous_wait_person_s=0, queue_wait_person_s=0,
                        tool_occupation_tool_s=.75, tool_work_tool_s=.5)
        for key, value in expected.items():
            self.assertEqual(row['actual'][key]['value'], value, key)
            self.assertTrue(attributed['reconciliation'][key], key)
        self.assertEqual(row['issue_fee']['value'], 1)
        self.assertEqual(row['issue_fee']['unit'], 'declared_research_cost')
        self.assertTrue(attributed['issue_fee_reconciled'])
        self.assertEqual(attributed['shared_queue_costs'], [])
        self.assertEqual(costs['personnel_total']['value'], .75)
        self.assertEqual(costs['admission']['spent_or_reserved']['person_s'], 10)
        self.assertEqual(costs['admission']['spent_or_reserved']['cost'], 1)
        self.assertEqual(self.returned_decisions, 3)


if __name__ == '__main__':
    unittest.main()
