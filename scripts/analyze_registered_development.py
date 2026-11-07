"""Recompute a registered development report from exact saved originals only."""

import argparse
from hashlib import sha256
import io
import json
from math import fsum
from pathlib import Path
import sys
from zipfile import ZipFile

from development_journal import reconcile
from development_run_evidence import check_run
from inspection_delivery import ROOT, durable, git, hashes, require
from registered_comparison import canonical, read

SOURCE_PACKAGE='evidence/mainline/engineering/30-comparison-preparation'
PREFIX='input-preparation/30-development-inputs-02'


def digest(raw):
    return sha256(raw).hexdigest()


def _same_history_divergence(base_run,candidate_run,base_audit,candidate_audit):
    b_rows=base_run['policy_public_decisions']
    c_rows=candidate_run['policy_public_decisions']
    require(len(b_rows)==len(c_rows),'Paired decision counts differ')
    for i,(left,right) in enumerate(zip(b_rows,c_rows,strict=True)):
        a,b=left['choice']['chosen_candidate_id'],right['choice']['chosen_candidate_id']
        same=canonical(left['frame'])==canonical(right['frame']) and canonical(left['history'])==canonical(right['history'])
        if a!=b:
            left_options=base_audit['opportunities'][i]['common_preference_eligible']
            right_options=candidate_audit['opportunities'][i]['common_preference_eligible']
            common=sorted(set(left_options)&set(right_options))
            return dict(first_different_s=left['frame']['as_of_s'],same_public_frame_and_history=same,
                baseline_intent=a,candidate_intent=b,common_eligible_paid=common,
                identified=bool(same and left_options==right_options and len(common)>=2))
        require(same,'Public histories diverged before any differing policy intention')
    return dict(first_different_s=None,identified=False,baseline_intent=None,candidate_intent=None,
                common_eligible_paid=[],same_public_frame_and_history=True)


def analyze(folder):
    batch=read(folder/'batch.json')
    source=batch['execution_commit']
    terminal=read(folder/'receipt.json')
    require(terminal['source_unchanged'] and terminal['execution_commit']==source
            and terminal['held_inputs_read']==terminal['held_seed_reads']==terminal['automatic_retries']==0,
            'Returned batch is not an unchanged development capture')
    require(durable(folder)==set(terminal['artifacts'])|{'receipt.json'}
            and all(digest((folder/path).read_bytes())==h for path,h in terminal['artifacts'].items()),
            'Batch durable set or fingerprint differs')
    total=reconcile(folder,batch['slots'],source)
    require(total==terminal['total'],'Recomputed attempts differ from batch receipt')
    require(batch['pins']==hashes(source,batch['pins'])
            and all(digest((ROOT/path).read_bytes())==h for path,h in batch['pins'].items()),
            'Executed source or input declaration differs')
    saved={}
    inputs={}
    with ZipFile(ROOT/SOURCE_PACKAGE/'preparation-originals.zip') as archive:
        for slot in batch['slots']:
            if not slot['input_member'] in inputs:
                raw=archive.read(slot['input_member'])
                require(digest(raw)==slot['input_sha256'],'Frozen development input differs')
                inputs[slot['input_member']]=json.loads(raw)
    runtime={path:h for path,h in batch['pins'].items()
             if (path.startswith('src/aegis_dc/') and path.endswith('.py')) or path=='src/patrol_rsi/contracts.py'}
    for slot in batch['slots']:
        case=folder/f"{slot['index']:02}-{slot['world_id']}-{slot['arm']}"
        if not case.exists():
            continue
        attempt=read(case/'terminal.json')
        row=dict(world_id=slot['world_id'],family=slot['family'],arm=slot['arm'],
                 status=attempt['status'],error=attempt.get('error'),returned=attempt['physical_returned'])
        if (case/'originals.zip').is_file():
            manifest=read(case/'originals.json')
            raw=(case/'originals.zip').read_bytes()
            require(digest(raw)==manifest['archive_sha256'],'Native archive identity differs')
            with ZipFile(io.BytesIO(raw)) as archive:
                require(set(archive.namelist())==set(manifest['members'])
                        and len(archive.namelist())==len(manifest['members'])==4,'Native members differ')
                members={path:archive.read(path) for path in archive.namelist()}
                require(all(digest(data)==manifest['members'][path] for path,data in members.items()),'Native raw bytes differ')
                run=json.loads(members['run.json'])
                model=json.loads(members['scenario.json'])
                document=inputs[slot['input_member']]
                require(model==document['model'] and run['code_identity']['git_commit']==source
                        and run['code_identity']['files']==runtime and run['code_identity']['implementation_has_changes'] is False,
                        'Returned native run source identity differs')
                for path,item in run['artifacts'].items():
                    require(digest(members[path])==item['sha256'],'Native declared artifact identity differs')
                trace=[json.loads(line) for line in members['private-state.jsonl'].splitlines()]
                balances=[json.loads(line) for line in members['balances.jsonl'].splitlines()]
            if attempt['status']=='COMPLETED':
                audit=check_run(document,run,trace,balances)
                require(audit==read(case/'audit.json'),'Saved original evidence analysis differs')
                row.update(totals=audit['totals'],common_two_or_more=audit['common_two_or_more'],
                    resource_contention_frames=audit['resource_contention_frames'],
                    completed_inspections=audit['completed_inspections'],
                    completed_interventions=audit['completed_interventions'],task_dispositions=audit['task_dispositions'],
                    effects=audit['applied_effects'])
                row['_run']=run
                row['_audit']=audit
        saved[(slot['world_id'],slot['arm'])]=row
    pairs=[]
    worlds={s['world_id']:s['family'] for s in batch['slots']}
    for world,family in worlds.items():
        base=saved.get((world,'one_observation_lookahead'))
        cand=saved.get((world,'evidence_consistent_contingent'))
        row=dict(world_id=world,family=family,complete=bool(base and cand and base['status']==cand['status']=='COMPLETED'))
        if row['complete']:
            costs={}
            for key in ('paid_person_s','worker_travel_person_s','tool_occupation_tool_s'):
                costs[key]=cand['totals'][key]-base['totals'][key]
            row.update(delta_service_deficit_s=base['totals']['service_deficit_time_s']-cand['totals']['service_deficit_time_s'],
                extra_costs=costs,opportunity=_same_history_divergence(base['_run'],cand['_run'],base['_audit'],cand['_audit']))
        pairs.append(row)
    plain=[{k:v for k,v in row.items() if not k.startswith('_')} for row in saved.values()]
    complete=[r for r in pairs if r['complete']]
    return dict(status='PASS_SAVED_DEVELOPMENT_REPORT',execution_commit=source,batch_status=terminal['status'],
        ledger_totals=total,planned_worlds=len(worlds),complete_primary_pairs=len(complete),
        primary_mean_delta_service_s=fsum(row['delta_service_deficit_s'] for row in complete)/len(worlds)
            if len(complete)==len(worlds) else None,
        identified_shared_history_worlds=sum(r['opportunity']['identified'] for r in complete),
        observed_identified_families=sorted({r['family'] for r in complete if r['opportunity']['identified']}),
        pairs=pairs,runs=plain,source_read_only=True,new_facility_calls=0,new_selector_calls=0,
        held_inputs_read=0,scope='Development diagnostics only. No confirmation result, candidate tuning or general superiority claim.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=analyze(args.capture.resolve())
    with args.output.open('x',encoding='utf-8',newline='\n') as file:
        json.dump(result,file,ensure_ascii=False,indent=2,allow_nan=False)
        file.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('runs','pairs')},ensure_ascii=False))


if __name__=='__main__':
    main()
