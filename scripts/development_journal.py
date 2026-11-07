"""Exact append-only development ledger audit; no physical or policy calls."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from registered_comparison import require

FINAL=('COMPLETED','FAILED','INTERRUPTED')


class RecorderIncomplete(OSError):
    """A record may be present, but its durable commit is not established."""


def append(path,record):
    row=dict(record,recorded_at_utc=datetime.now(timezone.utc).isoformat())
    raw=(json.dumps(row,allow_nan=False,ensure_ascii=False)+'\n').encode()
    try:
        with path.open('ab') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        require(path.read_bytes().endswith(raw),'Last journal record differs after append')
    except BaseException as exc:
        raise RecorderIncomplete(f'Journal durable write/readback not established: {type(exc).__name__}') from exc


def write_record(path,record):
    raw=(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    try:
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        require(path.read_bytes()==raw,'Durable per-slot record differs')
    except BaseException as exc:
        raise RecorderIncomplete(f'Per-slot durable write/readback not established: {type(exc).__name__}') from exc


def reconcile(folder,slots,source):
    raw=(folder/'attempts.jsonl').read_bytes()
    require(not raw or raw.endswith(b'\n'),'Partial final journal record')
    rows=[json.loads(line) for line in raw.splitlines()]
    roster={s['index']:s for s in slots}
    states={}
    pending=None
    total=dict(started=0,completed=0,failed=0,interrupted=0,unrun=0,
               charged_simulated_s=0,charged_scheduled_decisions=0,returned_decisions=0)
    for row in rows:
        index=row['index']
        require(index in roster and row['source']==source and all(row[k]==v for k,v in roster[index].items()),
                'Journal row differs from its declared roster')
        status=row['status']
        slot=roster[index]
        path=folder/f"{index:02}-{slot['world_id']}-{slot['arm']}"
        original={k:v for k,v in row.items() if k!='recorded_at_utc'}
        if status=='STARTED':
            require(pending is None and index==len(states)+1 and index not in states,
                    'Duplicate, out-of-order or overlapping STARTED')
            require(row['charged_simulated_s']==slot['duration_s']
                    and row['charged_scheduled_decisions']==slot['scheduled_decisions'],
                    'Journal start charges differ')
            require(json.loads((path/'start.json').read_bytes())==original,'Slot start differs from durable journal')
            pending=index
            states[index]=status
            total['started']+=1
            total['charged_simulated_s']+=row['charged_simulated_s']
            total['charged_scheduled_decisions']+=row['charged_scheduled_decisions']
        elif status in FINAL:
            require(pending==index and states.get(index)=='STARTED','Terminal has no unique start')
            require(json.loads((path/'terminal.json').read_bytes())==original,'Slot terminal differs from durable journal')
            require(type(row['physical_call_started']) is bool and type(row['physical_returned']) is bool,
                    'Unknown physical-call lifecycle')
            if status=='COMPLETED':
                require(row['physical_call_started'] and row['physical_returned']
                        and row['returned_decisions']==slot['scheduled_decisions'],'Incomplete successful physical lifecycle')
            total[status.lower()]+=1
            total['returned_decisions']+=row.get('returned_decisions',0)
            states[index]=status
            pending=None
        elif status=='UNRUN':
            require(pending is None and index==len(states)+1 and index not in states
                    and not path.exists(),'UNRUN overlaps a recorded attempt or partial slot')
            states[index]=status
            total['unrun']+=1
        else:
            raise ValueError('Unknown journal status')
    require(pending is None and len(states)==len(roster)
            and total['started']==sum(total[k] for k in ('completed','failed','interrupted'))
            and total['started']+total['unrun']==len(slots),'Ledger has an incomplete or ambiguous lifecycle')
    return total


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    args=parser.parse_args()
    batch=json.loads((args.folder/'batch.json').read_bytes())
    try:
        total=reconcile(args.folder,batch['slots'],batch['execution_commit'])
    except (ValueError,OSError,KeyError,TypeError) as exc:
        parser.exit(2,f'{exc}\n')
    print(json.dumps(dict(status='PASS_EXACT_JOURNAL',total=total,physical_calls=0)))


if __name__=='__main__':
    main()
