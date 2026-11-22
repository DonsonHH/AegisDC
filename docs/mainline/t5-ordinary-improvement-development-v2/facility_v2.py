"""Execute a single paid position for a verified allocation and save its original trajectory."""
from concurrent.futures import ThreadPoolExecutor
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from context_v2 import ACT, LOCK, METRICS, case_at, digest, job, need, panel, put, read, sha, verify_learned, verify_sources
from positions import binding,dev_groups,forecast_groups,pilot


def maintenance_penalties(run):
    rows=[]
    for event in run["v3_maintenance_events"]:
        if event["indicated"] or event["until"]<=event["at"]:
            continue
        parts=[]
        for left,right in zip(run["trace"],run["trace"][1:]):
            dt=min(event["until"],right["time_s"])-max(event["at"],left["time_s"])
            if dt<=0:
                continue
            service=left["domains"]["it_service"]
            demand=service["demand"]
            if demand>0:
                native=min(demand,*(v for k,v in service["capacities"].items() if k!="maintenance_support"))
                parts.append(dt*max(0,native-service["delivered"])/demand)
        rows.append(dict(event,lost_L_at_cap=math.fsum(parts)))
    return rows


def unit(group,label,key,cpu):
    os.sched_setaffinity(0,{int(cpu)})
    from native_v3 import native_run
    from public_ipc import Process
    from run_panel import retain
    from score_saved import score

    inputs=panel()
    path=ACT/"positions"/label/key
    path.mkdir(parents=True)
    registered=read(ACT/"batches"/group/"entry.json")
    need(registered["job"]==job() and [label,key] in registered["positions"],"reserved facility call")
    descriptor,manual=binding(label)
    case=case_at(key,inputs)
    pub=case["native"]["dispatch_program"]["public"]
    worker=Process(label,path/"worker.stderr",descriptor,manual)
    entry=dict(job=job(),group=group,label=label,key=key,host=socket.gethostname(),pid=os.getpid(),
            worker_pid=worker.child.pid,worker_bundle=worker.identity,descriptor=digest(descriptor) if descriptor else None,
            input=inputs["cases"][key]["sha256"],input_manifest=os.environ["T5V2_INPUTS"],source=sha(LOCK),charged=True)
    success=False
    try:
        worker.start(pub)
        put(path/"entry.json",entry)
        run,result=native_run(case,label,{},(),decider=worker.choose)
        success=True
    finally:
        worker.close(failed=not success)
    raw=path/"native.jsonl.gz"
    retain(raw,run,result)
    measures=score(case,run,result,label)
    proposals=run["v3_proposals"]
    need(worker.events==[[d["at"],d["view"],d["proposal"]] for d in proposals] and len(proposals)==measures["clocks"]==61,
         "61 public frames received by original facility")
    need(measures["runtime"]==registered["native_tree"] and run["v3_received_maintenance"]==case["maintenance"]
         and not run["t3_unpurchased_evaluator_only"] and worker.child.pid!=os.getpid(),"unchanged facility and isolated strategy")
    if label.endswith(("NOPROBE","-NP")) or label in ("B","B_COST"):
        need(all(not action.endswith("::I") for _,action in measures["requests"]),"registered no-initial-probe arm")
    measures={k:measures[k] for k in (*METRICS,"paid","requests","writes","curve","checkpoints","first","integral_balances","clocks")}
    measures.update(entry=entry,raw_sha256=sha(raw),public_transcript=digest(worker.events),public_ipc=digest(worker.ipc),
        maintenance=maintenance_penalties(run),terminal_power_events=result["events"] if result else [])
    put(path/"score.json",measures)
    print(label,key,"scored",flush=True)


def batch(name):
    native=verify_sources()
    verify_learned("learned")
    info=panel()
    checked=read(ACT/"public-checks/result.json")
    need(checked["native_entries"]==0 and checked["inputs"]==os.environ["T5V2_INPUTS"],"published self-check")
    if name=="pilot":
        expected=pilot(info)
    elif name.startswith("fit-"):
        expected=forecast_groups(info,int(name.split("-")[1]))[name]
    else:
        expected=dev_groups(info)[name]
        verify_learned("manual")
    reserve=read(ACT/"registrations"/(name+".json"))
    need(reserve["job"]==job() and reserve["input"]==os.environ["T5V2_INPUTS"] and reserve["source"]==sha(LOCK)
          and reserve["positions"]==[list(x) for x in expected],"exact charged positions")
    cpus=sorted(os.sched_getaffinity(0))
    n=reserve["cpus"]
    need(n==int(os.environ["SLURM_CPUS_PER_TASK"]) and len(cpus)>=n,"reserved compute lanes")
    path=ACT/"batches"/name
    path.mkdir()
    put(path/"entry.json",dict(job=job(),positions=expected,native_tree=native))
    started=time.monotonic()
    def lane(i):
        out=[]
        for label,key in expected[i::n]:
            with (path/(label+"-"+key+".log")).open("x") as stream:
                result=subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"unit",name,label,key,str(cpus[i])],
                                      stdout=stream,stderr=subprocess.STDOUT,check=False)
            unit_path=ACT/"positions"/label/key
            out.append(dict(label=label,key=key,position_entered=(unit_path/"entry.json").is_file(),
                            scored=(unit_path/"score.json").is_file(),exit_code=result.returncode))
        return out
    with ThreadPoolExecutor(max_workers=n) as pool:
        rows=[row for outcomes in pool.map(lane,range(n)) for row in outcomes]
    put(path/"terminal.json",dict(job=job(),positions=rows,wall_s=time.monotonic()-started))
    print(name,sum(x["scored"] for x in rows),"scored of",len(rows),flush=True)


if __name__=="__main__":
    if sys.argv[1]=="unit":
        unit(*sys.argv[2:])
    else:
        batch(sys.argv[1])
