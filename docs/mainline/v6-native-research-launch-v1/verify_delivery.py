"""Check committed delivery blobs, the deployed verification archive and the immutable research plan."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tarfile

PACK='docs/mainline/v6-native-research-launch-v1'
ENG='docs/mainline/v6-native-comparison-qualification-v1'
BASE='984071352142239201e3b69a449207ec35cd7cfa'
FREEZE='4daac1bcd467dc1ac7cb785946025f76a8da888e'
FINAL='59080339a1846f242e0b8664e80a59b91ac623c768010ad1652e7d648c3b3301'
def require(ok,msg):
    if not ok:raise ValueError(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canon(data):return sha(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def read(path):return json.loads(path.read_bytes())

def main(tree,attempt,output):
    def git(*args,stdin=None):return subprocess.check_output(['git','-C',str(tree),*args],input=stdin)
    def blob(rev,path):return git('cat-file','blob',rev+':'+path)
    rev=git('rev-parse','HEAD').decode().strip()
    require(not git('status','--porcelain','--untracked-files=no'),'Dirty verification worktree')
    changed=git('diff','--name-only',BASE,rev).decode().splitlines();files={};links=set()
    allowed={'docs/MAINLINE.md','docs/mainline/progress.json','docs/current-research.json',ENG+'/acceptance-20261120.json','scripts/v6_research_launch.py'}
    require(all(n.startswith((PACK+'/','scripts/v6_research/')) or n in allowed for n in changed),'Unexpected scientific, old protocol or evidence edit')
    for n in changed:
        raw=(tree/n).read_bytes()
        require(raw==blob(rev,n),'Fresh checkout differs: '+n)
        files[n]=dict(sha256=sha(raw),bytes=len(raw),git_blob=git('rev-parse',rev+':'+n).decode().strip())
        if n.startswith(PACK+'/') and n.endswith('.md'):
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',raw.decode()):
                target=posixpath.normpath(posixpath.join(posixpath.dirname(n),link.split('#')[0]))
                git('cat-file','-e',rev+':'+target);links.add(target)
    m=read(tree/PACK/'research-manifest.json');result=read(tree/PACK/'result.json');f=read(tree/PACK/'freeze.json')
    require(files[PACK+'/research-manifest.json']['sha256']==result['final_manifest_sha256']==FINAL,'Final manifest identity')
    require(sha(blob(FREEZE,PACK+'/freeze.json'))==files[PACK+'/freeze.json']['sha256'],'Witness freeze changed')
    require(sha(blob(FREEZE,ENG+'/acceptance-20261120.json'))==m['acceptance_sha256']==f['acceptance_sha256'],'Acceptance differed')
    prior=json.loads(blob(BASE,ENG+'/research-manifest.json'))
    require(m['groups']==prior['groups'] and m['budget']==prior['planned'] and m['runtime_and_material_sha256']==prior['runtime_and_material_sha256']
            and m['native_source_tree']==prior['actual_runtime_source_tree'] and m['python']==prior['python'],'Scientific identity changed')
    for fn,h in m['launcher_sha256'].items():
        require(sha(blob(m['launch_source_revision'],fn))==sha(blob(rev,fn))==h,'Launch file changed '+fn)
    launched=read(attempt/'launch.json');private=attempt/'returned'
    require(launched['source_revision']==result['verification_revision'] and launched['manifest_sha256']==FINAL,'Unexpected execution')
    retrieved=read(private/'retrieval.json')
    for path,h in retrieved['downloaded'].items():require(sha((private/path).read_bytes())==h,path)
    require(sha((attempt/'source.tar.gz').read_bytes())==launched['source_archive_sha256']==retrieved['server_sha256']['source.tar.gz'],'Archive transfer differs')
    with tarfile.open(attempt/'source.tar.gz','r:gz') as archive:
        archived={x.name:sha(archive.extractfile(x).read()) for x in archive if x.isfile()}
    require(archived==launched['files'],'Execution file set changed')
    specs=[launched['source_revision']+':'+path for path in archived]
    stream=BytesIO(git('cat-file','--batch',stdin=('\n'.join(specs)+'\n').encode()))
    for path in archived:
        fields=stream.readline().split();require(len(fields)==3 and fields[1]==b'blob','Missing executed file '+path)
        b=stream.read(int(fields[2]));stream.read(1)
        require(sha(b)==archived[path],'Actual archive differs from source commit '+path)
    require(not stream.read(1),'Extra blob')
    science={k:v for k,v in archived.items() if (k.startswith('src/aegis_dc/') and k.count('/')==2 and k.endswith('.py')) or k=='src/patrol_rsi/contracts.py'}
    require(canon(science)==m['native_source_tree'] and all(archived[k]==v for k,v in m['runtime_and_material_sha256'].items()),'Actual scientific source identity differs')
    require(all(archived[k]==v for k,v in m['launcher_sha256'].items()),'Actual research gate source differs')
    original=read(private/'output/report.json');catalog=read(private/'output/durable-files.json')
    require(original['durable_manifest_sha256']==sha((private/'output/durable-files.json').read_bytes()) and original['passed'] and not original['unexecuted'],'Execution report differs')
    require([t['id'] for t in f['tests']]==[c['id'] for c in result['checks']],'Frozen witness denominator')
    for check in result['checks']:
        unit=check['id'];require(check['passed'] and check['actual']==original['results'][unit]['actual'] and
            catalog['units/'+unit+'/observed.json']['sha256']==check['observed_file_sha256'],'Case receipt differs')
    r=result['additional_evidence']['H10'];require(r['actual_elapsed']==[0,5] and r['physical_records']==r['balance_records']+1
        and r['score_error'].endswith('Incomplete physical trajectory') and r['service_error']=='Incomplete H10 service window','H10 evidence missing')
    for key,ledger in result['fixture_journals'].items():
        require(ledger['complete_denominator']==len(ledger['observed_or_unresolved'])+len(ledger['not_executed'])==85,'Incomplete '+key)
    q=result['scope_counts']
    require(q['real_slurm_verification_jobs']==1 and q['surrogate_arm_processes']==12 and q['surrogate_scheduler_submissions']==6 and
        all(q[k]==0 for k in ['real_research_grants_created_or_consumed','real_research_scheduler_submissions','real_native_facility_calls','real_public_policy_calls']),
        'Scope or accounting differs')
    pg=read(tree/'docs/mainline/progress.json');require(pg['current_milestone']=='STOP_AT_NATIVE_RESEARCH_LAUNCH_REVIEW'
        and not pg['active_implementations'] and not pg['v6_native_study_launch_readiness']['research_consumed'],'Gate status differs')
    existing=read(tree/ENG/'integrity.json')['slice57_sha256']
    for name,h in existing.items():require(sha(blob(rev,name))==sha(blob(BASE,name))==h,'Slice 57 drift')
    checked=dict(schema='aegisdc-native-research-launch-integrity-v1',checked_content_revision=rev,baseline=BASE,freeze=FREEZE,
        final_manifest_sha256=FINAL,launcher_source=m['launch_source_revision'],validation_source=launched['source_revision'],
        durable_release_files=files,markdown_targets=sorted(links),executed_git_archive_files=len(archived),full_condition_arm_identities=85,
        qualified_native_runtime_and_material_files=len(m['runtime_and_material_sha256']),bound_launch_files=len(m['launcher_sha256']),
        finite_checks=10,frozen_fields=sum(len(t['expected']) for t in f['tests']),verification_attempts=1,private_inventory_count=len(catalog),
        slice57_sha256=existing,real_qualifier_job=result['attempts'][0]['job'],actual_facility_policy_or_study_runs_in_readback=0,
        old_scientific_code_and_evidence_unmodified=True,stop='RESEARCH_LAUNCH_REVIEW')
    with output.open('x',encoding='utf-8',newline='\n') as out:json.dump(checked,out,ensure_ascii=False,indent=2);out.write('\n')
    print('verified release',len(files),'archive',len(archived),'links',len(links),'raw evidence inventory',len(catalog),'frozen arm identities',85)
if __name__=='__main__':main(*map(Path,sys.argv[1:4]))
