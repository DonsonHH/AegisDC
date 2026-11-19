"""Archive the source and existing-reference evidence before the first research ticket."""
import argparse
import hashlib
import os
import sys
import traceback
from pathlib import Path
from record_io import MANIFEST, APPROVAL, RUN_SOURCE, MANIFEST_SHA, APPROVAL_SHA, RESOURCE_V, ARMS, DIMS
from record_io import digest, evidence_summary, read, require, save, sha


def closure(run, policy):
    for frame in run["public_trace"]:
        v=frame["view"]
        if policy.verified(v):
            parent=policy.execution_receipt(v)
            proof=[x for x in v["records"] if x.get("status")=="VERIFIED_FOR_TARGET"
                   and x.get("value")=="PASS" and x.get("parent_execution_id")==parent["execution_id"]
                   and x.get("config_epoch")==parent["target_config_epoch"]]
            return dict(kind="BOUND_PASS", at=frame["time"], records=proof, execution_receipt=parent)
    if run["public_trace"] and run["stop"]["reason"]=="NO_ACTION_CURRENT_SCOPE":
        view=run["public_trace"][-1]["view"]; facts=policy.Evidence(view)
        records=[facts.current[a] for a in policy.READS if facts.negative(a)]
        if records:
            return dict(kind="VALID_NEGATIVE_AT_STOP",at=run["stop"]["time"],records=records)
    return dict(kind="OPEN",at=run["stop"]["time"])


def check(source,stage):
    result=dict(status="PREFLIGHT_STARTED",job=os.environ["SLURM_JOB_ID"],source_files={},originals={},
                original_rows={},masks={},tickets_at_preflight=0,model_calls=0,scorer_calls=0)
    try:
        allocation=(stage/"job-start/allocation").read_text().split()
        result["allocation_sha256"]=sha(stage/"job-start/allocation")
        require("NumCPUs=1" in allocation and "NumTasks=1" in allocation and "Requeue=0" in allocation
                and "TimeLimit=00:15:00" in allocation
                and any(x in allocation for x in ("MinMemoryNode=2G","MinMemoryNode=2048M")),
                "Allocation differs from one serial 1 CPU / 2 GiB / 900 s job")
        tres=[x.split("=",1)[1] for x in allocation if x.startswith(("TRES=","AllocTRES=","ReqTRES="))]
        require(tres and all(int(f.rsplit("=",1)[-1])==0 for v in tres for f in v.split(",")
                             if "gpu" in f.lower()),"Nonzero GPU allocation or missing TRES")
        require(sha(source/MANIFEST)==MANIFEST_SHA and sha(source/APPROVAL)==APPROVAL_SHA,"Original manifest or grant bytes differ")
        m=read(source/MANIFEST); grant=read(source/APPROVAL)
        require(grant["authority"]=="EXPLICIT_USER_ONE_STUDY" and grant["manifest_sha256"]==MANIFEST_SHA
                and grant["execution_revision"]==m["execution_revision"]==RUN_SOURCE
                and grant["qualification_sha256"]==m["qualification_sha256"]
                and grant["output_root"]==m["output_root"],"Approval binding mismatch")
        require(not Path(m["output_root"]).exists(),"Exclusive output root already exists")
        result.update(manifest_sha256=MANIFEST_SHA,approval_sha256=APPROVAL_SHA,output_root=m["output_root"],
                      interpreter_sha256=sha(sys.executable),execution_revision=RUN_SOURCE)
        require(result["interpreter_sha256"]==m["interpreter_sha256"],"Interpreter drift")
        for f,h in m["files"].items():
            result["source_files"][f]=sha(source/f)
            require(result["source_files"][f]==h,"Pinned file mismatch: "+f)
        require(sha(source/grant["qualification_acceptance"])==grant["qualification_acceptance_sha256"],"Acceptance bytes differ")
        proof=read(source/m["source_identity_file"]); quali=read(source/m["qualification_file"])
        sys.path.insert(0,str(source/"scripts"))
        from ordinary_v2_identity import verify_source
        verify_source(source,proof)
        require(quali["status"]=="PASS" and quali["execution_revision"]==RUN_SOURCE and quali["job_id"]=="134587"
                and quali["source_manifest_sha256"]==sha(source/m["source_identity_file"])
                and not (quali["failures"] or quali["not_completed"] or quali["unresolved_episodes"] or quali["unknown_episode_counts"]),
                "Qualification terminal binding")
        sys.path.insert(0,str(source/"src"))
        from aegis_dc.ordinary import policy
        for panel in m["panels"]:
            label=panel["name"]
            conditions=read(source/panel["input"])["conditions"]
            old=read(source/panel["results"])
            index={x["condition_id"]:x for x in old.get("records",[])}
            info={}; closed_by_key={}; outside=[]
            result["originals"][label]=info
            result["original_rows"][label]=closed_by_key
            for c,row in zip(conditions,old["rows"],strict=True):
                key=c["condition_id"]
                require(key==row.get("condition_id",row.get("slot")),"Original panel order drift")
                if label=="dev19":
                    item=index[key];path=Path(m["dev_raw_root"])/item["file"];expected=item["sha256"]
                else:
                    path=Path(row["raw_path"]);expected=row["raw_sha256"]
                actual_hash=sha(path)
                info[key]=dict(path=str(path),bytes=path.stat().st_size,sha256=actual_hash,condition_digest=digest(c["common"]))
                require(actual_hash==expected,"Original raw hash mismatch: "+label+"."+key)
                previous=read(path)["actual"]["arms"]; arms={}
                for arm in ARMS:
                    run=previous[arm]; original=row["arms"][arm]
                    require(run["arm"]==arm and run["final_audit"]["original_input"]==c["common"],"Reference instance mismatch")
                    a=evidence_summary(run)
                    require(a["z"]==[original["L"],original["U"],original["costs"]["person_seconds"],original["costs"]["tool_seconds"]]
                            and a["complete"] and set(a["violations"])<=RESOURCE_V,"Invalid saved score: "+label+"."+key+"."+arm)
                    a["closure_evidence"]=closure(run,policy)
                    a["closed"]=a["closure_evidence"]["kind"]!="OPEN"
                    if run["stop"]["reason"]=="NO_ACTION_CURRENT_SCOPE" or a["stage"]=="VERIFIED":
                        require(a["closed"] and (a["stage"]!="VERIFIED" or a["closure_evidence"]["kind"]=="BOUND_PASS"),
                                "Original close lacks matching PRE evidence: "+label+"."+key+"/"+arm+"; raw "+actual_hash)
                    arms[arm]=a
                in_mask=all(not a["violations"] for a in arms.values())
                require(in_mask==row.get("valid_comparison",row.get("eligible")),"Reference mask mismatch")
                if not in_mask:outside.append(key)
                closed_by_key[key]=dict(in_mask=in_mask,arms=arms)
            require(len(conditions)==panel["conditions"] and outside==panel["excluded_from_numeric_gain"]
                    and len(conditions)-len(outside)==panel["mask"],"Frozen panel denominator drift")
            result["masks"][label]=dict(rows=len(conditions),eligible=len(conditions)-len(outside),outside=outside)
        result["status"]="PASS_BEFORE_FIRST_TICKET"
    except BaseException:
        result.update(status="PREFLIGHT_STOP",error=traceback.format_exc(),entry_invocations=0,retries=0)
        raise
    finally:
        save(stage/"preflight.json",result)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("source",type=Path);parser.add_argument("stage",type=Path)
    a=parser.parse_args();check(a.source.resolve(),a.stage.resolve())
