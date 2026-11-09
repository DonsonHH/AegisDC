import argparse,base64,hashlib,json,pathlib,shlex,subprocess
p=argparse.ArgumentParser();p.add_argument('phase',choices=['qualification']);a=p.parse_args()
root=pathlib.Path.cwd();attempt='11-saved-diagnostic-figures'
remote='/share/home/renly/renly-patrol-rsi/mainline/39c-development/'+attempt
program='''import base64,hashlib,json,pathlib,subprocess
r=pathlib.Path(REMOTE);job=(r/'job-id.txt').read_text().strip();assert job.isdigit()
accounting=subprocess.check_output(['sacct','-j',job,'--format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,AllocCPUS,ReqMem,MaxRSS','-P'])
main=next((x for x in accounting.decode().splitlines() if x.startswith(job+'|')),None)
if main is None or not any(t in main for t in ['|COMPLETED|','|FAILED|','|TIMEOUT|','|OUT_OF_MEMORY|','|CANCELLED|']):print(json.dumps({'state':'NOT_TERMINAL','accounting':accounting.decode()}))
else:
 names={'source-manifest.json':'manifest.json','job.slurm':'job.slurm','slurm-job-id.txt':'job-id.txt','attempt.json':'results/attempt.json','terminal.json':'results/terminal.json','test.log':'results/test.log','stdout.log':'slice-'+job+'.out','stderr.log':'slice-'+job+'.err'}
 files={k:(r/v).read_bytes() for k,v in names.items() if (r/v).is_file()};files['slurm-accounting.txt']=accounting
 terminal=json.loads(files['terminal.json'])
 for name,record in terminal['output_files'].items():
  path=r/'results'/name;assert path.resolve().is_relative_to(r/'results') and not path.is_symlink()
  data=path.read_bytes();assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
  files[name]=data
 print(json.dumps({'state':'TERMINAL','files':{name:{'data':base64.b64encode(data).decode('ascii'),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()}}))
'''.replace('Path(REMOTE)','Path('+repr(remote)+')')
command='/share/home/renly/miniconda3/bin/python -c '+shlex.quote(program)
cmd=['ssh.exe','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','renly@219.143.38.36','bash -lc '+shlex.quote(command)]
result=subprocess.run(cmd,capture_output=True,check=True);reply=json.loads(result.stdout)
if reply['state']!='TERMINAL':print(json.dumps(reply));raise SystemExit(0)
files={name:base64.b64decode(record['data']) for name,record in reply['files'].items()}
for name,data in files.items():assert len(data)==reply['files'][name]['bytes'] and hashlib.sha256(data).hexdigest()==reply['files'][name]['sha256']
assert files['source-manifest.json']==(root/'.work/39c-figures08-remote'/a.phase/'manifest.json').read_bytes()
dest=root/'evidence/mainline/engineering/39c-development/figures-02'/attempt;dest.mkdir(parents=True,exist_ok=False)
for name,data in files.items():
 path=dest/name;path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb') as stream:stream.write(data)
terminal=json.loads(files['terminal.json']);print(json.dumps({k:v for k,v in terminal.items() if k not in {'output_files','traceback'}}));print(files.get('test.log',b'').decode());print(accounting.decode()) if False else None
