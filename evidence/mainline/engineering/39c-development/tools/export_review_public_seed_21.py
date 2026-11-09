"""Copy one fixed original public call input; no project code is executed."""
import base64,hashlib,json,shlex,subprocess,sys
from pathlib import Path
if sys.flags.optimize:raise SystemExit('Use normal mode for public source transfer')
root=Path.cwd();source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
name='evidence/mainline/engineering/39c-development/tools/export_review_public_seed_21.py'
if Path(__file__).read_bytes()!=subprocess.check_output(['git','show',source+':'+name]):raise SystemExit('Frozen export tool differs')
program='''import base64,hashlib,json,os,pathlib,pwd,sys
if sys.flags.optimize:raise SystemExit('Use normal mode for source inspection')
assert pwd.getpwuid(os.getuid()).pw_name=='renly' and os.uname().nodename.split('.')[0]=='mu01' and os.environ['HOME']=='/share/home/renly'
r=pathlib.Path('/share/home/renly/renly-patrol-rsi/mainline/39c-development/23-public-instance-cross-scope')
raw=(r/'results/frozen-public-call-input.json').read_bytes()
expected={'bytes':78111,'sha256':'4f02ef6b8faf1fbbe0270b2b57bd8ce8e688c2fa5f98939ca3bc7eeebb905237'}
assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256']
terminal=json.loads((r/'results/terminal.json').read_bytes())
assert terminal['source_commit']=='334d2074501b1661c237aa3bce308c388e1b227f' and terminal['output_files']['frozen-public-call-input.json']==expected
document=json.loads(raw);assert set(document)=={'frame','program','history','closure_program'} and document['frame']['as_of_s']==5.5
print(json.dumps({'data':base64.b64encode(raw).decode(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
 'original_job':'133380','original_source_commit':terminal['source_commit'],'public_fields':sorted(document),'new_project_calls':0,'new_native_runs':0}))
'''
command='/share/home/renly/miniconda3/bin/python -c '+shlex.quote(program)
reply=subprocess.run(['ssh.exe','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','renly@219.143.38.36','bash -lc '+shlex.quote(command)],capture_output=True,check=True)
reply=json.loads(reply.stdout);data=base64.b64decode(reply.pop('data'))
if len(data)!=reply['bytes'] or hashlib.sha256(data).hexdigest()!=reply['sha256']:raise ValueError('Original public call transport differs')
path=root/'tests/fixtures/39c-two-instance-public-seed-21.json'
with path.open('xb') as stream:stream.write(data)
proof=root/'evidence/mainline/engineering/39c-development/public-seed-21';proof.mkdir(exist_ok=False)
reply.update(export_tool_commit=source,tool=name,input_path=path.relative_to(root).as_posix(),classification='SOURCE_METADATA_TRANSFER_ONLY_NO_PROJECT_OR_NATIVE_EXECUTION')
with (proof/'export-receipt.json').open('x',encoding='utf-8',newline='\n') as stream:json.dump(reply,stream,indent=2);stream.write('\n')
print(json.dumps(reply))
