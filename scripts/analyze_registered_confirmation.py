"""Recompute the independent confirmation facts from the exact native saved archives."""

import argparse,json
from pathlib import Path
import sys
from zipfile import ZipFile
from math import fsum

from comparison_release import ROOT,PROTOCOL
from inspection_delivery import digest,read,require,hashes,durable
from development_journal import reconcile
from development_run_evidence import check_run
from analyze_registered_development import _same_history_divergence
from summarize_comparison_facts import summarize

PREP='evidence/mainline/research/32-confirmation-freeze/prepared-02'


def analyze(folder):
    batch=read(folder/'batch.json');receipt=read(folder/'receipt.json')
    source=batch['execution_commit'];plan=read(ROOT/PROTOCOL)
    require(receipt['source_unchanged'] and receipt['execution_commit']==source,'Confirmation source guard failed')
    require(durable(folder)==set(receipt['artifacts'])|{'receipt.json'}
            and all(digest((folder/name).read_bytes())==sha for name,sha in receipt['artifacts'].items()),
            'Confirmation saved artifacts differ')
    total=reconcile(folder,batch['slots'],source)
    require(total==receipt['total'],'Confirmation ledger does not reconcile')
    require(total['failed']==total['interrupted']==0,
            'Failed or interrupted confirmation requires an explicit failure audit before classification')
    require(batch['pins']==hashes(source,batch['pins'])
            and all(digest((ROOT/name).read_bytes())==sha for name,sha in batch['pins'].items()),'Frozen confirmation sources differ')
    native_runtime={n:h for n,h in batch['pins'].items() if n.startswith('src/aegis_dc/') and n.endswith('.py')
                    or n=='src/patrol_rsi/contracts.py'}
    results={}
    for slot in batch['slots']:
        run_dir=folder/f"{slot['index']:02}-{slot['world_id']}-{slot['arm']}"
        if not run_dir.exists():continue
        terminal=read(run_dir/'terminal.json')
        row=dict(status=terminal['status'],world_id=slot['world_id'],arm=slot['arm'],family=slot['family'])
        if terminal['status']=='COMPLETED':
            original=read(run_dir/'originals.json')
            require(digest((run_dir/'originals.zip').read_bytes())==original['archive_sha256'],'Native archive SHA differs')
            with ZipFile(run_dir/'originals.zip') as archive:
                require(len(archive.namelist())==4 and set(archive.namelist())==set(original['members']),'Native archive membership differs')
                members={n:archive.read(n) for n in archive.namelist()}
            require(all(digest(raw)==original['members'][n] for n,raw in members.items()),'Native member SHA differs')
            run=json.loads(members['run.json'])
            input_path=ROOT/PREP/'inputs'/slot['input_member']
            require(digest(input_path.read_bytes())==slot['input_sha256'],'Original confirmation input differs')
            doc=read(input_path)
            require(json.loads(members['scenario.json'])==doc['model'] and run['code_identity']['git_commit']==source
                and run['code_identity']['files']==native_runtime and not run['code_identity']['implementation_has_changes'],
                'Confirmation physical source or model differs')
            trace=[json.loads(x) for x in members['private-state.jsonl'].splitlines()]
            balances=[json.loads(x) for x in members['balances.jsonl'].splitlines()]
            audit=check_run(doc,run,trace,balances)
            require(audit==read(run_dir/'audit.json'),'Saved confirmation metrics differ')
            row.update(totals=audit['totals'],work=audit['task_dispositions'],resource_contention=audit['resource_contention_frames'],
                       _run=run,_audit=audit)
        results[(slot['world_id'],slot['arm'])]=row
    pairs=[]
    for world in plan['phases']['confirmation']['worlds']:
        b=results.get((world['id'],'one_observation_lookahead'))
        c=results.get((world['id'],'evidence_consistent_contingent'))
        complete=bool(b and c and b['status']==c['status']=='COMPLETED')
        diagnostic=_same_history_divergence(b['_run'],c['_run'],b['_audit'],c['_audit']) if complete else None
        pairs.append(dict(world_id=world['id'],baseline=b['totals'] if b and b['status']=='COMPLETED' else None,
            candidate=c['totals'] if c and c['status']=='COMPLETED' else None,
            identified_first_difference=bool(diagnostic and diagnostic['identified']),hard_violations=[],
            opportunity=diagnostic))
    facts=dict(schema='aegisdc-comparison-analysis-facts-v1',
        pairs=[{k:v for k,v in row.items() if k!='opportunity'} for row in pairs])
    result=summarize(plan,facts)
    result.update(source_verification='PASS_EXACT_SAVED_NATIVE_INPUTS_AND_CODE',execution_commit=source,
        ledger_totals=total,batch_status=receipt['status'],opportunities={r['world_id']:r['opportunity'] for r in pairs},
        runs=[{k:v for k,v in r.items() if not k.startswith('_')} for r in results.values()])
    return result,facts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result,facts=analyze(args.capture.resolve())
    args.output.mkdir()
    for name,obj in (('results.json',result),('verified-facts.json',facts)):
        with (args.output/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('pairs','runs','opportunities')},ensure_ascii=False))

if __name__=='__main__':main()
