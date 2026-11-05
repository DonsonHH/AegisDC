"""Frozen evidence-only closure capture and saved-only delivery verification."""
import argparse
import json
import os
from pathlib import Path
import sys
from html import escape
from inspection_delivery import git,hashes,require,read,digest,write,durable,unchanged
ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/24-closure-engineering-protocol.json'
PACKAGE='evidence/mainline/engineering/24-closure'

def pins(protocol,revision):
    names=git('ls-tree','-rz','--name-only',revision,'src','configs',PACKAGE+'/development',PACKAGE+'/reference',
        'evidence/mainline/engineering/23-interventions/capture-01','evidence/mainline/engineering/23-interventions/reference').decode().strip('\0').split('\0')
    groups=dict(runtime=[n for n in names if n.startswith('src/') and n.endswith('.py')],
        tools=[protocol['authoring_tool'],protocol['helper_tool'],protocol['input_preparation_tool']],
        inputs=[PROTOCOL,protocol['contract'],protocol['input_fixture'],
            *[n for n in names if n.startswith(PACKAGE+'/') or n.startswith('configs/full-facility')
              or n.startswith('evidence/mainline/engineering/23-interventions/')]])
    return {role:hashes(revision,paths) for role,paths in groups.items()}

def declared(protocol):
    return set(protocol['durable_root'])|{c['id']+'/'+n for c in protocol['cases'] for n in protocol['durable_case']}

def check_case(folder,case):
    result=read(folder/case['id']/'result.json');expected=case['expected']
    if expected['status']=='REJECTED':
        require(result['status']=='REJECTED' and result['error_type']=='ValueError'
            and expected['error_contains'] in result['error'],'Invalid declaration rejected for wrong reason: '+case['id'])
        return dict(status='PASS',assessment_status='REJECTED',expected=expected,actual=result)
    inputs=read(ROOT/case['input']);frame=inputs['frame'];question=result['questions'][0]
    for key,value in expected.items():require(question[key]==value,'Frozen '+case['id']+' '+key+' differs')
    require(result['facility_id']==frame['facility_id'] and result['as_of_s']==frame['as_of_s'],'Assessment identity differs')
    require(not result['execution_permission'] and result['physical_actions']==[] and not question['physical_restoration_claim'],'Closure cannot authorize physical restoration')
    visible={r['id']:r for r in frame['evidence']['records']}
    for identifier in question['supporting_record_ids']:
        row=visible[identifier];require(row['availability']=='current' and row['arrived_at_s']<=frame['as_of_s'],'Support must be currently available')
    for event in question['trace']:
        require(event['observed_at_s']<=event['arrived_at_s']<=frame['as_of_s'],'Trace contains future time')
        if 'record_id' in event:
            row=visible[event['record_id']]
            require(all(event[key]==row[key] for key in ('observed_at_s','arrived_at_s','valid_until_s','provenance')),'Trace changed evidence identity')
    if case['id']=='actual23-inspection-incomplete':
        row=visible['post-clean-flow'];require(row['observed_at_s']==5.25 and row['arrived_at_s']==5.75,'Original actual23measurement time differs')
        require(question['supporting_record_ids']==['post-clean-flow'] and not question['risk_closed'],'One actual reading cannot create missing service or persistence evidence')
    return dict(status='PASS',assessment_status=question['status'],expected=expected,supporting_record_ids=question['supporting_record_ids'],
        disposition_record_ids=question['disposition_record_ids'],trace_events=len(question['trace']),unevaluated_questions=len(result['unevaluated_question_ids']))

def check_saved(folder,protocol):
    return dict(status='PASS',cases={c['id']:check_case(folder,c) for c in protocol['cases']},assessment_calls=len(protocol['cases']),
        physical_runs=0,registered_research_trials=0,scope=protocol['scope'])

def figures(checks):
    def label(x,y,value,cls='n'):return f'<text x="{x}" y="{y}" class="{cls}">{escape(str(value))}</text>'
    def start(title):return ['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="800" viewBox="0 0 1300 800">',
        '<metadata>Checks SHA256 '+digest(json.dumps(checks,sort_keys=True).encode())+'</metadata>',
        '<rect width="1300" height="800" fill="#f4f7fb"/><style>text{font-family:Arial,sans-serif;fill:#20334d}.h{font-size:25px;font-weight:bold}.s{font-size:19px;font-weight:bold}.n{font-size:15px}.tiny{font-size:13px}</style>',label(30,40,title,'h')]
    life=start('Evidence-verified lifecycle | saved engineering assessments')
    life+=[label(30,70,'15 frozen evidence-only calls / zero physical reruns / no policy or field effectiveness claim'),label(30,109,'Case','s'),label(440,109,'Saved status','s'),label(1010,109,'Evidence records','s')]
    for index,(name,row) in enumerate(checks['cases'].items()):
        y=143+index*37
        life+=[f'<rect x="25" y="{y-23}" width="1250" height="33" fill="'+('#fff' if index%2==0 else '#eaf0f7')+'"/>',
            label(35,y,name),label(440,y,row['assessment_status']),label(1050,y,len(row.get('supporting_record_ids',[])))]
    life+=[label(30,730,'Actual23handheld record: sampled 5.25 s, arrived 5.75 s. One sample plus no service evidence leaves the question open.'),
        label(30,766,'Risk acceptance and false-alarm review close only the declared question; neither is a physical restoration finding.'),'</svg>']
    boundary=start('Question closure uses arrived evidence, not private plant truth')
    boxes=[(30,'Public inputs',['Validated current decision frame','Bound declared task / operation','Arrived task-local action report','Current evidence + provenance']),
        (465,'Finite criterion review',['Post-action condition + service','Genuine origins and time span','Current cross-source contradictions','Explicit review authority + dossier']),
        (900,'Question assessment',['Verified sampled criteria','Unconfirmed / symptom retreat','Escalated / risk accepted','False alarm explicitly reviewed'])]
    for left,title,lines in boxes:
        boundary+=[f'<rect x="{left}" y="130" width="370" height="245" rx="8" fill="white" stroke="#aabbce"/>',label(left+16,167,title,'s')]
        boundary +=[label(left+16,213+i*38,line) for i,line in enumerate(lines)]
    boundary+=['<path d="M400 250H465M835 250H900" stroke="#007b9c" stroke-width="3"/>',
        label(30,442,'No automatic closure from APPLIED feedback','s'),label(30,480,'A saved action report is checked against its declared named operation and authorization at the action time.'),
        label(30,538,'Missing, future, copied, ambiguous or contradictory current evidence cannot satisfy the full criterion.'),
        label(30,580,'Expired historical evidence stays preserved; new genuine current samples can support a renewed verification window.'),
        label(30,638,'Sampled criteria do not establish continuous recovery. Other facility questions remain explicitly unevaluated.'),
        label(30,730,'No plant trace or actual-state parameter is accepted. No training, LLM, policy or RSI conclusion.'),'</svg>']
    return {'closure-lifecycle.svg':('\n'.join(life)+'\n').encode(),'closure-boundary.svg':('\n'.join(boundary)+'\n').encode()}

def append(path,value):
    with path.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())

def capture(folder,protocol):
    require(not git('status','--porcelain'),'Use clean execution checkout')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set PYTHONPATH=src')
    source=git('rev-parse','HEAD').decode().strip();identities=pins(protocol,source);require(unchanged(source,identities),'Source pin differs')
    folder.mkdir(exist_ok=False)
    write(folder/'attempt.json',dict(classification=protocol['classification'],execution_commit=source,argv=sys.argv,executable=sys.executable,
        python=sys.version,executable_sha256=digest(Path(sys.executable).read_bytes()),declared_assessment_calls=protocol['declared_assessment_calls'],physical_runs=0))
    receipt=dict(schema='aegisdc-closure-engineering-receipt-v1',execution_commit=source,pinned=identities,
        assessment_attempts=0,completed=0,expected_rejections=0,failures=0,physical_runs=0,registered_research_trials=0,field_calibration='PENDING',global_regression_gate='PENDING_ROOT_INTEGRATED_FULL')
    try:
        from aegis_dc.verified_closure import assess_closure
        for case in protocol['cases']:
            require(unchanged(source,identities),'Source changed before case');inputs=read(ROOT/case['input'])
            receipt['assessment_attempts']+=1;append(folder/'attempts.jsonl',dict(case=case['id'],status='STARTED',execution_commit=source))
            try:
                try:result=assess_closure(inputs['frame'],inputs['program'])
                except ValueError as error:
                    if case['expected']['status']!='REJECTED':raise
                    result=dict(status='REJECTED',error_type='ValueError',error=str(error))
                    receipt['expected_rejections']+=1
                path=folder/case['id'];path.mkdir(exist_ok=False);write(path/'result.json',result)
                check_case(folder,case);receipt['completed']+=1
                append(folder/'attempts.jsonl',dict(case=case['id'],status='COMPLETED',execution_commit=source))
            except Exception as error:
                append(folder/'attempts.jsonl',dict(case=case['id'],status='FAILED',error_type=type(error).__name__,error=str(error)));raise
        checks=check_saved(folder,protocol);write(folder/'checks.json',checks)
        for name,raw in figures(checks).items():write(folder/name,raw)
        require(durable(folder)==declared(protocol),'Durable set differs');receipt['status']='PASS'
    except Exception as error:
        receipt.update(status='FAIL',failures=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=unchanged(source,identities)
        if not receipt['source_head_and_bytes_unchanged']:
            receipt.update(status='FAIL',failures=1);receipt.setdefault('error_type','SourceGuardError');receipt.setdefault('error','Source changed during capture')
        receipt['artifacts']={n:digest((folder/n).read_bytes()) for n in sorted(durable(folder))};write(folder/'receipt.json',receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Source changed during capture')
    return dict(status=receipt['status'],execution=source,assessment_calls=receipt['assessment_attempts'],expected_rejections=receipt['expected_rejections'],physical_runs=0,artifacts=len(receipt['artifacts']))

def verify(folder,protocol,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),'Use clean requested delivery checkout')
    receipt=read(folder/'receipt.json');source=receipt['execution_commit']
    require(receipt['status']=='PASS' and receipt['source_head_and_bytes_unchanged'] and receipt['failures']==0,'Original capture failed')
    require(receipt['assessment_attempts']==receipt['completed']==protocol['declared_assessment_calls'] and receipt['expected_rejections']==2 and receipt['physical_runs']==0,'Attempt totals differ')
    require(set(receipt['artifacts'])==declared(protocol) and durable(folder)==declared(protocol)|{'receipt.json'},'Durable declaration differs')
    for name,h in hashes(delivery,[(folder/n).relative_to(ROOT).as_posix() for n in durable(folder)]).items():require(digest((ROOT/name).read_bytes())==h,'Delivery blob differs')
    for name,h in receipt['artifacts'].items():require(digest((folder/name).read_bytes())==h,'Original artifact differs')
    require(receipt['pinned']==pins(protocol,source),'Source pin roles differ')
    for role,identities in receipt['pinned'].items():require(identities==hashes(delivery,identities) and all(digest((ROOT/n).read_bytes())==h for n,h in identities.items()),'Execution source differs: '+role)
    ledger=[json.loads(line) for line in (folder/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
    require(len(ledger)==2*len(protocol['cases']),'Ledger row count differs')
    for i,case in enumerate(protocol['cases']):
        pair=ledger[i*2:i*2+2];require([x['status'] for x in pair]==['STARTED','COMPLETED'] and all(x['case']==case['id'] and x['execution_commit']==source for x in pair),'Ledger order/source differs')
    checks=check_saved(folder,protocol);require(checks==read(folder/'checks.json'),'Saved checks differ')
    for name,raw in figures(checks).items():require(raw==(folder/name).read_bytes(),'Saved figure differs')
    return dict(status='PASS',execution=source,delivery=delivery,assessment_calls=receipt['assessment_attempts'],
        artifacts=len(receipt['artifacts']),pins={k:len(v) for k,v in receipt['pinned'].items()},physical_runs=0,assessment_rerun=False,
        full_regression_rerun=False,inference_rerun=False,runtime_caches_required=0)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['capture','verify']);parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--delivery');args=parser.parse_args();folder=(ROOT/args.capture).resolve()
    require(folder.parent==ROOT/PACKAGE,'Use unique declared closure output');protocol=read(ROOT/PROTOCOL)
    print(json.dumps(capture(folder,protocol) if args.mode=='capture' else verify(folder,protocol,args.delivery),ensure_ascii=False))
