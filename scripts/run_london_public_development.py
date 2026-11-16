"""One explicitly authorized disclosed-development batch, never confirmation.

This wrapper loads, validates, archives and summarizes. Core policy/plant/scorer
are pinned unchanged to1c0b0c47. No policy loop, scoring formula or retry lives here.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import importlib
import json
import os
from pathlib import Path
import resource
import socket
import sys
import time
import traceback

CORE_REV='1c0b0c47a5742321a3524a5b16843775cc224e3e'
INPUT_SHA='661ed1da1611dde316d6920e3a4e9cc6546ec73e214727e8335bd5a47c663880'
IDS=['C01','C02','C03','C04a','C04b','C05a','C05b','C05c','C06a','C06b','C06c','C07a','C07b','C08a','C08b','C09a','C09b','C10a','C10b']
ARMS=('I','D','P')
VIEW_KEYS={'view_schema','time','pre_open','pending','terminal_failure','phase','records','receipts','history','attempted','known_epoch','certificate','context'}
PRIVATE_KEYS={'condition_id','condition_label','common','tF','tR','next_event','next_private_event','family','ready','exec_fault','approval','commit','verification','guard'}
RESOURCE_NONCOMPLIANCE={'within_budget','external_reservations_clear','reserved_exit_honored'}
CONSTRAINTS={'full_window','trace_chronological','service_and_power_bounds','frozen_input_matches','reported_demand_matches','energy_nonnegative','energy_balance','model_report_agrees','work_labels_valid','budget_ledger_agrees','within_budget','external_reservations_clear','reserved_exit_honored','clock_costs_nonnegative','authorization_respected','runner_contract','instance_isolation'}
COSTS=('person_seconds','tool_seconds','resource_queue_seconds','approval_wait_seconds','unstarted_observed_wait_seconds','observed_stop_time','request_count','policy_call_count')
CORE_FILES={'src/aegis_dc/__init__.py','src/aegis_dc/london_e14.py','src/aegis_dc/london_treatments.py','src/aegis_dc/london_treatment_score.py'}

def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def file_sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encode(x):
    if isinstance(x,Fraction):return x.numerator if x.denominator==1 else str(x)
    if isinstance(x,dict):return {k:encode(v) for k,v in x.items()}
    if isinstance(x,list):return [encode(v) for v in x]
    return x
def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def utc():return datetime.now(timezone.utc).isoformat()
def private_fields(value):
    if isinstance(value,dict):return set(value)&PRIVATE_KEYS | {k for v in value.values() for k in private_fields(v)}
    if isinstance(value,list):return {k for v in value for k in private_fields(v)}
    return set()
def diff(a,b):return None if a is None or b is None else encode(Fraction(a)-Fraction(b))

def validate_input(data,sha):
    if sha!=INPUT_SHA:raise ValueError('Only the user-frozen development file is authorized')
    if data.get('schema')!='aegisdc-r3-development-inputs-v1' or data.get('confirmation') is not False:
        raise ValueError('Only disclosed development schema; confirmation and engineering are forbidden')
    if data.get('treatments')!=list(ARMS) or data.get('public_tick_seconds')!=1:raise ValueError('Treatment or clock drift')
    if [c.get('condition_id') for c in data.get('conditions',[])]!=IDS:raise ValueError('Original19 condition order required')
    for c in data['conditions']:
        if c.get('classification')!='DISCLOSED_DEVELOPMENT' or c['common'].get('H')!=20:raise ValueError('Condition scope drift')

def preflight(root,manifest,manifest_sha,output):
    if manifest.get('schema')!='aegisdc-r4-public-dev-launch-v1' or manifest.get('authorization')!='ONE_PUBLIC_DEVELOPMENT_BATCH_ONLY':raise ValueError('Missing explicit launch authorization')
    if manifest['core_revision']!=CORE_REV or manifest['input']['sha256']!=INPUT_SHA:raise ValueError('Frozen identity drift')
    if manifest['budget']!=dict(conditions=19,arms=57,policy_calls_per_arm=20,policy_calls_total=1140,cpus=1,memory_MiB=1024,wall_seconds=300):raise ValueError('Budget drift')
    if Path(manifest['output_directory']).resolve()!=output:raise ValueError('Output/attempt directory differs from frozen manifest')
    if manifest['condition_order']!=IDS or manifest['arm_order']!=list(ARMS) or manifest.get('confirmation_authorized') is not False:raise ValueError('Order/scope mismatch')
    required=CORE_FILES|{'scripts/run_london_public_development.py',manifest['input']['path']}
    if not required.issubset(manifest['files']):raise ValueError('Incomplete runtime manifest')
    for f,meta in manifest['files'].items():
        path=(root/f).resolve()
        if root not in path.parents or not path.is_file() or file_sha(path)!=meta['sha256']:raise ValueError('Source/input mismatch: '+f)
        if f in CORE_FILES and meta.get('git_revision')!=CORE_REV:raise ValueError('Core not bound to accepted revision')
    if os.environ.get('SLURM_CPUS_PER_TASK')!='1' or os.environ.get('SLURM_MEM_PER_NODE')!='1024':raise ValueError('Allocation differs from1CPU/1GiB')
    data=json.loads((root/manifest['input']['path']).read_text(encoding='utf-8'))
    validate_input(data,file_sha(root/manifest['input']['path']))
    return data

def inspect_result(actual,common,condition_id):
    """Outside-policy contract checks. They never choose or replay actions."""
    fatal=[]
    def demand(ok,name):
        if not ok:fatal.append(name)
    demand(not actual.get('errors'),'RUNNER_EXCEPTION')
    arms=actual.get('arms',{});demand(set(arms)==set(ARMS),'MISSING_ARM')
    isolation=actual.get('isolation',{})
    for k in ('initial_public_equal','initial_private_equal','input_unchanged','all_other_states_unchanged'):demand(isolation.get(k) is True,'ISOLATION:'+k)
    ids=isolation.get('object_ids',{})
    demand(bool(ids),'MISSING_IDENTITY_EVIDENCE')
    for k,x in ids.items():demand(set(x)==set(ARMS) and len(set(x.values()))==3,'SHARED_OBJECT:'+k)
    demand(actual.get('common_input_sha256')==digest(common),'COMMON_INPUT_IDENTITY')
    demand(actual.get('execution_order')==list(ARMS),'ARM_ORDER')
    calls=actual.get('calls',[])
    counts={k:sum(c.get('kind')==kind for c in calls) for k,kind in [('constructor_attempts','constructor'),('plant_entry_calls','plant'),('policy_calls','policy'),('scorer_calls','scorer')]}
    demand(actual.get('counts')==counts,'CALL_LEDGER_COUNTS')
    demand(counts['constructor_attempts']==3,'CONSTRUCTOR_COUNT')
    for c in calls:demand('error' not in c,'CALL_EXCEPTION')
    # Compare actual before/after snapshots, not merely their boolean summaries.
    for pair in isolation.get('snapshots',[]):
        demand(canonical(calls[pair['before_call']]['actual'])==canonical(calls[pair['after_call']]['actual']),'OTHER_ARM_CHANGED')
    for name in ARMS:
        r=arms.get(name,{})
        demand(not r.get('errors'),'ARM_ERROR:'+name)
        score=r.get('score',{});audit=r.get('final_audit')
        demand(audit is not None,'MISSING_FINAL_AUDIT:'+name)
        if audit is not None:
            demand(audit.get('time')==20 and canonical(audit.get('original_input'))==canonical(common),'FINAL_INPUT_OR_WINDOW:'+name)
        demand(score.get('trace_status')=='COMPLETE','MISSING_OR_INVALID_TRACE:'+name)
        demand(score.get('L') is not None and score.get('U') is not None,'MISSING_SCORE:'+name)
        constraints=score.get('hard_constraints',{});demand(set(constraints)==CONSTRAINTS,'MISSING_CONSTRAINTS:'+name)
        for k,ok in constraints.items():
            if k not in RESOURCE_NONCOMPLIANCE:demand(ok is True,'INVARIANT:'+name+':'+k)
        demand(score.get('hard_constraints_ok')==all(constraints.values()),'CONSTRAINT_SUMMARY:'+name)
        trace=r.get('public_trace',[]);demand(len(trace)<=20,'POLICY_BUDGET:'+name)
        policy_calls=[c for c in calls if c.get('kind')=='policy' and c.get('arm')==name]
        demand(len(policy_calls)==len(trace),'POLICY_TRACE_COUNT:'+name)
        requests=r.get('requests',[]);demand(len(requests)<={'I':5,'D':2,'P':0}[name],'REQUEST_CAP:'+name)
        actions=[x['payload']['action'] for x in requests];demand(len(set(actions))==len(actions),'ACTION_RETRY:'+name)
        demand(r.get('requested_actions')==actions,'ACTION_LEDGER:'+name)
        if name=='D':demand(set(actions).issubset({'FIX_CTRL','VERIFY_CTRL'}),'DIRECT_DIAGNOSIS')
        for c,frame in zip(policy_calls,trace):
            view=frame['view'];t=Fraction(view['time'])
            demand(set(c['arguments'])=={'treatment','public_view'} and c['arguments']['treatment']==name,'POLICY_SIGNATURE:'+name)
            demand(canonical(c['arguments']['public_view'])==canonical(view) and canonical(c['actual'])==canonical(frame['decision']),'POLICY_CALL_BINDING:'+name)
            demand(set(view)==VIEW_KEYS and view.get('view_schema')=='aegisdc-e14-public-v2','PUBLIC_ENVELOPE:'+name)
            demand(not private_fields(view) and condition_id not in canonical(view),'PRIVATE_INPUT:'+name)
            demand(t.denominator==1 and 0<=t<20 and view['pre_open'],'PUBLIC_CLOCK:'+name)
            if common['tF'] is not None:demand(t<Fraction(common['tF']),'POST_FAULT_POLICY:'+name)
        for r0 in requests:
            demand(r0['reply']['status'] not in ('INVALID_REQUEST','INVALID_PARENT'),'ILLEGAL_REQUEST:'+name)
            if r0['payload']['action']=='VERIFY_CTRL':
                view=trace[r0['frame_index']]['view'];payload=r0['payload']
                demand(any(e.get('record_kind')=='EXECUTION_RECEIPT' and e.get('status')=='EXECUTED_UNVERIFIED' and payload['execution_id']==e['execution_id'] and payload['target_config_epoch']==e['target_config_epoch'] for e in view['receipts']),'VERIFY_PARENT:'+name)
    return list(dict.fromkeys(fatal))

def arm_summary(actual,name):
    r=actual.get('arms',{}).get(name,{})
    score=r.get('score',{});reached=r.get('reached',{})
    calls=[c for c in actual.get('calls',[]) if c.get('arm')==name]
    return dict(stage=reached.get('stage'),reached=reached,stop=r.get('stop'),L=score.get('L'),U=score.get('U'),
      costs={k:score.get(k) for k in COSTS},work_by_action=score.get('work_by_action'),work_by_stage=score.get('work_by_stage'),
      calls={k:sum(c.get('kind')==k for c in calls) for k in ('constructor','plant','policy','scorer')},
      hard_constraints=score.get('hard_constraints'),hard_constraints_ok=score.get('hard_constraints_ok',False),
      trace_status=score.get('trace_status'),verification_result=reached.get('verification_result'),
      recoveries=score.get('recoveries'),errors=r.get('errors',[]),request_statuses=[x['reply']['status'] for x in r.get('requests',[])],
      requested_actions=r.get('requested_actions',[]),request_times=r.get('request_times',[]),
      failure_status='IMPLEMENTATION_ERROR' if r.get('errors') else 'NONCOMPLIANT' if score.get('hard_constraints_ok') is False else 'PROCESS_NON_SUCCESS' if reached.get('stage') in ('NOT_IMPLEMENTED','APPROVAL_DENIED','COMMIT_FAILED','VERIFICATION_FAILED','VERIFY_INCONCLUSIVE','VERIFY_ABORTED','EXIT_INCOMPLETE','EXECUTED_UNVERIFIED') else 'NONE')

def summarize(identifier,actual,fatal):
    arms={name:arm_summary(actual,name) for name in ARMS};i,d=arms['I'],arms['D']
    raw_delta=diff(d['L'],i['L'])
    complete=all(a['trace_status']=='COMPLETE' and a['L'] is not None for a in arms.values())
    compliant=all(a['hard_constraints_ok'] for a in arms.values())
    valid=not fatal and complete and compliant
    outcome='STOPPED_ON_ERROR' if fatal else 'UNIDENTIFIED_MISSING_SCORE' if not complete else 'NONCOMPLIANT_NOT_VALID_GAIN' if not compliant else 'LESS_DEFICIT_WITH_INSPECTION' if Fraction(raw_delta)>0 else 'MORE_DEFICIT_WITH_INSPECTION' if Fraction(raw_delta)<0 else 'SAME_DEFICIT'
    return dict(condition_id=identifier,status='ERROR' if fatal else 'EXECUTED',arms=arms,
      delta_L_D_minus_I=raw_delta,delta_costs_I_minus_D={k:diff(i['costs'][k],d['costs'][k]) for k in COSTS},
      valid_comparison=valid,comparison_status=outcome,fatal_findings=fatal,raw_consequences_retained=True)

def not_executed(identifier,reason):
    return dict(condition_id=identifier,status='NOT_EXECUTED',reason=reason,arms={a:None for a in ARMS},delta_L_D_minus_I=None,delta_costs_I_minus_D={k:None for k in COSTS},valid_comparison=False,comparison_status='NOT_EXECUTED',fatal_findings=[])

def execute_batch(data,run_condition,output,manifest):
    rows=[not_executed(c['condition_id'],'Awaiting original order') for c in data['conditions']]
    terminal=dict(schema='aegisdc-public-development-result-v1',classification='R4_DISCLOSED_DEVELOPMENT_NOT_CONFIRMATION',status='RUNNING',started_at=utc(),job_id=os.environ.get('SLURM_JOB_ID'),
      core_revision=CORE_REV,entry_revision=manifest['entry_revision'],input_sha256=INPUT_SHA,conditions_declared=19,condition_order=IDS,arms_order=list(ARMS),conditions_started=0,conditions_returned=0,
      counts=dict(runner_calls=0,constructor_attempts=0,plant_entry_calls=0,policy_calls=0,scorer_calls=0),records=[],rows=rows,confirmation_runs=0,engineering_runs_this_batch=0)
    save(output/'started.json',{k:v for k,v in terminal.items() if k not in ('rows','records')})
    halted=False
    for index,condition in enumerate(data['conditions']):
        identifier=condition['condition_id']
        if halted:
            rows[index]=not_executed(identifier,'Batch stopped at preceding condition; no model call');continue
        # The ID remains here, in the evaluator archive; core receives config only.
        save(output/(identifier+'-started.json'),dict(condition=condition,started_at=utc(),index=index,core_revision=CORE_REV))
        terminal['conditions_started']+=1;terminal['counts']['runner_calls']+=1
        wall=time.monotonic();cpu=time.process_time();actual=None;fatal=[]
        record=dict(condition=deepcopy(condition),index=index,core_revision=CORE_REV,started_at=utc())
        try:
            actual=run_condition(deepcopy(condition['common']),order=list(ARMS))
            terminal['conditions_returned']+=1;record['actual']=actual
            for k in ('constructor_attempts','plant_entry_calls','policy_calls','scorer_calls'):terminal['counts'][k]+=actual.get('counts',{}).get(k,0)
            fatal=inspect_result(actual,condition['common'],identifier)
            if terminal['counts']['policy_calls']>1140:fatal.append('BATCH_POLICY_BUDGET')
        except BaseException as e:
            fatal.append('ENTRY_OR_CORE_EXCEPTION');record['exception']=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
        record.update(finished_at=utc(),wall_seconds=time.monotonic()-wall,cpu_seconds=time.process_time()-cpu,fatal_findings=fatal)
        try:summary=summarize(identifier,actual,fatal) if actual is not None else not_executed(identifier,'Started but runner returned no complete record')
        except Exception as e:
            fatal.append('SUMMARY_EXCEPTION');record['summary_exception']=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc());summary=not_executed(identifier,'Started; malformed/incomplete return; raw record retained')
        if actual is None or 'SUMMARY_EXCEPTION' in fatal:
            summary.update(status='ERROR',comparison_status='STOPPED_ON_ERROR',fatal_findings=list(fatal))
        record['summary']=summary;save(output/(identifier+'.json'),record)
        rows[index]=summary;terminal['records'].append(dict(condition_id=identifier,file=identifier+'.json',sha256=file_sha(output/(identifier+'.json')),fatal_findings=fatal))
        if fatal:halted=True;terminal['halted_at']=identifier
        # Write all19 rows at every completed step so a kill never hides suffixes.
        for n in range(index+1,len(rows)):rows[n]=not_executed(IDS[n],'Stopped after fatal condition' if halted else 'Not yet started')
        save(output/('progress-'+str(index+1).zfill(2)+'.json'),terminal)
    terminal['status']='STOPPED_ON_ERROR' if halted else 'COMPLETED_PUBLIC_DEVELOPMENT'
    terminal['finished_at']=utc();terminal['resource_usage']=dict(process_cpu_seconds=time.process_time(),max_rss_platform_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return terminal

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--manifest-sha',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Allocated remote CPU execution required')
    root=Path(__file__).resolve().parents[1];a.manifest=a.manifest.resolve();a.output=a.output.resolve()
    a.output.mkdir(parents=True,exist_ok=False)
    result=dict(status='PRE_EXECUTION_FAILURE',input_sha256=INPUT_SHA,core_revision=CORE_REV,conditions_started=0,counts=dict(runner_calls=0,constructor_attempts=0,plant_entry_calls=0,policy_calls=0,scorer_calls=0),rows=[not_executed(x,'Preflight did not complete') for x in IDS],confirmation_runs=0)
    try:
        if file_sha(a.manifest)!=a.manifest_sha:raise ValueError('Frozen launch manifest mismatch')
        manifest=json.loads(a.manifest.read_text(encoding='utf-8'));data=preflight(root,manifest,a.manifest_sha,a.output)
        save(a.output/'launch-manifest.json',manifest)
        sys.path.insert(0,str(root/'src'));module=importlib.import_module('aegis_dc.london_treatments')
        result=execute_batch(data,module.run_condition,a.output,manifest)
        result['manifest_sha256']=a.manifest_sha
        result['source_unchanged']=all(file_sha(root/f)==meta['sha256'] for f,meta in manifest['files'].items())
        if not result['source_unchanged']:result['status']='SOURCE_CHANGED_INVALID_RESULTS'
    except BaseException as e:result['error']=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    save(a.output/'terminal.json',result)
    print(json.dumps(dict(status=result['status'],conditions_started=result['conditions_started'],counts=result['counts'],output=str(a.output))))
    return 0 if result['status']=='COMPLETED_PUBLIC_DEVELOPMENT' else 1

if __name__=='__main__':raise SystemExit(main())
