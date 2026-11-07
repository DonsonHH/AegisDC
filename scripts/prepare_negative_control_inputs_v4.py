"""Correct only the late public catalog identity; preserve all inputs and literals."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'evidence/mainline/engineering/28-negative-controls/reference-v3'
NEW=ROOT/'evidence/mainline/engineering/28-negative-controls/reference-v4'


def main():
    assert not NEW.exists()
    original=json.loads((OLD/'cases-v1.json').read_bytes())
    current=deepcopy(original)
    case=current['cases']['too_late']
    nominal=case['public_preparation']['nominal_knowledge']['id']
    assert case['closure_program']['risk_catalog']['nominal_knowledge_id']=='V6-27-lake-side-crew-engineering'
    assert case['closure_program']['belief_model']['scope']['nominal_knowledge_id']==nominal=='V6-28-negative-controls-engineering'
    case['closure_program']['risk_catalog']['nominal_knowledge_id']=nominal
    restored=deepcopy(current)
    restored['cases']['too_late']['closure_program']['risk_catalog']['nominal_knowledge_id']='V6-27-lake-side-crew-engineering'
    assert restored==original
    NEW.mkdir(parents=True)
    def write(path,value):
        with path.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    write(NEW/'cases-v1.json',current)
    (NEW/'literals-v1.json').write_bytes((OLD/'literals-v1.json').read_bytes())
    write(NEW/'preparation.json',dict(status='PREPARED_NOT_EXECUTED',
        authoring_tool_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        source_inputs={(OLD/name).relative_to(ROOT).as_posix():sha256((OLD/name).read_bytes()).hexdigest()
                       for name in ('cases-v1.json','literals-v1.json')},
        outputs={name:sha256((NEW/name).read_bytes()).hexdigest() for name in ('cases-v1.json','literals-v1.json')},
        durable_files=['cases-v1.json','literals-v1.json','preparation.json'],
        changed_field='cases.too_late.closure_program.risk_catalog.nominal_knowledge_id',
        physical_models_changed=False,literals_changed=False,new_project_calls=0))
    print(json.dumps(dict(status='PREPARED_NOT_EXECUTED',changed_public_identity_fields=1,new_physics=0)))


if __name__=='__main__':
    main()
