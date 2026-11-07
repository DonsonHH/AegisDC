"""Correct public risk bounds and missing static request bindings from fixed input laws."""
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'evidence/mainline/engineering/28-negative-controls/reference-v2'
NEW = ROOT / 'evidence/mainline/engineering/28-negative-controls/reference-v3'


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    assert not NEW.exists()
    document = deepcopy(read(OLD/'cases-v1.json'))
    changed=[]
    for case_name in ('normal','false_report'):
        program=document['cases'][case_name]['replay_inputs']['dispatch_program']
        catalogs={'policy':program['policy_program']['options']['catalog'],
                  'closure':program['closure_program']['risk_catalog']}
        for role,catalog in catalogs.items():
            assert catalog['demand']==[dict(start_s=0,end_s=6,rate=.5)]
            for question in catalog['questions']:
                start,end=map(Fraction,question['window_s'])
                offered=sum((min(end,Fraction(item['end_s']))-max(start,Fraction(item['start_s'])))*Fraction(item['rate'])
                    for item in catalog['demand'] if max(start,Fraction(item['start_s'])) < min(end,Fraction(item['end_s'])))
                assert offered==3 and end-start==6
                bounds=question['consequence_bounds']
                assert bounds['unserved_service_unit_s']['interval']==[0,6]
                assert bounds['service_deficit_time_s']['interval']==[0,6]
                bounds['unserved_service_unit_s']['interval']=[0,3]
                changed.append(f'{case_name}.{role}.{question["id"]}.unserved_service_unit_s.interval')
    normal=document['cases']['normal']['replay_inputs']['dispatch_program']
    late=document['cases']['too_late']['public_preparation']
    required={'intent-filter-check','intent-it-check'}
    late['requests']=[deepcopy(row) for row in normal['preparation_requests'] if row['id'] in required]
    task=late['task']
    late['requests'].append(dict(id='network-check-request-28',target_id=task['target_id'],
        work_interface_id=task['work_interface_id'],worker_id=task['tool_carrier_id']))
    assert {r['id'] for r in late['requests']}==required|{'network-check-request-28'}
    assert len(changed)==32
    for name,case in document['cases'].items():
        old=read(OLD/'cases-v1.json')['cases'][name]
        assert case['model']==old['model'] and case['duration_s']==old['duration_s'] and case['maximum_step_s']==old['maximum_step_s']
    assert document['cases']['too_late']['intervention_program']==read(OLD/'cases-v1.json')['cases']['too_late']['intervention_program']
    NEW.mkdir(parents=True)
    write(NEW/'cases-v1.json',document)
    (NEW/'literals-v1.json').write_bytes((OLD/'literals-v1.json').read_bytes())
    write(NEW/'preparation.json',dict(status='PREPARED_NOT_EXECUTED',
        authoring_tool_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        source_inputs={(OLD/name).relative_to(ROOT).as_posix():sha256((OLD/name).read_bytes()).hexdigest()
            for name in ('cases-v1.json','literals-v1.json')},
        outputs={name:sha256((NEW/name).read_bytes()).hexdigest() for name in ('cases-v1.json','literals-v1.json')},
        durable_files=['cases-v1.json','literals-v1.json','preparation.json'],
        changed_public_fields=changed,added_static_request_ids=sorted(required),
        actual_network_submissions=1,physical_model_changed=False,literals_changed=False,
        basis='Exact offered amount 0.5*6=3 and the existing full-catalog request binding contract. No physical trajectory returned by the failed attempt; no outcome-based selection.',
        new_project_calls=0,new_physics=0,new_selectors=0))
    print(json.dumps(dict(status='PREPARED_NOT_EXECUTED',changed_bound_fields=len(changed),
        added_static_request_ids=sorted(required),physical_models_changed=False,literals_changed=False,new_physics=0)))


if __name__=='__main__':
    main()
