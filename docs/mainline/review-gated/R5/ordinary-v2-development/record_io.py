"""Read-only study record support. New receipts are written once outside the study tree."""
import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path

RUN_SOURCE = "a2ac508cc6bd166cf40da08dd9a15654398ecf6e"
MANIFEST_SHA = "45b29f25522908e1aa14ffa2077a355f8c0d70bdaecfdfa3d680938bbd445e5b"
APPROVAL_SHA = "9bf3c28e0a398e4b276b49df1ceafc46a669ea743c8a604196a508e6958912c9"
MANIFEST = Path("docs/mainline/review-gated/R5/ordinary-v2-qualification/research-manifest-review.json")
APPROVAL = Path("docs/mainline/review-gated/R5/ordinary-v2-development/approval.json")
RESOURCE_V = {"within_budget", "external_reservations_clear", "reserved_exit_honored"}
DIMS = ("L", "U", "person_seconds", "tool_seconds")
ARMS = ("I","D","P")


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(data):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(value,stream,ensure_ascii=False,separators=(",",":"),allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def exact(value):
    n = Fraction(value)
    return n.numerator if n.denominator == 1 else str(n)


def evidence_summary(run):
    """Describe saved events; never integrate, rescore, or invoke a strategy."""
    final = run["final_audit"] if "final_audit" in run else run["final"]
    record = run.get("run",run)
    score = run["score"]
    return dict(z=[score[k] for k in DIMS], violations=sorted(k for k,v in score["hard_constraints"].items() if not v),
                complete=score["trace_status"]=="COMPLETE", stage=run["reached"]["stage"], stop=record["stop"],
                costs={k:score[k] for k in ("resource_queue_seconds","approval_wait_seconds","unstarted_observed_wait_seconds","observed_stop_time","request_count","policy_call_count")},
                work_by_action=score["work_by_action"],work_by_stage=score["work_by_stage"],
                requests=[dict(time=x["time"],action=x["payload"]["action"],mode=x["payload"].get("mode"),
                               reply=x["reply"]["status"],request_id=x["payload"]["request_id"],
                               execution_id=x["payload"].get("execution_id"),target_epoch=x["payload"].get("target_config_epoch"))
                          for x in record["requests"]],
                commit_result=final["commit_result"],verification_result=final["verification_result"],
                execution_receipts=[x for x in final["receipts"] if x["record_kind"]=="EXECUTION_RECEIPT"],
                verify_records=[x for x in final["observations"] if x.get("action")=="VERIFY_CTRL"],
                recoveries=score["recoveries"],final_device=final["device"],final_backup=final["g_state"])
