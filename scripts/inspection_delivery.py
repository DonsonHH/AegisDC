"""Frozen real-inspection engineering capture and saved-only delivery verification."""
import argparse
from hashlib import sha256
from html import escape
import json
from math import isclose
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/22-inspection-engineering-protocol.json'
PACKAGE='evidence/mainline/engineering/22-inspections'
def require(ok,message):
    if not ok:raise ValueError(message)
def read(p):return json.loads(p.read_bytes())
def digest(raw):return sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def write(p,value):
    raw=value if isinstance(value,bytes) else (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    with p.open('xb') as stream:stream.write(raw)
def hashes(revision,names):
    names=sorted(set(names))
    if not names:return {}
    raw=subprocess.check_output(
        ['git','cat-file','--batch'],cwd=ROOT,input=''.join(revision+':'+n+'\n' for n in names).encode())
    result={};offset=0
    for n in names:
        end=raw.index(b'\n',offset);header=raw[offset:end].split()
        require(len(header)==3 and header[1]==b'blob','Missing declared blob: '+n)
        start=end+1;size=int(header[2]);result[n]=digest(raw[start:start+size]);offset=start+size+1
    require(offset==len(raw),'Unexpected Git blob bytes');return result
def pins(protocol,revision):
    names=git('ls-tree','-rz','--name-only',revision,'src',PACKAGE+'/development',PACKAGE+'/reference').decode().strip('\0').split('\0')
    groups=dict(runtime=sorted(n for n in names if n.startswith('src/') and n.endswith('.py')),
        tools=[protocol['authoring_tool']],inputs=sorted(set([PROTOCOL,protocol['contract'],protocol['input'],
        protocol['reference_model'],protocol['reference_property'],PACKAGE+'/.gitattributes',
        *[n for n in names if n.startswith(PACKAGE) and '__pycache__' not in n and not n.endswith(('.pyc','.pyo'))]])))
    return {role:hashes(revision,paths) for role,paths in groups.items()}
def unchanged(revision,identities):
    return git('rev-parse','HEAD').decode().strip()==revision and all(
        digest((ROOT/n).read_bytes())==h for group in identities.values() for n,h in group.items())
def durable(folder):
    return {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}}

def snapshots(run,inputs,protocol):
    # This evaluator-only readback uses produced records, not future plant samples.
    from aegis_dc.evidence_ledger import EvidenceLedger, RECORD_FIELDS
    registry=inputs['inspection_program']['profile']['nonfixed_profile']['registry']
    ledger=EvidenceLedger(registry)
    for row in run['inspection_public_snapshot']['records']:
        ledger.ingest({k:row[k] for k in RECORD_FIELDS})
    return {name:ledger.snapshot(t) for name,t in protocol['snapshot_as_of_s'].items()}

def check_saved(folder,protocol):
    run=read(folder/'run.json');expected=protocol['expected'];tolerance=protocol['absolute_tolerance']
    task=run['work_records'][0];record=run['inspection_public_snapshot']['records'][0]
    actual={k:task[k] for k in ('arrived_at_s','work_started_at_s','completed_at_s')}
    actual.update(observed_at_s=record['observed_at_s'],arrived_record_at_s=record['arrived_at_s'])
    trace=[json.loads(line) for line in (folder/'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    actual['initial_flow_m3_s']=trace[0]['domains']['facility_cooling']['internal_pump']['volume_flow_m3_s']
    at_completion=[row for row in trace if row['time_s']==record['observed_at_s']]
    require(len(at_completion)==1,'Completion point must exist exactly once')
    actual['completion_flow_m3_s']=at_completion[0]['domains']['facility_cooling']['internal_pump']['volume_flow_m3_s']
    actual['physical_change_at_s']=run['inputs']['boundary_events'][0]['time_s']
    for key,value in expected.items():require(isclose(actual[key],value,abs_tol=tolerance,rel_tol=0),'Independent timing/signal witness differs: '+key)
    require(actual['work_started_at_s']<actual['physical_change_at_s']<actual['completed_at_s'],'Physical change must occur during professional work')
    require(task['status']=='completed' and record['value']==actual['completion_flow_m3_s']
        and actual['initial_flow_m3_s']!=record['value'],'Reading must use actual completion signal')
    feedback=run['inspection_public_feedback'][0]
    require(feedback['record_id']==record['id'] and feedback['additional_evidence_factor'] is False
        and feedback['provenance']==record['provenance'],'Confirmation must retain supporting observation identity')
    require(feedback['current_confirmation'] and feedback['confirmation']=='CONFIRMED_BELOW_THRESHOLD','Expected bounded signal confirmation')
    require(not run['inspection_public_models']['execution_permission'],'Inspection cannot authorize a physical repair')
    require(run['field_calibration']=='PENDING' and run['research_trials']==run['model_calls']==run['training_calls']==0,'Engineering scope changed')
    require(read(folder/'public-before-completion.json')['records']==[] and
        read(folder/'public-before-arrival.json')['records']==[] and
        len(read(folder/'public-at-arrival.json')['records'])==1,'Strict public arrival boundary differs')
    for n,item in run['artifacts'].items():require(digest((folder/n).read_bytes())==item['sha256'],'Original physical artifact differs: '+n)
    rebuilt=snapshots(run,read(ROOT/protocol['input']),protocol)
    for n,value in rebuilt.items():require(read(folder/n)==value,'Public snapshot readback differs')
    return dict(status='PASS',expected=expected,actual=actual,trace_points=len(trace),
        snapshot_record_counts={n:len(x['records']) for n,x in rebuilt.items()},
        scope='Actual typed crew completion and finite measurement law only; no repair or effect comparison')

def figures(run,checks):
    record=run['inspection_public_snapshot']['records'][0];identity=digest(json.dumps(checks,sort_keys=True).encode())
    def label(x,y,text,cls='b'):return f'<text x="{x}" y="{y}" class="{cls}">{escape(str(text))}</text>'
    pre=['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="460" viewBox="0 0 1120 460">',
        '<metadata>Checks SHA256 '+identity+'</metadata><rect width="1120" height="460" fill="#f7f9fc"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#162b42}.h{font-size:24px;font-weight:bold}.b{font-size:16px}.n{font-size:14px}</style>']
    time=pre.copy()+[label(30,40,'Actual inspection | visit, work, observation and arrival','h'),
        label(30,70,'One saved 3 s V6 engineering run; completion sampling changes information only.','n')]
    x=lambda t:230+t/3*800
    rows=[('Travel',115,0,1,'#287d57'),('Safe access check',165,1,1.25,'#b47a20'),
          ('Professional work',215,1.25,2.25,'#007b9c'),('Report latency',265,2.25,2.75,'#8448a4')]
    for name,y,a,b,color in rows:
        time += [label(30,y+22,name),f'<rect x="{x(a):.3f}" y="{y}" width="{x(b)-x(a):.3f}" height="30" fill="{color}"/>']
    for t in (0,1,1.25,1.75,2.25,2.75,3):
        time += [f'<line x1="{x(t):.3f}" y1="100" x2="{x(t):.3f}" y2="310" stroke="#c9d4e1"/>',label(x(t)-10,335,t,'n')]
    time += [label(30,380,'Flow changes at 1.75 s during work: 0.12 → 0 m³/s. Observation at 2.25 s reports 0.','n'),
        label(30,411,'No public record before 2.75 s. Confirmation is a bounded signal finding, not fault diagnosis.','n'),
        label(30,442,'Travel, gate, work, sampling and delivery have distinct times; no physical restoration is claimed.','n'),'</svg>']
    boundary=pre.copy()+[label(30,40,'Real completion → finite observation → arrived public record','h')]
    boxes=[(30,'Private actual executor',['Same eight-domain facility','Qualified worker + occupied tool','Arrival, work and completion','Existing local safety stops']),
        (400,'Private observation kernel',['Current whitelisted SI signal','Bounded / binary / unknown law','Keyed error, seed and audit private','One event per actual completion']),
        (770,'Public evidence and confirmation',['Declared coverage / quality / origin','Strict observed / arrived / expiry','Confirmation shares record origin','No extra independent factor'])]
    for left,title,lines in boxes:
        boundary += [f'<rect x="{left}" y="95" width="320" height="225" fill="white" stroke="#aabbce"/>',label(left+12,128,title)]
        boundary += [label(left+12,168+32*i,text,'n') for i,text in enumerate(lines)]
    boundary += ['<path d="M350 200H400M720 200H770" stroke="#007b9c" stroke-width="3"/>',
        label(30,365,'An expired confirmation remains historical. Missing or failed checks do not become successful readings.','n'),
        label(30,402,'Inspection changes information. Intervention and verified closure remain separate23/24 gates.','n'),'</svg>']
    return {'inspection-timing.svg':('\n'.join(time)+'\n').encode(),'inspection-boundary.svg':('\n'.join(boundary)+'\n').encode()}

def capture(folder,protocol):
    require(not git('status','--porcelain'),'Execution checkout must be clean')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set execution PYTHONPATH=src')
    source=git('rev-parse','HEAD').decode().strip();identities=pins(protocol,source);require(unchanged(source,identities),'Initial pinned source differs')
    folder.mkdir();write(folder/'attempt.json',dict(classification='ENGINEERING_ONLY',execution_commit=source,
        argv=sys.argv,executable=sys.executable,executable_sha256=digest(Path(sys.executable).read_bytes()),python=sys.version,
        declared_physical_runs=1,registered_research_trials=0,llm_calls=0,training_calls=0))
    receipt=dict(schema='aegisdc-real-inspection-receipt-v1',execution_commit=source,pinned=identities,
        global_regression_gate='PENDING_ROOT_INTEGRATED_FULL',field_calibration='PENDING')
    try:
        from aegis_dc.plant import simulate_scenario,describe_run
        inputs=read(ROOT/protocol['input'])
        result=simulate_scenario(inputs['model'],duration_s=protocol['duration_s'],step_s=protocol['maximum_step_s'],
            work_program=inputs['work_program'],inspection_program=inputs['inspection_program'],boundary_events=inputs['boundary_events'])
        run=describe_run(result);documents={'scenario.json':json.dumps(result['source_config'],ensure_ascii=False,indent=2,allow_nan=False)+'\n',
            'private-state.jsonl':''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in result['trace']),
            'balances.jsonl':''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in result['balances'])}
        run['artifacts']={n:dict(sha256=digest(raw.encode())) for n,raw in documents.items()}
        for n,raw in documents.items():write(folder/n,raw.encode())
        write(folder/'run.json',run)
        for n,value in snapshots(run,inputs,protocol).items():write(folder/n,value)
        checks=check_saved(folder,protocol);write(folder/'checks.json',checks)
        for n,raw in figures(run,checks).items():write(folder/n,raw)
        require(durable(folder)==set(protocol['durable_outputs']),'Capture differs from durable declaration');receipt['status']='PASS'
    except Exception as error:
        receipt.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=unchanged(source,identities)
        if not receipt['source_head_and_bytes_unchanged']:receipt['status']='FAIL'
        receipt['artifacts']={n:digest((folder/n).read_bytes()) for n in sorted(durable(folder))}
        write(folder/protocol['terminal_receipt'],receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Source changed during capture');return dict(status=receipt['status'],execution=source,artifacts=len(receipt['artifacts']))
def verify(folder,protocol,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),'Use clean requested delivery checkout')
    receipt=read(folder/protocol['terminal_receipt']);source=receipt['execution_commit']
    require(receipt['status']=='PASS' and receipt['source_head_and_bytes_unchanged'],'Original capture failed')
    require(set(receipt['artifacts'])==set(protocol['durable_outputs']) and durable(folder)==set(protocol['durable_outputs'])|{'receipt.json'},'Durable set differs')
    names=[(folder/n).relative_to(ROOT).as_posix() for n in durable(folder)];actual=hashes(delivery,names)
    for name,expected in actual.items():require(digest((ROOT/name).read_bytes())==expected,'Delivery artifact differs: '+name)
    for name,expected in receipt['artifacts'].items():require(digest((folder/name).read_bytes())==expected,'Original artifact differs')
    require(receipt['pinned']==pins(protocol,source),'Execution pin roles differ')
    for role,identities in receipt['pinned'].items():
        require(identities==hashes(delivery,identities) and all(digest((ROOT/n).read_bytes())==h for n,h in identities.items()),'Execution/delivery source differs: '+role)
    checks=check_saved(folder,protocol);require(checks==read(folder/'checks.json'),'Saved check differs')
    for n,raw in figures(read(folder/'run.json'),checks).items():require(raw==(folder/n).read_bytes(),'Saved figure differs')
    return dict(status='PASS',execution=source,delivery=delivery,artifacts=len(receipt['artifacts']),terminal_receipts=1,
        pins={k:len(v) for k,v in receipt['pinned'].items()},trace_points=checks['trace_points'],physical_rerun=False,
        inference_rerun=False,full_regression_rerun=False,runtime_caches_required=0,global_regression_gate='PENDING_ROOT_INTEGRATED_FULL')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['capture','verify'])
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--delivery');args=parser.parse_args()
    protocol=read(ROOT/PROTOCOL);folder=(ROOT/args.capture).resolve();require(folder.parent==ROOT/PACKAGE,'Use unique declared inspection directory')
    print(json.dumps(capture(folder,protocol) if args.mode=='capture' else verify(folder,protocol,args.delivery),ensure_ascii=False))
