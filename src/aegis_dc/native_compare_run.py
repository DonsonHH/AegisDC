"""One new process and append-only attempt identity per frozen native V6 arm."""
import json
import os
from pathlib import Path
import subprocess
import sys
from time import time_ns
import traceback

from patrol_rsi.contracts import digest
from .native_compare_inputs import ARMS, Conditions, file_hash, read, write_new
from .native_compare_score import panel, read_native, score_arm


def checkpoint(path, value):
    temporary=path.with_suffix('.next')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary,path)


def note(path, event):
    # A durable pre-launch line survives even when the child or scorer fails.
    with path.open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(event,sort_keys=True,allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def run_order(directory, order, prepare, read_return, *, on_complete=None):
    directory=Path(directory).resolve()
    if not order or len(order)!=len(set(order)) or any(not c.isalnum() or a not in ARMS for c,a in order):
        raise ValueError('Declare unique, ordered condition and arm identities')
    directory.mkdir(parents=True,exist_ok=False)
    events=directory/'events.jsonl'
    rows=[dict(unit=c+'-'+a,condition=c,arm=a,state='NOT_EXECUTED',started=False,pid=None,start_ns=None,
               prepared_ns=None,returned_ns=None,complete_return=False,internal_policy_calls=None,
               directory=str(directory/(c+'-'+a))) for c,a in order]
    ledger=dict(rows=rows,started=0,complete_returns=0,unreturned=0,known_policy_subtotal=0,
                unresolved_internal=0)
    def archive():
        ledger.update(started=sum(r['started'] for r in rows),complete_returns=sum(r['complete_return'] for r in rows),
            unreturned=sum(r['started'] and not r['complete_return'] for r in rows),
            known_policy_subtotal=sum(r['internal_policy_calls'] for r in rows if r['internal_policy_calls'] is not None),
            unresolved_internal=sum(r['started'] and r['internal_policy_calls'] is None for r in rows))
        checkpoint(directory/'ledger.json',ledger)
    archive()
    for row in rows:
        case,arm=row['condition'],row['arm']
        path=Path(row['directory'])
        try:
            path.mkdir()
            command,call_digest=prepare(case,arm,path)
            row.update(input_sha256=call_digest,prepared_ns=time_ns(),state='PREPARED')
            write_new(path/'call.json',dict(unit=row['unit'],input_sha256=call_digest,command=command))
            note(events,dict(unit=row['unit'],event='BEFORE_LAUNCH',ns=row['prepared_ns'],input_sha256=call_digest))
            archive()
            with (path/'stdout').open('xb') as stdout,(path/'stderr').open('xb') as stderr:
                with subprocess.Popen(command,stdout=stdout,stderr=stderr) as child:
                    row.update(started=True,pid=child.pid,start_ns=time_ns(),state='STARTED')
                    note(events,dict(unit=row['unit'],event='STARTED',ns=row['start_ns'],pid=child.pid))
                    archive()
                    row['exit_code']=child.wait()
            row['process_exit_ns']=time_ns()
            note(events,dict(unit=row['unit'],event='EXIT',rc=row['exit_code'],ns=row['process_exit_ns']))
            if row['exit_code']!=0:
                raise RuntimeError(f"Child exited {row['exit_code']}; see {path/'stderr'}")
            returned=read_return(case,arm,path)
            row.update(complete_return=True,returned_ns=time_ns())
            calls=returned.get('internal_policy_calls')
            if type(calls) is not int or calls<0:
                note(events,dict(unit=row['unit'],event='COMPLETE_RETURN',ns=row['returned_ns'],decisions=None))
                archive()
                raise ValueError('Native return recorded; internal decision count unknown')
            row['internal_policy_calls']=calls
            if 'semantic_sha256' in returned:
                row['semantic_sha256']=returned['semantic_sha256']
            note(events,dict(unit=row['unit'],event='COMPLETE_RETURN',ns=row['returned_ns'],decisions=calls))
            archive()
            if on_complete is not None:on_complete(case,arm,path,returned)
            row['state']='COMPLETED'
        except Exception:
            row.update(state='FAILED',error=traceback.format_exc())
            manifest=path/'run/run.json'
            # Preserve evidence that the plant returned even if a later evaluator failed.
            if manifest.is_file():
                row['raw_native_return_sha256']=file_hash(manifest)
            note(events,dict(unit=row['unit'],event='FAILED',complete_return=row['complete_return'],ns=time_ns()))
            archive()
            break
        archive()
    return ledger


def run_native(directory, order, conditions, *, after_arm=None):
    eligibility=[('C01',a) for a in ARMS]+[('C03','K'),('C04','P'),('C05','P'),('C08','K'),('C17','D'),('C17','K')]
    if after_arm is None or any(unit not in eligibility for unit in order) or sorted(order,key=eligibility.index)!=order:
        raise PermissionError('Only the frozen engineering schedule can launch facilities in this version')
    scores={}
    def prepare(case,arm,path):
        call=conditions.call(case,arm)
        arguments=[sys.executable,'-B','-m','aegis_dc','simulate']
        for flag,value in [('model',call['scenario']),('dispatch-program',call['dispatch_program']),
                ('business-program',call['business_program']),('inputs',dict(schema='aegisdc-engineering-inputs-v1',
                work_requests=[],boundary_events=call['boundary_events']))]:
            name=path/(flag+'.json')
            write_new(name,value); arguments+=['--'+flag,str(name)]
        arguments+=['--duration',str(call['duration_s']),'--step',str(call['step_s']),'--output',str(path/'run')]
        return arguments,digest(call)
    def receive(case,arm,path):
        run,trace,balances=read_native(path/'run')
        pins=conditions.rows[case]['arms'][arm]
        if not (run['scenario_sha256']==pins['scenario'] and digest(run['inputs']['dispatch_program'])==pins['dispatch'] and
                digest(run['inputs']['business_program'])==pins['business'] and digest(run['inputs']['boundary_events'])==pins['events']
                and file_hash(path/'run/scenario.json')==run['artifacts']['scenario.json']['sha256']):
            raise ValueError('Actual returned call identity differs')
        return dict(internal_policy_calls=len(run['policy_public_decisions']),raw_return_sha256=file_hash(path/'run/run.json'))
    def evaluate(case,arm,path,returned):
        run,trace,balances=read_native(path/'run')
        scored=score_arm(run,trace,balances)
        if scored['internal_policy_calls']!=returned['internal_policy_calls']:
            raise ValueError('Evaluation/internal decision count differs')
        scored.update(condition=case,treatment=arm,native_sha256=returned['raw_return_sha256'],
            input_sha256=conditions.rows[case]['arms'][arm]['complete_call'],native_source=run['code_identity']['source_tree_sha256'])
        write_new(path/'score.json',scored)
        scores.setdefault(case,{})[arm]=scored
        if arm in ('V','H') and {'V','H'}<=scores[case].keys() and scores[case]['V']['semantic_sha256']!=scores[case]['H']['semantic_sha256']:
            raise ValueError('V/H full history and physical endpoint mismatch')
        if after_arm:after_arm(case,arm,path,scored)
        if scored['violations']:
            raise ValueError('Hard constraint violations archived')
        return dict(semantic_sha256=scored['semantic_sha256'],score_sha256=file_hash(path/'score.json'),
                    native_sha256=returned['raw_return_sha256'],native_source=scored['native_source'])
    def finish(case,arm,path,returned):
        details=evaluate(case,arm,path,returned)
        write_new(path/'evaluated.json',details)
        return details
    ledger=run_order(directory,order,prepare,receive,on_complete=finish)
    for row in ledger['rows']:
        if row['state']=='COMPLETED':
            row.update(read(Path(row['directory'])/'evaluated.json'))
        elif row['state']=='FAILED':
            scores.setdefault(row['condition'],{}).setdefault(row['arm'],{})['status']='FAILED'
    checkpoint(Path(directory)/'ledger.json',ledger)
    # This table retains all registered denominators even for a sparse engineering selection.
    table=panel(scores,list(conditions.rows))
    table['purpose']='ENGINEERING_ONLY'
    write_new(Path(directory)/'saved-evaluation.json',table)
    return ledger
