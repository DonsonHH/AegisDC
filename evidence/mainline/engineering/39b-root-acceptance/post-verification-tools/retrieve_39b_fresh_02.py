"""Retrieve the one saved-only Slurm attempt, never re-execute it."""
import base64, hashlib, json, subprocess
from pathlib import Path

destination=Path('evidence/mainline/engineering/39b-root-acceptance/fresh-02')
assert not destination.exists(), 'Do not overwrite the original saved verification receipt'
remote=r'''
import base64,hashlib,json,subprocess
from pathlib import Path
root=Path('/share/home/renly/renly-patrol-rsi/mainline/39b-fresh-delivery-02')
job=(root/'job-id.txt').read_text().strip();assert job=='133146'
result=subprocess.check_output(['sacct','-j',job,'-n','-P','--format=JobID,JobName,Partition,State,ExitCode,Elapsed,NodeList,AllocCPUS,MaxRSS'],text=True)
rows=[line.split('|') for line in result.splitlines() if line]
main=next(row for row in rows if row[0]==job)
if main[3] not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL'}:
 print(json.dumps({'waiting':True,'slurm':result}));raise SystemExit(0)
names=['job-id.txt','job.slurm','stage-manifest.json','verify-133146.out','verify-133146.err','output/attempt.json','output/terminal.json']
if (root/'output/verification.json').exists():names.append('output/verification.json')
files={}
for name in names:
 data=(root/name).read_bytes();files[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'base64':base64.b64encode(data).decode()}
print(json.dumps({'waiting':False,'slurm':result,'files':files,'private_root':str(root)}))
'''
result=subprocess.run(['ssh.exe','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','renly@219.143.38.36',"bash -lc '/share/home/renly/miniconda3/bin/python -'"],input=remote.encode(),capture_output=True)
if result.returncode:
 print(result.stderr.decode('utf-8','replace'))
 with Path('.work/39b-action-figures-01/retrieval-remote-error-02.json').open('x',encoding='utf-8') as stream:
  json.dump({'classification':'READONLY_RETRIEVAL_FAILURE_NOT_EXECUTION','returncode':result.returncode,'stdout':result.stdout.decode('utf-8','replace'),'stderr':result.stderr.decode('utf-8','replace')},stream,indent=2)
 raise SystemExit(result.returncode)
reply=json.loads(result.stdout)
if reply['waiting']:
 print(reply['slurm']);raise SystemExit(0)
destination.mkdir()
manifest={}
for name,record in reply['files'].items():
 data=base64.b64decode(record['base64']);assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
 path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb') as stream:stream.write(data)
 manifest[name]={k:v for k,v in record.items() if k!='base64'}
with (destination/'sacct.txt').open('x',encoding='utf-8',newline='\n') as stream:stream.write(reply['slurm'])
manifest['sacct.txt']={'bytes':(destination/'sacct.txt').stat().st_size,'sha256':hashlib.sha256((destination/'sacct.txt').read_bytes()).hexdigest()}
with (destination/'retrieval.json').open('x',encoding='utf-8',newline='\n') as stream:
 json.dump({'classification':'SMALL_SAVED_RECEIPT_RETRIEVAL_NOT_COMPUTATION','private_root':reply['private_root'],'files':manifest,'new_facility_or_model_calls':0},stream,indent=2);stream.write('\n')
print(reply['slurm'])
print((destination/'output/terminal.json').read_text())
if (destination/'output/verification.json').exists():print((destination/'output/verification.json').read_text())
