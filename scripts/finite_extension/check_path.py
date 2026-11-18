"""Exercise the selected process entry using only frozen replay/exception witnesses."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import BASE, COUNT_KEYS, EMPTY, HERE, OLD, PACK, ROOT, durable, file_sha, mkdir, need, read

SPEC=read(ROOT/(PACK+"witnesses.json"))
CASES={c["id"]:c for c in SPEC["cases"]}


def tree_hashes(folder):
    return {str(p.relative_to(folder)):file_sha(p) for p in folder.rglob("*") if p.is_file()}


def tally(original):
    return {key:sum(row["kind"]==kind for row in original["actual"]["calls"]) for kind,key in COUNT_KEYS.items()}


def observation(slot,directory,rc):
    unit=CASES[slot];expected=unit["expected"]
    exit_info=read(directory/"exit.json");ledger=exit_info["accounting"]
    raw_path=directory/"raw.json";entry_marker=directory/"fixture-entered.json"
    original=read(Path(SPEC["input_root"])/SPEC["inputs"][unit["input"]]["file"])
    wanted_counts=tally(original) if expected["internal_count_semantics"]=="KNOWN_REPORTED_SUBTOTAL" else EMPTY
    checks={k:ledger.get(k)==expected[k] for k in ("callback_state","calls_proved","returned","unreturned_or_pending","returned_count_unknown","internal_count_semantics")}
    checks.update(status=exit_info["status"]==expected["status"],exit_code=rc==expected["exit_code"],
        raw_saved=raw_path.is_file()==expected["raw_saved"],reported_subtotal=ledger["known_reported_subtotal"]==wanted_counts,
        fixture_invoked=entry_marker.is_file()==(slot not in ("W02","W03","W10","W15")),
        no_budget_released=ledger["retry_budget_released"] is False)
    if slot in ("W01","W11","W12"):
        checks["raw_bound_before_interpretation"]=read(directory/"interpretation-started.json")["raw_sha256"]==file_sha(raw_path)
        checks["old_return_preserved"]=read(raw_path)["actual"]==original["actual"]
    if slot in ("W04","W05","W06","W07","W08","W09"):
        checks["business_interpretations_zero"]=not (directory/"interpretation-started.json").exists()
    if slot=="W04":
        error=read(raw_path)["exception"]
        checks["raised_verbatim"]=error["type"]=="RuntimeError" and error["message"]=="FIXTURE_CALLBACK_RAISED"
    if slot in ("W05","W06","W07","W08"):
        got=read(raw_path)["actual"];target=original["actual"]
        if slot=="W05":del target["counts"]["policy_calls"]
        elif slot=="W06":target["counts"]["policy_calls"]=-1
        elif slot=="W07":target["counts"]["policy_calls"]=True
        else:target["counts"]["policy_calls"]+=1
        checks["only_frozen_mutation"]=json.dumps(got,sort_keys=True)==json.dumps(target,sort_keys=True)
    if slot in ("W02","W15"):
        checks["refusal_reason"]=exit_info["error"]["message"]==("PURPOSE_REJECTED" if slot=="W02" else "REVIEW_REQUIRED")
    if slot=="W03":checks["no_intent"]=not (directory/"intent.json").exists()
    if slot=="W10":checks["unresolved_intent"]=(directory/"intent.json").is_file() and exit_info["worker_exit"]==73 and not (directory/"accounting.json").exists()
    return dict(slot=slot,expected=expected,actual_exit=rc,status=exit_info["status"],
                ledger=ledger,fixture_callbacks=int(entry_marker.is_file()),checks=checks,
                passed=all(checks.values()),exit_sha256=file_sha(directory/"exit.json"),
                files=tree_hashes(directory))


def suite(manifest_path,output):
    m=read(manifest_path);root=Path(m["output_root"]);mkdir(root);mkdir(output)
    results=[]
    for index,slot in enumerate(m["order"]):
        current=manifest_path if slot not in ("W02","W15") else manifest_path.parent/(slot+".json")
        directory=root/("W01" if slot=="W14" else slot)
        if slot=="W14":before=tree_hashes(directory)
        cmd=["bash",str(HERE/"slot.slurm"),str(ROOT),str(current),file_sha(current),str(index),str(directory),"-","-"]
        proc=subprocess.run(cmd,capture_output=True,text=True)
        durable(output/(slot+"-process.json"),dict(command=cmd,returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
        if slot=="W14":
            checks=dict(exit_code=proc.returncode==1,refused_existing="REFUSED_EXISTING" in proc.stdout,all_bytes_preserved=before==tree_hashes(directory))
            row=dict(slot=slot,passed=all(checks.values()),checks=checks,fixture_callbacks=0,status="REFUSED_EXISTING")
        else:row=observation(slot,directory,proc.returncode)
        results.append(row);durable(output/(slot+".json"),row)
        if not row["passed"]:break
    value=dict(passed=len(results)==len(m["order"]) and all(r["passed"] for r in results),rows=results,
               denominator=m["order"],job_id=os.environ["SLURM_JOB_ID"],manifest_sha256=file_sha(manifest_path),
               fixture_callbacks=sum(r["fixture_callbacks"] for r in results),real_runner_calls=0,real_plant_calls=0,real_policy_calls=0,real_scorer_calls=0)
    durable(output/"suite.json",value)
    return value["passed"]


def reconcile(manifest_path,suite_path,output):
    m=read(manifest_path);out=Path(m["output_root"])
    terminal=read(out/"terminal.json")
    serial=[]
    for slot in ("W11","W12"):
        scheduled=read(out/("scheduler-"+slot+".json"))
        status=scheduled["row"]["scheduler"]
        rc=int(status["exit_code"].split(":")[0])
        row=observation(slot,out/slot,rc)
        row["scheduler"]=status;row["scheduler_record_sha256"]=file_sha(out/("scheduler-"+slot+".json"))
        row["checks"]["scheduler_state"]=status["state"]==("COMPLETED" if slot=="W11" else "FAILED")
        row["checks"]["continue_only_after_terminal"]=scheduled["permit_next"]==(slot=="W11")
        row["passed"]=all(row["checks"].values());serial.append(row)
    suffix=(terminal["status"]=="STOPPED" and [r["status"] for r in terminal["rows"]]==["NONCOMPLIANT","TECHNICAL_STOP","NOT_SUBMITTED"]
            and not (out/"W13").exists() and not (out/"submit-W13.json").exists())
    serial.append(dict(slot="W13",passed=suffix,status="NOT_SUBMITTED",fixture_callbacks=0))
    suite_data=read(suite_path)
    # Fresh read of individual case records and immutable raw/ledger hashes.
    for row in suite_data["rows"]:
        need(row==read(suite_path.parent/(row["slot"]+".json")),"SAVED_CHECK_RECORD")
        if "files" in row:
            suite_root=Path(read(suite_path.parent.parent/"suite-manifest-copy.json")["output_root"])
            need(row["files"]==tree_hashes(suite_root/row["slot"]),"SAVED_RAW_IDENTITY")
    rows=suite_data["rows"]+serial
    result=dict(passed=suite_data["passed"] and all(r["passed"] for r in serial),declared_units=15,
                checked_units=len(rows),recheck_job_id=os.environ["SLURM_JOB_ID"],recheck_runner_calls=0,
                real_runner_calls=0,real_plant_calls=0,real_policy_calls=0,real_scorer_calls=0,
                surrogate_calls=sum(r["fixture_callbacks"] for r in rows),controller_terminal_sha256=file_sha(out/"terminal.json"),
                rows=[{k:v for k,v in r.items() if k not in ("files","expected")} for r in sorted(rows,key=lambda x:x["slot"])])
    durable(output,result)
    return result["passed"]


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["suite","reconcile"]);p.add_argument("manifest",type=Path);p.add_argument("output",type=Path);p.add_argument("--suite",type=Path)
    args=p.parse_args();need(os.environ.get("SLURM_JOB_ID"),"SLURM_REQUIRED")
    if args.mode=="suite":
        durable(args.output.parent/"suite-manifest-copy.json",read(args.manifest))
        passed=suite(args.manifest,args.output)
    else:passed=reconcile(args.manifest,args.suite,args.output)
    print(json.dumps(dict(mode=args.mode,passed=passed,real_calls=0)))
    raise SystemExit(0 if passed else 1)
