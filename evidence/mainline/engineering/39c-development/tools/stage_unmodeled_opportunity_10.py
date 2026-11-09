import argparse,base64,hashlib,json,pathlib,shlex,subprocess,sys
if sys.flags.optimize:raise SystemExit("Optimized source authoring is forbidden")

p=argparse.ArgumentParser();p.add_argument('phase',choices=['red','green']);a=p.parse_args()
root=pathlib.Path.cwd();out=root/'.work/39c-opportunity10-remote'/a.phase;out.parent.mkdir(exist_ok=True);out.mkdir(exist_ok=False)
git=lambda *v:subprocess.check_output(['git',*v])
source=git('rev-parse','HEAD').decode().strip()
names=git('ls-tree','-r','--name-only',source,'--','src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py').decode().splitlines()
names+=['.gitattributes', '.gitignore', 'scripts/run_engineering_slice.py', 'tests/test_diagnostic_opportunity.py', 'tests/fixtures/39c-network-state-diagnostic.json', 'configs/materials/reference-r134a-saturation.json', 'tests/fixtures/39c-unmodeled-opportunity-10.json', 'tests/fixtures/39b-network-action-sequence.json', 'docs/mainline/39c-unmodeled-opportunity-protocol-10.json', 'docs/mainline/39c-unmodeled-opportunity-contract-10.md', 'evidence/mainline/engineering/39c-development/tools/stage_unmodeled_opportunity_10.py']
names=sorted(set(names));files={name:git('show',source+':'+name) for name in names}
assert pathlib.Path(__file__).read_bytes()==files['evidence/mainline/engineering/39c-development/tools/stage_unmodeled_opportunity_10.py'],'Actual authoring tool differs from frozen Git source'
blob_ids={name:git('rev-parse',source+':'+name).decode().strip() for name in names}
root_tree=git('rev-parse',source+'^{tree}').decode().strip()
trees=git('ls-tree','-d','-r','--full-tree','--format=%(objectname)',source).decode().splitlines()
objects=sorted(set([source,root_tree,*trees,*blob_ids.values()]))
packed=subprocess.run(['git','pack-objects','--stdout','--threads=1','--window=0'],input=('\n'.join(objects)+'\n').encode(),capture_output=True,check=True).stdout
files['source-objects.pack']=packed
files['execution-snapshot.json']=(json.dumps({'classification':'SPARSE_DECLARED_EXECUTION_SNAPSHOT_NOT_COMPLETE_CLONE','source_commit':source,'root_tree':root_tree,'selected_paths':names,'object_count':len(objects),'pack_sha256':hashlib.sha256(packed).hexdigest(),'preservation':'Canonical complete Git history and original large evidence remain in their existing repositories/storage; this is a bounded execution snapshot.'},indent=2)+'\n').encode()
attempt='13-unmodeled-reference-'+a.phase
remote='/share/home/renly/renly-patrol-rsi/mainline/39c-development/'+attempt
job=f'''#!/usr/bin/env bash
#SBATCH --job-name=aegis39c-run-{a.phase}
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --no-requeue
#SBATCH --output={remote}/slice-%j.out
#SBATCH --error={remote}/slice-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
unset PYTHONOPTIMIZE
cd {remote}
srun /share/home/renly/renly-patrol-rsi/environments/aegisdc-verify-20261109/bin/python -B -X utf8 scripts/run_engineering_slice.py --manifest manifest.json --output results
'''
files['job.slurm']=job.encode()
manifest={'classification':'ENGINEERING_DEVELOPMENT_NOT_RESEARCH_TRIAL','attempt':attempt,'phase':a.phase,'source_commit':source,'execution_git_snapshot':True,'protocol':'docs/mainline/39c-unmodeled-opportunity-protocol-10.json','evaluation':dict(test_pattern='test_diagnostic_opportunity.py',direct_public_choice_calls=0,facility_calls=1,maximum_returned_decisions=3,tests_run=1,test_names=['test_diagnostic_opportunity.DiagnosticOpportunityTests.test_unmodeled_reference_keeps_null_time_and_full_fault_event'],red_error='Business closure evaluation program fields do not match the closed contract'),'files':{name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),git_blob=blob_ids.get(name)) for name,data in files.items()}}
for name in names:
 if name.startswith('src/aegis_dc/') and (a.phase=='red' or name not in {'src/aegis_dc/business_endpoints.py','src/aegis_dc/diagnostic_endpoints.py'}):
  assert files[name]==git('show','2bd11ed32ac012ffc102611b5121739aa5386032:'+name),'Existing-behavior qualification changed domain runtime'
assert 'tests/'+manifest['evaluation']['test_pattern'] in files,'Frozen test is absent from declared stage'
files['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode();(out/'manifest.json').write_bytes(files['manifest.json'])
payload=json.dumps({'destination':remote,'files':{k:base64.b64encode(v).decode('ascii') for k,v in files.items()}}).encode()
program='''import base64,hashlib,json,os,pathlib,pwd,subprocess,sys
if sys.flags.optimize:raise SystemExit('Optimized source transport is forbidden')
assert pwd.getpwuid(os.getuid()).pw_name=='renly' and os.uname().nodename.split('.')[0]=='mu01' and os.environ['HOME']=='/share/home/renly'
p=json.load(sys.stdin);r=pathlib.Path(p['destination'])
assert r.parent.as_posix()=='/share/home/renly/renly-patrol-rsi/mainline/39c-development' and r.name in {'13-unmodeled-reference-red','13-unmodeled-reference-green'}
r.parent.mkdir(parents=True,exist_ok=True);r.mkdir(mode=0o700,exist_ok=False)
files={k:base64.b64decode(v) for k,v in p['files'].items()};m=json.loads(files['manifest.json'])
for name,v in m['files'].items():
 data=files[name];assert len(data)==v['bytes'] and hashlib.sha256(data).hexdigest()==v['sha256']
def git(*args,**kw):return subprocess.run(['git',*args],cwd=r,capture_output=True,check=True,**kw)
git('init','-q');git('config','core.autocrlf','false');git('unpack-objects','-q',input=files['source-objects.pack'])
git('update-ref','refs/heads/frozen-source',m['source_commit']);git('symbolic-ref','HEAD','refs/heads/frozen-source')
paths=[name for name,v in m['files'].items() if v['git_blob'] is not None]
git('sparse-checkout','set','--no-cone','--stdin',input=('\\n'.join('/'+name for name in paths)+'\\n').encode())
git('checkout','-q','--detach',m['source_commit'])
assert git('rev-parse','HEAD').stdout.decode().strip()==m['source_commit']
for name,data in files.items():
 path=r/name;assert path.resolve().is_relative_to(r)
 if path.exists():assert path.read_bytes()==data,name
 else:
  assert name not in paths,'Git failed to materialize a declared execution file: '+name
  path.parent.mkdir(parents=True,exist_ok=True)
  with path.open('xb') as f:f.write(data)
 path.chmod(0o400)
assert not git('status','--porcelain','--','src/aegis_dc','src/patrol_rsi/contracts.py').stdout.strip()
print(json.dumps({'source_commit':m['source_commit'],'phase':m['phase'],'staged_files':len(m['files']),'staged_bytes':sum(v['bytes'] for v in m['files'].values()),'source_pack_bytes':len(files['source-objects.pack']),'manifest_sha256':hashlib.sha256(files['manifest.json']).hexdigest(),'actual_git_head_verified':True}))
'''
cmd=['ssh.exe','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','renly@219.143.38.36','bash -lc '+shlex.quote('/share/home/renly/miniconda3/bin/python -c '+shlex.quote(program))]
result=subprocess.run(cmd,input=payload,capture_output=True)
with (out/'stage.log').open('xb') as f:f.write(result.stdout);f.write(result.stderr)
print(result.stdout.decode('utf-8','replace'),end='');print(result.stderr.decode('utf-8','replace'),end='');result.check_returncode()
submit=f'''sinfo -o '%P|%a|%l|%D|%t|%N|%G'
squeue -u renly -o '%.18i|%.9P|%.24j|%.8T|%.10M|%.10l|%.6D|%R'
cd {remote}
test ! -e job-id.txt
job_id=$(sbatch --parsable job.slurm)
printf '%s\\n' "$job_id" > job-id.txt
scontrol show job "$job_id" -o
'''
(out/'submit.sh').write_text(submit,encoding='utf-8',newline='\n')
