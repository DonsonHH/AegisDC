"""Public finite information/action value with independent literal expectations."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/name).read_bytes())

def fixture():
    frame=read('evidence/mainline/engineering/18-beliefs/capture-01/cli-frame.json')
    belief=read('configs/full-facility-belief-model-v1.json')
    catalog=read('configs/full-facility-risk-scenarios-v1.json')
    catalog['horizon_s']=100
    catalog['demand']=[dict(start_s=0,end_s=100,rate=1)]
    for outcome in catalog['outcomes']:
        capacity=0 if outcome['id']=='cooling-limited' else 1
        outcome['capacity_profile']=[dict(start_s=0,end_s=100,capacities={key:capacity for key in catalog['service_component_ids']})]
    for question in catalog['questions']:
        question['window_s']=[0,100]
        question['consequence_bounds']['service_deficit_time_s']['interval']=[0,100]
        question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,100]
    # Empty public evidence and an independent prior with P(cooling)=1/4.
    from aegis_dc.decision_view import DecisionGateway
    ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[])
    plan=dict(schema='aegisdc-public-preparation-plan-v1',id='action-value-witness',basis='synthetic_assumption',time_unit='s',decision_times_s=[0],requests=frame['requests'])
    frame=DecisionGateway(frame['nominal_knowledge'],ledger,plan).next_frame()
    for variant in belief['variants']:variant['prior']=[.5,.25,.125,.125]
    model=read('configs/full-facility-action-value-v1.json')
    model['question_models']=model['question_models'][:1]
    local=model['question_models'][0]
    local['inspection'].update(travel_s=0,wait_s=0,work_s=10,report_latency_s=0,cost=0)
    local['intervention'].update(travel_s=0,wait_s=0,work_s=20,cost=0)
    model['resource_budget'].update(person_s=1000,tool_s=1000,cost=1000)
    for resource in model['availability']:
        resource['window_s']=[0,100]
    for variant in local['variants']:
        for outcome in catalog['outcomes']:
            key=outcome['id'];variant['positive_likelihood'][key]=.8 if key=='cooling-limited' else .1
            variant['during_capacity'][key]={c:0 for c in catalog['service_component_ids']}
            variant['after_capacity'][key]={c:1 for c in catalog['service_component_ids']}
    return frame,belief,catalog,model

class ActionValueTests(unittest.TestCase):
    def test_information_requires_action_and_counts_delay_false_reports_and_person_time(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture();before=deepcopy((frame,belief,catalog,model))
        result=assess_action_value(frame,belief,catalog,model)
        rows={row['kind']:row for row in result['question_values'][0]['alternatives']}
        self.assertAlmostEqual(rows['defer']['expected']['service_deficit_time_s']['value'],25)
        self.assertAlmostEqual(rows['direct_intervention']['expected']['service_deficit_time_s']['value'],20)
        self.assertAlmostEqual(rows['inspect_then_act']['expected']['service_deficit_time_s']['value'],12.5)
        self.assertAlmostEqual(rows['inspect_then_act']['expected']['person_s']['value'],15.5)
        self.assertAlmostEqual(rows['inspect_then_act']['branches'][0]['probability'],11/40)
        self.assertEqual(rows['inspect_then_act']['information_updates_physical_state'],False)
        self.assertEqual(result['physical_actions'],[])
        self.assertEqual((frame,belief,catalog,model),before)

    def test_closed_public_model_and_action_bindings_refuse_private_or_unrelated_inputs(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        for name in ('private','wrong_scope','wrong_question','wrong_inspector','bad_probability','bad_capacity','negative_delay','unknown_resource'):
            local=deepcopy(model)
            if name=='private':local['actual_fault']='filter'
            elif name=='wrong_scope':local['risk_catalog_id']='other'
            elif name=='wrong_question':local['question_models'][0]['question_id']='people-and-tools'
            elif name=='wrong_inspector':local['question_models'][0]['inspector_id']='worker_it'
            elif name=='bad_probability':local['question_models'][0]['variants'][0]['positive_likelihood']['other']=2
            elif name=='bad_capacity':local['question_models'][0]['variants'][0]['after_capacity']['other']['actual_state']=1
            elif name=='negative_delay':local['question_models'][0]['inspection']['work_s']=-1
            else:local['availability'][0]['resource_id']='nonexistent-worker'
            with self.subTest(name=name),self.assertRaises(ValueError):assess_action_value(frame,belief,catalog,local)

    def test_same_declared_resources_restrict_only_candidates_without_reading_actual_occupation(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        model['resource_budget']['person_s']=16
        rows={r['kind']:r for r in assess_action_value(frame,belief,catalog,model)['question_values'][0]['alternatives']}
        self.assertFalse(rows['direct_intervention']['eligible_for_planning'])
        self.assertFalse(rows['inspect_then_act']['eligible_for_planning'])
        self.assertTrue(rows['defer']['eligible_for_planning'])
        model['resource_budget']['person_s']=1000
        model['availability'][0]['window_s']=None
        rows={r['kind']:r for r in assess_action_value(frame,belief,catalog,model)['question_values'][0]['alternatives']}
        self.assertIsNone(rows['direct_intervention']['eligible_for_planning'])
        self.assertIn('availability_unknown',rows['direct_intervention']['planning_reasons'])
        model['availability'][0]['window_s']=[0,10]
        rows={r['kind']:r for r in assess_action_value(frame,belief,catalog,model)['question_values'][0]['alternatives']}
        self.assertFalse(rows['direct_intervention']['eligible_for_planning'])
        self.assertTrue(all(not r['execution_permission'] for r in rows.values()))

    def test_conflicts_and_unmodeled_domains_remain_unknown_with_explicit_scope(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        result=assess_action_value(frame,belief,catalog,model)
        self.assertEqual(len(result['unmodeled_questions']),6)
        self.assertTrue(all(r['value'] is None for r in result['unmodeled_questions']))
        self.assertEqual(result['scope'],'SINGLE_NEXT_QUESTION_ALTERNATIVES_NOT_ADDITIVE_GLOBAL_GAIN')
        self.assertEqual(result['field_calibration'],'PENDING')
        frame,belief,catalog,model=fixture()
        # Move to accepted arrived report and make its likelihood impossible.
        frame=read('evidence/mainline/engineering/18-beliefs/capture-01/cli-frame.json')
        for variant in belief['variants']:variant['positive_likelihood']['fixed-hot']=[0,0,0,0]
        result=assess_action_value(frame,belief,catalog,model)
        self.assertEqual(result['status'],'MODEL_CONFLICT')
        self.assertIsNone(result['question_values'][0]['alternatives'][0]['expected']['service_deficit_time_s']['value'])
        self.assertIsNone(result['question_values'][0]['alternatives'][0]['eligible_for_planning'])

    def test_assumption_envelope_covers_belief_and_action_variants_and_conflict_withholds_it(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        model['question_models'][0]['variants'][1]['after_capacity']['cooling-limited']={k:0 for k in catalog['service_component_ids']}
        value=assess_action_value(frame,belief,catalog,model)['question_values'][0]
        rows=value['alternatives_by_assumption']
        self.assertEqual(len(rows),4)
        losses=[next(a for a in row['alternatives'] if a['kind']=='direct_intervention')['expected']['service_deficit_time_s']['value'] for row in rows]
        self.assertEqual(value['assumption_envelope']['direct_intervention']['service_deficit_time_s'],[min(losses),max(losses)])
        self.assertEqual(max(losses),40)
        # A valid reference remains shown when a sensitivity belief variant conflicts.
        frame=read('evidence/mainline/engineering/18-beliefs/capture-01/cli-frame.json')
        belief['variants'][1]['positive_likelihood']['fixed-hot']=[0,0,0,0]
        value=assess_action_value(frame,belief,catalog,model)['question_values'][0]
        self.assertIsNone(value['assumption_envelope'])
        self.assertIsNotNone(value['alternatives'][0]['expected']['service_deficit_time_s']['value'])

    def test_horizon_truncates_costs_but_never_invents_completed_inspection_or_repair(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        local=model['question_models'][0]
        local['inspection']['work_s']=120
        rows={r['kind']:r for r in assess_action_value(frame,belief,catalog,model)['question_values'][0]['alternatives']}
        self.assertEqual(rows['inspect_then_act']['expected']['service_deficit_time_s']['value'],25)
        self.assertEqual(rows['inspect_then_act']['expected']['person_s']['value'],100)
        self.assertEqual(rows['inspect_then_act']['branches'][0]['report'],'unavailable_within_horizon')
        self.assertEqual(rows['inspect_then_act']['branches'][0]['action'],'defer')
        local['inspection']['work_s']=10
        local['intervention']['work_s']=200
        rows={r['kind']:r for r in assess_action_value(frame,belief,catalog,model)['question_values'][0]['alternatives']}
        self.assertEqual(rows['direct_intervention']['expected']['service_deficit_time_s']['value'],100)
        self.assertIsNone(rows['direct_intervention']['branches'][0]['action_completed_at_s'])
        self.assertEqual(rows['direct_intervention']['branches'][0]['action_status'],'UNFINISHED_WITHIN_HORIZON')
        local['intervention'].update(travel_s=120,work_s=20)
        rows={r['kind']:r for r in assess_action_value(frame,belief,catalog,model)['question_values'][0]['alternatives']}
        self.assertEqual(rows['direct_intervention']['expected']['service_deficit_time_s']['value'],25)
        self.assertIsNone(rows['direct_intervention']['branches'][0]['action_started_at_s'])

    def test_zero_support_report_is_not_a_zero_risk_conditional_posterior(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        for variant in model['question_models'][0]['variants']:
            variant['positive_likelihood']={key:0 for key in variant['positive_likelihood']}
        rows={r['kind']:r for r in assess_action_value(frame,belief,catalog,model)['question_values'][0]['alternatives']}
        branch=rows['inspect_then_act']['branches'][0]
        self.assertEqual(branch['probability'],0)
        self.assertIsNone(branch['posterior_outcomes'])
        self.assertEqual(branch['status'],'ZERO_SUPPORT_REPORT')
        self.assertEqual(rows['inspect_then_act']['expected']['service_deficit_time_s']['value'],25)

    def test_information_value_is_a_separate_service_resource_comparison_not_a_mixed_score(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        value=assess_action_value(frame,belief,catalog,model)['question_values'][0]
        comparison=value['comparison']
        self.assertEqual(comparison['best_eligible_without_inspection'],'direct_intervention')
        self.assertEqual(comparison['inspection_service_deficit_reduction_s'],7.5)
        self.assertEqual(comparison['inspection_person_time_change_s'],-4.5)
        self.assertNotIn('weighted_score',comparison)
        for variant in model['question_models'][0]['variants']:variant['positive_likelihood']={key:0 for key in variant['positive_likelihood']}
        model['question_models'][0]['action_on_positive']='defer'
        value=assess_action_value(frame,belief,catalog,model)['question_values'][0]
        rows={r['kind']:r for r in value['alternatives']}
        self.assertEqual(rows['inspect_then_act']['expected']['service_deficit_time_s']['value'],25)
        self.assertEqual(rows['inspect_then_act']['expected']['person_s']['value'],10)
        self.assertLess(value['comparison']['inspection_service_deficit_reduction_s'],0)
        for prior,expected in (([.875,0,0,.125],'defer'),([.05,.9,.025,.025],'direct_intervention')):
            for variant in belief['variants']:variant['prior']=prior
            selected=assess_action_value(frame,belief,catalog,model)['question_values'][0]['comparison']['minimum_deficit_alternative']
            self.assertEqual(selected,expected)

    def test_unfinished_operation_cannot_hide_required_resources_or_selected_unqualified_worker(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        model['question_models'][0]['intervention']['work_s']=200
        model['resource_budget']['person_s']=110
        rows={r['kind']:r for r in assess_action_value(frame,belief,catalog,model)['question_values'][0]['alternatives']}
        self.assertFalse(rows['direct_intervention']['eligible_for_planning'])
        self.assertEqual(rows['direct_intervention']['branches'][0]['required_resources']['person_s'],200)
        frame,belief,catalog,model=fixture()
        catalog['questions'][0]['options'][1]['candidate_worker_ids']=['worker_cooling','worker_it']
        model['question_models'][0]['intervenor_id']='worker_it'
        with self.assertRaises(ValueError):assess_action_value(frame,belief,catalog,model)

    def test_finite_numeric_domain_and_cli_reject_without_traceback(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        local=model['question_models'][0]
        local['inspection']['report_latency_s']=1e308
        local['intervention']['travel_s']=1e308
        with self.assertRaisesRegex(ValueError,'finite binary64'):assess_action_value(frame,belief,catalog,model)
        frame,belief,catalog,model=fixture()
        model['question_models']=[]
        result=assess_action_value(frame,belief,catalog,model)
        self.assertEqual(result['question_values'],[])
        with tempfile.TemporaryDirectory() as directory:
            paths=[Path(directory)/(name+'.json') for name in ('frame','belief','catalog','value')]
            for p,v in zip(paths,(frame,belief,catalog,model)):p.write_text(json.dumps(v),encoding='utf-8')
            cmd=[sys.executable,'-B','-X','utf8','-m','aegis_dc.action_value','--frame',str(paths[0]),'--belief-model',str(paths[1]),'--catalog',str(paths[2]),'--value-model',str(paths[3])]
            called=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(called.returncode,0,called.stderr)
            self.assertEqual(json.loads(called.stdout),result)
            model['actual_state']='hidden'
            paths[3].write_text(json.dumps(model),encoding='utf-8')
            called=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(called.returncode,2)
            self.assertEqual(called.stdout,'')
            self.assertNotIn('Traceback',called.stderr)

    def test_independent_prior_extremes_zero_demand_and_current_public_restrictions(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        for prior,losses,choice in (([.875,0,0,.125],[0,20,2],'defer'),([.05,.9,.025,.025],[90,20,39.8],'direct_intervention')):
            for variant in belief['variants']:variant['prior']=prior
            value=assess_action_value(frame,belief,catalog,model)['question_values'][0]
            for row,expected in zip(value['alternatives'],losses):self.assertAlmostEqual(row['expected']['service_deficit_time_s']['value'],expected)
            self.assertEqual(value['comparison']['minimum_deficit_alternative'],choice)
        catalog['demand'][0]['rate']=0
        for question in catalog['questions']:question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,0]
        value=assess_action_value(frame,belief,catalog,model)['question_values'][0]
        self.assertTrue(all(row['expected']['service_deficit_time_s']['value']==0 for row in value['alternatives']))
        self.assertEqual(value['comparison']['minimum_deficit_alternative'],'defer')
        # Same public restriction mechanism as19; no private executor state is queried.
        frame,belief,catalog,model=fixture()
        constraint=frame['nominal_knowledge']['reported_constraints'][0]
        option=catalog['questions'][0]['options'][1]
        constraint['location_id']=next(e['nominal_location_id'] for e in frame['nominal_knowledge']['entities'] if e['id']==option['target_id'])
        from aegis_dc.decision_view import DecisionGateway
        row=dict(id='access-now',source_id=constraint['source_id'],target_id=constraint['target_id'],observable_id=constraint['observable_id'],unit='1',value=constraint['blocking_value'],observed_at_s=0,arrived_at_s=0,valid_until_s=1,quality=dict(status='reported',error_bound=None,note='Declared synthetic public restriction'),provenance=dict(origin_id='access-now',copied_from_record_id=None))
        ledger=dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],facility_id=frame['facility_id'],basis='synthetic_assumption',time_unit='s',**frame['evidence']['static_knowledge'],records=[row])
        plan=dict(schema='aegisdc-public-preparation-plan-v1',id='restriction-value',basis='synthetic_assumption',time_unit='s',decision_times_s=[0],requests=frame['requests'])
        frame=DecisionGateway(frame['nominal_knowledge'],ledger,plan).next_frame()
        value=assess_action_value(frame,belief,catalog,model)['question_values'][0]
        self.assertFalse(value['alternatives'][1]['eligible_for_planning'])
        self.assertFalse(value['alternatives'][2]['eligible_for_planning'])

    def test_optional_best_service_continuation_can_intervene_after_negative_when_prior_is_high(self):
        from aegis_dc.action_value import assess_action_value
        frame,belief,catalog,model=fixture()
        for variant in belief['variants']:variant['prior']=[.05,.9,.025,.025]
        model['question_models'][0]['action_on_positive']='minimum_service_deficit'
        model['question_models'][0]['action_on_negative']='minimum_service_deficit'
        value=assess_action_value(frame,belief,catalog,model)['question_values'][0]
        inspected=next(r for r in value['alternatives'] if r['kind']=='inspect_then_act')
        self.assertEqual([r['action'] for r in inspected['branches']],['intervene','intervene'])
        self.assertEqual(inspected['expected']['service_deficit_time_s']['value'],29)
        self.assertEqual(value['comparison']['minimum_deficit_alternative'],'direct_intervention')

if __name__=='__main__':unittest.main()
