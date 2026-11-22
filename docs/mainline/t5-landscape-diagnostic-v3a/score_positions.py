"""Charge, execute and retain each independent original native facility position."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from landscape import (
    ACT, LOCK, PK, batches, binding, case_at, check, check_source, config, digest, job,
    manifest, read, sha, verify_workers, write,
)


def oracle_plan(case):
    from bounds import certificate_for
    try:
        return certificate_for(case)
    except (ValueError, KeyError, TypeError) as error:
        return dict(plan={},lower=None,proof="independent bound unavailable",error=type(error).__name__)


def witness(certificate,metrics):
    if certificate is None:
        return None
    plan=certificate["plan"]
    chain=all([int(t),task] in metrics["requests"] and
              any(w["task"]==task and w["outcome"]=="APPLIED" for w in metrics["writes"]) and
              any(q["task"]==task[:-1]+"R" and q["fields"] and q["execution"] for q in metrics["paid"])
              for t,task in plan.items())
    lower=certificate["lower"]
    attained=lower is not None and chain and max(abs(metrics[k]-lower) for k in ("L","U"))<=1e-7
    return dict(certificate,status="ATTAINED" if attained else "UNRESOLVED",
                certified_min=lower if attained else None,actual_chain=chain,native_L=metrics["L"],native_U=metrics["U"])


def unit(group,label,key,lane):
    os.sched_setaffinity(0,{int(lane)})
    from native_v3 import native_run
    from public_ipc import Process
    import public_work
    from score_saved import score
    from run_panel import retain

    m=manifest();cfg=config()
    reserved=read(ACT/"registrations"/(group+".json"))
    allocation=read(ACT/"batches"/group/"entry.json")
    check(reserved["job"]==allocation["job"]==job() and [label,key] in allocation["slots"]
          and allocation["slots"]==reserved["slots"] and reserved["source"]==sha(LOCK)
          and reserved["panel"]==os.environ["V3A_PANEL"],"registered at the point of native execution")
    case=case_at(key,m)
    vector,manual=binding(label,m)
    dst=ACT/"positions"/label/key
    dst.mkdir(parents=True,exist_ok=False)
    cert=oracle_plan(case) if label=="ORACLE" else None
    worker=None if cert is not None else Process(label,dst/"worker.stderr",vector,manual)
    entry=dict(label=label,key=key,group=group,job=job(),pid=os.getpid(),host=socket.gethostname(),
        worker_pid=worker.child.pid if worker else None,worker_bundle=worker.identity if worker else None,
        vector_sha256=digest(vector) if vector is not None else None,input=m["conditions"][key]["sha256"],
        panel=os.environ["V3A_PANEL"],source=sha(LOCK))
    done=False;started=time.monotonic()
    try:
        if worker:
            worker.start(case["native"]["dispatch_program"]["public"])
        write(dst/"native-entry.json",entry)
        run,terminal=native_run(case,label,cert["plan"] if cert is not None else {},(),
                                decider=worker.choose if worker else public_work.choose)
        done=True
    finally:
        if worker:
            worker.close(failed=not done)
    raw=dst/"original.jsonl.gz"
    retain(raw,run,terminal)
    metrics=score(case,run,terminal,label)
    props=run["v3_proposals"]
    check(len(props)==metrics["clocks"]==61 and metrics["runtime"]==allocation["core_tree"] and
          run["v3_received_maintenance"]==case["maintenance"] and not run["t3_unpurchased_evaluator_only"],
          "original facility identity and information boundary")
    if worker:
        check(worker.child.pid!=os.getpid() and worker.events==[[q["at"],q["view"],q["proposal"]] for q in props],
              "actual worker decisions")
    if label=="B_COST":
        check(not any(n.endswith("::I") for _,n in metrics["requests"]),"unmodified cost baseline")
    summary={k:metrics[k] for k in ("L","U","integral_balances","person","tool","fee","requests","paid","writes","curve","clocks","runtime")}
    summary.update(entry=entry,raw=sha(raw),wall_s=time.monotonic()-started,oracle=witness(cert,metrics),
                   worker_ipc=digest(worker.ipc) if worker else None,proposal=digest(worker.events) if worker else None)
    write(dst/"score.json",summary)
    print(label,key,"scored",flush=True)


def group(name):
    tree=check_source();m=manifest();cfg=config()
    allocated=read(ACT/"registrations"/(name+".json"))
    slots=batches(m,cfg)[name]
    flat=[list(x) for lane in slots for x in lane]
    check(allocated["slots"]==flat and allocated["job"]==job() and allocated["panel"]==os.environ["V3A_PANEL"]
          and allocated["source"]==sha(LOCK) and m["selfcheck"]["pooled_denominator"],"pre-run registration")
    verify_workers()
    if not name.startswith("pilot-"):
        budget=read(ACT/"pilot-budget.json")
        check(budget["proceed"] and budget["panel"]==os.environ["V3A_PANEL"] and allocated["minutes"]==budget["minutes"][name],
              "post-pilot budget")
    cpus=sorted(os.sched_getaffinity(0));n=allocated["cpus"]
    check(n==len(slots)==int(os.environ["SLURM_CPUS_PER_TASK"]) and n<=len(cpus),"actual processor placement")
    dst=ACT/"batches"/name;dst.mkdir()
    write(dst/"entry.json",dict(job=job(),slots=flat,core_tree=tree))
    start=time.monotonic()
    def lane(i):
        outcomes=[]
        for label,key in slots[i]:
            with (dst/(label+"-"+key+".log")).open("x") as log:
                ret=subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"unit",name,label,key,str(cpus[i])],
                                   stdout=log,stderr=subprocess.STDOUT,check=False)
            path=ACT/"positions"/label/key
            outcomes.append(dict(label=label,key=key,exit_code=ret.returncode,entered=(path/"native-entry.json").exists(),
                                 scored=(path/"score.json").exists()))
        return outcomes
    with ThreadPoolExecutor(max_workers=n) as pool:
        complete=[x for items in pool.map(lane,range(n)) for x in items]
    write(dst/"terminal.json",dict(job=job(),wall_s=time.monotonic()-start,positions=complete))
    print(name,"scored",sum(q["scored"] for q in complete),"of",len(flat),flush=True)


if __name__=="__main__":
    if sys.argv[1]=="unit":
        unit(*sys.argv[2:])
    else:
        group(sys.argv[1])
