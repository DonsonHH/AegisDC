"""Serialize lightweight Slurm submissions and count actual reservations before accepting a job."""
from pathlib import Path
import fcntl
import json
import math
import os
import shlex
import subprocess
import sys

SOURCE=Path(__file__).resolve()
ROOT=SOURCE.parents[3]
ACT=ROOT.parent
PK=SOURCE.parent
POLICY=json.loads((PK/'settings-and-conditions.json').read_bytes())
FIXED={'input_authoring':('prepare.py',),'noninterference':('isolation_guard.py',),'failure_readback':('failure_readback.py',),
       'pilot':('execute_panel.py','pilot'),'final_readback_bootstrap':('analyse.py',)}
PY='/share/home/renly/miniconda3/bin/python'


def minutes(slurm):
    days,sep,clock=slurm.partition('-')
    parts=[int(t) for t in (clock if sep else slurm).split(':')]
    if len(parts)==2:parts.insert(0,0)
    return (int(days)*1440 if sep else 0)+parts[0]*60+parts[1]+math.ceil(parts[2]/60)


def allocation(job_id):
    out=subprocess.check_output(['scontrol','show','job','-o',str(job_id)],text=True)
    values=dict(pair.split('=',1) for pair in out.split() if '=' in pair)
    return int(values['NumCPUs']),minutes(values['TimeLimit'])


def resources(name):
    if name in FIXED:
        cores,limit=POLICY['fixed_allocations'][name]
        return cores,limit,FIXED[name]
    if name not in POLICY['groups']:raise ValueError('Unknown position group')
    gate=json.loads((ACT/'pilot.json').read_bytes())
    if not gate['continue']:raise ValueError('Pilot budget stop')
    return POLICY['groups'][name]['cpus'],gate['group_minutes'][name],('execute_panel.py',name)


def main(names,dependencies):
    source=os.environ['T4D_SOURCE'];inputs=os.environ.get('T4D_INPUTS')
    reg=ACT/'registrations';reg.mkdir(exist_ok=True)
    with (reg/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for name in names:
            path=reg/(name+'.json');pending=reg/(name+'.intent')
            if path.exists() or pending.exists():raise ValueError('Previously submitted or unsettled '+name)
            if list(reg.glob('*.intent')):raise ValueError('Unsettled Slurm submission must be reconciled first')
            ledger=[json.loads(f.read_bytes()) for f in reg.glob('*.json')]
            cores,limit,command=resources(name)
            if len(ledger)+1>POLICY['max_jobs'] or sum(z['reserved_s'] for z in ledger)+60*cores*limit>POLICY['max_reserved_cpu_s']:
                raise ValueError('Actual job or reservation cap')
            known={r['job'] for r in ledger}
            if not set(dependencies)<=known:raise ValueError('Unknown Slurm dependency')
            if name!='input_authoring' and not inputs:raise ValueError('Missing published input commitment')
            exports={'T4D_SOURCE':source,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
            if inputs:exports['T4D_INPUTS']=inputs
            wrap='umask 077 && cd '+shlex.quote(str(ROOT))+' && export '+ ' '.join(k+'='+shlex.quote(v) for k,v in exports.items())
            wrap+=' && exec '+shlex.join([PY,'-B',str(PK/command[0]),*command[1:]])
            mem=str(2+cores)+'G' if name!='final_readback_bootstrap' else '5G'
            args=['sbatch','--parsable','-p','cu','--nodes=1','--ntasks=1','--cpus-per-task='+str(cores),'--time='+str(limit),'--mem='+mem,
                '--job-name=T4d-'+name,'--output='+str(ACT/'logs/%j.out'),'--error='+str(ACT/'logs/%j.err')]
            if dependencies:args+=['--dependency=afterok:'+':'.join(dependencies),'--kill-on-invalid-dep=yes']
            item=dict(name=name,cores=cores,minutes=limit,reserved_s=60*cores*limit,depends=dependencies,source=source,inputs=inputs,mem=mem)
            with pending.open('x') as dest:json.dump(item,dest)
            job=subprocess.check_output([*args,'--wrap='+wrap],text=True).strip().split(';')[0]
            item['job']=job
            with path.open('x') as dest:json.dump(item,dest)
            pending.unlink()
            if allocation(job)!=(cores,limit):raise ValueError('Slurm changed the requested resources: '+job)
            print(name,job,flush=True)

if __name__=='__main__':
    d=sys.argv[2].split(':') if len(sys.argv)>2 and sys.argv[2] else []
    main(sys.argv[1].split(','),d)
