"""Confirmation admissions and empirical CPU projection (login-node bookkeeping only)."""
import fcntl
import json
import math
from pathlib import Path
import shlex
import subprocess
import sys
import time

from schedule import ACT,PY,accounting,check,read,save,seconds

PK=Path(__file__).resolve().parent
OUT=ACT/"confirmation"
ROLES=("S","W","V_COST","M_HOT","B_COST","P","PERIODIC","ALARM","ORACLE")
BATCHES=tuple(f"batch-{i:02}" for i in range(1,27))


def targets(order):
    full=[(key,r) for key in order for r in ROLES]+[(k,"MIRROR") for k in order[:3]]
    pilots=[(order[0],r) for r in ROLES]+[(order[i],r) for i,r in ((1,"S"),(2,"S"),(3,"W"),(4,"ORACLE"),(5,"V_COST"))]+[(k,"MIRROR") for k in order[:3]]
    rest=[x for x in full if x not in pilots]
    check(len(full)==len(set(full))==327 and len(pilots)==17 and len(rest)==310,"exact new positions")
    return pilots,{name:rest[i::26] for i,name in enumerate(BATCHES)}


def projection():
    j=read(OUT/"registrations/pilot.json")["job"];bill=accounting(j);p,groups=targets(read(OUT/"panel.json")["order"])
    durations={r:[] for r in [*ROLES,"MIRROR"]};bad=[]
    for k,r in p:
        pos=read(OUT/"positions"/k/r/"row.json")
        if pos["status"]!="SCORED":bad.append([k,r])
        durations[r].append((pos["wall_s"],pos["cpu_s"]))
    av={r:tuple(sum(t[i] for t in ts)/len(ts) for i in range(2)) for r,ts in durations.items()}
    plan={};reasons=[]
    if bad:reasons.append("pilot has incomplete required records")
    if bill["reserved_s"]>2*bill["process_s"]:reasons.append("pilot reservation > twice actual CPU")
    for name,positions in groups.items():
        loads=[0.,0.,0.];lanes=[[],[],[]]
        for k,r in sorted(positions,key=lambda x:-av[x[1]][0]):
            i=loads.index(min(loads));lanes[i].append([k,r]);loads[i]+=av[r][0]
        expected=sum(av[r][1] for k,r in positions)
        minutes=math.ceil((1.15*max(loads)+(24 if name==BATCHES[-1] else 0))/60)
        reserve=3*60*minutes
        if reserve>2*expected:reasons.append(name+" reservation > twice projected process CPU")
        plan[name]=dict(lanes=lanes,minutes=minutes,cpus=3,expected_process_s=expected,reserved_s=reserve)
    total=720+bill["reserved_s"]+sum(x["reserved_s"] for x in plan.values())
    if total>108000:reasons.append("work-package 30 CPU hour ceiling")
    obj=dict(pilot=bill,by_role=av,projected_jobs=29,projected_reserved_cpu_s=total,plan=plan,reasons=reasons,proceed=not reasons)
    save(OUT/"budget.json",obj);print("projection",total,"CPU seconds / 29 jobs",reasons,flush=True)


def await_publication(name,artifact):
    import hashlib
    end=time.monotonic()+135
    while not (OUT/("published-"+name+".json")).is_file():
        if time.monotonic()>end:raise TimeoutError("no published "+name+" receipt")
        time.sleep(.5)
    marker=read(OUT/("published-"+name+".json"))
    check(marker["sha256"]==hashlib.sha256(artifact.read_bytes()).hexdigest() and len(marker["commit"])==40,"published "+name+" bytes")
    return marker


def submit(name):
    regs=OUT/"registrations";release=read(OUT/"release.json")
    if name=="pilot":cpus,minutes=3,14
    else:
        budget=read(OUT/"budget.json");check(name in BATCHES and budget["proceed"],"measured total")
        cpus,minutes=budget["plan"][name]["cpus"],budget["plan"][name]["minutes"]
        if name==BATCHES[-1]:
            check(all((OUT/"jobs"/n/"terminal.json").is_file() for n in BATCHES[:-1]),"all previous batches terminal")
    allocated=[read(p) for p in regs.glob("*.json")]
    check(len(allocated)+3<=40 and 720+sum(x["reserved_s"] for x in allocated)+cpus*minutes*60<=108000,"combined execution envelope")
    record=dict(name=name,source=release["commit"],cpus=cpus,minutes=minutes,reserved_s=cpus*minutes*60)
    wrap="umask 077 && exec "+shlex.join(["env","OPENBLAS_NUM_THREADS=1","OMP_NUM_THREADS=1","PYTHONDONTWRITEBYTECODE=1",
                                   PY,"-B",str(PK/"confirmation.py"),name])
    cmd=["sbatch","--hold","--no-requeue","--parsable","-p","cu","-N","1","-n","1","-c",str(cpus),"--time="+str(minutes),
         "--mem=10G","--job-name=c3n-"+name,"--output="+str(OUT/"logs/%j.out"),"--error="+str(OUT/"logs/%j.err"),"--wrap="+wrap]
    save(regs/(name+".intent"),dict(record,cmd=cmd));jid=subprocess.check_output(cmd,text=True).strip().split(";")[0]
    check(jid.isdigit(),"Slurm registration");save(regs/(name+".json"),dict(record,job=jid))
    fields=dict(x.split("=",1) for x in subprocess.check_output(["scontrol","show","job","-o",jid],text=True).split() if "=" in x)
    check(int(fields["NumCPUs"])==cpus and seconds(fields["TimeLimit"])==minutes*60,"Slurm allocation")
    subprocess.run(["scontrol","release",jid],check=True);print(name,jid,flush=True)


if __name__=="__main__":
    with (OUT/"registrations"/".lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if sys.argv[1]=="budget":projection()
        else:
            for token in sys.argv[1:]:submit(token)
