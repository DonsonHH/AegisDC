"""Source-frozen workforce engineering capture and saved-delivery verification."""
import argparse
from hashlib import sha256
import json
from math import isclose
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/21-workforce-engineering-protocol.json'
PACKAGE='evidence/mainline/engineering/21-workforce'

def require(ok,message):
    if not ok:raise ValueError(message)

def read(path):return json.loads(path.read_bytes())
def digest(raw):return sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def write(path,value):
    with path.open('xb') as stream:
        stream.write(value if isinstance(value,bytes) else (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

def pins(protocol,revision):
    runtime=[n for n in git('ls-tree','-rz','--name-only',revision,'src').decode().strip('\0').split('\0') if n.endswith('.py')]
    inputs=[PROTOCOL,protocol['model'],protocol['program'],protocol['profile'],protocol['witness'],protocol['wait_annotation'],
        'docs/mainline/21-workforce-contract.md',PACKAGE+'/.gitattributes']
    inputs += [n for n in git('ls-tree','-rz','--name-only',revision,PACKAGE+'/reference',PACKAGE+'/development').decode().strip('\0').split('\0') if n]
    groups=dict(runtime=runtime,tools=protocol['authoring_tools'],inputs=sorted(set(inputs)))
    return {g:{n:digest(git('cat-file','blob',revision+':'+n)) for n in paths} for g,paths in groups.items()}

def unchanged(source,identities):
    return git('rev-parse','HEAD').decode().strip()==source and all(digest((ROOT/n).read_bytes())==h for rows in identities.values() for n,h in rows.items())

def figures(run):
    record=run['work_records'][0];summary=run['summary'];start=record['work_started_at_s'];end=record['completed_at_s']
    rows=['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="410" viewBox="0 0 1080 410">',
        '<style>text{font-family:Arial,sans-serif;fill:#162b42}.t{font-size:24px;font-weight:bold}.l{font-size:16px}.n{font-size:14px}</style>',
        '<rect width="1080" height="410" fill="#f7f9fc"/>',
        '<text x="30" y="38" class="t">Two-person crew | saved V6 engineering timeline</text>',
        '<text x="30" y="66" class="n">Positive access check1s | feedback latency2s | no repair or inspection measurement</text>']
    x=lambda t:235+t/95*780
    tracks=[('Cooling specialist',110,[(0,1,'#c48c3c'),(1,start,'#9dacc1'),(start,end,'#007b9c')]),
            ('Control specialist',180,[(0,60,'#287d57'),(60,start,'#c48c3c'),(start,end,'#007b9c')]),
            ('Flow-meter reservation',250,[(0,end,'#8f6bb1')])]
    for label,y,segments in tracks:
        rows.append(f'<text x="30" y="{y+20}" class="l">{label}</text>')
        for a,b,color in segments:rows.append(f'<rect x="{x(a):.3f}" y="{y}" width="{x(b)-x(a):.3f}" height="30" fill="{color}"/>')
    for t in (0,30,60,91,95):rows.append(f'<text x="{x(t):.3f}" y="308" class="n" text-anchor="middle">{t}</text>')
    rows += ['<text x="620" y="338" class="l" text-anchor="middle">Time(s)</text>',
        '<text x="30" y="368" class="n">Green walking | gold access check | grey rendezvous | blue work | purple tool reservation</text>',
        f'<text x="30" y="394" class="n">Travel{summary["worker_travel_person_s"]:.0f} + wait{summary["worker_wait_person_s"]:.0f} + work{summary["worker_work_person_s"]:.0f} =182person-s. Checks2 are within wait62.</text>','</svg>']
    architecture=['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="350" viewBox="0 0 1080 350">',
        '<style>text{font-family:Arial,sans-serif;fill:#162b42}.t{font-size:24px;font-weight:bold}.h{font-size:18px;font-weight:bold}.b{font-size:15px}</style>',
        '<rect width="1080" height="350" fill="#f7f9fc"/>',
        '<text x="30" y="40" class="t">Timed work intentions | public and private boundary</text>']
    boxes=[(30,300,'Current public preparation',['Current frame + static profile','Qualifications / tools / reports','One intention, no future program','Execution permission remains false']),
           (390,300,'Private plant and resources',['Queue / tool pickup / gate check','Crew rendezvous / timed work','Local protection uses actual state','Travel / wait / work stay separate']),
           (750,300,'Declared public feedback',['Task-local observed result','Available after declared latency','No early actual-resource query','No repair or measurement invented'])]
    for left,width,title,labels in boxes:
        architecture += [f'<rect x="{left}" y="90" width="{width}" height="180" fill="white" stroke="#aabbce"/>',f'<text x="{left+16}" y="120" class="h">{title}</text>']
        architecture += [f'<text x="{left+16}" y="{153+i*30}" class="b">{label}</text>' for i,label in enumerate(labels)]
    architecture += ['<path d="M330 180H390M690 180H750" stroke="#007b9c" stroke-width="3"/>',
        '<text x="30" y="312" class="b">Same eight-domain plant and four relation graphs. Private traces never become dispatcher input.</text>',
        '<text x="30" y="337" class="b">Engineering execution only; inspection observations, intervention and method comparisons remain later gates.</text>','</svg>']
    return {'crew-timing.svg':('\n'.join(rows)+'\n').encode(),'workforce-boundary.svg':('\n'.join(architecture)+'\n').encode()}

def saved_checks(directory,protocol):
    run=read(directory/'run.json');record=run['work_records'][0];summary=run['summary'];expected=protocol['expected'];tolerance=protocol['absolute_time_tolerance_s']
    values=dict(work_started_at_s=record['work_started_at_s'],completed_at_s=record['completed_at_s'],
        feedback_arrived_at_s=run['workforce_public_feedback'][0]['arrived_at_s'],**{k:summary[k] for k in expected if k in summary})
    for name,value in expected.items():require(isclose(values[name],value,rel_tol=0,abs_tol=tolerance),'Timing witness differs:'+name)
    require(record['status']=='completed' and record['effect']=='ENGINEERING_WORK_RECORD_ONLY_NO_REPAIR_OR_EVIDENCE','Unexpected task effect')
    require(run['field_calibration']=='PENDING' and run['research_trials']==run['model_calls']==run['training_calls']==0,'Scope changed')
    for name,entry in run['artifacts'].items():require(digest((directory/name).read_bytes())==entry['sha256'],'Saved physical artifact differs:'+name)
    count=0
    for line in (directory/'balances.jsonl').read_text().splitlines():
        row=json.loads(line);count+=1
        require(all(row[k]>=0 for k in ('worker_travel_person_s','worker_wait_person_s','worker_work_person_s')),'Negative occupation')
        require(isclose(row['worker_wait_person_s'],row['access_check_person_s']+row['rendezvous_wait_person_s']+row['queue_wait_person_s'],abs_tol=1e-12,rel_tol=0),'Waiting partition differs')
    return dict(status='PASS',expected=expected,actual=values,absolute_tolerance_s=tolerance,balance_rows=count,
        independent_witness=protocol['witness'],wait_annotation=protocol['wait_annotation'])

def capture(directory,protocol):
    require(not git('status','--porcelain'),'Capture checkout must be clean')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set explicit execution PYTHONPATH=src')
    source=git('rev-parse','HEAD').decode().strip();identities=pins(protocol,source);require(unchanged(source,identities),'Initial source bytes differ')
    require(not directory.exists(),'No capture overwrite');directory.mkdir()
    write(directory/'attempt.json',dict(classification='ENGINEERING_ONLY',execution_commit=source,argv=sys.argv,
        python=sys.version,executable=sys.executable,executable_sha256=digest(Path(sys.executable).read_bytes()),
        declared_physical_runs=1,registered_research_trials=0,llm_calls=0,training_calls=0))
    receipt=dict(schema='aegisdc-workforce-engineering-receipt-v1',execution_commit=source,pinned=identities,
        global_regression_gate='PENDING_ROOT_INTEGRATED_FULL',field_calibration='PENDING')
    try:
        from aegis_dc.plant import simulate_scenario,save_run
        from aegis_dc.scenario import load_scenario
        result=simulate_scenario(load_scenario(ROOT/protocol['model']),duration_s=protocol['duration_s'],
            step_s=protocol['maximum_step_s'],work_program=read(ROOT/protocol['program']))
        from aegis_dc.plant import describe_run
        run=describe_run(result)
        documents={'scenario.json':json.dumps(result['source_config'],ensure_ascii=False,indent=2,allow_nan=False)+'\n',
            'private-state.jsonl':''.join(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n' for row in result['trace']),
            'balances.jsonl':''.join(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n' for row in result['balances'])}
        counts={'scenario.json':1,'private-state.jsonl':len(result['trace']),'balances.jsonl':len(result['balances'])}
        run['artifacts']={n:dict(sha256=digest(raw.encode()),records=counts[n]) for n,raw in documents.items()}
        for name,data in documents.items():write(directory/name,data.encode())
        write(directory/'run.json',run)
        write(directory/'checks.json',saved_checks(directory,protocol))
        for name,data in figures(run).items():write(directory/name,data)
        require({p.name for p in directory.iterdir()}==set(protocol['durable_outputs']),'Declared capture set differs')
        receipt['status']='PASS'
    except Exception as error:
        receipt.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=unchanged(source,identities)
        if not receipt['source_head_and_bytes_unchanged']:receipt['status']='FAIL'
        receipt['artifacts']={p.name:digest(p.read_bytes()) for p in sorted(directory.iterdir()) if p.is_file()}
        write(directory/protocol['terminal_receipt'],receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Source changed during capture');return receipt

def verify(directory,protocol,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),'Use clean requested delivery checkout')
    receipt=read(directory/protocol['terminal_receipt']);require(receipt['status']=='PASS' and receipt['source_head_and_bytes_unchanged'],'Original capture failed')
    require(set(receipt['artifacts'])==set(protocol['durable_outputs']) and {p.name for p in directory.iterdir() if p.is_file()}==set(protocol['durable_outputs'])|{protocol['terminal_receipt']},'Durable set differs')
    for name,expected in receipt['artifacts'].items():
        path=(directory/name).relative_to(ROOT).as_posix();require(digest((directory/name).read_bytes())==expected==digest(git('cat-file','blob',delivery+':'+path)),'Original artifact differs:'+name)
    terminal=(directory/protocol['terminal_receipt']).relative_to(ROOT).as_posix()
    require(digest((ROOT/terminal).read_bytes())==digest(git('cat-file','blob',delivery+':'+terminal)),'Terminal receipt differs')
    require(receipt['pinned']==pins(protocol,receipt['execution_commit']),'Recorded pin set differs')
    for rows in receipt['pinned'].values():
        for name,expected in rows.items():require(digest((ROOT/name).read_bytes())==expected==digest(git('cat-file','blob',delivery+':'+name)),'Execution/delivery pin differs:'+name)
    checks=saved_checks(directory,protocol);require(checks==read(directory/'checks.json'),'Saved check summary differs')
    for name,data in figures(read(directory/'run.json')).items():require(data==(directory/name).read_bytes(),'Saved figure differs')
    return dict(schema='aegisdc-workforce-fresh-delivery-v1',status='PASS',execution_commit=receipt['execution_commit'],delivery_commit=delivery,
        durable_artifacts=len(receipt['artifacts']),terminal_receipts=1,pinned_paths={g:len(x) for g,x in receipt['pinned'].items()},
        balance_rows=checks['balance_rows'],physical_rerun=False,inference_rerun=False,full_regression_rerun=False,svg_figures=2,
        global_regression_gate=receipt['global_regression_gate'],field_calibration='PENDING',registered_research_trials=0,llm_calls=0,training_calls=0)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['capture','verify']);parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--delivery');args=parser.parse_args()
    protocol=read(ROOT/PROTOCOL);directory=(ROOT/args.capture).resolve();require(directory.parent==ROOT/PACKAGE,'Use unique ticket21 capture directory')
    result=capture(directory,protocol) if args.mode=='capture' else verify(directory,protocol,args.delivery)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))

if __name__=='__main__':main()
