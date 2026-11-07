"""Run only the registered development phase, from the exact precompiled originals."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from comparison_release import AUTHORITY, LOCK, PROTOCOL, audit_lock
from inspection_delivery import ROOT, digest, durable, git, hashes, require, write
from registered_comparison import read
from verify_comparison_delivery import _verified_input_originals
from development_journal import append as journal_append, write_record as journal_write, reconcile as reconcile_journal

PREP='evidence/mainline/engineering/30-comparison-preparation'
MEMBER_PREFIX='input-preparation/30-development-inputs-02'
PHASE='development'


def head():
    return git('rev-parse','HEAD').decode().strip()


def committed(path):
    raw=(ROOT/path).read_bytes()
    require(raw==git('cat-file','blob',f'{head()}:{path}'),'Committed input bytes differ: '+path)
    return json.loads(raw)


def load_roster():
    authority=committed(AUTHORITY)
    require(authority['status']=='ACCEPTED' and authority['ticket']=='30'
            and authority['protocol']==PROTOCOL and authority['protocol_lock']==LOCK,
            'Requires accepted ticket 30 and its frozen protocol')
    committed(LOCK)
    lock=audit_lock(ROOT/LOCK)
    require(authority['design_commit']==lock['design_commit']
            and authority['protocol_lock_sha256']==digest((ROOT/LOCK).read_bytes()),
            'Acceptance does not bind the frozen design')
    protocol=read(ROOT/PROTOCOL)
    phase=protocol['phases'][PHASE]
    roles=read(ROOT/PREP/'manifest.json')
    archive=ROOT/PREP/'preparation-originals.zip'
    require(digest(archive.read_bytes())==roles['archive_sha256'],'Prepared originals archive differs')
    slots=[]
    originals={}
    with ZipFile(archive) as source:
        require(len(source.namelist())==len(set(source.namelist())),'Repeated archived member')
        for row in phase['worlds']:
            arms=phase['arms']
            shift=(row['slot']-1)%len(arms)
            for arm in arms[shift:]+arms[:shift]:
                member=f"{MEMBER_PREFIX}/{row['id']}/{arm}.json"
                raw=source.read(member)
                sha=digest(raw)
                require(roles['members'][member]==sha,'Development original bytes differ')
                slot=dict(index=len(slots)+1,world_id=row['id'],family=row['family'],arm=arm,
                          duration_s=row['duration_s'],scheduled_decisions=len(protocol['decision_times_s']),
                          input_member=member,input_sha256=sha)
                slots.append(slot)
                originals[member]=raw
        receipt=f'{MEMBER_PREFIX}/receipt.json'
        raw=source.read(receipt)
        require(digest(raw)==roles['members'][receipt],'Preparation receipt differs')
        require(_verified_input_originals(dict(originals,**{receipt:raw}),protocol)==36,'Development input parity differs')
    budget=phase['budget']
    require(budget==dict(attempts=len(slots),simulated_charge_s=sum(s['duration_s'] for s in slots),
        scheduled_decisions=sum(s['scheduled_decisions'] for s in slots)),
        'Development schedule does not match the frozen budget')
    return protocol,slots,originals


RUNBOOK='docs/mainline/31-development-execution.json'
PACKAGE='evidence/mainline/research/31-development'
NATIVE=('scenario.json','run.json','private-state.jsonl','balances.jsonl')


def _execution_pins(source,lock):
    names=set(lock['pins'])|{AUTHORITY,LOCK,RUNBOOK,
        'scripts/registered_development.py','scripts/development_run_evidence.py',
        'tests/test_registered_development.py','scripts/development_journal.py'}
    return hashes(source,names)


def _guard(source,pins):
    require(head()==source and all(digest((ROOT/name).read_bytes())==sha for name,sha in pins.items()),
            'Live executable, input or HEAD differs from the frozen registered source')


def _begin(folder,stage,source,protocol,slots):
    book=committed(RUNBOOK)
    require(book['schema']=='aegisdc-development-execution-v1' and book['phase']==PHASE
            and book['classification']=='REGISTERED_DEVELOPMENT_NOT_CONFIRMATION'
            and book['protocol']==PROTOCOL and book['protocol_lock']==LOCK
            and book['budget']==protocol['phases'][PHASE]['budget']
            and book['durable_native_members']==list(NATIVE)
            and book['automatic_retries']==0, 'Declared execution runbook differs')
    require(folder==ROOT/PACKAGE/book['capture_directory'] and not folder.exists(),
            'Use the declared unique development output directory')
    require(stage==ROOT/'.work'/book['native_staging_directory'] and not stage.exists(),
            'Use the declared unique native staging directory')
    progress=committed('docs/mainline/progress.json')
    require(progress['current_ticket']=='31' and progress['research_trials']['status']=='frozen_not_started'
            and progress['research_trials']['attempts']==0,'Requires the unstarted registered development frontier')
    require(head()==source and not git('status','--porcelain'),'Use clean exact registered development source')
    require(sys.dont_write_bytecode and sys.pycache_prefix is not None
            and not Path(sys.pycache_prefix).exists(),'Use -B and an unused PYTHONPYCACHEPREFIX')
    lock=read(ROOT/LOCK)
    pins=_execution_pins(source,lock)
    _guard(source,pins)
    folder.mkdir(parents=True)
    stage.mkdir(parents=True)
    receipt=dict(schema='aegisdc-registered-development-batch-v1',phase=PHASE,classification=book['classification'],
        execution_commit=source,protocol_sha256=digest((ROOT/PROTOCOL).read_bytes()),
        design_lock_sha256=digest((ROOT/LOCK).read_bytes()),budget=book['budget'],pins=pins,slots=slots,
        python=sys.version,interpreter_sha256=digest(Path(sys.executable).read_bytes()),
        unused_cache_prefix=True,held_inputs_read=0,held_seed_reads=0,automatic_retries=0)
    write(folder/'batch.json',receipt)
    return pins


def _save_native(native,folder,program,result,source):
    from aegis_dc.plant import save_run
    from development_run_evidence import check_run

    run=save_run(result,native)
    require(set(durable(native))==set(NATIVE),'Native returned members differ from declaration')
    originals=folder/'originals.zip'
    with ZipFile(originals,'x',compression=ZIP_DEFLATED,compresslevel=4) as archive:
        members={}
        for name in NATIVE:
            raw=(native/name).read_bytes()
            members[name]=digest(raw)
            archive.writestr(name,raw)
    # Exact raw return is archived before any verifier can reject it.
    write(folder/'originals.json',dict(archive_sha256=digest(originals.read_bytes()),members=members))
    require(run['code_identity']['git_commit']==source and run['code_identity']['implementation_has_changes'] is False,
            'Physical runtime identity differs from the registered execution commit')
    require(read(native/'scenario.json')==program['model'],'Returned scenario differs from its registered input')
    for name,item in run['artifacts'].items():
        require(members[name]==item['sha256'],'Native artifact manifest differs')
    audit=check_run(program,run,result['trace'],result['balances'])
    write(folder/'audit.json',audit)
    return len(result['policy_public_decisions'])


def capture(source,folder,stage):
    protocol,slots,originals=load_roster()
    pins=_begin(folder,stage,source,protocol,slots)
    ledger=folder/'attempts.jsonl'
    stop=None
    status='PASS'
    attempted=set()
    invoked=returned=0
    try:
        sys.path.insert(0,str(ROOT/'src'))
        from aegis_dc.plant import simulate_scenario

        for slot in slots:
            try:
                _guard(source,pins)
            except BaseException as exc:
                stop=dict(index=slot['index'],kind='SOURCE_GUARD_FAILURE',reason=str(exc))
                status='STOPPED'
                break
            index=slot['index']
            folder_slot=folder/f"{index:02}-{slot['world_id']}-{slot['arm']}"
            folder_slot.mkdir()
            program=json.loads(originals[slot['input_member']])
            require(index==len(attempted)+1 and index<=protocol['phases'][PHASE]['budget']['attempts'],
                    'Registered phase attempt budget exhausted')
            start=dict(slot,status='STARTED',source=source,charged_simulated_s=slot['duration_s'],
                       charged_scheduled_decisions=slot['scheduled_decisions'])
            # The fsynced journal append is the charge commit point. If any
            # recorder operation is uncertain, stop without UNRUN synthesis.
            journal_append(ledger,start)
            journal_write(folder_slot/'start.json',start)
            attempted.add(index)
            terminal=dict(slot,status='FAILED',source=source,physical_call_started=False,physical_returned=False)
            try:
                terminal['physical_call_started']=True
                invoked+=1
                result=simulate_scenario(program['model'],duration_s=program['duration_s'],
                    step_s=program['maximum_step_s'],boundary_events=program['boundary_events'],
                    dispatch_program=program['dispatch_program'])
                terminal['physical_returned']=True
                returned+=1
                terminal['returned_decisions']=len(result['policy_public_decisions'])
                decisions=_save_native(stage/f'{index:02}',folder_slot,program,result,source)
                require(decisions==slot['scheduled_decisions'],'Actual decision count differs from frozen slot')
                _guard(source,pins)
                terminal['status']='COMPLETED'
            except BaseException as exc:
                interrupted=isinstance(exc,KeyboardInterrupt)
                terminal.update(status='INTERRUPTED' if interrupted else 'FAILED',
                    error_type=type(exc).__name__,error=str(exc))
                stop=dict(index=index,kind='INTERRUPTED' if interrupted else 'UNCLASSIFIED_OR_CONTRACT_FAILURE',
                          reason=str(exc))
                status='STOPPED'
            terminal['artifacts']={name:digest((folder_slot/name).read_bytes()) for name in sorted(durable(folder_slot))}
            journal_write(folder_slot/'terminal.json',terminal)
            journal_append(ledger,terminal)
            if stop is not None:
                break
        for slot in slots:
            if slot['index'] not in attempted:
                journal_append(ledger,dict(slot,status='UNRUN',source=source,reason='BATCH_STOPPED_WITHOUT_NEW_ATTEMPT'))
        total=reconcile_journal(folder,slots,source)
    except BaseException as exc:
        # This is explicitly not an authoritative reconciled attempt receipt.
        # Original partial writes remain intact for a later accounting audit.
        unknown=dict(status='RECORDER_INCOMPLETE',phase=PHASE,execution_commit=source,
            error_type=type(exc).__name__,error=str(exc),authoritative_totals=None,
            in_memory_physical_invocations=invoked,in_memory_returned_runs=returned,
            automatic_retries=0,held_inputs_read=0,held_seed_reads=0,
            observed_files={name:digest((folder/name).read_bytes()) for name in sorted(durable(folder))})
        write(folder/'recorder-incomplete.json',unknown)
        print(json.dumps({k:v for k,v in unknown.items() if k!='observed_files'},ensure_ascii=False))
        return 4
    try:
        _guard(source,pins)
        source_unchanged=True
    except ValueError:
        source_unchanged=False
        status='STOPPED'
    artifacts={name:digest((folder/name).read_bytes()) for name in sorted(durable(folder))}
    receipt=dict(status=status,phase=PHASE,execution_commit=source,source_unchanged=source_unchanged,
        total=total,stop=stop,artifacts=artifacts,registered_research_trials=total['started'],
        held_inputs_read=0,held_seed_reads=0,llm_calls=0,training_calls=0,automatic_retries=0,
        field_calibration='PENDING')
    write(folder/'receipt.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','phase','execution_commit','total','stop')},ensure_ascii=False))
    return 0 if status=='PASS' else 3

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_subparsers(dest='mode',required=True)
    modes.add_parser('plan')
    runner=modes.add_parser('capture')
    runner.add_argument('--source',required=True)
    runner.add_argument('--output',type=Path,required=True)
    runner.add_argument('--native-staging',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.mode=='capture':
            return capture(args.source,args.output.resolve(),args.native_staging.resolve())
        protocol,slots,_=load_roster()
        print(json.dumps(dict(status='PASS_DEVELOPMENT_PLAN_ONLY',phase=PHASE,slots=slots,
            budget=protocol['phases'][PHASE]['budget'],facility_calls=0,selector_calls=0,
            held_inputs_read=0,seed_reads=0,registered_research_trials=0),allow_nan=False))
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as exc:
        parser.exit(2,f'{exc}\n')


if __name__=='__main__':
    raise SystemExit(main())
