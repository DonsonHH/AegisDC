"""Guarded, exactly-once Slurm submission and budget gates on the login node."""
import argparse
import fcntl
import os
from pathlib import Path
import shlex
import subprocess

from operations import ACTIVITY_NAME, BASE, PYTHON, check_stage, file_sha, need, now, public_bundle, read, save


def shell_out(*args):
    return subprocess.check_output(args,text=True).strip()


def initialize(act, manifest):
    for n in ("submissions","batches","positions","logs","job-costs"):
        (act/n).mkdir(exist_ok=True)
    marker=act/"ready-to-qualify.json"
    if marker.is_file():
        need(read(marker)["manifest"]==manifest,"activity already bound to a different version")
        public_bundle(act)
        return
    bundle=public_bundle(act,create=True)
    save(marker,dict(manifest=manifest,public_bundle=bundle,utc=now()))


def register(act, manifest, group):
    name=group["name"]
    location=act/"submissions"
    out=location/(name+".json")
    with (location/".lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if out.exists():
            rec=read(out)
            need(rec["manifest"]==manifest,"existing submitted version")
            return rec["job"]
        need(not (location/(name+".intent.json")).exists(),"outstanding submission intent: reconcile before proceeding")
        if name not in ("analysis","center-timing"):
            need(not (act/"STOP.json").exists(),"scientific stop")
        if group["kind"]=="science" or name=="center-timing":
            qual=read(act/"qualification"/"acceptance.json")
            need(qual["pass"] and qual["implementation_manifest"]==manifest,"qualified source required")
            need(qual["witness_sha256"]==file_sha(act/"qualification"/"public-witness.json"),"witness identity")
        if group.get("batch",0)>1:
            need(read(act/"pilot-projection.json")["continue"] is True,"pilot did not release later positions")
        if name=="analysis":
            need((act/"science-settled.json").is_file(),"settle before readback")
        prior=[read(p) for p in location.glob("*.json") if not p.name.endswith((".intent.json",".error.json"))]
        expected=read(act/"registration.json")
        need(len(prior)+1<=63 and sum(r["reserved_cpu_s"] for r in prior)+group["seconds"]<=229800,"allocation ceiling")
        need(all(prev["name"] in expected["groups"] for prev in prior),"unregistered preceding job")
        jobname=group["slurm_name"]
        call=[str(PYTHON),"-I","-B",str(act/"source"/"runner.py"),"--activity",str(act),"--manifest",manifest,"job",name]
        args=["sbatch","--parsable","--partition=cu","--nodes=1","--ntasks=1","--cpus-per-task=1","--mem=4G",
              "--time="+str(group["seconds"]//60),"--job-name="+jobname,"--chdir="+str(act),"--export=NONE",
              "--output="+str(act/"logs"/"%j.out"),"--error="+str(act/"logs"/"%j.err"),
              "--wrap","umask 077; export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1; exec "+shlex.join(call)]
        intent=dict(name=name,slurm_name=jobname,manifest=manifest,reserved_cpu_s=group["seconds"],utc=now())
        save(location/(name+".intent.json"),intent)
        sub=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if sub.returncode:
            save(location/(name+".error.json"),dict(**intent,returncode=sub.returncode,stdout=sub.stdout,stderr=sub.stderr))
            raise RuntimeError("sbatch rejected "+name)
        job=sub.stdout.strip().split(";")[0]
        need(job.isdigit(),"scheduler returned ambiguous ID")
        save(out,dict(**intent,job=job))
        print(name,job,flush=True)
        return job


def scheduler_state(job):
    raw=shell_out("sacct","-n","-P","-j",job,"--format=JobIDRaw,State,ExitCode")
    for line in raw.splitlines():
        parts=line.split("|")
        if parts[0]==job:
            return parts[1].split()[0].rstrip("+"),parts[2]
    return None,None


def project(act,reg):
    pilots=[g for g in reg["groups"].values() if g.get("batch")==1]
    need(len(pilots)==10,"all first batches")
    if (act/"pilot-projection.json").exists():
        print(read(act/"pilot-projection.json")); return
    by_role={};projected=sum(g["seconds"] for g in reg["groups"].values() if g["kind"]!="science")
    for g in pilots:
        name=g["name"]; sub=read(act/"submissions"/(name+".json"))
        state,code=scheduler_state(sub["job"])
        need(state=="COMPLETED" and code=="0:0","pilot not successfully terminal: "+name)
        receipt=read(act/"batches"/name/"terminal.json")
        need(receipt["complete"] and receipt["job"]==sub["job"] and len(receipt["returns"])==12,"full pilot")
        max_wall=max(v["wall_s"] for v in receipt["returns"])
        seconds=12*1.25*max_wall+receipt["overhead_s"]
        need(abs(seconds-receipt["projected_next_batch_s"])<1e-6,"pilot projection arithmetic")
        by_role[g["role"]]=dict(job=sub["job"],max_position_s=max_wall,overhead_s=receipt["overhead_s"],
                         next_batch_projection_s=seconds,job_limit_s=g["seconds"],within_limit=seconds<=g["seconds"])
        projected+=g["seconds"]+5*seconds
    budget=sum(g["seconds"] for g in reg["groups"].values())
    gate=all(v["within_limit"] for v in by_role.values()) and projected<=229800 and budget==229800 and len(reg["groups"])==63 and not (act/"STOP.json").exists()
    record={"continue":gate,"roles":by_role,"projected_single_cpu_seconds_including_support":projected,
            "all_planned_reservation_s":budget,"registered_jobs":len(reg["groups"]),"pilot_positions":120,"utc":now()}
    save(act/"pilot-projection.json",record)
    if not gate:
        from runner import stop
        stop(act,"pilot_projection_stop","pilot_gate",None)
    print(record)


def settle(act,reg):
    if (act/"science-settled.json").exists():return
    terminal={"COMPLETED","FAILED","TIMEOUT","CANCELLED","NODE_FAIL","OUT_OF_MEMORY","BOOT_FAIL","DEADLINE","PREEMPTED","REVOKED"}
    stopped=(act/"STOP.json").exists()
    summaries={}
    for g in reg["groups"].values():
        if g["kind"]!="science":continue
        sub=act/"submissions"/(g["name"]+".json")
        if not sub.exists():
            need(stopped,"unsubmitted rows and no recorded stop")
            continue
        j=read(sub)["job"];state,code=scheduler_state(j)
        need(state in terminal,"job not yet terminal: "+j)
        receipt=act/"batches"/g["name"]/"terminal.json"
        if not receipt.exists() or not read(receipt)["complete"] or state!="COMPLETED" or code!="0:0":
            from runner import stop
            stop(act,"incomplete_or_failed_allocation",g["name"],j);stopped=True
        summaries[g["name"]]=dict(job=j,state=state,exit_code=code)
    timing=act/"submissions"/"center-timing.json"
    if timing.exists():
        state,_=scheduler_state(read(timing)["job"])
        need(state in terminal,"timing not settled")
    save(act/"science-settled.json",dict(utc=now(),stopped=stopped,allocations=summaries))


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--manifest",required=True)
    a.add_argument("action",choices=("init","qualification","center-timing","pilot","project","remaining","settle","analysis","status"))
    r=a.parse_args()
    act,spec=check_stage(BASE/ACTIVITY_NAME,r.manifest)
    reg=read(act/"registration.json");groups=reg["groups"]
    if r.action=="init":initialize(act,r.manifest);return
    if r.action=="status":
        for path in sorted((act/"submissions").glob("*.json")):
            if not path.name.endswith((".intent.json",".error.json")):
                j=read(path);print(j["name"],j["job"],*scheduler_state(j["job"]))
        print("native entries",len(list((act/"positions").glob("*/*/native-entry.json"))),
              "scores",len(list((act/"positions").glob("*/*/score.json"))),"stop",(act/"STOP.json").exists())
        return
    if r.action=="project":project(act,reg);return
    if r.action=="settle":settle(act,reg);return
    initial=read(act/"ready-to-qualify.json")["manifest"]
    if initial!=r.manifest:
        approved=read(act/"qualification"/"acceptance.json")
        need(approved["pass"] and approved["initial_implementation_manifest"]==initial and
             approved["implementation_manifest"]==r.manifest,"repaired implementation is not qualified")
    if r.action in ("qualification","center-timing","analysis"):
        register(act,r.manifest,groups[r.action]);return
    for label in reg["order"]:
        g=groups[label]
        if g["kind"]=="science" and ((r.action=="pilot" and g["batch"]==1) or (r.action=="remaining" and g["batch"]>1)):
            register(act,r.manifest,g)

if __name__=="__main__":
    main()
