"""Read saved engineering originals; no facility, decision code or evaluator imports."""
import gzip
import hashlib
import json
import math
import os
from pathlib import Path

A=Path('/share/home/renly/renly-patrol-rsi/mainline/T2-minute-facility-20261121-v1')
PK=A/'source/docs/mainline/t2-minute-facility-v1'
CLOCK=list(range(0,3601,60))


def filehash(path):
    with path.open('rb') as fp:return hashlib.file_digest(fp,'sha256').hexdigest()


def load(path):return json.loads(path.read_bytes())


def extract(tag,step,bindings):
    folder=A/('A-'+tag)
    full=A/'A-inputs'/(tag+'.json')
    item=load(full);res=load(folder/'result.json')
    checks={}
    def record(k,v):checks[k]=bool(v)
    record('input_bound',filehash(full)==bindings['inputs'][tag]['input_sha256']==res['input_sha256'])
    record('raw_digest',filehash(folder/'original.jsonl.gz')==res['raw_sha256'])
    ticks=[];previous=None;largest=0;samples=0;intervals=0;end=0;loss=[];unserved=[]
    first=None
    with gzip.open(folder/'original.jsonl.gz','rt') as fp:
        meta=json.loads(next(fp))['metadata']
        record('original_facility',meta['source_config']==item['scenario'] and meta['inputs']['dispatch_program']==item['dispatch_program']
               and meta['inputs']['boundary_events']==item['boundary_events'])
        record('requested_grid',meta['inputs']['maximum_step_s']==item['step_s']==res['actual']['physics_step']==step)
        record('public_clock',[q['view']['time'] for q in meta['policy_public_decisions']]==CLOCK)
        for line in fp:
            row=json.loads(line)
            if 'sample' in row:
                p=row['sample'];t=p['time_s'];state=p['domains'];samples+=1
                plc=state['control_monitoring']
                m=plc['local_measurement']['sampled_at_s']
                if not ticks or ticks[-1]!=m:ticks.append(m)
                if first is None and plc['protection_latched']:first=t
                if previous is not None:
                    last,d,y=previous
                    loss.append((t-last)*(d-y)/d if d else 0)
                    unserved.append((t-last)*(d-y))
                it=state['it_service'];previous=(t,it['demand'],it['delivered'])
            elif 'balance' in row:
                b=row['balance'];dt=b['end_s']-b['start_s']
                if b['start_s']!=end or dt<=0:raise ValueError('Discontinuous original')
                end=b['end_s'];largest=max(largest,dt);intervals+=1
            else:raise ValueError('Unknown original member')
    record('physical_grid',samples==intervals+1 and end==3600 and largest==step)
    record('independent_PLC_clock',ticks==list(range(3601)))
    record('saved_rates',first==res['actual']['first_trip'] and
           [math.fsum(loss),math.fsum(unserved)]==res['actual']['account']['rate'])
    record('raw_positions',res['grid']==tag and res['manifest']==filehash(A/'A-inputs/manifest.json'))
    return dict(checks=checks,passed=all(checks.values()),native_assertions_passed=res['passed'],raw_sha256=res['raw_sha256'],
        input_sha256=res['input_sha256'],observed_max_step=largest,local_samples=len(ticks),intervals=intervals,
        first_trip=first,L=math.fsum(loss),U=math.fsum(unserved),physics_job=res['job'])


def main():
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Slurm required')
    manifest=load(A/'A-inputs/manifest.json')
    data=[load(A/'A-inputs'/(tag+'.json')) for tag in ('coarse','fine')]
    only_grid={k for k in data[0].keys()|data[1].keys() if data[0].get(k)!=data[1].get(k)}=={'step_s'}
    present={tag:extract(tag,step,manifest) for tag,step in [('coarse',.25),('fine',.125)] if (A/('A-'+tag)/'result.json').is_file()}
    cross=load(A/'A-final.json') if (A/'A-final.json').is_file() else None
    actual=dict(job=os.environ['SLURM_JOB_ID'],purpose='READ_SAVED_A_ONLY',only_grid_differs=only_grid,positions=present,
        source_sha256={p:filehash(PK/p) for p in ('qualification.py','public_gate.py','facility_inputs.py','timing.json','qualification-expected.json')},
        comparison=cross,passed=bool(only_grid and len(present)==2 and cross and cross['passed'] and
        all(z['passed'] and z['native_assertions_passed'] for z in present.values())))
    with (A/'A-readback.json').open('x') as fp:json.dump(actual,fp,indent=2)
    print(json.dumps(actual),flush=True)


if __name__=='__main__':main()
