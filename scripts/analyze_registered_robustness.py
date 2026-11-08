"""Saved-only descriptive analysis of the original four contrast blocks."""
import argparse
from collections import Counter,defaultdict
import csv
import io
import json
import math
from pathlib import Path
import sys
import zipfile
from inspection_delivery import ROOT,read,write,digest,durable,require,git
from development_journal import reconcile

PACKAGE='evidence/mainline/research/36-robustness'
BASELINE='one_observation_lookahead'
CANDIDATE='evidence_consistent_contingent'

def analyze(folder,out):
    require(not out.exists(),'Use a unique saved-analysis directory')
    out.mkdir(parents=True)
    source=git('rev-parse','HEAD').decode().strip();inputs={}
    write(out/'start.json',dict(status='STARTED_SAVED_ANALYSIS',source=source,physical_calls=0,selector_calls=0))
    def original(path):
        raw=path.read_bytes();relative=path.relative_to(ROOT).as_posix()
        require(git('cat-file','blob',source+':'+relative)==raw,'Analysis input differs from committed original')
        inputs[relative]=digest(raw);return raw
    try:
        receipt=json.loads(original(folder/'receipt.json'));batch=json.loads(original(folder/'batch.json'))
        original(folder/'attempts.jsonl')
        total=reconcile(folder,batch['slots'],batch['execution_commit'])
        require(total==receipt['total'] and receipt['source_unchanged'],'Saved budget/source receipt differs')
        require(receipt['status']=='PASS' and total['completed']==16 and total['failed']==total['interrupted']==total['unrun']==0,
                'Failed/missing robustness requires an explicit failure audit and fixed-denominator partial-outcome report')
        require(all(digest((folder/n).read_bytes())==h for n,h in receipt['artifacts'].items()),'Saved capture artifact differs')
        plan=json.loads(original(ROOT/'docs/mainline/30-comparison-protocol-v1.json'))
        world_index={r['id']:r for r in plan['phases']['robustness']['worlds']}
        rows=[];timing=[]
        for slot in batch['slots']:
            directory=folder/f"{slot['index']:02}-{slot['world_id']}-{slot['arm']}"
            began=json.loads(original(directory/'start.json'));terminal=json.loads(original(directory/'terminal.json'))
            audit=json.loads(original(directory/'audit.json'));archive=original(directory/'originals.zip')
            require(terminal['status']=='COMPLETED' and digest(archive)==terminal['artifacts']['originals.zip'],'Incomplete native original')
            with zipfile.ZipFile(io.BytesIO(archive)) as z:
                require(set(z.namelist())=={'scenario.json','run.json','private-state.jsonl','balances.jsonl'},'Native member set differs')
                native=json.loads(z.read('run.json'))
            require(native['code_identity']['git_commit']==began['source']==terminal['source']==batch['execution_commit'],'Executed source differs')
            require(native['inputs']['dispatch_program']['closure_program'] is None and not audit['hard_violations'],'Unexpected closure or hard breach')
            totals=dict(audit['totals'])
            require(math.isclose(totals['demand_service_unit_s']-totals['delivered_service_unit_s'],totals['unserved_service_unit_s'],abs_tol=1e-8),'Service account differs')
            require(math.isclose(totals['paid_person_s'],math.fsum(totals[k] for k in ['worker_travel_person_s','worker_work_person_s','worker_wait_person_s']),abs_tol=1e-8),'Paid account double counts wait')
            world=world_index[slot['world_id']];work={r['id']:r for r in native['work_records']}
            bindings={r['task_id']:r for r in native['inspection_public_models']['bindings']}
            records={r['id']:r for r in native['inspection_public_snapshot']['records']}
            feedback=native['inspection_public_feedback'];findings=Counter(f['confirmation'] for f in feedback)
            for f in feedback:
                record=records[f['record_id']];task=work[f['task_id']]
                require(f['scope']=='NAMED_SIGNAL_THRESHOLD_ONLY_NOT_FAULT_DIAGNOSIS' and f['additional_evidence_factor'] is False,'Wrong confirmation scope')
                require(task['status']=='completed' and f['observed_at_s']==task['completed_at_s'],'No actual sample completion')
                for field in ['source_id','target_id','observable_id','provenance','observed_at_s','arrived_at_s','valid_until_s']:
                    require(f[field]==record[field],'Feedback/source binding differs')
                timing.append(dict(world_id=world['id'],arm=slot['arm'],task_id=f['task_id'],record_id=f['record_id'],
                    issued_at_s=task['issued_at_s'],observed_at_s=f['observed_at_s'],arrived_at_s=f['arrived_at_s'],
                    issue_to_report_s=f['arrived_at_s']-task['issued_at_s'],valid_until_s=f['valid_until_s'],
                    source_id=f['source_id'],target_id=f['target_id'],observable_id=f['observable_id'],provenance=f['provenance'],
                    historical_threshold_finding=f['confirmation'],current_confirmation=f['current_confirmation'],scope=f['scope']))
            counters=Counter()
            for item in native['policy_computation_audit']:counters.update(item['model_evaluations'])
            rows.append(dict(world_id=world['id'],comparison=world['comparison'],family=world['family'],level=world['level'],arm=slot['arm'],
                **totals,completed_inspections=audit['completed_inspections'],completed_interventions=audit['completed_interventions'],
                issued_inspection_tasks=sum(n in bindings for n in work),arrived_inspection_feedback=len(feedback),
                historical_named_threshold_findings=sum(v for k,v in findings.items() if k!='UNCONFIRMED'),
                current_named_threshold_findings=sum(f['current_confirmation'] for f in feedback),unconfirmed_readings=findings['UNCONFIRMED'],
                task_dispositions=dict(Counter(w['status'] for w in work.values())),applied_effects=len(audit['applied_effects']),
                selector_instants=len(native['policy_computation_audit']),model_evaluations=dict(counters),
                wall_compute_s=math.fsum(c['elapsed_ns'] for c in native['policy_computation_audit'])/1e9,
                structural_validation_counter='NOT_INSTRUMENTED',generic_fault_confirmation='NOT_OPERATIONALIZED',
                misleading_report_rate='NOT_OPERATIONALIZED_NO_CUE_TRUTH_MAPPING',missed_report_rate='NOT_OPERATIONALIZED_NO_OPPORTUNITY_DENOMINATOR',
                pre_failure_prevention='NOT_TESTED',verified_closure='NOT_EVALUATED_WITHOUT_POST_ACTION_PROTOCOL'))
        by_world=defaultdict(dict)
        for row in rows:by_world[row['world_id']][row['arm']]=row
        paired=[]
        for world in plan['phases']['robustness']['worlds']:
            b,c=(by_world[world['id']][arm] for arm in [BASELINE,CANDIDATE])
            paired.append(dict(world_id=world['id'],comparison=world['comparison'],family=world['family'],level=world['level'],
                baseline_deficit_s=b['service_deficit_time_s'],candidate_deficit_s=c['service_deficit_time_s'],
                delta_service_s=b['service_deficit_time_s']-c['service_deficit_time_s'],
                extra_paid_person_s=c['paid_person_s']-b['paid_person_s'],
                extra_travel_person_s=c['worker_travel_person_s']-b['worker_travel_person_s'],
                extra_tool_s=c['tool_occupation_tool_s']-b['tool_occupation_tool_s']))
        contrasts=[]
        for i in range(0,8,2):
            reference,perturbed=paired[i:i+2]
            contrasts.append(dict(comparison=reference['comparison'],family=reference['family'],reference=reference,perturbed=perturbed,
                shift_in_delta_service_s=perturbed['delta_service_s']-reference['delta_service_s'],
                shift_in_extra_paid_person_s=perturbed['extra_paid_person_s']-reference['extra_paid_person_s']))
        primary=json.loads(original(ROOT/'evidence/mainline/research/34-paired-analysis/results.json'))
        result=dict(status='COMPLETE_FINITE_ROBUSTNESS_DESCRIPTIVES',source=source,execution_source=batch['execution_commit'],
            runs=16,worlds=8,contrast_blocks=4,simulated_s=160,scheduled_decisions=160,paired=paired,contrasts=contrasts,
            mean_over_eight_designed_worlds_service_delta_s=math.fsum(r['delta_service_s'] for r in paired)/8,
            independence='Four matched reference/perturbed blocks; not16 independent replications. No population interval.',
            original_primary_unchanged=dict(status=primary['status'],mean_service_delta_s=primary['mean_service_delta_s'],worlds=16),
            new_physical_calls=0,new_selectors=0,new_inference=0,field_calibration='PENDING')
        write(out/'run-readout.json',rows);write(out/'inspection-timing.json',timing);write(out/'results.json',result)
        for name,data in [('run-readout.csv',rows),('paired.csv',paired)]:
            with (out/name).open('x',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');writer.writeheader()
                for row in data:writer.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()})
        write(out/'input-manifest.json',inputs)
        require(not any(n.startswith('aegis_dc') for n in sys.modules),'Saved analysis imported project models')
        require(git('rev-parse','HEAD').decode().strip()==source,'Analysis source changed')
        terminal=dict(status='PASS_SAVED_ANALYSIS',source=source,input_files=len(inputs),runs=16,physical_calls=0,selector_calls=0)
    except BaseException as exc:
        terminal=dict(status='FAILED_SAVED_ANALYSIS',source=source,error_type=type(exc).__name__,error=str(exc),physical_calls=0,selector_calls=0)
        write(out/'receipt.json',terminal);raise
    write(out/'receipt.json',terminal)
    write(out/'manifest.json',dict(artifacts={n:digest((out/n).read_bytes()) for n in sorted(durable(out))}))
    return terminal

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(analyze(ROOT/PACKAGE/'capture-01',a.output.resolve())))
