"""Register one Slurm allocation for each frozen batch and keep cumulative reservations."""
from collections import Counter
import fcntl
import os
from pathlib import Path
import shlex
import subprocess
import sys

from context_t5 import ACT, LOCK, PK, cases, read, require, settings, sha, verify_sources, write
from run_plan import expected_positions,fit_groups,projection


def ledger():
    return sorted((read(f) for f in (ACT/"registrations").glob("*.json")),key=lambda z:int(z["job"]))


def status(rows, usage=False):
    fields=("JobID","JobName%36","State","ExitCode","ElapsedRaw","AllocCPUS","TimelimitRaw","TotalCPU","Start","End","NodeList")
    if not rows:
        return {}
    ids={r["job"] for r in rows}
    cmd=["sacct","-n","-P","-j",",".join(sorted(ids)),"-o",",".join(fields)]
    if not usage:
        cmd.insert(1,"-X")
    out=subprocess.check_output(cmd,text=True)
    return {values[0]:dict(zip(fields,values,strict=True)) for line in out.splitlines()
            if (values:=line.split("|"))[0] in ids}


def completed(row):
    return row and row["State"]=="COMPLETED" and row["ExitCode"]=="0:0"


def budget():
    require(not (ACT/"pilot-budget.json").exists(),"budget registration exists")
    records=ledger()
    result=next(r for r in records if r["name"]=="pilot")
    a=status(records)
    proof=read(ACT/"batches/pilot/return.json")
    require(completed(a.get(result["job"])) and len(proof["positions"])==24
            and all(r["entered"] and r["scored"] and not r["exit_code"] for r in proof["positions"]),"full pilot required")
    estimate=projection(proof["wall_s"],records)
    save=dict(estimate,pilot=result["job"],complete_wall_s=proof["wall_s"],before=len(records),input=os.environ["T5_INPUT_SHA"])
    write(ACT/"pilot-budget.json",save)
    print(save,flush=True)


def resources(name,records):
    design,space,u=settings()
    if name=="prepare":
        require(not records,"single authoring and self-check")
        return 1,8,"3G","prepare.py",[],[]
    manifest=cases()
    require(sha(ACT/"inputs.json")==read(ACT/"initial-checks/result.json")["input_sha256"],"same self-checked inputs")
    if name=="pilot":
        reg=design["pilot"]
        return reg["cpus"],reg["minutes"],"34G","evaluate.py",[name],expected_positions(manifest,name)
    gate=read(ACT/"pilot-budget.json")
    require(gate["continue_"] and gate["input"]==os.environ["T5_INPUT_SHA"],"actual pilot budget gate")
    if name=="analyse":
        require((ACT/"locked.json").exists(),"tracks locked before evaluation")
        accounted=status(records)
        require(all(completed(accounted.get(x["job"])) for x in records) and sum(x["name"].startswith("dev-") for x in records)==16,
                "all 16 development groups have terminal accounting")
        return 1,12,"6G","analyse.py",[],[]
    if name.startswith("advance-"):
        round_number=int(name.split("-")[1])
        tasks=fit_groups(round_number)
        paid={x["name"]:x for x in records if x["name"] in tasks}
        accounted=status(list(paid.values()))
        require(set(paid)==set(tasks) and all(completed(accounted.get(x["job"])) for x in paid.values()),"terminal FIT groups")
        return 1,3,"4G","advance.py",[str(round_number)],[]
    positions=expected_positions(manifest,name)
    cpus=(len(positions)+1)//2
    return cpus,gate["minutes_per_two_positions"],str(cpus+5)+"G","evaluate.py",[name],positions


def slurm_allocation(jid):
    returned=subprocess.check_output(["scontrol","show","job","-o",jid],text=True)
    fields=dict(p.split("=",1) for p in returned.split() if "=" in p)
    hours,minutes,seconds=map(int,fields["TimeLimit"].split(":"))
    require(seconds==0,"whole minute allocation")
    return int(fields["NumCPUs"]),hours*60+minutes


def submit(name,path):
    records=ledger()
    require(name not in {r["name"] for r in records},"preserve prior attempt")
    design,_,_=settings()
    cpus,minutes,memory,script,args,positions=resources(name,records)
    reserved=cpus*minutes*60
    require(len(records)+1<=design["max_jobs"] and sum(x["reserved"] for x in records)+reserved<=design["max_reserved_cpu_s"],
            "cumulative Slurm cap")
    conf={k:os.environ[k] for k in ("T5_SOURCE_SHA","T5_INPUT_SHA") if k in os.environ}
    conf.update(OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",PYTHONDONTWRITEBYTECODE="1")
    wrap="umask 077 && exec "+shlex.join(["env",*(k+"="+v for k,v in conf.items()),sys.executable,"-B",str(PK/script),*args])
    command=["sbatch","--hold","--no-requeue","--parsable","-p","cu","--nodes=1","--ntasks=1",
             "--cpus-per-task="+str(cpus),"--time="+str(minutes),"--mem="+memory,"--job-name=T5-"+name,
             "--output="+str(ACT/"logs/%j.out"),"--error="+str(ACT/"logs/%j.err"),"--wrap="+wrap]
    intent=path/(name+".intent")
    record=dict(name=name,source=sha(LOCK),input=os.environ.get("T5_INPUT_SHA"),positions=positions,
                cpus=cpus,minutes=minutes,mem=memory,reserved=reserved)
    write(intent,dict(record,command=command))
    jid=subprocess.check_output(command,text=True).strip().split(";")[0]
    write(path/(name+".json"),dict(record,job=jid))
    intent.unlink()
    require(slurm_allocation(jid)==(cpus,minutes),"held job resources")
    subprocess.run(["scontrol","release",jid],check=True)
    print(name,jid,cpus,minutes,flush=True)


def main():
    mode=sys.argv[1]
    if mode=="status":
        rows=ledger()
        returned=status(rows)
        print(len(rows),sum(q["reserved"] for q in rows),"reserved",dict(Counter(q["State"] for q in returned.values())))
        for r in rows:
            current=returned.get(r["job"],{})
            if mode=="status" and (len(sys.argv)>2 or not completed(current)):
                print(r["name"],r["job"],current.get("State"),current.get("ElapsedRaw"),current.get("ExitCode"))
    elif mode=="budget":
        budget()
    elif mode=="groups":
        round_number=int(sys.argv[2])
        print(" ".join(fit_groups(round_number)))
    elif mode=="submit":
        verify_sources(on_slurm=False)
        path=ACT/"registrations"
        path.mkdir(exist_ok=True)
        with (path/".lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            require(not any(path.glob("*.intent")),"reconcile previously requested allocation")
            for name in sys.argv[2:]:
                submit(name,path)
    else:
        raise ValueError(mode)


if __name__=="__main__":
    main()
