"""Enforce the frozen once-per-target read entitlement across distinct task IDs."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import checked_execution as execution

ACTIVITY=execution.ACTIVITY
AUDIT_SHA='b382d8899f451c0a58fdc88e5b726cdc2d3954b7273440a022d581afef199a39'
AFFECTED=(('1-02','PERIODIC'),('3-02','PERIODIC'),('4-02','PERIODIC'),('1-03','PERIODIC'),
          ('3-03','PERIODIC'),('4-03','PERIODIC'),('1-04','PERIODIC'))
base_folder=execution.folder


def final_folder(key,mode):
    base=base_folder(key,mode)
    return base/'entitlement-attempt-02' if (key,mode) in AFFECTED else base


def limited_producer(native):
    class OncePerTarget(native):
        def __init__(self,*args):
            super().__init__(*args)
            self.consumed={}
        def process(self,time_s,workforce,point):
            offset=len(self.rows);previous={}
            # An initial read can be addressed by more than one work-order identity.
            # After its physical acquisition later visits still do all work and earn an
            # availability receipt; they cannot measure this same target and phase again.
            for task,binding in self.bindings.items():
                token=(binding['target'],task.rsplit('/',1)[1])
                if token in self.consumed and self.consumed[token]!=task and task not in self.done:
                    previous[task]=binding['fields']
                    binding['fields']=dict.fromkeys(binding['fields'])
            try:super().process(time_s,workforce,point)
            finally:
                for task,fields in previous.items():self.bindings[task]['fields']=fields
            for row in self.rows[offset:]:
                if row['interval'] is None:continue
                token=(row['target'],row['phase'])
                if self.consumed.setdefault(token,row['task'])!=row['task']:
                    raise ValueError('duplicate quantitative acquisition')
        def private_audit(self):
            result=super().private_audit()
            result['consumed_entitlements']=[dict(target=k[0],phase=k[1],task=v) for k,v in sorted(self.consumed.items())]
            return result
    return OncePerTarget


def unit(key,mode,manifest):
    sys.path[:0]=[str(execution.CORE/'src'),str(execution.CORE/'scripts')]
    from aegis_dc import joint_session
    saved=execution.read(ACTIVITY/'study-inputs'/(key+'.json'))
    if not saved['public']['once_per_named_target']:raise ValueError('missing public entitlement')
    with patch.object(joint_session,'JointInspection',limited_producer(joint_session.JointInspection)),patch.object(execution,'folder',final_folder):
        execution.position(key,mode,manifest)


def run_group(name,manifest):
    pin,_=execution.study.pinned()
    gate=execution.read(ACTIVITY/'pilot-account.json')
    assert gate['continue'] and gate['manifest']==manifest and execution.sha(ACTIVITY/'study-inputs/manifest.json')==manifest
    assert execution.sha(ACTIVITY/'observation-scope-audit.json')==AUDIT_SHA
    audited=execution.read(ACTIVITY/'observation-scope-audit.json')
    assert set(map(tuple,audited['affected']))==set(AFFECTED)
    tasks=list(AFFECTED) if name=='rights-recovery' else list(map(tuple,pin['batches'][name]))
    assert name=='rights-recovery' or name not in ('group_01','group_02','group_03')
    assert int(os.environ['SLURM_CPUS_PER_TASK'])==len(tasks)
    cpus=sorted(os.sched_getaffinity(0));assert len(cpus)>=len(tasks)
    job=os.environ['SLURM_JOB_ID'];log=ACTIVITY/'batches'/name;log.mkdir()
    execution.write(log/'started.json',dict(job=job,manifest=manifest,ordered=tasks,cpus=len(tasks)))
    def one(index_and_pair):
        i,(key,mode)=index_and_pair
        env=dict(os.environ,T2_CPU_ID=str(cpus[i]),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        with (log/(key+'-'+mode+'.log')).open('x') as f:
            rc=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'unit',key,mode,manifest],
                              env=env,stdout=f,stderr=subprocess.STDOUT).returncode
        return [key,mode,rc]
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:results=list(pool.map(one,enumerate(tasks)))
    execution.write(log/'terminal.json',dict(job=job,entries=results))
    if any(q[-1] for q in results):raise RuntimeError('preserved nonreturn')
    print(name,job,len(results),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='unit':unit(*sys.argv[2:])
    else:run_group(*sys.argv[1:])
