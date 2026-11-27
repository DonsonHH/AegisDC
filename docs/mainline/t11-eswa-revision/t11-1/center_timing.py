"""Verify historic development histories and measure the unchanged public worker only."""
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import re
import time

from operations import ORIGINAL, center_rows, cpu, file_sha, need, now, packed, read, save, signature


def history(key,unit,original_score):
    folder=ORIGINAL/"positions"/("dev-"+key+"-V_COST")/"a1"
    raw=folder/"original.jsonl.gz"
    need(file_sha(raw)==unit["raw"]==original_score["raw"],"original trajectory hash: "+key)
    with gzip.open(raw,"rb") as stream:
        record=json.loads(stream.readline())
    meta=record["metadata"]
    actual=meta["policy_public_decisions"]; proposals=meta["v3_proposals"]
    audit=meta["policy_computation_audit"]
    need(len(actual)==len(proposals)==len(audit)==61,"full original decision history: "+key)
    need([r["view"]["time"] for r in actual]==list(range(0,3601,60)),"original public clock")
    for step,proposal in zip(actual,proposals,strict=True):
        need(signature(step["view"])==proposal["view"],"archived public view hash")
    need(signature([[r["at"],r["view"],r["proposal"]] for r in proposals])==unit["IPC"],"original IPC identity")
    public=meta["inputs"]["dispatch_program"]["public"]
    need(signature(public)==read(folder/"native-entry.json")["public_program"],"original public static bundle")
    return public,actual,proposals,audit


def historical_point(record):
    if type(record.get("ipc_wall_ns")) is int and record["ipc_wall_ns"]>=0:
        return record["ipc_wall_ns"]
    start=record.get("request_start_monotonic_ns"); end=record.get("reply_parsed_monotonic_ns")
    if type(start) is int and type(end) is int and 0<=start<=end:
        return end-start
    return None


def inspect_archives(activity):
    rows,units=center_rows(activity)
    plan=read(ORIGINAL/"source"/"docs"/"mainline"/"t4c-action-cost-v3"/"freeze.json")
    origins={key:group for group,slots in plan["groups"].items() for key,role in slots if role=="V_COST" and group.startswith("new")}
    schema=Counter(); searchable_logs=0;clock_hits=0; matched=0; unexpected=[]
    pattern=re.compile(rb"perf_counter|monotonic_ns|wall_ns|cpu_ns|dispatch_latency|decision_latency|timing_ns",re.I)
    for key,unit in units.items():
        _,events,proposals,audit=history(key,unit,rows[key])
        for event,proposal,record in zip(events,proposals,audit,strict=True):
            fields={"event":sorted(event),"proposal":sorted(proposal),"audit":sorted(record)}
            schema[packed(fields).decode()]+=1
            values=[v for r in (record,proposal,event) if (v:=historical_point(r)) is not None]
            if values:
                need(len(set(values))==1,"inconsistent historic timing channels")
                matched+=1
            elif any(pattern.search(k.encode()) for r in (record,proposal,event) for k in r):
                unexpected.append(key)
        position=ORIGINAL/"positions"/("dev-"+key+"-V_COST")/"a1"
        logs=[position/"worker.stderr",ORIGINAL/"batches"/origins[key]/"a1"/(key+"-V_COST.log")]
        for f in logs:
            need(f.is_file(),"missing historic process log "+f.name)
            searchable_logs+=1
            clock_hits+=bool(pattern.search(f.read_bytes()))
    status=("HISTORICAL_RTT_AVAILABLE" if matched==4392 else "NO_PER_DECISION_TIMING" if matched==0 and
            not unexpected and not clock_hits else "PARTIAL_OR_UNCLASSIFIED")
    return dict(status=status,eligible_rows=72,frames=4392,native_original_hashes_verified=72,
                event_schema_counts=dict(schema),complete_wall_fields=matched,unit_logs_read=searchable_logs,
                timer_log_hits=clock_hits,whole_position_elapsed_present=True,simulation_clock_is_not_runtime=True)


def measure(activity,manifest):
    from runner import PublicProcess
    need(read(activity/"qualification"/"acceptance.json")["pass"] is True,"timing before qualification")
    directory=activity/"center-timing";directory.mkdir()
    inspection=read(activity/"qualification"/"historical-fields.json")
    mode={"HISTORICAL_RTT_AVAILABLE":"archived_online","NO_PER_DECISION_TIMING":"isolated_worker_replay"}.get(inspection["status"])
    rows,units=center_rows(activity);keys=read(activity/"references"/"original-dev-manifest.json")["order"]
    total=0;validated_count=0;started_cpu=cpu()
    try:
        need(mode is not None,"partial or unclassified historic timing requires readback review")
        with (directory/"measurements.jsonl").open("xb") as output,(directory/"startups.jsonl").open("xb") as startups:
            for key in keys:
                public,frames,proposals,audit=history(key,units[key],rows[key])
                folder=directory/key;folder.mkdir()
                worker=None
                try:
                    if mode=="isolated_worker_replay":
                        begin=time.perf_counter_ns()
                        worker=PublicProcess(ORIGINAL/"public-only","V_COST",folder,None,center=True)
                        worker.start(public)
                        startups.write(packed(dict(key=key,worker_startup_ns=time.perf_counter_ns()-begin))+b"\n")
                        startups.flush()
                    for item,proposal,record in zip(frames,proposals,audit,strict=True):
                        public_view=item["view"]
                        if worker is not None:
                            need(total<4392,"worker replay ceiling")
                            total+=1
                            answer,timing=worker.decision(public_view)
                            need(answer["request"]==proposal["requested"] and signature(answer)==proposal["proposal"],
                                 "center replay proposal identity: "+key+"/"+str(public_view["time"]))
                        else:
                            wall=next(v for rec in (record,proposal,item) if (v:=historical_point(rec)) is not None)
                            timing=dict(ipc_wall_ns=wall,reason=item["decision"]["rationale"]["reason"])
                        output.write(packed(dict(key=key,time=public_view["time"],validated=True,mode=mode,**timing))+b"\n")
                        validated_count+=1
                    output.flush()
                finally:
                    if worker is not None:need(worker.close()==0,"center timing worker exit")
        need(validated_count==72*61 and total in (0,4392),"timing denominator")
        save(directory/"status.json",dict(mode=mode,validated=True,rows=72,frames=validated_count,
             worker_calls=total,facility_calls=0,scores_created=0,job=os.environ["SLURM_JOB_ID"],
             receipt_manifest=manifest,measurements_sha256=file_sha(directory/"measurements.jsonl"),
             startups_sha256=file_sha(directory/"startups.jsonl"),worker_internal_cpu="unavailable for byte-identical archived worker",
             process_cpu_s=cpu()-started_cpu,utc=now()))
    except Exception as exc:
        save(directory/"status.json",dict(mode="UNAVAILABLE",attempted_mode=mode,validated=False,
             frames_validated=validated_count,worker_calls=total,facility_calls=0,scores_created=0,
             category=type(exc).__name__,message=str(exc),job=os.environ["SLURM_JOB_ID"],process_cpu_s=cpu()-started_cpu,utc=now()))
        raise
