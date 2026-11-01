import unittest
import numpy as np

from patrol_rsi.action_value_features import features,FEATURE_NAMES,task_vector
from patrol_rsi.action_value_execution import RootSampler


class FeatureTests(unittest.TestCase):
    def test_original_zero_and_state_conditioned_timing(self):
        rows={0:{'kind':'thermal','observed_value':70.,'direct_available':True,'direct_time_s':10.,'source':'qualified_temperature',
            'raw_cvae_temperature_c':60.,'raw_cvae_time_s':30.,'nominal_temperature_c':50.,'risk':1.,'weight':1.,'last_check_s':10.,'deadline_s':100.}}
        original={'first_completion_s':{0:80.},'segment_and_bridge_travel_s':10.}
        candidate={'first_completion_s':{0:60.},'segment_and_bridge_travel_s':10.}
        self.assertEqual(len(FEATURE_NAMES),36)
        self.assertTrue(np.array_equal(features(rows,original,original,40.),np.zeros(36)))
        value=features(rows,original,candidate,40.)
        self.assertAlmostEqual(value[0],.2)
        self.assertAlmostEqual(value[1],.2)
        self.assertAlmostEqual(value[2],.1)

    def test_future_is_rejected_and_root_types_are_not_risk_gates(self):
        row={'kind':'thermal','observed_value':70.,'direct_available':True,'direct_time_s':10.,'source':'qualified_temperature',
            'raw_cvae_temperature_c':60.,'raw_cvae_time_s':30.,'nominal_temperature_c':50.,'risk':1.,'weight':1.,'last_check_s':10.,'deadline_s':100.}
        for key in ('direct_time_s','raw_cvae_time_s'):
            with self.assertRaises(ValueError):task_vector(dict(row,**{key:41.}),40.)
        sampler=RootSampler()
        common={'legal_nonoriginal':2,'window':[0,1],'shadow_H':[0,1],'shadow_R':[1,0],'round_id':0}
        sampler.consider(dict(common,time_s=5.,agent=0,discrimination=.1),lambda:{'observed':1},[])
        sampler.consider(dict(common,time_s=10.,agent=0,discrimination=.5),lambda:{'observed':2},[])
        selected=sampler.selected()
        self.assertEqual([(v['root_type'],v['time_s']) for v in selected],[('A',5.),('B',10.)])

    def test_discrimination_uses_global_maximum_tolerance_band(self):
        sampler=RootSampler()
        for time_s,d in [(5.,1.),(10.,1.+.75e-9),(15.,1.+1.5e-9)]:
            sampler.consider({'legal_nonoriginal':1,'window':[0,1],'shadow_H':[0,1],'shadow_R':[0,1],
                'round_id':0,'time_s':time_s,'agent':0,'discrimination':d},lambda:{'observed':1},[])
        self.assertEqual(sampler.selected()[0]['time_s'],10.)

    def test_root_a_is_excluded_before_b_maximization(self):
        sampler=RootSampler()
        common={'legal_nonoriginal':1,'window':[0,1],'shadow_H':[0,1],'round_id':0,'agent':0}
        sampler.consider(dict(common,time_s=5.,shadow_R=[1,0],discrimination=10.),lambda:{'state':1},[])
        sampler.consider(dict(common,time_s=10.,shadow_R=[0,1],discrimination=1.),lambda:{'state':2},[])
        self.assertEqual([(v['root_type'],v['time_s']) for v in sampler.selected()],[('A',5.),('B',10.)])


class LearningTests(unittest.TestCase):
    def test_heldout_group_cannot_fit_scaler_and_ridge_has_known_solution(self):
        from patrol_rsi.action_value_learning import fit_fold,predict
        rows=[]
        for group in range(4):
            for root in range(2):
                for action in range(2):
                    x=[0.]*36;x[0]=float(action)*(1000000 if group==3 else 1)
                    rows.append({'group_id':group,'root_id':f'{group}-{root}','x':x,'y':[2.*action,None if group==0 else 2.*action,0.,2.*action]})
        model=fit_fold(rows,3)
        self.assertAlmostEqual(model['mean'][0],.5)
        self.assertAlmostEqual(model['scale'][0],.5)
        x=np.zeros((1,36));x[0,0]=1.
        p=predict(model,x)[0]
        self.assertAlmostEqual(p[0],4/3)
        self.assertAlmostEqual(p[1],4/3)
        self.assertEqual(p[2],0.)
        self.assertEqual(model['heads'][2]['status'],'constant_zero_no_variation')


class LabelTests(unittest.TestCase):
    def test_healthy_wait_null_and_lost_confirmation_remains_visible(self):
        from patrol_rsi.action_value_data import outcomes,event_pairs
        keys=('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s','completed_inspections','current_round_unfinished_obligations','unfinished_committed_tasks')
        healthy={'metrics':dict.fromkeys(keys,0)};healthy['metrics']['consequence_weighted_censored_delay_s']=None
        self.assertIsNone(outcomes(healthy,healthy)['y'][1]);self.assertFalse(outcomes(healthy,healthy)['wait_valid'])
        a={'anomaly_intervals':[{'task_id':'thermal:0','onset_s':100.,'end_s':200.,'first_confirmation_s':150.}]}
        b={'anomaly_intervals':[{'task_id':'thermal:0','onset_s':100.,'end_s':200.,'first_confirmation_s':None}]}
        self.assertEqual(event_pairs(a,b,120.)[0]['status'],'lost_confirmation')
        with self.assertRaises(ValueError):event_pairs(a,b,150.)


if __name__=='__main__':unittest.main()
