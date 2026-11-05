"""Finite ticket19 checks through the public risk interface; no physical runner."""
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json


def read(path):
    return json.loads(path.read_bytes())


def public_frames(frame, times):
    from aegis_dc.decision_view import DecisionGateway
    from aegis_dc.evidence_ledger import RECORD_FIELDS
    static = frame['evidence']['static_knowledge']
    records = [{key:row[key] for key in RECORD_FIELDS} for row in frame['evidence']['records']]
    ledger = dict(schema='aegisdc-evidence-ledger-v1',id=frame['evidence']['ledger_id'],
        facility_id=frame['facility_id'],basis='synthetic_assumption',time_unit='s',
        **static,records=records)
    plan = dict(schema='aegisdc-public-preparation-plan-v1',id='ticket19-public-engineering',
        basis='synthetic_assumption',time_unit='s',decision_times_s=times,requests=frame['requests'])
    gateway = DecisionGateway(frame['nominal_knowledge'],ledger,plan)
    return [gateway.next_frame() for _ in times]


def exercise(root, protocol):
    from aegis_dc.risk_scenarios import assess_risks
    frame,belief,catalog = [read(root/protocol[key]) for key in ('frame','belief_model','risk_catalog')]
    tolerance = protocol['absolute_numeric_tolerance']
    expected = read(root/protocol['expected_witness'])
    mapping = dict(offered='offered_service_unit_s',delivered='delivered_service_unit_s',
                   unserved='unserved_service_unit_s',deficit_time_s='service_deficit_time_s')
    results = [assess_risks(row,belief,catalog) for row in public_frames(frame,protocol['as_of_s'])]
    assert all(row['physical_actions']==[] and not row['execution_permission'] for row in results)
    actual = results[-1]['full_horizon_service']
    errors = {}
    for name,key in mapping.items():
        errors[key] = abs(actual[key]['value']-float(Fraction(expected['expected'][name])))
        assert errors[key] <= tolerance
    assert results[-1]['portfolio']['consequences']['service_deficit_time_s']['value'] < float(Fraction(expected['expected']['wrong_sum_component_deficit_s']))
    archive = read(root/protocol['window_witness'])
    window_checks=[]
    for name,case in archive['cases'].items():
        assert sha256((root/case['run_path']).read_bytes()).hexdigest()==case['run_sha256']
        rows = case['literal_intervals']
        local = deepcopy(catalog)
        local['demand']=[dict(start_s=float(Fraction(row[0])),end_s=float(Fraction(row[1])),rate=float(Fraction(row[2]))) for row in rows]
        local['outcomes']=[dict(id='known-joint',meaning='Independent archived08 literal capacity law',
            conditional_probability={state['id']:1 for state in belief['hypotheses']},
            capacity_profile=[dict(start_s=float(Fraction(row[0])),end_s=float(Fraction(row[1])),
                capacities={key:float(Fraction(value)) for key,value in zip(local['service_component_ids'],row[3:])}) for row in rows])]
        for window in case['windows']:
            question=deepcopy(local['questions'][0]);question.update(outcome_ids=['known-joint'],window_s=[float(Fraction(value)) for value in window['window_s']])
            left,right=map(Fraction,window['window_s'])
            offered=Fraction(window['offered'])
            question['consequence_bounds']['service_deficit_time_s']['interval']=[0,float(right-left)]
            question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,float(offered)]
            local['questions']=[question]
            result=assess_risks(frame,belief,local)['questions'][0]['consequences']
            for a,b in mapping.items():
                literal=window['normalized_deficit_s' if a=='deficit_time_s' else a]
                assert abs(result[b]['value']-float(Fraction(literal)))<=tolerance,(name,a)
            window_checks.append(dict(case=name,window_s=question['window_s'],expected={key:window['normalized_deficit_s' if key=='deficit_time_s' else key] for key in mapping},actual=result,source=case['run_path'],source_sha256=case['run_sha256']))
    # Explicit old FIFO/priority results are unrelated. This is finite joint-law arithmetic only.
    zero=deepcopy(catalog);zero['questions']=[]
    assert assess_risks(frame,belief,zero)['portfolio']['consequences']['service_deficit_time_s']['value']==0
    # Independently declared shared compound outcome: question addition is deliberately wrong.
    witness=read(root/protocol['joint_witness'])
    joint=deepcopy(catalog)
    joint['demand']=[dict(start_s=0,end_s=2,rate=1)]
    for outcome,capacity in zip(joint['outcomes'],(2,.6,.5,.3125)):
        outcome['capacity_profile']=[dict(start_s=0,end_s=2,capacities={key:capacity for key in joint['service_component_ids']})]
    joint['questions']=joint['questions'][:2]
    for question in joint['questions']:
        question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,2]
    empty=deepcopy(frame)
    empty['evidence']['records']=[]
    empty=public_frames(empty,[0])[0]
    joint_result=assess_risks(empty,belief,joint)
    for question in joint_result['questions']:
        assert abs(question['consequences']['service_deficit_time_s']['value']-float(Fraction(
            witness['expected_question_deficit_time_s'][question['id']])))<=tolerance
    assert abs(joint_result['portfolio']['consequences']['service_deficit_time_s']['value']-
               float(Fraction(witness['expected_joint_union_deficit_time_s'])))<=tolerance
    conflict=deepcopy(belief)
    for variant in conflict['variants']:variant['positive_likelihood']['fixed-hot']=[0,0,0,0]
    unresolved=assess_risks(frame,conflict,catalog)
    assert unresolved['portfolio']['consequences']['service_deficit_time_s']['value'] is None
    return dict(schema='aegisdc-risk-engineering-checks-v1',classification='ENGINEERING_ONLY',
        results=results,joint_witness_result=joint_result,expected_full_horizon=expected['expected'],absolute_errors=errors,
        maximum_absolute_error=max(errors.values()),window_checks=window_checks,
        registered_research_trials=0,new_physical_runs=0,llm_calls=0,training_calls=0),frame
