"""One-time Slurm reservations for the shared parent, first round, and all three remaining rounds."""

import argparse
import csv
from decimal import Decimal
import hashlib
import io
import os
from pathlib import Path
import subprocess

from prepare_runtime import PK, STUDY, compact, read, require, save
from study import FIT_ROOT, score_gate


def seconds(token):
    days,sep,rest=token.partition("-")
    if not sep:days,rest="0",token
    total=Decimal(0)
    for field in rest.split(":"):total=60*total+Decimal(field)
    return Decimal(days)*86400+total


def accounting(name):
    plan=read(STUDY/"jobs"/(name+".json"));jid=plan["job"]
    text=subprocess.check_output(["sacct","-P","-j",jid,
          "--format=JobID,State,ExitCode,ElapsedRaw,TimelimitRaw,AllocCPUS,TotalCPU,ReqMem,MaxRSS"],text=True)
    rows={v["JobID"]:v for v in csv.DictReader(io.StringIO(text),delimiter="|")}
    job,batch=rows[jid],rows[jid+".batch"]
    require(job["State"]==batch["State"]=="COMPLETED" and job["ExitCode"]==batch["ExitCode"]=="0:0" and
            job["TotalCPU"]==batch["TotalCPU"] and int(job["TimelimitRaw"])==plan["minutes"] and
            int(job["AllocCPUS"])==plan["cpus"] and (STUDY/"jobs"/(name+"-complete.json")).is_file(),"completed reconciled allocation")
    cpu=seconds(job["TotalCPU"])
    require(0<cpu<=Decimal(plan["reserved_cpu_s"]),"measured positive CPU within reservation")
    f=STUDY/"jobs"/(name+"-accounting.psv")
    if not f.exists():
        with f.open("x") as stream:stream.write(text)
    return job,cpu


def admit(labels,cpus,minutes,mem,revision):
    jobs=STUDY/"jobs";jobs.mkdir(exist_ok=True)
    require(not (STUDY/"STOP").exists(),"study stopped")
    existing=[]
    for name in ["parent","parent-a2","pilot",*(f"r{r}{a}" for r in (2,3,4) for a in ("O","R"))]:
        p=jobs/(name+".json")
        if p.exists():existing.append(read(p))
    total=240+sum(p["reserved_cpu_s"] for p in existing)+len(labels)*cpus*minutes*60
    require(len(existing)+len(labels)+1<=10 and total<=285900,"study allocation ceiling")
    submitted=[]
    try:
        for label in labels:
            record={"name":label,"release":revision,"batch_root":FIT_ROOT,"cpus":cpus,"mem":mem,
                    "minutes":minutes,"reserved_cpu_s":cpus*minutes*60,
                    "positions":48 if label=="parent-a2" else 384 if label=="pilot" else 192}
            save(jobs/(label+".intent"),record)
            options=["sbatch","--parsable","--hold","--no-requeue","--kill-on-invalid-dep=yes","-p","cu","--nodes=1",
                     "--ntasks=1","--cpus-per-task="+str(cpus),"--time="+str(minutes),"--mem="+mem,"--export=NONE",
                     "--job-name=t8-fit-"+label,"--chdir="+str(STUDY),"--output="+str(jobs/"%j.out"),
                     "--error="+str(jobs/"%j.err")]
            if submitted:options.append("--dependency=afterok:"+submitted[-1])
            jid=subprocess.check_output([*options,str(PK/"study.sbatch"),label,revision],cwd=STUDY,text=True).strip().split(";")[0]
            require(jid.isdecimal(),"unbound Slurm allocation")
            submitted.append(jid);save(jobs/(label+".json"),dict(record,job=jid))
        subprocess.run(["scontrol","release",",".join(submitted)],check=True)
    except Exception:
        # These allocations belong to this grouped submission. Never replace a partly admitted wave.
        if submitted:subprocess.run(["scancel",*submitted],check=False)
        raise
    return submitted


def main(stage):
    score_gate()
    plan=read(STUDY/"execution-recovery.json");rev=read(PK/"export.json")["revision"]
    require(plan["release_revision"]==rev and read(STUDY/"published-envelope-recovery.json")["fingerprint"]==
            hashlib.sha256(compact(plan)).hexdigest(),"published pre-feedback envelope")
    if stage=="parent-a2":
        require(read(STUDY/"jobs/parent.json")["job"]=="135577" and
                hashlib.sha256((STUDY/"jobs/135577.err").read_bytes()).hexdigest()==
                "5ae20de57f6a9cfc0fa1af33f59f3a2f9644ef5d10c6575a9ce8de28cc2539dd" and
                all(not (STUDY/n).exists() for n in ("jobs/parent-entry.json","positions","baseline.json","evidence")),
                "single authorized pre-entry recovery")
        ids=admit(["parent-a2"],24,6,"48G",rev)
    elif stage=="pilot":
        accounting("parent-a2")
        base=read(STUDY/"baseline.json")["slot"]
        require(base["status"]=="COMPLETE" and base["started_fit_n"]==base["complete_fit_n"]==48 and
                base["fit_return"]["hard_violations"]==0,"complete safe shared parent")
        ids=admit(["pilot"],48,24,"96G",rev)
    else:
        pil,cpu=accounting("pilot"); records=[read(STUDY/"evidence/rounds"/f"{a}-1.json") for a in ("O","R")]
        require(all(r["status"]=="CLOSED" and r["accounting"]["complete_positions"]==192 and
                    all(s["fit_return"]["hard_violations"]==0 for s in r["slots"]) for r in records),"complete pilot")
        require([s["policy"]["id"] for s in records[0]["slots"]]==[s["policy"]["id"] for s in records[1]["slots"]],
                "identical paid first proposals")
        spent=240+sum(read(STUDY/"jobs"/(n+".json"))["reserved_cpu_s"] for n in ("parent","parent-a2","pilot"))
        cpus=48;ceiling=min(6*cpu,Decimal(6*34620),Decimal(285900-spent))
        minutes=int(ceiling//(6*cpus*60))
        projection={"pilot_job":pil["JobID"],"pilot_positions":384,"pilot_total_cpu_s":str(cpu),
            "remaining_positions":1152,"jobs":6,"extrapolated_cpu_s":str(3*cpu),"twice_extrapolated_cpu_s":str(6*cpu),
            "registered_and_measured_ceiling_s":str(ceiling),"minutes_per_job":minutes,
            "remaining_global_reservation_s":285900-spent,"planned_reserved_cpu_s":6*cpus*60*minutes}
        save(STUDY/"jobs/batch-projection.json",projection)
        require(minutes>=1 and minutes*120>=int(pil["ElapsedRaw"]),"batch cannot fit observed time within twice-extrapolated budget")
        ids=admit([f"r{r}{a}" for r in (2,3,4) for a in ("O","R")],cpus,minutes,"96G",rev)
    print("SUBMITTED",stage,*ids,flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("parent-a2","pilot","batch"))
    os.umask(0o077)
    main(parser.parse_args().stage)
