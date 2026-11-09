import base64,hashlib,json,pathlib,shlex,subprocess
root=pathlib.Path.cwd();remote='/share/home/renly/renly-patrol-rsi/mainline/39c-development/17-reference-refusal-qualification'
program='''import base64,hashlib,json,pathlib,subprocess
r=pathlib.Path(REMOTE);job=(r/'job-id.txt').read_text().strip();assert job.isdigit()
accounting=subprocess.check_output(['sacct','-j',job,'--format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,AllocCPUS,ReqMem,MaxRSS','-P'])
main=next((line for line in accounting.decode().splitlines() if line.startswith(job+'|')),None)
if main is None or not any(state in main for state in ['|COMPLETED|','|FAILED|','|TIMEOUT|','|OUT_OF_MEMORY|','|CANCELLED|']):print(json.dumps({'state':'NOT_TERMINAL','accounting':accounting.decode()}))
else:
 names={'source-manifest.json':'manifest.json','job.slurm':'job.slurm','slurm-job-id.txt':'job-id.txt','attempt.json':'results/attempt.json','terminal.json':'results/terminal.json','test.log':'results/test.log','stdout.log':'slice-'+job+'.out','stderr.log':'slice-'+job+'.err'}
 files={name:(r/path).read_bytes() for name,path in names.items() if (r/path).is_file()};files['slurm-accounting.txt']=accounting
 terminal=json.loads(files['terminal.json']);private={}
 for name,record in terminal['output_files'].items():
  path=r/'results'/name;assert path.resolve().is_relative_to(r/'results') and not path.is_symlink()
  data=path.read_bytes();assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256'],name
  if name.endswith('/frozen-call-input.json') or '/unexpected-actual-run/' in name:private[name]=record
  elif name not in files:files[name.replace('/','--')]=data
 files['private-raw-index.json']=(json.dumps({'classification':'FULL_INVALID_INPUTS_AND_ANY_UNEXPECTED_NATIVE_STAY_PRIVATE','remote_root':str(r/'results'),'files':private},indent=2)+chr(10)).encode()
 print(json.dumps({'state':'TERMINAL','files':{name:{'data':base64.b64encode(data).decode('ascii'),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()}}))
'''.replace('Path(REMOTE)','Path('+repr(remote)+')')
command='/share/home/renly/miniconda3/bin/python -c '+shlex.quote(program)
reply=subprocess.run(['ssh.exe','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','renly@219.143.38.36','bash -lc '+shlex.quote(command)],capture_output=True,check=True)
response=json.loads(reply.stdout)
if response['state']!='TERMINAL':print(json.dumps(response));raise SystemExit(0)
files={name:base64.b64decode(record['data']) for name,record in response['files'].items()}
for name,data in files.items():assert len(data)==response['files'][name]['bytes'] and hashlib.sha256(data).hexdigest()==response['files'][name]['sha256']
assert files['source-manifest.json']==(root/'.work/39c-reference14-remote/qualification/manifest.json').read_bytes()
terminal=json.loads(files['terminal.json'])
for name,record in terminal['output_files'].items():
 local=name.replace('/','--')
 if local in files:assert len(files[local])==record['bytes'] and hashlib.sha256(files[local]).hexdigest()==record['sha256']
dest=root/'evidence/mainline/engineering/39c-development/slice-14/17-reference-refusal-qualification';dest.mkdir(parents=True,exist_ok=False)
for name,data in files.items():
 with (dest/name).open('xb') as stream:stream.write(data)
print(json.dumps({key:value for key,value in terminal.items() if key not in {'output_files','traceback'}}));print(files['test.log'].decode());print(files.get('rejections-summary.json',b'').decode())
