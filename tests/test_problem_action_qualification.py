"""Qualify direct, deferred, failed and no-human paths at the facility seam."""
from copy import deepcopy
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


def network_fixture():
    return json.loads((ROOT / 'tests/fixtures/39b-network-action-sequence.json').read_text(encoding='utf-8'))


class ProblemActionQualificationTests(unittest.TestCase):
    def run_case(self, fixture, name, duration):
        self.facility_calls = getattr(self, 'facility_calls', 0) + 1
        result = simulate_scenario(fixture['model'], duration_s=duration, step_s=.01,
                                   dispatch_program=fixture['dispatch_program'])
        self.returned_decisions = getattr(self, 'returned_decisions', 0) + len(result['policy_public_decisions'])
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) / 'cases' / name
            output.mkdir(parents=True, exist_ok=False)
            save_run(result, output / 'actual-run')
            summary = dict(classification='PRIVATE_EVALUATOR_FINITE_ENGINEERING_QUALIFICATION',
                           case_id=name, code_identity=result['code_identity'],
                           work_records=result['work_records'], summary=result['summary'],
                           inspection_records=result['inspection_public_snapshot']['records'],
                           intervention_feedback=result['intervention_public_feedback'],
                           resource_ledger=result['policy_public_resource_ledger'],
                           decisions=[dict(as_of_s=row['frame']['as_of_s'],
                                           history=row['history'], choice=row['choice'])
                                      for row in result['policy_public_decisions']])
            with (output / 'summary.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
        return result

    def test_direct_filter_action_does_not_run_initial_check_and_has_paid_residual_recheck(self):
        fixture = json.loads((ROOT / 'tests/fixtures/39b-direct-filter-sequence.json').read_text(encoding='utf-8'))
        result = self.run_case(fixture, 'direct-filter', 6)
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in result['policy_public_decisions']],
                         ['cooling-direct/action-0', 'cooling-direct/recheck-0', None])
        tasks = {r['id']: r for r in result['work_records']}
        self.assertEqual(set(tasks), {'cooling-direct/action-0', 'cooling-direct/recheck-0'})
        self.assertEqual(tasks['cooling-direct/action-0']['completed_at_s'], 3.25)
        self.assertEqual(tasks['cooling-direct/recheck-0']['completed_at_s'], 5)
        records = result['inspection_public_snapshot']['records']
        self.assertEqual(len(records), 1)
        self.assertEqual((records[0]['id'], records[0]['observed_at_s'], records[0]['arrived_at_s']),
                         ('flow-after-clean', 5, 5.5))
        self.assertAlmostEqual(records[0]['value'], math.sqrt(1 / 180), places=12)
        self.assertNotAlmostEqual(records[0]['value'], .1, places=4)
        for field, expected in [('worker_work_person_s', 2), ('worker_travel_person_s', 2), ('access_check_person_s', .5)]:
            self.assertAlmostEqual(result['summary'][field], expected, places=12)
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'],
                         dict(person_s=16.25, tool_s=16.25, cost=2))
        self.assertFalse(result['policy_public_decisions'][-1]['choice']['questions'][0]['risk_closed'])

    def test_normal_and_unknown_measurements_withhold_action_and_recheck(self):
        for name in ['normal-network', 'unknown-network']:
            with self.subTest(case=name):
                fixture = network_fixture()
                dispatch = fixture['dispatch_program']
                if name == 'normal-network':
                    next(r for r in fixture['model']['parameters'] if r['id'] == 'network_service_capacity')['value'] = 1
                else:
                    model = dispatch['inspection_program']['profile']['nonfixed_profile']['models'][0]['model']
                    model['kind'] = 'unknown'
                    del model['reported_error_bound']
                    dispatch['policy_program']['inspection_declaration'] = deepcopy(dispatch['inspection_program']['profile'])
                result = self.run_case(fixture, name, 5.5)
                self.assertEqual([r['choice']['chosen_candidate_id'] for r in result['policy_public_decisions']],
                                 ['network-case/inspect-0', None, None, None])
                self.assertEqual(len(result['work_records']), 1)
                self.assertEqual(result['intervention_public_feedback'], [])
                measured = result['inspection_public_snapshot']['records'][0]
                if name == 'normal-network':
                    self.assertEqual(measured['value'], 1)
                else:
                    self.assertIsNone(measured['value'])
                    self.assertEqual(measured['quality']['status'], 'unknown')
                self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'], dict(person_s=10, tool_s=10, cost=1))

    def test_authority_expiring_at_actual_completion_applies_no_effect_and_no_recheck(self):
        fixture = network_fixture()
        dispatch = fixture['dispatch_program']
        dispatch['intervention_program']['profile']['authorizations'][0]['expires_at_s'] = 3
        dispatch['policy_program']['intervention_declaration'] = deepcopy(dispatch['intervention_program'])
        result = self.run_case(fixture, 'expired-at-completion', 5.5)
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in result['policy_public_decisions']],
                         ['network-case/inspect-0', 'network-case/action-0', None, None])
        self.assertEqual(len(result['work_records']), 2)
        report = result['intervention_public_feedback'][0]
        self.assertEqual((report['observed_at_s'], report['arrived_at_s'], report['outcome'], report['reason']),
                         (3, 3.5, 'NO_EFFECT', 'authorization_unavailable_at_completion'))
        self.assertEqual([r['id'] for r in result['inspection_public_snapshot']['records']], ['it-capacity-before'])
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], float(Fraction(11, 8)), places=12)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], float(Fraction(33, 8)), places=12)
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'], dict(person_s=18.25, tool_s=18.25, cost=2))
        self.assertEqual(result['policy_public_decisions'][-1]['choice']['questions'][0]['workflow_status'], 'ACTION_NO_EFFECT_UNCLOSED')

    def test_no_human_retains_unconfirmed_problem_without_work_or_measurement(self):
        fixture = network_fixture()
        fixture['dispatch_program']['policy_program']['policy'] = 'no_human'
        fixture['dispatch_program']['decision_times_s'] = [0, 2]
        result = self.run_case(fixture, 'no-human', 2)
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in result['policy_public_decisions']], [None, None])
        self.assertEqual(result['work_records'], [])
        self.assertEqual(result['inspection_public_snapshot']['records'], [])
        self.assertEqual(result['intervention_public_feedback'], [])
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'], dict(person_s=0, tool_s=0, cost=0))
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 1.5, places=12)


if __name__ == '__main__':
    unittest.main()
