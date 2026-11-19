"""Fresh detached checkout and previously fetched emission identity checks; no project import."""
import hashlib,json,posixpath,re,subprocess,sys
from pathlib import Path
work=Path.cwd().resolve()
tree=Path(sys.argv[1]).resolve()
rev=sys.argv[2]
pack='docs/mainline/v6-intake-engineering-v1'
def run(*args):
    return subprocess.check_output(['git','-C',str(tree),*args])
def sha(b):return hashlib.sha256(b).hexdigest()
def obj(version,path):return run('cat-file','blob',version+':'+path)
assert run('rev-parse','HEAD').decode().strip()==rev
tracked=run('ls-tree','-r','--name-only',rev,'--',pack,'src/aegis_dc','src/patrol_rsi/contracts.py','scripts/qualify_v6_intake.py','docs/MAINLINE.md','docs/mainline/progress.json','docs/current-research.json').decode().splitlines()
files={};targets=set()
for name in tracked:
    x=(tree/name).read_bytes(); original=obj(rev,name)
    assert x==original,name
    files[name]=dict(sha256=sha(x),bytes=len(x))
    if name.startswith(pack+'/') and name.endswith('.md'):
        for url in re.findall(r'\[[^\]]*\]\(([^)]+)\)',x.decode()):
            target=url.split('#')[0]
            if target and not re.match(r'[a-z]+:',target):
                path=posixpath.normpath(posixpath.join(posixpath.dirname(name),target))
                run('cat-file','-e',rev+':'+path);targets.add(path)
manifest=json.loads(obj(rev,pack+'/manifest.json'))
for name,expected in manifest['files'].items():assert files[pack+'/'+name]['sha256']==expected
amend=json.loads(obj(rev,pack+'/input-binding-addendum.json'))
for name,h in amend['author_files'].items():assert files[pack+'/'+name]['sha256']==h
ledger=json.loads(obj(rev,pack+'/attempts.json'));result=json.loads(obj(rev,pack+'/result.json'))
assert files[pack+'/result.json']['sha256']==ledger['verified_public_summary_sha256']
pins=[]
for a in ledger['attempts']:
    path=work/'.work/v6-intake'/a['attempt']/'source-manifest.json';body=path.read_bytes()
    assert sha(body)==a['durable_sha256']['source/source-manifest.json']
    m=json.loads(body)
    specs=[(m['execution_revision'] if f.startswith(('src/','configs/')) else m['checker_revision'])+':'+f for f in m['files']]
    process=subprocess.run(['git','-C',str(tree),'cat-file','--batch-check=%(objectname)'],input=('\n'.join(specs)+'\n').encode(),stdout=subprocess.PIPE,check=True)
    rows=dict(zip(m['files'],process.stdout.decode().splitlines()))
    assert rows==m['git_blobs']
    pins.append(dict(attempt=a['attempt'],source_revision=m['execution_revision'],pinned_files=len(rows),manifest_sha256=sha(body)))
protected=['tests/fixtures/39c-business-record-replay-57.json','docs/mainline/39c-business-record-replay-contract-57.md','evidence/mainline/engineering/39c-development/slice-57/result.json']
guards={f:sha(obj(rev,f)) for f in protected}
assert guards=={f:sha(obj('b5a2e9ad',f)) for f in protected}
assert not run('diff','--name-only','b5a2e9ad',rev,'--','configs','tests','evidence','docs/mainline/review-gated')
names=[u['unit'] for u in result['units']]
assert names==manifest['order'] and len(set(names))==19
assert [u['unit'] for u in result['units'] if u['mismatches']]==['expired-read']
assert sum(len(u['mismatches']) for u in result['units'])==9
assert sum(u['assertions'] for u in result['units'])==325
assert all(i['passed'] for i in result['interfaces']) and len(result['interfaces'])==5
assert all(i['matched'] for i in result['pairs']) and len(result['pairs'])==3
out=dict(checked_revision=rev,method='fresh detached sparse Git checkout, raw byte comparison, job manifest Git identities and originally stored artifact hashes',files_verified=files,local_document_targets_verified=sorted(targets),runtime_and_check_sources=pins,frozen_slice57_sha256=guards,old_configs_tests_evidence_incident_protocols_changed=False,
      saved_reconciliation_sha256=result['full_checks_sha256'],model_calls=0)
def observation_path(version):
    text=obj(version,'src/aegis_dc/intake_value.py').decode()
    def section(left,right):
        start=text.index(left);return text[start:text.index(right,start)]
    return {key:sha(body.encode()) for key,body in [
        ('exact_numeric_conversion',section('def number(', 'def validate_model(')),
        ('report_class',section('def report_class(', 'def masses(')),
        ('own_record_and_work_ack_before_supported_continuation',section("        elif ids['inspect'] in issued:", "            if outcome in ('LOW','NORMAL'):"))]}
original=observation_path('75675e85')
assert original==observation_path('534fbfa9')==observation_path('6aaea863')==observation_path(rev)
old=json.loads((work/'.work/v6-intake/green01/observed.json').read_bytes())
before=next(q for q in old['rows'] if q['unit']=='expired-read')
after=next(q for q in result['units'] if q['unit']=='expired-read')
out['expiry_evidence']={'actual_arrival_path_source_sha256':original,'earlier_actual_decisions':before['decisions'],
    'earlier_recorded_revision':old['execution_revision'],'earlier_saved_run_sha256':before['run_sha256'],
    'final_actual_source':after['source'],'final_saved_run_sha256':after['run_sha256'],
    'scope':'Earlier build actually received EXPIRED; exact report classifier and own-record/ACK prefix are unchanged. Repaired root excludes the route. The full original path remains a mismatch.'}
out['integrity_tool_sha256']=sha(Path(__file__).read_bytes())
Path(sys.argv[3]).write_bytes((json.dumps(out,indent=2)+'\n').encode())
print('checkout files',len(files),'links',len(targets),'source manifests',[(x['attempt'],x['pinned_files']) for x in pins],'protected',len(guards))

