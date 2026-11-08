"""Author small acceptance metadata from already captured, verified receipts only."""
from pathlib import Path
import hashlib,json,shutil,subprocess

root=Path.cwd();packet=Path('evidence/mainline/engineering/39b-root-acceptance')
delivery='dfa7ab521bdfa4e7f06554c836a16417759eab26'
execution='4f80bb35480bf633a777ab34d30a8573ea0734f0'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==delivery
v=json.loads((packet/'fresh-02/output/verification.json').read_text())
assert v['status']=='PASS' and v['delivery_commit']==delivery and v['execution_source']==execution
assert v['declared_files']==406 and v['verified_original_files']==20 and v['root_tests']['executed']==609
assert all(v['root_tests'][x]==0 for x in ['failures','errors','skipped'])
assert '133146|aegis39b-fresh|cu|COMPLETED|0:0|' in (packet/'fresh-02/sacct.txt').read_text()
assert not subprocess.check_output(['git','diff','--name-only','047fc6615313fe28137a17eaefcb35d714222753','HEAD','--','configs','evidence/mainline/research','paper/mainline-report-20261108']).strip()

def write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8',newline='\n') as stream:
  json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
def record(path):
 p=Path(path);return {'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

review_files={}
for axis in ['spec','standards']:
 source=Path('.work/39b-fresh-verifier-'+axis+'-correction-01')
 target=packet/'reviews/fresh-verifier-v2'/axis;target.mkdir(parents=True)
 for name in ['report.md','source-pin.json']:
  destination=target/name;assert not destination.exists();shutil.copyfile(source/name,destination)
  review_files[destination.as_posix()]=record(destination)
write(packet/'reviews/fresh-verifier-v2/originals-manifest.json',{'classification':'ORIGINAL_INDEPENDENT_STATIC_CLOSURE_RECORDS','source':delivery,'axes':['Spec','Standards'],'files':review_files,'project_or_verifier_calls':0})

transport=packet/'fresh-02/input-transport';transport.mkdir()
for name in ['stage-fresh-delivery-02.log','stage-fresh-delivery-02-resume-01.log','inspect-stage-02.log','stop-stalled-stage-fetch-02.log','stage-fresh-delivery-02-bundle-01.log','submit-fresh-delivery-02.log']:
 source=Path('.work/39b-action-figures-01')/name
 if source.is_file():shutil.copyfile(source,transport/name)
write(transport/'classification.json',{'classification':'INPUT_STAGING_TRANSPORT_RECORDS_NOT_VERIFICATION_EXECUTIONS','original_git_failure':'Empty reply from server before checkout','stalled_fetch':'Own input-only fetch PID1374849 stopped after verifying user/cwd/exact arguments; no Slurm cancellation','recovery':'40001-byte Git delta bundle via strict-host-key SSH, same exact candidate, SHA256 and Git prerequisite verified','bundle_sha256':'1217970181810fd237ac937a9eab207bb0c7780d76ba1ef9b78e3e58fa23bf56','fresh_executions':1,'job':'133146','root_or_physics_or_research_repeats':0})

proof={'schema':'aegisdc-fresh-git-delivery-proof-v1','ticket':'39b','status':'PASS','classification':'SAVED_REMOTE_INTEGRITY_NOT_NEW_RESEARCH','delivery_commit':delivery,'execution_source':execution,'protocol':'docs/mainline/39b-fresh-delivery-protocol-02.json','manifest':(packet/'delivery-manifest-v2.json').as_posix(),'manifest_sha256':record(packet/'delivery-manifest-v2.json')['sha256'],'slurm':{'job_id':'133146','state':'COMPLETED','exit_code':'0:0','node':'cu18','elapsed_s':3,'partition':'cu','cpus':1},'receipt':(packet/'fresh-02/output/verification.json').as_posix(),'receipt_sha256':record(packet/'fresh-02/output/verification.json')['sha256'],'declared_files':v['declared_files'],'source_file_checks':v['recorded_source_file_checks'],'current_execution_files':v['current_execution_files'],'original_receipt_files':v['original_receipt_files'],'private_staging_inputs':v['private_staging_inputs'],'private_native_files':v['private_native_files'],'original_historical_files':20,'fresh_attempts':1,'maximum_fresh_attempts':1,'unrun_v1_preserved':True,'root_tests':v['root_tests'],'original_failures_preserved':True,'facility_calls':0,'direct_public_choice_calls':0,'model_calls':0,'new_research_trials':0}
write('docs/mainline/evidence/39b-delivery.json',proof)
acceptance={'schema':'aegisdc-mainline-ticket-acceptance-v1','ticket':'39b','date':'2026-11-09','status':'ACCEPTED_FINITE_SYNTHETIC_ENGINEERING_SCOPE','body_source':'2dece5e87c5b96e8381b75ebb8b6f9d14e65b3c4','integrated_root_execution_source':execution,'delivery_commit':delivery,'report':'docs/mainline/39b-root-acceptance.md','data_figures':'evidence/mainline/engineering/39b-development/slice-05/figures-02','root':{'job':'133145','state':'COMPLETED','exit_code':'0:0','tests_run':609,'executed':609,'failures':0,'errors':0,'skips':0,'historical_originals':20,'source_guard':'PASS_BEFORE_AND_AFTER','original_failed_job':'133143','original_failure_retained':True},'fresh_proof':'docs/mainline/evidence/39b-delivery.json','independent_review':{'body':'evidence/mainline/engineering/39b-development/reviews-01','root_gates':(packet/'reviews').as_posix(),'saved_verifier_closure':(packet/'reviews/fresh-verifier-v2').as_posix(),'axes':['Spec','Standards'],'unresolved_blocking_findings':0,'original_findings_and_failed_attempts_preserved':True},'scope':['Arrived public evidence creates stable problem/task identities across cooling,power,IT; static shared-service context is not a capacity or probability model.','Real professional checks, qualified named action, residual effect and later paid recheck; conditional/direct/defer/no-human cases.','Copied/late evidence, hidden-state privacy, shared-tool competition, expired authority and contradictory/asynchronous public receipts.','Action/recheck does not automatically close risk; business truth/opportunity/verified closure endpoints belong to39c.'],'development_counts':{'facility_interface_calls':17,'completed_native_horizons':13,'returned_decisions':43,'direct_public_choice_calls':6,'internal_choice_calls':'NOT_INSTRUMENTED','root_regressions_separate':2,'saved_fresh_executions_separate':1,'registered_research_runs_unchanged':180,'new_registered_research_runs':0},'preserved_failures':['slice02 input failure133111','slice08 native horizon completed but test assertion failed133138; saved correction133139 kept separately','first root regression133143 failed1/609','original independent findings and first plot-layout failures','input GitHub failure and stopped stalled transfer; no new compute attempt'],'unchanged':{'original180_and_NO_PRACTICAL_GAIN':True,'field_calibration':'PENDING','AI_effect':'NOT_MEASURED','RSI_effect':'NOT_MEASURED','remaining_six_unmodeled_risk_classes':'NOT_UPGRADED','old_protocols_reports_and_source_identities':True},'next_primary_ticket':'39c','original39_comparison':'UNRUN_REQUIRES39b39c39d_AND_NEW_FROZEN_PROTOCOL','overall_goal':'INCOMPLETE'}
write('docs/mainline/evidence/39b-root.json',acceptance)

p=Path('docs/mainline/progress.json');a=json.loads(p.read_text(encoding='utf-8'))
a['current_ticket']='39c';a['active_implementations']=[]
a['liveness_refresh']='2026-11-09 root39b accepted after remote609/609 and unique fresh133146 PASS. Two local worktrees retained; no duplicate implementation.39c is earliest ready frontier, not yet implemented.'
a['research_execution_status']='original180_preserved_39a39b_accepted_39c_next_before39d_and39'
b=a['development_39b'];b['status']='ACCEPTED_FINITE_SYNTHETIC_ENGINEERING_SCOPE';b['acceptance']='docs/mainline/evidence/39b-root.json';b['open_review_finding']='NONE_UNRESOLVED; all original findings and corrections retained'
b['fresh_delivery'].update(status='PASS',attempts=1,delivery_commit=delivery,job='133146',declared_files=406,source_file_checks=2208,private_native_files=52,proof='docs/mainline/evidence/39b-delivery.json')
a['next_phase_plan']['status']='39A_39B_ACCEPTED_39C_NEXT_39D_BLOCKED_BEFORE_ORIGINAL39'
p.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

p=Path('.scratch/full-facility-mainline/issues/39b-multisystem-questions-and-tasks.md');s=p.read_text(encoding='utf-8')
s=s.replace('**Status:** claimed','**Status:** resolved').replace('- [ ]','- [x]')
s=s.replace('## Evidence\n','## Evidence\n\n2026-11-09 **accepted finite engineering scope**. Authority: `docs/mainline/evidence/39b-root.json`; actual root source4f80bb35 / Slurm133145 executed609/609 with0failure/error/skip and20historical originals. Fresh candidate dfa7ab52 / Slurm133146 verified406files,2208source identities,52private native files, allPASS. Both independent axes and exact original failures retained. [Readable acceptance](../../../docs/mainline/39b-root-acceptance.md) includes three actual data/architecture figures.39c is next; original180 and all scientific conclusions unchanged.\n\nThe following development notes are preserved snapshots before final acceptance.\n',1)
p.write_text(s,encoding='utf-8',newline='\n')
