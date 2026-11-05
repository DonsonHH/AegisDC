"""Engineering checks of public finite value trees; no physical runner."""
from copy import deepcopy
from fractions import Fraction
import json

def read(path):return json.loads(path.read_bytes())

def exercise(root,protocol):
    from aegis_dc.action_value import assess_action_value
    frame,belief,catalog,model=[read(root/protocol[k]) for k in ('witness_frame','witness_belief','witness_catalog','witness_value')]
    witness=read(root/protocol['independent_witness']);results=[];errors=[]
    priors=[[.875,0,0,.125],[.5,.25,.125,.125],[.05,.9,.025,.025]]
    for prior,expected in zip(priors,witness['cases']):
        local=deepcopy(belief)
        for variant in local['variants']:variant['prior']=prior
        result=assess_action_value(frame,local,catalog,model);rows={r['kind']:r for r in result['question_values'][0]['alternatives']}
        names={'defer':'defer','direct_intervention':'direct_intervention','inspect_then_intervene_if_positive':'inspect_then_act'}
        for key,name in names.items():
            actual=rows[name]['expected']['service_deficit_time_s']['value'];error=abs(actual-float(Fraction(expected['expected_deficit_time_s'][key])));errors.append(error);assert error<=protocol['absolute_numeric_tolerance']
            actual=rows[name]['expected']['person_s']['value'];error=abs(actual-float(Fraction(expected['expected_worker_person_s'][key])));errors.append(error);assert error<=protocol['absolute_numeric_tolerance']
        assert abs(rows['inspect_then_act']['branches'][0]['probability']-float(Fraction(expected['positive_probability'])))<=protocol['absolute_numeric_tolerance']
        assert result['physical_actions']==[] and not result['execution_permission']
        results.append(dict(prior_fault=expected['prior_fault'],expected=expected,result=result))
    default=[read(root/protocol[k]) for k in ('frame','belief_model','risk_catalog','value_model')]
    standard=assess_action_value(*default)
    assert len(standard['unmodeled_questions'])==6 and all(r['value'] is None for r in standard['unmodeled_questions'])
    special=[]
    for case in ('unfinished-inspection','unfinished-action','resource-budget','unknown-availability','zero-support-report'):
        m=deepcopy(model)
        if case=='unfinished-inspection':m['question_models'][0]['inspection']['work_s']=120
        elif case=='unfinished-action':m['question_models'][0]['intervention']['work_s']=200
        elif case=='resource-budget':m['resource_budget']['person_s']=16
        elif case=='unknown-availability':m['availability'][0]['window_s']=None
        else:
            for v in m['question_models'][0]['variants']:v['positive_likelihood']={key:0 for key in v['positive_likelihood']}
        result=assess_action_value(frame,belief,catalog,m);rows={r['kind']:r for r in result['question_values'][0]['alternatives']}
        if case=='unfinished-inspection':assert rows['inspect_then_act']['branches'][0]['report']=='unavailable_within_horizon' and rows['inspect_then_act']['expected']['service_deficit_time_s']['value']==25
        elif case=='unfinished-action':assert rows['direct_intervention']['branches'][0]['action_completed_at_s'] is None and rows['direct_intervention']['expected']['service_deficit_time_s']['value']==100
        elif case=='resource-budget':assert not rows['direct_intervention']['eligible_for_planning'] and not rows['inspect_then_act']['eligible_for_planning']
        elif case=='unknown-availability':assert rows['direct_intervention']['eligible_for_planning'] is None
        else:assert rows['inspect_then_act']['branches'][0]['posterior_outcomes'] is None and rows['inspect_then_act']['expected']['service_deficit_time_s']['value']==25
        special.append(dict(case=case,result=result))
    return dict(schema='aegisdc-action-value-engineering-checks-v1',classification='ENGINEERING_ONLY',
        independent_cases=results,default_result=standard,boundary_cases=special,maximum_absolute_error=max(errors),
        new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0)
