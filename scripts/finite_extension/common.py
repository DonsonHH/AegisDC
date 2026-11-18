"""Frozen launch identity and single-write durable records."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import london_confirmation_entry as prior

PACK = "docs/mainline/review-gated/R4/finite-extension-v1/"
OLD = "docs/mainline/review-gated/R4/confirmation-entry-v1/"
REAL = "FINITE_SYNTHETIC_EXTENSION"
FIXTURE = "PUBLIC_LAUNCH_WITNESS"
PYTHON_SHA = "5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6"
PYTHON = "/share/home/renly/miniconda3/bin/python"
BASE = Path("/share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118")
STUDY_OUTPUT = BASE / "study-v1"
RUNTIME = ["scripts/finite_extension/"+name for name in ("common.py","launch.py","analysis.py","submit.py","slot.slurm")]
RUNTIME += ["scripts/london_confirmation_entry.py","scripts/run_london_public_development.py",*prior.CORE_HASHES]
COUNT_KEYS = {"constructor":"constructor_attempts","plant":"plant_entry_calls","policy":"policy_calls","scorer":"scorer_calls"}
EMPTY = dict.fromkeys(COUNT_KEYS.values(), 0)
ARMS = ["I","D","P"]


class Rejected(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Rejected(message)


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def durable(path, value):
    """Expose complete files with no replacement. A failed write leaves evidence."""
    tmp = path.with_name("writing-"+path.name)
    with tmp.open("x",encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, allow_nan=False, separators=(",",":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.link(tmp, path)
    tmp.unlink()
    sync_dir(path.parent)


def sync_dir(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def mkdir(path):
    path.mkdir()
    sync_dir(path.parent)


def budget(purpose):
    return dict(conditions=35,arms=105,policy_calls=2100,cpus=1,memory_MiB=1024,seconds=60) if purpose==REAL else dict(cpus=1,memory_MiB=1024,seconds=120,real_calls=0)


def manifest_data(path,digest,approval,approval_sha):
    data=Path(path).read_bytes()
    need(hashlib.sha256(data).hexdigest()==digest,"MANIFEST_HASH")
    m=prior.strict_loads(data)
    purpose=m.get("purpose")
    need(purpose in (REAL,FIXTURE),"PURPOSE_REJECTED")
    # Explicit future human decision is recorded outside the review manifest.
    if purpose==REAL:
        need(approval!="-" and approval_sha!="-","REVIEW_REQUIRED")
        auth_bytes=Path(approval).read_bytes()
        need(hashlib.sha256(auth_bytes).hexdigest()==approval_sha,"REVIEW_HASH")
        auth=prior.strict_loads(auth_bytes)
        need(auth==dict(purpose=REAL,decision="AUTHORIZE_ONE_FROZEN_EXECUTION",manifest_sha256=digest),"REVIEW_BINDING")
    need(m["schema"]=="aegisdc-finite-extension-launch-v1" and m["core_revision"]==prior.CORE_REV,"MANIFEST_SCHEMA")
    need(m["arm_order"]==ARMS and m["budget"]==budget(purpose),"BUDGET_OR_ORDER")
    need(m["python_sha256"]==PYTHON_SHA and file_sha(Path(sys.executable).resolve())==PYTHON_SHA,"PYTHON_IDENTITY")
    need(m["runtime"].keys()==set(RUNTIME),"RUNTIME_SET")
    for name,expected in m["runtime"].items():
        need(file_sha(ROOT/name)==expected,"RUNTIME_HASH:"+name)
        if name in prior.CORE_HASHES:
            need(expected==prior.CORE_HASHES[name],"CORE_IDENTITY")
    need(m["source_revision"]==read(ROOT/"staged.json")["revision"],"STAGED_REVISION")
    output=Path(m["output_root"]).resolve()
    need(BASE in output.parents and (output==STUDY_OUTPUT if purpose==REAL else output.parent==BASE and output.name.startswith("witness-")),"OUTPUT_ROOT")
    datafile=PACK+"conditions.json" if purpose==REAL else OLD+"inputs.json"
    need(m["data_path"]==datafile and file_sha(ROOT/datafile)==m["data_sha256"],"INPUT_HASH")
    document=prior.strict_loads((ROOT/datafile).read_bytes())
    if purpose==REAL:
        need(document["purpose"]==REAL,"INPUT_PURPOSE")
        need(m["supporting"].keys()=={PACK+n for n in ("selection.json","protocol.md","static-audit.json","selection-notes.md","freeze-addendum.json")},"SUPPORT_SET")
        for name,sha in m["supporting"].items():need(file_sha(ROOT/name)==sha,"SUPPORT_HASH")
        scope=read(ROOT/(PACK+"selection.json"))
        order=sorted(s for group in scope["groups"] for s in group["slots"])
        need(len(order)==35 and document["order"]==m["order"]==order,"SLOT_ORDER")
        rows=document["conditions"]
        need([r["condition_id"] for r in rows]==order and len({r["canonical_sha256"] for r in rows})==35,"FROZEN_ROWS")
        for r in rows:need(prior.config_hash(r["common"])==r["canonical_sha256"],"CONFIG_HASH")
        audit=read(ROOT/(PACK+"static-audit.json"))
        need(not audit["gaps"] and audit["ready_for_static_review"],"STATIC_GAP")
        return m,{r["condition_id"]:r["common"] for r in rows},{}
    need(m["supporting"].keys()=={PACK+"witnesses.json",PACK+"freeze-addendum.json"},"FIXTURE_SUPPORT")
    for name,sha in m["supporting"].items():need(file_sha(ROOT/name)==sha,"FIXTURE_HASH")
    spec=read(ROOT/(PACK+"witnesses.json"));cases={c["id"]:c for c in spec["cases"]}
    alternatives=[spec["parts"]["local_in_allocation"],spec["parts"]["separate_serial_scheduler_jobs"]+spec["parts"]["expected_unsubmitted_suffix"]]
    need(m["order"] in alternatives,"FIXTURE_ORDER")
    inputs={r["condition_id"]:r["common"] for r in document["conditions"]}
    return m,{s:inputs[cases[s]["input"]] for s in m["order"]},cases


def empty_ledger(state="NOT_CALLED"):
    return dict(callback_state=state,calls_proved=0,returned=0,unreturned_or_pending=0,
                returned_count_unknown=0,known_reported_subtotal=EMPTY.copy(),
                internal_count_semantics="KNOWN_ZERO",retry_budget_released=False)


def counts_from_return(actual):
    if not isinstance(actual,dict):return None
    counts=actual.get("counts");calls=actual.get("calls")
    if type(counts) is not dict or set(counts)!=set(EMPTY) or type(calls) is not list:return None
    if any(type(n) is not int or n<0 for n in counts.values()):return None
    observed=EMPTY.copy()
    for call in calls:
        if type(call) is not dict or call.get("kind") not in COUNT_KEYS or call.get("arm") not in ARMS:return None
        observed[COUNT_KEYS[call["kind"]]]+=1
    return counts if counts==observed else None


def recovery(directory):
    # Read errors and torn writes are unknown. Only an explicit zero-call receipt proves zero.
    try:
        ledger=read(directory/"accounting.json")
        if ledger.get("callback_state") in ("RETURNED","RAISED","NOT_CALLED"):return ledger
    except (OSError,ValueError,TypeError,AttributeError):
        pass
    ledger=empty_ledger("PENDING")
    ledger.update(calls_proved=None,unreturned_or_pending=1,internal_count_semantics="UNKNOWN_INTERNAL_COUNTS")
    return ledger
