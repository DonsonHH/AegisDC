"""Copy observed remote receipts and prepare a declared saved-only delivery."""
from pathlib import Path
import hashlib
import json
import subprocess

root=Path.cwd();returned=root/'.work/39b-root-remote-02/returned'
terminal=json.loads((returned/'terminal.json').read_text(encoding='utf-8'))
assert terminal['status']=='PASS' and terminal['source_commit']=='4f80bb35480bf633a777ab34d30a8573ea0734f0'
t=terminal['tests'];assert t['run']==t['executed']==609 and t['failures']==t['errors']==t['skipped']==0
assert terminal['verified_original_files']==20
packet=root/'evidence/mainline/engineering/39b-root-acceptance'
target=packet/'root';target.mkdir(exist_ok=False)
def copy(source,destination):
 destination.parent.mkdir(parents=True,exist_ok=True)
 with destination.open('xb') as f:f.write(source.read_bytes())
for p in returned.iterdir():
 if p.is_file():copy(p,target/p.name)
legacy=root/'evidence/mainline/engineering/39b-development/slice-09/15-historical-cli-qualification';legacy.mkdir(parents=True,exist_ok=False)
for p in (root/'.work/39b-legacy09-remote-01/returned').iterdir():
 if p.is_file():copy(p,legacy/p.name)
copy(root/'.work/39b-legacy-cli-09-source-pin.json',legacy/'readonly-source-pin.json')
reviews={
 'gates-spec-original':'.work/39b-final-gates-spec-01',
 'gates-standards-original':'.work/39b-final-gates-standards-01',
 'gates-spec-correction':'.work/39b-final-gates-spec-correction-01',
 'gates-standards-correction':'.work/39b-final-gates-standards-correction-01',
 'legacy-spec':'.work/39b-legacy-correction-spec-01',
 'legacy-standards':'.work/39b-legacy-correction-standards-01',
}
review_files={}
for category,folder in reviews.items():
 for p in sorted((root/folder).iterdir()):
  if p.is_file() and p.suffix in {'.json','.md'}:
   dest=packet/'reviews'/category/p.name;copy(p,dest)
   review_files[dest.relative_to(packet).as_posix()]={'original':p.relative_to(root).as_posix(),'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
with (packet/'review-originals-manifest.json').open('x',encoding='utf-8',newline='\n') as f:
 json.dump({'classification':'EXACT_STATIC_ORIGINALS_AND_SEPARATE_CORRECTIONS','files':review_files},f,indent=2);f.write('\n')
setup_names=['full-check-preflight-01.log','full-check-preflight-02.log','full-check-preflight-03.log',
 'verification-environment-01.log','complete-repository-01.log','complete-repository-02.log',
 'stage-root-acceptance-01.log','submit-root-acceptance-01.log','stage-legacy-09.log','stage-submit-root-acceptance-02.log']
for name in setup_names:copy(root/'.work/39b-action-figures-01'/name,packet/'remote-preparation'/name)
copy(root/'.work/verify_39b_delivery.py',root/'scripts/verify_39b_delivery.py')
protocol=dict(schema='aegisdc-fresh-git-saved-delivery-protocol-v1',id='39b-root-fresh-delivery-01',
 classification='SAVED_INTEGRITY_VERIFICATION_NOT_RESEARCH_TRIAL',maximum_attempts=1,
 execution_source=terminal['source_commit'],base_commit='047fc6615313fe28137a17eaefcb35d714222753',
 verifier='scripts/verify_39b_delivery.py',
 dataset='Every committed changed file since the accepted base, excluding only the manifest itself, at one fixed delivery commit. New native trajectories are retained remotely and verified by their declared indexes.',
 required_checks=['Fresh actual HEAD and exact manifest/delivery Git bytes','All declared changed files, no empty or omitted change set','609/609 root tests,0failure/error/skip and20historical originals','Current and historical captured runtime/tool/input Git identities, plus explicitly classified private staging inputs','Remote native byte hashes and complete JSON/JSONL readability','Original root01 and delayed-ACK native failure preserved; saved correction remains separate','Original180/configs/accepted report byte-unchanged'],
 facility_calls=0,direct_public_choice_calls=0,model_calls=0,new_research_trials=0,
 resources=dict(partition='cu',cpus=1,memory_GiB=2,wall_minutes=5,requeue=False),
 durable_outputs=['Attempt/terminal','verification.json','fixed-source/job manifest','Slurm stdout/stderr/accounting'],
 retry_policy='No automatic retry or requeue. Preserve any failure and use a new explicit correction/output before another saved check.',
 excludes=['Python and Matplotlib caches','Private full repository object store: existing source identity and complete history are checked, not copied into the public artifact packet'])
with (root/'docs/mainline/39b-fresh-delivery-protocol-01.json').open('x',encoding='utf-8',newline='\n') as f:
 json.dump(protocol,f,ensure_ascii=False,indent=2);f.write('\n')
authority={'status':'PENDING_FRESH_DELIVERY_NOT_ACCEPTED','ticket':'39b','execution_source':terminal['source_commit'],
 'tests':t,'historical_originals':20,'root_job':'133145','original_root_job':'133143',
 'original_root_failure':'Retained: old36 CLI tested at wrong source; all original CLI assertions/source guards kept',
 'development':'evidence/mainline/engineering/39b-development/README.md','packet':packet.relative_to(root).as_posix(),
 'fresh_protocol':'docs/mainline/39b-fresh-delivery-protocol-01.json','research_trials':180,'new_research_trials':0,
 'field_calibration':'PENDING','AI_RSI_effect':'NOT_MEASURED','overall_goal':'INCOMPLETE'}
with (root/'docs/mainline/evidence/39b-candidate.json').open('x',encoding='utf-8',newline='\n') as f:
 json.dump(authority,f,ensure_ascii=False,indent=2);f.write('\n')
p=root/'docs/mainline/progress.json';v=json.loads(p.read_text(encoding='utf-8'));d=v['development_39b']
d.update(status='ROOT_PASS_PENDING_FRESH_DELIVERY',qualification_attempts=4,qualification_tests=10,
 historical_cli_calls=2,root_regression={'attempts':2,'passed':1,'failed':1,'original_job':'133143','passed_job':'133145',
 'passed_source':terminal['source_commit'],'tests_run':609,'tests_passed':609,'test_failures':0,'test_errors':0,'test_skips':0,
 'originals_verified':20,'source_guard':'PASS','original_root_failed_not_relabelled':True},
 open_review_finding='All recorded finite runtime and startup/test-epoch findings closed separately; root02 actual609/609 passes. Fresh delivery pending.')
v['active_implementations'][0].update(branch='donson/full-facility-mainline',status='root609_pass_waiting_fresh_delivery')
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'execution_source':terminal['source_commit'],'root_tests':t,'review_files':len(review_files),'root_status':'PASS_PENDING_FRESH'}))
