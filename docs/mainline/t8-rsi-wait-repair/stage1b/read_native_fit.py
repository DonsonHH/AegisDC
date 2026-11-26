"""Read sealed FIT evidence. Release only arm/slot aggregates, lineage, resource accounts, and stops."""

import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys


def read(p):return json.loads(Path(p).read_bytes())
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=True,separators=(",",":"),allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()


def require(v,why):
    if not v:raise ValueError(why)


def public_score(score):
    if score is None:return None
    n=score["fit_n"]
    require(n==48,"complete fixed FIT denominator")
    return {"n":n,"loss_sum_us":score["L_sum_us"],"person_sum_us":score["person_sum_us"],
            "L_mean_s":score["L_sum_us"]/(n*1e6),"person_mean_s":score["person_sum_us"]/(n*1e6),
            "hard_violations":score["hard_violations"]}


def cpu_seconds(text):
    days,sep,rest=text.partition("-")
    if not sep:days,rest="0",text
    value=Decimal(0)
    for s in rest.split(":"):value=60*value+Decimal(s)
    return Decimal(days)*86400+value


def accounting(study):
    names=["parent","parent-a2","pilot",*[f"r{r}{a}" for r in (2,3,4) for a in ("O","R")]]
    registered=[("input",{"job":"135576","reserved_cpu_s":240})]
    registered += [(n,read(study/"jobs"/(n+".json"))) for n in names if (study/"jobs"/(n+".json")).is_file()]
    ids=[v["job"] for _,v in registered]
    out=subprocess.check_output(["sacct","-P","-j",",".join(ids),
        "--format=JobID,State,ExitCode,ElapsedRaw,TimelimitRaw,AllocCPUS,TotalCPU,ReqMem,MaxRSS,NodeList"],text=True)
    tab={r["JobID"]:r for r in csv.DictReader(io.StringIO(out),delimiter="|")}
    rows=[]
    for n,r in registered:
        a=tab[r["job"]]; step=tab.get(r["job"]+".batch")
        require(a["State"] not in ("PENDING","RUNNING","COMPLETING"),"nonterminal allocation")
        if step:require(step["TotalCPU"]==a["TotalCPU"],"Slurm allocation/step CPU mismatch")
        reserve=int(a["TimelimitRaw"])*60*int(a["AllocCPUS"])
        require(reserve==r["reserved_cpu_s"],"planned and actual reservation")
        rows.append(dict(job=r["job"],stage=n,state=a["State"],exit=a["ExitCode"],cpus=int(a["AllocCPUS"]),
                         minutes=int(a["TimelimitRaw"]),reserved_cpu_s=reserve,wall_s=int(a["ElapsedRaw"]),
                         actual_cpu_s=str(cpu_seconds(a["TotalCPU"])),node=a["NodeList"]))
    require(len(rows)<=10 and sum(x["reserved_cpu_s"] for x in rows)<=285900,"total FIT ceilings")
    return rows,out


def make(study,package):
    r1=package/"r1"
    sys.path.insert(0,str(r1))
    from fit_evidence import authenticated, dereference
    from read_fit import read_case
    from jsonschema import Draft202012Validator

    evidence=study/"evidence";summary=read(evidence/"case.json")
    validator=Draft202012Validator(read(package/"r0/round-ledger.schema.json"))
    independently=read_case(evidence,summary,validator.validate)
    jobs,slurm=accounting(study)
    envelope=read(study/"execution-recovery.json")
    require(summary["frozen"]==envelope["frozen"] and summary["context"]==sha(canonical(envelope)) and
            sha(bytes.fromhex(summary["journal_key"]))==envelope["signer_fingerprints"]["journal"] and
            sha(bytes.fromhex(summary["score_key"]))==envelope["signer_fingerprints"]["evaluator"],"execution identity")
    parent=read(study/"baseline.json")["slot"]
    base_score=public_score(parent["fit_return"])
    report={"scope":"T8 shared-account development FIT only","execution_revision":envelope["release_revision"],
            "execution_envelope_sha256":sha(canonical(envelope)),"fit_batch_root":summary["frozen"]["fit_commitment"],
            "study_context":summary["context"],"receipt_signature_sha256":envelope["fit_receipt_signature_sha256"],
            "status":"STOPPED" if summary["result"]["stop"] else "DUAL_LOCKED_PENDING_REVIEW",
            "stop":summary["result"]["stop"],"jobs":jobs,
            "total_reserved_cpu_s":sum(j["reserved_cpu_s"] for j in jobs),
            "total_slurm_cpu_s":str(sum(Decimal(j["actual_cpu_s"]) for j in jobs)),
            "local_intake_comparison_cpu_s":"2.500",
            "baseline":{"id":parent["policy"]["id"],"scheduled":48,"started":parent["started_fit_n"],
                        "completed":parent["complete_fit_n"],"score":base_score},
            "arms":{},"private_round_record_heads":summary["result"]["round_heads"],
            "provenance":"Native originals and OS traces are retained privately. This readback verifies signed round and score "
                         "objects, original score/entry/access file hashes, rounding, counterfactual rosters and selected ancestry.",
            "dev_positions":0,"h2_access":0,"h3_originals_access":0}
    for a in ("O","R"):
        rows=[];selected_lineage=[];armcpu=0
        for i in range(1,5):
            rec=read(evidence/"rounds"/f"{a}-{i}.json")
            armcpu+=rec["accounting"]["actual_process_cpu_us"] or 0
            w=rec["next_witness"];inc=rec["incoming_witness"];sel=rec["selection"]
            selected=sel["accepted_slot"] if sel else None
            row={"round":i,"record_sha256":sha(canonical(rec)),"status":rec["status"],"selected_slot":selected,
                 "starting_incumbent":rec["before"]["incumbent"]["id"] if rec["before"] else None,
                 "resulting_incumbent":rec["after"]["incumbent"]["id"] if rec["after"] else None,
                 "program_before_sha256":rec["before"]["program_bytes"]["sha256"] if rec["before"] else None,
                 "program_after_sha256":rec["after"]["program_bytes"]["sha256"] if rec["after"] else None,
                 "rewrite_reason":rec["rewrite"]["reason"],"patch":rec["rewrite"]["patch"],
                 "credit":{k:v for k,v in (rec["rewrite"]["credit"] or {}).items() if k!="feedback_receipt"} or None,
                 "new_paid_slots":inc["actually_paid_new_slots"] if inc else [],
                 "next_roster_change":None if w is None else {k:w[k] for k in ("classification","before_policy_ids","after_policy_ids")},
                 "scheduled_positions":192,"started_positions":rec["accounting"]["started_positions"],
                 "completed_positions":rec["accounting"]["complete_positions"],"slots":[]}
            for s in rec["slots"]:
                n=s["slot"];ret={"slot":n,"status":s["status"],"id":s["policy"]["id"] if s["policy"] else None,
                    "levels":s["policy"]["levels"] if s["policy"] else None,"parent":s["parent_policy_id"],"cells":s["changed_cells"],
                    "reserved":s["policy"] is not None,"paid_full":s["fit_return"] is not None,
                    "membership_changed_and_paid":n in row["new_paid_slots"],"selected":selected==n,
                    "started":s["started_fit_n"],"completed":s["complete_fit_n"],"score":public_score(s["fit_return"])}
                row["slots"].append(ret)
                if ret["selected"]:selected_lineage.append({"round":i,"slot":n,"parent":ret["parent"],"id":ret["id"],
                                                            "newly_paid":ret["membership_changed_and_paid"]})
            rows.append(row)
        last=read(evidence/"rounds"/f"{a}-4.json")
        lock=None
        if summary["result"]["dual_lock"]:
            state=last["after"];box=dereference(evidence,state["paid_score_receipt"])
            data=authenticated(box,summary["score_key"])["data"]
            lock={"id":state["incumbent"]["id"],"levels":state["incumbent"]["levels"],
                  "descriptor_sha256":state["incumbent"]["bytes"]["sha256"],
                  "score":public_score({**data,"fit_n":data["completed"]})}
            require(not selected_lineage or lock["id"]==selected_lineage[-1]["id"],"selected ancestry reaches lock")
        report["arms"][a]={"rounds":rows,"lineage":selected_lineage,"locked":lock,
            "started":independently["arms"][a]["started"],"completed":independently["arms"][a]["completed"],
            "charged_arm_cpu_us":armcpu,"scheduled_positions":768}
    raw_positions=0;physical_starts=0;raw_bytes=0;chain=hashlib.sha256();signed_observations=0
    max_position_cpu=0;observed_violations=0
    for group in sorted((study/"positions").iterdir()) if (study/"positions").is_dir() else ():
        closed=read(group/"closed.json")
        meter=authenticated(dereference(evidence,closed["meter"]),summary["score_key"])
        physical=dereference(evidence,meter["physical"])["physical"]
        numeric=iter(dereference(evidence,meter["originals"])["rows"])
        for p in physical:
            dest=group/f"{p['ordinal']:02}";physical_starts+=int(p["native_entered"])
            max_position_cpu=max(max_position_cpu,p["cpu_us"])
            if p.get("native_failure",{}).get("hard_violation") is True:observed_violations+=1
            if not p["complete"]:continue
            original=next(numeric)
            score_bytes=(dest/"sink/score.json").read_bytes()
            score=json.loads(score_bytes,parse_float=str,parse_int=str)
            native_size=(dest/"sink/native.jsonl.gz").stat().st_size
            require(score["raw_sha256"]==p["raw_sha256"] and native_size>0 and
                    score["L"]==original["L"] and score["person"]==original["person"] and
                    sha(score_bytes)==p["score_sha256"] and
                    sha((dest/"native-admitted.json").read_bytes())==p["native_entry_sha256"] and
                    sha((dest/"access.json").read_bytes())==p["access_sha256"],"per-position evidence binding")
            for role,item in read(dest/"access.json").items():
                box={k:item[k] for k in ("payload","signer","signature")}
                require(sha(bytes.fromhex(box["signer"]))==envelope["signer_fingerprints"]["audit"],"published auditor")
                signed=authenticated(box,box["signer"])
                require(signed["role"]==role and signed["os_access"]["interpreter"]==1 and
                        item["observer"]["interpreter"]==1,"observer and audited role")
                signed_observations+=1
            chain.update(canonical([group.name,p["ordinal"],p["raw_sha256"],p["score_sha256"],p["access_sha256"],native_size])+b"\n")
            raw_bytes+=native_size
            raw_positions+=1
        require(next(numeric,None) is None,"all original scores consumed exactly once")
    require(physical_starts==parent["started_fit_n"]+sum(x["started"] for x in report["arms"].values()) and
            raw_positions==parent["complete_fit_n"]+sum(x["completed"] for x in report["arms"].values()),"all paid native totals")
    report.update(native_starts=physical_starts,scored_positions=raw_positions,rounds_verified=independently["rounds"],
                  signed_position_role_observations=signed_observations,native_gzip_bytes=raw_bytes,
                  retained_position_index_sha256=chain.hexdigest(),max_charged_position_cpu_us=max_position_cpu,
                  observed_native_hard_violations=observed_violations,
                  signed_events_verified=independently["events"],content_objects_verified=independently["objects"])
    if report["status"]=="DUAL_LOCKED_PENDING_REVIEW":
        require(physical_starts==raw_positions==1584 and max_position_cpu<=180_000_000 and
                observed_violations==0 and signed_observations==2*raw_positions,"complete safe dual lock")
    if (study/"jobs/batch-projection.json").exists():report["pilot_projection"]=read(study/"jobs/batch-projection.json")
    return report,slurm


def public_evidence(study, output):
    """Publish the eight actual round files and verifiable aggregate/structural objects only."""
    from fit_evidence import dereference
    evidence=study/"evidence";summary=read(evidence/"case.json")
    objects={}
    def keep(ref):
        if not ref:return
        obj=dereference(evidence,ref)
        objects[ref["sha256"]]=obj
    parent=read(study/"baseline.json")["slot"]
    keep(summary["result"]["shared"]);keep(summary["result"]["dual_lock"])
    if parent["fit_return"]:keep(parent["fit_return"]["receipt"])
    keep(parent["policy"]["bytes"])
    folder=output/"rounds";folder.mkdir()
    for a in ("O","R"):
        for n in range(1,5):
            name=f"{a}-{n}.json";raw=(evidence/"rounds"/name).read_bytes();rec=json.loads(raw)
            with (folder/name).open("xb") as f:f.write(raw)
            keep(rec["audit"]["record_seal"]);keep(rec["rewrite"]["patch_bytes"]);keep(rec["feedback"])
            if rec["selection"]:keep(rec["selection"]["rank_evidence"])
            for state in (rec["before"],rec["after"]):
                if state:
                    for k in ("program_bytes","seen_set_bytes","paid_score_receipt"):keep(state[k])
                    keep(state["incumbent"]["bytes"])
            for slot in rec["slots"]:
                if slot["policy"]:keep(slot["policy"]["bytes"])
                if slot["fit_return"]:keep(slot["fit_return"]["receipt"])
            if rec["next_witness"]:
                w=rec["next_witness"]
                for k in ("common_inputs","before_roster","after_roster"):keep(w[k])
    proof={"context":summary["context"],"journal_public":summary["journal_key"],"score_public":summary["score_key"],
           "shared":summary["result"]["shared"],"dual_lock":summary["result"]["dual_lock"],"objects":objects}
    with (output/"public-proof.json").open("xb") as f:f.write(canonical(proof)+b"\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study",type=Path,required=True);parser.add_argument("--package",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();report,rows=make(args.study,args.package)
    args.output.mkdir(exist_ok=False)
    public_evidence(args.study,args.output)
    with (args.output/"results.json").open("xb") as f:f.write(canonical(report)+b"\n")
    with (args.output/"sacct.psv").open("x",newline="") as f:f.write(rows)
    print("VERIFIED",report["status"],report["native_starts"],report["scored_positions"],"native positions;",report["rounds_verified"],"rounds")
