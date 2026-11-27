"""Independent remote readback of new scores, trace/decision identities and return paths."""
import csv
import gzip
import json
from pathlib import Path

from operations import ORIGINAL, file_sha, need, now, packed, read, save, signature


def finalize(activity):
    public=activity/"analysis"
    road=read(activity/"registration.json")
    baseline=read(activity/"references"/"baseline-freeze.json")
    inputs=read(activity/"references"/"original-dev-manifest.json")
    settled=read(activity/"science-settled.json")
    index=[]
    verified=0;diagnostics=0
    for spec in (road["groups"][label] for label in road["order"] if road["groups"][label]["kind"]=="science"):
        batch=spec["name"];role=spec["role"]
        submitted=activity/"submissions"/(batch+".json")
        submitted_job=read(submitted)["job"] if submitted.is_file() else ""
        for key in spec["keys"]:
            unit=activity/"positions"/role/key
            start=unit/"entry.json"; native=unit/"native-entry.json"; score=unit/"score.json"; failure=unit/"failure.json"
            timing=unit/"timing.jsonl"; raw=unit/"original.jsonl.gz"
            record={"batch":batch,"key":key,"role":role,"input_sha256":inputs["files"][key],"job":submitted_job,
                    "entered":int(start.exists()),"native_calls":int(native.exists()),"score_sha256":"","raw_sha256":"",
                    "timing_sha256":"","timing_rows":0,"failure_sha256":"","as_run_diagnostic_sha256":"","status":"UNEXECUTED_SUFFIX"}
            if start.is_file():
                e=read(start);need((e["key"],e["role"],e["input_sha256"],e["job"])==(key,role,record["input_sha256"],submitted_job),
                                    "retained entry identity")
                record["status"]="PRE_NATIVE_INCOMPLETE"
            if native.is_file():
                n=read(native);need(start.is_file() and all(n[k]==v for k,v in e.items()) and
                                    n["pid"]!=n["worker_pid"],"retained native process/entry")
                record["status"]="ENTERED_WITHOUT_COMPLETE_SCORE"
            if timing.is_file():
                stamps=[]
                for line in timing.read_bytes().splitlines():
                    try:stamps.append(json.loads(line)["time"])
                    except (ValueError,KeyError):break
                record.update(timing_sha256=file_sha(timing),timing_rows=len(stamps))
            observed={}
            if failure.is_file():
                failed=read(failure)
                record.update(failure_sha256=file_sha(failure),status=failed["category"])
                observed=failed.get("observed") or {}
            if raw.is_file():record["raw_sha256"]=file_sha(raw)
            full_diagnostic=(not score.is_file() and observed.get("clocks")==61 and observed.get("key")==key
                             and observed.get("role")==role and all(field in observed for field in
                             ("entry","raw_sha256","timing_sha256","IPC","L","U","person","tool","fee","runtime")))
            if score.is_file() or full_diagnostic:
                s=read(score) if score.is_file() else observed
                need(native.is_file() and (unit/"native-return.json").is_file() and s["input_sha256"]==record["input_sha256"]
                     and s["key"]==key and s["role"]==role and s["entry"]==e,"score identity")
                need((not score.is_file() or s["conformant"] is True) and s["clocks"]==61 and s["runtime"]==baseline["native_runtime"] and
                     s["raw_sha256"]==record["raw_sha256"] and s["timing_sha256"]==record["timing_sha256"] and
                     stamps==list(range(0,3601,60)),"score/trace/timing accounting")
                with gzip.open(raw,"rb") as f: header=json.loads(f.readline())["metadata"]
                decisions=header["policy_public_decisions"]; proposals=header["v3_proposals"]
                need(len(decisions)==len(proposals)==61 and header["code_identity"]["source_tree_sha256"]==s["runtime"]
                     and n["public_program"]==signature(header["inputs"]["dispatch_program"]["public"]),"recorded original")
                need(all(signature(d["view"])==z["view"] and d["view"]["time"]==z["at"]
                         for d,z in zip(decisions,proposals,strict=True)),"recorded public history")
                transcript=signature([[z["at"],z["view"],z["proposal"]] for z in proposals])
                need(transcript==s["IPC"],"scored IPC")
                with (unit/"public-call-attempts.jsonl").open("rb") as stream:
                    dispatched=[json.loads(line) for line in stream]
                need(dispatched==[{"time":z["at"],"view_sha256":z["view"]} for z in proposals],"pre-call accounting")
                case=read(ORIGINAL/"dev-inputs"/(key+".json"))
                need(header["source_config"]==case["native"]["scenario"] and
                     header["inputs"]["dispatch_program"]==case["native"]["dispatch_program"] and
                     header["v3_received_maintenance"]==case["maintenance"],"original condition and actual execution")
                if score.is_file():
                    record.update(score_sha256=file_sha(score),status="COMPLETE_COMPLIANT")
                    verified+=1
                else:
                    record["as_run_diagnostic_sha256"]=signature(observed);diagnostics+=1
            index.append(record)
    need(len(index)==720 and len({(q["role"],q["key"]) for q in index})==720,"full denominator")
    with (public/"native-evidence-index.tsv").open("x",encoding="utf8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(index[0]),delimiter="\t",lineterminator="\n")
        writer.writeheader();writer.writerows(index)
    extras={}
    for name in ("source-manifest.json","registration.json","qualification/identity.json","qualification/historical-fields.json",
                 "qualification/public-witness.json","qualification/acceptance.json","pilot-projection.json","STOP.json",
                 "science-settled.json","center-timing/status.json"):
        path=activity/name
        if path.is_file(): extras[name]=file_sha(path)
    batch_index={label:file_sha(activity/"batches"/label/"terminal.json") for label in settled["allocations"]
                 if (activity/"batches"/label/"terminal.json").is_file()}
    save(public/"native-readback-receipt.json",dict(utc=now(),registered=720,committed_scores=verified,
         native_calls=sum(r["native_calls"] for r in index),index_sha256=file_sha(public/"native-evidence-index.tsv"),
         metadata_and_clocks_checked=verified+diagnostics,as_run_diagnostics_checked=diagnostics,
         original_bytes_hashed=sum(bool(r["raw_sha256"]) for r in index),
         anchors=extras,batch_receipts=batch_index,center_scores_recomputed=0,
         sealed_h2_h3_accesses=[0,0]))
