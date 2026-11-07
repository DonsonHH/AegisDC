"""Recompute registered mask comparisons from immutable native originals only."""
import argparse,json
from collections import Counter
from math import fsum
from pathlib import Path
from zipfile import ZipFile
from comparison_release import ROOT,PROTOCOL
from inspection_delivery import read,require,digest,durable,hashes
from development_journal import reconcile
from ablation_planner import ARMS
from ablation_run_evidence import check_ablation_run
from prepare_ablation import PREP

def analyze(folder):
    batch=read(folder/'batch.json');receipt=read(folder/'receipt.json');source=batch['execution_commit'];plan=read(ROOT/PROTOCOL)
    require(receipt['source_unchanged'] and source==receipt['execution_commit'],'Ablation source guard failed')
    require(durable(folder)==set(receipt['artifacts'])|{'receipt.json'}
        and all(digest((folder/n).read_bytes())==h for n,h in receipt['artifacts'].items()),'Ablation durable originals differ')
    total=reconcile(folder,batch['slots'],source);require(total==receipt['total'],'Ablation totals do not reconcile')
    require(total['failed']==total['interrupted']==0,'Failed ablation requires an explicit cause/invalidity audit before interpretation')
    require(batch['pins']==hashes(source,batch['pins']) and all(digest((ROOT/n).read_bytes())==h for n,h in batch['pins'].items()),
        'Ablation execution/source/input identity differs')
    runtime={n:h for n,h in batch['pins'].items() if n.startswith('src/aegis_dc/') and n.endswith('.py') or n=='src/patrol_rsi/contracts.py'}
    rows=[]
    for slot in batch['slots']:
        case=folder/f"{slot['index']:02}-{slot['world_id']}-{slot['arm']}"
        if not case.exists():continue
        terminal=read(case/'terminal.json');require(terminal['status']=='COMPLETED','Incomplete ablation needs fixed-denominator missing-outcome audit')
        manifest=read(case/'originals.json');require(digest((case/'originals.zip').read_bytes())==manifest['archive_sha256'],'Ablation original ZIP differs')
        with ZipFile(case/'originals.zip') as z:
            require(len(z.namelist())==4 and set(z.namelist())==set(manifest['members']),'Ablation native membership differs')
            raw={n:z.read(n) for n in z.namelist()}
        require(all(digest(b)==manifest['members'][n] for n,b in raw.items()),'Ablation native bytes differ')
        docpath=ROOT/PREP/'inputs'/slot['input_member'];require(digest(docpath.read_bytes())==slot['input_sha256'],'Ablation input differs')
        doc=read(docpath);run=json.loads(raw['run.json'])
        require(json.loads(raw['scenario.json'])==doc['model'] and run['code_identity']['git_commit']==source
            and run['code_identity']['files']==runtime and run['code_identity']['implementation_has_changes'] is False,
            'Ablation actual native source/model identity differs')
        for n,item in run['artifacts'].items():require(digest(raw[n])==item['sha256'],'Native inner manifest differs')
        trace=[json.loads(v) for v in raw['private-state.jsonl'].splitlines()];balances=[json.loads(v) for v in raw['balances.jsonl'].splitlines()]
        audit=check_ablation_run(doc,run,trace,balances);require(audit==read(case/'audit.json'),'Ablation saved audit differs')
        calls=Counter();computations=run['policy_computation_audit']
        for row in computations:
            for name,value in row['model_evaluations'].items():
                require(type(value) is int and value>=0,'Unknown model-call counter');calls[name]+=value
        rows.append(dict(world_id=slot['world_id'],family=slot['family'],arm=slot['arm'],status='COMPLETED',
            totals=audit['totals'],work=audit['task_dispositions'],model_evaluations=dict(calls),
            diagnostic_policy_elapsed_ms=fsum(r['elapsed_ns'] for r in computations)/1e6,
            public_record_ids=sorted({r['id'] for d in run['policy_public_decisions'] for r in d['frame']['evidence']['records']}),
            adapter=run['ablation_execution_audit']))
    indexed={(r['world_id'],r['arm']):r for r in rows};pairs=[]
    require(len(rows)==32 and total['completed']==32,'Retain all32 original ablation units before complete interpretation')
    for world in plan['phases']['ablation']['worlds']:
        full=indexed[(world['id'],'full')]
        for arm in ARMS[1:]:
            mask=indexed[(world['id'],arm)];f=full['totals'];m=mask['totals']
            pairs.append(dict(world_id=world['id'],family=world['family'],mask=arm,
                mask_minus_full_deficit_s=m['service_deficit_time_s']-f['service_deficit_time_s'],
                full_minus_mask_paid_person_s=f['paid_person_s']-m['paid_person_s'],
                full_minus_mask_travel_person_s=f['worker_travel_person_s']-m['worker_travel_person_s'],
                full_minus_mask_tool_s=f['tool_occupation_tool_s']-m['tool_occupation_tool_s']))
    summaries={arm:{key:fsum(p[key] for p in pairs if p['mask']==arm)/8 for key in
        ('mask_minus_full_deficit_s','full_minus_mask_paid_person_s','full_minus_mask_travel_person_s','full_minus_mask_tool_s')} for arm in ARMS[1:]}
    return dict(status='COMPLETE_REGISTERED_ABLATION_DESCRIPTIVE',execution_source=source,ledger_totals=total,
        planned_worlds=8,completed_runs=32,pairs=pairs,summary=summaries,runs=rows,
        primary_confirmation_result_unchanged='NO_PRACTICAL_GAIN',observed_hard_violations=[],
        scope='Eight fixed independent mechanism conditions; paired finite means, no population inference or change to primary confirmation conclusion.',
        new_physical_calls=0,new_selector_calls=0,new_seed_reads=0)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    value=analyze(a.capture.resolve())
    with a.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('pairs','runs')},ensure_ascii=False))
if __name__=='__main__':main()
