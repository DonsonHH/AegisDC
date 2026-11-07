"""Remove evaluator labels from public report payloads while retaining the earlier inputs."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'evidence/mainline/engineering/28-negative-controls/reference-v4'
NEW=ROOT/'evidence/mainline/engineering/28-negative-controls/reference-v5'
OLD_REVIEW='false-alarm-review-28'
REVIEW='cooling-review-record-28'
SUSPICION='Operator reported possible low intake flow; a professional check is pending.'
RATIONALE='Review the reported low-flow suspicion using the listed flow and service observations.'


def neutralize(document):
    corrected=deepcopy(document)
    for name in ('normal','false_report'):
        program=corrected['cases'][name]['replay_inputs']['dispatch_program']
        dossier,=program['closure_program']['profile']['false_alarm_reviews']
        assert dossier['review_record_id']==OLD_REVIEW
        dossier.update(review_record_id=REVIEW,rationale=RATIONALE)
        for row in program['evidence_ledger']['records']:
            if row['id']=='delayed-lake-work-order':
                row['quality']['note']=SUSPICION
                row['provenance']['origin_id']='operator-lake-suspicion-28'
            elif row['id']==OLD_REVIEW:
                row['id']=REVIEW
    return corrected


def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    assert not NEW.exists()
    doc=json.loads((OLD/'cases-v1.json').read_bytes())
    fixed=neutralize(doc)
    NEW.mkdir(parents=True)
    write(NEW/'cases-v1.json',fixed)
    with (NEW/'literals-v1.json').open('xb') as stream:
        stream.write((OLD/'literals-v1.json').read_bytes())
    names=('cases-v1.json','literals-v1.json')
    write(NEW/'preparation.json',dict(status='PREPARED_NOT_EXECUTED',
        source_inputs={(OLD/name).relative_to(ROOT).as_posix():digest(OLD/name) for name in names},
        outputs={name:digest(NEW/name) for name in names},
        authoring_tool_sha256=digest(Path(__file__)),
        roles='Public work-order note and origin, shared conditional dossier ID and rationale, arrived review record ID.',
        physical_inputs_changed=False, timing_values_or_probability_laws_changed=False,
        literals_changed=False, new_project_calls=0))
    print(json.dumps(dict(status='PREPARED_NOT_EXECUTED',path=NEW.relative_to(ROOT).as_posix(),project_calls=0)))


if __name__=='__main__':
    main()
