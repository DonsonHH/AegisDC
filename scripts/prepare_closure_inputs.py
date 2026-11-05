"""Prepare explicit public closure inputs without running an assessment or plant."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
spec=importlib.util.spec_from_file_location('development_fixture',ROOT/'tests/test_verified_closure.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from aegis_dc.evidence_ledger import RECORD_FIELDS
def read(p):return json.loads(p.read_bytes())
def write(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def review(program,ledger,disposition):
    ledger['observables'].append(dict(id='cooling-review',quantity='category',value_type='text',unit='1'))
    ledger['sources'].append(dict(id='authorized-reviewer',kind='human_report',basis='synthetic_assumption',target_ids=['intake_pump'],
        observable_ids=['cooling-review'],dependency_group=None,source_note='Declared finite research review channel.'))
    ledger['records'].append(dict(id='review-disposition',source_id='authorized-reviewer',target_id='intake_pump',observable_id='cooling-review',unit='1',
        value=disposition,observed_at_s=5.5,arrived_at_s=5.75,valid_until_s=8,quality=dict(status='reported',error_bound=None,
        note='Finite synthetic management review, not field authority.'),provenance=dict(origin_id='review-origin',copied_from_record_id=None)))
    program['profile']['review_channels']=[dict(id='review-channel',question_id='cooling',source_id='authorized-reviewer',target_id='intake_pump',
        observable_id='cooling-review',authorization_id='risk-owner')]
    program['profile']['authorizations']=[dict(id='risk-owner',source_id='authorized-reviewer',question_ids=['cooling'],
        dispositions=['ACCEPT_RISK','ESCALATE','FALSE_ALARM'],starts_at_s=0,expires_at_s=8,basis='synthetic_assumption',source_note='Explicit finite synthetic research authority.')]
    if disposition=='FALSE_ALARM':program['profile']['false_alarm_reviews']=[dict(review_record_id='review-disposition',question_id='cooling',
        supporting_record_ids=['service-review-4','service-review-5','verify-flow-4','verify-flow-5'],
        rationale='Review of originating suspicion against declared received finite records, not inference from normality alone.')]
def main():
    folder=ROOT/'evidence/mainline/engineering/24-closure/reference';folder.mkdir(exist_ok=False);cases=[]
    definitions=[('verified','VERIFIED_CLOSED',6),('action-only','ACTION_COMPLETED_PENDING_VERIFICATION',3.5),
        ('condition-only','SYMPTOM_RETREATED_PENDING_VERIFICATION',6),('expired','ACTION_COMPLETED_PENDING_VERIFICATION',10),
        ('same-origin','ACTION_COMPLETED_PENDING_VERIFICATION',6),('cross-source-conflict','ACTION_COMPLETED_PENDING_VERIFICATION',6),
        ('risk-accepted','RISK_ACCEPTED',6),('risk-acceptance-expired','SYMPTOM_RETREATED_PENDING_VERIFICATION',8),
        ('escalated','ESCALATED',6),('false-alarm','FALSE_ALARM_REVIEWED',6),('false-alarm-adverse','OPEN_UNCONFIRMED',6),
        ('fresh-after-expiry','VERIFIED_CLOSED',6),('fabricated-operation','REJECTED',6),('expired-action-grant','REJECTED',6),
        ('actual23-inspection-incomplete','ACTION_COMPLETED_PENDING_VERIFICATION',6)]
    for name,status,time in definitions:
        frame,program,ledger,nominal=fixture.fixture()
        if name in {'condition-only','risk-accepted','risk-acceptance-expired','escalated'}:
            ledger['records']=[r for r in ledger['records'] if r['source_id']!='service-review']
        if name=='expired':pass
        if name=='same-origin':
            for r in ledger['records']:
                if r['source_id']=='verify-flow':r['provenance']['origin_id']='one-flow-origin'
        if name in {'cross-source-conflict','false-alarm-adverse'}:
            ledger['sources'].append(dict(id='fixed-adverse',kind='fixed_sensor',basis='synthetic_assumption',target_ids=['intake_pump'],
                observable_ids=['flow'],dependency_group=None,source_note='Separate sparse fixed measurement of the declared same signal.'))
            r=deepcopy(next(r for r in ledger['records'] if r['id']=='verify-flow-5'));r.update(id='fixed-adverse-5',source_id='fixed-adverse',value=.01)
            r['provenance']['origin_id']='fixed-adverse-origin';ledger['records'].append(r)
        if name in {'risk-accepted','risk-acceptance-expired'}:review(program,ledger,'ACCEPT_RISK')
        if name=='escalated':review(program,ledger,'ESCALATE')
        if name in {'false-alarm','false-alarm-adverse'}:
            program['intervention_feedback']=[];review(program,ledger,'FALSE_ALARM')
        if name=='fresh-after-expiry':
            r=deepcopy(ledger['records'][0]);r.update(id='old-expired',value=.01,observed_at_s=3.25,arrived_at_s=3.5,valid_until_s=3.75)
            r['provenance']['origin_id']='old-expired-origin';ledger['records'].append(r)
        if name=='fabricated-operation':
            program['profile']['rules'][0]['operation_id']='invented-repair';program['intervention_feedback'][0]['operation_id']='invented-repair'
        if name=='expired-action-grant':program['intervention_declaration']['profile']['authorizations'][0]['expires_at_s']=3
        if name=='actual23-inspection-incomplete':
            original=read(ROOT/'evidence/mainline/engineering/23-interventions/capture-01/filter-later-inspection/run.json')
            inputs=read(ROOT/'evidence/mainline/engineering/23-interventions/reference/filter-later-inspection.json')
            actual=original['inspection_public_snapshot']['records'][0]
            source=next(s for s in inputs['inspection_program']['profile']['nonfixed_profile']['registry']['sources'] if s['id']==actual['source_id'])
            ledger['sources'].append(source);ledger['records']=[{k:actual[k] for k in RECORD_FIELDS}]
            program['intervention_declaration']=inputs['intervention_program']
            program['intervention_feedback']=original['intervention_public_feedback']
            rule=program['profile']['rules'][0];rule.update(task_id='restore-network',operation_id='network-restore')
            rule['checks'][0]['source_ids']=[actual['source_id']];rule['checks'][0]['accepted_interval']=[.07,.08]
        frame=fixture.reframe(ledger,nominal,time)
        path=folder/(name+'.json');write(path,dict(frame=frame,program=program))
        expected=dict(status=status,question_closed=status in {'VERIFIED_CLOSED','RISK_ACCEPTED','FALSE_ALARM_REVIEWED'},risk_closed=status=='VERIFIED_CLOSED')
        if status=='REJECTED':expected=dict(status='REJECTED',error_contains=
            'Closure action must bind a declared named task operation' if name=='fabricated-operation' else
            'Applied action report contradicts its declared authorization interval')
        cases.append(dict(id=name,input=path.relative_to(ROOT).as_posix(),expected=expected))
    protocol=dict(schema='aegisdc-closure-engineering-protocol-v1',ticket='24',classification='ENGINEERING_ONLY_EVIDENCE_CONSUMER',
        cases=cases,declared_assessment_calls=15,physical_runs=0,llm_calls=0,training_calls=0,registered_research_trials=0,
        authoring_tool='scripts/closure_delivery.py',helper_tool='scripts/inspection_delivery.py',input_preparation_tool='scripts/prepare_closure_inputs.py',
        input_fixture='tests/test_verified_closure.py',contract='docs/mainline/24-closure-contract.md',
        retry_rule='One assessment per frozen case. Start ledger before call; check saved output before next case. Preserve failure and stop. No automatic retries.',
        rejection_rule='Expected invalid declarations must raise ValueError with the specified semantic reason, not a fixture registry/import error.',
        durable_root=['attempt.json','attempts.jsonl','checks.json','closure-lifecycle.svg','closure-boundary.svg'],
        durable_case=['result.json'],terminal_receipt='receipt.json',full_regression='ROOT_INTEGRATED_ONLY',field_calibration='PENDING',
        scope='Finite synthetic sampled evidence criteria and dispositions, no physical repair, continuous restoration, policy gain or field result. Actual23case reuses original actual handheld record without recapture.')
    write(ROOT/'docs/mainline/24-closure-engineering-protocol.json',protocol)
    print(json.dumps(dict(prepared_inputs=len(cases),assessment_calls=0,physical_runs=0)))
if __name__=='__main__':main()
