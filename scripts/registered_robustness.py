"""Execute exactly the16 original robustness slots after a corrected-source freeze."""

import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys

from comparison_release import _read_nonce
from robustness_release import ROOT,LOCK,PROTOCOL,NONCE,verify_freeze,EXECUTION_LOCK,AUTHORIZATION,EXTENSION
from inspection_delivery import digest,durable,git,hashes,require,write
from registered_comparison import read,audit_pair
from development_journal import append as journal_append,write_record as journal_write,reconcile as reconcile_journal
from registered_development import _guard,_save_native

PHASE='robustness'
FREEZE='evidence/mainline/research/36-robustness/prepared-01'
PACKAGE='evidence/mainline/research/36-robustness'
RUNBOOK='docs/mainline/36-robustness-execution.json'


def head():
    return git('rev-parse','HEAD').decode().strip()


def load_roster():
    verify_freeze();lock=read(ROOT/LOCK)
    plan=read(ROOT/PROTOCOL)
    prepared=read(ROOT/FREEZE/'receipt.json')
    require(prepared['status']=='PASS_INPUT_ONLY' and prepared['prepared_inputs']==16
            and prepared['physical_calls']==prepared['selector_calls']==0,'Robustness preparation incomplete')
    actual={path.relative_to(ROOT/FREEZE).as_posix() for path in (ROOT/FREEZE).rglob('*') if path.is_file()}
    require(actual==set(prepared['artifacts'])|{'receipt.json'}
            and all(digest((ROOT/FREEZE/name).read_bytes())==sha for name,sha in prepared['artifacts'].items()),
            'Robustness prepared originals differ')
    phase=plan['phases'][PHASE]
    originals,slots={},[]
    for world in phase['worlds']:
        arms=phase['arms']
        shift=(world['slot']-1)%len(arms)
        for arm in arms[shift:]+arms[:shift]:
            name=world['id']+'/'+arm+'.json'
            raw=(ROOT/FREEZE/'inputs'/name).read_bytes()
            require(digest(raw)==prepared['input_hashes'][name],'Robustness input byte identity differs')
            slots.append(dict(index=len(slots)+1,world_id=world['id'],family=world['family'],arm=arm,
                duration_s=world['duration_s'],scheduled_decisions=len(plan['decision_times_s']),
                input_member=name,input_sha256=digest(raw)))
            originals[name]=raw
        audit_pair((ROOT/FREEZE/'inputs'/world['id']/'one_observation_lookahead.json',
                    ROOT/FREEZE/'inputs'/world['id']/'evidence_consistent_contingent.json'))
    return plan,slots,originals


def _begin(folder,stage,source,plan,slots):
    require(head()==source and not git('status','--porcelain'),'Use the clean accepted execution checkout')
    book=read(ROOT/RUNBOOK)
    require(folder==ROOT/PACKAGE/'capture-01' and stage==ROOT/'.work'/'36-robustness-native-01'
            and not folder.exists() and not stage.exists(),'Use unique registered robustness output directories')
    progress=read(ROOT/'docs/mainline/progress.json')
    require(progress['current_ticket']=='36' and progress['research_trials']['robustness']['attempts']==0,
            'Robustness already attempted or wrong mainline frontier')
    require(progress['research_trials']['attempts']==164 and progress['research_trials']['charged_s']==1640,
            'Cumulative registered budget before robustness differs')
    require(book['budget']==plan['phases'][PHASE]['budget'] and book['automatic_retries']==0,'Runbook budget differs')
    authorization=read(ROOT/AUTHORIZATION)
    require(authorization['status']=='REVIEWED_TO_EXECUTE' and authorization['execution_lock']==EXECUTION_LOCK
        and authorization['execution_lock_sha256']==digest((ROOT/EXECUTION_LOCK).read_bytes()),'Missing exact independent execution authorization')
    require(not progress['pre36_alignment_audit']['blocks_ticket36'],'Alignment audit still blocks36')
    require(sys.dont_write_bytecode and sys.pycache_prefix is not None and not Path(sys.pycache_prefix).exists(),
            'Use -B and a fresh cache prefix')
    # This metadata validation precedes every chargeable physical slot. Keep
    # a failure here even when no capture/batch directory can yet be created.
    gate=ROOT/PACKAGE/'execution-validation-01';require(not gate.exists(),'Execution validation already attempted')
    gate.mkdir()
    journal_write(gate/'start.json',dict(status='STARTED_NONCE_VALIDATION',source=source,nonce_read_attempts=1,physical_calls=0))
    try:
        _read_nonce(NONCE,read(ROOT/LOCK)['commitments_sha256'][PHASE])
    except BaseException as exc:
        journal_write(gate/'terminal.json',dict(status='REFUSED_BEFORE_PHYSICAL_SLOTS',source=source,nonce_read_attempts=1,
            nonce_validated=0,nonce_read_completion='UNKNOWN_OR_FAILED',error_type=type(exc).__name__,error=str(exc),physical_calls=0));raise
    journal_write(gate/'terminal.json',dict(status='PASS_NONCE_VALIDATION',source=source,nonce_read_attempts=1,nonce_validated=1,nonce_read_completion='VALIDATED_RETURN',physical_calls=0))
    names=set(read(ROOT/EXECUTION_LOCK)['execution_pins'])
    names.update(read(ROOT/LOCK)['pins'])
    names.update({RUNBOOK,LOCK,PROTOCOL,'docs/mainline/progress.json','docs/mainline/evidence/30-root.json','docs/mainline/evidence/31-root.json',
        'docs/mainline/evidence/34-root.json','docs/mainline/evidence/35-root.json',EXECUTION_LOCK,AUTHORIZATION,EXTENSION,'docs/mainline/evidence/pre36-alignment.json'})
    names.update((ROOT/FREEZE/name).relative_to(ROOT).as_posix() for name in
                 set(read(ROOT/FREEZE/'receipt.json')['artifacts'])|{'receipt.json'})
    pins=hashes(source,names)
    _guard(source,pins)
    folder.mkdir(parents=True);stage.mkdir(parents=True)
    write(folder/'batch.json',dict(schema='aegisdc-registered-robustness-batch-v1',phase=PHASE,
        classification='REGISTERED_FINITE_ROBUSTNESS_CONTRASTS',execution_commit=source,pins=pins,slots=slots,
        budget=plan['phases'][PHASE]['budget'],protocol_sha256=digest((ROOT/PROTOCOL).read_bytes()),
        design_lock_sha256=digest((ROOT/LOCK).read_bytes()),interpreter_sha256=digest(Path(sys.executable).read_bytes()),
        unused_cache_prefix=True,automatic_retries=0,phase_nonce_commitment=read(ROOT/LOCK)['commitments_sha256'][PHASE]))
    return pins


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
            automatic_retries=0,held_inputs_read=len(originals),held_seed_reads=1,
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
        held_inputs_read=len(originals),held_seed_reads=1,llm_calls=0,training_calls=0,automatic_retries=0,
        field_calibration='PENDING')
    write(folder/'receipt.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','phase','execution_commit','total','stop')},ensure_ascii=False))
    return 0 if status=='PASS' else 3


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('plan','capture'))
    parser.add_argument('--source')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--native-staging',type=Path)
    args=parser.parse_args()
    if args.mode=='plan':
        plan,slots,_=load_roster()
        print(json.dumps(dict(status='PASS_CONFIRMATION_ROSTER_ONLY',slots=len(slots),
            budget=plan['phases'][PHASE]['budget'],physical_calls=0,selector_calls=0)))
    else:
        require(args.source and args.output and args.native_staging,'Capture requires the exact execution and new output paths')
        return capture(args.source,args.output.resolve(),args.native_staging.resolve())

if __name__=='__main__':
    raise SystemExit(main())
