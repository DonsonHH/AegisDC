"""Trusted per-position broker. The evaluator and online policy communicate through checked pipes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time

import sandbox
from prepare_runtime import BASE, STUDY, compact, read, require, save


def digest(x):
    return hashlib.sha256(compact(x)).hexdigest()


def receive(proc):
    raw=proc.stdout.readline()
    if not raw:raise RuntimeError("role terminated before replying")
    return json.loads(raw)


def transmit(proc,obj):
    proc.stdin.write(compact(obj)+b"\n")
    proc.stdin.flush()


def terminate(proc):
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=3)
        except Exception:
            proc.kill()
            proc.wait()


def bind_broker(image):
    # This is the checked gateway. It never passes its policy module or evaluator objects to a role.
    path=str(image/"parent")
    if path not in sys.path:sys.path.insert(0,path)
    from aegis_risk_dispatch import policy
    require(Path(policy.__file__).resolve().is_relative_to(image/"parent"),"public gateway binding")
    return policy


def frame_guard(policy, pub, view, original_channel, ordinal, previous):
    policy.validate(pub,view)
    now=ordinal*60
    require(view["time"]==now and ordinal<61,"original sixty-second public clock")
    require([r for r in view["records"] if r["kind"]!="status"]==[r for r in original_channel if r["arrived"]<=now],
            "original public arrivals and copy provenance")
    subs={s["id"]:s for s in pub["subjects"]}
    for r in view["records"]:
        if r["kind"]=="status":
            require(r["source"]=="controller-work-channel" and r["origin"]=="return-ack" and
                    r["subject"]=="NP" and r["copied_from"] is None,"status publication")
    for r in view["fixed"]:
        field=r["field"]
        physical="service" if field=="service" else subs[field]["key"]
        require(r["source"]=="meter/"+field and r["origin"]=="meter/"+physical+"@"+format(r["sampled"],"g") and
                r["arrived"]==r["sampled"]+15 and r["until"]==r["sampled"]+pub["fixed_ttl"],"fixed origin/timing")
    for r in view["paid"]:
        sub=subs[r["subject"]]
        require(r["source"]=="onsite/"+r["subject"] and r["origin"]==r["task"]+"@"+format(r["sampled"],"g") and
                r["worker"]==sub["worker"] and r["tool"]==sub["tool"] and r["arrived"]==r["sampled"]+pub["latency"] and
                r["until"]==r["sampled"]+pub["paid_ttl"],"paid origin/timing")
    for r in view["work"]:
        require(r["source_id"]=="workforce-execution-report" and r["origin_id"]=="workforce:"+r["task_id"],
                "work provenance")
    for r in view["writes"]:
        require(r["source"]=="work-execution" and r["origin"]=="write/"+r["task"] and r["arrived"]==r["at"]+15,
                "write provenance")
    require(all(r["task"] in previous and previous[r["task"]]==r for r in view["issued"]),"prior lawful proposal")


def online(image, levels, logs):
    baseline=levels is None
    role="parent" if baseline else "child"
    entry="/public/aegis_action_cost/worker.py" if baseline else "/t8/public_roles.py"
    arg="V_COST" if baseline else "descriptor"
    child=sandbox.spawn(image,role,entry,[arg],logs)
    if not baseline:
        transmit(child,{"levels":levels})
        require(receive(child)=={"configured":True},"descriptor acknowledgement")
    return role,child


def actual(image, scratch, out, ordinal, levels):
    from access_audit import audit
    reservations=read(out.parent/"reservation.json")
    require(ordinal in reservations["ordinals"] and os.environ["SLURM_JOB_ID"]==reservations["job_id"],"prepaid position")
    path=BASE/"panel/conditions"/f"{ordinal:02}.json"
    original=path.read_bytes()
    require(hashlib.sha256(original).hexdigest()==reservations["full_inputs"][ordinal-1],"frozen position input")
    case=json.loads(original)
    public=case["native"]["dispatch_program"]["public"]
    original_channel=case["native"]["dispatch_program"]["channel"]
    policy=bind_broker(image)
    scratch.mkdir(exist_ok=False)
    sink=scratch/"sink";sink.mkdir(mode=0o755)
    sink.chmod(0o700)
    local_input=scratch/"input.json"
    local_input.write_bytes(original);local_input.chmod(0o444)
    worker=evaluator=None;role="parent" if levels is None else "child";events=[];previous={}
    try:
        role,worker=online(image,levels,scratch/"online")
        evaluator=sandbox.spawn(image,"eval","/t8/native_role.py",["V_COST" if levels is None else "T8"],
                   scratch/"eval",mounts=[("--ro-bind",local_input,"/input.json"),("--bind",sink,"/out")])
        msg=receive(evaluator);require(msg=={"public":public},"only the frozen static frame")
        transmit(worker,msg);require(receive(worker)=={"ready":True,"role":"V_COST"},"original public handshake")
        transmit(evaluator,{"ready":True})
        verify=receive(evaluator);require(verify=={"begin":hashlib.sha256(original).hexdigest()},"native input identity")
        require(not (STUDY/"STOP").exists(),"study already stopped")
        save(out/"native-admitted.json",{"job":os.environ["SLURM_JOB_ID"],"input":verify["begin"],"ordinal":ordinal})
        transmit(evaluator,{"proceed":True})
        while True:
            msg=receive(evaluator)
            if "complete" in msg:break
            require(set(msg)=={"view"} and not (STUDY/"STOP").exists(),"closed public envelope/active run")
            view=msg["view"];frame_guard(policy,public,view,original_channel,len(events),previous)
            transmit(worker,msg);decision=receive(worker)
            require(set(decision)=={"request","certificates","refusals","rationale"} and
                    set(decision["certificates"])=={s["id"] for s in public["subjects"]},"public response layout")
            if decision["request"] is not None:
                req=decision["request"]
                require(set(req)==policy.FIELDS["issued"] and req["at"]==view["time"],"issued task wire")
                previous[req["task"]]=req
            events.append([view["time"],digest(view),digest(decision)])
            transmit(evaluator,decision)
        require(set(msg)=={"complete","L","person","hard_violations","public_transcript"} and
                msg["complete"] is True and msg["hard_violations"]==0 and
                len(events)==61 and msg["public_transcript"]==digest(events),"complete physical/public transcript")
        transmit(worker,{"close":True});worker.stdin.close()
        evaluator.stdin.close()
        require(evaluator.wait(timeout=15)==worker.wait(timeout=15)==0,"worker/plant exit")
        audits={}
        for kind,folder in ((role,"online"),("eval","eval")):
            loc=scratch/(folder+"-audit")
            audits[kind]=sandbox.audit_role(image,kind,scratch/folder,loc)
            audits[kind]["observer"]=audit(loc,"audit")
        save(scratch/"access.json",audits)
        store_result={k:msg[k] for k in ("L","person","hard_violations")}
        save(scratch/"return.json",store_result)
    except Exception as failure:
        stop("position failed: "+type(failure).__name__)
        raise
    finally:
        terminate(worker);terminate(evaluator)
        # A failed position keeps all available traces and native originals. The evaluator only has a local sink.
        for path in scratch.iterdir():
            if path==local_input:continue
            if path.is_dir():shutil.copytree(path,out/path.name,dirs_exist_ok=False)
            else:shutil.copyfile(path,out/path.name)


def stop(reason):
    try:save(STUDY/"STOP",{"job":os.environ["SLURM_JOB_ID"],"reason":reason})
    except FileExistsError:pass


def unit(args):
    os.sched_setaffinity(0,{args.cpu})
    # Parent-created slot/ordinal directory is an exclusive pre-launch charge.
    out=args.output
    require(out.is_dir() and not (out/"broker-entry.json").exists(),"unique evaluator launch")
    save(out/"broker-entry.json",{"ordinal":args.ordinal,"pid":os.getpid(),"cpu":args.cpu,"started_ns":time.time_ns()})
    def aborted(signum,frame):
        raise InterruptedError("position interrupted after study stop")
    signal.signal(signal.SIGTERM,aborted)
    try:
        actual(args.image,args.scratch,out,args.ordinal,None if args.levels=="parent" else json.loads(args.levels))
    except Exception as failure:
        stop(type(failure).__name__)
        save(out/"broker-failure.json",{"type":type(failure).__name__,"reason":str(failure)})
        return 1
    return 0


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("image","scratch","output"):p.add_argument("--"+n,type=Path,required=True)
    p.add_argument("--levels",required=True);p.add_argument("--ordinal",required=True,type=int);p.add_argument("--cpu",required=True,type=int)
    sys.exit(unit(p.parse_args()))
