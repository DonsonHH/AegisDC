"""Pinned, single-allocation engineering controller with append-only per-unit evidence."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
import gc
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import traceback
from unittest.mock import patch

from audit_v6_joint import Checks, digest, native_case, public_case

ROOT=Path(__file__).resolve().parents[1]
PACK='docs/mainline/v6-joint-engineering-v1'
GROUPS={'F1':[f'P{i:02d}-{m}' for i in range(1,14) for m in ('J','B')]+[f'G{i:02d}' for i in range(1,26)],
        'F2':[f'S{i:02d}' for i in range(1,20)]+['L01','L02'],
        'F3':['T01','T02','T05','T06'],'F4':['T03','T04']}
LIMITS={'F1':(0,26,0,25),'F2':(21,0,971,0),'F3':(4,0,88,0),'F4':(2,0,44,0),
        'F5':(0,0,0,0),'F6':(27,26,1103,25),'F7':(0,0,0,0)}
DIM=['facility','direct','internal','component']


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(p):
    p=Path(p)
    if p.suffix=='.gz':
        with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)
    return json.loads(p.read_bytes())


def save(path,data):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,separators=(',',':'),allow_nan=False);f.write('\n')


def dump_native(path,data):
    with path.open('xb') as f, gzip.GzipFile(filename='',mode='wb',fileobj=f,compresslevel=1,mtime=0) as z:
        with io.TextIOWrapper(io.BufferedWriter(z,buffer_size=262144),encoding='utf-8') as writer:
            json.dump(data,writer,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def load_release(manifest_sha):
    release=ROOT/'release.json'
    if sha(release)!=manifest_sha:raise ValueError('Execution release identity differs')
    pin=read(release)
    for name,h in pin['files'].items():
        if sha(ROOT/name)!=h:raise ValueError('Execution file differs: '+name)
    freeze=ROOT/PACK;manifest=read(freeze/'manifest.json')
    for name,h in manifest['artifacts'].items():
        if sha(freeze/name)!=h:raise ValueError('F0 output differs: '+name)
    inputs=read(freeze/'inputs.json.gz');oracle=read(freeze/'oracle.json')
    if manifest['purpose']!='FINITE_PUBLIC_ENGINEERING' or set(inputs)!=set(oracle['units']) or any(
            digest(v)!=manifest['units'][k] for k,v in inputs.items()):raise PermissionError('Frozen engineering input binding')
    return pin,inputs,oracle,manifest


class Counts:
    def __init__(self,out,group):
        self.out=out;self.limits=dict(zip(DIM,LIMITS[group]));self.total={d:0 for d in DIM};self.local={}
    def event(self,dimension,key):
        if self.total[dimension]>=self.limits[dimension]:raise PermissionError('Frozen ceiling '+dimension)
        self.total[dimension]+=1;self.local[dimension]=self.local.get(dimension,0)+1
        with (self.out/'calls.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps([key,dimension,self.total[dimension]])+'\n')


@contextmanager
def observe_actual_decisions(key,counts):
    if key.startswith('L'):
        from aegis_dc import policy_execution as host
        name='choose_work'
    else:
        from aegis_dc import joint_session as host
        name='choose'
    original=getattr(host,name)
    def counted(*args,**kwargs):
        counts.event('internal',key)
        return original(*args,**kwargs)
    with patch.object(host,name,counted):
        yield


def private_sidecar(item,pin,manifest,key,oracle_sha):
    return dict(schema='aegisdc-joint-engineering-evaluation-v1',scenario_sha256=digest(item['scenario']),
        dispatch_program_sha256=digest(item['dispatch_program']),boundary_events_sha256=digest(item['boundary_events']),
        action_commands_sha256=digest(item.get('action_commands',[])),duration_s=item['duration_s'],maximum_step_s=item['step_s'],
        evaluator_source_sha256=pin['files']['scripts/audit_v6_joint.py'],
        fixture_and_oracle_sha256=digest([manifest['units'][key],oracle_sha]))


def evaluate_unit(key,item,expected,unit,pin,manifest,counts,oracle):
    counts.local={}
    save(unit/'start.json',dict(key=key,input_sha256=manifest['units'][key],expected_sha256=digest(expected),
         revision=pin['revision'],job=os.environ['SLURM_JOB_ID']))
    if key[0] in 'PG':
        if key[0]=='P':
            from aegis_dc.joint_policy import choose
            counts.event('direct',key);actual=choose(deepcopy(item['program']),deepcopy(item['view']))
        else:
            from v6_joint_components import evaluate
            counts.event('component',key);actual=evaluate(deepcopy(item))
        save(unit/'actual.json',actual)
        result=public_case(key,item,read(unit/'actual.json'),expected)
        artifact='actual.json'
    else:
        from aegis_dc.plant import simulate_scenario
        sidecar=private_sidecar(item,pin,manifest,key,sha(ROOT/PACK/'oracle.json'))
        save(unit/'private-evaluation.json',sidecar)
        with observe_actual_decisions(key,counts):
            counts.event('facility',key)
            run=simulate_scenario(deepcopy(item['scenario']),duration_s=item['duration_s'],step_s=item['step_s'],
                dispatch_program=deepcopy(item['dispatch_program']),business_program=deepcopy(item.get('business_program')),
                boundary_events=deepcopy(item['boundary_events']),action_commands=deepcopy(item.get('action_commands',[])),
                work_requests=deepcopy(item.get('work_requests',[])))
        artifact='run.json.gz';dump_native(unit/artifact,run);del run;gc.collect()
        saved=read(unit/artifact)
        if saved['code_identity']['files']!={k:v for k,v in pin['files'].items() if k.startswith('src/aegis_dc/') and k.endswith('.py') or k=='src/patrol_rsi/contracts.py'}:
            raise ValueError('Actual running facility source differs from release')
        if private_sidecar(item,pin,manifest,key,sha(ROOT/PACK/'oracle.json'))!=read(unit/'private-evaluation.json'):
            raise ValueError('Private evaluation sidecar identity changed')
        result=native_case(key,item,saved,oracle)
        del saved;gc.collect()
    save(unit/'checks.json',result)
    return dict(key=key,status='PASS' if result['passed'] else 'FAILED_ASSERTION',counts=counts.local.copy(),
        assertions=result['assertions'],failures=result['failures'],actual_file=artifact,actual_sha256=sha(unit/artifact),
        checks_sha256=sha(unit/'checks.json'),input_sha256=manifest['units'][key])


def run_group(root,out,group,keys,pin,inputs,oracle,manifest):
    if group=='F6':
        if not keys or len(keys)!=len(set(keys)) or any(k not in inputs for k in keys):raise ValueError('Invalid affected subset')
        if (root/'F6'/'result.json').exists():raise PermissionError('Repair already consumed')
        for key in keys:
            previous=[row for g in GROUPS if (root/g/'result.json').exists() for row in read(root/g/'result.json')['rows'] if row['key']==key]
            if any(r['status']=='PASS' for r in previous):raise PermissionError('Unaffected passed unit cannot rerun: '+key)
    elif keys!=GROUPS[group]:raise PermissionError('Group must use fixed order')
    counts=Counts(out,group);rows=[];stopped=None
    for key in keys:
        if stopped:break
        unit=out/key;unit.mkdir();counts.local={}
        try:
            row=evaluate_unit(key,inputs[key],oracle['units'][key],unit,pin,manifest,counts,oracle)
        except Exception as exc:
            (unit/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
            row=dict(key=key,status='FAILED_EXCEPTION',counts=counts.local.copy(),assertions=0,error=repr(exc),
                     input_sha256=manifest['units'][key])
            if group!='F1':stopped=key
        rows.append(row);save(unit/'terminal.json',row)
        if row['status']=='FAILED_ASSERTION' and any('arrival' in f['check'] or 'private' in f['check'] for f in row['failures']):
            stopped=key
        print(key,row['status'],counts.local,flush=True)
    remaining=keys[len(rows):];failed=[r['key'] for r in rows if r['status']!='PASS']
    report=dict(group=group,job=os.environ['SLURM_JOB_ID'],revision=pin['revision'],scheduled=keys,rows=rows,unexecuted=remaining,
                failed=failed,counts=counts.total,status='FAILED' if failed or remaining else 'PASS')
    save(out/'result.json',report)
    return 1 if failed or remaining else 0


def compare_saved(root,out,pin,inputs,oracle,manifest):
    rows={};checks=Checks();details={};failed={};prior=[]
    for group in (*GROUPS,'F6'):
        rp=root/group/'result.json'
        if not rp.is_file():continue
        report=read(rp);prior.append((group,sha(rp)))
        for r in report['rows']:
            key=r['key'];unit=root/group/key
            if r['status']!='PASS':failed.setdefault(key,[]).append([group,r['status']])
            rows[key]=r
            if not r.get('actual_file'):continue
            checks.condition('raw digest '+key,sha(unit/r['actual_file'])==r['actual_sha256'] and sha(unit/'checks.json')==r['checks_sha256'])
            actual=read(unit/r['actual_file'])
            verified=public_case(key,inputs[key],actual,oracle['units'][key]) if key[0] in 'PG' else native_case(key,inputs[key],actual,oracle)
            checks.compare('reconcile full independent check '+key,digest(verified),digest(read(unit/'checks.json')))
            details[key]=verified['details'];del actual;gc.collect()
    for left,right,until in [('S12','S14',1.75),('S13','S15',5.5),('S03','S04',1.75)]:
        if left in details and right in details:
            for t,h in details[left]['prefix_sha256'].items():
                if float(t)<until:checks.compare(f'public paired prefix {left}/{right} {t}',h,details[right]['prefix_sha256'].get(t))
    if 'P06-J' in details and 'P08-J' in details:
        for method in ('J','B'):
            checks.compare('row-order invariance '+method,details['P06-'+method],details['P08-'+method])
    for dirty,clean in [('T01','T02'),('T03','T04'),('T05','T06')]:
        if dirty not in details or clean not in details:continue
        a,b=details[dirty],details[clean]
        checks.compare('pre-intervention hydraulics/heat and service '+dirty,a['warm_prefix'],b['warm_prefix'])
        checks.condition('q and heat separate '+dirty,b['q_at_3_25']>a['q_at_3_25'] and b['heat_at_3_25']>a['heat_at_3_25'])
        if dirty=='T05':checks.compare('masked endpoints',a['physical_integrals'],b['physical_integrals'])
        else:checks.condition('step-specific physical direction '+dirty,all(x>y for x,y in zip(a['physical_integrals'],b['physical_integrals'])))
    if all(k in details for k in ('T01','T03')):
        a,b=[details[k]['first_trip'] for k in ('T01','T03')]
        checks.condition('first protection tick sensitivity',a is not None and b is not None and abs(a-b)<=1)
    for d in details.values():d.pop('prefix_sha256',None)
    result=checks.report(dict(unit_details=details,prior_result_hashes=prior))
    save(out/'checks.json',result)
    missing=sorted(set(inputs)-set(rows))
    save(out/'result.json',dict(group=out.name,job=os.environ['SLURM_JOB_ID'],revision=pin['revision'],counts=dict.fromkeys(DIM,0),
        completed=len(rows),missing=missing,all_failures=failed,final_status={k:r['status'] for k,r in rows.items()},
        saved_assertions=result['assertions'],failures=result['failures'],checks_sha256=sha(out/'checks.json'),
        status='RECONCILED' if result['passed'] else 'RECONCILED_WITH_FINDINGS'))
    return 0 if result['passed'] else 1


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('group',choices=LIMITS);p.add_argument('release_sha');p.add_argument('affected',nargs='*');args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=1:raise PermissionError('Single-CPU Slurm allocation required')
    pin,inputs,oracle,manifest=load_release(args.release_sha)
    out=args.root/args.group
    with (out/'started.lock').open('x') as f:f.write(os.environ['SLURM_JOB_ID'])
    if args.group in ('F5','F7'):return compare_saved(args.root,out,pin,inputs,oracle,manifest)
    return run_group(args.root,out,args.group,GROUPS.get(args.group,args.affected),pin,inputs,oracle,manifest)


if __name__=='__main__':
    sys.exit(main())
