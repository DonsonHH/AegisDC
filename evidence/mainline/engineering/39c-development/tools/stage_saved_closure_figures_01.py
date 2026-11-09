"""Stage a small frozen saved-only renderer through strict SSH; no local plotting."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

root=Path.cwd();out=root/'.work/39c-closure-figures-01'
out.mkdir(exist_ok=False)
git=lambda *args:subprocess.check_output(['git',*args])
source=git('rev-parse','HEAD').decode().strip()
protocol_name='docs/mainline/39c-saved-closure-figures-protocol-01.json'
tool='evidence/mainline/engineering/39c-development/tools/stage_saved_closure_figures_01.py'
renderer='scripts/plot_business_closure_endpoints.py'
files={name:git('show',source+':'+name) for name in [protocol_name,tool,renderer]}
assert Path(__file__).read_bytes()==files[tool]
protocol=json.loads(files[protocol_name])
remote='/share/home/renly/renly-patrol-rsi/mainline/39c-development/05-saved-closure-figures-01'
job=f'''#!/usr/bin/env bash
#SBATCH --job-name=aegis39c-saved-figures
#SBATCH --partition=cu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --no-requeue
#SBATCH --output={remote}/render-%j.out
#SBATCH --error={remote}/render-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
cd {remote}
srun /share/home/renly/miniconda3/envs/diffv2ir/bin/python -B -X utf8 {renderer} --manifest manifest.json --source-commit {source} --output figures
'''
records={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                  git_blob=git('rev-parse',source+':'+name).decode().strip(),source_path=name)
         for name,data in files.items()}
files['job.slurm']=job.encode();records['job.slurm']=dict(bytes=len(files['job.slurm']),sha256=hashlib.sha256(files['job.slurm']).hexdigest())
manifest=dict(classification='SAVED_ONLY_RENDER_TOOL_SNAPSHOT_NOT_APPLICATION_CHECKOUT',source_commit=source,
              protocol=protocol_name,renderer=records[renderer],inputs=protocol['inputs'],files=records,
              runtime_cache_excluded=['runtime-matplotlib-cache','__pycache__','*.pyc','*.pyo'],
              facility_calls=0,public_choice_calls=0,model_calls=0,new_research_trials=0)
files['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
(out/'manifest.json').write_bytes(files['manifest.json'])
payload=json.dumps({'destination':remote,'files':{name:base64.b64encode(data).decode() for name,data in files.items()}}).encode()
program='''import base64,hashlib,json,os,pathlib,pwd,subprocess,sys
assert pwd.getpwuid(os.getuid()).pw_name=='renly' and os.uname().nodename.split('.')[0]=='mu01' and os.environ['HOME']=='/share/home/renly'
subprocess.run(['sinfo','-o','%P|%a|%l|%D|%t|%N|%G'],check=True)
subprocess.run(['squeue','-u','renly','-o','%.18i|%.9P|%.24j|%.8T|%.10M|%.10l|%.6D|%R'],check=True)
p=json.load(sys.stdin);root=pathlib.Path(p['destination'])
assert root.parent.as_posix()=='/share/home/renly/renly-patrol-rsi/mainline/39c-development' and root.name=='05-saved-closure-figures-01'
files={name:base64.b64decode(data) for name,data in p['files'].items()};m=json.loads(files['manifest.json'])
for name,record in m['files'].items():
 data=files[name];assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
for record in m['inputs']:
 path=pathlib.Path(record['path']);assert path.resolve().is_relative_to(root.parent.resolve())
 assert path.stat().st_size==record['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
root.mkdir(mode=0o700,exist_ok=False)
for name,data in files.items():
 path=root/name;assert path.resolve().is_relative_to(root)
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb') as stream:stream.write(data)
 path.chmod(0o400)
print(json.dumps({'source_commit':m['source_commit'],'saved_input_files':len(m['inputs']),'staged_source_files':len(m['files']),'staged_bytes':sum(len(data) for data in files.values()),'manifest_sha256':hashlib.sha256(files['manifest.json']).hexdigest(),'project_or_facility_or_model_execution':0}))
'''
command='/share/home/renly/miniconda3/bin/python -c '+shlex.quote(program)
result=subprocess.run(['ssh.exe','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','renly@219.143.38.36','bash -lc '+shlex.quote(command)],input=payload,capture_output=True)
with (out/'stage.log').open('xb') as stream:stream.write(result.stdout);stream.write(result.stderr)
print(result.stdout.decode('utf-8','replace'));print(result.stderr.decode('utf-8','replace'));result.check_returncode()
submit=f'''sinfo -o '%P|%a|%l|%D|%t|%N|%G'
squeue -u renly -o '%.18i|%.9P|%.24j|%.8T|%.10M|%.10l|%.6D|%R'
cd {remote}
test ! -e job-id.txt
test ! -e figures
sbatch --parsable job.slurm > job-id.txt
cat job-id.txt
'''
(out/'submit.sh').write_text(submit,encoding='utf-8',newline='\n')
