"""Reserve an entire FIT slot, launch fresh bounded positions, retain every physical attempt."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from prepare_runtime import PK, STUDY, compact, read, require, save
from positions import stop
from sandbox import filehash

sys.path.insert(0,str(PK.parents[1]/"r1"))
from fit_broker import POSITION_US, ROWS, microseconds
from fit_evidence import public_hex, signed
from fit_program import ZERO


def process_us(pid):
    total=0
    pending=[pid]
    seen=set()
    while pending:
        p=pending.pop()
        if p in seen:continue
        seen.add(p)
        try:
            stat=Path(f"/proc/{p}/stat").read_text().rsplit(")",1)[1].split()
            total+=sum(int(t) for t in stat[11:15])
            pending.extend(map(int,Path(f"/proc/{p}/task/{p}/children").read_text().split()))
        except (FileNotFoundError,ProcessLookupError):continue
    return total*1_000_000//os.sysconf("SC_CLK_TCK")


class NativeBroker:
    def __init__(self,store,key,image,scratch,full_inputs):
        self.store=store
        self.key=key
        self.authority=public_hex(key)
        self.image=image
        self.scratch=scratch
        self.inputs=full_inputs
        self.cpus=sorted(os.sched_getaffinity(0))
        require(len(self.cpus)>=int(os.environ["SLURM_CPUS_PER_TASK"]),"allocated CPU affinity")
        self.cpus=self.cpus[:int(os.environ["SLURM_CPUS_PER_TASK"])]

    def evaluate(self,binding,levels):
        label=f"{binding['arm']}-{binding['round']}-{binding['slot']}"
        target=STUDY/"positions"/label
        target.mkdir(parents=True,exist_ok=False)
        save(target/"reservation.json",{"job_id":os.environ["SLURM_JOB_ID"],"binding":binding,"levels":levels,
                                       "ordinals":list(range(1,ROWS+1)),"full_inputs":self.inputs})
        attempts,rows=[],[]
        returns={}
        pending=list(range(1,ROWS+1))
        live={}
        available=list(self.cpus)
        terminated=set()
        started_ns=time.monotonic_ns()
        supervisor_start=time.process_time_ns()
        next_cpu_poll=0.0
        def launch(n,lane):
            out=target/f"{n:02}"
            out.mkdir()
            local=self.scratch/f"{label}-{n:02}"
            require(not local.exists(),"fresh position scratch")
            save(out/"launch.json",{"ordinal":n,"lane":lane,"reserved_cpu_s":180,"time_ns":time.time_ns()})
            log=(out/"broker.log").open("xb")
            arg="parent" if binding["arm"]=="PARENT" else json.dumps(levels,separators=(",",":"))
            try:
                proc=subprocess.Popen([sys.executable,"-B",str(PK/"positions.py"),"--image",str(self.image),
                    "--scratch",str(local),"--output",str(out),"--levels",arg,"--ordinal",str(n),"--cpu",str(lane)],
                    stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            except Exception:
                log.close()
                raise
            live[proc.pid]=(proc,n,lane,log,local)
        try:
            while pending or live:
                stopped=(STUDY/"STOP").exists()
                while pending and available and not stopped:
                    launch(pending.pop(0),available.pop(0))
                    stopped=(STUDY/"STOP").exists()
                if not live:break
                poll_cpu=time.monotonic()>=next_cpu_poll
                if poll_cpu:next_cpu_poll=time.monotonic()+1
                for pid,item in list(live.items()):
                    proc,n,lane,log,local=item
                    ended,status,usage=os.wait4(pid,os.WNOHANG)
                    if not ended:
                        if poll_cpu and process_us(pid)>POSITION_US:stop("per-position CPU limit")
                        if (STUDY/"STOP").exists() and pid not in terminated:
                            # Send to this position's broker so its finally block preserves role outputs.
                            try:os.kill(pid,signal.SIGTERM)
                            except ProcessLookupError:pass
                            terminated.add(pid)
                        continue
                    proc.returncode=os.waitstatus_to_exitcode(status)
                    log.close()
                    cpu=int(round((usage.ru_utime+usage.ru_stime)*1_000_000))
                    out=target/f"{n:02}"
                    result=out/"return.json"
                    entered=(out/"native-admitted.json").is_file()
                    done=proc.returncode==0 and entered and result.is_file()
                    ret=read(result) if done else None
                    status_row={"ordinal":n,"native_entered":entered,"complete":done,"cpu_us":cpu,
                                "process_exit":proc.returncode,"interrupted":pid in terminated}
                    failure=out/"sink/failure.json"
                    if failure.exists():status_row["native_failure"]=read(failure)
                    if done:
                        saved_score=out/"sink/score.json"
                        status_row["raw_sha256"]=filehash(out/"sink/native.jsonl.gz")
                        require(status_row["raw_sha256"]==read(saved_score)["raw_sha256"],"copied native original")
                        status_row["score_sha256"]=filehash(saved_score)
                        status_row["access_sha256"]=filehash(out/"access.json")
                        status_row["native_entry_sha256"]=filehash(out/"native-admitted.json")
                    save(out/"physical-terminal.json",status_row)
                    returns[n]=(status_row,ret)
                    if not done or cpu>POSITION_US or (ret and ret["hard_violations"]):
                        stop("native position, resource, or hard constraint failure")
                    del live[pid]
                    available.append(lane)
                if live:time.sleep(.20)
        except Exception as exc:
            stop("slot broker "+type(exc).__name__)
            for pid in live:
                try:os.kill(pid,signal.SIGTERM)
                except ProcessLookupError:pass
            for pid,(proc,n,lane,log,local) in live.items():
                _,status,usage=os.wait4(pid,0);proc.returncode=os.waitstatus_to_exitcode(status);log.close()
                out=target/f"{n:02}"
                row={"ordinal":n,"native_entered":(out/"native-admitted.json").is_file(),"complete":False,
                     "cpu_us":int(round((usage.ru_utime+usage.ru_stime)*1_000_000)),
                     "process_exit":proc.returncode,"interrupted":True}
                if not (out/"physical-terminal.json").exists():save(out/"physical-terminal.json",row)
                returns[n]=(row,None)
        physical=[returns[n][0] for n in sorted(returns)]
        supervisor_us=(time.process_time_ns()-supervisor_start)//1000
        if physical:
            share,remainder=divmod(supervisor_us,len(physical))
            for index,p in enumerate(physical):
                p["subtree_cpu_us"]=p["cpu_us"]
                p["supervisor_share_us"]=share+int(index<remainder)
                p["cpu_us"]+=p["supervisor_share_us"]
                if p["cpu_us"]>POSITION_US:stop("charged position CPU cap")
        for p in physical:
            n=p["ordinal"]
            # Only actually entered native positions contribute to the facility denominator.
            # Pre-entry process failures and their cost are retained in the allocations and stop evidence.
            if p["native_entered"]:
                attempts.append(dict(ordinal=n,complete=p["complete"],cpu_us=p["cpu_us"]))
            if p["complete"]:
                rows.append(dict(returns[n][1],cpu_us=p["cpu_us"]))
        complete=len(rows)
        ok=(complete==len(attempts)==ROWS and not (STUDY/"STOP").exists())
        reason=None if ok else "stopped; see retained physical attempt ledger"
        status="COMPLETE" if ok else "PARTIAL" if complete else "FAILED"
        original=self.store.put({"binding":binding,"rows":rows})
        accounting=self.store.put({"binding":binding,"physical":physical,"unlaunched":pending,
               "elapsed_ns":time.monotonic_ns()-started_ns,"reserved_positions":ROWS})
        meter=self.store.put(signed(self.key,{"binding":binding,"attempts":attempts,"status":status,
                                             "reason":reason,"originals":original,"physical":accounting}))
        packet=None
        if ok:
            data={"scheduled":ROWS,"completed":ROWS,"status":"COMPLETE",
                  "L_sum_us":sum(microseconds(r["L"]) for r in rows),
                  "person_sum_us":sum(microseconds(r["person"]) for r in rows),
                  "hard_violations":sum(r["hard_violations"] for r in rows)}
            packet=signed(self.key,{"binding":binding,"data":data})
            require(data["hard_violations"]==0,"hard-constraint stop")
        save(target/"closed.json",{"meter":meter,"packet":self.store.put(packet) if packet else None,
             "started":len(attempts),"complete":complete,"cpu_us":sum(p["cpu_us"] for p in physical),
             "pre_entry_cpu_us":sum(p["cpu_us"] for p in physical if not p["native_entered"])})
        return meter,packet
