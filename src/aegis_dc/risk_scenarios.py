"""Risk consequences from a public frame and a declared finite joint-outcome law."""
from copy import deepcopy
from fractions import Fraction
import argparse
import json
import math
from pathlib import Path

from patrol_rsi.contracts import strict_json

from .belief import infer_belief
from .decision_view import validate_current_frame, public_feasibility
from .evidence_ledger import _fields, _plain_json, _registry, _require, _strings, _text

CATALOG_FIELDS = {'schema','id','basis','source_note','facility_id','nominal_knowledge_id',
    'belief_model_id','horizon_s','time_unit','service_id','service_component_ids','demand',
    'outcomes','questions','unidentified'}
QUESTION_FIELDS = {'id','quantification','domain_ids','target_ids','scenario','barriers',
    'dependency_edge_ids','outcome_ids','window_s','evidence_gaps','closure_evidence','options',
    'impact_description','conditional_consequence','consequence_bounds','other_consequences',
    'immediate_service_effect'}
QUANTITIES = ('offered_service_unit_s','delivered_service_unit_s','unserved_service_unit_s','service_deficit_time_s')
OPTION_FIELDS = {'id','kind','request_id','operation_id','target_id','qualification_id',
                 'tool_ids','candidate_worker_ids','source_note','capability_interface_id'}


def _number(value, label, *, maximum=None):
    _require(type(value) in (int,float) and value >= 0
             and (maximum is None or value <= maximum), 'Declare finite nonnegative ' + label)
    return Fraction(value)


def _outward_upper(exact):
    try:
        upper = float(exact)
    except OverflowError as error:
        raise ValueError('Universal consequence bound exceeds finite binary64 output range') from error
    if math.isfinite(upper) and Fraction(upper) < exact:
        upper = math.nextafter(upper, math.inf)
    _require(math.isfinite(upper), 'Universal consequence bound exceeds finite binary64 output range')
    return Fraction(upper)


def _profile(rows, horizon, fields, label):
    _require(type(rows) is list and bool(rows), 'Declare a nonempty ' + label)
    end = Fraction(0)
    for row in rows:
        _fields(row, fields, label)
        start = _number(row['start_s'],label + ' start')
        stop = _number(row['end_s'],label + ' end')
        _require(start == end and start < stop <= horizon, label + ' must cover the horizon once without gaps or overlaps')
        end = stop
    _require(end == horizon, label + ' must cover the entire finite horizon')


def _catalog_for_frame(catalog, frame, belief_model):
    _plain_json(catalog)
    _fields(catalog,CATALOG_FIELDS,'Risk catalog')
    _require(catalog['schema']=='aegisdc-risk-catalog-v1' and catalog['basis']=='synthetic_assumption'
             and catalog['time_unit']=='s','Declare the finite synthetic risk catalog in SI seconds')
    for key in ('id','source_note'):
        _text(catalog[key],'Risk ' + key)
    knowledge = frame['nominal_knowledge']
    _require(catalog['facility_id']==frame['facility_id']
             and catalog['nominal_knowledge_id']==knowledge['id']
             and catalog['belief_model_id']==belief_model['id'],'Risk scope differs from public frame or belief model')
    entities = {row['id']:row for row in knowledge['entities']}
    service = catalog['service_id']
    components = catalog['service_component_ids']
    _require(service in entities and entities[service]['kind']=='service','Unknown nominal risk service')
    _strings(components,'service component')
    required = {edge['from'] for edge in knowledge['graphs']['functional']
                if edge['to']==service and edge['kind']=='requires' and entities[edge['from']]['domain']=='it_service'}
    _require(set(components)==required and bool(required),'Declare the required joint service component set')
    horizon = _number(catalog['horizon_s'],'risk horizon')
    _require(horizon>0,'Risk horizon must be positive')
    _profile(catalog['demand'],horizon,{'start_s','end_s','rate'},'Common exogenous demand')
    for row in catalog['demand']:
        _number(row['rate'],'offered service rate')
    states = {row['id'] for row in belief_model['hypotheses']}
    outcomes = _registry(catalog['outcomes'],'joint risk outcome')
    _require(bool(outcomes),'Declare a finite joint outcome law')
    totals = dict.fromkeys(states,Fraction(0))
    for row in outcomes.values():
        _fields(row,{'id','meaning','conditional_probability','capacity_profile'},'Risk outcome')
        _text(row['meaning'],'Risk outcome meaning')
        _fields(row['conditional_probability'],states,'Conditional outcome probabilities')
        for state,value in row['conditional_probability'].items():
            _number(value,'conditional probability',maximum=1)
            totals[state] += Fraction(str(value))
        _profile(row['capacity_profile'],horizon,{'start_s','end_s','capacities'},'Conditional capacity profile')
        for interval in row['capacity_profile']:
            _fields(interval['capacities'],set(components),'Conditional component capacities')
            for value in interval['capacities'].values():
                _number(value,'normalized service capacity')
    _require(all(total==1 for total in totals.values()),'Joint conditional outcome masses must sum to one for every belief state')
    questions = _registry(catalog['questions'],'risk question')
    edges = {row['id'] for rows in knowledge['graphs'].values() for row in rows}
    for row in questions.values():
        _fields(row,QUESTION_FIELDS,'Risk question')
        for key in ('scenario','barriers','closure_evidence','impact_description','conditional_consequence'):
            _text(row[key],'Risk question ' + key)
        _require(row['immediate_service_effect'] in {'INDIRECT_VIA_ACTION_FEASIBILITY',
            'ALTERNATIVE_PHYSICAL_AND_INFORMATION_EFFECTS','CONDITIONAL_CAPACITY_OR_PROTECTION_EFFECT'},
            'Declare the difference between physical service and execution feasibility impacts')
        for key in ('domain_ids','target_ids','evidence_gaps'):
            _strings(row[key],'Risk question ' + key)
        for key in ('dependency_edge_ids','outcome_ids'):
            _require(type(row[key]) is list, 'Risk question ' + key + ' must be a list')
            if row[key]:
                _strings(row[key],'Risk question ' + key)
        _require(bool(row['domain_ids']) and set(row['domain_ids'])<=set(knowledge['domain_ids'])
                 and bool(row['target_ids']) and set(row['target_ids'])<=set(entities)
                 and set(row['dependency_edge_ids'])<=edges and bool(row['evidence_gaps']), 'Unknown or incomplete public risk question bindings')
        window = row['window_s']
        _require(type(window) is list and len(window)==2,'Declare a two-endpoint question window')
        start,end = (_number(value,'question window') for value in window)
        _require(start<end<=horizon,'Question window must be within the declared horizon')
        bounds = row['consequence_bounds']
        _fields(bounds,{'service_deficit_time_s','unserved_service_unit_s','basis'},'Conditional consequence bounds')
        _text(bounds['basis'],'Conditional bound basis')
        for key,unit in (('service_deficit_time_s','s'),('unserved_service_unit_s','normalized_service_unit*s')):
            _fields(bounds[key],{'interval','unit'},'Conditional bound')
            _require(bounds[key]['unit']==unit and type(bounds[key]['interval']) is list
                     and len(bounds[key]['interval'])==2,'Declare conditional bound units')
            lower,upper = (_number(value,'conditional bound') for value in bounds[key]['interval'])
            _require(lower<=upper,'Conditional bound endpoints are reversed')
            offered = sum((min(end,Fraction(item['end_s']))-max(start,Fraction(item['start_s'])))*Fraction(item['rate'])
                for item in catalog['demand'] if max(start,Fraction(item['start_s']))<min(end,Fraction(item['end_s'])))
            universal_upper = end-start if key=='service_deficit_time_s' else offered
            _require(lower==0 and upper==_outward_upper(universal_upper),
                'Conservative bounds require zero and the minimal outward finite binary64 upper of the nonnegative-capacity limit')
        _require(type(row['other_consequences']) is list,'Other consequence dimensions must be separate records')
        for dimension in _registry(row['other_consequences'],'consequence dimension').values():
            _fields(dimension,{'id','description','unit','interval','basis'},'Other consequence dimension')
            for key in ('description','unit','basis'):
                _text(dimension[key],'Other consequence ' + key)
            _require(dimension['interval'] is None,'Unquantified secondary effects require an explicit missing interval')
        _require(row['quantification'] in {'FINITE_CONDITIONAL_LAW','UNMODELED'},'Unknown question quantification')
        _require((bool(row['outcome_ids']) and set(row['outcome_ids'])<=set(outcomes))
                 if row['quantification']=='FINITE_CONDITIONAL_LAW' else row['outcome_ids']==[],
                 'Finite questions require declared outcomes; unmodeled causes cannot receive zero-mass substitutes')
        _require(type(row['options']) is list,'Risk options must be a list')
        options = _registry(row['options'],'risk option')
        _require(bool(options),'Declare options for every open risk question')
        for option in options.values():
            _fields(option,OPTION_FIELDS,'Risk option')
            _text(option['source_note'],'Option basis')
            _require(option['kind'] in {'defer','inspect','intervene'},'Unknown risk option kind')
            if option['kind']=='defer':
                _require(all(option[key] is None for key in ('request_id','operation_id','target_id','qualification_id','capability_interface_id'))
                         and option['tool_ids']==option['candidate_worker_ids']==[],'Deferral has no equipment operation')
            elif option['kind']=='inspect':
                request = next((r for r in frame['requests'] if r['id']==option['request_id']),None)
                _require(request is not None and request['target_id'] in row['target_ids']
                         and all(option[key] is None for key in ('operation_id','target_id','qualification_id','capability_interface_id'))
                         and option['tool_ids']==option['candidate_worker_ids']==[],'Inspection must bind an existing public preparation request')
            else:
                _text(option['operation_id'],'Declared intervention operation')
                _require(option['request_id'] is None and option['target_id'] in row['target_ids']
                         and option['qualification_id'] in knowledge['qualification_ids'],'Intervention must bind a question target and declared qualification')
                for key in ('tool_ids','candidate_worker_ids'):
                    _strings(option[key],'Intervention ' + key)
                _require(all(key in entities and entities[key]['kind']=='tool' for key in option['tool_ids'])
                         and all(key in entities and entities[key]['kind']=='worker' for key in option['candidate_worker_ids']),
                         'Intervention capability must reference declared tools and personnel')
                interface = next((item for item in knowledge['work_interfaces'] if item['id']==option['capability_interface_id']),None)
                _require(interface is not None and option['target_id'] in interface['target_ids']
                         and option['qualification_id']==interface['qualification_id']
                         and set(option['tool_ids'])==set(interface['tool_ids']),
                         'Intervention referral must match an existing nominal target capability; operation authorization remains separate')
    _strings(catalog['unidentified'],'Unidentified risk item')
    _require(bool(catalog['unidentified']),'Declare remaining risk model gaps')
    return catalog


def _options(frame, question):
    entities = {row['id']:row for row in frame['nominal_knowledge']['entities']}
    assessments = []
    for option in question['options']:
        if option['kind']=='inspect':
            result = public_feasibility(frame,option['request_id'])
        elif option['kind']=='defer':
            result = dict(legal_for_planning=True,public_reasons=[],unresolved_dynamic_requirements=[])
        else:
            eligible, failures = [], set()
            for identifier in option['candidate_worker_ids']:
                worker = entities[identifier]
                reasons = []
                if option['qualification_id'] not in worker['qualification_ids']:
                    reasons.append('nominal_qualification_mismatch')
                if not set(option['tool_ids'])<=set(worker['tool_ids']):
                    reasons.append('nominal_tool_capability_mismatch')
                if not reasons:
                    eligible.append(identifier)
                failures.update(reasons)
            target = entities[option['target_id']]
            location = target['id'] if target['kind']=='location' else target['nominal_location_id']
            current = set(frame['evidence']['current_record_ids'])
            blocking = [record['id'] for record in frame['evidence']['records'] for constraint in frame['nominal_knowledge']['reported_constraints']
                if constraint['location_id']==location and record['id'] in current
                and all(record[key]==constraint[key] for key in ('source_id','target_id','observable_id'))
                and record['value'] is constraint['blocking_value']]
            reasons = ([] if eligible else sorted(failures)) + (['current_report_restricts_entry'] if blocking else [])
            result = dict(legal_for_planning=bool(eligible) and not blocking,public_reasons=reasons,
                nominal_candidate_worker_ids=eligible,blocking_record_ids=sorted(set(blocking)),
                unresolved_dynamic_requirements=['actual_access','current_worker_position','tool_availability',
                    'resource_occupation','route_and_timing','execution_authorization','operation_effect_contract'])
        assessment = dict(deepcopy(option),**result)
        assessment.update(execution_permission=False,
            requires_prior_inspection=False,physical_effect='NOT_EXECUTED',
            execution_gate='NONE_FOR_DEFER' if option['kind']=='defer' else 'REQUIRES_PERSONNEL_EXECUTOR_AND_OPERATION_CONTRACT')
        assessments.append(assessment)
    return assessments


def _service(outcome, demand, windows, components):
    offered = delivered = deficit = Fraction(0)
    for left, right in windows:
        for profile in outcome['capacity_profile']:
            for request in demand:
                start = max(left, Fraction(profile['start_s']), Fraction(request['start_s']))
                end = min(right, Fraction(profile['end_s']), Fraction(request['end_s']))
                if start >= end:
                    continue
                duration = end - start
                rate = Fraction(request['rate'])
                supply = min(rate, *(Fraction(profile['capacities'][key]) for key in components))
                offered += duration * rate
                delivered += duration * supply
                if rate:
                    deficit += duration * (rate - supply) / rate
    return dict(offered_service_unit_s=offered, delivered_service_unit_s=delivered,
                unserved_service_unit_s=offered-delivered, service_deficit_time_s=deficit)


def _union(windows):
    result = []
    for start, end in sorted(windows):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _consequences(outcomes, weights, demand, windows_by_outcome, components):
    totals = dict.fromkeys(QUANTITIES, Fraction(0))
    for outcome in outcomes:
        values = _service(outcome, demand, windows_by_outcome.get(outcome['id'], []), components)
        for key in totals:
            totals[key] += weights[outcome['id']] * values[key]
    return {key:dict(value=float(value),unit='s' if key=='service_deficit_time_s' else 'normalized_service_unit*s')
            for key,value in totals.items()}


def assess_risks(frame, belief_model, catalog):
    """Assess open questions without executing an inspection or physical action."""
    frame = validate_current_frame(frame)
    belief = infer_belief(frame, belief_model)
    catalog = _catalog_for_frame(catalog,frame,belief_model)
    posteriors = {key:({state:Fraction(str(value)) for state,value in row.items()} if row is not None else None)
                  for key,row in belief['posterior_by_variant'].items()}
    for key,row in posteriors.items():
        if row is not None:
            total = sum(row.values())
            posteriors[key] = {state:value/total for state,value in row.items()}
    weights_by_variant = {variant:({row['id']:sum(posterior[state]*Fraction(str(probability))
                            for state,probability in row['conditional_probability'].items())
               for row in catalog['outcomes']} if posterior is not None else None)
               for variant,posterior in posteriors.items()}
    weights = weights_by_variant[belief['reference_variant_id']]
    unresolved = belief['status'] in {'MODEL_CONFLICT','PARTIAL_MODEL_CONFLICT'}
    questions, portfolio_windows = [], {}
    for question in catalog['questions']:
        windows = [tuple(map(Fraction,question['window_s']))]
        variant_consequences = {variant:(_consequences(catalog['outcomes'],row,catalog['demand'],
            {key:windows for key in question['outcome_ids']},catalog['service_component_ids'])
            if row is not None and question['quantification']=='FINITE_CONDITIONAL_LAW' else None)
            for variant,row in weights_by_variant.items()}
        consequence = variant_consequences[belief['reference_variant_id']]
        if consequence is None:
            consequence = {key:dict(value=None,unit='s' if key=='service_deficit_time_s' else 'normalized_service_unit*s') for key in QUANTITIES}
        question_envelope = None if unresolved or question['quantification']=='UNMODELED' else {key:[
            min(row[key]['value'] for row in variant_consequences.values()),
            max(row[key]['value'] for row in variant_consequences.values())] for key in QUANTITIES}
        for key in question['outcome_ids']:
            portfolio_windows.setdefault(key, []).extend(windows)
        questions.append(dict(deepcopy(question),status='OPEN',
            window_s=[frame['as_of_s']+value for value in question['window_s']],
            probability=dict(value=None if question['quantification']=='UNMODELED' or weights is None else
                float(sum(weights[key] for key in question['outcome_ids'])),unit='1'),
            option_assessments=_options(frame,question),
            consequences_by_variant=variant_consequences,assumption_envelope=question_envelope,
            secondary_consequence_dimensions=deepcopy(question['other_consequences']),
            consequences_basis='EVENT_WEIGHTED_CONTRIBUTION_NOT_CONDITIONAL_ON_EVENT',
            consequences=consequence,physical_actions=[]))
    portfolio_windows = {key: _union(windows) for key, windows in portfolio_windows.items()}
    variants = {variant:(_consequences(catalog['outcomes'],row,catalog['demand'],
        portfolio_windows,catalog['service_component_ids']) if row is not None else None)
        for variant,row in weights_by_variant.items()}
    portfolio = variants[belief['reference_variant_id']]
    if portfolio is None:
        portfolio = {key:dict(value=None,unit='s' if key=='service_deficit_time_s' else 'normalized_service_unit*s') for key in QUANTITIES}
    envelope = None if unresolved else {key:[min(row[key]['value'] for row in variants.values()),
        max(row[key]['value'] for row in variants.values())] for key in QUANTITIES}
    full_service = (_consequences(catalog['outcomes'],weights,catalog['demand'],
        {key:[[Fraction(0),Fraction(catalog['horizon_s'])]] for key in weights},catalog['service_component_ids'])
        if weights is not None else {key:dict(value=None,unit=value['unit']) for key,value in portfolio.items()})
    return dict(schema='aegisdc-risk-result-v1',facility_id=frame['facility_id'],
        catalog_id=catalog['id'],catalog_basis=catalog['basis'],catalog_source_note=catalog['source_note'],
        unidentified=deepcopy(catalog['unidentified']),time_unit='s',
        domain_ids=frame['nominal_knowledge']['domain_ids'],as_of_s=frame['as_of_s'],
        status=belief['status'],covered_domain_ids=sorted({domain for row in questions for domain in row['domain_ids']}),
        full_horizon_service=full_service,envelope_basis='DECLARED_MODEL_VARIANT_RANGE_NOT_CONFIDENCE_INTERVAL',
        questions=questions,portfolio=dict(aggregation='JOINT_OUTCOME_AND_WINDOW_UNION',consequences=portfolio,
            completeness='PARTIAL_WITH_UNMODELED_QUESTIONS' if any(row['quantification']=='UNMODELED' for row in questions) else 'DECLARED_QUESTION_SET_ONLY',
            unmodeled_question_ids=[row['id'] for row in questions if row['quantification']=='UNMODELED'],
            consequences_by_variant=variants,assumption_envelope=envelope,
            outcome_windows_s={key:[[float(a),float(b)] for a,b in windows] for key,windows in portfolio_windows.items()}),
        belief=belief,physical_actions=[],execution_permission=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame',type=Path,required=True)
    parser.add_argument('--belief-model',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,required=True)
    args = parser.parse_args()
    try:
        values = [strict_json(path.read_text(encoding='utf-8')) for path in (args.frame,args.belief_model,args.catalog)]
        result = assess_risks(*values)
    except (OSError,ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
