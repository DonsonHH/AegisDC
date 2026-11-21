"""Recover only the two pre-native missing-import entries. Use unmodified frozen scientific sources."""
from concurrent.futures import ThreadPoolExecutor
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from common import *
import execute

FAILED=(('4-01','ORACLE'),('6-01','ORACLE'))
RECOVERY=REMOTE/'pre-native-import-recovery'


def main(manifest):
    spec,_=execute.pinned();old=load(REMOTE/'batches/pilot/terminal.json')
    insist(old['job']=='134777' and old['manifest']==manifest and
        old['entries']==[[*p,int(tuple(p) in FAILED)] for p in spec['pilot']],'original pilot terminal')
    insist(os.environ['SLURM_CPUS_PER_TASK']=='2','recovery reservation')
    for k,role in FAILED:
        d=REMOTE/'positions'/(k+'-'+role)
        insist(d.is_dir() and sorted(v.name for v in d.iterdir())==['entry.json'],'preserve pre-native failure')
    RECOVERY.mkdir();(RECOVERY/'positions').mkdir()
    (RECOVERY/'development-inputs').symlink_to(REMOTE/'development-inputs',target_is_directory=True)
    cpus=sorted(os.sched_getaffinity(0));start=time.monotonic()
    def one(args):
        i,(k,r)=args;env=dict(os.environ,T3_CPU=str(cpus[i]),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        with (RECOVERY/(k+'-'+r+'.log')).open('x') as fp:
            return subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'unit',k,r,manifest],
                env=env,stdout=fp,stderr=subprocess.STDOUT).returncode
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(one,enumerate(FAILED)))
    write(RECOVERY/'terminal.json',dict(job=slurm(),keys=FAILED,exit=statuses,manifest=manifest))
    insist(statuses==[0,0],'retain recovery terminal')
    names=spec['pilot'];parts=[]
    for k,r in names:
        folder=RECOVERY if (k,r) in FAILED else REMOTE
        part=load(folder/'positions'/(k+'-'+r)/'result.json')
        insist(part['manifest']==manifest and part['passed'] and part['clocks']==61,'complete pilot')
        if r=='ORACLE':insist(part['oracle']['attained'] and part['oracle']['applied_as_planned'],'native oracle witness')
        parts.append(part)
    elapsed=time.monotonic()-start;maximum=max([94,elapsed]+[v['elapsed_s'] for v in parts])
    limit=math.ceil((maximum*1.25+15)/60)
    projected=spec['dev_initial_reserved_CPU_s']+480+282*limit*60+spec['dev_read_reserved_CPU_s']
    jobs=len(spec['groups'])+4
    write(REMOTE/'pilot-account.json',dict(manifest=manifest,**{'continue':jobs<=24 and projected<=72000},
        first_job='134777',retry_job=slurm(),pre_native_failures=FAILED,unique_pilot_positions=6,
        elapsed=[v['elapsed_s'] for v in parts],cpu=[v['cpu_s'] for v in parts],initial_sacct_elapsed=94,
        recovered_wall_s=elapsed,max_wall_s=maximum,limit_minutes=limit,projected_CPU_s=projected,projected_jobs=jobs))
    print(load(REMOTE/'pilot-account.json'),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='unit':
        execute.REMOTE=RECOVERY
        execute.unit('development',*sys.argv[2:])
    else:main(sys.argv[1])
