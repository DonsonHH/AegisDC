"""Buy and execute precisely one original physical run per registered policy and condition."""
from concurrent.futures import ThreadPoolExecutor
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from context_t5 import (
    ACT, LOCK, METRICS, bundle_paths, cases, digest, job, read, read_case, require,
    sha, verify_bundles, verify_sources, write,
)
from run_plan import descriptor, expected_positions


def execute(group, label, key, cpu):
    os.sched_setaffinity(0,{int(cpu)})
    from bounds import information
    from native_v3 import native_run
    from public_process import Process
    from run_panel import retain
    from score_saved import score

    manifest=cases()
    registration=read(ACT/"registrations"/(group+".json"))
    entry=read(ACT/"batches"/group/"entry.json")
    require(registration["job"]==entry["job"]==job() and [label,key] in entry["positions"],"paid placement")
    path=ACT/"positions"/label/key
    path.mkdir(parents=True,exist_ok=False)
    case=read_case(key,manifest)
    pub=case["native"]["dispatch_program"]["public"]
    theta=descriptor(label)
    refs,_=bundle_paths()
    proc=Process(label,path/"worker.stderr",reference=refs.get(label),descriptor=theta)
    measurements=information(case,None,None)["all_paid"] if label=="P" else ()
    receipt=dict(group=group,job=job(),label=label,key=key,pid=os.getpid(),host=socket.gethostname(),worker_pid=proc.child.pid,
         source=sha(LOCK),input_manifest=os.environ["T5_INPUT_SHA"],input=manifest["conditions"][key]["sha256"],
         descriptor=digest(theta) if theta else None,worker_bundle=proc.identity,paid=True)
    started=time.monotonic()
    success=False
    try:
        proc.start(pub)
        write(path/"native-entry.json",receipt)
        run,terminal=native_run(case,label,{},measurements,decider=proc.choose)
        success=True
    finally:
        proc.close(failed=not success)
    raw=path/"original.jsonl.gz"
    retain(raw,run,terminal)
    metrics=score(case,run,terminal,label)
    props=run["v3_proposals"]
    require(proc.events==[[q["at"],q["view"],q["proposal"]] for q in props] and len(props)==metrics["clocks"]==61,
            "native/worker correspondence")
    require(proc.child.pid!=os.getpid() and run["v3_received_maintenance"]==case["maintenance"]
            and metrics["runtime"]==entry["native_tree"],"separate workers and original facility")
    require(label=="P" or not run["t3_unpurchased_evaluator_only"],"paid diagnostic scope")
    if label in ("V_COST_NOPROBE","HOT_NOPROBE","B","B_COST"):
        require(not any(t.endswith("::I") for _,t in metrics["requests"]),"no initial inspection in this arm")
    binding=[]
    for event in run["v3_maintenance_events"]:
        if event["indicated"] or event["until"]<=event["at"]:
            continue
        losses=[]
        for left,right in zip(run["trace"],run["trace"][1:]):
            dt=min(event["until"],right["time_s"])-max(event["at"],left["time_s"])
            if dt<=0:
                continue
            service=left["domains"]["it_service"]
            if service["demand"]>0:
                unaffected=min(service["demand"],*(v for k,v in service["capacities"].items() if k!="maintenance_support"))
                losses.append(max(0,unaffected-service["delivered"])*dt/service["demand"])
        binding.append(dict(event,lost_L_at_cap=math.fsum(losses)))
    output={k:metrics[k] for k in (*METRICS,"first","checkpoints","requests","writes","paid","curve","integral_balances","refusals","clocks","runtime")}
    output.update(entry=receipt,status="SCORED",raw_sha256=sha(raw),public_transcript=digest(proc.events),public_ipc=digest(proc.ipc),
                  elapsed_s=time.monotonic()-started,maintenance=binding,
                  terminal_power_events=terminal["events"] if terminal else [])
    write(path/"score.json",output)
    print(label,key,"scored",round(output["elapsed_s"],2),flush=True)


def batch(group):
    tree=verify_sources()
    manifest=cases()
    verify_bundles(learned=True)
    witness=read(ACT/"initial-checks/result.json")
    require(witness["native_entries"]==0 and witness["input_sha256"]==os.environ["T5_INPUT_SHA"],"checked initial policies")
    registration=read(ACT/"registrations"/(group+".json"))
    items=expected_positions(manifest,group)
    require(registration["job"]==job() and registration["source"]==sha(LOCK) and
            registration["input"]==os.environ["T5_INPUT_SHA"] and registration["positions"]==[list(x) for x in items],
            "complete reserved group")
    cpus=sorted(os.sched_getaffinity(0))
    n=registration["cpus"]
    require(n==int(os.environ["SLURM_CPUS_PER_TASK"]) and len(cpus)>=n,"assigned processor lanes")
    path=ACT/"batches"/group
    path.mkdir()
    write(path/"entry.json",dict(job=job(),positions=items,native_tree=tree))
    started=time.monotonic()
    def lane(i):
        returns=[]
        for label,key in items[i::n]:
            with (path/(label+"-"+key+".log")).open("x") as log:
                exit_code=subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"unit",group,label,key,str(cpus[i])],
                                         stdout=log,stderr=subprocess.STDOUT,check=False).returncode
            folder=ACT/"positions"/label/key
            returns.append(dict(label=label,key=key,entered=(folder/"native-entry.json").is_file(),
                                scored=(folder/"score.json").is_file(),exit_code=exit_code))
        return returns
    with ThreadPoolExecutor(max_workers=n) as pool:
        returns=[x for lane_results in pool.map(lane,range(n)) for x in lane_results]
    write(path/"return.json",dict(job=job(),positions=returns,wall_s=time.monotonic()-started))
    print(group,len(returns),"scored",sum(r["scored"] for r in returns),flush=True)


if __name__=="__main__":
    if sys.argv[1]=="unit":
        execute(*sys.argv[2:])
    else:
        batch(sys.argv[1])
