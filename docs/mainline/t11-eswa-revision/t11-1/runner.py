"""Native T4c execution and a public-only subprocess, with pre-call accounting."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from operations import (BASELINE_ROLES, ORIGINAL, PYTHON, SCIENCE, check_stage, cpu, file_sha,
                        in_allocation, need, now, original_identities, packed, public_bundle,
                        read, save, signature)


class HardViolation(ValueError):
    """An observed executed action violates a frozen hard constraint."""


class PublicProcess:
    def __init__(self, bundle, role, directory, timing_file, *, center=False):
        self.role=role
        self.center=center
        self.events=[]
        self.timing_file=timing_file
        self.stderr=(directory/"worker.stderr").open("xb")
        self.attempt_log=None if center else (directory/"public-call-attempts.jsonl").open("xb")
        entry=bundle/("aegis_action_cost/worker.py" if center else "worker.py")
        flags=["-I","-S","-B"] if center else ["-I","-B"]
        self.proc=subprocess.Popen([str(PYTHON),*flags,str(entry),role],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=self.stderr,cwd=bundle,env={"LANG":"C.UTF-8","LC_ALL":"C.UTF-8",
            "OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1","MKL_NUM_THREADS":"1","NUMEXPR_NUM_THREADS":"1"})
        self.static=None

    def exchange(self,message):
        start=time.perf_counter_ns()
        data=packed(message)+b"\n"
        serialized=time.perf_counter_ns()
        self.proc.stdin.write(data)
        self.proc.stdin.flush()
        line=self.proc.stdout.readline()
        returned=time.perf_counter_ns()
        need(bool(line),"public worker terminated before complete response")
        reply=json.loads(line)
        parsed=time.perf_counter_ns()
        return reply,dict(ipc_wall_ns=parsed-start,request_serialization_ns=serialized-start,
                          response_parse_ns=parsed-returned)

    def start(self,pub):
        reply,_=self.exchange({"public":pub})
        need(reply=={"ready":True,"role":self.role},"public handshake")
        self.static=signature(pub)

    def decision(self,view):
        answer,measured=self.exchange({"view":view})
        if self.center:
            rationale=answer["rationale"]
            measured["reason"]=rationale["reason"]
            # Historical worker remains byte-identical. Its internal CPU timing is unavailable.
            return answer,measured
        need(set(answer)=={"decision","timing"},"public envelope")
        timing=answer["timing"]
        need(all(k in timing for k in ("worker_wall_ns","worker_cpu_ns","tree_ns","leaf_ns",
                                       "tree_steps","leaf_evaluations","simulations","nodes","max_depth","reason")),
             "per-decision timing fields")
        need(all(type(timing[k]) is int and timing[k]>=0 for k in
                 ("worker_wall_ns","worker_cpu_ns","tree_ns","leaf_ns","tree_steps","leaf_evaluations",
                  "simulations","nodes","max_depth")),"timing/counter domains")
        need(timing["simulations"]<=128 and timing["max_depth"]<=4 and
             timing["tree_steps"]<=4*timing["simulations"] and
             timing["leaf_evaluations"]<=timing["simulations"],"planner operation ceiling")
        need(timing["reason"]==answer["decision"]["rationale"]["reason"] and
             timing["leaf_ns"]+timing["tree_ns"]<=timing["worker_wall_ns"] and
             type(timing.get("effective_choices")) is int and timing["effective_choices"]>=0,
             "recorded reason, legal-choice count and disjoint timing")
        if self.role=="POMCP" and timing["effective_choices"]>1:
            need(timing["simulations"]==128,"fixed POMCP root budget")
        if self.role!="POMCP":
            need(not any(timing[k] for k in ("tree_steps","leaf_evaluations","simulations","nodes","max_depth",
                                             "tree_ns","leaf_ns")),"non-tree accounting")
        measured.update(timing)
        return answer["decision"],measured

    def choose(self,pub,view,role,plan):
        need(role==self.role and not plan and signature(pub)==self.static,"public-only ingress")
        view_hash=signature(view)
        self.attempt_log.write(packed({"time":view["time"],"view_sha256":view_hash})+b"\n")
        self.attempt_log.flush()
        decision,timing=self.decision(view)
        t=view["time"]
        self.events.append([t,view_hash,signature(decision)])
        self.timing_file.write(packed(dict(time=t,**timing))+b"\n")
        self.timing_file.flush()
        return decision

    def close(self):
        try:
            if self.proc.poll() is None:
                try:
                    self.proc.stdin.write(b'{"close":true}\n')
                    self.proc.stdin.flush()
                except BrokenPipeError:
                    pass
            try:self.proc.stdin.close()
            except BrokenPipeError:pass
            return self.proc.wait(timeout=15)
        finally:
            if self.proc.poll() is None:
                self.proc.terminate()
                self.proc.wait(timeout=15)
            self.proc.stdout.close()
            self.stderr.close()
            if self.attempt_log is not None:self.attempt_log.close()


def hard_checks(pub,run,metrics,gate,role,timing_path):
    """Check actual issued work; a lawful rejection with no work is not a violation."""
    from aegis_action_cost.planning import PublicCalendar, sequences
    from aegis_risk_dispatch import policy,belief
    subjects={s["id"]:s for s in pub["subjects"]}
    actual={w[0] for w in metrics["work"]}
    settings=read(ORIGINAL/"public-only"/"aegis_risk_dispatch"/"settings.json")
    if role in ("match_low","match_high"):
        settings["fixed_match_probability"]=0.85 if role=="match_low" else 0.99
    with timing_path.open("rb") as stream:timings=[json.loads(line) for line in stream]
    for row,point in zip(run["policy_public_decisions"],timings,strict=True):
        v=row["view"]; req=row["decision"]["request"]
        due,renew=policy.priorities(pub,v,gate)
        forced,_=policy.first_legal(due+renew,pub,v,gate)
        if forced is not None and req!=forced:
            raise HardViolation("required own verification or renewal was skipped")
        if req is not None and req["phase"] in ("R","X") and req!=forced:
            raise HardViolation("unmatched mandatory work")
        if (role=="POMCP" or req is not None) and forced is None:
            posterior,_=belief.posterior(pub,v,settings)
            paid={r["task"] for r in v["paid"]}
            waiting=False
            for work in (r for r in v["issued"] if r["phase"]=="I"):
                ack=gate.ack(v,work["task"])
                waiting|=(ack is None and v["time"]<=work["planned_end"]+pub["latency"]) or (
                      bool(ack) and ack["status"]=="completed" and work["task"] not in paid and
                      v["time"]<ack["observed_at_s"]+pub["latency"])
            eligible=set()
            if posterior and not waiting:
                cal=PublicCalendar(pub,v,gate)
                for sid,subject in subjects.items():
                    if not subject["primary"] or sid not in cal.opened:continue
                    for phase in ("A","I"):
                        if phase=="I" and sid+"::A" in cal.done:continue
                        allowed,_=gate.admit(pub,v,subject,phase)
                        if not allowed:continue
                        complete=cal.run((sid,phase),(),renew_initial=False) is not None
                        if phase=="A" and not complete:
                            other=[(k,"A") for k,item in subjects.items() if k!=sid and item["primary"] and
                                   k in cal.opened and k+"::A" not in cal.done and item["write_window"][1]>v["time"]]
                            complete=any(seq and cal.run((sid,phase),seq,renew_initial=False) is not None for seq in sequences(other))
                        if complete:eligible.add((sid,phase))
            if req is not None and (req["subject"],req["phase"]) not in eligible:
                raise HardViolation("executed elective request lacked a feasible calendar or public support")
            if role=="POMCP":
                need(point["simulations"]==(128 if eligible else 0),"POMCP real-root budget vs independent mask")
                if eligible:
                    need(point["effective_choices"]==len(eligible)+1,"effective root choices vs calendar")
        elif role=="POMCP":
            need(point["simulations"]==point["tree_steps"]==point["leaf_evaluations"]==0,"mandatory root search accounting")
        if req is None: continue
        need(req["task"] in actual,"returned issued request missing actual record")
        s=subjects[req["subject"]]
        admitted,_=gate.admit(pub,v,s,req["phase"],req["patrol_slot"])
        after_write=any(q["subject"]==req["subject"] and q["phase"]=="A" for q in v["issued"])
        if req!=admitted or (req["phase"] in ("A","I") and not s["primary"]) or (req["phase"]=="I" and after_write):
            raise HardViolation("executed action outside common public mask")
    if any(metrics[k]>bound+1e-7 for k,bound in zip(("person","tool","fee"),pub["resources"],strict=True)):
        raise HardViolation("actual work above hard resource limit")


def unit(activity,manifest,role,key,label):
    job=os.environ["SLURM_JOB_ID"]
    registration=read(activity/"registration.json")["groups"][label]
    need(registration["role"]==role and key in registration["keys"],"unit not in registered batch")
    result=activity/"positions"/role/key
    result.mkdir(parents=True,exist_ok=False)
    start=time.monotonic(); startcpu=cpu()
    score=None; run=None
    try:
        original_manifest=read(activity/"references"/"original-dev-manifest.json")
        path=ORIGINAL/"dev-inputs"/(key+".json")
        h=file_sha(path)
        need(h==original_manifest["files"][key],"live input digest")
        case=read(path);pub=case["native"]["dispatch_program"]["public"]
        entry=dict(key=key,role=role,input_sha256=h,job=job,label=label,attempt=1,
                   manifest=manifest,implementation=read(activity/"source-manifest.json")["implementation_revision"],
                   protocol="T11-0-ESWA-SUPP-v1.1",started_utc=now())
        save(result/"entry.json",entry)
        bundle=public_bundle(activity)
        # The original native module and scorer import the exact T4c source and release core.
        sys.path.insert(0,str(SCIENCE))
        import common_v3
        common_v3.pinned()
        import native_v3
        import score_saved
        import run_panel
        from aegis_action_cost.permit import Gate
        need(Path(native_v3.__file__).resolve()==SCIENCE/"native_v3.py" and
             Path(score_saved.__file__).resolve()==SCIENCE.parent/"t3-prior-information-v2"/"score_saved.py",
             "native and scoring module origins")
        need(common_v3.CORE==ORIGINAL.parent/"V6-cold-launch-release-v1"/"source","native core binding")
        with (result/"timing.jsonl").open("xb") as timings:
            startup=time.perf_counter_ns()
            child=PublicProcess(activity/"public-only",role,result,timings)
            try:
                child.start(pub)
                before_native=dict(**entry,pid=os.getpid(),worker_pid=child.proc.pid,public_program=signature(pub),
                                   bundle=bundle,worker_startup_ns=time.perf_counter_ns()-startup)
                save(result/"native-entry.json",before_native)
                # A single charged call; no hidden reference run, diagnostic probe or retry.
                run,terminal=native_v3.native_run(case,role,{},(),decider=child.choose)
                save(result/"native-return.json",dict(key=key,role=role,job=job,input_sha256=h,
                     clocks=len(run["policy_public_decisions"]),worker_calls=len(child.events),
                     source_tree=run["code_identity"]["source_tree_sha256"],utc=now()))
            finally:
                code=child.close()
            need(code==0,"public worker exit")
        raw=result/"original.jsonl.gz"
        run_panel.retain(raw,run,terminal)
        metrics=score_saved.score(case,run,terminal,role)
        clock=run["v3_proposals"]
        need(len(child.events)==len(clock)==metrics["clocks"]==61 and
             child.events==[[q["at"],q["view"],q["proposal"]] for q in clock],"detached transcript and clock count")
        need(not run["t3_unpurchased_evaluator_only"] and run["v3_received_maintenance"]==case["maintenance"],
             "independent service/observation boundary")
        need(metrics["runtime"]==read(activity/"references"/"baseline-freeze.json")["native_runtime"],"actual native core")
        need(abs(metrics["L"]-metrics["integral_balances"][0])<1e-7 and
             abs(metrics["U"]-metrics["integral_balances"][1])<1e-7,"independent integral checks")
        selected=("L","U","person","tool","fee","requests","refusals","first","checkpoints","work","clocks",
                  "runtime","writes","first_loss","closure_changes","public_prefix")
        score={k:metrics[k] for k in selected}
        score["maintenance"]=run["v3_maintenance_events"]
        score["locks"]=[[q["at"],q["requested"]["subject"]] for q in clock if q["external_refusal"]]
        score.update(key=key,role=role,input_sha256=h,job=job,entry=entry,
                     IPC=signature(child.events),raw_sha256=file_sha(raw),timing_sha256=file_sha(result/"timing.jsonl"),
                     elapsed_s=time.monotonic()-start,process_cpu_s=cpu()-startcpu,completed_utc=now())
        hard_checks(pub,run,metrics,Gate(case["maintenance"]["recovery"]),role,result/"timing.jsonl")
        score["conformant"]=True
        save(result/"score.json",score)
        print(key,role,"completed",flush=True)
    except BaseException as exc:
        counted=(result/"native-entry.json").is_file()
        category="HARD_VIOLATION" if isinstance(exc,HardViolation) else ("IDENTITY_OR_RUN_UNRESOLVED" if counted else "PRE_NATIVE_FAILURE")
        failure=dict(key=key,role=role,job=job,category=category,hard_violation=isinstance(exc,HardViolation),
                     native_call_counted=counted,terminal_utc=now(),error_type=type(exc).__name__)
        if score is not None:
            score["conformant"]=False if isinstance(exc,HardViolation) else None
            failure["observed"]=score
        save(result/"failure.json",failure)
        stop(activity,category,label,job)
        raise


def stop(activity,cause,label,job):
    try:save(activity/"STOP.json",dict(cause=cause,label=label,job=job,utc=now()))
    except FileExistsError:pass


def batch(activity,manifest,label):
    group=read(activity/"registration.json")["groups"][label]
    role=group["role"];keys=group["keys"]
    need(read(activity/"qualification"/"acceptance.json")["pass"] is True,"public qualification gate")
    if group["batch"]>1:
        need(read(activity/"pilot-projection.json")["continue"] is True,"whole-panel pilot gate")
    out=activity/"batches"/label
    out.mkdir()
    save(out/"entry.json",dict(label=label,role=role,job=os.environ["SLURM_JOB_ID"],keys=keys,utc=now()))
    start=time.monotonic();c=cpu();returns=[]
    for key in keys:
        if (activity/"STOP.json").exists():break
        t=time.monotonic()
        with (out/(key+".log")).open("xb") as log:
            ret=subprocess.run([str(PYTHON),"-I","-B",str(Path(__file__).resolve()),"--activity",str(activity),
                    "--manifest",manifest,"unit",label,role,key],stdout=log,stderr=subprocess.STDOUT,check=False)
        returns.append(dict(key=key,code=ret.returncode,wall_s=time.monotonic()-t))
        if ret.returncode:
            stop(activity,"unit_failure",label,os.environ["SLURM_JOB_ID"])
            break
    wall=time.monotonic()-start
    overhead=max(0.,wall-sum(x["wall_s"] for x in returns))
    complete=len(returns)==12 and all(x["code"]==0 for x in returns)
    projection=(12*1.25*max(x["wall_s"] for x in returns)+overhead) if complete else None
    save(out/"terminal.json",dict(role=role,label=label,job=os.environ["SLURM_JOB_ID"],complete=complete,returns=returns,
             suffix=keys[len(returns):],elapsed_s=wall,measured_process_cpu_s=cpu()-c,overhead_s=overhead,
             projected_next_batch_s=projection,resource_limit_s=group["seconds"],utc=now()))
    need(complete,"batch stopped before full return")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activity",required=True)
    parser.add_argument("--manifest",required=True)
    parser.add_argument("action",choices=("job","unit"))
    parser.add_argument("label")
    parser.add_argument("args",nargs="*")
    arg=parser.parse_args()
    act,_=check_stage(arg.activity,arg.manifest)
    in_allocation(act,arg.label)
    if arg.action=="unit":
        unit(act,arg.manifest,*arg.args,arg.label);return
    try:
        if arg.label=="qualification":
            __import__("qualification_session").run(act,arg.manifest)
        elif arg.label=="center-timing":
            __import__("center_timing").measure(act,arg.manifest)
        elif arg.label=="analysis":
            need((act/"science-settled.json").is_file(),"science attempts not reconciled")
            start=cpu()
            __import__("native_readback").finalize(act)
            subprocess.run([str(PYTHON),"-B",str(act/"source"/"analysis.py"),"--activity",str(act)],check=True)
            save(act/"analysis-job.json",dict(job=os.environ["SLURM_JOB_ID"],cpu_s=cpu()-start,utc=now()))
        else:
            batch(act,arg.manifest,arg.label)
    except BaseException as exc:
        if arg.label!="center-timing":
            stop(act,"job_"+type(exc).__name__,arg.label,os.environ["SLURM_JOB_ID"])
        traceback.print_exc()
        raise
    finally:
        save(act/"job-costs"/(arg.label+".json"),dict(job=os.environ["SLURM_JOB_ID"],label=arg.label,
             process_cpu_s=cpu(),utc=now()))

if __name__=="__main__":
    main()
