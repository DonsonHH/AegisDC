"""Read-only metadata export of one original current public frame; no project calls."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

if sys.flags.optimize:raise SystemExit('Use normal mode for original source export')
root=Path.cwd();source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
name='evidence/mainline/engineering/39c-development/tools/export_instance_public_seed_20.py'
if Path(__file__).read_bytes()!=subprocess.check_output(['git','show',source+':'+name]):raise SystemExit('Pinned export tool differs')
program='''import base64,hashlib,json,os,pathlib,pwd,subprocess,sys
if sys.flags.optimize:raise SystemExit('Use normal mode for original source inspection')
assert pwd.getpwuid(os.getuid()).pw_name=='renly' and os.uname().nodename.split('.')[0]=='mu01' and os.environ['HOME']=='/share/home/renly'
r=pathlib.Path('/share/home/renly/renly-patrol-rsi/mainline/39c-development/21-instance-service-qualification')
path=r/'results/cases/network-healthy/actual-run/run.json';raw=path.read_bytes()
expected={'bytes':636572,'sha256':'767f224bab59ba54729dae65583cb079e74f534a9ffe4f02c5a5c86da89ecf14'}
assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256']
terminal=json.loads((r/'results/terminal.json').read_bytes())
assert terminal['output_files']['cases/network-healthy/actual-run/run.json']==expected
run=json.loads(raw);assert run['code_identity']['git_commit']=='8eeef6b724a130dad12fb21cfe8bf68c46ec47f5' and not run['code_identity']['implementation_has_changes']
selected=next(row for row in run['policy_public_decisions'] if row['frame']['as_of_s']==5.5)
document={'schema':'aegisdc-saved-public-interface-seed-v1','classification':'PUBLIC_AVAILABLE_FRAME_AND_DECLARATIONS_ONLY_NOT_PRIVATE_TRUTH',
 'source':{'job':'133378','code_commit':run['code_identity']['git_commit'],'private_run_identity':expected,'selected_at_s':5.5},
 'frame':selected['frame'],'history':selected['history'],'policy_program':run['inputs']['dispatch_program']['policy_program'],
 'closure_program':run['inputs']['dispatch_program']['closure_program']}
data=(json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False)+chr(10)).encode()
print(json.dumps({'data':base64.b64encode(data).decode(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
 'original_private_run':expected,'exported_keys':sorted(document),'new_project_calls':0,'new_native_runs':0}))
'''
command='/share/home/renly/miniconda3/bin/python -c '+shlex.quote(program)
result=subprocess.run(['ssh.exe','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','renly@219.143.38.36','bash -lc '+shlex.quote(command)],capture_output=True,check=True)
reply=json.loads(result.stdout);data=base64.b64decode(reply.pop('data'))
if len(data)!=reply['bytes'] or hashlib.sha256(data).hexdigest()!=reply['sha256']:raise ValueError('Public seed transport differs')
destination=root/'tests/fixtures/39c-instance-public-seed-20.json'
with destination.open('xb') as stream:stream.write(data)
reply.update(export_tool_commit=source,tool=name,input_path=destination.relative_to(root).as_posix(),
    note='Original private file SHA checked; only selected public fields exported. No plant,selector,metric or project import executed.')
proof=root/'evidence/mainline/engineering/39c-development/public-seed-20';proof.mkdir(exist_ok=False)
with (proof/'export-receipt.json').open('x',encoding='utf-8',newline='\n') as stream:json.dump(reply,stream,indent=2);stream.write('\n')
print(json.dumps(reply))
