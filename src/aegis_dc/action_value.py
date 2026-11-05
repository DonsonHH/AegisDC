"""Finite evidence-only comparison of inspection and intervention alternatives."""
from copy import deepcopy
from fractions import Fraction
import argparse
import json
from pathlib import Path

from patrol_rsi.contracts import strict_json

from .risk_scenarios import assess_risks
from .evidence_ledger import _fields, _plain_json, _registry, _require, _text, _strings
from .risk_scenarios import _outward_upper

MODEL_FIELDS={'schema','id','basis','source_note','facility_id','nominal_knowledge_id',
    'risk_catalog_id','time_unit','cost_unit','availability_basis','resource_budget',
    'availability','question_models','unidentified'}
LOCAL_FIELDS={'id','question_id','inspection_option_id','intervention_option_id','inspector_id',
    'intervenor_id','inspection','intervention','action_on_positive','action_on_negative','variants'}
SERVICE=('offered_service_unit_s','delivered_service_unit_s','unserved_service_unit_s','service_deficit_time_s')
RESOURCE=('travel_person_s','wait_person_s','work_person_s','person_s','tool_s','cost')


def _number(value,label,maximum=None,positive=False):
    _require(type(value) in (int,float) and value>=0 and (maximum is None or value<=maximum),
             'Declare a finite nonnegative '+label)
    result=Fraction(value)
    _require(not positive or result>0,'Declare a positive '+label)
    _outward_upper(result)
    return result


def _validate(model,frame,catalog,risk):
    _plain_json(model);_fields(model,MODEL_FIELDS,'Action value model')
    _require(model['schema']=='aegisdc-action-value-model-v1' and model['basis']=='synthetic_assumption'
        and model['time_unit']=='s','Declare a synthetic action value model in SI seconds')
    for key in ('id','source_note','cost_unit','availability_basis'):_text(model[key],'Value model '+key)
    _require(model['facility_id']==frame['facility_id'] and model['nominal_knowledge_id']==frame['nominal_knowledge']['id']
        and model['risk_catalog_id']==catalog['id'],'Value model scope differs from public risk inputs')
    _strings(model['unidentified'],'Unidentified value assumption')
    _fields(model['resource_budget'],{'person_s','tool_s','cost'},'Decision resource budget')
    for value in model['resource_budget'].values():_number(value,'resource budget')
    entities={r['id']:r for r in frame['nominal_knowledge']['entities']}
    horizon=Fraction(catalog['horizon_s'])
    availability={}
    _require(type(model['availability']) is list,'Declare resource availability windows')
    for row in model['availability']:
        _fields(row,{'resource_id','window_s'},'Declared resource availability')
        key=row['resource_id']
        _require(key in entities and entities[key]['kind'] in {'worker','tool'} and key not in availability,
            'Unknown or repeated declared worker/tool availability')
        if row['window_s'] is not None:
            window=row['window_s'];_require(type(window) is list and len(window)==2,'Availability window requires two endpoints')
            start,end=(_number(x,'availability time') for x in window)
            _require(start<=end,'Availability window endpoints are reversed')
        availability[key]=row['window_s']
    questions={r['id']:r for r in risk['questions']};requests={r['id']:r for r in frame['requests']}
    interfaces={r['id']:r for r in frame['nominal_knowledge']['work_interfaces']}
    outcomes={r['id'] for r in catalog['outcomes']};components=set(catalog['service_component_ids'])
    seen=set()
    for local in _registry(model['question_models'],'question value model').values():
        _fields(local,LOCAL_FIELDS,'Question value model')
        _require(local['question_id'] in questions and local['question_id'] not in seen,'Unknown or repeated value question')
        seen.add(local['question_id']);q=questions[local['question_id']]
        _require(q['quantification']=='FINITE_CONDITIONAL_LAW','A value model cannot assign probabilities to an unmodeled risk question')
        options={r['id']:r for r in q['option_assessments']}
        _require(local['inspection_option_id'] in options and options[local['inspection_option_id']]['kind']=='inspect'
            and local['intervention_option_id'] in options and options[local['intervention_option_id']]['kind']=='intervene',
            'Value alternatives must bind this question inspection and intervention options')
        inspect=options[local['inspection_option_id']];action=options[local['intervention_option_id']]
        request=requests[inspect['request_id']];interface=interfaces[request['work_interface_id']]
        _require(local['inspector_id']==request['worker_id'] and local['intervenor_id'] in action['candidate_worker_ids'],
            'Value personnel must match the bound public capability options')
        selected=entities[local['intervenor_id']]
        _require(action['qualification_id'] in selected['qualification_ids'] and set(action['tool_ids'])<=set(selected['tool_ids']),
            'Selected intervention worker does not meet the nominal bound capability')
        resources={local['inspector_id'],local['intervenor_id'],*interface['tool_ids'],*action['tool_ids']}
        _require(resources<=set(availability),'Declare known or unknown availability for every used worker and tool')
        for stage_name in ('inspection','intervention'):
            stage=local[stage_name];fields={'travel_s','wait_s','work_s','cost'}
            if stage_name=='inspection':fields.add('report_latency_s')
            _fields(stage,fields,'Declared '+stage_name)
            for key,value in stage.items():_number(value,stage_name+' '+key,positive=key=='work_s')
            _outward_upper(sum(Fraction(stage[k]) for k in fields-{'cost'}))
        _outward_upper(sum(Fraction(local['inspection'][k]) for k in ('travel_s','wait_s','work_s','report_latency_s'))
                       +sum(Fraction(local['intervention'][k]) for k in ('travel_s','wait_s','work_s')))
        _outward_upper(Fraction(local['inspection']['cost'])+Fraction(local['intervention']['cost']))
        for key in ('action_on_positive','action_on_negative'):
            _require(local[key] in {'defer','intervene','minimum_service_deficit'},
                'A report branch must declare defer, intervene or a bounded service comparison')
        variants=_registry(local['variants'],'value model variant');_require(2<=len(variants)<=8,'Declare reference and sensitivity variants')
        for variant in variants.values():
            _fields(variant,{'id','basis','positive_likelihood','during_capacity','after_capacity'},'Value variant')
            _text(variant['basis'],'Value variant basis')
            _fields(variant['positive_likelihood'],outcomes,'Conditional prospective report likelihoods')
            for value in variant['positive_likelihood'].values():_number(value,'report probability',maximum=1)
            for key in ('during_capacity','after_capacity'):
                _fields(variant[key],outcomes,'Declared action capacity law')
                for capacity in variant[key].values():
                    _fields(capacity,components,'Action capacity components')
                    for value in capacity.values():_number(value,'action capacity')
    return availability


def _expected(catalog, weights, variant, action_start=None, action_end=None):
    totals=dict.fromkeys(('offered_service_unit_s','delivered_service_unit_s','unserved_service_unit_s','service_deficit_time_s'),Fraction(0))
    for outcome in catalog['outcomes']:
        cuts={Fraction(0),Fraction(catalog['horizon_s'])}
        for row in catalog['demand']+outcome['capacity_profile']:
            cuts.update((Fraction(row['start_s']),Fraction(row['end_s'])))
        for t in (action_start,action_end):
            if t is not None and 0<t<catalog['horizon_s']:cuts.add(t)
        points=sorted(cuts)
        for a,b in zip(points,points[1:]):
            demand=next(r for r in catalog['demand'] if Fraction(r['start_s'])<=a<Fraction(r['end_s']))
            baseline=next(r for r in outcome['capacity_profile'] if Fraction(r['start_s'])<=a<Fraction(r['end_s']))
            capacity=baseline['capacities']
            if action_start is not None and a>=action_start:
                capacity=variant['during_capacity' if a<action_end else 'after_capacity'][outcome['id']]
            rate=Fraction(demand['rate']);delivered=min(rate,*(Fraction(capacity[k]) for k in catalog['service_component_ids']))
            w=weights[outcome['id']]*(b-a)
            totals['offered_service_unit_s']+=w*rate
            totals['delivered_service_unit_s']+=w*delivered
            totals['unserved_service_unit_s']+=w*(rate-delivered)
            if rate:totals['service_deficit_time_s']+=w*(rate-delivered)/rate
    return totals


def _time(stage):
    return {key:Fraction(stage[key]) for key in ('travel_s','wait_s','work_s')}


def _occupation(stage,start,horizon,tools):
    result=dict(travel_person_s=Fraction(0),wait_person_s=Fraction(0),work_person_s=Fraction(0),tool_s=Fraction(0),cost=Fraction(0))
    at=start
    for key,time in _time(stage).items():
        duration=max(Fraction(0),min(horizon,at+time)-min(horizon,at))
        result[{'travel_s':'travel_person_s','wait_s':'wait_person_s','work_s':'work_person_s'}[key]]+=duration
        result['tool_s']+=duration*len(tools);at+=time
    result['person_s']=sum(result[k] for k in ('travel_person_s','wait_person_s','work_person_s'))
    result['cost']=Fraction(stage['cost']) if start<horizon else Fraction(0)
    return result


def _planning(model,availability,stages,costs,public_legal):
    reasons=[];unknown=False
    if not public_legal:reasons.append('public_option_not_eligible')
    for key,limit in model['resource_budget'].items():
        if costs[key]>Fraction(limit):reasons.append('branch_resource_budget_exceeded:'+key)
    for worker,tools,start,end in stages:
        for key in (worker,*tools):
            window=availability[key]
            if window is None:
                unknown=True;continue
            if start<Fraction(window[0]) or end>Fraction(window[1]):
                reasons.append('declared_resource_window_exceeded:'+key)
    if unknown:reasons.append('availability_unknown')
    return (False if any(r!='availability_unknown' for r in reasons) else None if unknown else True),sorted(set(reasons))


def _continuation_action(catalog,joint,variant,local,model,availability,inspection_tools,action_tools,
                         inspect_finish,report_at,horizon,action_legal):
    start=report_at+Fraction(local['intervention']['travel_s'])+Fraction(local['intervention']['wait_s'])
    end=start+Fraction(local['intervention']['work_s'])
    intervention=_expected(catalog,joint,variant,start,end)['service_deficit_time_s']
    no_action=_expected(catalog,joint,variant)['service_deficit_time_s']
    required=_occupation(local['inspection'],Fraction(0),inspect_finish,inspection_tools)
    full_end=report_at+sum(_time(local['intervention']).values())
    for key,value in _occupation(local['intervention'],report_at,full_end,action_tools).items():required[key]+=value
    for value in (*required.values(),full_end):_outward_upper(value)
    stages=[(local['inspector_id'],inspection_tools,Fraction(0),inspect_finish),
            (local['intervenor_id'],action_tools,report_at,full_end)]
    legal,_=_planning(model,availability,stages,required,action_legal)
    return legal is True and intervention<no_action


def _comparison(alternatives):
    eligible=[r for r in alternatives if r['eligible_for_planning'] is True]
    eligible=[r for r in eligible if r['expected']['service_deficit_time_s']['value'] is not None]
    key=lambda r:(r['expected']['service_deficit_time_s']['value'],r['expected']['person_s']['value'],r['kind'])
    without=[r for r in eligible if r['kind']!='inspect_then_act']
    baseline=min(without,key=key) if without else None
    inspected=next((r for r in eligible if r['kind']=='inspect_then_act'),None)
    return dict(best_eligible_without_inspection=baseline['kind'] if baseline else None,
        minimum_deficit_alternative=min(eligible,key=key)['kind'] if eligible else None,
        inspection_service_deficit_reduction_s=(baseline['expected']['service_deficit_time_s']['value']-inspected['expected']['service_deficit_time_s']['value']) if baseline and inspected else None,
        inspection_person_time_change_s=(inspected['expected']['person_s']['value']-baseline['expected']['person_s']['value']) if baseline and inspected else None,
        inspection_cost_change=(inspected['expected']['cost']['value']-baseline['expected']['cost']['value']) if baseline and inspected else None,
        rule='MINIMUM_EXPECTED_DEFICIT_WITH_SEPARATE_RESOURCE_BUDGETS_NOT_MIXED_UNIT_SCORE',
        scope='DECLARED_SINGLE_NEXT_DECISION_TREE_NOT_GLOBAL_POLICY_OR_VERIFIED_GAIN')


def assess_action_value(frame,belief_model,catalog,model):
    """Compare a finite single-question decision tree, without executing actions."""
    risk=assess_risks(frame,belief_model,catalog)
    availability=_validate(model,frame,catalog,risk)
    horizon=Fraction(catalog['horizon_s']);questions={q['id']:q for q in risk['questions']}
    requests={r['id']:r for r in frame['requests']};interfaces={r['id']:r for r in frame['nominal_knowledge']['work_interfaces']}
    values=[]
    for local in model['question_models']:
        q=questions[local['question_id']];options={r['id']:r for r in q['option_assessments']}
        inspect=options[local['inspection_option_id']];action=options[local['intervention_option_id']]
        inspection_tools=interfaces[requests[inspect['request_id']]['work_interface_id']]['tool_ids'];action_tools=action['tool_ids']
        records=[]
        for belief_variant,posterior in risk['belief']['posterior_by_variant'].items():
            for variant in local['variants']:
                if posterior is None:
                    records.append(dict(belief_variant_id=belief_variant,value_variant_id=variant['id'],alternatives=None))
                    continue
                mass=sum(Fraction(str(p)) for p in posterior.values())
                weights={o['id']:sum(Fraction(str(p))/mass*Fraction(str(o['conditional_probability'][s])) for s,p in posterior.items()) for o in catalog['outcomes']}
                it=local['inspection'];act=local['intervention']
                inspect_finish=sum(_time(it).values());report_at=inspect_finish+Fraction(it['report_latency_s'])
                alternatives=[]
                for kind in ('defer','direct_intervention','inspect_then_act'):
                    expected=dict.fromkeys((*SERVICE,*RESOURCE),Fraction(0));branches=[];eligibility=[];planning_reasons=[]
                    for positive in ((True,False) if kind=='inspect_then_act' and report_at<horizon else (None,)):
                        joint={key:p*(Fraction(str(variant['positive_likelihood'][key])) if positive else 1-Fraction(str(variant['positive_likelihood'][key]))) for key,p in weights.items()} if positive is not None else weights
                        probability=sum(joint.values());policy=local['action_on_positive' if positive else 'action_on_negative']
                        do_action=kind=='direct_intervention' or (kind=='inspect_then_act' and positive is not None and policy=='intervene')
                        if kind=='inspect_then_act' and positive is not None and probability and policy=='minimum_service_deficit':
                            do_action=_continuation_action(catalog,joint,variant,local,model,availability,inspection_tools,
                                action_tools,inspect_finish,report_at,horizon,action['legal_for_planning'])
                        start=report_at if kind=='inspect_then_act' else Fraction(0)
                        action_start=start+Fraction(act['travel_s'])+Fraction(act['wait_s']) if do_action else None
                        action_end=action_start+Fraction(act['work_s']) if do_action else None
                        service=_expected(catalog,joint,variant,action_start,action_end)
                        for key,v in service.items():expected[key]+=v
                        costs=dict.fromkeys(('travel_person_s','wait_person_s','work_person_s','person_s','tool_s','cost'),Fraction(0))
                        stages=[];required=dict.fromkeys(RESOURCE,Fraction(0))
                        if kind=='inspect_then_act':
                            for key,v in _occupation(it,Fraction(0),horizon,inspection_tools).items():costs[key]+=v
                            stages.append((local['inspector_id'],inspection_tools,Fraction(0),inspect_finish))
                            for key,v in _occupation(it,Fraction(0),inspect_finish,inspection_tools).items():required[key]+=v
                        if do_action:
                            for key,v in _occupation(act,start,horizon,action_tools).items():costs[key]+=v
                            if start<horizon:
                                full_end=start+sum(_time(act).values());_outward_upper(full_end)
                                stages.append((local['intervenor_id'],action_tools,start,full_end))
                                for key,v in _occupation(act,start,full_end,action_tools).items():required[key]+=v
                        legal=(kind=='defer' or (inspect['legal_for_planning'] if kind=='inspect_then_act' else True)
                               and (not do_action or action['legal_for_planning']))
                        permitted,reasons=_planning(model,availability,stages,required,legal)
                        for value in (*required.values(),*costs.values()):_outward_upper(value)
                        if probability:eligibility.append(permitted);planning_reasons.extend(reasons)
                        for key,v in costs.items():expected[key]+=probability*v
                        branches.append(dict(report=('unavailable_within_horizon' if kind=='inspect_then_act' and positive is None else None) if positive is None else ('positive' if positive else 'negative'),probability=float(probability),status='ZERO_SUPPORT_REPORT' if not probability else 'PREDICTED',action='intervene' if do_action else 'defer',posterior_outcomes={k:float(v/probability) for k,v in joint.items()} if probability else None,action_started_at_s=float(action_start) if action_start is not None and action_start<horizon else None,action_completed_at_s=float(action_end) if action_end is not None and action_end<=horizon else None,required_resources={k:float(v) for k,v in required.items()},action_status='NOT_SELECTED' if not do_action else 'NOT_STARTED_WITHIN_HORIZON' if action_start>=horizon else 'UNFINISHED_WITHIN_HORIZON' if action_end>horizon else 'COMPLETED_PREDICTED'))
                    for value in expected.values():_outward_upper(value)
                    alternatives.append(dict(kind=kind,expected={key:dict(value=float(v),unit=_unit(key,model)) for key,v in expected.items()},branches=branches,information_updates_physical_state=False,
                        eligible_for_planning=False if False in eligibility else None if None in eligibility else True,
                        planning_reasons=sorted(set(planning_reasons)),resource_gate='ALL_POSITIVE_SUPPORT_BRANCHES_WITHIN_SAME_DECLARED_BUDGET',execution_permission=False))
                records.append(dict(belief_variant_id=belief_variant,value_variant_id=variant['id'],alternatives=alternatives))
        reference=records[0]['alternatives']
        if reference is None:
            reference=[dict(kind=kind,expected={key:dict(value=None,unit=_unit(key,model)) for key in (*SERVICE,*RESOURCE)},
                branches=[],information_updates_physical_state=False,eligible_for_planning=None,
                planning_reasons=['reference_belief_model_conflict'],execution_permission=False)
                for kind in ('defer','direct_intervention','inspect_then_act')]
        envelope=None
        if all(row['alternatives'] is not None for row in records):
            envelope={kind:{key:[min(row['alternatives'][index]['expected'][key]['value'] for row in records),
                max(row['alternatives'][index]['expected'][key]['value'] for row in records)] for key in (*SERVICE,*RESOURCE)}
                for index,kind in enumerate(('defer','direct_intervention','inspect_then_act'))}
        values.append(dict(question_id=q['id'],alternatives=reference,alternatives_by_assumption=records,
            comparison=_comparison(reference),assumption_envelope=envelope,envelope_basis='DECLARED_BELIEF_AND_VALUE_VARIANT_RANGE_NOT_CONFIDENCE_INTERVAL'))
    return dict(schema='aegisdc-action-value-result-v1',status=risk['status'],question_values=values,
        unmodeled_questions=[dict(question_id=q['id'],value=None,reason='UNIDENTIFIED_PROBABILITY_AND_CONSEQUENCE',
            evidence_gaps=q['evidence_gaps'],impact_description=q['impact_description']) for q in risk['questions'] if q['quantification']=='UNMODELED'],
        scope='SINGLE_NEXT_QUESTION_ALTERNATIVES_NOT_ADDITIVE_GLOBAL_GAIN',field_calibration='PENDING',
        physical_actions=[],execution_permission=False,risk=risk)


def _unit(key,model):
    return ('s' if key=='service_deficit_time_s' else model['cost_unit'] if key=='cost' else
            'normalized_service_unit*s' if 'service_unit' in key else 'tool*s' if key=='tool_s' else 'person*s')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('frame','belief-model','catalog','value-model'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    try:
        inputs=[strict_json(path.read_text(encoding='utf-8')) for path in (args.frame,args.belief_model,args.catalog,args.value_model)]
        result=assess_action_value(*inputs)
    except (OSError,ValueError) as error:parser.error(str(error))
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()
