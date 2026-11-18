"""Finish the interrupted bookkeeping from its two already-written originals."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import BASE, OLD, PACK, ROOT, RUNTIME, STUDY_OUTPUT, file_sha, need, read
from seal_preparation import receipt, save


def recover(snapshot,snapshot_sha,output):
    need(os.environ.get("SLURM_JOB_ID"),"SLURM_REQUIRED")
    output.mkdir(exist_ok=False)
    prior=BASE/"review-01/output"
    pins={"execution-manifest.json":"fa5478798a47d9b37c05e25775337e59f4ac0e2425d495e393852f9dd28164d0",
          "path-results.json":"66f6dc8facb6ea81cfbb3ab3ef9f89ebb24793886090b44320ab351f1dca145a"}
    for f,sha in pins.items():need(file_sha(prior/f)==sha,"RECOVERY_IDENTITY:"+f)
    m=read(prior/"execution-manifest.json");paths=read(prior/"path-results.json")
    transfer=read(ROOT/(PACK+"static-transfer.json"))
    need(paths["passed"] and paths["checked_units"]==15 and paths["surrogate_calls"]==9 and paths["real_runner_calls"]==0,"SAVED_PATH_RESULTS")
    need(file_sha(snapshot)==snapshot_sha,"SCHEDULER_SNAPSHOT")
    jobs={}
    for line in snapshot.read_text().splitlines():
        job,state,rc,elapsed,cpu,n,mem,tres,limit=line.strip().split("|")[:9]
        jobs[job]=dict(state=state,exit=rc,elapsed_seconds=int(elapsed),total_cpu=cpu,allocated_cpus=int(n),memory=mem,tres=tres,time_limit=limit)
    roles={"134472":"static-01","134473":"red-01","134476":"bind-01","134477":"path-01","134478":"W11","134479":"W12","134480":"review-01"}
    need(set(jobs)==set(roles),"FROZEN_JOB_SET")
    for job,role in roles.items():
        j=jobs[job];j["role"]=role
        expected_rc={"red-01":"2:0","W12":"1:0","review-01":"1:0"}.get(role,"0:0")
        need(j["exit"]==expected_rc and j["state"]==("COMPLETED" if expected_rc=="0:0" else "FAILED"),"JOB_STATE:"+job)
        need(j["allocated_cpus"]==1 and j["memory"]=="1G" and j["time_limit"]=="00:02:00","SLURM_RESOURCES:"+job)
    attempt_files={}
    for tag in ("static-01","red-01","bind-01","path-01","review-01"):
        attempt_files[tag]=receipt(BASE/tag,["job.slurm","stdout.log","stderr.log","exit-status"])
    serial=BASE/"witness-serial-01"
    for slot in ("W11","W12"):
        jid=read(serial/("job-"+slot+".json"))["job_id"]
        names=["submit-"+slot+".json","job-"+slot+".json","scheduler-"+slot+".json","observed-"+slot+".json",
               slot+"-"+jid+".out",slot+"-"+jid+".err",slot+"/exit.json",slot+"/raw.json",slot+"/accounting.json"]
        attempt_files[slot]=receipt(serial,names)
    need(not (serial/"W13").exists() and not (serial/"submit-W13.json").exists(),"SUFFIX_SUBMITTED")
    need(not STUDY_OUTPUT.exists(),"STUDY_OUTPUT_EXISTS")
    green=read(BASE/"source-cea3317e/staged.json")
    release=read(BASE/"source-24cc268d/staged.json")
    for f in RUNTIME:
        need(m["runtime"][f]==green["files"][f]["sha256"]==release["files"][f]["sha256"]==file_sha(ROOT/f),"RUNTIME_DRIFT:"+f)
    need(m["data_sha256"]==transfer["input_sha256"]==file_sha(ROOT/(PACK+"conditions.json")),"INPUT_IDENTITY")
    need(transfer["passed"] and not transfer["unresolved_slots"],"TRANSFER")
    summary=dict(schema="finite-synthetic-extension-preparation-result-v1",status="DELIVERED_FOR_FINAL_PRE_EXECUTION_REVIEW",
        activity="执行前冻结的有限合成机制扩展验证（同账号、非独立保管）",baseline="5e944066",scope_revision="c036536d",
        independent_custody="UNMET_NOT_WAIVED",user_and_Codex_can_read_full_static_inputs=True,
        fixed_core=m["core_revision"],scientific_comparison="I/D primary; P background; full H20 and separately reported service/cost",
        versions=dict(rule_freeze="c036536d",before_first_static_generation="eedece41",static_inputs="7522c157",
            actual_launch_and_static_correction=green["revision"],transfer_and_engineering_manifests="0c67469f",
            study_manifest_source=release["revision"],accounting_recovery_source=read(ROOT/"staged.json")["revision"]),
        counts=dict(static_slots=35,selected=35,group_backgrounds=transfer["counts"]["backgrounds"],slot_checks=transfer["counts"]["slot_checks"],
            public_canonical_compared=transfer["rows"][0]["disclosed_compared"],path_units=15,observed_surrogate_entries=9,
            crash_intent_with_unknown_operational_call_count=1,real_runner_calls=0,real_facility_calls=0,real_policy_calls=0,real_score_calls=0,new_research_runs=0),
        scientific_scope="Analytic transfer of the specified relationships to the 35 frozen inputs for review. No new scientific output exists.",
        preparation_budget=dict(jobs_used_including_recovery=8,job_cap=8,reserved_cpu_seconds=960,cap_reserved_cpu_seconds=960,
            per_job=dict(cpus=1,memory_MiB=1024,seconds=120),peak_concurrency=1),
        research_budget_if_authorized=m["selected_launch"]|m["budget"],jobs_before_this_receipt=jobs,final_receipt_job_id=os.environ["SLURM_JOB_ID"],
        failures_retained=[dict(job="134473",kind="Expected missing-worker red",facility_calls=0),
            dict(job="134479",kind="Injected outer exit failure W12; original summary retained, final predicates null; W13 not submitted",facility_calls=0),
            dict(job="134480",kind="Unexpected receipt-only failure: compute node could not connect to sacct after saving path-results and manifest",
                 recovery="Same two original files reused; login-node terminal observations; current allocation completes remaining file accounting only",additional_callbacks=0)],
        evidence=dict(private_root=str(BASE),hashes_of_original_outputs=pins,old_public_return_source=read(ROOT/(PACK+"witnesses.json"))["inputs"],
            attempts=attempt_files,group_path_results=file_sha(BASE/"path-01/output/suite.json"),serial_terminal=file_sha(serial/"terminal.json"),
            prior_receipt_job_exit=1,login_sacct_sha256=snapshot_sha,qualified_runtime_equals_study_runtime=m["runtime"],
            corrected_detailed_static_audit=transfer["corrected_detailed_audit_sha256"]),
        accounting_note="The W11/W12 immediate terminal observations displayed 16? in ReqMem. Settled login-node sacct reports 1G and the submitted requests and compute environment agree.",
        disclosure="Prepared conditions and arithmetic are visible to the same account. No new keys, private authorization, independent custody or unseen-outcome claim.",
        study_output_root_exists=False,activation_record_created=False,execution_authorized=False,
        remaining_technical_static_slots=[],remaining=["User review of fixed static transfer, selected path scope and exact manifest","Separate explicit authorization to run this exact manifest"],
        independent_confirmation_satisfied=False,independent_confirmation_waived=False,full_Q11_R2_R3=False)
    save(output/"result.json",summary)
    print(json.dumps(dict(status=summary["status"],counts=summary["counts"],recovery_new_callbacks=0)))


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("snapshot",type=Path);parser.add_argument("snapshot_sha");parser.add_argument("output",type=Path)
    a=parser.parse_args();recover(a.snapshot,a.snapshot_sha,a.output)
