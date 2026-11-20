"""Fresh Git checkout, durable-file and Slurm-return identity readback; zero scientific calls."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tarfile

PACK='docs/mainline/v6-native-comparison-qualification-v1'
PROTO='docs/mainline/v6-native-method-comparison-v1'
BASE='53cc32b93dd62c8ce5ffd725eed9afba167557e5'
FREEZE='5836f0f17c7189a5782835647181713a19ee68f1'
RUNTIME='721d966218cbed4d5603c7fda5dafb83d595dfbe'


def require(condition,reason):
    if not condition:raise ValueError(reason)


def sha(data):return hashlib.sha256(data).hexdigest()
def parse(path):return json.loads(path.read_bytes())
def canonical(doc):return sha(json.dumps(doc,sort_keys=True,allow_nan=False,separators=(',',':')).encode())


def main(checkout,work,output):
    def git(*args,stdin=None):
        return subprocess.check_output(['git','-C',str(checkout),*args],input=stdin)
    def blob(version,path):return git('cat-file','blob',version+':'+path)
    rev=git('rev-parse','HEAD').decode().strip()
    require(not git('status','--porcelain','--untracked-files=no'),'Dirty verification worktree')
    result=parse(checkout/PACK/'result.json');manifest=parse(checkout/PACK/'research-manifest.json')
    freeze=parse(checkout/PACK/'freeze.json');fixtures=parse(checkout/PACK/'fixtures.json')
    classified=parse(checkout/PACK/'evidence-scope.json');conditions=parse(checkout/PROTO/'conditions.json')
    changes=git('diff','--name-only',BASE,rev).decode().splitlines()
    allowed={'docs/MAINLINE.md','docs/current-research.json','docs/mainline/progress.json',PROTO+'/acceptance-20261120.json',
        'scripts/qualify_native_comparison.py',*['src/aegis_dc/'+n+'.py' for n in ('problem_tasks','intake_value','problem_actions',
        'native_compare_inputs','native_compare_run','native_compare_score')]}
    require(all(f in allowed or f.startswith(PACK+'/') for f in changes),'Undeclared baseline change')
    links=set();delivery={}
    for f in changes:
        raw=blob(rev,f)
        require((checkout/f).read_bytes()==raw,'Fresh delivery file differs: '+f)
        delivery[f]=dict(bytes=len(raw),sha256=sha(raw),git_blob=git('rev-parse',rev+':'+f).decode().strip())
        if (f.startswith(PACK+'/') or f==PROTO+'/acceptance-20261120.json') and f.endswith('.md'):
            for url in re.findall(r'\[[^\]]*\]\(([^)]+)\)',raw.decode()):
                target=posixpath.normpath(posixpath.join(posixpath.dirname(f),url.split('#')[0]))
                git('cat-file','-e',rev+':'+target);links.add(target)
    freeze_pins=freeze['files']|fixtures['source_sha256']
    for f,h in freeze_pins.items():
        require(sha(blob(FREEZE,f))==sha(blob(rev,f))==h,'Original frozen checker or input changed: '+f)
    require(not git('diff','--name-only','0f5db8c8',rev,'--','src','scripts/qualify_native_comparison.py'),'Returned runtime differs from delivered runtime')
    versions=[]
    for a in result['attempts']:
        folder=work/a['attempt'];download=folder/'collected';launch=parse(folder/'launch.json')
        require(sha((folder/'launch.json').read_bytes())==a['launch_sha256'] and sha((folder/'source.tar.gz').read_bytes())==a['source_archive_sha256'],'Staging material drift')
        with tarfile.open(folder/'source.tar.gz','r:gz') as archive:
            seen={m.name:sha(archive.extractfile(m).read()) for m in archive if m.isfile()}
        require(seen==launch['files'],'Incorrect archive files')
        refs=[(a['implementation_revision'] if path.startswith(('src/','configs/')) else a['checker_revision'])+':'+path for path in seen]
        stream=BytesIO(git('cat-file','--batch',stdin=('\n'.join(refs)+'\n').encode()))
        for path in seen:
            header=stream.readline().split()
            require(len(header)==3 and header[1]==b'blob','Missing Git blob '+path)
            data=stream.read(int(header[2]));stream.read(1)
            require(sha(data)==seen[path],'Archived source differs from Git revision '+path)
        require(not stream.read(1),'Unexpected Git response suffix')
        report=parse(download/'output/report.json')
        durable=parse(download/'output/durable-files.json')
        require(sha((download/'output/report.json').read_bytes())==a['report_sha256'] and
                sha((download/'output/durable-files.json').read_bytes())==a['durable_manifest_sha256']==report['durable_manifest_sha256'],'Private report or inventory drift')
        roles=classified['original_inventories'][a['attempt']]
        require(roles['original_sha256']==a['durable_manifest_sha256'] and set(durable)==set(roles['roles']) and all(roles['roles'].values()),'Unclassified original artifact')
        for path,h in parse(download/'retrieval.json')['downloaded_sha256'].items():
            require(sha((download/path).read_bytes())==h,'Retrieved file changed: '+path)
        require(report['job']==a['job'] and a['slurm']['state']==parse(download/'retrieval.json')['sacct'][0].split('|')[1],'Job state differs')
        runtime={k:v for k,v in seen.items() if (k.startswith('src/aegis_dc/') and k.count('/')==2 and k.endswith('.py')) or k=='src/patrol_rsi/contracts.py'}
        versions.append(dict(attempt=a['attempt'],job=a['job'],pinned_files=len(seen),durable_files=len(durable),runtime_sha256=canonical(runtime)))
    require(versions[1]['runtime_sha256']==versions[2]['runtime_sha256']==manifest['actual_runtime_source_tree'],'Runtime identity drift')
    for spec,group in zip(conditions['conditions'],manifest['groups'],strict=True):
        require(group['condition']==spec['id'] and group['arm_inputs']==spec['arms'] and group['fixed_order']==['V','D','K','H','P'],'Research schedule identity differs')
    require(manifest['state']=='PREPARED_AWAITING_SEPARATE_USER_AUTHORIZATION' and not manifest['research_execution_authorized']
        and manifest['already_launched']==0 and manifest['planned']['arm_positions']==85,'Research gate drift')
    checks=result['checks']
    require(len(checks)==43 and all(u['passed'] for u in checks.values()),'Incomplete finite check set')
    assertions=sum(len(u['assertions']) for u in checks.values())
    require(assertions==512,'Assertion denominator changed')
    require(sum(a['facility_started'] for a in result['attempts'])==12 and sum(a['internal_known'] for a in result['attempts'])==240
        and sum(len(a['public_started']) for a in result['attempts'])==27 and sum(len(a['substitute_started']) for a in result['attempts'])==4,
        'Actual call denominators differ')
    need_ids=[x['unit'] for x in fixtures['facilities']]
    require([u['unit'] for u in result['actual_native']]==need_ids and result['actual_native'][0]['pid']!=result['actual_native'][3]['pid']
            and result['actual_native'][0]['semantic_sha256']==result['actual_native'][3]['semantic_sha256'],'Independent arm evidence differs')
    require(len(result['failures']['initial_facility']['assertions'])==18 and len(result['failures']['suffix'])==10 and
            len(result['failures']['retained_raw_timestamp_diagnostics'])==6,'Retained failure provenance drift')
    scope=classified['counter_boundary']['public_return_examples'];require(len(scope)==2 and all(x['logical_version_counter_only'] for x in scope),'Counter scope differs')
    progress=parse(checkout/'docs/mainline/progress.json')
    require(progress['current_milestone']=='STOP_AT_NATIVE_COMPARISON_FINITE_ENGINEERING_REVIEW' and not progress['active_implementations']
        and progress['v6_native_comparison_engineering_v1']['user_acceptance_pending'],'Wrong delivery state')
    old=['tests/fixtures/39c-business-record-replay-57.json','docs/mainline/39c-business-record-replay-contract-57.md',
         'evidence/mainline/engineering/39c-development/slice-57/result.json']
    protected={f:sha(blob(rev,f)) for f in old}
    require(all(sha(blob(BASE,f))==h for f,h in protected.items()),'Protected slice changed')
    out=dict(schema='aegisdc-native-qualification-git-integrity-v1',content_revision=rev,protocol=BASE,original_oracle_freeze=FREEZE,
        files=delivery,archive_pins=versions,immutable_input_and_oracle_file_count=len(freeze_pins),
        exact_research_arm_identities=85,matched_unique_assertions=assertions,retained_failed_slurm_jobs=['134665','134666'],
        markdown_targets=sorted(links),slice57_sha256=protected,physics_closure_prior_protocols_and_old_evidence_unchanged=True,
        phase='ENGINEERING_REVIEW_ONLY',new_computational_calls_in_this_readback=0)
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(out,stream,indent=2,ensure_ascii=False);stream.write('\n')
    print('Fresh delivery',len(delivery),'files;',len(links),'links; source/durable maps',[(v['pinned_files'],v['durable_files']) for v in versions],
        '; 85 planned arm identities; 512 finite assertions; 3 protected slice files')

if __name__=='__main__':main(*map(Path,sys.argv[1:4]))
