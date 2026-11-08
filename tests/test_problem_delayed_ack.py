"""Actual unequal channel delays gate recheck and preserve spent envelopes."""
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class DelayedActionAcknowledgmentTests(unittest.TestCase):
    def test_recheck_waits_for_work_ack_and_spent_action_survives_stale_initial_reading(self):
        fixture = json.loads((ROOT / 'tests/fixtures/39b-network-action-sequence.json').read_text(encoding='utf-8'))
        dispatch = fixture['dispatch_program']
        dispatch['policy_program']['workforce_profile']['feedback_latency_s'] = .75
        dispatch['decision_times_s'] = [0, 1.75, 2, 3.75, 4, 7]
        self.facility_calls = 1
        result = simulate_scenario(fixture['model'], duration_s=7, step_s=.01, dispatch_program=dispatch)
        self.returned_decisions = len(result['policy_public_decisions'])
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR'])
            save_run(result, output / 'actual-run')
            summary = dict(classification='PRIVATE_EVALUATOR_FINITE_DELAYED_ACK_QUALIFICATION',
                           code_identity=result['code_identity'], work_records=result['work_records'],
                           summary=result['summary'], inspection_records=result['inspection_public_snapshot']['records'],
                           intervention_feedback=result['intervention_public_feedback'],
                           resource_ledger=result['policy_public_resource_ledger'],
                           decisions=[dict(as_of_s=r['frame']['as_of_s'], history=r['history'], choice=r['choice'])
                                      for r in result['policy_public_decisions']])
            with (output / 'actual-run-summary.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
        decisions = result['policy_public_decisions']
        self.assertEqual([r['choice']['chosen_candidate_id'] for r in decisions],
                         ['network-case/inspect-0', None, 'network-case/action-0', None, 'network-case/recheck-0', None])
        waiting = decisions[3]
        self.assertEqual(waiting['history']['intervention_feedback'][0]['outcome'], 'APPLIED')
        self.assertEqual(waiting['choice']['questions'][0]['workflow_status'], 'ACTION_APPLIED_AWAITING_WORK_ACK')
        self.assertFalse(next(r for r in waiting['choice']['stage_gates'] if r['stage'] == 'recheck')['prerequisites_met'])
        tasks = {r['id']: r for r in result['work_records']}
        self.assertEqual(tasks['network-case/action-0']['completed_at_s'], 3.25)
        self.assertEqual(tasks['network-case/recheck-0']['completed_at_s'], 5.25)
        records = {r['id']: r for r in result['inspection_public_snapshot']['records']}
        self.assertEqual(records['it-capacity-before']['availability'], 'stale')
        self.assertEqual((records['it-capacity-after']['observed_at_s'], records['it-capacity-after']['arrived_at_s'],
                          records['it-capacity-after']['value']), (5.25, 5.75, .75))
        self.assertEqual(result['policy_public_resource_ledger']['spent_or_reserved'], dict(person_s=24.5, tool_s=24.5, cost=3))
        for key, expected in [('demand_service_unit_s', 7), ('delivered_service_unit_s', 3.625),
                              ('service_deficit_time_s', 3.375), ('worker_work_person_s', 3), ('access_check_person_s', .75)]:
            self.assertAlmostEqual(result['summary'][key], expected, places=12)
        self.assertFalse(decisions[-1]['choice']['questions'][0]['risk_closed'])


if __name__ == '__main__':
    unittest.main()
