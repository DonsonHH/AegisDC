"""Seal and fresh-verify saved36 evidence; no project models or nonce access."""
import argparse,hashlib,io,json,math,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
PACKAGE='evidence/mainline/research/36-robustness'
MANIFEST=PACKAGE+'/delivery-manifest.json'
EXECUTION='18679d7620385c553041e58065d6c7841faebb15'
git=lambda *a:subprocess.check_output(['git',*a],cwd=ROOT)
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_bytes())

def write(p,d):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def blob_hashes(revision,names):
    names=sorted(names)
    if not names:return {}
    raw=subprocess.check_output(['git','cat-file','--batch'],cwd=ROOT,input=''.join(revision+':'+n+'\n' for n in names).encode())
    values={};offset=0
    for name in names:
        end=raw.index(b'\n',offset);header=raw[offset:end].split();assert len(header)==3 and header[1]==b'blob',name
        size=int(header[2]);start=end+1;values[name]=sha(raw[start:start+size]);offset=start+size+1
    assert offset==len(raw);return values

def declaration():
    names=set(read(ROOT/'docs/mainline/evidence/30-robustness-execution-lock.json')['execution_pins'])
    for directory in [PACKAGE,'evidence/mainline/engineering/36-public-admission']:
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*') if p.is_file()
            and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'})
    names.discard(MANIFEST)
    names.update(['docs/mainline/30-comparison-protocol-v1.json','docs/mainline/36-prospective-extension.json',
        'docs/mainline/36-public-contract-correction-01.json','docs/mainline/36-pure-input-classification.json',
        'docs/mainline/36-robustness-execution.json','docs/mainline/evidence/30-robustness-execution-lock.json',
        'docs/mainline/evidence/36-preparation-authorization.json','docs/mainline/evidence/36-execution-authorization.json',
        'docs/mainline/evidence/36-preexecution-fresh.json','evidence/mainline/research/34-paired-analysis/results.json',
        'tests/test_robustness_release.py'])
    return names

def seal():
    names=declaration();assert not (ROOT/MANIFEST).exists()
    files={n:sha((ROOT/n).read_bytes()) for n in sorted(names)}
    assert files==blob_hashes('HEAD',names),'Commit all durable artifacts before sealing'
    write(ROOT/MANIFEST,dict(schema='aegisdc-36-saved-delivery-v1',authoring_source=git('rev-parse','HEAD').decode().strip(),
        actual_execution_source=EXECUTION,files=files,scope='Explicit durable files; native originals, all failed QA/reviews, frozen tools and source. Caches excluded.'))
    return dict(status='SEALED_SAVED_DELIVERY',files=len(files))

def verify(output):
    source=git('rev-parse','HEAD').decode().strip();manifest=read(ROOT/MANIFEST);files=manifest['files']
    assert declaration()==set(files) and files==blob_hashes(source,files)
    for n,h in files.items():assert sha((ROOT/n).read_bytes())==h,n
    review_members=0
    for entry in read(ROOT/PACKAGE/'result-review/index.json').values():
        archive=ROOT/PACKAGE/'result-review'/entry['archive'];assert sha(archive.read_bytes())==entry['sha256']
        with zipfile.ZipFile(archive) as z:
            assert set(z.namelist())==set(entry['members']) and len(z.namelist())==len(set(z.namelist()))
            for n,h in entry['members'].items():assert sha(z.read(n))==h;review_members+=1
    lock=read(ROOT/'docs/mainline/evidence/30-robustness-execution-lock.json');pins=lock['execution_pins']
    assert pins==blob_hashes(EXECUTION,pins) and len(pins)==286
    assert sha(Path(sys.executable).read_bytes())==lock['interpreter_sha256']
    capture=ROOT/PACKAGE/'capture-01';receipt=read(capture/'receipt.json');batch=read(capture/'batch.json')
    assert receipt['status']=='PASS' and receipt['source_unchanged'] and batch['execution_commit']==EXECUTION
    assert batch['pins']==blob_hashes(EXECUTION,batch['pins'])
    preparation=read(ROOT/PACKAGE/'prepared-01/receipt.json')
    assert preparation['pins']==blob_hashes(preparation['source'],preparation['pins'])
    assert receipt['total']==dict(started=16,completed=16,failed=0,interrupted=0,unrun=0,charged_simulated_s=160,charged_scheduled_decisions=160,returned_decisions=160)
    for n,h in receipt['artifacts'].items():assert sha((capture/n).read_bytes())==h
    journal=[json.loads(line) for line in (capture/'attempts.jsonl').read_bytes().splitlines()]
    assert len(journal)==32 and [(r['index'],r['status']) for r in journal]==[(i,s) for i in range(1,17) for s in ['STARTED','COMPLETED']]
    rows=read(ROOT/PACKAGE/'analysis-01/run-readout.json');lookup={(r['world_id'],r['arm']):r for r in rows}
    recomputed={};members=0
    for slot in batch['slots']:
        folder=capture/f"{slot['index']:02}-{slot['world_id']}-{slot['arm']}"
        terminal=read(folder/'terminal.json');original=read(folder/'originals.json');archive=(folder/'originals.zip').read_bytes()
        assert terminal['source']==EXECUTION and terminal['status']=='COMPLETED' and sha(archive)==original['archive_sha256']==terminal['artifacts']['originals.zip']
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            assert set(z.namelist())==set(original['members']) and len(z.namelist())==4
            raw={n:z.read(n) for n in z.namelist()}
            for n,h in original['members'].items():assert sha(raw[n])==h;members+=1
        native=json.loads(raw['run.json']);input_path=ROOT/PACKAGE/'prepared-01/inputs'/slot['input_member']
        assert sha(input_path.read_bytes())==lock['input_hashes'][slot['input_member']]
        expected=read(input_path)
        assert json.loads(raw['scenario.json'])==expected['model'] and native['inputs']['dispatch_program']==expected['dispatch_program']
        assert native['code_identity']['git_commit']==EXECUTION and native['code_identity']['implementation_has_changes'] is False
        assert all(pins[n]==h for n,h in native['code_identity']['files'].items())
        trace={r['time_s']:r for r in map(json.loads,raw['private-state.jsonl'].splitlines())}
        balances=list(map(json.loads,raw['balances.jsonl'].splitlines()));audit=read(folder/'audit.json');totals=audit['totals']
        assert not audit['hard_violations'] and native['inputs']['dispatch_program']['closure_program'] is None
        contributions=[]
        for b in balances:
            state=trace[b['start_s']]['domains']['it_service'];dt=b['end_s']-b['start_s'];demand=state['demand'];delivered=state['delivered']
            assert 0<=delivered<=demand and delivered<=min(state['capacities'].values())+1e-8
            amount=(demand-delivered)/demand*dt if demand else 0;contributions.append(amount)
            assert math.isclose(amount,b['service_deficit_time_s'],rel_tol=0,abs_tol=1e-8)
            assert math.isclose(b['worker_wait_person_s'],math.fsum(b[k] for k in ['access_check_person_s','rendezvous_wait_person_s','queue_wait_person_s']),rel_tol=0,abs_tol=1e-8)
        key=(slot['world_id'],slot['arm']);recomputed[key]=math.fsum(contributions)
        assert math.isclose(recomputed[key],totals['service_deficit_time_s'],rel_tol=0,abs_tol=1e-8)
        for k,v in totals.items():assert math.isclose(v,lookup[key][k],rel_tol=0,abs_tol=1e-8)
        assert lookup[key]['verified_closure']=='NOT_EVALUATED_WITHOUT_POST_ACTION_PROTOCOL'
    result=read(ROOT/PACKAGE/'analysis-01/results.json');deltas=[]
    for p in result['paired']:
        delta=recomputed[(p['world_id'],'one_observation_lookahead')]-recomputed[(p['world_id'],'evidence_consistent_contingent')]
        assert math.isclose(delta,p['delta_service_s'],rel_tol=0,abs_tol=1e-8);deltas.append(delta)
    assert len(deltas)==8 and math.isclose(math.fsum(deltas)/8,result['mean_over_eight_designed_worlds_service_delta_s'],rel_tol=0,abs_tol=1e-8)
    assert result['original_primary_unchanged']==dict(status='NO_PRACTICAL_GAIN',mean_service_delta_s=.03515625,worlds=16)
    for version in ['figures','figures-v2','figures-v3']:
        folder=ROOT/PACKAGE/version;m=read(folder/'manifest.json')
        assert m['input_sha256']==sha((ROOT/PACKAGE/'analysis-01/results.json').read_bytes())
        for n,h in m['artifacts'].items():assert sha((folder/n).read_bytes())==h
    assert not any(n.startswith('aegis_dc') for n in sys.modules)
    proof=dict(status='PASS_FRESH_SAVED36_DELIVERY',source=source,files=len(files),frozen_execution_files=286,
        archives=16,native_members=members,result_review_members=review_members,actual_runs=16,paired_worlds=8,contrast_blocks=4,
        original_primary_unchanged=True,new_physical_calls=0,new_selectors=0,new_inference=0)
    write(output,proof);return proof

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['seal','verify']);p.add_argument('--output',type=Path);a=p.parse_args()
    try:print(json.dumps(seal() if a.mode=='seal' else verify(a.output)))
    except BaseException as exc:
        if a.output and not a.output.exists():write(a.output,dict(status='REFUSED_SAVED_DELIVERY',error_type=type(exc).__name__,error=str(exc),new_physical_calls=0))
        raise
