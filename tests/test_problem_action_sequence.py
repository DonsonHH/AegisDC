"""A public question opens paid inspection, named action and later recheck."""
from fractions import Fraction
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class ProblemActionSequenceTests(unittest.TestCase):
    def test_arrived_capacity_check_then_residual_action_then_actual_recheck(self):
        fixture = json.loads((ROOT / 'tests/fixtures/39b-network-action-sequence.json').read_text(encoding='utf-8'))
        self.facility_calls = 1
        result = simulate_scenario(fixture['model'], duration_s=5.5, step_s=.01,
                                   dispatch_program=fixture['dispatch_program'])
        self.returned_decisions = len(result['policy_public_decisions'])
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR'])
            save_run(result, output / 'actual-run')
            summary = dict(classification='PRIVATE_EVALUATOR_ENGINEERING_SUMMARY_NOT_RESEARCH_GAIN',
                           code_identity=result['code_identity'], facility_id=result['facility_id'],
                           work_records=result['work_records'], summary=result['summary'],
                           inspection_records=result['inspection_public_snapshot']['records'],
                           intervention_feedback=result['intervention_public_feedback'],
                           intervention_audit=result['intervention_private_audit'],
                           resource_ledger=result['policy_public_resource_ledger'],
                           decisions=[dict(as_of_s=row['frame']['as_of_s'],
                                           current_record_ids=row['frame']['evidence']['current_record_ids'],
                                           history=row['history'], choice=row['choice'])
                                      for row in result['policy_public_decisions']])
            with (output / 'actual-run-summary.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
        decisions = result['policy_public_decisions']
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in decisions],
                         ['network-case/inspect-0', 'network-case/action-0', 'network-case/recheck-0', None])
        tasks = {row['id']: row for row in result['work_records']}
        for identifier, start, finish in [('network-case/inspect-0', .25, 1.25),
                                           ('network-case/action-0', 2, 3),
                                           ('network-case/recheck-0', 3.75, 4.75)]:
            self.assertEqual((tasks[identifier]['work_started_at_s'], tasks[identifier]['completed_at_s']), (start, finish))
        records = {row['id']: row for row in result['inspection_public_snapshot']['records']}
        self.assertEqual(set(records), {'it-capacity-before', 'it-capacity-after'})
        for identifier, sample, arrival, value in [('it-capacity-before', 1.25, 1.75, .25),
                                                   ('it-capacity-after', 4.75, 5.25, .75)]:
            self.assertEqual((records[identifier]['observed_at_s'], records[identifier]['arrived_at_s'],
                              records[identifier]['value']), (sample, arrival, value))
        self.assertEqual(decisions[1]['history']['intervention_feedback'], [])
        report = decisions[2]['history']['intervention_feedback'][0]
        self.assertEqual((report['observed_at_s'], report['arrived_at_s'], report['outcome']), (3, 3.5, 'APPLIED'))
        self.assertFalse(report['risk_closed'])
        self.assertNotIn('it-capacity-before', decisions[0]['frame']['evidence']['current_record_ids'])
        self.assertNotIn('it-capacity-after', decisions[2]['frame']['evidence']['current_record_ids'])
        for field, expected in [('demand_service_unit_s', 5.5),
                                ('delivered_service_unit_s', float(Fraction(21, 8))),
                                ('service_deficit_time_s', float(Fraction(23, 8))),
                                ('worker_work_person_s', 3), ('access_check_person_s', .75),
                                ('worker_travel_person_s', 0)]:
            self.assertAlmostEqual(result['summary'][field], expected, places=12)
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'],
                         dict(person_s=24.75, tool_s=24.75, cost=3))
        final = decisions[-1]['choice']['questions'][0]
        self.assertEqual(final['workflow_status'], 'RECHECK_REPORTED_UNCLOSED')
        self.assertFalse(final['risk_closed'])
        self.assertIsNone(final['fault_probability'])


if __name__ == '__main__':
    unittest.main()
