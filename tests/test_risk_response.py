import unittest
from patrol_rsi.risk_response import RiskEpisodes, ResponseTask, run_response
from patrol_rsi.reorder_execution import run_reorder

SPEC=dict(seed=0,scenario='aux_feeder_loss+cdu_fouling',duration_s=180,
          fault_start_s=335,noise_c=.2,estimator='nominal',control='feedback',resources='provisioned')

class RiskResponseTests(unittest.TestCase):
    def test_expired_event_does_not_swallow_a_new_rising_edge(self):
        ledger=RiskEpisodes(1)
        ledger.observe(0,[.2])
        ledger.observe(120,[0])
        self.assertIn(0,ledger.pending)
        ledger.observe(125,[.3])
        self.assertEqual(len(ledger.events),2)
        self.assertEqual(ledger.events[0]['status'],'expired')
        self.assertEqual(ledger.pending[0]['visible_s'],125)
        self.assertEqual(ledger.pending[0]['expires_s'],245)
        ledger.observe(130,[.4])
        self.assertEqual(len(ledger.events),2)

    def test_expiry_without_a_new_rising_edge_does_not_reopen(self):
        ledger=RiskEpisodes(1)
        ledger.observe(0,[.2])
        ledger.observe(125,[.3])
        self.assertFalse(ledger.pending)
        self.assertEqual(len(ledger.events),1)
        self.assertEqual(ledger.events[0]['status'],'expired')

    def test_opportunity_rule_can_protect_a_lower_risk_waiting_task(self):
        import numpy as np
        from patrol_rsi.contracts import DeniedOnlineTrace
        env=ResponseTask(SPEC,priority='opportunity')
        first,second=env.agents[0]['tour'][:2]
        risks=np.zeros(len(env.tasks));risks[first]=.8;risks[second]=.2
        env.public_risk=lambda:(risks,np.zeros(128))
        env.risk_episodes.observe(5,risks)
        def check(now,position,last,cursor,target,reserved):
            if now>5 and target==second and last[first]>0:
                return {'ok':False,'reason':'fixture_other_deadline'}
            return {'ok':True,'candidate_finish_s':now+10}
        env.checkers[0].check=check
        env.trace=DeniedOnlineTrace()
        choices=env.choose()
        self.assertEqual(choices[0],second)
        row=env.decisions[0]
        self.assertEqual(next(c for c in row['candidates'] if c['task']==first)['lost_next_opportunities'],[second])

    def test_each_priority_uses_the_same_certified_execution_boundary(self):
        for priority in ['risk','opportunity']:
            record,_=run_response(SPEC,priority=priority)
            self.assertEqual(record['metrics']['tasks_violating_exact_gap'],0)
            self.assertEqual(record['metrics']['invalid_assignments'],0)
            self.assertTrue(all(d['certificate']['ok'] for d in record['dispatches']))

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
