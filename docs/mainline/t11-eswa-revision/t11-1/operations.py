"""Immutable operational identities, original-development linkage and one-time records."""
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time

BASE = Path.home() / "renly-patrol-rsi" / "mainline"
ORIGINAL = BASE / "T4c-action-cost-development-v3"
NATIVE_ROOT = BASE / "V6-cold-launch-release-v1" / "source"
SCIENCE = ORIGINAL / "source" / "docs" / "mainline" / "t4c-action-cost-v3"
PYTHON = Path.home() / "miniconda3" / "bin" / "python"
ACTIVITY_NAME = "T11-1-eswa-dev72-v11-c41ab910"
PROTOCOL_SHA = "8dfc03a7c1df9c254f246e1d40add424a0c04218ffdd345acc2b05ade6dc7284"
BASELINE_ROLES = ("MYOPIC","POMCP")
PUBLIC_NEW = ("worker.py","baselines.py","pomcp.py")


def need(ok, message):
    if not ok:
        raise ValueError(message)


def packed(obj):
    return json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=True, allow_nan=False).encode()


def signature(obj):
    return hashlib.sha256(packed(obj)).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, obj):
    """Publish a complete immutable record atomically, refusing overwrite."""
    path=Path(path)
    fd,tmp=tempfile.mkstemp(prefix="."+path.name+"-", dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as writer:
            writer.write(packed(obj)+b"\n")
            writer.flush()
            os.fsync(writer.fileno())
        os.link(tmp,path)
    finally:
        os.unlink(tmp)


def cpu():
    own=resource.getrusage(resource.RUSAGE_SELF)
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    return own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime


def check_stage(activity, freeze_sha):
    activity=Path(activity).resolve()
    need(activity == (BASE/ACTIVITY_NAME).resolve(),"unregistered activity root")
    manifest=activity/"source-manifest.json"
    need(file_sha(manifest)==freeze_sha,"published implementation manifest")
    spec=read(manifest)
    need(spec["protocol_sha256"]==PROTOCOL_SHA,"protocol identity")
    for path,digest in spec["files"].items():
        need(file_sha(activity/path)==digest,"staged file identity: "+path)
    evidence=read(activity/"references"/"protocol-freeze.json")
    for path,digest in evidence["files"].items():
        need(file_sha(activity/"references"/path)==digest,"normative member: "+path)
    need(file_sha(activity/"references"/"protocol-freeze.json")==PROTOCOL_SHA,"effective frozen protocol")
    return activity,spec


def in_allocation(activity, label):
    job=os.environ["SLURM_JOB_ID"]
    need(os.environ.get("SLURM_CPUS_PER_TASK")=="1","one CPU required")
    affinity=os.sched_getaffinity(0)
    os.sched_setaffinity(0,{min(affinity)})
    need(os.sched_getaffinity(0)=={min(affinity)},"single CPU affinity")
    path=activity/"submissions"/(label+".json")
    # A fast scheduler can start the allocation before the login process receives its ID.
    until=time.monotonic()+25
    while not path.exists() and time.monotonic()<until:
        time.sleep(.25)
    registration=read(path)
    need(registration["job"]==job and registration["name"]==label,"registered live allocation")
    return job


def stop(activity,category,label,detail):
    evidence=dict(category=category,label=label,detail=detail,time_utc=now(),
                  job=os.environ.get("SLURM_JOB_ID"))
    try:
        save(activity/"STOP.json",evidence)
    except FileExistsError:
        pass


def center_rows(activity):
    src=activity/"references"/"development.json.gz"
    expected=read(activity/"references"/"design.json")["panel"]["scores_sha256"]
    need(file_sha(src)==expected,"archived center development scores")
    data=json.loads(gzip.decompress(src.read_bytes()))
    units={u["key"]:u for u in data["units"] if u["role"]=="V_COST"}
    rows={r["key"]:r["arms"]["V_COST"] for r in data["rows"]}
    need(len(units)==len(rows)==72,"72 historic center positions")
    return rows,units


def original_identities(activity):
    ref=activity/"references"
    original=read(ref/"baseline-freeze.json")
    design=read(ref/"design.json")
    panel=design["panel"]
    recorded=read(activity/"source"/"stage0-identity.json")
    release=read(ref/"launch-manifest.json")
    need(file_sha(ref/"launch-manifest.json")==recorded["native_release_manifest_sha256"]
         and release["core_revision"]==original["native_core"]
         and release["core_revision"].startswith(design["native_core"])
         and release["core_tree"]==original["native_runtime"],"native core binding")
    for path,digest in release["core_files"].items():
        need(file_sha(NATIVE_ROOT/path)==digest,"native core file: "+path)
    need(file_sha(PYTHON)==release["python"]["sha256"]==original["python"]["sha256"],"research interpreter")
    frozen=read(SCIENCE/"freeze.json")
    source_root=ORIGINAL/"source"
    need(original["scientific_source"]==design["worker_revision"] and frozen["files"]==original["sources"],
         "historical scientific member map")
    for path,digest in frozen["files"].items():
        need(file_sha(source_root/path)==digest,"historical science file: "+path)
    original_members=original["public_bundle_files"]
    need(signature(original_members)==original["public_bundle_sha256"],"old public bundle")
    for path,digest in original_members.items():
        need(file_sha(ORIGINAL/"public-only"/path)==digest,"old public member: "+path)
    mfile=ORIGINAL/"dev-inputs"/"manifest.json"
    need(file_sha(mfile)==file_sha(ref/"original-dev-manifest.json")==panel["manifest_sha256"]
         and file_sha(ORIGINAL/"dev-inputs.jsonl.gz")==panel["archive_sha256"],"original development inputs")
    manifest=read(mfile); rows,units=center_rows(activity); index={}
    need(len(manifest["order"])==len(set(manifest["order"]))==72,"development order")
    for key in manifest["order"]:
        root=ORIGINAL/"positions"/("dev-"+key+"-V_COST")/"a1"
        entry=read(root/"entry.json");native=read(root/"native-entry.json");score=read(root/"score.json")
        unit=units[key];inp=file_sha(ORIGINAL/"dev-inputs"/(key+".json"))
        need(inp==manifest["files"][key]==entry["input"]==native["input"]==unit["input"],"original input "+key)
        need(entry["role"]==native["role"]=="V_COST" and entry["key"]==native["key"]==key and
             entry["manifest"]==panel["manifest_sha256"] and entry["freeze"]==file_sha(SCIENCE/"freeze.json")
             and entry["launch_code"]==recorded["original_launcher_sha256"]==file_sha(SCIENCE/"execute_v3_corrected.py")
             and entry["runtime_code"]==file_sha(SCIENCE/"native_v3.py"),"original entry: "+key)
        need(native["bundle"]==original["public_bundle_sha256"] and score["runtime"]==release["core_tree"]
             and entry==score["entry"]==rows[key]["entry"] and score["clocks"]==score["public_calls"]==61,
             "original native/public identities: "+key)
        need(file_sha(root/"score.json")==unit["score"]==rows[key]["score_sha256"] and
             score["raw"]==unit["raw"]==rows[key]["raw"] and score["IPC"]==unit["IPC"]==rows[key]["IPC"],
             "original score and saved history index: "+key)
        index[key]=[inp,unit["score"],unit["raw"],unit["IPC"],entry["job"],entry["attempt"]]
    result=signature(index)
    need(result==recorded["matched_remote_development_archive"]["stable_center_ledger"],"complete archived center ledger")
    return dict(original_input_count=len(index),core_members=len(release["core_files"]),
                science_members=len(frozen["files"]),public_members=len(original_members),
                original_ledger_sha256=result,python_sha256=original["python"]["sha256"],
                native_core=release["core_revision"],native_tree=release["core_tree"],
                worker_revision=original["scientific_source"],original_public_bundle=original["public_bundle_sha256"])


def public_bundle(activity, *, create=False):
    original=read(activity/"references"/"baseline-freeze.json")["public_bundle_files"]
    spec=read(activity/"source-manifest.json")
    files=dict(original)
    for name in PUBLIC_NEW:
        files[name]=spec["files"]["source/"+name]
    target=activity/"public-only"
    if create:
        target.mkdir()
        for path in files:
            source=activity/"source"/path if path in PUBLIC_NEW else ORIGINAL/"public-only"/path
            dest=target/path
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,dest)
            dest.chmod(0o444)
    found={p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
    need(found==set(files),"complete allowlisted policy bundle")
    for path,digest in files.items():
        need(file_sha(target/path)==digest,"public actor file: "+path)
    return signature(files)
