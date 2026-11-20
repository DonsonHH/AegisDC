"""Cold arm isolation: durable intent, one fresh process, byte-bound return, no retries."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
PK=ROOT/'docs/mainline/v6-stage-three-cold-v2'
PY_SHA='5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6'


def encode(x):
    return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)).encode()


def digest(x):
    return hashlib.sha256(encode(x)).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):
    path=Path(path)
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf8') as fp:return json.load(fp)
    return json.loads(path.read_bytes())


def save(path,data):
    path=Path(path)
    with path.open('xb') as out:
        if path.suffix=='.gz':
            with gzip.GzipFile(filename='',mode='wb',fileobj=out,mtime=0,compresslevel=1) as gz:
                with io.TextIOWrapper(io.BufferedWriter(gz,buffer_size=262144),encoding='utf8') as fp:
                    json.dump(data,fp,separators=(',',':'),ensure_ascii=True,allow_nan=False)
        else:
            out.write(encode(data)+b'\n')


def release(h):
    path=ROOT/'release.json'
    if not os.getenv('SLURM_JOB_ID') or os.getenv('SLURM_CPUS_PER_TASK')!='1' or sha(path)!=h:raise PermissionError('ALLOCATION_OR_RELEASE')
    pin=read(path)
    if pin['purpose']!='PUBLIC_ENGINEERING' or pin['retries']!=0 or Path(pin['activity']).resolve()!=ROOT.parent or sha(sys.executable)!=PY_SHA:
        raise PermissionError('HOST_OR_PURPOSE')
    for name,expected in pin['files'].items():
        if sha(ROOT/name)!=expected:raise ValueError('SOURCE_IDENTITY '+name)
    return pin


def engineering_admit(purpose,kind,key,item,manifest):
    if purpose!='PUBLIC_ENGINEERING' or kind!='engineering':raise PermissionError('STUDY_UNAUTHORIZED')
    if key not in manifest['engineering'] or digest(item)!=manifest['engineering'][key]:raise PermissionError('INPUT_HASH')


def phase_units(phase,plan):
    schedule=next(j[2] for j in plan['jobs'] if j[0]==phase)
    if not isinstance(schedule,list):raise ValueError('Not a native allocation')
    groups={g['id']:g for g in plan['groups']}
    return [g+'-'+arm for g in schedule for arm in groups[g]['arms']]


def execute_group(out,order,start):
    """A child exit or binding failure halts the suffix. Each directory can be consumed once."""
    out=Path(out)
    with (out/'group.lock').open('x') as fp:fp.write(json.dumps(order))
    rows=[]
    for key in order:
        unit=out/key
        try:
            unit.mkdir(exist_ok=False)
            save(unit/'intent.json',dict(slot=key,index=len(rows),state='INTENT'))
            result=start(key,unit)
            if result.get('status')!='RETURNED' or result.get('slot')!=key:raise ValueError('RETURN_BINDING')
            row=dict(slot=key,state='RETURNED',receipt=result)
        except Exception as exc:
            row=dict(slot=key,state='FAILED',error=repr(exc))
            if unit.is_dir():
                with (unit/'failure.txt').open('x',encoding='utf8') as fp:fp.write(traceback.format_exc())
            rows.append(row);break
        rows.append(row)
    missing=list(order[len(rows):])
    result=dict(scheduled=order,rows=rows,unexecuted=missing,
        status='FAILED' if missing or any(r['state']=='FAILED' for r in rows) else 'ALL_RETURNED')
    save(out/'group.json',result)
    return result


def journal(out,unit,kind):
    with (out/'calls.jsonl').open('a',encoding='utf8') as fp:fp.write(json.dumps([unit,kind])+'\n')


def native_parent(phase,pin,h,out,plan,manifest):
    items=read(PK/'engineering-inputs.json.gz');order=phase_units(phase,plan)
    seen_pid=set()
    def start(key,unit):
        item=items[key]
        engineering_admit(pin['purpose'],'engineering',key,item,manifest)
        save(unit/'input.json',item)
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT/'scripts'),
            PYTHONNOUSERSITE='1',PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',GIT_CEILING_DIRECTORIES=str(ROOT.parent))
        args=[sys.executable,'-B',str(ROOT/'scripts/cold3_runner.py'),'child',h,phase,key]
        save(unit/'command.json',args)
        with (unit/'stdout.log').open('xb') as so,(unit/'stderr.log').open('xb') as se:
            child=subprocess.Popen(args,cwd=ROOT,env=env,stdout=so,stderr=se)
            code=child.wait()
        save(unit/'exit.json',dict(pid=child.pid,exit=code))
        if code!=0:raise RuntimeError('native child exit '+str(code))
        actual=read(unit/'return.json')
        if (actual['pid']!=child.pid or actual['pid'] in seen_pid or actual['parent_pid']!=os.getpid() or
            actual['input_sha256']!=manifest['engineering'][key] or actual['raw_sha256']!=sha(unit/'run.json.gz') or
            actual['public_decisions']!=49 or actual['release']!=h or actual['job']!=os.environ['SLURM_JOB_ID']):
            raise ValueError('ISOLATION_OR_RETURN_IDENTITY')
        seen_pid.add(child.pid)
        return actual
    return execute_group(out,order,start)


def child(h,phase,key):
    pin=release(h);plan=read(PK/'engineering-plan.json')
    if key not in phase_units(phase,plan):raise PermissionError('UNREGISTERED_SLOT')
    out=Path(pin['activity'])/phase;unit=out/key
    if not (out/'group.lock').is_file() or read(unit/'intent.json')['slot']!=key:raise PermissionError('NO_ADMISSION')
    item=read(unit/'input.json');manifest=read(PK/'input-freeze.json')
    engineering_admit(pin['purpose'],'engineering',key,item,manifest)
    cfg=item['dispatch_program']['policy_program'];clock=cfg['clock']
    if (set(item)!=set('scenario duration_s step_s boundary_events action_commands work_requests business_program dispatch_program private_physical_audit'.split()) or
        item['duration_s']!=12 or item['step_s']!=.01 or item['boundary_events'] or item['action_commands'] or item['work_requests']
        or item['business_program'] is not None or item['private_physical_audit'] is not True or clock!=[i/4 for i in range(49)]):
        raise PermissionError('ENGINEERING_H12_ONLY')
    from aegis_dc import joint_session
    from aegis_dc.plant import simulate_scenario
    original=joint_session.choose;count=0
    def observed(config,view):
        nonlocal count
        if count>=49 or view['time']!=clock[count]:raise PermissionError('INTERNAL_CLOCK_CAP')
        journal(out,key,'internal');count+=1
        if config!=cfg or set(view)!={'time','orders','issued','work','writes','paid','fixed'} or any(
                r['arrived']>view['time'] for channel in ('orders','work','writes','paid','fixed') for r in view[channel]):
            raise PermissionError('PUBLIC_BOUNDARY')
        answer=original(config,view)
        req=answer['request']
        if req and (not answer['selected']['admitted'] or req['at']!=view['time'] or
                    (cfg['method']=='J_NO_PROBE' and req['task'].endswith('/I'))):
            raise PermissionError('NATIVE_ADMISSION')
        with (unit/'decision-progress.jsonl').open('a',encoding='utf8') as fp:
            fp.write(json.dumps([view['time'],digest(view),req['task'] if req else None])+'\n')
        return answer
    save(unit/'native-start.json',dict(pid=os.getpid(),parent=os.getppid(),input=digest(item),release=h))
    with patch.object(joint_session,'choose',observed):
        journal(out,key,'facility')
        run=simulate_scenario(item['scenario'],duration_s=12,step_s=.01,dispatch_program=item['dispatch_program'],private_physical_audit=True)
    save(unit/'run.json.gz',run)
    runtime={f:v for f,v in pin['files'].items() if f.startswith('src/aegis_dc/') or f=='src/patrol_rsi/contracts.py'}
    stored=run['inputs']
    if (run['code_identity']['files']!=runtime or count!=49 or digest(run['source_config'])!=digest(item['scenario'])
        or digest(stored['dispatch_program'])!=digest(item['dispatch_program']) or not stored.get('private_physical_audit')
        or stored.get('boundary_events') or stored.get('action_commands') or stored.get('work_requests') or stored.get('business_program')
        or stored['duration_s']!=12 or stored['maximum_step_s']!=.01 or 'business_evaluation' in run):
        raise ValueError('SAVED_INPUT_OR_SOURCE_MISMATCH')
    save(unit/'return.json',dict(slot=key,status='RETURNED',pid=os.getpid(),parent_pid=os.getppid(),job=os.environ['SLURM_JOB_ID'],
        input_sha256=digest(item),raw_sha256=sha(unit/'run.json.gz'),runtime_tree=run['code_identity']['source_tree_sha256'],
        release=h,public_decisions=count))


if __name__=='__main__':
    if len(sys.argv)!=5 or sys.argv[1]!='child':raise SystemExit('A separately admitted H12 engineering child is required')
    child(*sys.argv[2:])
