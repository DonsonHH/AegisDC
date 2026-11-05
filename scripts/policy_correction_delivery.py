"""Explicit FIFO-oracle correction with zero reruns of completed physical cases."""
import argparse
import json
import os
from pathlib import Path
import sys
import policy_delivery as original
from inspection_delivery import git,hashes,require,read,digest,write,durable,unchanged

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/25-policy-engineering-correction-01.json'
PACKAGE=original.PACKAGE


def pins(protocol,revision):
    base=original.pins(read(ROOT/protocol['original_protocol']),revision)
    base['tools']=hashes(revision,[*base['tools'],protocol['authoring_tool']])
    original_names=[protocol['original_capture']+'/'+n for n in durable(ROOT/protocol['original_capture'])]
    base['inputs']=hashes(revision,[*base['inputs'],PROTOCOL,protocol['revision_note'],*original_names])
    return base


def predecessor(protocol):
    folder=ROOT/protocol['original_capture'];receipt=read(folder/'receipt.json')
    require(receipt['execution_commit']==protocol['original_execution'] and receipt['status']=='FAIL'
        and receipt['physical_attempts']==receipt['physical_completed']==2 and receipt['validated_cases']==1
        and receipt['failures']==1 and receipt['error']=='Literal selection sequence differs: fifo'
        and receipt['source_head_and_bytes_unchanged'],'Original failed attempt identity differs')
    names=durable(folder);require(names==set(receipt['artifacts'])|{'receipt.json'},'Original durable set differs')
    originals=hashes(protocol['original_delivery'],[protocol['original_capture']+'/'+n for n in names])
    require(all(digest((ROOT/n).read_bytes())==h for n,h in originals.items()),'Original failure was rewritten')
    for n,h in receipt['artifacts'].items():require(digest((folder/n).read_bytes())==h,'Original failed artifact differs')
    for role,identities in receipt['pinned'].items():require(identities==hashes(protocol['original_execution'],identities),'Original source roles differ: '+role)
    ledger=original.rows(folder/'attempts.jsonl')
    require([r['status'] for r in ledger]==['STARTED','COMPLETED','STARTED','FAILED']
        and [r['case'] for r in ledger]==['no-human','no-human','fifo','fifo'],'Original failure ledger differs')
    return originals


def figures(folder,checks,protocol):
    outputs=original.figures(folder,checks,protocol)
    old=b'Actual inspection ends 1.25 s; observation arrives 1.75 s; selected action ends 3 s.'
    new=b'FIFO: action 1.25 s, later measurement 3 s / arrival 3.5 s; risk/lookahead: inspection 1.25 s, action 3 s.'
    require(old in outputs['policy-decisions.svg'],'Original figure template differs')
    outputs['policy-decisions.svg']=outputs['policy-decisions.svg'].replace(old,new)
    return outputs


def check_saved(folder,protocol):
    return original.check_saved(folder,protocol)


def reuse(folder,protocol):
    before=predecessor(protocol);copies={}
    for case in protocol['reused_cases']:
        destination=folder/case;destination.mkdir(exist_ok=False)
        for name in protocol['durable_case']:
            source=ROOT/protocol['original_capture']/case/name
            write(destination/name,source.read_bytes());copies[case+'/'+name]=dict(original=source.relative_to(ROOT).as_posix(),sha256=digest(source.read_bytes()))
        spec=next(c for c in protocol['cases'] if c['id']==case)
        original.check_case(folder,spec,protocol)
    write(folder/'reused-originals.json',dict(classification='BYTE_IDENTICAL_REUSE_NO_NEW_PHYSICAL_CALL',original_failed_capture=protocol['original_capture'],
        original_failed_receipt_sha256=digest((ROOT/protocol['original_capture']/'receipt.json').read_bytes()),copies=copies,original_artifacts=before))


def capture(folder,protocol):
    require(not git('status','--porcelain'),'Use clean frozen correction checkout')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set PYTHONPATH=src')
    source=git('rev-parse','HEAD').decode().strip();identities=pins(protocol,source);require(unchanged(source,identities),'Source pin differs')
    old=read(ROOT/protocol['original_capture']/'receipt.json')
    require(identities['runtime']==old['pinned']['runtime'],'Oracle correction changed physical runtime')
    folder.mkdir(exist_ok=False)
    write(folder/'attempt.json',dict(classification=protocol['classification'],execution_commit=source,argv=sys.argv,
        executable=sys.executable,python=sys.version,executable_sha256=digest(Path(sys.executable).read_bytes()),
        declared_new_physical_runs=protocol['new_physical_runs'],reused_cases=protocol['reused_cases'],declared_cumulative_physical_runs=protocol['cumulative_physical_runs']))
    receipt=dict(schema='aegisdc-policy-engineering-correction-receipt-v1',execution_commit=source,pinned=identities,
        physical_attempts=0,physical_completed=0,validated_new_cases=0,reused_cases_validated=0,failures=0,
        simulated_duration_attempted_s=0,original_validation_failure_retained=True,registered_research_trials=0,llm_calls=0,
        training_calls=0,field_calibration='PENDING',global_regression_gate='PENDING_ROOT_INTEGRATED_FULL')
    try:
        reuse(folder,protocol);receipt['reused_cases_validated']=len(protocol['reused_cases'])
        from aegis_dc.plant import simulate_scenario,save_run
        for case in protocol['cases']:
            if case['id'] in protocol['reused_cases']:continue
            require(unchanged(source,identities),'Source changed before case');inputs=read(ROOT/case['input'])
            receipt['physical_attempts']+=1;receipt['simulated_duration_attempted_s']+=case['duration_s']
            original.append(folder/'attempts.jsonl',dict(case=case['id'],status='STARTED',execution_commit=source,duration_s=case['duration_s']))
            try:
                result=simulate_scenario(inputs['model'],duration_s=case['duration_s'],step_s=protocol['maximum_step_s'],dispatch_program=inputs['dispatch_program'])
                save_run(result,folder/case['id']);receipt['physical_completed']+=1
                original.check_case(folder,case,protocol);receipt['validated_new_cases']+=1
                original.append(folder/'attempts.jsonl',dict(case=case['id'],status='COMPLETED',execution_commit=source))
            except Exception as error:
                original.append(folder/'attempts.jsonl',dict(case=case['id'],status='FAILED',error_type=type(error).__name__,error=str(error)));raise
        checks=check_saved(folder,protocol);write(folder/'checks.json',checks)
        for name,raw in figures(folder,checks,protocol).items():write(folder/name,raw)
        require(durable(folder)==original.declared(protocol),'Durable correction set differs');receipt['status']='PASS'
    except Exception as error:
        receipt.update(status='FAIL',failures=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=unchanged(source,identities)
        if not receipt['source_head_and_bytes_unchanged']:
            receipt.update(status='FAIL',failures=1,source_guard_error='Source changed during capture')
            receipt.setdefault('error_type','SourceGuardError');receipt.setdefault('error','Source changed during capture')
        receipt['artifacts']={n:digest((folder/n).read_bytes()) for n in sorted(durable(folder))};write(folder/'receipt.json',receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Source changed during capture')
    return dict(status=receipt['status'],execution=source,new_physical_calls=receipt['physical_attempts'],reused_physical_outputs=receipt['reused_cases_validated'],
        cumulative_physical_calls=protocol['cumulative_physical_runs'],cumulative_simulated_duration_s=protocol['cumulative_simulated_duration_s'],artifacts=len(receipt['artifacts']))


def verify(folder,protocol,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),'Use clean requested delivery checkout')
    predecessor(protocol);receipt=read(folder/'receipt.json');source=receipt['execution_commit']
    require(receipt['status']=='PASS' and receipt['failures']==0 and receipt['source_head_and_bytes_unchanged'],'Correction did not pass')
    require(receipt['physical_attempts']==receipt['physical_completed']==receipt['validated_new_cases']==protocol['new_physical_runs']
        and receipt['reused_cases_validated']==len(protocol['reused_cases']) and receipt['simulated_duration_attempted_s']==protocol['new_simulated_duration_s'],'New/reused budget differs')
    require(durable(folder)==original.declared(protocol)|{'receipt.json'} and set(receipt['artifacts'])==original.declared(protocol),'Durable declaration differs')
    for n,h in hashes(delivery,[(folder/n).relative_to(ROOT).as_posix() for n in durable(folder)]).items():require(digest((ROOT/n).read_bytes())==h,'Correction delivery blob differs')
    for n,h in receipt['artifacts'].items():require(digest((folder/n).read_bytes())==h,'Correction artifact differs')
    require(receipt['pinned']==pins(protocol,source),'Correction pin roles differ')
    for role,identities in receipt['pinned'].items():
        require(identities==hashes(delivery,identities) and all(digest((ROOT/n).read_bytes())==h for n,h in identities.items()),'Execution/delivery differs: '+role)
    index=read(folder/'reused-originals.json');require(index['classification']=='BYTE_IDENTICAL_REUSE_NO_NEW_PHYSICAL_CALL','Reuse classification differs')
    for name,item in index['copies'].items():require(digest((folder/name).read_bytes())==item['sha256']==digest((ROOT/item['original']).read_bytes()),'Reused original was changed')
    ledger=original.rows(folder/'attempts.jsonl');new_cases=[c for c in protocol['cases'] if c['id'] not in protocol['reused_cases']]
    require(len(ledger)==2*len(new_cases),'New attempt ledger count differs')
    for i,case in enumerate(new_cases):
        pair=ledger[2*i:2*i+2];require([r['status'] for r in pair]==['STARTED','COMPLETED'] and all(r['case']==case['id'] and r['execution_commit']==source for r in pair),'New ledger/source differs')
    for case in protocol['cases']:
        run=read(folder/case['id']/'run.json');expected_source=protocol['original_execution'] if case['id'] in protocol['reused_cases'] else source
        require(run['code_identity']['git_commit']==expected_source and not run['code_identity']['implementation_has_changes'],'Actual run revision differs')
    checks=check_saved(folder,protocol);require(checks==read(folder/'checks.json'),'Saved correction checks differ')
    for name,raw in figures(folder,checks,protocol).items():require(raw==(folder/name).read_bytes(),'Saved correction figure differs')
    return dict(status='PASS',execution=source,delivery=delivery,new_physical_calls=protocol['new_physical_runs'],reused_original_cases=receipt['reused_cases_validated'],
        cumulative_physical_calls=protocol['cumulative_physical_runs'],artifacts=len(receipt['artifacts']),original_failed_artifacts=len(predecessor(protocol)),
        pins={role:len(identities) for role,identities in receipt['pinned'].items()},physical_rerun=False,full_regression_rerun=False,inference_rerun=False,runtime_caches_required=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['capture','verify']);parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--delivery');args=parser.parse_args();folder=(ROOT/args.capture).resolve()
    require(folder.parent==ROOT/PACKAGE,'Use unique declared correction output');protocol=read(ROOT/PROTOCOL)
    print(json.dumps(capture(folder,protocol) if args.mode=='capture' else verify(folder,protocol,args.delivery),ensure_ascii=False))
