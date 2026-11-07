"""Run the32 preregistered ablation slots with unchanged private physical execution."""
import argparse,json,sys
from pathlib import Path
from comparison_release import ROOT,LOCK,PROTOCOL,audit_release,audit_lock
from inspection_delivery import read,require,git,hashes,digest,durable,write
from development_journal import append as journal_append,write_record as journal_write,reconcile as reconcile_journal
from registered_development import _guard
from ablation_run_evidence import save_native as _save_native
from prepare_ablation import verify,PREP,EXECUTION_LOCK,EXTENSION
PHASE='ablation'
PACKAGE='evidence/mainline/research/35-ablation'
RUNBOOK='docs/mainline/35-ablation-execution.json'
AUTHORIZATION='docs/mainline/evidence/35-execution-authorization.json'
def head():return git('rev-parse','HEAD').decode().strip()

def load_roster():
    verify();plan=read(ROOT/PROTOCOL);phase=plan['phases'][PHASE];prepared=read(ROOT/PREP/'receipt.json')
    originals,slots={},[]
    for world in phase['worlds']:
        arms=phase['arms'];shift=(world['slot']-1)%len(arms)
        for arm in arms[shift:]+arms[:shift]:
            name=world['id']+'/'+arm+'.json';raw=(ROOT/PREP/'inputs'/name).read_bytes()
            require(digest(raw)==prepared['input_hashes'][name],'Frozen ablation input differs')
            originals[name]=raw
            slots.append(dict(index=len(slots)+1,world_id=world['id'],family=world['family'],arm=arm,
                duration_s=world['duration_s'],scheduled_decisions=len(plan['decision_times_s']),input_member=name,input_sha256=digest(raw)))
    return plan,slots,originals

def _begin(folder,stage,source,plan,slots):
    require(head()==source and not git('status','--porcelain'),'Use clean exact ablation execution checkout')
    require(folder==ROOT/PACKAGE/'capture-01' and stage==ROOT/'.work/35-ablation-native-01'
        and not folder.exists() and not stage.exists(),'Use unique original ablation output paths')
    progress=read(ROOT/'docs/mainline/progress.json')
    require(progress['current_ticket']=='35' and progress['research_trials']['ablation']['attempts']==0,'Wrong frontier or ablation already attempted')
    authorization=read(ROOT/AUTHORIZATION)
    require(authorization['status']=='REVIEWED_TO_EXECUTE' and authorization['execution_lock']==EXECUTION_LOCK
        and authorization['execution_lock_sha256']==digest((ROOT/EXECUTION_LOCK).read_bytes()),'Missing exact independent ablation authorization')
    book=read(ROOT/RUNBOOK);nonce=Path(book['nonce_directory'])/'ablation.bin'
    audit_release(PHASE,'execute',ROOT/LOCK,nonce,ROOT/PREP/'inputs',folder)
    require(sys.dont_write_bytecode and sys.pycache_prefix is not None and not Path(sys.pycache_prefix).exists(),'Use -B and unused cache prefix')
    names=set(read(ROOT/EXECUTION_LOCK)['execution_pins'])|set(read(ROOT/LOCK)['pins'])
    names.update({RUNBOOK,LOCK,PROTOCOL,EXTENSION,EXECUTION_LOCK,AUTHORIZATION,'docs/mainline/evidence/34-root.json'})
    names.update((ROOT/PREP/n).relative_to(ROOT).as_posix() for n in set(read(ROOT/PREP/'receipt.json')['artifacts'])|{'receipt.json'})
    pins=hashes(source,names);_guard(source,pins);folder.mkdir(parents=True);stage.mkdir(parents=True)
    write(folder/'batch.json',dict(schema='aegisdc-registered-ablation-batch-v1',phase=PHASE,
        classification='REGISTERED_INDEPENDENT_MECHANISM_ABLATION',execution_commit=source,pins=pins,slots=slots,
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
        from ablation_planner import simulate_masked, audit_document

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
                result=simulate_masked(program)
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
        print(json.dumps(dict(status='PASS_ABLATION_ROSTER_ONLY',slots=len(slots),
            budget=plan['phases'][PHASE]['budget'],physical_calls=0,selector_calls=0)))
    else:
        require(args.source and args.output and args.native_staging,'Capture requires the exact execution and new output paths')
        return capture(args.source,args.output.resolve(),args.native_staging.resolve())

if __name__=='__main__':
    raise SystemExit(main())
