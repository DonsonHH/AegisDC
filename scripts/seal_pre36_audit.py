"""Package and fresh-verify the declared pre36 audit delivery, without models."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
AUDIT='docs/mainline/audits/20261108-pre36'
BASE='2dfe5537e4f95fa605f325b060ef32223dafb4f6'
git=lambda *a:subprocess.check_output(['git',*a],cwd=ROOT)
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_bytes())

def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def durable(folder):
    return {p.relative_to(ROOT).as_posix() for p in folder.rglob('*') if p.is_file()
            and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}}

def declaration():
    names=durable(ROOT/AUDIT)
    names.discard(AUDIT+'/delivery-manifest.json')
    for role in ['pre36-closure-review','pre36-historical-ci','pre36-readout']:
        names.update(durable(ROOT/'evidence/mainline/engineering'/role))
    names.update('scripts/'+p for p in ['seal_pre36_audit.py','check_closure_review_time.py',
        'check_historical_ci_contracts.py','complete_registered_readout.py'])
    names.update('tests/'+p for p in ['test_pre36_closure_review_time.py','historical_research_checkout.py',
        'test_registered_development.py','test_confirmation_freeze.py','test_ablation_masks.py','test_verified_closure.py'])
    names.update(['src/aegis_dc/verified_closure.py',
        'evidence/mainline/engineering/18-beliefs/capture-01/cli-frame.json',
        'evidence/mainline/engineering/23-interventions/reference/filter-later-inspection.json'])
    return names

def build(reviews):
    assert not (ROOT/AUDIT/'delivery-manifest.json').exists()
    assert not git('status','--porcelain','--untracked-files=no').strip()
    source=git('rev-parse','HEAD').decode().strip()
    packets={}
    directory=ROOT/AUDIT/'reviews';directory.mkdir(exist_ok=False)
    for spec in reviews:
        role,path=spec.split('=',1);folder=ROOT/path
        mf=folder/('final-manifest.json' if (folder/'final-manifest.json').exists() else 'manifest.json')
        data=read(mf)
        if 'artifacts' in data:
            files={n:(v['sha256'] if isinstance(v,dict) else v) for n,v in data['artifacts'].items()}
        else:files={r['path']:r['sha256'] for r in data['files']}
        files[mf.name]=sha(mf.read_bytes())
        destination=directory/(role+'.zip')
        with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for n,expected in sorted(files.items()):
                raw=(folder/n).read_bytes();assert sha(raw)==expected,(role,n)
                z.writestr(n,raw)
        packets[role]=dict(path=destination.relative_to(ROOT).as_posix(),members=files,
            original_manifest_sha256=sha(mf.read_bytes()))
    # The human-readable35-row Spec matrix is byte-identical to its frozen review.
    matrix=ROOT/'.work/pre36-spec-audit-01/ticket-matrix.md'
    (ROOT/AUDIT/'ticket-matrix.md').write_bytes(matrix.read_bytes())
    names=declaration()
    files={n:dict(sha256=sha((ROOT/n).read_bytes()),bytes=(ROOT/n).stat().st_size) for n in sorted(names)}
    write(ROOT/AUDIT/'delivery-manifest.json',dict(schema='aegisdc-pre36-audit-delivery-v1',
        authoring_source=source,original_audit_source=BASE,files=files,review_packets=packets,
        durable_scope='Explicit files only; no caches or new research execution',new_registered_runs=0))
    return dict(status='SEALED',files=len(files),review_packets=len(packets),source=source)

def verify(output):
    source=git('rev-parse','HEAD').decode().strip();mf=ROOT/AUDIT/'delivery-manifest.json';m=read(mf)
    assert declaration()==set(m['files'])
    for n,entry in m['files'].items():
        raw=(ROOT/n).read_bytes();assert len(raw)==entry['bytes'] and sha(raw)==entry['sha256'],n
        assert git('cat-file','blob',source+':'+n)==raw,n
    assert git('cat-file','blob',source+':'+mf.relative_to(ROOT).as_posix())==mf.read_bytes()
    members=0
    for entry in m['review_packets'].values():
        with zipfile.ZipFile(ROOT/entry['path']) as z:
            assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(entry['members'])
            for n,expected in entry['members'].items():assert sha(z.read(n))==expected;members+=1
    inventory=read(ROOT/AUDIT/'ticket-inventory.json')
    assert len(inventory['tickets'])==35 and all(r['acceptance_status']=='ACCEPTED' for r in inventory['tickets'])
    for r in inventory['tickets']:
        assert sha(git('cat-file','blob',BASE+':'+r['path']))==r['ticket_sha256']
    readout=ROOT/'evidence/mainline/engineering/pre36-readout/readout-01'
    rm=read(readout/'manifest.json')
    for n,expected in rm['artifacts'].items():assert sha((readout/n).read_bytes())==expected['sha256']
    inputs=read(readout/'input-manifest.json')
    for n,entry in inputs['files'].items():
        raw=(ROOT/n).read_bytes();assert sha(raw)==entry['sha256']
        assert git('cat-file','blob',BASE+':'+n)==raw
    for n,entry in inputs['native_members'].items():
        with zipfile.ZipFile(ROOT/n) as z:
            raw=z.read('run.json');assert sha(raw)==entry['run.json']['sha256']
    for name,tests,failures in [('red-01',3,2),('green-01',3,0),('compatibility-01',14,0)]:
        folder=ROOT/'evidence/mainline/engineering/pre36-closure-review'/name
        r=read(folder/'receipt.json');start=read(folder/'start.json')
        assert (r['tests'],r['failures'],r['errors'],r['skipped'])==(tests,failures,0,0)
        for n,h in start['source_sha256'].items():assert sha(git('cat-file','blob',r['source']+':'+n))==h
    changed=git('diff','--name-only',BASE,source,'--','src/aegis_dc').decode().splitlines()
    assert changed==['src/aegis_dc/verified_closure.py']
    receipt=dict(status='PASS_FRESH_SAVED_DELIVERY',source=source,files=len(m['files']),review_members=members,
        tickets=35,original_archives=len(inputs['native_members']),original_input_files=len(inputs['files']),
        historical_primary_unchanged=True,new_physical_calls=0,new_selector_calls=0,new_research_trials=0,
        closure_account='37 instrumented parent calls +1 saved CLI invocation =38 derived',
        fixture_scope='Two input identities supplemented after execution, not simultaneous guards')
    write(output,receipt);return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    b=sub.add_parser('build');b.add_argument('--review',action='append',required=True)
    v=sub.add_parser('verify');v.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(build(args.review) if args.mode=='build' else verify(args.output)))
