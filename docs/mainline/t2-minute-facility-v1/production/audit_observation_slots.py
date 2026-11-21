"""Determine repair eligibility from paid production alone. Do not read service outcomes."""
from collections import defaultdict
from pathlib import Path
import gzip
import hashlib
import json
import os

ROOT=Path('/share/home/renly/renly-patrol-rsi/mainline/T2-minute-facility-20261121-v1')
def load(path):return json.loads(path.read_bytes())
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    assert os.environ.get('SLURM_JOB_ID') and os.environ.get('SLURM_CPUS_PER_TASK')=='1'
    m=load(ROOT/'study-inputs/manifest.json')
    completed=[];invalid=[];records=[]
    for key,role in m['pilot']+sum([m['batches'][k] for k in ('group_01','group_02','group_03')],[]):
        d=ROOT/'positions'/(key+'-'+role)
        if (key,role)==('4-01','ORACLE'):d/= 'attempt-02'
        with gzip.open(d/'original.jsonl.gz','rt') as f:meta=json.loads(next(f))['metadata']
        work={row['id'] for row in meta['work_records']}
        acquired=defaultdict(set)
        for field in meta['inspection_public_feedback']:
            if field['interval'] is not None:
                assert field['task'] in work
                acquired[(field['target'],field['phase'])].add(field['task'])
        repeated=any(len(tasks)>1 for tasks in acquired.values())
        count=len(set().union(*acquired.values())) if acquired else 0
        ok=not repeated and count<=2 and (d/'result.json').exists()
        detail=dict(key=key,role=role, job=load(d/'start.json')['job'],published={k+'/'+s:sorted(v) for (k,s),v in acquired.items()},
             total_paid_tasks=count,within_contract=ok,score_saved=(d/'result.json').exists(),raw_sha256=sha(d/'original.jsonl.gz'))
        records.append(detail)
        (completed if ok else invalid).append([key,role])
    assert len(records)==52 and len({(q['key'],q['role']) for q in records})==52
    with (ROOT/'observation-scope-audit.json').open('x') as f:
        json.dump(dict(purpose='arrival-and-permission-only; no service/score used for inclusion',job=os.environ['SLURM_JOB_ID'],
            material_files=records,legal=completed,affected=invalid),f,separators=(',',':'))
    print('registered',len(records),'lawful',len(completed),'affected',invalid,flush=True)


if __name__=='__main__':main()
