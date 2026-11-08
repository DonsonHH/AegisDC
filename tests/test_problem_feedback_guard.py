"""Public action reports cannot contradict declared authority or work completion."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.decision_view import DecisionGateway
from aegis_dc.dispatch_policy import choose_work

ROOT = Path(__file__).resolve().parents[1]


class ProblemFeedbackGuardTests(unittest.TestCase):
    def test_contradictory_applied_reports_are_refused_at_the_public_boundary(self):
        fixture = json.loads((ROOT / 'tests/fixtures/39b-feedback-contradictions.json').read_text(encoding='utf-8'))
        outcomes = []
        for variant in ['expired-authorization', 'aborted-work']:
            program = deepcopy(fixture['policy_program'])
            history = deepcopy(fixture['history'])
            report = history['intervention_feedback'][0]
            report.update(outcome='APPLIED', reason=None)
            if variant == 'aborted-work':
                program['intervention_declaration']['profile']['authorizations'][0]['expires_at_s'] = 10
                completion = next(r for r in history['work_feedback'] if r['task_id'] == report['task_id'])
                completion.update(status='aborted', reason='DECLARED_ENGINEERING_CONTRADICTION')
            plan = dict(schema='aegisdc-public-preparation-plan-v1', id='39b-feedback-refusal',
                        basis='synthetic_assumption', time_unit='s', decision_times_s=[3.5], requests=[])
            frame = DecisionGateway(fixture['nominal_knowledge'], fixture['evidence_ledger'], plan).next_frame()
            self.public_choice_calls = getattr(self, 'public_choice_calls', 0) + 1
            try:
                choice = choose_work(frame, program, history)
                outcomes.append(dict(case=variant, result='ACCEPTED_CONTRADICTION', chosen=choice['chosen_candidate_id']))
            except ValueError as error:
                outcomes.append(dict(case=variant, result='REFUSED', reason=str(error)))
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            with (Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) / 'public-refusal-summary.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(dict(classification='PUBLIC_CONTRACT_ENGINEERING_NOT_RESEARCH_TRIAL', outcomes=outcomes), stream, indent=2)
                stream.write('\n')
        self.assertEqual([r['result'] for r in outcomes], ['REFUSED', 'REFUSED'], 'APPLIED contradiction guards')
        self.assertIn('authorization', outcomes[0]['reason'])
        self.assertIn('completion', outcomes[1]['reason'])


if __name__ == '__main__':
    unittest.main()
