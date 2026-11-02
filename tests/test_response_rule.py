import unittest

from patrol_rsi.response_rule import ResponseRule, select_response
from patrol_rsi.risk_response import run_response, ResponseTask
from patrol_rsi.reorder_execution import run_reorder
from patrol_rsi.contracts import DeniedOnlineTrace

SPEC = dict(seed=0, scenario='aux_feeder_loss+cdu_fouling', duration_s=180,
            fault_start_s=335, noise_c=.2, estimator='nominal', control='feedback', resources='provisioned')


class ResponseRuleTests(unittest.TestCase):
    def test_defer_keeps_event_and_executes_the_certified_routine_head(self):
        rule = ResponseRule(bias=-1).to_dict()
        env = ResponseTask(SPEC, response_rule=rule, extra_visit_budget=12)
        observed = False
        while not env.done:
            previous = len(env.binary_decisions)
            trace, env.trace = env.trace, DeniedOnlineTrace()
            try:choices = env.choose()
            finally:env.trace = trace
            rows = [r for r in env.binary_decisions[previous:] if r['choice'] == 'defer']
            if rows:
                row = rows[0]; target = row['event_task']; agent = row['agent']
                self.assertEqual(choices[agent], row['routine_head'])
                self.assertIn(target, env.risk_episodes.pending)
                self.assertNotEqual(row['routine_head'], target)
                cursor = env.cursor[agent]
                self.assertEqual(env.extra_dispatched, 0)
                env.step(choices)
                self.assertIn(target, env.risk_episodes.pending)
                self.assertEqual(env.cursor[agent], cursor)
                observed = True
                break
            env.step(choices)
        self.assertTrue(observed)
        record, _ = run_response(SPEC, response_rule=rule, extra_visit_budget=12)
        tour, _ = run_reorder(SPEC,None,{'method':'T'})
        self.assertEqual(record['action_log'], tour['action_log'])
        self.assertEqual(record['metrics']['extra_event_visits'], 0)
        self.assertEqual(record['metrics']['tasks_violating_exact_gap'], 0)

    def test_only_event_legal_forces_response_even_for_defer_rule(self):
        event = {'task':2,'certificate':{'ok':True},'budget_allowed':True}
        result = select_response(ResponseRule(bias=-1),event,None,100)
        self.assertEqual(result['choice'],'respond')
        self.assertEqual(result['selected'],event)
        self.assertIsNone(result['features'])
        routine = {'task':0,'certificate':{'ok':True},'budget_allowed':True}
        result = select_response(ResponseRule(),None,routine,100)
        self.assertEqual(result['selected'],routine)
        with self.assertRaises(ValueError):
            select_response(ResponseRule(),dict(event,budget_allowed=False),routine,100,100)

    def test_illegal_schema_numbers_and_duplicates_are_rejected(self):
        import copy
        base = ResponseRule().to_dict()
        invalid = [dict(base, version=True), dict(base, code='return true'),
                   dict(base, bias=10**1000), dict(base, bias=True), dict(base, bias=float('nan')),
                   dict(base, weights=dict(base['weights'], risk=5)),
                   dict(base, weights=dict(base['weights'], future_temperature=1))]
        for candidate in invalid:
            with self.subTest(candidate_type=type(candidate['bias']).__name__):
                with self.assertRaises(ValueError):ResponseRule.from_dict(candidate)
        with self.assertRaises(ValueError):
            ResponseRule.from_json('{"version":1,"version":1,"bias":0,"weights":{}}')
        changed = copy.deepcopy(base)
        rule = ResponseRule.from_dict(changed)
        changed['weights']['risk'] = 4
        self.assertEqual(rule.to_dict(), base)

    def test_zero_rule_preserves_every_fifo_dispatch(self):
        original, _ = run_response(SPEC, extra_visit_budget=12)
        selected, _ = run_response(SPEC, extra_visit_budget=12, response_rule=ResponseRule().to_dict())
        self.assertEqual(selected['action_log'], original['action_log'])
        self.assertEqual(selected['inspection_events'], original['inspection_events'])
        self.assertTrue(selected['binary_decisions'])
        self.assertTrue(all(d['choice'] == 'respond' for d in selected['binary_decisions'] if d['reason'] == 'rule'))

    def test_bounded_rule_roundtrip_and_score_direction(self):
        rule = ResponseRule.from_dict({'version': 1, 'bias': -.25,
            'weights': {'risk': 2, 'age': 0, 'extra_time': -1, 'slack_difference': 0}})
        self.assertTrue(rule.respond({'risk': .5, 'age': 0, 'extra_time': .25, 'slack_difference': 0}))
        self.assertFalse(rule.respond({'risk': 0, 'age': 0, 'extra_time': .5, 'slack_difference': 0}))
        self.assertEqual(ResponseRule.from_dict(rule.to_dict()), rule)


if __name__ == '__main__':
    unittest.main()
