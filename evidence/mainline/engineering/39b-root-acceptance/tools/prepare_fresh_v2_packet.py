"""Preserve the original fresh-tool reviews and classify one legacy saved receipt."""
from pathlib import Path
import hashlib
import json
import subprocess

root=Path.cwd();packet=root/'evidence/mainline/engineering/39b-root-acceptance'
dest=packet/'reviews/fresh-verifier-v1';dest.mkdir(exist_ok=False)
records={}
for category,folder in [('spec','.work/39b-fresh-verifier-spec-01'),('standards','.work/39b-fresh-verifier-standards-01')]:
 for p in sorted((root/folder).iterdir()):
  if p.is_file() and p.suffix in {'.md','.json'}:
   target=dest/category/p.name;target.parent.mkdir(exist_ok=True)
   with target.open('xb') as f:f.write(p.read_bytes())
   records[target.relative_to(dest).as_posix()]={'original':p.relative_to(root).as_posix(),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
with (dest/'originals-manifest.json').open('x',encoding='utf-8',newline='\n') as f:
 json.dump({'classification':'ORIGINAL_INDEPENDENT_FRESH_TOOL_REVIEW_NO_EXECUTION','candidate':'ae101123b7d55c3eeff58c1bfe3df0e63291b53f','files':records,'disposition':'Spec fixed-data reviewPASS, Standards3P2 captured; no fresh attempt executed and no root/research rerun.'},f,indent=2);f.write('\n')
correction=packet/'metadata-corrections';correction.mkdir(exist_ok=False)
name='evidence/mainline/engineering/39b-development/slice-08/saved-correction-01/source-manifest.json'
raw=(root/name).read_bytes();attempt=json.loads((root/name).with_name('attempt.json').read_text(encoding='utf-8'))
assert 'manifest_sha256' not in attempt and attempt['facility_calls']==attempt['direct_public_choice_calls']==attempt['model_calls']==0
with (correction/'saved08-manifest-binding.json').open('x',encoding='utf-8',newline='\n') as f:
 json.dump({'classification':'EXACT_LEGACY_SAVED_ONLY_METADATA_CORRECTION_NOT_HASH_WAIVER','original_commit':'ae101123b7d55c3eeff58c1bfe3df0e63291b53f','path':name,'original_manifest_sha256':hashlib.sha256(raw).hexdigest(),'original_manifest_git_blob':subprocess.check_output(['git','rev-parse','ae101123b7d55c3eeff58c1bfe3df0e63291b53f:'+name],text=True).strip(),'omission':'Original saved-only attempt did not persist manifest_sha256; reused staging class says visualization although executed tool was saved-assertion checking.','binding':'No original rewritten. The one path must match its exact reviewed original Git blob, zero-call attempt, terminal outputs and captured tool/input Git identities. All actual facility captures still require the original pre-work manifest hash.','new_execution_calls':0},f,indent=2);f.write('\n')
p=root/'docs/mainline/progress.json';v=json.loads(p.read_text(encoding='utf-8'));v['development_39b'].update(fresh_delivery={'status':'V1_NOT_RUN_SUPERSEDED_BY_V2_AFTER_STATIC_REVIEW','original_delivery':'ae101123b7d55c3eeff58c1bfe3df0e63291b53f','maximum_execution_attempts':1,'attempts':0,'original_tool_findings':3,'protocol':'docs/mainline/39b-fresh-delivery-protocol-02.json'},open_review_finding='Fresh verifier3P2 being closed before its first execution: current source binding, complete original index binding, explicit20/root01 gates. Root02 actual609PASS and all native originals unchanged.')
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
p=root/'docs/mainline/evidence/39b-candidate.json';v=json.loads(p.read_text(encoding='utf-8'));v['fresh_protocol']='docs/mainline/39b-fresh-delivery-protocol-02.json';v['original_receipt_commit']='ae101123b7d55c3eeff58c1bfe3df0e63291b53f';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Preserved both original verifier reviews; no root/data/attempt original was rewritten.')
