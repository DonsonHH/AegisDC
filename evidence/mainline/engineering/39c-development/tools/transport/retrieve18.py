"""Retrieve small original receipts; native trajectories and full inputs stay private."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

if sys.flags.optimize:raise SystemExit('Use normal mode for immutable retrieval')
root=Path.cwd()
attempt='21-instance-service-qualification'
remote='/share/home/renly/renly-patrol-rsi/mainline/39c-development/'+attempt
program='''import base64,hashlib,json,pathlib,subprocess,sys
if sys.flags.optimize:raise SystemExit('Use normal mode for source identity inspection')
r=pathlib.Path(REMOTE)
job=(r/'job-id.txt').read_text().strip();assert job.isdigit()
accounting=subprocess.check_output(['sacct','-j',job,'--format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,AllocCPUS,ReqMem,MaxRSS','-P'])
main=next((line for line in accounting.decode().splitlines() if line.startswith(job+'|')),None)
if main is None or not any(state in main for state in ['|COMPLETED|','|FAILED|','|TIMEOUT|','|OUT_OF_MEMORY|','|CANCELLED|']):
 print(json.dumps({'state':'NOT_TERMINAL','accounting':accounting.decode()}))
else:
 names={'source-manifest.json':'manifest.json','job.slurm':'job.slurm','slurm-job-id.txt':'job-id.txt','attempt.json':'results/attempt.json','terminal.json':'results/terminal.json','test.log':'results/test.log','stdout.log':'slice-'+job+'.out','stderr.log':'slice-'+job+'.err'}
 files={name:(r/path).read_bytes() for name,path in names.items() if (r/path).is_file()}
 files['slurm-accounting.txt']=accounting
 terminal=json.loads(files['terminal.json']);manifest=json.loads(files['source-manifest.json']);raw={}
 for name,record in terminal.get('output_files',{}).items():
  if '/actual-run/' in name or name.endswith('/frozen-call-input.json'):raw[name]=record
  elif name.endswith(('/business-result.json','/actual-instance-summary.json')):
   path=r/'results'/name;assert path.resolve().is_relative_to(r/'results') and not path.is_symlink()
   data=path.read_bytes();assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
   files[name.replace('/','--')]=data
 if raw:files['private-raw-index.json']=(json.dumps({'classification':'PRIVATE_NATIVE_TRAJECTORIES_AND_FULL_INPUTS_REMAIN_REMOTE','remote_root':str(r/'results'),'files':raw},indent=2)+chr(10)).encode()
 paths={case:'cases/'+case+'/frozen-call-input.json' for case in ['network-healthy','network-still-blocked']}
 if all(path in raw for path in paths.values()):
  inputs={}
  for case,name in paths.items():
   path=r/'results'/name;data=path.read_bytes();record=raw[name]
   assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
   inputs[case]=json.loads(data)
  assert raw[paths['network-still-blocked']]==manifest['expected_case_call_inputs']['network-still-blocked']
  original=inputs['network-still-blocked'];healthy=inputs['network-healthy']
  parameter=next(row for row in original['model']['parameters'] if row['id']=='network_service_capacity')
  assert parameter['value']==.25
  parameter['value']=1
  assert original==healthy,'The actual case inputs differ beyond declared network capacity'
  identity={'classification':'ACTUAL_FULL_INPUT_IDENTITY_ONLY_NO_ENDPOINT_RECOMPUTATION','original_job':job,'source_commit':manifest['source_commit'],
   'cases':{case:raw[name] for case,name in paths.items()},'only_parameter_difference':'network_service_capacity0.25_to1',
   'all_other_actual_input_fields_equal':True,'original133377_negative_input_equal':True,'project_calls':0}
  files['case-input-identity.json']=(json.dumps(identity,indent=2)+chr(10)).encode()
 if terminal['status']=='QUALIFICATION_BEHAVIORS_PASSED':assert 'case-input-identity.json' in files
 print(json.dumps({'state':'TERMINAL','files':{name:{'data':base64.b64encode(data).decode('ascii'),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()}}))
'''.replace('Path(REMOTE)','Path('+repr(remote)+')')
command='/share/home/renly/miniconda3/bin/python -c '+shlex.quote(program)
reply=subprocess.run(['ssh.exe','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','renly@219.143.38.36','bash -lc '+shlex.quote(command)],capture_output=True,check=True)
reply=json.loads(reply.stdout)
if reply['state']!='TERMINAL':print(json.dumps(reply));raise SystemExit(0)
files={name:base64.b64decode(record['data']) for name,record in reply['files'].items()}
for name,data in files.items():
    record=reply['files'][name]
    if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Transport identity differs: '+name)
manifest=json.loads(files['source-manifest.json'])
if files['source-manifest.json']!=(root/'.work/39c-instance18-remote/qualification/manifest.json').read_bytes():raise ValueError('Original stage manifest differs')
terminal=json.loads(files['terminal.json'])
for name,data in files.items():
    original=name.replace('--','/')
    if original in terminal['output_files']:
        record=terminal['output_files'][original]
        if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Original terminal bytes differ: '+name)
    if name.endswith('--business-result.json'):
        result=json.loads(data);identity=result['execution_code_identity']
        if identity['git_commit']!=manifest['source_commit'] or identity['implementation_has_changes']:raise ValueError('Actual case runtime differs')
        for path,digest in identity['files'].items():
            if manifest['files'][path]['sha256']!=digest:raise ValueError('Actual runtime file differs: '+path)
destination=root/'evidence/mainline/engineering/39c-development/slice-18'/attempt
destination.mkdir(parents=True,exist_ok=False)
for name,data in files.items():
    with (destination/name).open('xb') as stream:stream.write(data)
print(json.dumps({key:value for key,value in terminal.items() if key not in {'output_files','traceback'}}))
print(files.get('test.log',b'').decode('utf-8','replace'))
print(files['slurm-accounting.txt'].decode())
