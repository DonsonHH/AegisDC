"""Problem-triggered professional work at the existing public decision seam."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from aegis_dc.decision_view import DecisionGateway
from aegis_dc.dispatch_policy import choose_work

ROOT = Path(__file__).resolve().parents[1]


class ProblemTaskTests(unittest.TestCase):
    def test_arrived_work_order_opens_a_typed_problem_and_professional_check(self):
        fixture = json.loads((ROOT / 'tests/fixtures/39b-public-question-base.json').read_text(encoding='utf-8'))
        ledger = deepcopy(fixture['ledger'])
        ledger['records'] = [dict(
            id='it-report-01', source_id='it-service-desk', target_id='network',
            observable_id='problem_reported', unit='1', value=True,
            observed_at_s=1, arrived_at_s=2, valid_until_s=9,
            quality=dict(status='reported', error_bound=None, note='Unconfirmed synthetic service-desk claim.'),
            provenance=dict(origin_id='case-it-01', copied_from_record_id=None),
        )]
        plan = dict(schema='aegisdc-public-preparation-plan-v1', id='39b-first-public-work-order',
                    basis='synthetic_assumption', time_unit='s', decision_times_s=[2], requests=[])
        frame = DecisionGateway(fixture['nominal_knowledge'], ledger, plan).next_frame()
        program = dict(schema='aegisdc-problem-driven-policy-v1', id='39b-public-trigger',
                       basis='synthetic_assumption', time_unit='s', policy='fifo',
                       workforce_profile=fixture['workforce_profile'], templates=[fixture['template']])
        self.public_choice_calls = 1  # Billed before the public call, including an expected red failure.
        choice = choose_work(frame, program, dict(issued=[], work_feedback=[], question_instances=[]))
        self.assertEqual(choice['chosen_candidate_id'], 'it-desk/task-0')
        self.assertEqual(choice['work_intention']['id'], 'it-desk/task-0')
        self.assertEqual(choice['work_intention']['target_id'], 'network')
        self.assertEqual(choice['work_intention']['crew'], [dict(worker_id='worker_it', qualification_id='qualified_it_inspection')])
        question = choice['questions'][0]
        self.assertEqual((question['id'], question['origin_id'], question['trigger_record_id']),
                         ('it-desk/question-0', 'case-it-01', 'it-report-01'))
        self.assertEqual(question['quantification'], 'UNMODELED_IN_THIS_FACTORY')
        self.assertIsNone(question['fault_probability'])
        self.assertIsNone(question['expected_service_deficit_time_s'])
        self.assertFalse(choice['generated_tour'])
        self.assertFalse(choice['execution_permission'])


if __name__ == '__main__':
    unittest.main()
