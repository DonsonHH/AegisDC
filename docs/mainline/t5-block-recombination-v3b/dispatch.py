"""Submit each allowed batch once, recording the intent and the held Slurm ID before release."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ACT=Path("/share/home/renly/renly-patrol-rsi/mainline/T5-block-recombination-v3b")
PY="/share/home/renly/miniconda3/bin/python"
MAPS=tuple(f"map-{h}-{f}" for h in ("A","B") for f in range(1,7))
NATIVES=tuple(f"native-{f}" for f in range(1,7))
RES={"selfcheck":(1,5,3),"construct":(1,8,3),"report":(1,8,4),
     **dict.fromkeys(MAPS,(4,20,8)),**dict.fromkeys(NATIVES,(6,6,12))}


def read(p):
    return json.loads(p.read_bytes())


def save(p,value):
    with p.open("x") as out:
        json.dump(value,out,sort_keys=True,separators=(",",":"));out.write("\n");out.flush();os.fsync(out.fileno())


def need(ok,reason):
    if not ok:
        raise ValueError(reason)


def sha(p):
    with p.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def submit(name):
    cpus,minutes,gb=RES[name]
    release=read(ACT/"release.json")
    for fn,h in release["files"].items():
        need(sha(HERE/fn)==h,"staged file changed: "+fn)
    registrations=ACT/"registrations"
    need(not (registrations/(name+".json")).exists() and not (registrations/(name+".intent")).exists(),"already registered: "+name)
    if name!="selfcheck":
        need(read(ACT/"selfcheck.json")["status"]=="PASS","self-check not passed")
    if name=="construct":
        need(all((ACT/"jobs"/n/"terminal.json").exists() for n in MAPS),"incomplete replay batches")
    construction=None
    if name in NATIVES or name=="report":
        construction=sha(ACT/"construction.json")
        need(construction==sha(HERE/"construction.json") and
             construction==read(ACT/"published-construction.json")["sha256"],"publish exact construction first")
        if name in NATIVES:
            need(read(ACT/"construction.json")["construction"]["status"]=="LOCKED","no MAIN vector")
        elif read(ACT/"construction.json")["construction"]["status"]=="LOCKED":
            need(all((ACT/"jobs"/n/"terminal.json").exists() for n in NATIVES),"incomplete native batches")
    env={"STAGE_A_JOB":name,"STAGE_A_RELEASE":release["commit"],"OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1","PYTHONDONTWRITEBYTECODE":"1"}
    wrap="umask 077 && exec "+shlex.join(["env",*(k+"="+v for k,v in env.items()),PY,"-B",str(HERE/"execute.py"),name])
    cmd=["sbatch","--hold","--no-requeue","--parsable","--partition=cu","--nodes=1","--ntasks=1",
         "--cpus-per-task="+str(cpus),"--mem="+str(gb)+"G","--time="+str(minutes),"--job-name=b3-"+name,
         "--output="+str(ACT/"logs/%j.out"),"--error="+str(ACT/"logs/%j.err"),"--wrap="+wrap]
    details=dict(name=name,release=release["commit"],files=release["files"],construction=construction,cpus=cpus,minutes=minutes,reserved_s=minutes*cpus*60)
    save(registrations/(name+".intent"),dict(details,command=cmd))
    jid=subprocess.check_output(cmd,text=True).strip().split(";")[0]
    need(jid.isdigit(),"unresolved Slurm receipt")
    save(registrations/(name+".json"),dict(details,job=jid))
    fields=dict(p.split("=",1) for p in subprocess.check_output(["scontrol","show","job","-o",jid],text=True).split() if "=" in p)
    need(int(fields["NumCPUs"])==cpus and fields["TimeLimit"]==f"00:{minutes:02}:00","actual resource request")
    subprocess.run(["scontrol","release",jid],check=True)
    print(name,jid,flush=True)


if __name__=="__main__":
    with (ACT/"registrations"/".lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for name in sys.argv[1:]:
            submit(name)
