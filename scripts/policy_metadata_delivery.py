"""Exact legacy metadata classification and two separately frozen public checks."""
import argparse
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import sys
import policy_correction_delivery as policy
from inspection_delivery import git,hashes,require,read,digest,write,durable,unchanged

ROOT=Path(__file__).resolve().parents[1];PACKAGE=policy.PACKAGE
PROTOCOL='docs/mainline/25-policy-metadata-correction-01.json'


def exact_metadata_source(protocol,revision):
    name=protocol['runtime_changed_path'];before=git('cat-file','blob',protocol['prior_runtime_source']+':'+name)
    old=protocol['original_metadata_line'].encode();new=protocol['corrected_metadata_line'].encode()
    require(before.count(old)==1,'Original metadata line differs')
    require(before.replace(old,new)==git('cat-file','blob',revision+':'+name),'Undeclared runtime change')


def verify_policy_history(protocol,delivery):
    exact_metadata_source(protocol,delivery)
    correction=read(ROOT/policy.PROTOCOL);policy.predecessor(correction)
    folder=ROOT/PACKAGE/'capture-02';receipt=read(folder/'receipt.json')
    require(receipt['status']=='PASS' and receipt['physical_attempts']==receipt['physical_completed']==receipt['validated_new_cases']==11
        and receipt['reused_cases_validated']==2 and receipt['failures']==0,'Original policy correction accounting differs')
    for role,identities in receipt['pinned'].items():
        require(identities==hashes(receipt['execution_commit'],identities),'Recorded policy execution source differs: '+role)
        current=hashes(delivery,identities)
        for name,expected in identities.items():
            if name!=protocol['runtime_changed_path']:require(current[name]==expected and digest((ROOT/name).read_bytes())==expected,'Unclassified policy source differs: '+name)
    for name,expected in receipt['artifacts'].items():require(digest((folder/name).read_bytes())==expected,'Original policy artifact differs')
    sidecar=read(ROOT/protocol['sidecar']);require(sidecar['originals_unchanged'] and len(sidecar['entries'])==15,'Sidecar coverage differs')
    declared={p.relative_to(ROOT).as_posix() for c in ('capture-01','capture-02') for p in (ROOT/PACKAGE/c).glob('*/run.json')}
    require({r['path'] for r in sidecar['entries']}==declared,'Sidecar run set differs')
    for row in sidecar['entries']:
        path=ROOT/row['path'];run=read(path)
        require(digest(path.read_bytes())==row['sha256'] and run['dispatch_interface']==row['original_emitted_value']=='NOT_IMPLEMENTED'
            and run['code_identity']['git_commit']==row['execution_commit'] and 'policy_public_decisions' in run
            and row['sidecar_classification']=='PUBLIC_SELECTION_WITH_PRIVATE_EXECUTION','Sidecar changed or misclassified original')
    require(policy.check_saved(folder,correction)==read(folder/'checks.json'),'Original saved policy checks differ')
    return dict(status='PASS',original_policy_calls=13,original_policy_simulated_duration_s=30,historical_run_classifications=15,
        old_source_verified=True,current_source_change='EXACT_ONE_METADATA_LINE_ONLY',physical_rerun=False)


def pins(protocol,revision):
    groups=policy.pins(read(ROOT/policy.PROTOCOL),revision)
    groups['tools']=hashes(revision,[*groups['tools'],protocol['authoring_tool']])
    names=[PACKAGE+'/capture-02/'+n for n in durable(ROOT/PACKAGE/'capture-02')]
    groups['inputs']=hashes(revision,[*groups['inputs'],PROTOCOL,protocol['revision_note'],protocol['sidecar'],*names])
    return groups


def declared(protocol):
    return set(protocol['durable_root'])|{c['id']+'/'+n for c in protocol['cases'] for n in protocol['durable_case']}


def check_case(folder,case,protocol):
    path=folder/case['id'];run=read(path/'run.json')
    require(run['dispatch_interface']==case['expected_interface'],'Public dispatch metadata classification differs')
    require(('policy_public_decisions' in run)==case['dispatch'],'Dispatch enabled metadata differs from actual records')
    require(run['work_records']==[],'Metadata fixture created work')
    if case['dispatch']:require(len(run['policy_public_decisions'])==1 and run['policy_public_decisions'][0]['choice']['chosen_candidate_id'] is None,'No-human metadata fixture dispatched work')
    for name,expected in protocol['expected_summary'].items():require(math.isclose(run['summary'][name],expected,abs_tol=protocol['absolute_tolerance'],rel_tol=0),'Metadata fixture service witness differs')
    for name,identity in run['artifacts'].items():require(digest((path/name).read_bytes())==identity['sha256'],'Metadata fixture saved artifact differs')
    require(run['research_trials']==run['model_calls']==run['training_calls']==0,'Metadata fixture became research')
    return dict(status='PASS',interface=run['dispatch_interface'],actual_work=0,summary=run['summary'])


def capture(folder,protocol):
    require(not git('status','--porcelain'),'Use clean frozen metadata checkout')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set PYTHONPATH=src')
    source=git('rev-parse','HEAD').decode().strip();verify_policy_history(protocol,source);identities=pins(protocol,source)
    require(unchanged(source,identities),'Metadata source pin differs');folder.mkdir(exist_ok=False)
    write(folder/'attempt.json',dict(execution_commit=source,classification=protocol['classification'],executable=sys.executable,
        executable_sha256=digest(Path(sys.executable).read_bytes()),python=sys.version,argv=sys.argv,declared_new_physical_runs=2,original_policy_reruns=0))
    receipt=dict(schema='aegisdc-policy-metadata-engineering-receipt-v1',execution_commit=source,pinned=identities,
        physical_attempts=0,physical_completed=0,validated_cases=0,failures=0,registered_research_trials=0,original_policy_reruns=0)
    try:
        from aegis_dc.plant import simulate_scenario,save_run
        inputs=read(ROOT/protocol['input'])
        for case in protocol['cases']:
            require(unchanged(source,identities),'Source changed before metadata case');receipt['physical_attempts']+=1
            policy.original.append(folder/'attempts.jsonl',dict(case=case['id'],status='STARTED',execution_commit=source))
            try:
                program=deepcopy(inputs['dispatch_program']) if case['dispatch'] else None
                if program is not None:program['decision_times_s']=[0]
                result=simulate_scenario(inputs['model'],duration_s=.01,step_s=.01,dispatch_program=program)
                save_run(result,folder/case['id']);receipt['physical_completed']+=1
                check_case(folder,case,protocol);receipt['validated_cases']+=1
                policy.original.append(folder/'attempts.jsonl',dict(case=case['id'],status='COMPLETED',execution_commit=source))
            except Exception as error:
                policy.original.append(folder/'attempts.jsonl',dict(case=case['id'],status='FAILED',error_type=type(error).__name__,error=str(error)));raise
        write(folder/'checks.json',dict(status='PASS',cases={c['id']:check_case(folder,c,protocol) for c in protocol['cases']},
            historical_policy=verify_policy_history(protocol,source),original_policy_calls=13,new_metadata_calls=2,all_engineering_calls=15,all_engineering_simulated_duration_s=30.02))
        require(durable(folder)==declared(protocol),'Metadata durable set differs');receipt['status']='PASS'
    except Exception as error:receipt.update(status='FAIL',failures=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=unchanged(source,identities)
        if not receipt['source_head_and_bytes_unchanged']:
            receipt.update(status='FAIL',failures=1,source_guard_error='Metadata source changed');receipt.setdefault('error_type','SourceGuardError');receipt.setdefault('error','Metadata source changed')
        receipt['artifacts']={n:digest((folder/n).read_bytes()) for n in sorted(durable(folder))};write(folder/'receipt.json',receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Metadata source changed')
    return dict(status=receipt['status'],source=source,new_metadata_calls=2,policy_reruns=0,all_engineering_calls=15,all_engineering_duration_s=30.02)


def verify(folder,protocol,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery and not git('status','--porcelain'),'Use clean requested delivery checkout')
    history=verify_policy_history(protocol,delivery);receipt=read(folder/'receipt.json');source=receipt['execution_commit']
    require(receipt['status']=='PASS' and receipt['physical_attempts']==receipt['physical_completed']==receipt['validated_cases']==2 and receipt['failures']==0 and receipt['source_head_and_bytes_unchanged'],'Metadata check accounting differs')
    require(durable(folder)==declared(protocol)|{'receipt.json'} and set(receipt['artifacts'])==declared(protocol),'Metadata durable declaration differs')
    for n,h in hashes(delivery,[(folder/n).relative_to(ROOT).as_posix() for n in durable(folder)]).items():require(digest((ROOT/n).read_bytes())==h,'Metadata committed artifact differs')
    for n,h in receipt['artifacts'].items():require(digest((folder/n).read_bytes())==h,'Metadata original differs')
    require(receipt['pinned']==pins(protocol,source),'Metadata pin groups differ')
    for role,identities in receipt['pinned'].items():require(identities==hashes(delivery,identities) and all(digest((ROOT/n).read_bytes())==h for n,h in identities.items()),'Metadata execution/delivery source differs: '+role)
    ledger=policy.original.rows(folder/'attempts.jsonl');require(len(ledger)==4,'Metadata attempt rows differ')
    for i,case in enumerate(protocol['cases']):
        pair=ledger[2*i:2*i+2];require([r['status'] for r in pair]==['STARTED','COMPLETED'] and all(r['case']==case['id'] and r['execution_commit']==source for r in pair),'Metadata attempt/source differs')
        run=read(folder/case['id']/'run.json');require(run['code_identity']['git_commit']==source and not run['code_identity']['implementation_has_changes'],'Metadata actual source differs')
        check_case(folder,case,protocol)
    return dict(status='PASS',source=source,delivery=delivery,historical_policy=history,new_metadata_calls=2,
        artifacts=len(receipt['artifacts']),pins={k:len(v) for k,v in receipt['pinned'].items()},physical_rerun=False,full_regression_rerun=False,all_engineering_calls=15,all_engineering_simulated_duration_s=30.02)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['capture','verify']);parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--delivery')
    args=parser.parse_args();folder=(ROOT/args.capture).resolve();require(folder.parent==ROOT/PACKAGE,'Use unique declared metadata output')
    protocol=read(ROOT/PROTOCOL);print(json.dumps(capture(folder,protocol) if args.mode=='capture' else verify(folder,protocol,args.delivery),ensure_ascii=False))
