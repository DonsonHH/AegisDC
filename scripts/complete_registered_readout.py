"""Complete descriptive readouts from immutable originals; never execute models."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import traceback
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'docs/mainline/audits/20261108-pre36/saved-readout-plan.json'
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
out=args.output if args.output.is_absolute() else ROOT/args.output
out.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
git=lambda *a:subprocess.check_output(['git',*a],cwd=ROOT)
source=git('rev-parse','HEAD').decode().strip()
plan=json.loads(PLAN.read_bytes());data_source=plan['source']
input_files={}
tree={}
for row in git('ls-tree','-r','-z',data_source).split(b'\0'):
    if row:
        header,path=row.split(b'\t',1);_,kind,blob=header.split()
        if kind==b'blob':tree[path.decode()]=blob.decode()
def read_original(path):
    relative=path.relative_to(ROOT).as_posix();raw=path.read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert tree.get(relative)==blob,'Original differs from pinned Git blob: '+relative
    input_files[relative]=dict(sha256=sha(raw),bytes=len(raw),git_blob=blob)
    return raw
def write(name,value):
    with (out/name).open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csv_file(name,rows,fields):
    with (out/name).open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n',extrasaction='raise');writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()})
def journal(value):
    with (out/'attempts.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,sort_keys=True)+'\n')
start=dict(event='STARTED',source=source,data_source=data_source,plan_sha256=sha(PLAN.read_bytes()),
    tool_sha256=sha(Path(__file__).read_bytes()),started_utc=datetime.now(timezone.utc).isoformat(),
    scope='SAVED_ONLY_DESCRIPTIVE_REPORTING_COMPLETION',new_research_runs=0)
write('start.json',start);journal(start)
try:
    assert not git('status','--porcelain','--untracked-files=no').strip(),'Pin tools and plan before aggregate extraction'
    assert git('show',source+':scripts/complete_registered_readout.py')==Path(__file__).read_bytes()
    assert git('show',source+':'+PLAN.relative_to(ROOT).as_posix())==PLAN.read_bytes()
    protocol=json.loads(read_original(ROOT/'docs/mainline/30-comparison-protocol-v1.json'))
    original_primary=json.loads(read_original(ROOT/'evidence/mainline/research/34-paired-analysis/results.json'))
    rows=[];timing=[];archive_members={};run_keys=set()
    confirmed={'CONFIRMED_AT_OR_ABOVE_THRESHOLD','CONFIRMED_BELOW_THRESHOLD'}
    for dataset in plan['datasets']:
        archives=sorted((ROOT/dataset['capture']).glob('*/originals.zip'))
        assert len(archives)==dataset['expected_runs'],dataset['phase']
        phase_rows=[]
        for archive in archives:
            parent=archive.parent
            start_bytes=read_original(parent/'start.json');began=json.loads(start_bytes)
            terminal=json.loads(read_original(parent/'terminal.json'))
            audit_bytes=read_original(parent/'audit.json');audit=json.loads(audit_bytes)
            assert terminal['status']=='COMPLETED' and terminal['physical_returned'] is True
            assert sha(start_bytes)==terminal['artifacts']['start.json']
            assert sha(audit_bytes)==terminal['artifacts']['audit.json']
            run_key=(dataset['phase'],began['world_id'],began['arm'])
            assert run_key not in run_keys;run_keys.add(run_key)
            assert not audit['hard_violations']
            raw_archive=read_original(archive)
            assert sha(raw_archive)==terminal['artifacts']['originals.zip']
            with zipfile.ZipFile(io.BytesIO(raw_archive)) as z:
                assert set(z.namelist())=={'scenario.json','run.json','private-state.jsonl','balances.jsonl'}
                native_bytes=z.read('run.json');native=json.loads(native_bytes)
            archive_members[archive.relative_to(ROOT).as_posix()]={'run.json':dict(sha256=sha(native_bytes),bytes=len(native_bytes))}
            assert native['code_identity']['git_commit']==began['source']==terminal['source']
            duration=began['duration_s'];dispatch=native['inputs']['dispatch_program']
            assert dispatch.get('closure_program') is None,'Do not silently reinterpret a configured closure study'
            totals=dict(audit['totals'])
            assert math.isclose(totals['demand_service_unit_s']-totals['delivered_service_unit_s'],totals['unserved_service_unit_s'],rel_tol=0,abs_tol=1e-8)
            assert math.isclose(totals['paid_person_s'],math.fsum(totals[k] for k in ['worker_travel_person_s','worker_work_person_s','worker_wait_person_s']),rel_tol=0,abs_tol=1e-8)
            snapshot=native['inspection_public_snapshot'];feedback=native['inspection_public_feedback']
            records={r['id']:r for r in snapshot['records']}
            tasks={r['id']:r for r in native['work_records']}
            private=native['inspection_private_audit']
            sample_events={e['task_id']:e for e in private['events'] if 'record_id' in e}
            bindings={b['task_id']:b for b in native['inspection_public_models']['bindings']}
            findings=Counter();matched=0;seen=set()
            feedback_by_task={}
            for f in feedback:
                key=(f['task_id'],f['record_id']);assert key not in seen;seen.add(key)
                r=records[f['record_id']];task=tasks[f['task_id']];event=sample_events[f['task_id']]
                assert f['scope']=='NAMED_SIGNAL_THRESHOLD_ONLY_NOT_FAULT_DIAGNOSIS'
                assert f['additional_evidence_factor'] is False
                assert task['status']=='completed' and task['completed_at_s']==f['observed_at_s']==event['source_sample_at_s']
                assert f['arrived_at_s']<=duration and f['observed_at_s']>=task['work_started_at_s']>=task['issued_at_s']
                assert f['record_id']==event['record_id']==bindings[f['task_id']]['record_id']
                for field in ['source_id','target_id','observable_id','provenance','observed_at_s','arrived_at_s','valid_until_s']:
                    assert f[field]==r[field],field
                assert f['current_confirmation']==(r['availability']=='current' and f['confirmation']!='UNCONFIRMED')
                if f['confirmation'] in confirmed:assert r['quality']['status']=='bounded' and r['value'] is not None
                matched+=1;findings[f['confirmation']]+=1;feedback_by_task[f['task_id']]=f
            provenance_count=(sum(findings[k] for k in confirmed) if not snapshot['provenance_issues'] else None)
            current_count=(sum(f['current_confirmation'] for f in feedback) if not snapshot['provenance_issues'] else None)
            for task_id,task in tasks.items():
                if task_id not in bindings:continue
                event=sample_events.get(task_id,{});f=feedback_by_task.get(task_id)
                item=dict(phase=dataset['phase'],world_id=began['world_id'],arm=began['arm'],task_id=task_id,
                    task_status=task['status'],issued_at_s=task.get('issued_at_s'),site_arrival_at_s=task.get('arrived_at_s'),
                    work_started_at_s=task.get('work_started_at_s'),completed_at_s=task.get('completed_at_s'),
                    sampled_at_s=event.get('source_sample_at_s'),record_id=event.get('record_id'),
                    public_report_arrived_at_s=f['arrived_at_s'] if f else None,
                    source_id=f['source_id'] if f else None,
                    target_id=f['target_id'] if f else None,
                    observable_id=f['observable_id'] if f else None,
                    provenance=f['provenance'] if f else None,
                    valid_until_s=f['valid_until_s'] if f else None,
                    confirmation_scope=f['scope'] if f else None,
                    additional_evidence_factor=f['additional_evidence_factor'] if f else None,
                    report_metadata_status='ARRIVED_NATIVE_FEEDBACK' if f else 'NO_ARRIVED_REPORT_METADATA',
                    historical_named_signal_finding=f['confirmation'] if f else None,
                    endpoint_availability=f['availability'] if f else None,
                    endpoint_current_confirmation=f['current_confirmation'] if f else None,
                    observation_status='PUBLIC_REPORT_ARRIVED' if f else 'SAMPLED_NOT_PUBLICLY_ARRIVED' if event else 'NO_SAMPLE',
                    issue_to_report_s=f['arrived_at_s']-task['issued_at_s'] if f else None,
                    sample_to_report_s=f['arrived_at_s']-f['observed_at_s'] if f else None)
                timing.append(item)
            computation=native['policy_computation_audit'];counts=Counter()
            for c in computation:
                assert c['scope']=='DIAGNOSTIC_WALL_TIME_ONLY_NOT_PHYSICAL_TIME_OR_POLICY_INPUT'
                for k,v in c['model_evaluations'].items():
                    assert type(v) is int and v>=0
                    counts[k]+=v
            applied=[e for e in native['intervention_private_audit']['events'] if e['outcome']=='APPLIED']
            assert len(applied)==len(audit['applied_effects'])
            statuses=Counter(r['status'] for r in tasks.values())
            structure=native.get('ablation_execution_audit')
            structural_checks=structure['schema_component_identity_validations'] if structure is not None else None
            if structural_checks is not None:
                assert type(structural_checks) is int and structural_checks>=0
            quality=Counter('BOUND_CONTAINS_SIGNAL' if e['declared_bound_contains_signal'] else 'BOUND_FAILED'
                for e in private['events'] if 'declared_bound_contains_signal' in e)
            row=dict(phase=dataset['phase'],world_id=began['world_id'],family=began['family'],arm=began['arm'],
                original_index=began['index'],execution_source=began['source'],archive=archive.relative_to(ROOT).as_posix(),
                duration_s=duration,**totals,completed_inspections=audit['completed_inspections'],completed_interventions=audit['completed_interventions'],
                issued_inspection_tasks=sum(task_id in bindings for task_id in tasks),
                task_dispositions=dict(statuses),aborted_or_rejected_tasks=sum(n for k,n in statuses.items() if k in {'aborted','rejected'}),
                nonterminal_tasks=sum(n for k,n in statuses.items() if k not in {'completed','aborted','rejected'}),
                arrived_inspection_feedback=len(feedback),source_record_binding_checks_passed=matched,
                historical_named_threshold_findings=provenance_count,current_named_threshold_findings=current_count,
                threshold_findings=dict(findings),unconfirmed_named_signal_readings=findings['UNCONFIRMED'],
                provenance_status='MATCHED_NATIVE_TASK_RECORD_SCOPE' if not snapshot['provenance_issues'] else 'ISSUE_TIMING_NOT_INFERRED_FROM_FINAL_SNAPSHOT',
                numeric_bound_diagnostic=dict(quality),selector_instants=len(computation),model_evaluations=dict(counts),
                schema_component_identity_validations=structural_checks,
                structural_check_status='NATIVE_SEPARATE_COUNTER' if structure is not None else 'NOT_INSTRUMENTED_IN_ORIGINAL',
                selector_wall_seconds=math.fsum(c['elapsed_ns'] for c in computation)/1e9,
                applied_effects=len(applied),arrived_applied_feedback=sum(r['outcome']=='APPLIED' for r in native['intervention_public_feedback']),
                verified_closure='NOT_EVALUATED_WITHOUT_POST_ACTION_PROTOCOL',
                generic_fault_confirmation='NOT_OPERATIONALIZED',misleading_report_truth='NOT_OPERATIONALIZED_NO_CUE_TRUTH_MAPPING',
                missed_distinguishable_reports='NOT_OPERATIONALIZED_NO_OPPORTUNITY_DENOMINATOR',
                pre_failure_detection='NOT_TESTED_NO_FROZEN_PRECURSOR_ENDPOINT')
            assert sum(t['task_status']=='completed' for t in timing if t['phase']==row['phase'] and t['world_id']==row['world_id'] and t['arm']==row['arm'])==row['completed_inspections']
            rows.append(row);phase_rows.append(row)
        assert len({r['world_id'] for r in phase_rows})==dataset['independent_worlds']
    assert len(rows)==164
    # Reconcile the unchanged pre-registered primary, not a new outcome category.
    paired=defaultdict(dict)
    for r in rows:
        if r['phase']=='confirmation':paired[r['world_id']][r['arm']]=r
    deltas=[arms['one_observation_lookahead']['service_deficit_time_s']-arms['evidence_consistent_contingent']['service_deficit_time_s'] for arms in paired.values()]
    assert len(deltas)==16 and math.fsum(deltas)/16==original_primary['mean_service_delta_s']
    summaries=[]
    groups=defaultdict(list)
    for r in rows:groups[(r['phase'],r['arm'])].append(r)
    for (phase,arm),group in sorted(groups.items()):
        selected=[t for t in timing if t['phase']==phase and t['arm']==arm and t['public_report_arrived_at_s'] is not None]
        summarize=lambda key:sum(r[key] for r in group) if all(r[key] is not None for r in group) else None
        summaries.append(dict(phase=phase,arm=arm,worlds=len(group),completed_inspections=sum(r['completed_inspections'] for r in group),
            issued_inspection_tasks=sum(r['issued_inspection_tasks'] for r in group),
            arrived_inspection_feedback=sum(r['arrived_inspection_feedback'] for r in group),
            historical_named_threshold_findings=summarize('historical_named_threshold_findings'),
            endpoint_current_named_threshold_findings=summarize('current_named_threshold_findings'),
            unconfirmed_readings=sum(r['unconfirmed_named_signal_readings'] for r in group),
            applied_effects=sum(r['applied_effects'] for r in group),verified_closure='NOT_EVALUATED',
            issue_to_report_mean_s=math.fsum(t['issue_to_report_s'] for t in selected)/len(selected) if selected else None,
            issue_to_report_denominator=len(selected),
            timing_scope='DESCRIPTIVE_AMONG_SELECTED_ARRIVED_TASKS_NOT_CAUSAL_OR_FIELD_TIME'))
    coverage=[]
    for metric in protocol['comparison']['report_separately']:
        status='MEASURED_FROM_ORIGINAL_ACCOUNT_OR_FEEDBACK';reason='Separate quantity in run-readout with explicit units/denominators.'
        if metric=='provenance_valid_confirmation':status='MEASURED_NAMED_SIGNAL_SCOPE_ONLY';reason='Historical/current source-bound threshold findings; no generic fault diagnosis or risk closure claim.'
        elif metric=='misleading_reports_by_declared_world_truth':status='NOT_OPERATIONALIZED';reason='No frozen mapping from operator vibration cue to actual vibration truth; family names are not per-record labels.'
        elif metric=='missed_distinguishable_reports':status='NOT_OPERATIONALIZED';reason='No frozen opportunity/detectability universe and denominator; unissued tasks are not automatically missed faults.'
        elif metric=='actual_effect_vs_public_verified_closure':status='EFFECT_MEASURED_CLOSURE_NOT_EVALUATED';reason='APPLIED effects counted; all original closure_program values are null, so verified closure is NA.'
        coverage.append(dict(metric=metric,status=status,reason=reason))
    assert len(coverage)==18
    write('input-manifest.json',dict(data_source=data_source,files=input_files,native_members=archive_members))
    write('run-readout.json',rows);write('inspection-timing.json',timing);write('metric-coverage.json',coverage);write('method-summary.json',summaries)
    csv_file('run-readout.csv',rows,list(rows[0]));csv_file('inspection-timing.csv',timing,list(timing[0]));csv_file('method-summary.csv',summaries,list(summaries[0]))
    assert not any(name.startswith('aegis_dc') for name in sys.modules)
    assert git('rev-parse','HEAD').decode().strip()==source
    assert sha(PLAN.read_bytes())==start['plan_sha256'] and sha(Path(__file__).read_bytes())==start['tool_sha256']
    receipt=dict(status='PASS_SAVED_ONLY_READOUT_COMPLETION',source=source,data_source=data_source,runs=164,
        archives=len(archive_members),promised_metrics=18,inspection_timing_rows=len(timing),primary_status=original_primary['status'],
        primary_mean_service_delta_s=original_primary['mean_service_delta_s'],registered_runs=164,
        new_physical_calls=0,new_selector_calls=0,new_inference_calls=0,new_research_trials=0,
        scope='Post-hoc descriptive completion. Undefined fault/miss/prevention endpoints remain unmeasured, not zero or successful.')
    write('receipt.json',receipt);journal(dict(event='COMPLETED',**receipt))
except BaseException as error:
    (out/'error.txt').write_text(traceback.format_exc(),encoding='utf-8',newline='\n')
    write('receipt.json',dict(status='FAILED_SAVED_ONLY_EXTRACTION',source=source,error_type=type(error).__name__,message=str(error),
        new_research_trials=0,new_physical_calls=0,new_selector_calls=0,new_inference_calls=0))
    journal(dict(event='FAILED',source=source,error_type=type(error).__name__))
    raise
finally:
    artifacts={p.name:dict(sha256=sha(p.read_bytes()),bytes=p.stat().st_size) for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.json'}
    write('manifest.json',dict(schema='aegisdc-saved-readout-artifacts-v1',artifacts=artifacts,excluded=['Self-hash','runtime caches']))
print(json.dumps(receipt))
