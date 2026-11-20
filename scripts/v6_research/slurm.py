"""Selected production transport: one held, recorded, released Slurm job at a time."""
import os
from pathlib import Path
import subprocess
import time

from .binding import PACK, PYTHON, GateError, check

BIN=Path('/share/software/slurm-22.05.11/bin')


def run(*args):
    proc=subprocess.run([str(BIN/args[0]),*args[1:]],capture_output=True,text=True,timeout=20)
    check(proc.returncode==0,'SCHEDULER_IO',proc.stderr[-500:])
    return proc.stdout.strip()


def memory_mib(token):
    if token in ('1G','1024M','1024'):return 1024
    return None


class Slurm:
    def __init__(self, command=run, pause=time.sleep):
        self.command=command
        self.pause=pause

    def submit_held(self,case,jobdir,release):
        args=['sbatch','--parsable','--hold','--no-requeue','--partition=cu','--nodes=1','--ntasks=1','--cpus-per-task=1',
              '--mem=1G','--time=00:02:00','--job-name=v6-study-'+case,'--chdir='+str(release.root),
              '--output='+str(jobdir/'slurm-%j.out'),'--error='+str(jobdir/'slurm-%j.err'),
              str(release.root/PACK/'study.sbatch'),str(release.root),release.sha,case]
        from .control import once
        once(jobdir/'scheduler-command.json',args)
        return self.command(*args).split(';')[0]

    def release(self,job,case,jobdir):
        self.command('scontrol','release',job)

    def observe(self,job):
        check(job.isdecimal(),'JOB_IDENTITY')
        live_states={'PENDING','RUNNING','COMPLETING','CONFIGURING','SUSPENDED','RESIZING','SIGNALING','STAGE_OUT'}
        raw=self.command('sacct','-X','-nP','-j',job,'-o','JobIDRaw,State,ExitCode,ElapsedRaw')
        lines=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
        if lines:
            check(len(lines)==1,'JOB_IDENTITY')
            _,state,rc,elapsed=lines[0][:4]
            state=state.split()[0].rstrip('+')
            return dict(job=job,state=state,exit=rc,elapsed_s=int(elapsed),live=state in live_states)
        queue=self.command('squeue','-h','-j',job,'-o','%i|%T')
        active=[r for r in queue.splitlines() if r.split('|')[0]==job]
        if active:
            return dict(job=job,state=active[0].split('|')[1],exit=None,elapsed_s=None,live=True)
        return dict(job=job,state='UNRESOLVED',exit=None,elapsed_s=None,live=False)

    def terminal(self,job):
        missing=0
        while True:
            try:
                record=self.observe(job)
                if record['live']:
                    missing=0
                elif record['state']!='UNRESOLVED':
                    return record
                else:
                    missing+=1
            except (OSError,subprocess.SubprocessError,GateError):
                missing+=1
            if missing>=3:return dict(job=job,state='UNRESOLVED',exit=None,elapsed_s=None)
            self.pause(5)


def current_allocation(command=run, environ=None):
    environ=os.environ if environ is None else environ
    job=environ.get('SLURM_JOB_ID','')
    check(job.isdecimal(),'JOB_IDENTITY')
    raw=command('scontrol','show','job','-o',job)
    f=dict(token.split('=',1) for token in raw.split() if '=' in token)
    check(f['JobId']==job and environ.get('SLURM_CPUS_PER_TASK')=='1' and environ.get('SLURM_MEM_PER_NODE')=='1024','ALLOCATION')
    memory=memory_mib(f.get('MinMemoryNode',''))
    if memory is None:
        tres=dict(item.split('=',1) for item in f.get('ReqTRES',f.get('TRES','')).split(',') if '=' in item)
        memory=memory_mib(tres.get('mem',''))
    allocation=dict(item.split('=',1) for item in f.get('AllocTRES',f.get('TRES','')).split(',') if '=' in item)
    check('cpu' in allocation,'ALLOCATION')
    gpu=sum(int(v) for k,v in allocation.items() if 'gpu' in k.lower())
    return dict(gpus=gpu,job=job,name=f['JobName'],cpus=int(f['NumCPUs']),mem_MiB=memory,
        seconds=120 if f['TimeLimit']=='00:02:00' else None,nodes=int(f['NumNodes']),partition=f['Partition'],
        restart=max(int(environ.get('SLURM_RESTART_COUNT','0')),int(f.get('Restarts','0'))),requeue=int(f['Requeue']),
        state=f['JobState'],user=f['UserId'].split('(')[0])
