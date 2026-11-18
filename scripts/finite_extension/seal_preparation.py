"""Bind the review copy to saved files and Slurm outcomes, with zero callbacks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import BASE, FIXTURE, OLD, PACK, REAL, ROOT, RUNTIME, STUDY_OUTPUT, file_sha, need, read
from check_path import reconcile
from make_manifest import construct


def save(path,value):
    with path.open("x",encoding="utf-8") as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2,allow_nan=False)
        handle.write("\n")


def receipt(directory,files):
    return {name:dict(sha256=file_sha(directory/name),bytes=(directory/name).stat().st_size) for name in files}


def accounting(ids):
    command=["sacct","-X","-n","-P","-j",",".join(ids),"-o","JobID,State,ExitCode,ElapsedRaw,TotalCPU,AllocCPUS,ReqMem,AllocTRES,Timelimit"]
    lines=subprocess.check_output(command,text=True).splitlines()
    return {k:dict(state=st,exit=rc,elapsed_seconds=int(elapsed),total_cpu=cpu,allocated_cpus=int(n),
                   memory=mem,tres=tres,time_limit=limit)
            for k,st,rc,elapsed,cpu,n,mem,tres,limit in (line.strip().split("|")[:9] for line in lines if line.strip())}


def finish(output):
    need(os.environ.get("SLURM_JOB_ID"),"SLURM_REQUIRED")
    output.mkdir(exist_ok=False)
    frozen=BASE/"bind-01/output"
    suite_path=BASE/"path-01/output/suite.json"
    serial=BASE/"witness-serial-01"
    need((BASE/"dispatch-01/exit-status").read_text().strip()=="1","EXPECTED_DISPATCH_FAILURE")
    need(reconcile(frozen/"serial.json",suite_path,output/"path-results.json"),"PATH_RECONCILIATION")
    paths=read(output/"path-results.json")
    need(len(paths["rows"])==15 and all(u["passed"] for u in paths["rows"]),"INCOMPLETE_WITNESSES")
    # This is an identity-only comparison with the actual path job source tree.
    green=read(BASE/"source-cea3317e/staged.json")
    current=read(ROOT/"staged.json")
    runtime_match={f:green["files"][f]["sha256"]==current["files"][f]["sha256"]==file_sha(ROOT/f)
                   and file_sha(BASE/"source-cea3317e"/f)==file_sha(ROOT/f) for f in RUNTIME}
    need(all(runtime_match.values()),"RUNTIME_DRIFT")
    old=read(ROOT/(OLD+"acceptance-20261117.json"))
    for path,sha in __import__("london_confirmation_entry").CORE_HASHES.items():
        need(current["files"][path]["sha256"]==sha,"CORE_CHANGED")
    conditions=read(ROOT/(PACK+"conditions.json"))
    transfer=read(ROOT/(PACK+"static-transfer.json"))
    need(transfer["passed"] and not transfer["unresolved_slots"] and len(conditions["order"])==35,"STATIC_HANDOFF")
    need(file_sha(ROOT/(PACK+"conditions.json"))==transfer["input_sha256"]==file_sha(BASE/"static-01/output/conditions.json"),"CONDITION_IDENTITY")
    for src,dest in [("suite.json","launch-fixture-suite.json"),("serial.json","launch-fixture-serial.json"),
                      ("W02.json","launch-fixture-reject-legacy.json"),("W15.json","launch-fixture-reject-review.json"),
                      ("static-transfer.json","static-transfer.json"),("qualification.md","qualification.md")]:
        need(file_sha(frozen/src)==file_sha(ROOT/(PACK+dest)),"FROZEN_ARTIFACT_DRIFT:"+dest)
    nominal=construct("study",STUDY_OUTPUT)
    nominal["selected_launch"]={"submitter":"scripts/finite_extension/submit.py","batch":"scripts/finite_extension/slot.slurm",
        "entry":"scripts/finite_extension/launch.py","partition":"cu","jobs_serial":35,"concurrency":1,
        "requeue":False,"max_reserved_cpu_seconds":2100,"max_policy_calls_per_condition":60,"max_policy_calls_per_arm":20,
        "physical_scope":"one London PRE synthetic instance, one repair, one aggregate service",
        "version_identity":{"core":old["fixed_core"],"entry_last_qualified":green["revision"],"staged_source":current["revision"]}}
    need(not STUDY_OUTPUT.exists(),"RESEARCH_OUTPUT_ROOT_ALREADY_EXISTS")
    save(output/"execution-manifest.json",nominal)
    job_roles={"134472":"static-01","134473":"red-01","134476":"bind-01","134477":"path-01",
               read(serial/"job-W11.json")["job_id"]:"W11",read(serial/"job-W12.json")["job_id"]:"W12"}
    account=accounting(list(job_roles))
    need(set(account)==set(job_roles),"MISSING_JOB_ACCOUNTING")
    for job,role in job_roles.items():
        a=account[job];a["role"]=role
        expected="FAILED" if role in ("red-01","W12") else "COMPLETED"
        need(a["state"]==expected and a["allocated_cpus"]==1 and a["time_limit"]=="00:02:00","SLURM_TERMINAL:"+job)
    attempt_files={}
    for tag in ("static-01","red-01","bind-01","path-01"):
        attempt_files[tag]=receipt(BASE/tag,["job.slurm","stdout.log","stderr.log","exit-status"])
    for slot in ("W11","W12"):
        jid=read(serial/("job-"+slot+".json"))["job_id"]
        attempt_files[slot]=receipt(serial,["submit-"+slot+".json","job-"+slot+".json","scheduler-"+slot+".json","observed-"+slot+".json",slot+"-"+jid+".out",slot+"-"+jid+".err",slot+"/exit.json",slot+"/raw.json",slot+"/accounting.json"])
    assert not (serial/"W13").exists() and not (serial/"submit-W13.json").exists()
    reviewed_files={name:file_sha(ROOT/(PACK+name)) for name in ["protocol.md","selection.json","witnesses.json","freeze-addendum.json","preflight-review.md","conditions.json","static-audit.json","static-transfer.json","qualification.md"]}
    summary=dict(schema="finite-synthetic-extension-preparation-result-v1",status="DELIVERED_FOR_FINAL_PRE_EXECUTION_REVIEW",
        authority="2026-11-18 user scope revision",activity="执行前冻结的有限合成机制扩展验证（同账号、非独立保管）",baseline="5e944066",
        independent_custody="UNMET_NOT_WAIVED",user_and_Codex_can_read_full_static_inputs=True,
        scientific_core=nominal["core_revision"],rule_freeze="c036536d",pre_generation_author_and_addendum="eedece41",
        static_input_commit="7522c157",static_correction_execution=green["revision"],corrected_transfer_and_fixture_manifest_freeze="0c67469f",
        launch_qualification_source=green["revision"],review_manifest_source=current["revision"],identical_runtime_files=runtime_match,
        counts=dict(static_slots=35,selected=35,templates_examined=transfer["counts"]["backgrounds"],candidate_slot_checks=transfer["counts"]["slot_checks"],
                    public_canonical_compared=transfer["rows"][0]["disclosed_compared"],witness_units=paths["checked_units"],
                    surrogate_callback_entries_witnessed=paths["surrogate_calls"],unresolved_crash_intents=1,
                    real_runner_calls=0,real_facility_calls=0,real_policy_calls=0,real_score_calls=0,research_runs=0),
        budget=dict(max_preparation_jobs=8,max_reserved_cpu_seconds=960,used_including_this_job=7,reserved_cpu_seconds=840,concurrency=1,per_job=dict(cpu=1,MiB=1024,seconds=120)),
        jobs_before_this_receipt=account,final_receipt_job=os.environ["SLURM_JOB_ID"],
        scheduler_note="Final sacct is authoritative for requested memory. Immediate observations of W11/W12 displayed 16? before accounting settled; input command and compute environment also bind 1 GiB.",
        two_retained_negative_jobs=["134473 expected missing worker before implementation","W12 deliberate outer exit failure"],
        witness_interpretation="9 observed surrogate invocations, including historical-record and exception callbacks. W10 has intent-only evidence at recovery. Reconciliation makes no callbacks.",
        evidence=dict(private_activity_root=str(BASE),attempt_files=attempt_files,suite_sha256=file_sha(suite_path),
            serial_terminal_sha256=file_sha(serial/"terminal.json"),detailed_path_receipt_sha256=file_sha(output/"path-results.json"),
            study_manifest_sha256=file_sha(output/"execution-manifest.json"),durable_static_artifacts=reviewed_files),
        research_execution_authorized=False,activation_record_created=False,review_scope="Static analytic transfer and selected path qualification. Future actual stages and scientific findings are pending.",
        original_independent_confirmation_complete=False,full_Q11_R2_R3=False,unresolved_static_slots=transfer["unresolved_slots"],
        remaining=["User review of static transfer and scope","Separate user authorization bound to this exact execution manifest before any research submission"])
    need(paths["surrogate_calls"]==9,"FIXTURE_CALL_RECONCILIATION")
    save(output/"result.json",summary)
    print(json.dumps(dict(status=summary["status"],counts=summary["counts"],study_manifest_sha256=summary["evidence"]["study_manifest_sha256"])))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("output",type=Path)
    finish(p.parse_args().output)
