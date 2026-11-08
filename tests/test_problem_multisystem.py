"""IT and electrical investigations share a service, but retain professional gates."""
from fractions import Fraction
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class MultisystemProblemTests(unittest.TestCase):
    def test_it_and_power_checks_execute_with_separate_tools_and_shared_service_context(self):
        fixture = json.loads((ROOT / 'tests/fixtures/39b-power-it-inspections.json').read_text(encoding='utf-8'))
        self.facility_calls = 1
        result = simulate_scenario(fixture['model'], duration_s=3, step_s=.01,
                                   dispatch_program=fixture['dispatch_program'])
        self.returned_decisions = len(result['policy_public_decisions'])
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR'])
            save_run(result, output / 'actual-run')
            summary = dict(classification='PRIVATE_EVALUATOR_ENGINEERING_SUMMARY_NOT_RESEARCH_GAIN',
                           code_identity=result['code_identity'], facility_id=result['facility_id'],
                           work_records=result['work_records'], summary=result['summary'],
                           inspection_records=result['inspection_public_snapshot']['records'],
                           inspection_feedback=result['inspection_public_feedback'],
                           decisions=[dict(as_of_s=row['frame']['as_of_s'],
                                           current_record_ids=row['frame']['evidence']['current_record_ids'],
                                           chosen_candidate_id=row['choice']['chosen_candidate_id'],
                                           questions=row['choice']['questions'])
                                      for row in result['policy_public_decisions']])
            with (output / 'actual-run-summary.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
        decisions = result['policy_public_decisions']
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in decisions],
                         ['a-it-desk/task-0', 'b-power-desk/task-0', None])
        tasks = {row['id']: row for row in result['work_records']}
        self.assertEqual((tasks['a-it-desk/task-0']['work_started_at_s'], tasks['a-it-desk/task-0']['completed_at_s']), (.25, 1.25))
        self.assertEqual((tasks['b-power-desk/task-0']['work_started_at_s'], tasks['b-power-desk/task-0']['completed_at_s']), (.75, 1.75))
        records = {row['id']: row for row in result['inspection_public_snapshot']['records']}
        network, power = records['it-capacity-0'], records['power-input-0']
        self.assertEqual((network['observed_at_s'], network['arrived_at_s'], network['value'], network['unit']), (1.25, 1.75, .25, '1'))
        self.assertEqual((power['observed_at_s'], power['arrived_at_s'], power['unit']), (1.75, 2.25, 'W'))
        self.assertAlmostEqual(power['value'], float(Fraction(212500000, 97)), places=6)
        for early in decisions[:2]:
            self.assertNotIn('it-capacity-0', early['frame']['evidence']['current_record_ids'])
            self.assertNotIn('power-input-0', early['frame']['evidence']['current_record_ids'])
        for field, expected in [('demand_service_unit_s', 3), ('delivered_service_unit_s', .75),
                                ('worker_work_person_s', 2), ('access_check_person_s', .5), ('worker_travel_person_s', 0)]:
            self.assertAlmostEqual(result['summary'][field], expected, places=12)
        questions = {row['catalog_question_id']: row for row in decisions[0]['choice']['questions']}
        for question in questions.values():
            self.assertIsNone(question['fault_probability'])
            self.assertIsNone(question['expected_service_deficit_time_s'])
            self.assertEqual(question['service_context']['classification'], 'STATIC_FUNCTIONAL_PATHS_NOT_AVAILABLE_CAPACITY')
            self.assertEqual(question['service_context']['paths'][0]['service_id'], 'critical_service')
        self.assertEqual(questions['it-dependence']['service_context']['paths'][0]['edge_ids'], ['f13'])
        self.assertEqual(questions['power']['service_context']['paths'][0]['edge_ids'], ['f3', 'f12'])
        self.assertNotIn('intervention_private_audit', result)


if __name__ == '__main__':
    unittest.main()
