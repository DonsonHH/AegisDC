import argparse,base64,hashlib,json,pathlib,shlex,subprocess

p=argparse.ArgumentParser();p.add_argument('phase',choices=['red','green']);a=p.parse_args()
root=pathlib.Path.cwd();attempt='13-unmodeled-reference-'+a.phase
remote='/share/home/renly/renly-patrol-rsi/mainline/39c-development/'+attempt
program='''import base64,hashlib,json,pathlib,subprocess
r=pathlib.Path(REMOTE)
job=(r/'job-id.txt').read_text().strip();assert job.isdigit()
accounting=subprocess.check_output(['sacct','-j',job,'--format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,AllocCPUS,ReqMem,MaxRSS','-P'])
rows=accounting.decode().splitlines()
main=next((x for x in rows if x.startswith(job+'|')),None)
if main is None or not any(t in main for t in ['|COMPLETED|','|FAILED|','|TIMEOUT|','|OUT_OF_MEMORY|','|CANCELLED|']):
 print(json.dumps({'state':'NOT_TERMINAL','accounting':accounting.decode()}))
else:
 names={'source-manifest.json':'manifest.json','job.slurm':'job.slurm','slurm-job-id.txt':'job-id.txt','attempt.json':'results/attempt.json','terminal.json':'results/terminal.json','business-result.json':'results/business-result.json','test.log':'results/test.log','stdout.log':'slice-'+job+'.out','stderr.log':'slice-'+job+'.err'}
 files={k:(r/v).read_bytes() for k,v in names.items() if (r/v).is_file()};files['slurm-accounting.txt']=accounting
 terminal=json.loads(files['terminal.json'])
 raw={name:v for name,v in terminal.get('output_files',{}).items() if name.startswith('actual-run/') or name=='frozen-call-input.json'}
 if raw:files['private-raw-index.json']=(json.dumps({'classification':'PRIVATE_NATIVE_TRAJECTORIES_REMAIN_REMOTE','remote_root':str(r/'results'),'files':raw},indent=2)+chr(10)).encode()
 print(json.dumps({'state':'TERMINAL','files':{name:{'data':base64.b64encode(data).decode('ascii'),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()}}))
'''.replace('Path(REMOTE)', 'Path('+repr(remote)+')')
command='/share/home/renly/miniconda3/bin/python -c '+shlex.quote(program)
cmd=['ssh.exe','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','renly@219.143.38.36','bash -lc '+shlex.quote(command)]
result=subprocess.run(cmd,capture_output=True)
if result.returncode: print(result.stderr.decode('utf-8','replace'))
if result.returncode:raise SystemExit(result.stderr.decode('utf-8','replace'))
reply=json.loads(result.stdout)
if reply['state']!='TERMINAL':print(json.dumps(reply));raise SystemExit(0)
files={name:base64.b64decode(v['data']) for name,v in reply['files'].items()}
for name,data in files.items():assert len(data)==reply['files'][name]['bytes'] and hashlib.sha256(data).hexdigest()==reply['files'][name]['sha256']
assert files['source-manifest.json']==(root/'.work/39c-opportunity10-remote'/a.phase/'manifest.json').read_bytes()
terminal=json.loads(files['terminal.json'])
if 'actual-run-summary.json' in files:
 summary=json.loads(files['actual-run-summary.json']);expected=json.loads(files['source-manifest.json'])['source_commit']
 assert summary['code_identity']['git_commit']==expected and summary['code_identity']['implementation_has_changes'] is False
if 'business-result.json' in files:
 business=json.loads(files['business-result.json']);manifest=json.loads(files['source-manifest.json'])
 assert business['execution_code_identity']['git_commit']==manifest['source_commit'] and business['execution_code_identity']['implementation_has_changes'] is False
 for name,value in business['execution_code_identity']['files'].items():assert manifest['files'][name]['sha256']==value
if 'test_log_sha256' in terminal:assert hashlib.sha256(files['test.log']).hexdigest()==terminal['test_log_sha256']
dest=root/'evidence/mainline/engineering/39c-development/slice-10'/attempt
dest.mkdir(parents=True,exist_ok=False)
for name,data in files.items():
 with (dest/name).open('xb') as f:f.write(data)
print(json.dumps({k:v for k,v in terminal.items() if k not in {'output_files','traceback'}},ensure_ascii=False));print(files.get('test.log',b'').decode('utf-8','replace'));print(files['slurm-accounting.txt'].decode())
