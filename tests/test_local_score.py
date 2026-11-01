import json
import unittest

from patrol_rsi.local_score import ScoreExpression, response_example, parse_response, require_mutation, FEATURES


class LocalScoreTests(unittest.TestCase):
    def test_single_contract_example_passes_real_parser(self):
        example=response_example();expr,reason=parse_response(json.dumps(example))
        self.assertEqual(expr.source,example['score_expression'])
        self.assertTrue(reason)
        values={name:0. for name in FEATURES};values['risk_delay']=2.;values['deadline_pressure']=.5;values['travel_cost']=1.
        self.assertAlmostEqual(expr.evaluate(values),2.15)
        with self.assertRaises(ValueError):require_mutation(expr,ScoreExpression('risk_delay+0.20*deadline_pressure+0.05*travel_cost'))

    def test_forbidden_or_nonfinite_expressions_are_rejected(self):
        for source in ('','seed','x[0]','risk_delay.__class__','__import__("os")','float("nan")','1e309','risk_delay*0','0.1','risk_delay**2'):
            with self.subTest(source=source),self.assertRaises(ValueError):ScoreExpression(source)
        for obj in ([],{'score_expression':['risk_delay'],'mechanism':'x'}, {'score_expression':'unknown','mechanism':'x'}):
            with self.assertRaises(ValueError):parse_response(json.dumps(obj))
        expr=ScoreExpression('safe_div(risk_delay,travel_cost)')
        values={name:0. for name in FEATURES};values['risk_delay']=.1
        self.assertAlmostEqual(expr.evaluate(values),100000.)

    def test_zero_cancellation_cannot_hide_intermediate_numeric_failure(self):
        expr=ScoreExpression('(risk_delay*10*10*10*10*10*10*10)*0 + freshness_delay')
        with self.assertRaises(ValueError):expr.evaluate({name:1. for name in FEATURES})
        self.assertNotEqual(expr.identity,ScoreExpression('freshness_delay').identity)


if __name__=='__main__':unittest.main()
