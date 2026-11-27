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
        if group["kind"]=="science":
            states=scheduler_states([p["job"] for p in prior if expected["groups"][p["name"]]["kind"]=="science"])
            failures={"NODE_FAIL","OUT_OF_MEMORY","BOOT_FAIL","CANCELLED","FAILED","TIMEOUT","PREEMPTED","DEADLINE","REVOKED"}
            for p in prior:
                state,code=states.get(p["job"],(None,None))
                if state in failures or state=="COMPLETED" and code!="0:0":
                    from runner import stop
                    stop(act,"scheduler_"+state,p["name"],p["job"])
                    raise ValueError("Prior scientific allocation failed: "+p["job"])
                if state=="COMPLETED" and expected["groups"][p["name"]].get("batch")==1:
                    terminal=act/"batches"/p["name"]/"terminal.json"
                    if terminal.is_file():
                        first=read(terminal)
                        if not first["complete"] or first["projected_next_batch_s"]>expected["groups"][p["name"]]["seconds"]:
                            from runner import stop
                            stop(act,"pilot_projection_stop",p["name"],p["job"])
                            raise ValueError("First batch cannot release another submission: "+p["name"])
            if group["batch"]>1:
                need(predecessor_ready(act,group,states),"same-arm previous batch is not complete")
            need(not (act/"STOP.json").exists(),"scientific stop before scheduler call")
        need(len(prior)+1<=63 and sum(r["reserved_cpu_s"] for r in prior)+group["seconds"]<=229800,"allocation ceiling")
        need(all(prev["name"] in expected["groups"] for prev in prior),"unregistered preceding job")
        jobname=group["slurm_name"]
        call=[str(PYTHON),"-I","-B",str(act/"source"/"runner.py"),"--activity",str(act),"--manifest",manifest,"job",name]
        args=["sbatch","--parsable","--no-requeue","--partition=cu","--nodes=1","--ntasks=1","--cpus-per-task=1","--mem=4G",
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


def scheduler_states(jobs):
    if not jobs:
        return {}
    raw=shell_out("sacct","-n","-P","-j",",".join(jobs),"--format=JobIDRaw,State,ExitCode")
    states={}
    for line in raw.splitlines():
        parts=line.split("|")
        if len(parts)>=3 and parts[0] in jobs and parts[1].strip():
            states[parts[0]]=(parts[1].split()[0].rstrip("+"),parts[2])
    return states

def scheduler_state(job):
    return scheduler_states([job]).get(job,(None,None))

def predecessor_ready(activity,group,states=None):
    previous=group["role"]+"-b"+str(group["batch"]-1)
    terminal=activity/"batches"/previous/"terminal.json"
    if not terminal.is_file():return False
    record=read(terminal)
    if not record["complete"] or len(record["returns"])!=12:return False
    job=read(activity/"submissions"/(previous+".json"))["job"]
    state,code=states.get(job,(None,None)) if states is not None else scheduler_state(job)
    return record["job"]==job and (state,code)==("COMPLETED","0:0")


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
        allocation_elapsed=int(shell_out("sacct","-n","-X","-j",sub["job"],"--format=ElapsedRaw","-P").splitlines()[0].strip("| "))
        overhead=max(receipt["overhead_s"],allocation_elapsed-sum(v["wall_s"] for v in receipt["returns"]),0.0)
        seconds=12*1.25*max_wall+overhead
        need(abs(12*1.25*max_wall+receipt["overhead_s"]-receipt["projected_next_batch_s"])<1e-6,"pilot projection arithmetic")
        by_role[g["role"]]=dict(job=sub["job"],max_position_s=max_wall,overhead_s=overhead,scheduler_elapsed_s=allocation_elapsed,
                         driver_overhead_s=receipt["overhead_s"],overhead_basis="allocation elapsed less measured unit times; bounded below by driver overhead",
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
        jid=read(timing)["job"];state,code=scheduler_state(jid)
        need(state in terminal,"timing not settled")
        status=act/"center-timing"/"status.json"
        if not status.exists():
            need(state!="COMPLETED" or code!="0:0","completed timing job without its receipt")
            status.parent.mkdir(exist_ok=True)
            def count(file):
                if not file.is_file():return 0
                with file.open("rb") as stream:return sum(1 for l in stream if l.endswith(b"\n"))
            save(status,dict(mode="UNAVAILABLE",validated=False,job=jid,scheduler_state=state,exit_code=code,
                 worker_calls=count(status.parent/"dispatches.jsonl"),frames_validated=count(status.parent/"measurements.jsonl"),
                 facility_calls=0,scores_created=0,category="TERMINAL_WITHOUT_TIMING_RECEIPT",utc=now()))
    else:
        need((act/"center-timing"/"status.json").is_file(),"timing job or documented timing-only gap required")
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
        submitted=[read(path) for path in sorted((act/"submissions").glob("*.json"))
                   if not path.name.endswith((".intent.json",".error.json"))]
        states=scheduler_states([item["job"] for item in submitted])
        from collections import Counter
        state_counts=Counter()
        failed_states={"NODE_FAIL","OUT_OF_MEMORY","BOOT_FAIL","CANCELLED","FAILED","TIMEOUT","PREEMPTED","DEADLINE","REVOKED"}
        for item in submitted:
            state,code=states.get(item["job"],("UNRECONCILED",""))
            state_counts[state]+=1
            if groups[item["name"]]["kind"]=="science" and (state in failed_states or state=="COMPLETED" and code!="0:0"):
                from runner import stop
                stop(act,"scheduler_"+state,item["name"],item["job"])
        print("allocations",len(submitted),dict(state_counts))
        for item in submitted:
            if states.get(item["job"],(None,None))[0] not in ("COMPLETED",):
                print(item["name"],item["job"],*states.get(item["job"],("UNRECONCILED","")))
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
        if r.action=="center-timing":
            need(read(act/"qualification"/"acceptance.json")["pass"] is True,"timing before qualification")
            availability=read(act/"qualification"/"historical-fields.json")["status"]
            if availability not in ("HISTORICAL_RTT_AVAILABLE","NO_PER_DECISION_TIMING"):
                folder=act/"center-timing";folder.mkdir(exist_ok=True)
                if not (folder/"status.json").exists():
                    save(folder/"status.json",dict(mode="UNAVAILABLE",validated=False,category=availability,
                         worker_calls=0,frames_validated=0,native_runs=0,facility_calls=0,scores_created=0,utc=now()))
                print("Timing-only gap recorded",availability);return
        register(act,r.manifest,groups[r.action]);return
    for label in reg["order"]:
        g=groups[label]
        if g["kind"]=="science" and ((r.action=="pilot" and g["batch"]==1) or (r.action=="remaining" and g["batch"]>1)):
            if (act/"submissions"/(label+".json")).exists():continue
            if g["batch"]>1 and not predecessor_ready(act,g):
                print("waiting for preceding serial batch before",label)
                break
            register(act,r.manifest,g)

if __name__=="__main__":
    main()
