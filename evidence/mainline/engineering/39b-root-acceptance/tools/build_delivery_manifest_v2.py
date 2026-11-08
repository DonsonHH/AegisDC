"""Freeze the strengthened saved-only delivery without replacing the v1 manifest."""
from pathlib import Path
import hashlib
import json
import subprocess

root=Path.cwd();base='047fc6615313fe28137a17eaefcb35d714222753'
destination=root/'evidence/mainline/engineering/39b-root-acceptance/delivery-manifest-v2.json'
assert not destination.exists()
rows=subprocess.check_output(['git','diff','--cached','--name-status',base],text=True).splitlines()
assert rows and all(row.split('\t',1)[0] in {'A','M'} for row in rows)
files={}
for row in rows:
 name=row.split('\t',1)[1];data=(root/name).read_bytes();blob=subprocess.check_output(['git','show',':'+name])
 assert data==blob,'Native delivery bytes differ from staged Git: '+name
 files[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
m={'schema':'aegisdc-39b-declared-delivery-v2','base_commit':base,'execution_source':'4f80bb35480bf633a777ab34d30a8573ea0734f0',
 'original_receipt_commit':'ae101123b7d55c3eeff58c1bfe3df0e63291b53f','files':files,
 'classification':'ROOT_ENGINEERING_AND_STRENGTHENED_SAVED_ONLY_VERIFIER_PENDING_FRESH',
 'scope':'Complete changed set since accepted39a base, excluding only this manifest self-hash; original v1 manifest and all original captured receipts remain unchanged.',
 'non_application_tool_added_after_root':['scripts/verify_39b_delivery.py'],
 'remote_only':'Native trajectories, immutable staged source packs and execution snapshots checked via exact original indexes/source manifests.',
 'excluded':['Runtime caches','Full shared remote Git object store; object identities/history checked rather than copied into public data packet'],
 'root_or_research_reruns_for_this_revision':0,'original_registered_research_runs':180,'new_research_trials':0}
with destination.open('x',encoding='utf-8',newline='\n') as f:json.dump(m,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
print(json.dumps({'declared_files':len(files),'bytes':sum(r['bytes'] for r in files.values()),'manifest_sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}))
