"""Supervise the frozen checker and reconcile its final counts with the durable native journal."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(path.read_bytes())


def journal_counts(directory, scheduled):
    ledger_path=directory/'ledger.json'
    journal_path=directory/'events.jsonl'
    rows={u:dict(prepared=False,started=False,returned=False,known=None,failed=False) for u in scheduled}
    if not directory.exists():
        return dict(status='NO_FACILITY_BATCH_CREATED',started=0,complete_returns=0,unreturned=0,known_subtotal=0,
                    unknown_internal=[],uncertain_starts=[],unexecuted=list(scheduled))
    if not ledger_path.is_file():
        return dict(status='LEDGER_UNAVAILABLE',started=None,complete_returns=None,unreturned=None,known_subtotal=None,
                    unknown_internal=None,uncertain_starts=list(scheduled),unexecuted=None)
    ledger=read(ledger_path)
    if [r['unit'] for r in ledger['rows']]!=scheduled:
        raise ValueError('Persistent schedule differs')
    if journal_path.is_file():
        with journal_path.open(encoding='utf-8') as stream:
            for line in stream:
                e=json.loads(line);r=rows[e['unit']]; kind=e['event']
                if kind=='BEFORE_LAUNCH':r['prepared']=True
                elif kind=='STARTED':r['started']=True
                elif kind=='COMPLETE_RETURN':r.update(returned=True,known=e.get('decisions'))
                elif kind=='FAILED':r['failed']=True
    for saved in ledger['rows']:
        r=rows[saved['unit']]
        r['started'] |= saved['started']
        r['returned'] |= saved['complete_return']
        r['prepared'] |= saved['prepared_ns'] is not None
        r['failed'] |= saved['state']=='FAILED'
        if r['known'] is None:r['known']=saved.get('internal_policy_calls')
    uncertain=[k for k,v in rows.items() if v['prepared'] and not v['started'] and not v['failed']]
    return dict(status='COMPLETE_ACCOUNTING' if not uncertain else 'UNCERTAIN_START_NO_RETRY',
                started=sum(v['started'] for v in rows.values()),complete_returns=sum(v['returned'] for v in rows.values()),
                unreturned=sum(v['started'] and not v['returned'] for v in rows.values()),
                known_subtotal=sum(v['known'] for v in rows.values() if type(v['known']) is int and v['known']>=0),
                unknown_internal=[k for k,v in rows.items() if v['started'] and not (type(v['known']) is int and v['known']>=0)],
                uncertain_starts=uncertain,unexecuted=[k for k,v in rows.items() if not v['started'] and not v['prepared'] and not v['failed']])


def main():
    args=sys.argv[1:]
    launch=read(Path(args[args.index('--launch')+1]))
    out=Path(launch['output'])
    receipt=out.parent/'terminal-account.json'
    if out.exists() or receipt.exists():
        raise FileExistsError('Attempt already has output')
    job=os.environ['SLURM_JOB_ID']
    checker=Path(__file__).with_name('repair_facilities.py') if launch['mode']=='repair' else ROOT/'scripts/qualify_native_comparison.py'
    result=subprocess.run([sys.executable,'-B',str(checker),*args])
    evidence=dict(job=job,checker_exit=result.returncode,mode=launch['mode'])
    try:
        counts=journal_counts(out/'native',launch['units']['facilities'])
        evidence.update(native=counts,public_call_markers=sorted(p.parent.name for p in out.glob('public-*/begin.json')),
            public_returns=sorted(p.parent.name for p in out.glob('public-*/return.json')),
            substitute_call_markers=sorted(p.parent.name for p in out.glob('substitute-*/begin.json')),
            substitute_returns=sorted(p.parent.name for p in out.glob('substitute-*/return.json')))
        report=read(out/'report.json')
        evidence['checker_summary_consistent']=(counts['status'] in ('NO_FACILITY_BATCH_CREATED','COMPLETE_ACCOUNTING') and
            (counts['started'],counts['complete_returns'],counts['known_subtotal'],counts['unknown_internal'])==
            (report['facility_started'],report['facility_returned'],report['internal_policy_known'],report['unknown_facility_internal']))
    except Exception as error:
        evidence.update(accounting_error=repr(error),checker_summary_consistent=False)
    with receipt.open('x',encoding='utf-8') as stream:
        json.dump(evidence,stream,indent=2)
        stream.flush();os.fsync(stream.fileno())
    return result.returncode or (0 if evidence['checker_summary_consistent'] else 1)

if __name__=='__main__':sys.exit(main())
