"""Pure wire/provenance checks, not task-benefit simulations."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from propose_baseline_correction import parse_model_response,paired_feedback
from patrol_rsi.baseline_correction import Rule,require_mutation,response_example


class WireTests(unittest.TestCase):
    def test_numeric_spelling_cannot_create_a_model_edit(self):
        value=response_example();value['margin']=-0.0;value['source_weights']={k:1.0 for k in value['source_weights']};value['mechanism']='New wording only'
        rule,_=parse_model_response(json.dumps(value))
        self.assertEqual(rule.identity,Rule().identity)
        with self.assertRaises(ValueError):require_mutation(rule,Rule())

    def test_anonymous_pods_follow_profession_sorted_task_layout(self):
        tasks=[(128,'electrical'),(144,'cooling'),(129,'electrical')]
        rows=[{'task':j,'kind':kind,'risk':0.,'direct_age_s':None,'value_output_time_s':None,'evidence_components':[]} for j,kind in tasks]
        proof={'first_completion_s':{str(j):50. for j,_ in tasks},'remaining_before':[j for j,_ in tasks]}
        features=dict.fromkeys(('risk_delay','deadline_pressure','deadline_peak','travel_cost','freshness_delay'),0.)
        root={'public_tasks':rows,'agent':17,'round_id':0,'time_s':5.,'window':[128,144,129],'alternative_order':[144,128,129],
            'candidate_pool':[{'original':True,'order':[128,144,129],'certificate':proof,'features':features},
                {'original':False,'order':[144,128,129],'certificate':proof,'features':features}],
            'state_snapshot':{'spec':{'seed':'must_not_be_transferred'}}}
        keys=('missed_segments','consequence_weighted_censored_delay_s','travel_m','service_s','completed_inspections','current_round_unfinished_obligations','unfinished_committed_tasks','numeric_scoring_failures')
        record={'metrics':dict.fromkeys(keys,0)}
        feedback,_=paired_feedback({'pairs':[{'root':root,'A':record,'B':record,'category':'no_difference','prefix_verified':True}]})
        frame=next(iter(feedback['evidence_frames'].values()))
        self.assertEqual(frame[0][2],frame[1][2]);self.assertNotEqual(frame[0][2],frame[2][2])
        self.assertNotIn('must_not_be_transferred',json.dumps(feedback))


if __name__=='__main__':unittest.main()
