"""Reserve Slurm resources for the fixed experiment and release only registered batches."""
from collections import Counter
import fcntl
import os
import shlex
import subprocess
import sys

from context_v2 import ACT, LOCK, PK, config, need, panel, put, read, sha, verify_sources
from positions import dev_groups, forecast_groups, pilot, projection


def ledger():
    return sorted((read(q) for q in (ACT/"registrations").glob("*.json")),key=lambda r:int(r["job"]))


def accounting(records, include_steps=False):
    fields=("JobID","JobName%36","State","ExitCode","ElapsedRaw","AllocCPUS","TimelimitRaw","TotalCPU","Start","End","NodeList")
    if not records:
        return {}
    ids={r["job"] for r in records}
    command=["sacct","-n","-P","-j",",".join(sorted(ids)),"-o",",".join(fields)]
    if not include_steps:
        command.insert(1,"-X")
    output=subprocess.check_output(command,text=True)
    return {items[0]:dict(zip(fields,items,strict=True)) for row in output.splitlines()
            if (items:=row.split("|"))[0] in ids}


def all_terminal(records):
    if not records:
        return
    current=accounting(records)
    pending={"PENDING","RUNNING","CONFIGURING","COMPLETING","REQUEUE_HOLD","REQUEUED","RESIZING","SIGNALING","SUSPENDED"}
    need(len(current)==len(records) and all(row["End"] and row["End"]!="Unknown" and row["State"].split()[0].rstrip("+") not in pending for row in current.values()),
         "all registered jobs have terminal accounting")


def group_records(records, names):
    by_name={r["name"]:r for r in records}
    need(set(names)<=by_name.keys(),"all registered scientific batches")
    return [by_name[n] for n in names]


def measure_pilot():
    records=ledger()
    registered=group_records(records,["pilot"])
    result=accounting(registered)[registered[0]["job"]]
    evidence=read(ACT/"batches/pilot/terminal.json")
    need(result["State"]=="COMPLETED" and result["ExitCode"]=="0:0" and
         evidence["job"]==registered[0]["job"] and len(evidence["positions"])==24
         and all(x["scored"] and x["position_entered"] and x["exit_code"]==0 for x in evidence["positions"]),
         "24 complete pilot scores")
    estimate=projection(evidence["wall_s"],records)
    estimate.update(complete_wall_s=evidence["wall_s"],input_sha256=os.environ["T5V2_INPUTS"],job=evidence["job"])
    put(ACT/"pilot-budget.json",estimate)
    print(estimate,flush=True)


def resources(name,records):
    design, _, u=config()
    if name=="prepare":
        need(not records,"one development authoring allocation")
        return "prepare_v2.py",[],[],1,design["offload"]["prepare_minutes"],"3G"
    manifest=panel()
    witness=read(ACT/"public-checks/result.json")
    need(witness["inputs"]==os.environ["T5V2_INPUTS"] and witness["native_entries"]==0,"same self-checked panel")
    if name=="pilot":
        selected=pilot(manifest)
        return "facility_v2.py",[name],selected,design["pilot"]["cpus"],design["pilot"]["minutes"],"34G"
    gate=read(ACT/"pilot-budget.json")
    need(gate["proceed"] and gate["input_sha256"]==os.environ["T5V2_INPUTS"],"measured projection within both limits")
    if name.startswith("update-"):
        epoch=int(name.split("-")[1])
        need(1<=epoch<=u["rounds"],"frozen round count")
        all_terminal(group_records(records,forecast_groups(manifest,epoch)))
        return "rounds_v2.py",[str(epoch)],[],1,design["offload"]["per_update_minutes"],"4G"
    if name=="analyse":
        need((ACT/"locked.json").is_file(),"signed lock before DEV")
        all_terminal(group_records(records,dev_groups(manifest)))
        return "analyse_v2.py",[],[],1,design["offload"]["final_minutes"],"7G"
    if name.startswith("fit-"):
        selected=forecast_groups(manifest,int(name.split("-")[1]))[name]
    else:
        selected=dev_groups(manifest)[name]
    n=(len(selected)+1)//2
    return "facility_v2.py",[name],selected,n,gate["minutes"],str(n+5)+"G"


def submit(path,name):
    records=ledger()
    design, _, _=config()
    need(name not in {r["name"] for r in records},"retain previous job and reconcile before retry")
    script,args,positions,cpus,minutes,memory=resources(name,records)
    reserved=cpus*minutes*60
    need(len(records)+1<=design["max_jobs"] and sum(r["reserved_cpu_s"] for r in records)+reserved<=design["max_reserved_cpu_s"],
         "cumulative budget")
    env={name:os.environ[name] for name in ("T5V2_SOURCE","T5V2_INPUTS") if name in os.environ}
    env.update(OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",PYTHONDONTWRITEBYTECODE="1")
    wrap="umask 077 && exec "+shlex.join(["env",*(k+"="+v for k,v in env.items()),sys.executable,"-B",str(PK/script),*args])
    command=["sbatch","--hold","--no-requeue","--parsable","-p","cu","--nodes=1","--ntasks=1","--cpus-per-task="+str(cpus),
        "--mem="+memory,"--time="+str(minutes),"--job-name=T5v2-"+name,"--output="+str(ACT/"logs/%j.out"),
        "--error="+str(ACT/"logs/%j.err"),"--wrap="+wrap]
    row=dict(name=name,source=sha(LOCK),input=os.environ.get("T5V2_INPUTS"),cpus=cpus,minutes=minutes,memory=memory,
             reserved_cpu_s=reserved,positions=positions)
    intent=path/(name+".intent")
    put(intent,dict(row,command=command))
    jid=subprocess.check_output(command,text=True).strip().split(";")[0]
    put(path/(name+".json"),dict(row,job=jid))
    intent.unlink()
    detail=subprocess.check_output(["scontrol","show","job","-o",jid],text=True)
    parsed=dict(x.split("=",1) for x in detail.split() if "=" in x)
    h,m,s=map(int,parsed["TimeLimit"].split(":"))
    need(int(parsed["NumCPUs"])==cpus and h*60+m==minutes and s==0,"held Slurm reservation")
    subprocess.run(["scontrol","release",jid],check=True)
    print(name,jid,cpus,minutes,len(positions),flush=True)


def main(mode,args):
    if mode=="budget":
        measure_pilot()
    elif mode=="groups":
        manifest=panel()
        groups=dev_groups(manifest) if args[0]=="dev" else forecast_groups(manifest,int(args[0]))
        print(" ".join(groups))
    elif mode=="status":
        records=ledger()
        result=accounting(records)
        print(len(records),"jobs",sum(r["reserved_cpu_s"] for r in records),"reserved",dict(Counter(q["State"] for q in result.values())))
        for r in records:
            s=result.get(r["job"],{})
            print(r["name"],r["job"],s.get("State"),s.get("ElapsedRaw"),s.get("ExitCode"))
    elif mode=="submit":
        verify_sources(on_compute=False)
        path=ACT/"registrations"
        path.mkdir(exist_ok=True)
        with (path/".lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            need(not any(path.glob("*.intent")),"reconcile previous Slurm request")
            for name in args:
                submit(path,name)
    else:
        raise ValueError(mode)


if __name__=="__main__":
    main(sys.argv[1],sys.argv[2:])
