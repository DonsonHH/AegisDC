"""Retain the native return before checking its canonical boundary order; all scientific rules are frozen."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import gzip
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import study

ACTIVITY=study.ACTIVITY
CORE=study.CORE
read,write,sha,require=study.read,study.write,study.sha,study.require
FAILED=('4-01','ORACLE')


def folder(key,mode):
    base=ACTIVITY/'positions'/(key+'-'+mode)
    return base/'attempt-02' if (key,mode)==FAILED else base


def retain(out,run):
    with gzip.open(out/'original.jsonl.gz','xt',encoding='utf8',compresslevel=1) as fp:
        def save(obj):fp.write(json.dumps(obj,separators=(',',':'),allow_nan=False)+'\n')
        save({'metadata':{k:v for k,v in run.items() if k not in ('trace','balances')}})
        for a,b in zip(run['trace'],run['balances']):save({'sample':a,'balance':b})
        save({'sample':run['trace'][-1]})


def position(key,mode,mh):
    if 'T2_CPU_ID' in os.environ:os.sched_setaffinity(0,{int(os.environ['T2_CPU_ID'])})
    _,core=study.pinned()
    ip=ACTIVITY/'study-inputs';require(sha(ip/'manifest.json')==mh and mode in study.ROLES,'manifest/role')
    m=read(ip/'manifest.json');path=ip/(key+'.json');require(sha(path)==m['files'][key],'whole input')
    x=read(path);item=x['native'];public=x['public']
    out=folder(key,mode);out.mkdir()
    write(out/'start.json',dict(job=os.environ['SLURM_JOB_ID'],pid=os.getpid(),key=key,mode=mode,input=sha(path),manifest=mh))
    sys.path[:0]=[str(CORE/'src'),str(CORE/'scripts')]
    from aegis_dc import joint_session
    from aegis_dc.plant import simulate_scenario
    from baselines import controller
    from oracle import schedule_certificate
    cert=schedule_certificate(x) if mode=='ORACLE' else None
    schedule=None if cert is None else cert['plan']
    original=joint_session.JointInspection
    def rights(scenario,catalog,program):
        plan=deepcopy(program)
        for b in plan['bindings']:b['fields']=deepcopy(public['read_rights'][b['task']])
        return original(scenario,catalog,plan)
    start=time.monotonic();cpu=time.process_time()
    with patch.object(joint_session,'choose',controller(mode,public,schedule)),patch.object(joint_session,'JointInspection',rights):
        run=simulate_scenario(**item)
    retain(out,run)
    expected=sorted(item['boundary_events'],key=lambda event:event['time_s'])
    identity={'source':run['code_identity']['source_tree_sha256']==core['core_tree'],
              'scenario':run['source_config']==item['scenario'],'public':run['inputs']['dispatch_program']==item['dispatch_program'],
              'boundary':run['inputs']['boundary_events']==expected,
              'window':run['inputs']['duration_s']==item['duration_s'] and run['inputs']['maximum_step_s']==item['step_s']}
    write(out/'identity.json',dict(checks=identity,input_event_order=item['boundary_events'],
                         native_return_event_order=run['inputs']['boundary_events']))
    require(all(identity.values()),'native return identity '+str(identity))
    score=study.make_score(run,x,mode)
    if cert:
        if cert['proof']=='NO_EFFECTIVE_WRITABLE_PARAMETER_HOLD_L_EQUALS_P':
            require(not cert['plan'] and not score['writes'] and not score['issues'],'invariant singleton trace')
            cert['lower']=score['L']
        cert['attained']=abs(cert['lower']-score['L'])<=1e-7 and abs(cert['lower']-score['U'])<=1e-7
        cert['issued_as_planned']=all([int(t),task] in [v[:2] for v in score['issues']] for t,task in cert['plan'].items())
    score.update(key=key,mode=mode,family=x['evaluation']['family'],input_sha256=sha(path),job=os.environ['SLURM_JOB_ID'],
        pid=os.getpid(),native_sha256=sha(out/'original.jsonl.gz'),runtime=core['core_tree'],oracle=cert,
        elapsed_s=time.monotonic()-start,process_cpu_s=time.process_time()-cpu)
    write(out/'result.json',score)
    if cert:require(cert['attained'] and cert['issued_as_planned'],'oracle bound not attained; retained')
    print(key,mode,score['L'],score['elapsed_s'],flush=True)


def recover_pilot(mh):
    start=time.monotonic()
    pin,_=study.pinned()
    first=read(ACTIVITY/'batches/pilot/terminal.json')
    require(first['job']=='134753' and first['entries']==[[*pair,int(tuple(pair)==FAILED)] for pair in pin['pilot']],
            'original terminal or failed suffix different')
    position(*FAILED,mh)
    elapsed=time.monotonic()-start
    units=[read(folder(k,m)/'result.json') for k,m in pin['pilot']]
    oracle=next(u for u in units if u['mode']=='ORACLE')
    require(oracle['oracle']['attained'] and oracle['oracle']['issued_as_planned'],'unqualified recovered pilot')
    # 134753 Slurm ElapsedRaw=94 includes the failed return. Re-use the same four original positions.
    longest=max([94,elapsed]+[u['elapsed_s'] for u in units])
    minutes=max(2,math.ceil((longest*1.25+15)/60))
    reservations=pin['input_and_pilot_reserved_CPU_s']+240+pin['readback_reserved_CPU_s']+188*minutes*60
    jobs=len(pin['batches'])+4
    write(ACTIVITY/'pilot-account.json',dict(manifest=mh,**{'continue':reservations<=57600 and jobs<=24},
        pilot_slots=pin['pilot'],pilot_completed=4,native_attempts_including_return_rejection=5,
        recovered_position=list(FAILED),first_pilot_job='134753',repair_job=os.environ['SLURM_JOB_ID'],
        initial_allocation_wall_s=94,recovery_wall_s=elapsed,slowest_s=longest,wall_s=[u['elapsed_s'] for u in units],
        cpu_s=[u['process_cpu_s'] for u in units],minutes_per_next_job=minutes,
        projected_reserved_CPU_s=reservations,planned_jobs=jobs,remaining_positions=188))
    print('PILOT GATE',read(ACTIVITY/'pilot-account.json'),flush=True)


def group(name,mh):
    pin,_=study.pinned()
    admission=read(ACTIVITY/'pilot-account.json')
    require(admission['continue'] and admission['manifest']==mh and sha(ACTIVITY/'study-inputs/manifest.json')==mh,'budget or frozen identity')
    tasks=pin['batches'][name];cpus=int(os.environ['SLURM_CPUS_PER_TASK']);require(cpus==len(tasks),'resource count')
    available=sorted(os.sched_getaffinity(0));require(len(available)>=cpus,'CPU affinity')
    log=ACTIVITY/'batches'/name;log.mkdir()
    write(log/'started.json',dict(job=os.environ['SLURM_JOB_ID'],manifest=mh,ordered=tasks,cpus=cpus))
    def one(pos):
        i,(key,mode)=pos;env=dict(os.environ,T2_CPU_ID=str(available[i]),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        with (log/(key+'-'+mode+'.log')).open('x') as f:
            ret=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'unit',key,mode,mh],env=env,
                               stdout=f,stderr=subprocess.STDOUT)
        return [key,mode,ret.returncode]
    with ThreadPoolExecutor(max_workers=cpus) as pool:results=list(pool.map(one,enumerate(tasks)))
    write(log/'terminal.json',dict(job=os.environ['SLURM_JOB_ID'],entries=results))
    require(all(v[-1]==0 for v in results),'group has preserved incomplete positions')
    print(name,len(results),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='repair':recover_pilot(sys.argv[2])
    elif sys.argv[1]=='unit':position(*sys.argv[2:])
    else:group(sys.argv[1],sys.argv[2])
