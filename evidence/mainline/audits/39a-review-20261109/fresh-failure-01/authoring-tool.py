from pathlib import Path
import hashlib,json,subprocess,sys

root=Path.cwd().resolve()
fresh=(root/'.work/39a-sparse-identity-01').resolve()
if not fresh.is_relative_to(root/'.work') or fresh==root or fresh.exists():
 raise ValueError('Fresh target must be a new, bounded small delivery checkout')
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
manifest_name='docs/mainline/audits/20261109-integrated/delivery-manifest-v2.json'
manifest=json.loads(subprocess.check_output(['git','show',commit+':'+manifest_name]))
names=sorted(set(manifest['artifacts'])|{manifest_name})
events=[]
def run(words,**kwargs):
 result=subprocess.run(words,capture_output=True,**kwargs)
 events.append({'command':words,'exit_code':result.returncode,'stdout':result.stdout.decode('utf-8','replace'),'stderr':result.stderr.decode('utf-8','replace')})
 if result.returncode:raise ValueError(events[-1])
 return result
run(['git','worktree','add','--detach','--no-checkout',str(fresh),commit])
run(['git','-C',str(fresh),'sparse-checkout','set','--no-cone','--stdin'],input=('\n'.join('/'+name for name in names)+'\n').encode())
run(['git','-C',str(fresh),'checkout','--detach',commit])
output=root/'docs/mainline/evidence/39a-delivery.json'
command=[sys.executable,'-B','-X','utf8',str(fresh/'scripts/verify_scope_audit_delivery.py'),'--root',str(fresh),'--commit',commit,'--manifest',manifest_name,'--output',str(output)]
run(command)
proof=json.loads(output.read_text(encoding='utf-8'))
original=(fresh/manifest_name).read_bytes()
try:
 (fresh/manifest_name).write_bytes(b'{}\n')
 refused=subprocess.run([*command[:-1],str(root/'.work/39a-saved-audit-01/negative-unused-output.json')],capture_output=True)
 if refused.returncode==0 or b'Delivery manifest differs from its committed Git blob' not in refused.stderr:
  raise ValueError('Corrupt manifest was not refused by the explicit committed-blob guard')
finally:
 (fresh/manifest_name).write_bytes(original)
negative=root/'evidence/mainline/audits/39a-review-20261109/fresh-manifest-refusal.json'
negative.write_text(json.dumps({'classification':'EXPECTED_INTEGRITY_REFUSAL_NOT_PROJECT_OR_RESEARCH_RUN','delivery_commit':commit,'manifest':manifest_name,'original_sha256':hashlib.sha256(original).hexdigest(),'probe':'Temporarily replace the disposable fresh manifest with an empty object; restore exact original bytes afterward.','exit_code':refused.returncode,'expected_refusal':'Delivery manifest differs from its committed Git blob','stderr':refused.stderr.decode('utf-8','replace'),'original_restored':hashlib.sha256((fresh/manifest_name).read_bytes()).hexdigest()==hashlib.sha256(original).hexdigest(),'project_calls':0,'metric_recomputations':0},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
status=run(['git','-C',str(fresh),'status','--porcelain']).stdout
if status.strip():raise ValueError('Fresh identity checkout gained an unexpected change; retain it for inspection')
materialized=[fresh/name for name in names]
proof['sparse_checkout']={'registered_with_no_checkout_first':True,'declared_files_only':len(names),'materialized_bytes':sum(p.stat().st_size for p in materialized),'clean_before_removal':True,'temporary_directory':str(fresh),'removed_normally':False}
run(['git','worktree','remove',str(fresh)])
proof['sparse_checkout']['removed_normally']=True
proof['expected_corrupt_manifest_refusal']=str(negative.relative_to(root)).replace('\\','/')
output.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
(root/'.work/39a-saved-audit-01/fresh-commands.json').write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(proof,ensure_ascii=False))
