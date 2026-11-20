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
    events=[]
    for e in item['boundary_events']:
        if set(e)!={'time_s','parameter_id','value','source_note'} or any(type(e[k]) not in (int,float) for k in ('time_s','value')):
            raise ValueError('Unexpected native event input')
        events.append(dict(e,time_s=float(e['time_s']),value=float(e['value'])))
    events.sort(key=lambda e:e['time_s'])
    return dict(schema='aegisdc-joint-engineering-evaluation-v1',scenario_sha256=digest(item['scenario']),
        literal_input_sha256=manifest['units'][key],dispatch_program_sha256=digest(item['dispatch_program']),boundary_events_sha256=digest(events),
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
        if key.startswith(('S','T')) and (item.get('business_program') is not None or
                item['dispatch_program']['schema']!='aegisdc-policy-run-program-v6' or
                item['dispatch_program']['policy_program']['schema']!='aegisdc-joint-problem-policy-v1' or
                item['action_commands'] or item['work_requests']):
            raise PermissionError('Incorrect native joint entry or external action')
        if key.startswith('L') and (item['dispatch_program']['schema']!='aegisdc-policy-run-program-v5' or
                item['business_program']['schema']!='aegisdc-business-composite-evaluation-v1'):
            raise PermissionError('Incorrect original H10 entry')
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
        actual_bind=dict(saved['inputs'],scenario=saved['source_config'],step_s=saved['inputs']['maximum_step_s'])
        if private_sidecar(actual_bind,pin,manifest,key,sha(ROOT/PACK/'oracle.json'))!=read(unit/'private-evaluation.json'):
            raise ValueError('Saved native run and private evaluation sidecar differ')
        result=native_case(key,item,saved,oracle)
        del saved;gc.collect()
    save(unit/'checks.json',result)
    return dict(key=key,status='PASS' if result['passed'] else 'FAILED_ASSERTION',counts=counts.local.copy(),
        assertions=result['assertions'],failures=result['failures'],actual_file=artifact,actual_sha256=sha(unit/artifact),
        checks_sha256=sha(unit/'checks.json'),input_sha256=manifest['units'][key])


def recover_sealed(root,unit,key,item,pin,manifest,oracle,repair):
    original=root/repair['original_group']/key
    audit_hash=sha(ROOT/PACK/'oracle.json')
    original_pin=read(ROOT/PACK/repair['prior_execution_pin'])
    if (sha(original/'run.json.gz')!=repair['raw_sha256'] or sha(original/'private-evaluation.json')!=repair['old_sidecar_sha256']
        or sha(original/'terminal.json')!=repair['old_terminal_sha256']):raise ValueError('Original S06 evidence identity')
    old_start=read(original/'start.json')
    if old_start['input_sha256']!=manifest['units'][key] or old_start['expected_sha256']!=digest(oracle['units'][key]):
        raise ValueError('Original S06 input or independent oracle differs')
    new_side=private_sidecar(item,pin,manifest,key,audit_hash)
    old_side=read(original/'private-evaluation.json')
    legacy=dict(new_side);legacy.pop('literal_input_sha256')
    legacy.update(boundary_events_sha256=digest(item['boundary_events']),evaluator_source_sha256=original_pin['files']['scripts/audit_v6_joint.py'])
    if legacy!=old_side:raise ValueError('Original sidecar differs outside documented normalization')
    save(unit/'start.json',dict(key=key,job=os.environ['SLURM_JOB_ID'],mode='SAVED_OUTPUT_ONLY',revision=pin['revision'],
         originating_revision=old_start['revision'],input_sha256=manifest['units'][key],expected_sha256=digest(oracle['units'][key])))
    save(unit/'private-evaluation.json',new_side);os.link(original/'run.json.gz',unit/'run.json.gz')
    saved=read(unit/'run.json.gz')
    runtime={k:v for k,v in original_pin['files'].items() if (k.startswith('src/aegis_dc/') and k.endswith('.py')) or k=='src/patrol_rsi/contracts.py'}
    if saved['code_identity']['files']!=runtime:raise ValueError('Recovered runtime differs from original execution pin')
    actual=dict(saved['inputs'],scenario=saved['source_config'],step_s=saved['inputs']['maximum_step_s'])
    if private_sidecar(actual,pin,manifest,key,audit_hash)!=new_side:raise ValueError('Normalized saved binding differs')
    result=native_case(key,item,saved,oracle)
    save(unit/'checks.json',result)
    return dict(key=key,status='PASS' if result['passed'] else 'FAILED_ASSERTION',counts={},recovered_from=repair['original_group'],
        assertions=result['assertions'],failures=result['failures'],actual_file='run.json.gz',actual_sha256=repair['raw_sha256'],
        checks_sha256=sha(unit/'checks.json'),input_sha256=manifest['units'][key])


def run_group(root,out,group,keys,pin,inputs,oracle,manifest):
    repair=None
    if group=='F6':
        repair=read(ROOT/PACK/'repair-plan.json')
        if keys!=repair['affected'] or sha(root/repair['original_group']/'result.json')!=repair['original_result_sha256']:
            raise PermissionError('One repair must match its retained original terminal and ordered affected scope')
        if not keys or len(keys)!=len(set(keys)) or any(k not in inputs for k in keys):raise ValueError('Invalid affected subset')
        if (root/'F6'/'result.json').exists():raise PermissionError('Repair already consumed')
        for key in keys:
            previous=[row for g in GROUPS if (root/g/'result.json').exists() for row in read(root/g/'result.json')['rows'] if row['key']==key]
            origin=next(g for g,units in GROUPS.items() if key in units)
            if not (root/origin/'result.json').is_file():raise PermissionError('Original terminal missing: '+key)
            if not previous and key not in read(root/origin/'result.json')['unexecuted']:raise PermissionError('No affected exception or suffix')
            if any(r['status']=='PASS' for r in previous):raise PermissionError('Unaffected passed unit cannot rerun: '+key)
    elif keys!=GROUPS[group]:raise PermissionError('Group must use fixed order')
    counts=Counts(out,group);rows=[];stopped=None
    for key in keys:
        if stopped:break
        unit=out/key;unit.mkdir();counts.local={}
        try:
            if repair and key==repair['failed_unit']:
                row=recover_sealed(root,unit,key,inputs[key],pin,manifest,oracle,repair)
            else:
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
        entries=[json.loads(line) for line in (root/group/'calls.jsonl').read_text().splitlines()] if (root/group/'calls.jsonl').exists() else []
        observed={k:sum(e[1]==k for e in entries) for k in DIM}
        checks.compare('durable call and group counters '+group,observed,report['counts'])
        checks.condition('per-group caps '+group,all(observed[k]<=lim for k,lim in zip(DIM,LIMITS[group])))
        checks.compare('started and unexecuted suffix '+group,[r['key'] for r in report['rows']]+report['unexecuted'],report['scheduled'])
        for r in report['rows']:
            key=r['key'];unit=root/group/key
            unit_counts={k:sum(e[:2]==[key,k] for e in entries) for k in DIM}
            checks.compare('unit counters '+group+'/'+key,unit_counts,{k:r['counts'].get(k,0) for k in DIM})
            if r['status']=='PASS':
                native=key[0] in 'STL'
                ticks=len(inputs[key]['dispatch_program'].get('decision_times_s',inputs[key]['dispatch_program']['policy_program'].get('clock',[]))) if native else 0
                calls=[int(native),int(key[0]=='P'),ticks,int(key[0]=='G')]
                if 'recovered_from' in r:
                    origin=read(root/r['recovered_from']/key/'terminal.json')
                    checks.compare('retained original native consumption '+key,[origin['counts'].get(k,0) for k in DIM],calls)
                    calls=[0,0,0,0]
                checks.compare('complete unit calls '+group+'/'+key,list(unit_counts.values()),calls)
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
        common=sorted(a['warm_prefix'].keys() & b['warm_prefix'].keys(),key=float)
        checks.condition('shared pre-intervention epochs '+dirty,'0' in common and len(common)>=2)
        for time in common:
            left,right=a['warm_prefix'][time],b['warm_prefix'][time]
            checks.compare('pre-write native rates and protection '+dirty+' '+time,
                           [left[k] for k in ('q','service','latched')],[right[k] for k in ('q','service','latched')])
            # Compare like quantities on common native epochs. The two per-interval
            # native balance allowances give an explicit identity guard, not a solver error estimator.
            params={x['id']:x['value'] for x in inputs[dirty]['scenario']['parameters']}
            eps=2*params['energy_absolute_tolerance']+params['balance_relative_tolerance']*(left['boundary_abs_J']+right['boundary_abs_J'])
            dt=min(left['dt'],right['dt'])
            for field,delta in [('heat',dt*abs(left['heat']-right['heat']))]+[
                    (k,abs(left['stored_J'][k]-right['stored_J'][k])) for k in left['stored_J']]:
                checks.condition(f'pre-write {dirty} {time} {field} {delta:g} J <= {eps:g} J',delta<=eps)
        a['prewrite_common_epochs']=common
        checks.condition('q and heat separate '+dirty,b['q_at_3_25']>a['q_at_3_25'] and b['heat_at_3_25']>a['heat_at_3_25'])
        if dirty=='T05':checks.compare('masked endpoints',a['physical_integrals'],b['physical_integrals'])
        else:checks.condition('step-specific physical direction '+dirty,all(x>y for x,y in zip(a['physical_integrals'],b['physical_integrals'])))
    if all(k in details for k in ('T01','T03')):
        a,b=[details[k]['first_trip'] for k in ('T01','T03')]
        checks.condition('first protection tick sensitivity',a is not None and b is not None and abs(a-b)<=1)
    for d in details.values():d.pop('prefix_sha256',None)
    missing=sorted(set(inputs)-set(rows))
    checks.condition('all scheduled engineering units reached',not missing)
    checks.condition('all final units passed',len(rows)==len(inputs) and all(r['status']=='PASS' for r in rows.values()))
    result=checks.report(dict(unit_details=details,prior_result_hashes=prior))
    save(out/'checks.json',result)
    save(out/'result.json',dict(group=out.name,job=os.environ['SLURM_JOB_ID'],revision=pin['revision'],counts=dict.fromkeys(DIM,0),
        completed=len(rows),missing=missing,all_failures=failed,final_status={k:r['status'] for k,r in rows.items()},
        saved_assertions=result['assertions'],failures=result['failures'],checks_sha256=sha(out/'checks.json'),
        status='FINITE_ENGINEERING_CHECKS_PASSED_PENDING_REVIEW' if result['passed'] else 'FINITE_ENGINEERING_PARTIAL_OR_FAILED'))
    return 0 if result['passed'] else 1


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('group',choices=LIMITS);p.add_argument('release_sha');p.add_argument('affected',nargs='*');args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=1:raise PermissionError('Single-CPU Slurm allocation required')
    pin,inputs,oracle,manifest=load_release(args.release_sha)
    if pin.get('purpose')!='FINITE_PUBLIC_ENGINEERING' or args.root.resolve()!=Path(pin['activity']).resolve():raise PermissionError('Incorrect activity root or purpose')
    out=args.root/args.group
    with (out/'started.lock').open('x') as f:f.write(os.environ['SLURM_JOB_ID'])
    if args.group in ('F5','F7'):return compare_saved(args.root,out,pin,inputs,oracle,manifest)
    return run_group(args.root,out,args.group,GROUPS.get(args.group,args.affected),pin,inputs,oracle,manifest)


if __name__=='__main__':
    sys.exit(main())
