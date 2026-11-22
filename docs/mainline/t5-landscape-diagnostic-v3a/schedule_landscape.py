"""Serialize Slurm admissions, preserve attempts and apply the published pilot projection."""
from collections import Counter
import fcntl
import math
import os
import shlex
import subprocess
import sys

from landscape import ACT, LOCK, PK, batches, check, check_source, config, manifest, read, sha, write


def ledger():
    return sorted((read(f) for f in (ACT/"registrations").glob("*.json")),key=lambda r:int(r["job"]))


def statuses(rows):
    if not rows:return {}
    ids={r["job"] for r in rows}
    result=subprocess.check_output(["sacct","-X","-n","-P","-j",",".join(sorted(ids)),"-o","JobID,State,ExitCode,ElapsedRaw,End"],text=True)
    return {q[0]:q for line in result.splitlines() if (q:=line.split("|"))[0] in ids}


def compute_budget():
    m=manifest();cfg=config();all_jobs=batches(m,cfg)
    records=ledger();rows=statuses(records)
    logs={r["name"]:r for r in records}
    check(set(logs)=={"prepare",*(name for name in all_jobs if name.startswith("pilot-"))},
          "freeze budget immediately after all six pilots")
    times={};complete=True
    for index,fam in enumerate(cfg["families"],1):
        name=f"pilot-{index:02}";reg=logs[name];account=rows.get(reg["job"])
        check(account is not None and account[-1] not in ("","Unknown","None") and account[1] not in ("RUNNING","PENDING","COMPLETING"),
              "pilot not terminal")
        evidence=ACT/"batches"/name/"terminal.json"
        if not evidence.exists():
            complete=False;continue
        output=read(evidence)
        check(output["job"]==reg["job"] and len(output["positions"])==len(reg["slots"]),"pilot identity")
        complete=complete and account[1]=="COMPLETED" and account[2]=="0:0" and all(x["entered"] and x["scored"] and x["exit_code"]==0 for x in output["positions"])
        times[fam]=output["wall_s"]
    minutes={};projection=None
    rules=cfg["scheduler"];remaining={k:v for k,v in all_jobs.items() if not k.startswith("pilot-")}
    if complete:
        for name,lanes in remaining.items():
            longest=max(math.fsum(times[m["conditions"][key]["family"]] for _,key in lane) for lane in lanes)
            minutes[name]=math.ceil((rules["margin"]*longest+rules["group_overhead_s"])/60)
        projection=sum(r["reserved_s"] for r in records)+sum(60*minutes[name]*len(lanes) for name,lanes in remaining.items())+60*rules["analysis_minutes"]
    jobs=len(records)+len(remaining)+1
    passed=complete and projection<=rules["max_reserved_s"] and jobs<=rules["max_jobs"]
    summary=dict(panel=os.environ["V3A_PANEL"],complete_pilot=complete,wall_s_by_family=times,minutes=minutes,
        pilot_positions=36,projected_jobs=jobs,projected_reserved_s=projection,reservations_to_date=sum(r["reserved_s"] for r in records),
        proceed=passed,full_policy_and_oracle_positions=2124,additional_P_witnesses=len(m["identity_only_keys"]))
    write(ACT/"pilot-budget.json",summary)
    print("pilot",times,"job count",jobs,"CPU seconds",projection,"proceed",passed,flush=True)


def choose(name,records):
    cfg=config();sched=cfg["scheduler"]
    if name=="prepare":
        check(not records,"one initial allocation")
        return "prepare.py",[],[],1,sched["prep_minutes"],"4G"
    m=manifest()
    check(m["selfcheck"]["branch_boundaries"] and m["native_starts"]==0,"zero-facility selfcheck")
    allocated=batches(m,cfg)
    if name.startswith("pilot-"):
        return "score_positions.py",[name],allocated[name],cfg["pilot"]["cpus"],cfg["pilot"]["minutes"],"9G"
    budget=read(ACT/"pilot-budget.json")
    if name=="analyse":
        byid=statuses(records)
        check(all(r["job"] in byid and byid[r["job"]][-1] not in ("","Unknown","None") for r in records),"all registrations terminal")
        if budget["proceed"]:
            need=set(allocated);seen={r["name"] for r in records}
            check(need<=seen,"all registered scoring batches")
        return "analyse_landscape.py",[],[],1,sched["analysis_minutes"],"5G"
    check(budget["proceed"] and budget["panel"]==os.environ["V3A_PANEL"],"pilot budget stop")
    lanes=allocated[name]
    return "score_positions.py",[name],lanes,len(lanes),budget["minutes"][name],str(3+len(lanes))+"G"


def submit_one(name,path):
    records=ledger()
    check(name not in {r["name"] for r in records},"job already registered")
    cfg=config()
    script,args,lanes,cpus,minutes,memory=choose(name,records)
    reserved=cpus*minutes*60
    report=0 if name=="analyse" else cfg["scheduler"]["analysis_minutes"]*60
    check(len(records)+1+bool(report)<=cfg["scheduler"]["max_jobs"] and
          sum(r["reserved_s"] for r in records)+reserved+report<=cfg["scheduler"]["max_reserved_s"],"execution budget")
    env={k:os.environ[k] for k in ("V3A_SOURCE","V3A_PANEL") if k in os.environ}
    env.update(OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1",PYTHONDONTWRITEBYTECODE="1")
    wrap="umask 077 && exec "+shlex.join(["env",*(k+"="+v for k,v in env.items()),sys.executable,"-B",str(PK/script),*args])
    command=["sbatch","--hold","--no-requeue","--parsable","-p","cu","--nodes=1","--ntasks=1","--cpus-per-task="+str(cpus),
        "--time="+str(minutes),"--mem="+memory,"--job-name=V3a-"+name,"--output="+str(ACT/"logs/%j.out"),
        "--error="+str(ACT/"logs/%j.err"),"--wrap="+wrap]
    reg=dict(name=name,slots=[s for lane in lanes for s in lane],cpus=cpus,minutes=minutes,reserved_s=reserved,memory=memory,
             source=sha(LOCK),panel=os.environ.get("V3A_PANEL"))
    intent=path/(name+".intent")
    write(intent,dict(reg,command=command))
    jid=subprocess.check_output(command,text=True).strip().split(";")[0]
    write(path/(name+".json"),dict(reg,job=jid))
    intent.unlink()
    info=subprocess.check_output(["scontrol","show","job","-o",jid],text=True)
    fields=dict(s.split("=",1) for s in info.split() if "=" in s)
    h,m,s=map(int,fields["TimeLimit"].split(":"))
    check(int(fields["NumCPUs"])==cpus and h*60+m==minutes and s==0,"actual Slurm resources")
    subprocess.run(["scontrol","release",jid],check=True)
    print(name,jid,cpus,minutes,len(reg["slots"]),flush=True)


def main():
    mode=sys.argv[1]
    if mode=="submit":
        check_source(compute=False)
        path=ACT/"registrations";path.mkdir(exist_ok=True)
        with (path/".lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            check(not any(path.glob("*.intent")),"unreconciled Slurm submission")
            for name in sys.argv[2:]:
                submit_one(name,path)
    elif mode=="budget":
        compute_budget()
    elif mode=="groups":
        print(" ".join(k for k in batches(manifest(),config()) if not k.startswith("pilot-")))
    elif mode=="status":
        records=ledger();state=statuses(records)
        print(len(records),"jobs",sum(r["reserved_s"] for r in records),"reserved CPU seconds",dict(Counter(q[1] for q in state.values())))
        for r in records:
            q=state.get(r["job"])
            if len(sys.argv)>2 or q is None or q[1]!="COMPLETED":
                print(r["name"],r["job"],q[1:] if q else "NO_ACCOUNTING_YET")
    else:
        raise ValueError(mode)


if __name__=="__main__":
    main()
