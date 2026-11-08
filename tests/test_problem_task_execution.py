"""An arrived question causes actual professional travel and measurement."""
import json
import math
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class ProblemTaskExecutionTests(unittest.TestCase):
    def test_triggered_cooling_check_measures_only_after_real_crew_work(self):
        fixture = json.loads((ROOT / 'tests/fixtures/39b-triggered-inspection-v2.json').read_text(encoding='utf-8'))
        self.facility_calls = 1  # Charged before entry, including a constructor refusal in the red phase.
        result = simulate_scenario(fixture['model'], duration_s=4, step_s=.01,
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
        task = result['work_records'][0]
        self.assertEqual((task['id'], task['status']), ('cooling-desk/task-0', 'completed'))
        self.assertEqual((task['work_started_at_s'], task['completed_at_s']), (2.25, 3.25))
        record = next(row for row in result['inspection_public_snapshot']['records'] if row['id'] == 'cooling-desk-flow-0')
        self.assertEqual((record['observed_at_s'], record['arrived_at_s']), (3.25, 3.75))
        self.assertAlmostEqual(record['value'], math.sqrt(1 / 340), places=12)
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in result['policy_public_decisions']],
                         ['cooling-desk/task-0', None])
        self.assertNotIn('cooling-desk-flow-0', result['policy_public_decisions'][0]['frame']['evidence']['current_record_ids'])
        self.assertIn('cooling-desk-flow-0', result['policy_public_decisions'][1]['frame']['evidence']['current_record_ids'])
        for field, expected in [('worker_travel_person_s', 2), ('worker_work_person_s', 1), ('access_check_person_s', .25)]:
            self.assertAlmostEqual(result['summary'][field], expected, places=12)
        self.assertEqual(len(result['work_records']), 1)
        self.assertNotIn('intervention_private_audit', result)


if __name__ == '__main__':
    unittest.main()
