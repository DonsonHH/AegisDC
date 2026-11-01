import unittest
from copy import deepcopy

from patrol_rsi.baseline_correction import Rule,choose_advantage,parse_response,response_example,advantage,relative_features,require_mutation
from patrol_rsi.correction_selection import retain,adopt
import json


class CorrectionTests(unittest.TestCase):
    def test_keep_tour_without_positive_risk_gain(self):
        options=[{'order':[0,1],'original':True,'correction':{'gain_plus':0.,'gain_minus':0.,'delta_travel':0.,'delta_pressure':0.}},
            {'order':[1,0],'original':False,'correction':{'gain_plus':0.,'gain_minus':0.,'delta_travel':-2.,'delta_pressure':-.5}}]
        self.assertEqual(choose_advantage(options,Rule()).get('order'),[0,1])
        options[1]['correction']['gain_plus']=.2
        self.assertEqual(choose_advantage(options,Rule()).get('order'),[1,0])

    def test_contract_and_cost_direction(self):
        rule,_=parse_response(json.dumps(response_example()))
        with self.assertRaises(ValueError):require_mutation(rule,Rule())
        alternate=response_example();alternate['source_weights']={k:1.0 for k in alternate['source_weights']};alternate['margin']=0.0;alternate['mechanism']='Different words'
        same,_=parse_response(json.dumps(alternate));self.assertEqual(same.identity,Rule().identity)
        with self.assertRaises(ValueError):require_mutation(same,Rule())
        for invalid in (-.05,True,float('nan')):
            v=response_example();v['travel_penalty']=invalid
            with self.assertRaises(ValueError):parse_response(json.dumps(v))
        for value in ([response_example()],dict(response_example(),unknown=1)):
            with self.assertRaises(ValueError):parse_response(json.dumps(value))
        f={'gain_plus':.1,'gain_minus':.02,'delta_travel':0.,'delta_pressure':0.}
        base=advantage(f,rule)[1]
        self.assertAlmostEqual(base,.08)
        self.assertLess(advantage(dict(f,delta_travel=1.),rule)[1],base)
        self.assertLess(advantage(dict(f,delta_pressure=1.),rule)[1],base)

    def test_later_other_risk_task_cancels_gain_and_unknown_is_not_normal(self):
        original={'first_completion_s':{0:50.,1:100.},'segment_and_bridge_travel_s':20.}
        changed={'first_completion_s':{0:30.,1:140.},'segment_and_bridge_travel_s':20.}
        snapshot={j:{'weight':1.,'deadline_s':100.,'last_check_s':0.,'evidence_components':[
            {'group':'power','value':1.,'time_s':5.}]} for j in (0,1)}
        f=relative_features(original,changed,snapshot,[0,1],5.,Rule())
        self.assertAlmostEqual(f['gain_plus'],.1);self.assertAlmostEqual(f['gain_minus'],.2)
        self.assertLess(advantage(f,Rule())[0],0)
        for row in snapshot.values():row['evidence_components']=[{'group':'unknown','value':None,'time_s':None}]
        f=relative_features(original,changed,snapshot,[0,1],5.,Rule())
        self.assertEqual((f['gain_plus'],f['gain_minus']),(0.,0.))

    def test_small_wait_gain_cannot_buy_unbounded_travel(self):
        def result(wait,travel):
            return {'rows':[{'metrics':{'missed_segments':1,'consequence_weighted_censored_delay_s':wait,
                'travel_m':travel,'completed_inspections':100,'numeric_scoring_failures':0},'audit':{'passed':True}} for _ in range(6)]}
        parent=result(50.,100.);tradeoff=result(49.999,10000.);good=result(49.,99.)
        self.assertFalse(retain(parent,tradeoff,{'T':parent,'R':parent})[1]['accepted'])
        self.assertTrue(retain(parent,good,{'T':parent,'R':parent})[1]['accepted'])
        self.assertEqual(adopt(parent,{'H':tradeoff})['selected'],'T')


if __name__=='__main__':unittest.main()
