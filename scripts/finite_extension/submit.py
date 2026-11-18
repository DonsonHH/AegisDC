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
    rows=[dict(slot=s,status="NOT_SUBMITTED",score_available=False) for s in m["order"]]
    durable(out/"denominator.json",rows)
    for index,slot in enumerate(m["order"]):
        directory=out/slot
        entry=[str(HERE/"slot.slurm"),str(ROOT),str(manifest_path.resolve()),digest,str(index),str(directory),approval,approval_sha]
        command=["sbatch","--parsable","--no-requeue","--partition=cu","--nodes=1","--ntasks=1","--cpus-per-task=1","--mem=1G",
                 "--time=00:"+("01:00" if m["purpose"]==REAL else "02:00"),"--job-name=ext-"+slot,
                 "--output="+str(out/(slot+"-%j.out")),"--error="+str(out/(slot+"-%j.err")), *entry]
        allowed=False;job_id=None
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
            exit_record=read(directory/"exit.json")
            bound=(exit_record.get("slot")==slot and exit_record.get("manifest_sha256")==digest
                   and exit_record.get("job_id")==job_id and exit_record.get("purpose")==m["purpose"])
            allowed=bool(bound and scheduler["state"]=="COMPLETED" and scheduler["exit_code"]=="0:0"
                         and exit_record["status"] in ("PASS","NONCOMPLIANT") and not exit_record["technical_stop"])
            rows[index]=dict(slot=slot,status=exit_record.get("status") if allowed else "TECHNICAL_STOP",
                     scheduler=scheduler,exit=exit_record,score_available=(directory/"summary.json").is_file())
            if rows[index]["score_available"]:
                rows[index]["summary"]=read(directory/"summary.json")
            if allowed:
                for key,filename in [("raw_sha256","raw.json"),("summary_sha256","summary.json")]:
                    need(file_sha(directory/filename)==exit_record["files"][key],"ARCHIVE_IDENTITY")
        except Exception as error:
            allowed=False
            rows[index].update(status="UNRESOLVED_OR_TECHNICAL_STOP",error=str(error),job_id=job_id,accounting=recovery(directory))
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
