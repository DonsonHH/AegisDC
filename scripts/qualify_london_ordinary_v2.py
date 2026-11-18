"""The sole frozen public-engineering qualification. Never loads either research panel."""
import argparse
import hashlib
import json
import os
import socket
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QDIR = ROOT/"docs/mainline/review-gated/R5/ordinary-v2-qualification"
FREEZE = "c32f00e7ba6c1b5cdce651ea03b2e702e1faaa25"
PROTOCOL = "4182f423bba954fce680a5268e4111a6b58bd989"
CORE = "1c0b0c47a5742321a3524a5b16843775cc224e3e"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def preflight(manifest, expected_sha):
    if sha(manifest)!=expected_sha:
        raise ValueError("Engineering source manifest SHA mismatch")
    m=read(manifest)
    if (m["purpose"],m["freeze_revision"],m["protocol_revision"],m["core_revision"])!=(
            "PUBLIC_ENGINEERING_ONLY",FREEZE,PROTOCOL,CORE):
        raise ValueError("Unrecognized qualification or engineering purpose")
    if sha(sys.executable)!=m["interpreter_sha256"]:
        raise ValueError("Interpreter mismatch")
    for filename,meta in m["files"].items():
        if sha(ROOT/filename)!=meta["sha256"]:
            raise ValueError("Source/fixture drift: "+filename)
    frozen=read(QDIR/"freeze.json")
    for filename,expected in frozen["sha256"].items():
        if sha(QDIR/filename)!=expected:
            raise ValueError("Frozen artifact drift: "+filename)
    f=read(QDIR/"fixtures.json");e=read(QDIR/"expected.json")
    kinds=("episodes","interfaces","feedback","ledger")
    if (f["purpose"]!="PUBLIC_ENGINEERING_ONLY" or len(f["episodes"])!=6 or len(f["interfaces"])>48
            or len(f["feedback"])!=13 or f["budget"]["retries"]!=0):
        raise ValueError("Engineering fixture scope changed")
    for kind in kinds:
        ids=[x["id"] for x in f[kind]]
        if len(ids)!=len(set(ids)) or set(ids)!=set(e[kind]):
            raise ValueError("Missing or duplicate fixture identity: "+kind)
    return m,f,e


def run(manifest,expected_sha,out):
    from aegis_dc.ordinary.archive import Journal,save,digest
    from aegis_dc.ordinary.episode import run_isolated
    from ordinary_v2_fixture_io import interface,episode_projection
    from ordinary_v2_witnesses import feedback_case,ledger_case,differences
    out.mkdir(parents=True,exist_ok=False)
    journal=Journal(out/"units.jsonl")
    status=dict(status="PRECHECK",job_id=os.environ["SLURM_JOB_ID"],machine=socket.gethostname(),
                source_manifest_sha256=expected_sha,fixture_revision=FREEZE,units=[],failures=[],
                full_calls=dict(constructor=0,plant=0,policy=0,request=0,scorer=0),
                facility_started=0,facility_returned=0,unknown_episode_counts=0,unresolved_episodes=[],
                counters=dict(interfaces=0,feedback=0,ledger_operations=0),research_episodes=0,
                real_research_tickets=0,qualification_attempt=1)
    actuals={};raws={};all_ids=[]
    def check(kind,identifier,value,expected):
        errs=differences(value,expected)
        record=dict(category=kind,id=identifier,actual=value,expected=expected,
                    assertions=[{"field":key,"pass":key not in errs} for key in sorted(value.keys()|expected.keys())],
                    mismatch=errs)
        journal.event("unit_return",**record)
        status["units"].append(record)
        if errs:
            status["failures"].append(dict(id=identifier,fields=errs))
    try:
        m,f,e=preflight(manifest,expected_sha)
        status.update(status="RUNNING",execution_revision=m["execution_revision"],input_files=read(QDIR/"freeze.json")["sha256"])
        all_ids=[x["id"] for bucket in ("episodes","interfaces","feedback","ledger") for x in f[bucket]]+["K-prefix"]
        for case in f["episodes"]:
            key=case["id"]
            journal.event("unit_intent",category="episodes",input=case)
            status["facility_started"]+=1
            status["unresolved_episodes"].append(key)
            destination=out/"episodes"/key
            try:
                raw=run_isolated(f["conditions"][case["condition"]],case["descriptor"],f["purpose"],key,destination)
            except BaseException:
                # The outer worker and all proven internal starts have separate accounts.
                end=destination/"terminal.json"
                if end.is_file():
                    receipt=read(end)
                    for k,n in receipt.get("counts",{}).items():
                        status["full_calls"][k]+=n
                    if not receipt.get("pending") and receipt.get("status")=="ERROR":
                        status["unresolved_episodes"].remove(key)
                status["unknown_episode_counts"]+=1
                raise
            status["facility_returned"]+=1
            status["unresolved_episodes"].remove(key)
            for k,n in raw["counts"].items():
                status["full_calls"][k]+=n
            raws[key]=raw;actuals[key]=episode_projection(raw)
            check("episodes",key,actuals[key],e["episodes"][key])
        for pair in e["pairs"]:
            a,b=raws[pair["left"]],raws[pair["right"]]
            ticks=range(pair["through_tick"]+1)
            def prefix(raw):
                frames={x["time"]:x for x in raw["run"]["public_trace"]}
                return [{k:frames[t][k] for k in pair["identical"]} for t in ticks]
            check("pair","K-prefix",{"same_public_prefix":prefix(a)==prefix(b),"ticks":len(ticks)},
                  {"same_public_prefix":True,"ticks":13})
        for category in ("interfaces","feedback","ledger"):
            for case in f[category]:
                key=case["id"]
                journal.event("unit_intent",category=category,input=case)
                if category=="interfaces":
                    status["counters"]["interfaces"]+=1
                    value=interface(f,case,journal)
                elif category=="feedback":
                    status["counters"]["feedback"]+=1
                    value=feedback_case(f,case,journal)
                else:
                    operations=6 if case["op"]=="three_rounds" else 2 if case["op"]=="repeat_ticket" else 1
                    status["counters"]["ledger_operations"]+=operations
                    if status["counters"]["ledger_operations"]>f["budget"]["ledger_operations"]:
                        raise ValueError("Ledger fixture cap exceeded")
                    value=ledger_case(f,case,out,journal,actuals,e["episodes"])
                check(category,key,value,e[category][key])
        if any(sha(ROOT/name)!=v["sha256"] for name,v in m["files"].items()):
            raise ValueError("Execution source changed")
        status["status"]="PASS" if not status["failures"] else "EXPECTED_ACTUAL_DIFFERENCES"
    except BaseException:
        status["status"]="TECHNICAL_STOP"
        status["error"]=traceback.format_exc()
    finally:
        status["not_completed"]=[k for k in all_ids if k not in {x["id"] for x in status["units"]}]
        status["assertions"]=sum(len(x["assertions"]) for x in status["units"])
        status["archive_index"]={}
        for path in sorted((out/"episodes").glob("*/*")) if (out/"episodes").exists() else ():
            if path.is_file():
                status["archive_index"][str(path.relative_to(out))]=dict(bytes=path.stat().st_size,sha256=sha(path))
        journal.event("qualification_terminal",status=status["status"],calls=status["full_calls"])
        journal.close()
        status["unit_log_sha256"]=sha(out/"units.jsonl")
        save(out/"qualification.json",status)
    print(json.dumps({k:status[k] for k in ("status","full_calls","counters","failures","not_completed")},ensure_ascii=False))
    return 0 if status["status"]=="PASS" else 1


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,required=True);p.add_argument("--manifest-sha",required=True)
    p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or socket.gethostname().split(".")[0]=="mu01":
        raise SystemExit("Remote Slurm allocation required")
    # Authenticate the full staged bundle before importing the implementation.
    preflight(a.manifest,a.manifest_sha)
    sys.path.insert(0,str(ROOT/"src"))
    return run(a.manifest,a.manifest_sha,a.output)


if __name__=="__main__":
    raise SystemExit(main())
