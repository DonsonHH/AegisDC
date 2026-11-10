"""Existing closure counters and absent fee concepts at the facility run seam."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class CostAuditCorrectionTests(unittest.TestCase):
    def test_existing_closure_audit_counts_and_no_admission_fee_applicability(self):
        base = json.loads((ROOT/'tests/fixtures/39c-cost-audit-43.json').read_bytes())
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
            for name in ('closure-audit', 'no-admission'):
                row = dict(case=name, passed=False)
                rows.append(row)
                with self.subTest(case=name):
                    data = deepcopy(base)
                    if name == 'no-admission':
                        del data['dispatch_program']
                        data['duration_s'] = .5
                    directory = output/name if output is not None else None
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
                    row.update(costs=costs, returned_decisions=len(result.get('policy_public_decisions', [])),
                               duration_s=result['summary']['duration_s'])
                    if name == 'closure-audit':
                        self.assertEqual([r['instance_closure_evaluations'] for r in result['policy_computation_audit']], [1, 1, 1])
                        count = costs['computation']['instance_closure_evaluations']
                        self.assertEqual(count['count'], 3)
                        self.assertEqual(count['records_with_count'], 3)
                        self.assertEqual(count['audit_records'], 3)
                        self.assertEqual(count['coverage'], 'ALL_AUDIT_RECORDS')
                        self.assertEqual(costs['computation']['audit_record_details'], result['policy_computation_audit'])
                        self.assertIsNone(costs['computation']['internal_nested_calls']['value'])
                    else:
                        self.assertIsNone(costs['issue_fees']['value'])
                        self.assertEqual(costs['issue_fees']['status'], 'NOT_APPLICABLE')
                        self.assertEqual(costs['issue_fees']['unavailable_reason'], 'NO_ADMISSION_LEDGER')
                        self.assertIsNone(costs['actual']['worker_wait_person_s']['value'])
                        self.assertIsNone(costs['personnel_total']['value'])
                    row['passed'] = True
        finally:
            save(output, 'qualification.json', rows)
            if identity is not None:
                save(output, 'actual-execution-summary.json', dict(code_identity=identity, cases=rows,
                    facility_calls=self.facility_calls, completed_horizons=self.completed_native_horizons,
                    completed_duration_s=self.completed_native_duration_s, returned_decisions=self.returned_decisions))
        self.assertTrue(all(row['passed'] for row in rows))


if __name__ == '__main__':
    unittest.main()
