"""One declared small physical correction witness; verify mode reads saved evidence only."""
import argparse
from hashlib import sha256
import json
from math import isclose
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/21-safety-closure-protocol.json'
FOLDER='evidence/mainline/engineering/21-workforce/safety-closure-01'
def read(p):return json.loads(p.read_bytes())
def h(raw):return sha256(raw).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
def write(p,v):
    with p.open('xb') as f:f.write(v if isinstance(v,bytes) else (json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def identities(source,protocol):
    names=[n for n in git('ls-tree','-rz','--name-only',source,'src').decode().strip('\0').split('\0') if n.endswith('.py')]
    names += [PROTOCOL,protocol['input'],'scripts/workforce_safety_closure.py','docs/mainline/21-workforce-contract.md']
    return {n:h(git('cat-file','blob',source+':'+n)) for n in names}
def check(folder,protocol):
    r=read(folder/'run.json');record=r['work_records'][0];feedback=r['workforce_public_feedback'];summary=r['summary']
    actual=dict(cancel_requested_at_s=record['cancel_requested_at_s'],finished_at_s=record['finished_at_s'],
        hazard_available_at_s=feedback[0]['arrived_at_s'],terminal_available_at_s=feedback[1]['arrived_at_s'],
        worker_travel_person_s=summary['worker_travel_person_s'],tool_occupation_tool_s=summary['tool_occupation_tool_s'])
    for key,value in protocol['expected'].items():require(isclose(actual[key],value,rel_tol=0,abs_tol=1e-10),'Correction witness differs:'+key)
    require(record['status']=='aborted' and feedback[0]['status']=='safety_stop_observed','Safety lifecycle differs')
    for name,item in r['artifacts'].items():require(h((folder/name).read_bytes())==item['sha256'],'Saved physical output differs:'+name)
    at_one=[]
    for line in (folder/'private-state.jsonl').read_text().splitlines():
        row=json.loads(line)
        if row['time_s']==1:at_one.append(row['domains']['people_tools_work'])
    require(len(at_one)==1 and at_one[0]['workers']['worker_cooling']['location_id'] is None
            and at_one[0]['tools']['tool_flow_meter']['reserved_by']=='cancel','Moving resources released before safe endpoint')
    return dict(status='PASS',actual=actual,expected=protocol['expected'],no_teleport_at_s=1,
        scope='Timed cancellation correction only, no upgrade of original canonical capture')
def capture(protocol):
    require(not git('status','--porcelain'),'Execution checkout must be clean')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set PYTHONPATH=src')
    source=git('rev-parse','HEAD').decode().strip();pins=identities(source,protocol)
    require(all(h((ROOT/n).read_bytes())==v for n,v in pins.items()),'Initial source differs')
    folder=ROOT/FOLDER;folder.mkdir()
    write(folder/'attempt.json',dict(execution_commit=source,classification='ENGINEERING_ONLY_CORRECTION',argv=sys.argv,executable=sys.executable,physical_runs=1))
    receipt=dict(execution_commit=source,pinned=pins,global_regression_gate='PENDING_ROOT_INTEGRATED_FULL',field_calibration='PENDING')
    try:
        from aegis_dc.plant import simulate_scenario,describe_run
        inputs=read(ROOT/protocol['input'])
        result=simulate_scenario(inputs['model'],duration_s=protocol['duration_s'],step_s=protocol['maximum_step_s'],
            work_program=inputs['program'],boundary_events=inputs['boundary_events'])
        r=describe_run(result);documents={'scenario.json':json.dumps(result['source_config'],ensure_ascii=False,indent=2,allow_nan=False)+'\n',
            'private-state.jsonl':''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in result['trace']),
            'balances.jsonl':''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in result['balances'])}
        r['artifacts']={n:dict(sha256=h(v.encode())) for n,v in documents.items()}
        for n,v in documents.items():write(folder/n,v.encode())
        write(folder/'run.json',r);write(folder/'checks.json',check(folder,protocol))
        require({p.name for p in folder.iterdir()}==set(protocol['durable_outputs']),'Declared set differs');receipt['status']='PASS'
    except Exception as error:receipt.update(status='FAIL',error=str(error));raise
    finally:
        receipt['source_unchanged']=git('rev-parse','HEAD').decode().strip()==source and all(h((ROOT/n).read_bytes())==v for n,v in pins.items())
        if not receipt['source_unchanged']:receipt['status']='FAIL'
        receipt['artifacts']={p.name:h(p.read_bytes()) for p in folder.iterdir() if p.is_file()};write(folder/'receipt.json',receipt)
    require(receipt['source_unchanged'],'Source changed');return receipt
def verify(protocol,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),'Use clean delivery checkout')
    folder=ROOT/FOLDER;receipt=read(folder/'receipt.json');require(receipt['status']=='PASS' and receipt['source_unchanged'],'Correction capture failed')
    require(set(receipt['artifacts'])==set(protocol['durable_outputs']),'Durable declaration differs')
    for n,v in {**receipt['artifacts'],'receipt.json':h((folder/'receipt.json').read_bytes())}.items():
        require(h((folder/n).read_bytes())==v==h(git('cat-file','blob',delivery+':'+FOLDER+'/'+n)),'Correction output differs:'+n)
    require(receipt['pinned']==identities(receipt['execution_commit'],protocol),'Source set differs')
    for n,v in receipt['pinned'].items():require(h((ROOT/n).read_bytes())==v==h(git('cat-file','blob',delivery+':'+n)),'Correction source differs:'+n)
    require(read(folder/'checks.json')==check(folder,protocol),'Saved summary differs')
    return dict(status='PASS',execution_commit=receipt['execution_commit'],delivery_commit=delivery,artifacts=6,terminal_receipts=1,
        pinned_paths=len(receipt['pinned']),physical_rerun=False,full_regression_rerun=False,registered_research_trials=0,llm_calls=0,training_calls=0)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['capture','verify']);p.add_argument('--delivery');a=p.parse_args();protocol=read(ROOT/PROTOCOL)
    print(json.dumps(capture(protocol) if a.mode=='capture' else verify(protocol,a.delivery),ensure_ascii=False))
