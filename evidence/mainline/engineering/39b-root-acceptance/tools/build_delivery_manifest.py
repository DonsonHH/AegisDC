"""Freeze the complete staged change set and assert native bytes equal Git blobs."""
from pathlib import Path
import hashlib
import json
import subprocess

root=Path.cwd();base='047fc6615313fe28137a17eaefcb35d714222753'
destination=root/'evidence/mainline/engineering/39b-root-acceptance/delivery-manifest.json'
assert not destination.exists()
rows=subprocess.check_output(['git','diff','--cached','--name-status',base],text=True).splitlines()
assert rows and all(row.split('\t',1)[0] in {'A','M'} for row in rows)
names=sorted(row.split('\t',1)[1] for row in rows)
files={}
for name in names:
 data=(root/name).read_bytes()
 blob=subprocess.check_output(['git','show',':'+name])
 assert data==blob,'Native delivery bytes differ from staged Git blob: '+name
 files[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
manifest={'schema':'aegisdc-39b-declared-delivery-v1','base_commit':base,
 'execution_source':'4f80bb35480bf633a777ab34d30a8573ea0734f0','files':files,
 'classification':'ROOT_ENGINEERING_DATA_AND_SOURCE_PENDING_FRESH_CHECK',
 'scope':'Every committed change since accepted39a base at the frozen delivery commit; only this manifest omits its own self-hash. Includes original failures, separate corrections, reviewer originals and pinned tools.',
 'remote_only':'Detailed native traces and captured source packs remain in the declared private server namespaces and are checked separately by their exact indexes.',
 'excluded':['Runtime caches','Full remote Git object store: source/history identities are verified, not repackaged as an artifact'],
 'new_research_trials':0,'original_registered_research_runs':180}
with destination.open('x',encoding='utf-8',newline='\n') as stream:
 json.dump(manifest,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
print(json.dumps({'declared_files':len(files),'bytes':sum(r['bytes'] for r in files.values()),'manifest_sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}))
