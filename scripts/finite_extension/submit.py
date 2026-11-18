"""Submit the next slot only after the preceding Slurm job AND archive succeed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import BASE, FIXTURE, HERE, REAL, ROOT, durable, file_sha, manifest_data, mkdir, need, read, recovery

TERMINAL={"COMPLETED","FAILED","TIMEOUT","DEADLINE","NODE_FAIL","PREEMPTED","OUT_OF_MEMORY","BOOT_FAIL","CANCELLED","REVOKED","SPECIAL_EXIT"}


def placeholder(slot,status):
    return dict(slot=slot,status=status,score_available=False,eligible=False,
                arms={a:None for a in ("I","D","P")},finite_propositions=None)


def read_same_job(directory,slot,digest,job_id,purpose):
    attempts=[]
    for attempt in range(3):
        try:
            info=read(directory/"exit.json")
            need(info.get("slot")==slot and info.get("manifest_sha256")==digest and info.get("job_id")==job_id
                 and info.get("purpose")==purpose,"SLOT_OR_JOB_IDENTITY")
            status=info["status"]
            summary=read(directory/"summary.json") if status in ("PASS","NONCOMPLIANT") or (directory/"summary.json").is_file() else None
            if status in ("PASS","NONCOMPLIANT"):
                for key,filename in (("raw_sha256","raw.json"),("summary_sha256","summary.json")):
                    need(file_sha(directory/filename)==info["files"][key],"ARCHIVE_IDENTITY")
            return info,summary,attempts
        except (OSError,ValueError,KeyError,TypeError) as error:
            attempts.append(str(error))
            if attempt<2:time.sleep(1)
    raise RuntimeError("SAME_JOB_EVIDENCE_UNRESOLVED: "+str(attempts))


def accounting(job_id):
    # An unavailable observation never submits another job.
    for _ in range(150):
        query=subprocess.run(["sacct","-n","-X","-P","-j",job_id,"-o","JobID,State,ExitCode,Elapsed,AllocCPUS,ReqMem,AllocTRES"],capture_output=True,text=True)
        for line in query.stdout.splitlines():
            values=line.strip().split("|")
            if query.returncode==0 and len(values)>=7 and values[0]==job_id and values[1].split()[0] in TERMINAL:
                return dict(job=job_id,state=values[1],exit_code=values[2],elapsed=values[3],
                            cpus=values[4],memory=values[5],tres=values[6])
        time.sleep(2)
    raise RuntimeError("Scheduler state still unresolved; inspect the SAME job")


def dispatch(manifest_path, digest, approval, approval_sha):
    m,_,_=manifest_data(manifest_path,digest,approval,approval_sha)
    need(m["route"]=="serial","SERIAL_ROUTE_REQUIRED")
    out=Path(m["output_root"]);mkdir(out)
    start=dict(manifest_sha256=digest,source_revision=m["source_revision"],purpose=m["purpose"],
               allocation=m["budget"],order=m["order"],attempt=out.name)
    durable(out/"manifest.json",m);durable(out/"started.json",start)
    rows=[placeholder(s,"NOT_SUBMITTED") for s in m["order"]]
    durable(out/"denominator.json",rows)
    for index,slot in enumerate(m["order"]):
        directory=out/slot
        entry=[str(HERE/"slot.slurm"),str(ROOT),str(manifest_path.resolve()),digest,str(index),str(directory),approval,approval_sha]
        command=["sbatch","--parsable","--no-requeue","--partition=cu","--nodes=1","--ntasks=1","--cpus-per-task=1","--mem=1G",
                 "--time=00:"+("01:00" if m["purpose"]==REAL else "02:00"),"--job-name=ext-"+slot,
                 "--output="+str(out/(slot+"-%j.out")),"--error="+str(out/(slot+"-%j.err")), *entry]
        allowed=False;job_id=None;scheduler=None
        try:
            durable(out/("submit-"+slot+".json"),dict(index=index,manifest_sha256=digest,command=command))
            rows[index].update(status="SUBMISSION_UNRESOLVED")
            response=subprocess.run(command,capture_output=True,text=True,check=True)
            job_id=response.stdout.strip().split(";")[0]
            need(re.fullmatch(r"[0-9]+",job_id),"UNRESOLVED_SUBMISSION_ID")
            durable(out/("job-"+slot+".json"),dict(job_id=job_id,raw_stdout=response.stdout,raw_stderr=response.stderr))
            scheduler=accounting(job_id)
            # Keep scheduler evidence even when the per-slot filesystem is incomplete.
            durable(out/("observed-"+slot+".json"),scheduler)
            exit_record,summary,observations=read_same_job(directory,slot,digest,job_id,m["purpose"])
            allowed=bool(scheduler["state"]=="COMPLETED" and scheduler["exit_code"]=="0:0"
                         and exit_record["status"] in ("PASS","NONCOMPLIANT") and not exit_record["technical_stop"])
            rows[index]=placeholder(slot,exit_record.get("status") if allowed else "TECHNICAL_STOP")
            rows[index].update(scheduler=scheduler,exit=exit_record,observation_errors=observations)
            if summary is not None:rows[index]["worker_summary_file"]=str(directory/"summary.json")
            if allowed:
                rows[index].update(score_available=True,eligible=summary["valid_comparison"],arms=summary["arms"],
                        finite_propositions=summary["finite_propositions"] if summary["valid_comparison"] else None,
                        delta_L_D_minus_I=summary["delta_L_D_minus_I"],I_minus_D_costs=summary["delta_costs_I_minus_D"],
                        P_background=summary["P_background"],assigned_stage_observed=summary["assigned_stage_observed"])
        except Exception as error:
            allowed=False
            status="TECHNICAL_STOP_EVIDENCE_INCOMPLETE" if scheduler and (scheduler["state"]!="COMPLETED" or scheduler["exit_code"]!="0:0") else "EVIDENCE_UNRESOLVED"
            rows[index].update(status=status,error=str(error),job_id=job_id,
                               scheduler=scheduler,accounting=recovery(directory),eligible=False,finite_propositions=None)
        durable(out/("scheduler-"+slot+".json"),dict(slot=slot,index=index,manifest_sha256=digest,job_id=job_id,
                    permit_next=allowed,row=rows[index]))
        durable(out/f"progress-{index+1:02}.json",rows)
        if not allowed:break
    complete=all(r["status"] in ("PASS","NONCOMPLIANT") for r in rows)
    durable(out/"terminal.json",dict(status="COMPLETE" if complete else "STOPPED",purpose=m["purpose"],
        manifest_sha256=digest,rows=rows,new_retries=0))
    return 0 if complete else 1


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("manifest",type=Path);p.add_argument("digest")
    p.add_argument("--approval",default="-");p.add_argument("--approval-sha",default="-")
    args=p.parse_args()
    raise SystemExit(dispatch(args.manifest,args.digest,args.approval,args.approval_sha))
