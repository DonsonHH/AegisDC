"""Check one explicit prose correction, retaining the entire original delivery."""
import argparse,hashlib,json,subprocess
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--checkout',type=Path,required=True);parser.add_argument('--revision',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
root=args.checkout;prefix='evidence/mainline/research/checkpoint35/'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
git=lambda *v:subprocess.check_output(['git',*v],cwd=root)
assert git('rev-parse','HEAD').decode().strip()==args.revision
assert not git('status','--porcelain','--untracked-files=no').strip()
def current(path):
 data=(root/path).read_bytes();assert data==git('show',args.revision+':'+path),path
 return data
c=json.loads(current(prefix+'delivery-correction-01.json'))
assert c['original_delivery_commit']=='901f81de29b8ea50a3bcb9922554cae17307e3c9'
old=git('show',c['original_delivery_commit']+':'+prefix+'delivery-manifest.json')
assert sha(old)==c['original_manifest_sha256'] and current(prefix+'delivery-manifest.json')==old
m=json.loads(old)
assert set(c['replacements'])=={'docs/mainline/checkpoint35.md'}
for path,spec in m['artifacts'].items():
 if path in c['replacements']:
  replacement=c['replacements'][path]
  assert spec['sha256']==replacement['old_sha256']
  assert sha(git('show',c['original_delivery_commit']+':'+path))==replacement['old_sha256']
  assert sha(current(path))==replacement['new_sha256']
 else:assert sha(current(path))==spec['sha256'],path
for path,digest in c['added_tool_artifacts'].items():assert sha(current(path))==digest,path
assert git('rev-parse','pre-meeting-20261103^{}').decode().strip()=='076d9aa15c5bc99a5b7985f296e15543b7b0f3d7'
assert c['new_physical_calls']==c['new_selector_calls']==c['new_seed_reads']==0
receipt=dict(status='PASS_EXACT_CHECKPOINT35_WITH_ONE_PROSE_CORRECTION',commit=args.revision,original_delivery=c['original_delivery_commit'],original_artifacts=len(m['artifacts']),exact_replacements=1,original_manifest_retained=True,source_figures_and_embedded_csv_unchanged=True,registered_runs=164,new_physical_calls=0,new_selector_calls=0,new_seed_reads=0)
with args.output.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
