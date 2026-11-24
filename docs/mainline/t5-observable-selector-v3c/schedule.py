"""Register held jobs, measure the pilot with step accounting, and enforce the ceiling."""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys

PK=Path(__file__).resolve().parent
ACT=Path("/share/home/renly/renly-patrol-rsi/mainline/T5-observable-selector-v3c")
PY="/share/home/renly/miniconda3/bin/python"


def read(p):return json.loads(p.read_bytes())


def save(p,v):
    with p.open("x") as f:
        json.dump(v,f,sort_keys=True,separators=(",",":"));f.write("\n");f.flush();os.fsync(f.fileno())


def check(ok,msg):
    if not ok:raise ValueError(msg)


def seconds(field):
    d,_,rest=field.rpartition("-");n=0.
    for v in rest.split(":"):n=n*60+float(v)
    return n+(int(d) if d else 0)*86400


def accounting(j):
    names="JobID,State,ExitCode,ElapsedRaw,AllocCPUS,TimelimitRaw,TotalCPU,UserCPU,SystemCPU,Start,End,NodeList"
    out=subprocess.check_output(["sacct","-n","-P","-j",j,"-o",names],text=True)
    table={x[0]:dict(zip(names.split(","),x,strict=True)) for line in out.splitlines() if (x:=line.split("|")) and len(x)==12}
    job=table[j];step=table[j+".batch"]
    check(job["State"]==step["State"]=="COMPLETED" and job["ExitCode"]==step["ExitCode"]=="0:0"
          and job["TotalCPU"]==step["TotalCPU"],"completed original job with measured batch TotalCPU")
    return dict(job,process_s=seconds(job["TotalCPU"]),reserved_s=int(job["AllocCPUS"])*int(job["TimelimitRaw"])*60)


def budget():
    reg=read(ACT/"registrations/pilot.json");state=read(ACT/"pilot.json");a=accounting(reg["job"])
    check(state["job"]==reg["job"] and state["status"]=="PASS" and len(state["inspected_keys"])==12,"complete two-per-family pilot")
    cpu=a["process_s"];wall=int(a["ElapsedRaw"]);cpus=2
    minutes=math.ceil(1.15*2*max(wall,cpu/cpus)/60)
    cost=cpus*minutes*60; projection=2*cpu
    b=dict(pilot=a,estimated_remaining_process_s=projection,minutes=minutes,cpus=cpus,reserved_remaining_s=cost,
           projected_jobs=2,projected_reserved_s=a["reserved_s"]+cost,
           proceed=a["reserved_s"]<=2*cpu and cost<=2*projection and a["reserved_s"]+cost<=108000)
    save(ACT/"budget.json",b);print(json.dumps(b),flush=True)


def submit(name):
    reg=ACT/"registrations";pub=read(ACT/"release.json")
    for k,h in pub["files"].items():
        check(hashlib.sha256((PK/k).read_bytes()).hexdigest()==h,"published "+k)
    if name=="pilot":
        cpus,mins=2,2
    else:
        b=read(ACT/"budget.json")
        check(name=="remaining" and b["proceed"],"measured budget stop")
        cpus,mins=b["cpus"],b["minutes"]
    placed=list(reg.glob("*.json"))
    check(len(placed)+1<=40 and sum(read(p)["reserved_s"] for p in placed)+cpus*mins*60<=108000,"all-job ceiling")
    env=["OPENBLAS_NUM_THREADS=1","OMP_NUM_THREADS=1","PYTHONDONTWRITEBYTECODE=1"]
    wrap="umask 077 && exec "+shlex.join(["env",*env,PY,"-B",str(PK/"development.py"),name])
    cmd=["sbatch","--hold","--no-requeue","--parsable","-p","cu","-N","1","-n","1","-c",str(cpus),
         "--time="+str(mins),"--mem=6G","--job-name=c3-"+name,"--output="+str(ACT/"logs/%j.out"),"--error="+str(ACT/"logs/%j.err"),"--wrap="+wrap]
    entry=dict(name=name,source=pub["commit"],cpus=cpus,minutes=mins,reserved_s=cpus*mins*60)
    save(reg/(name+".intent"),dict(entry,cmd=cmd))
    jid=subprocess.check_output(cmd,text=True).strip().split(";")[0];check(jid.isdigit(),"Slurm ID")
    save(reg/(name+".json"),dict(entry,job=jid))
    show=subprocess.check_output(["scontrol","show","job","-o",jid],text=True)
    fields=dict(x.split("=",1) for x in show.split() if "=" in x)
    check(int(fields["NumCPUs"])==cpus and seconds(fields["TimeLimit"])==mins*60,"actual resources")
    subprocess.run(["scontrol","release",jid],check=True);print(name,jid,flush=True)


if __name__=="__main__":
    with (ACT/"registrations"/".lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if sys.argv[1]=="budget":budget()
        else:submit(sys.argv[1])
