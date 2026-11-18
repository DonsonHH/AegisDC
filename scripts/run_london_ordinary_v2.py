"""Future research front door. A review manifest alone cannot authorize a run."""
import argparse
import hashlib
import json
import os
import socket
import sys
from pathlib import Path
from ordinary_v2_identity import verify_source, REQUIRED

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("docs/mainline/review-gated")
PROTOCOL = "4182f423bba954fce680a5268e4111a6b58bd989"
CORE = "1c0b0c47a5742321a3524a5b16843775cc224e3e"
DEV_INPUT = BASE/"R3/formal-protocol-v1/development-inputs.json"
EXT_INPUT = BASE/"R4/finite-extension-v1/conditions.json"
DEV_SCORES = BASE/"R4/public-development-v1/terminal.json"
EXT_SCORES = BASE/"R4/finite-extension-study-v1/paired-results.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def baseline(manifest):
    """Only read previously scored raw evidence; never reconstruct a missing score."""
    from aegis_dc.ordinary import policy
    from aegis_dc.ordinary.episode import RESOURCE
    from aegis_dc.ordinary.selection import Panels
    configs = {}
    refs = {arm:{} for arm in ("I","D","P")}
    for panel,input_file,score_file in (("dev19",DEV_INPUT,DEV_SCORES),("ext35",EXT_INPUT,EXT_SCORES)):
        frozen,ledger=read(ROOT/input_file),read(ROOT/score_file)
        records={r["condition_id"]:r for r in ledger.get("records",[])}
        for c,row in zip(frozen["conditions"],ledger["rows"],strict=True):
            ident=c["condition_id"];key=panel+"."+ident
            require(ident==row.get("condition_id",row.get("slot")), "Baseline row drift")
            configs[key]=c["common"]
            if panel=="dev19":
                meta=records[ident]
                path=Path(manifest["dev_raw_root"])/meta["file"]
                expected=meta["sha256"]
            else:
                path=Path(row["raw_path"]);expected=row["raw_sha256"]
            require(sha(path)==expected,"Missing/mismatched historical raw")
            actual=read(path)["actual"]
            for arm in refs:
                run=actual["arms"][arm];score=run["score"]; old=row["arms"][arm]
                require(run["final_audit"]["original_input"]==c["common"] and run["arm"]==arm,"Baseline instance")
                z=[score[k] for k in ("L","U","person_seconds","tool_seconds")]
                require(z==[old["L"],old["U"],old["costs"]["person_seconds"],old["costs"]["tool_seconds"]],"Baseline cost identity")
                violations={k for k,v in score["hard_constraints"].items() if not v}
                require(violations<=RESOURCE and score["trace_status"]=="COMPLETE","Historical technical failure")
                frames=run["public_trace"]
                closed=any(policy.verified(f["view"]) for f in frames)
                if frames and run["stop"]["reason"]=="NO_ACTION_CURRENT_SCOPE":
                    facts=policy.Evidence(frames[-1]["view"])
                    closed |= any(facts.negative(a) for a in policy.READS)
                refs[arm][key]=dict(complete=True,z=z,closed=closed,violations=sorted(violations))
    panels=Panels(configs,refs)
    require(len(configs)==54 and set(configs)-panels.mask=={"dev19.C09b","ext35.B03"},"Frozen reference mask")
    return configs,panels


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--manifest-sha",required=True)
    parser.add_argument("--approval",type=Path,required=True)
    parser.add_argument("--approval-sha",required=True)
    args=parser.parse_args()
    require(sha(args.manifest)==args.manifest_sha and sha(args.approval)==args.approval_sha,"Launch identity drift")
    m=read(args.manifest);grant=read(args.approval)
    require(m["purpose"]=="ORDINARY_V2_STUDY_REVIEW" and m["qualification_status"]=="PASS"
            and m["protocol_revision"]==PROTOCOL and m["core_revision"]==CORE,"Wrong scope or qualification")
    require(grant.get("authority")=="EXPLICIT_USER_ONE_STUDY" and grant.get("manifest_sha256")==args.manifest_sha
            and grant.get("execution_revision")==m["execution_revision"]
            and grant.get("qualification_sha256")==m["qualification_sha256"]
            and grant.get("output_root")==m["output_root"],"Separate version-bound study approval required")
    require(os.environ.get("SLURM_JOB_ID") and socket.gethostname().split(".")[0]!="mu01","Compute allocation required")
    require(sha(sys.executable)==m["interpreter_sha256"],"Interpreter drift")
    require(REQUIRED | {f.as_posix() for f in (DEV_INPUT,EXT_INPUT,DEV_SCORES,EXT_SCORES)}
            <= set(m["files"]),"Missing mandatory study identities")
    for f,v in m["files"].items():
        require(sha(ROOT/f)==v,"Pinned file drift: "+f)
    require(sha(ROOT/m["qualification_file"])==m["qualification_sha256"],"Qualification receipt drift")
    receipt=read(ROOT/m["qualification_file"])
    source_path=ROOT/m["source_identity_file"]
    require(receipt["status"]=="PASS" and not receipt["failures"] and not receipt["not_completed"]
            and receipt["execution_revision"]==m["execution_revision"]
            and receipt["facility_started"]==receipt["facility_returned"]==6
            and receipt["unknown_episode_counts"]==0 and not receipt["unresolved_episodes"]
            and receipt["source_manifest_sha256"]==sha(source_path),"Passing selected execution evidence required")
    source=read(source_path)
    require(source["execution_revision"]==m["execution_revision"],"Different qualified runtime")
    verify_source(ROOT,source)
    sys.path.insert(0,str(ROOT/"src"))
    from aegis_dc.ordinary import policy
    from aegis_dc.ordinary.archive import digest,save
    from aegis_dc.ordinary.episode import run_isolated,outcome
    from aegis_dc.ordinary.ledger import PaidStudy
    root=Path(m["output_root"])
    root.mkdir(parents=True,exist_ok=False)
    save(root/"launch-intent.json",dict(manifest=args.manifest_sha,approval=args.approval_sha,job=os.environ["SLURM_JOB_ID"]))
    try:
        configs,panels=baseline(m)
        ids={k:digest(v) for k,v in configs.items()}
        identity=dict(purpose=policy.STUDY,protocol=PROTOCOL,core=CORE,runtime=m["interpreter_sha256"],
                      source=m["execution_revision"],input_revision=digest(m["files"]),clock_horizon="H20-public-integers-v2",
                      scoring=m["files"]["src/aegis_dc/london_treatment_score.py"],initial="empty-PRE",
                      observations="public-view-v2",instance=args.manifest_sha)
        study=PaidStudy(root/"queries",identity,panels,ids)
        def evaluate(name,key):
            run_id=digest(study.cache.key(key,ids[key],name))
            raw=run_isolated(configs[key],name,policy.STUDY,run_id,root/"episodes"/run_id)
            return dict(row=outcome(raw),counts=raw["counts"],episode=run_id,raw_digest=digest(raw))
        reports=study.run(evaluate)
        from aegis_dc.ordinary.selection import paired_summary
        locks={g:panels.lock(c) for g,c in study.columns.items()}
        save(root/"terminal.json",dict(status="COMPLETE",paid=study.tickets.paid,locks=locks,reports=reports,
                                       paired=paired_summary(panels,study.columns,locks)))
    except Exception as exc:
        save(root/"failure.json",dict(error=repr(exc),retry=False,partial_comparison_valid=False))
        raise


if __name__=="__main__":
    main()
