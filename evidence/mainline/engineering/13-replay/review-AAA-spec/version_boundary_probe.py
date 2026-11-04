"""Copy-only terminal version probe; no original edit or plant execution."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
repo=Path('C:/Users/Donson/Documents/ChatGPT/Renly/.work/worktrees/full-site-13')
freeze='aaa4d8cba3738e47e700c2134000a72bd2390cc0'
names=['src/aegis_dc/replay.py','src/patrol_rsi/contracts.py']
def guard():
 result={name:sha256((repo/name).read_bytes()).hexdigest() for name in names}
 assert all(result[name]==sha256(subprocess.check_output(['git','cat-file','blob',freeze+':'+name],cwd=repo)).hexdigest() for name in names)
 return result
before=guard()
sys.path.insert(0,str(repo/'src'))
from aegis_dc.replay import read_attempt
origin=repo/'evidence/mainline/engineering/13-replay/capture-02/causal-baseline'
origin_sha=sha256((origin/'attempt.json').read_bytes()).hexdigest()
observed=[]
with tempfile.TemporaryDirectory(prefix='aegisdc13-version-probe-') as temporary:
 for mutation in ('terminal_schema','declaration_schema','terminal_status'):
  folder=Path(temporary)/mutation;shutil.copytree(origin,folder)
  path=folder/'attempt.json';record=json.loads(path.read_text(encoding='utf-8'))
  if mutation=='terminal_schema':record['schema']='aegisdc-facility-attempt-v999'
  elif mutation=='declaration_schema':
   declaration_path=folder/'declaration.json';d=json.loads(declaration_path.read_text(encoding='utf-8'))
   d['schema']='aegisdc-attempt-declaration-v999'
   declaration_path.write_text(json.dumps(d,indent=2,allow_nan=False),encoding='utf-8')
   record['artifacts']['declaration.json']=sha256(declaration_path.read_bytes()).hexdigest()
  else:
   record['status']='UNRECOGNIZED_TERMINAL_STATE'
   life=folder/'lifecycle.jsonl';rows=[json.loads(row) for row in life.read_text(encoding='utf-8').splitlines()]
   rows[-1]['state']=record['status']
   life.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows),encoding='utf-8')
   record['artifacts']['lifecycle.jsonl']=sha256(life.read_bytes()).hexdigest()
  path.write_text(json.dumps(record,indent=2,allow_nan=False),encoding='utf-8')
  try:
   result=read_attempt(folder)
   outcome={'mutation':mutation,'outcome':'ACCEPTED','returned_status':result['record']['status'],
     'reader_returned_trajectory':result['run'] is not None,'mutated_record_schema':record['schema']}
  except Exception as error:
   outcome={'mutation':mutation,'outcome':'REFUSED','type':type(error).__name__,'message':str(error)}
  observed.append(outcome)
after=guard();assert after==before
assert sha256((origin/'attempt.json').read_bytes()).hexdigest()==origin_sha
report={'classification':'COPY_ONLY_FORMAT_BOUNDARY_PROBE_NO_PLANT_EXECUTION',
 'source_pin':freeze,'source_guard_before':before,'source_guard_after':after,
 'origin':str(origin),'origin_attempt_sha256_preserved':origin_sha,
 'method':'Each mutation starts from a separate copy; declaration/lifecycle artifact SHA is updated only in the copy so the probe isolates missing version/state validation. Originals are never changed.',
 'expected':'Unknown terminal/declaration versions and unknown finalized states should be rejected before interpretation/replay.',
 'observed':observed,'new_simulations':0,'full_regression_run':False,
 'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}
output=Path('C:/Users/Donson/AppData/Local/Temp/aegisdc-review-13-spec-attachments/version-boundary-red-01.json')
with output.open('x',encoding='utf-8') as f:f.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({'observed':observed,'receipt':str(output),'sha256':sha256(output.read_bytes()).hexdigest()}))
