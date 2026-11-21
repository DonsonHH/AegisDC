"""Cold resources and commands on the established held-job Slurm transport."""
import os
import re
import socket
from pathlib import Path
from v6_research.control import once
from v6_research.slurm import Slurm, run
from .binding import CLI, DEPLOY, PACK, PYTHON, check


def commands():
    entry=[PYTHON,'-I','-B',str(DEPLOY/CLI)]
    return dict(start=entry+['start','--manifest-sha','{launch}','--approval-revision','{review}'],
        status=entry+['status','--manifest-sha','{launch}'],
        worker=entry+['worker','--manifest-sha','{launch}','--case','{row}'],
        arm=entry+['arm','--manifest-sha','{launch}','--case','{row}','--slot','{slot}'],
        submit=['sbatch','--parsable','--hold','--no-requeue','--partition=cu','--nodes=1','--ntasks=1',
            '--cpus-per-task=1','--mem=4G','--time=00:05:00','--job-name=cold3-study-{row}',f'--chdir={DEPLOY}',
            '--output={jobdir}/slurm-%j.out','--error={jobdir}/slurm-%j.err',str(DEPLOY/PACK/'study.sbatch'),str(DEPLOY),'{launch}','{row}'],
        release=['scontrol','release','{job}'],observe=['sacct','-X','-nP','-j','{job}','-o','JobIDRaw,State,ExitCode,ElapsedRaw'])


def argv(rel,name,**fields):
    return [arg.format(launch=rel.sha,**fields) for arg in rel.manifest['commands'][name]]


class ColdSlurm(Slurm):
    def submit_held(self,case,jobdir,release):
        args=argv(release,'submit',row=case,jobdir=str(jobdir))
        once(jobdir/'scheduler-command.json',args)
        return self.command(*args).split(';')[0]


def allocation(command=run,environ=None):
    env=os.environ if environ is None else environ
    job=env.get('SLURM_JOB_ID','');check(job.isdecimal(),'JOB_IDENTITY')
    f=dict(x.split('=',1) for x in command('scontrol','show','job','-o',job).split() if '=' in x)
    check(f.get('JobId')==job,'JOB_IDENTITY')
    tres=dict(x.split('=',1) for x in f.get('AllocTRES',f.get('TRES','')).split(',') if '=' in x)
    req=dict(x.split('=',1) for x in f.get('ReqTRES','').split(',') if '=' in x)
    mem=f.get('MinMemoryNode',req.get('mem'))
    check(env.get('SLURM_CPUS_PER_TASK')=='1' and env.get('SLURM_MEM_PER_NODE')=='4096' and tres.get('cpu')=='1'
          and mem in ('4G','4096M','4096'),'ALLOCATION')
    node=socket.gethostname().split('.')[0]
    check(f.get('BatchHost',f.get('NodeList'))==node and f.get('NodeList')==node and
          env.get('SLURMD_NODENAME',node)==node and int(f.get('NumNodes','0'))==1,'ALLOCATION')
    cg=Path('/proc/self/cgroup')
    inside=cg.is_file() and re.search(r'(?:^|/)job[_-]'+re.escape(job)+r'(?:/|\.scope|\.slice|$)',cg.read_text(),re.M) is not None
    if not inside:
        ids=command('scontrol','listpids',job,node)
        inside=any(len(parts)>1 and parts[0]==str(os.getpid()) and parts[1].split('.')[0]==job
                   for parts in (line.split() for line in ids.splitlines()))
    check(inside,'ALLOCATION')
    reported=tres.get('mem')
    check(reported is None or reported in ('4G','4096M','4096'),'ALLOCATION')
    return dict(node=node,process_membership=True,allocated_mem_tres=reported,
        memory_basis='Slurm allocation TRES and request' if reported else 'Slurm per-node request and live allocation environment; memory TRES unadvertised',job=job,name=f['JobName'],user=f['UserId'].split('(')[0],state=f['JobState'],partition=f['Partition'],
        nodes=int(f['NumNodes']),cpus=int(f['NumCPUs']),mem_mib=4096,seconds=300 if f['TimeLimit']=='00:05:00' else None,
        gpus=sum(int(v) for k,v in tres.items() if 'gpu' in k),requeue=int(f['Requeue']),
        restarts=max(int(f.get('Restarts','0')),int(env.get('SLURM_RESTART_COUNT','0'))))
