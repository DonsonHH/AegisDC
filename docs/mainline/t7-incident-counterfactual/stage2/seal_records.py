"""Index the saved private originals. This command has no simulator or seed dependency."""

import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path("/share/home/renly/renly-patrol-rsi/mainline/T7-incident-counterfactual-stage2-v1")


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def need(value, name):
    if not value:
        raise ValueError(str(name))


def packed(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def check_wire(path, last):
    with path.open("rb") as f:
        static=json.loads(next(f))["send"]["public"]
        ready=json.loads(next(f))["return"]
        need(ready=={"ready":True,"role":"V_COST"} and len(static["clock"])==61,path)
        picked=None
        for t in range(0,3601,60):
            view=json.loads(next(f))["send"]["view"]
            answer=json.loads(next(f))["return"]
            need(t==view["time"],"clock in native IPC")
            if last and t==last["time"]:
                need(hashlib.sha256(packed(view)).hexdigest()==last["view_sha256"],"last legal public frame")
                req=answer["request"]
                picked={"time":t,"proposal":req["task"] if req else "WAIT","admitted":last["actual"],
                        "reason":answer["rationale"]["reason"], "posterior_records":answer["rationale"]["posterior"]["groups"]["records"]}
        need(json.loads(next(f))=={"worker_exit":0} and not f.readline(),path)
        need(last is None or picked is not None,"matched last legal tick")
        return picked


def main():
    positions={};group_files={};spot=[];dutch_public={};logs={}
    for group in ("pilot","batch"):
        folder=ROOT/group
        term=read(folder/"terminal.json")
        for n in ("start.json","terminal.json","saved.json"):
            group_files[group+"/"+n]=sha(folder/n)
        for k,role in term["positions"]:
            name=k+"-"+role; d=folder/name
            if name not in term["result_sha256"]:
                positions[name]={"status":"ENTERED_NO_SCORE" if name in term["entries"] else "NO_ENTRY"}
                continue
            result=read(d/"result.json");pins=result["files_sha256"]
            need(sha(d/"result.json")==term["result_sha256"][name],name+" returned digest")
            sizes={n:(d/n).stat().st_size for n in pins}
            for n in ("entry.json","score.json","worker.stderr"):
                need(sha(d/n)==pins[n],name+"/"+n)
            score=read(d/"score.json");entry=read(d/"entry.json")
            need(all(result[m]==score[m] for m in ("L","U","person","tool","fee")) and
                 all(entry[m]==result[m] for m in ("key","role","job","input_sha256","bundle_sha256","input_publication")),name)
            pos={"status":result["status"],"directory":group+"/"+name,
                 "files_sha256":pins|{"result.json":term["result_sha256"][name]},"bytes":sizes}
            if k in ("5-01","6-60"):
                need(sha(d/"original.jsonl.gz")==pins["original.jsonl.gz"] and sha(d/"ipc.jsonl")==pins["ipc.jsonl"],name+" spot hashes")
                with gzip.open(d/"original.jsonl.gz","rb") as f:
                    meta=json.loads(next(f))["metadata"]
                ticks=meta["policy_public_decisions"]
                need(len(ticks)==61 and meta["code_identity"]["source_tree_sha256"]==score["runtime"] and
                     [[t["view"]["time"],t["decision"]["request"]["task"]] for t in ticks if t["decision"]["request"]]==score["requests"],
                     name+" spot native metadata")
                spot.append(name)
            win=result["dutch_window"]
            if win and win["fault"] is not None:
                lo,hi=win["fault"],win["restored"]
                area=math.fsum(max(0,min(hi,b)-max(lo,a))*max(0,dem-y)/dem for a,b,dem,y in score["curve"] if dem>0)
                effect=next((w["at"] for w in score["writes"] if w["task"]=="NR::A" and w["outcome"]=="APPLIED"),None)
                need(abs(area-win["transfer_loss"])<=1e-9 and effect==win["effective_NR"],name+" transfer record")
            if k.startswith("6-") and role=="V_COST":
                need(sha(d/"ipc.jsonl")==pins["ipc.jsonl"],name+" IPC")
                last=win["legal_NR_ticks"][-1] if win and win.get("legal_NR_ticks") else None
                picked=check_wire(d/"ipc.jsonl",last)
                if picked:
                    actual=dict(score["requests"]).get(last["time"],"WAIT")
                    need(actual==picked["admitted"],name+" selected vs admitted action")
                dutch_public[k]=picked
            positions[name]=pos
        for log in sorted(folder.glob("*.log")):
            logs[str(log.relative_to(ROOT))]={"bytes":log.stat().st_size,"sha256":sha(log)}
        job=term["job"]
        for n in (f"t7s2{group}-{job}.err",f"t7s2{group}-{job}.out",group+".submit-once",group+".sbatch",group+"-accounting.psv"):
            path=ROOT/"jobs"/n;group_files["jobs/"+n]=sha(path)
    for f in ("source.tar","score-release.json","author-entry.json","batch-budget.json",
              "pre-score/input-freeze.json","pre-score/within-panel.json","pre-score/input-manifest.json",
              "pre-score/overlap-ledger.json","batch/analysis.json","batch/mechanisms.json"):
        group_files[f]=sha(ROOT/f)
    data={"root":str(ROOT),"positions":positions,"group_files":group_files,"row_logs":logs,
          "raw_and_ipc_rehashed_at_close":spot,"dutch_V_public_last_legal_tick":dutch_public,
          "verification_scope":"All scored native files and IPC were hashed when saved on compute nodes. At sealing, original byte sizes and every returned result, entry and score were checked. Full native/IPC bytes were separately rehashed for the two fixed boundary rows (all five arms); every Dutch V_COST wire transcript was also checked."}
    target=ROOT/"originals.json"
    with target.open("xb") as stream:stream.write(packed(data)+b"\n")
    print("Private index:",len(positions),"registered positions;",len(spot),"full boundary trace checks;",
          len(dutch_public),"Dutch V_COST IPC checks; SHA-256",sha(target))


if __name__=="__main__": main()
