"""Actual cost dimensions through the complete facility run interface."""
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class BusinessActualCostTests(unittest.TestCase):
    def test_actual_occupation_admission_fees_and_computation_keep_distinct_units(self):
        data = json.loads((ROOT/'tests/fixtures/39c-actual-cost-42.json').read_bytes())
        output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None

        def save(name, value):
            if output is not None:
                with (output/name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, indent=2, allow_nan=False)
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

        self.assertEqual(costs['schema'], 'aegisdc-business-cost-result-v1')
        self.assertEqual(costs['visibility'], 'PRIVATE_EVALUATOR_ONLY')
        actual = costs['actual']
        for key, value in dict(worker_travel_person_s=0, worker_work_person_s=1, worker_wait_person_s=.25,
                               access_check_person_s=.25, rendezvous_wait_person_s=0, queue_wait_person_s=0).items():
            self.assertEqual(actual[key]['value'], value, key)
            self.assertEqual(actual[key]['unit'], 'person_s')
            self.assertEqual(actual[key]['status'], 'RECORDED')
        self.assertEqual(costs['personnel_total']['value'], 1.25)
        self.assertEqual(costs['personnel_total']['unit'], 'person_s')
        self.assertEqual(actual['tool_occupation_tool_s']['value'], 1.25)
        self.assertEqual(actual['tool_work_tool_s']['value'], 1)
        self.assertEqual(actual['tool_work_tool_s']['unit'], 'tool_s')
        self.assertTrue(costs['consistency']['wait_components_partition_total'])
        self.assertTrue(costs['consistency']['tool_work_within_occupation'])
        self.assertEqual(costs['admission']['spent_or_reserved']['person_s'], 10)
        self.assertEqual(costs['admission']['spent_or_reserved']['tool_s'], 10)
        self.assertEqual(costs['issue_fees']['value'], 1)
        self.assertEqual(costs['issue_fees']['unit'], 'declared_research_cost')
        self.assertIsNone(costs['distance_m']['value'])
        self.assertIsNone(costs['currency_payment']['value'])
        self.assertEqual(costs['task_outcomes']['counts'], {'completed': 1})
        self.assertEqual(costs['failure_attribution']['status'], 'NOT_IMPLEMENTED_FOR_THIS_VERSION')
        computation = costs['computation']
        self.assertEqual(computation['observed_selector_invocations'], 3)
        self.assertEqual(computation['observed_condition_assessment_invocations'], 3)
        self.assertEqual(computation['model_evaluations']['risk']['count'], 0)
        self.assertEqual(computation['model_evaluations']['action_value']['count'], 0)
        self.assertEqual(computation['llm_calls']['value'], 0)
        self.assertEqual(computation['training_calls']['value'], 0)
        self.assertIsNone(computation['internal_nested_calls']['value'])
        for key in ('selector_elapsed_ns', 'condition_assessment_elapsed_ns'):
            self.assertIs(type(computation[key]['value']), int)
            self.assertGreaterEqual(computation[key]['value'], 0)
            self.assertEqual(computation[key]['unit'], 'ns')
        self.assertEqual(self.returned_decisions, 3)


if __name__ == '__main__':
    unittest.main()
