"""Actual facility execution keeps physical and administrative instance closure separate."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class NativeInstanceReviewTests(unittest.TestCase):
    def test_native_v5_old_own_closure_new_instance_acceptance_and_producer_guards(self):
        base = json.loads((ROOT/'tests/fixtures/39c-native-review-50.json').read_bytes())
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
            for case in ('native-v5', 'producer-mismatch', 'legacy-v4-refusal'):
                row = dict(case=case, passed=False)
                rows.append(row)
                with self.subTest(case=case):
                    data = deepcopy(base)
                    if case == 'producer-mismatch':
                        data['dispatch_program']['closure_program']['intervention_declaration']['bindings'][0]['setting'] = 1.1
                    elif case == 'legacy-v4-refusal':
                        data['dispatch_program']['schema'] = 'aegisdc-policy-run-program-v4'
                    directory = output/case if output is not None else None
                    if directory is not None:
                        directory.mkdir()
                    save(directory, 'frozen-call-input.json', data)
                    self.facility_calls += 1
                    try:
                        result = simulate_scenario(**data)
                    except ValueError as error:
                        if case == 'native-v5':
                            raise
                        expected = ('Closure and execution must share the same public action declaration'
                                    if case == 'producer-mismatch' else 'Problem workflow requires an instance-scoped closure declaration')
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
                    row.update(duration_s=result['summary']['duration_s'], returned_decisions=len(result['policy_public_decisions']))
                    save(directory, 'business-result.json', result['business_evaluation'])
                    public = [dict(at_s=d['frame']['as_of_s'], lifecycle=d['choice']['question_lifecycle'],
                                   selected=d['choice']['chosen_candidate_id']) for d in result['policy_public_decisions']]
                    save(directory, 'public-lifecycle.json', public)
                    row['public_lifecycle'] = public
                    self.assertEqual(case, 'native-v5', 'A guarded input unexpectedly completed')
                    first_closed = min(d['at_s'] for d in public for q in d['lifecycle']['questions']
                        if q['question_id']=='cooling-direct/question-0' and q['status']=='VERIFIED_CLOSED')
                    self.assertEqual(first_closed, 5.5)
                    self.assertEqual(len(result['policy_public_decisions']), 7)
                    latest = {q['question_id']:q for q in public[-1]['lifecycle']['questions']}
                    self.assertEqual(latest['cooling-direct/question-0']['status'], 'VERIFIED_CLOSED')
                    second = latest['cooling-direct/question-1']
                    self.assertEqual(second['opened_at_s'], 5.75)
                    self.assertEqual(second['status'], 'RISK_ACCEPTED')
                    self.assertTrue(second['question_closed'])
                    self.assertFalse(second['risk_closed'])
                    self.assertFalse(second['physical_restoration_claim'])
                    self.assertFalse(second['own_recheck']['passed'])
                    self.assertEqual(min(d['at_s'] for d in public for q in d['lifecycle']['questions']
                        if q['question_id']=='cooling-direct/question-1' and q['status']=='RISK_ACCEPTED'), 5.75)
                    self.assertEqual([r['id'] for r in result['work_records']],
                                     ['cooling-direct/action-0','cooling-direct/recheck-0'])
                    row['passed'] = True
        finally:
            save(output, 'qualification.json', rows)
            if identity is not None:
                save(output, 'actual-execution-summary.json', dict(code_identity=identity,cases=rows,
                    facility_calls=self.facility_calls,completed_horizons=self.completed_native_horizons,
                    completed_duration_s=self.completed_native_duration_s,returned_decisions=self.returned_decisions))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r['passed'] for r in rows))


if __name__ == '__main__':
    unittest.main()
