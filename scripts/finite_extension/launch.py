"""One scheduled slot. The outer process verifies a child and seals its exit."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import (ARMS, BASE, EMPTY, FIXTURE, HERE, OLD, PACK, PYTHON, REAL, ROOT,
                    counts_from_return, durable, empty_ledger, file_sha, manifest_data,
                    mkdir, need, read, recovery)
from analysis import inspect


def public_callback(unit, spec, directory):
    expected=spec["inputs"][unit["input"]]
    raw=Path(spec["input_root"])/expected["file"]
    need(file_sha(raw)==expected["sha256"],"REPLAY_IDENTITY")
    reference=read(raw)
    def callback(common, order):
        # The receipt is an external witness of fixture invocation, never a facility call.
        durable(directory/"fixture-entered.json",{"order":order,"action":unit["scenario"]})
        need(common==reference["condition"]["common"] and order==ARMS,"REPLAY_COMMON")
        scenario=unit["scenario"]
        if scenario=="callback-raises":raise RuntimeError("FIXTURE_CALLBACK_RAISED")
        value=deepcopy(reference["actual"])
        if scenario=="counts-missing":del value["counts"]["policy_calls"]
        elif scenario=="counts-negative":value["counts"]["policy_calls"]=-1
        elif scenario=="counts-bool":value["counts"]["policy_calls"]=True
        elif scenario=="counts-mismatch":value["counts"]["policy_calls"]+=1
        return value
    return callback


def error_data(error):
    return dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())


def worker(directory,slot,common,purpose,unit):
    ledger=empty_ledger()
    scenario=unit.get("scenario","none")
    raw=None;raised=None;accounted=False
    try:
        if purpose==FIXTURE:
            need(not any(k.startswith("aegis_dc") for k in sys.modules),"REAL_MODULE_IN_FIXTURE")
            callback=public_callback(unit,read(ROOT/(PACK+"witnesses.json")),directory)
        else:
            sys.path.insert(0,str(ROOT/"src"))
            from aegis_dc.london_treatments import run_condition as callback
        payload=deepcopy(common);order=list(ARMS)
        if scenario=="before-marker":raise OSError("FIXTURE_INTENT_WRITE_FAILED")
        binding=dict(slot=slot,job_id=os.environ["SLURM_JOB_ID"],purpose=purpose,
            manifest_sha256=read(directory/"slot.json")["manifest_sha256"],
            common_sha256=hashlib.sha256(json.dumps(common,sort_keys=True).encode()).hexdigest(),meaning="may dispatch once")
        durable(directory/"intent.json",binding)
        if scenario=="exit-after-intent":os._exit(73)
        ledger.update(callback_state="RAISED",calls_proved=1,unreturned_or_pending=1,internal_count_semantics="UNKNOWN_INTERNAL_COUNTS")
        try:
            raw=callback(payload,order=order)
        except BaseException as error:
            raised=error_data(error)
        else:
            ledger.update(callback_state="RETURNED",returned=1,unreturned_or_pending=0)
        # Independent accounting survives a later raw/summary/terminal write failure.
        try:
            if scenario=="raw-archive":raise OSError("FIXTURE_RAW_WRITE_FAILED")
            durable(directory/"raw.json",dict(binding=binding,actual=raw,exception=raised))
        finally:
            if ledger["returned"]:
                counts=counts_from_return(raw)
                if counts is None:ledger["returned_count_unknown"]=1
                else:ledger.update(known_reported_subtotal=counts,internal_count_semantics="KNOWN_REPORTED_SUBTOTAL")
            durable(directory/"accounting.json",ledger)
            accounted=True
        need(raised is None,"CALLBACK_RAISED")
        need(ledger["returned_count_unknown"]==0,"INVALID_INTERNAL_COUNTS")
        need(ledger["known_reported_subtotal"]["policy_calls"]<=60,"CONDITION_POLICY_CAP")
        raw_sha=file_sha(directory/"raw.json")
        durable(directory/"interpretation-started.json",dict(raw_sha256=raw_sha))
        summary=inspect(slot,common,raw)
        durable(directory/"summary.json",summary)
        need(not summary["fatal_findings"],"TECHNICAL_RETURN")
        durable(directory/"worker-complete.json",dict(raw_sha256=raw_sha,summary_sha256=file_sha(directory/"summary.json")))
        return 0
    except BaseException as error:
        if not accounted and not (directory/"accounting.json").exists():
            durable(directory/"accounting.json",ledger)
        durable(directory/"worker-error.json",error_data(error))
        return 1


def parse():
    p=argparse.ArgumentParser()
    for name in ("source","manifest","digest","index","directory","approval","approval_sha"):
        p.add_argument(name,type=int if name=="index" else str)
    p.add_argument("--worker",action="store_true")
    return p.parse_args()


def main():
    args=parse()
    directory=Path(args.directory).resolve()
    need(BASE in directory.parents,"OUTSIDE_ACTIVITY")
    if not args.worker:
        try:mkdir(directory)
        except FileExistsError:
            print("REFUSED_EXISTING",flush=True)
            return 1
    manifest=None;slot=None
    child_dispatched=False;worker_rc=None
    try:
        need(Path(args.source).resolve()==ROOT,"SOURCE_LOCATION")
        need(os.environ.get("SLURM_JOB_ID") and socket.gethostname().split(".")[0]!="mu01","SLURM_REQUIRED")
        need(os.environ.get("SLURM_CPUS_PER_TASK")=="1" and os.environ.get("SLURM_MEM_PER_NODE")=="1024","ALLOCATION")
        manifest,configs,units=manifest_data(args.manifest,args.digest,args.approval,args.approval_sha)
        index=args.index
        need(0<=index<len(manifest["order"]),"SLOT_INDEX")
        slot=manifest["order"][index];purpose=manifest["purpose"]
        need(directory==Path(manifest["output_root"])/slot,"OUTPUT_DIRECTORY")
        if manifest["route"]=="serial" or purpose==REAL:
            intent=read(directory.parent/("submit-"+slot+".json"))
            need(intent["manifest_sha256"]==args.digest and intent["index"]==index,"SUBMISSION_BINDING")
            if index:
                predecessor=read(directory.parent/("scheduler-"+manifest["order"][index-1]+".json"))
                need(predecessor["permit_next"] is True,"SUFFIX_STOP")
        unit=units.get(slot,{})
        if args.worker:
            owner=read(directory/"slot.json")
            need(owner["job_id"]==os.environ["SLURM_JOB_ID"] and owner["slot"]==slot and owner["manifest_sha256"]==args.digest,"OUTER_BINDING")
            # A second worker, even after an interrupted marker, cannot restart this slot.
            mkdir(directory/"worker-claim")
            return worker(directory,slot,configs[slot],purpose,unit)
        durable(directory/"slot.json",dict(slot=slot,index=index,job_id=os.environ["SLURM_JOB_ID"],
              source_revision=manifest["source_revision"],manifest_sha256=args.digest,
              untouched_suffix_if_stopped=manifest["order"][index+1:]))
        child_dispatched=True
        worker_rc=subprocess.run([PYTHON,"-I","-B","-u",str(HERE/"launch.py"),*sys.argv[1:],"--worker"]).returncode
        ledger=recovery(directory)
        need(worker_rc==0,"WORKER_EXIT_"+str(worker_rc))
        complete=read(directory/"worker-complete.json")
        need(complete["summary_sha256"]==file_sha(directory/"summary.json") and complete["raw_sha256"]==file_sha(directory/"raw.json"),"WORKER_RECORD_HASH")
        row=read(directory/"summary.json")
        need(ledger["callback_state"]=="RETURNED" and ledger["returned_count_unknown"]==0 and not row["fatal_findings"],"INCOMPLETE_RETURN")
        if unit.get("scenario")=="outer-exit":raise OSError("FIXTURE_OUTER_EXIT_FAILURE")
        status="PASS" if row["valid_comparison"] else "NONCOMPLIANT"
        durable(directory/"exit.json",dict(status=status,slot=slot,purpose=purpose,job_id=os.environ["SLURM_JOB_ID"],
                manifest_sha256=args.digest,worker_exit=worker_rc,accounting=ledger,files=complete,technical_stop=False))
        return 0
    except BaseException as error:
        if args.worker:
            print(json.dumps(error_data(error)),file=sys.stderr,flush=True)
            return 1
        ledger=recovery(directory) if child_dispatched else empty_ledger()
        if not child_dispatched:durable(directory/"accounting.json",ledger)
        status="ERROR" if child_dispatched else "REFUSED"
        failed=dict(status=status,slot=slot,purpose=manifest["purpose"] if manifest else None,
            job_id=os.environ.get("SLURM_JOB_ID"),manifest_sha256=args.digest,worker_exit=worker_rc,
            accounting=ledger,error=error_data(error),technical_stop=True)
        print(json.dumps(failed),file=sys.stderr,flush=True)
        durable(directory/"exit.json",failed)
        return 1


if __name__=="__main__":raise SystemExit(main())
