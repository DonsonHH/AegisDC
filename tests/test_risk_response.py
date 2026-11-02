import unittest
from patrol_rsi.risk_response import RiskEpisodes, ResponseTask, run_response
from patrol_rsi.reorder_execution import run_reorder

SPEC=dict(seed=0,scenario='aux_feeder_loss+cdu_fouling',duration_s=180,
          fault_start_s=335,noise_c=.2,estimator='nominal',control='feedback',resources='provisioned')

class RiskResponseTests(unittest.TestCase):
    def test_old_normal_check_does_not_discharge_new_risk_and_confirmation_deduplicates(self):
        ledger=RiskEpisodes(1)
        ledger.complete({'task':0,'time_s':10,'alarm':False,'agent':0})
        ledger.observe(20,[.2])
        self.assertEqual(len(ledger.pending),1)
        ledger.complete({'task':0,'time_s':30,'alarm':True,'agent':0})
        ledger.observe(35,[.4])
        self.assertFalse(ledger.pending)
        ledger.observe(40,[0]);ledger.observe(45,[.3])
        self.assertEqual(len(ledger.events),2)

    def test_single_step_without_event_responses_is_exactly_tour(self):
        a,_=run_reorder(SPEC,None,{'method':'T'})
        b,_=run_response(SPEC,False)
        self.assertEqual(a['action_log'],b['action_log'])
        self.assertEqual(a['metrics']['completed_inspections'],b['metrics']['completed_inspections'])

    def test_response_checks_ownership_reservation_and_horizon(self):
        env=ResponseTask(SPEC);a=env.agents[0];checker=env.checkers[0];j=a['tour'][0]
        self.assertFalse(checker.check(5,a['position'],env.last_inspection,0,j,{j})['ok'])
        foreign=next(k for k in range(len(env.tasks)) if k not in a['allowed'])
        self.assertFalse(checker.check(5,a['position'],env.last_inspection,0,foreign,set())['ok'])
        self.assertFalse(checker.check(1799,a['position'],env.last_inspection,0,j,set())['ok'])

    def test_inserted_event_does_not_skip_routine_head_and_all_revisits_hold(self):
        record,_=run_response(SPEC)
        self.assertEqual(record['metrics']['tasks_violating_exact_gap'],0)
        extras=[d for d in record['dispatches'] if d['extra_event_visit']]
        self.assertTrue(extras)
        for d in extras:
            following=next((n for n in record['dispatches'] if n['agent']==d['agent'] and n['time_s']>d['time_s']),None)
            if following:self.assertEqual(following['routine_head'],d['routine_head'])

if __name__=='__main__':unittest.main()
