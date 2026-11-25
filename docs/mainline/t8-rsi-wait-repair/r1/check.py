"""Read the stage-1a delivery, including original signed engineering records. No executions."""

import argparse
import csv
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile

import check_a
from read_fit import read_case

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PARENT="6b63c4f4db6b8b19d01b2d00b99f740fba68525e"
PREFIX="docs/mainline/t8-rsi-wait-repair/"


def require(ok,why):
    if not ok: raise ValueError(why)


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)


def load(path):return json.loads(path.read_bytes())
def sha(raw):return hashlib.sha256(raw).hexdigest()


def verify_delivery(committed):
    receipt=load(HERE/"delivery.json")
    for name,entry in receipt["artifacts"].items():
        raw=(HERE/name).read_bytes()
        require(len(raw)==entry["bytes"] and sha(raw)==entry["sha256"],"delivery bytes: "+name)
        if committed:
            require(raw==git("cat-file","blob","HEAD:"+PREFIX+"r1/"+name),"checkout versus git: "+name)
    if committed:
        tracked=set(git("ls-tree","-r","--name-only","HEAD",PREFIX+"r1").decode().splitlines())
        require(tracked=={PREFIX+"r1/"+n for n in [*receipt["artifacts"],"delivery.json"]},"complete declared delivery set")
        require((HERE/"delivery.json").read_bytes()==git("cat-file","blob","HEAD:"+PREFIX+"r1/delivery.json"),"manifest bytes")
        require(not git("diff","--name-only",PARENT,"HEAD","--",".",":(exclude)"+PREFIX+"r1/**"),"work beyond r1")
    for identity in ("initial_fixture","corrected_fixture"):
        rev=receipt["versions"][identity]
        freeze=json.loads(git("cat-file","blob",rev+":"+PREFIX+"r1/b-freeze.json"))
        for folder in ("r0","sources"):
            for name,h in freeze[folder].items():
                target=PREFIX+("r1/" if folder=="sources" else "r0/")+name
                require(sha(git("cat-file","blob",rev+":"+target))==h,"execution source hash: "+identity+" "+name)
    prev,curr=[json.loads(git("cat-file","blob",receipt["versions"][k]+":"+PREFIX+"r1/b-freeze.json"))
               for k in ("initial_fixture","corrected_fixture")]
    for obj in (prev,curr):obj["sources"].pop("synthetic_selftest.py")
    require(prev==curr,"fixture expectations or study design changed")
    with (HERE/"stage1a-accounting.psv").open(encoding="utf8") as f:
        rows={r["JobID"]:r for r in csv.DictReader(f,delimiter="|") if "." not in r["JobID"]}
    actual=Decimal(0);reserved=0
    for job, stats in receipt["jobs"].items():
        row=rows[job]
        mins,secs=row["TotalCPU"].split(":")
        cpu=Decimal(mins)*60+Decimal(secs)
        require(cpu==Decimal(stats["actual_cpu_s"]) and row["ExitCode"]==stats["exit"] and row["State"]==stats["state"],
                "physical Slurm account "+job)
        actual+=cpu
        reservation=int(row["TimelimitRaw"])*60*int(row["AllocCPUS"])
        require(reservation==stats["reserved_cpu_s"],"reservation "+job)
        reserved+=reservation
    require(set(rows)==set(receipt["jobs"]) and actual==Decimal("321.572") and reserved==3840,"all job costs")
    print("PASS delivery inventory and hashes; five Slurm jobs, 3,840 reserved / 321.572 actual CPU s")
    if committed:print("PASS fresh checkout bytes and Git blobs; all changes since r0 confined to r1")
    return receipt


def unpack(file, root):
    with tarfile.open(file,"r:gz") as archive:
        for item in archive:
            p=PurePosixPath(item.name)
            require(p.parts and p.parts[0]=="records" and all(re.fullmatch(r"[a-zA-Z0-9_.-]+",s) and s not in (".","..")
                    for s in p.parts) and (item.isdir() or item.isfile()),"unexpected archive path/type")
            dest=root.joinpath(*p.parts)
            if item.isdir():
                dest.mkdir(parents=True,exist_ok=True)
            else:
                dest.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(item) as source,dest.open("xb") as out:shutil.copyfileobj(source,out)
    return root/"records"


def schema_files(paths):
    schema=HERE.parent/"r0"/"round-ledger.schema.json"
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        engine=shutil.which("pwsh")
        require(engine is not None,"round records require jsonschema or PowerShell Test-Json with Draft 2020-12")
        command=('$ErrorActionPreference="Stop"; $s=$env:T8_CHECK_SCHEMA; '
                 '$paths=[Console]::In.ReadToEnd() | ConvertFrom-Json; '
                 'foreach($p in $paths){if(-not(Test-Json -LiteralPath $p -SchemaFile $s)){throw $p}}')
        subprocess.run([engine,"-NoProfile","-NonInteractive","-Command",command],check=True,
            input=json.dumps([str(p) for p in paths]),text=True,env=dict(os.environ,T8_CHECK_SCHEMA=str(schema)))
    else:
        validator=Draft202012Validator(load(schema))
        for p in paths: validator.validate(load(p))


def read_attempt(receipt, failed):
    archive="standin-failed-135555.tar.gz" if failed else "standin-records.tar.gz"
    rev=receipt["versions"]["initial_fixture" if failed else "corrected_fixture"]
    freeze_raw=git("cat-file","blob",rev+":"+PREFIX+"r1/b-freeze.json")
    freeze=json.loads(freeze_raw)
    with tempfile.TemporaryDirectory(prefix="t8-signed-") as tmp:
        root=unpack(HERE/archive,Path(tmp))
        rep=None if failed else load(root/"selftest.json")
        if rep:require(rep==load(HERE/"selftest.json"),"published B summary differs from originals")
        expected={"gain"} if failed else set(freeze["cases"])
        folders={p.name for p in root.iterdir() if p.is_dir()}
        require(folders==expected,"retained case denominator")
        schemas=sorted(root.glob("*/rounds/*.json"))
        require(len(schemas)==8*len(expected),"round record denominator")
        schema_files(schemas)
        tokens=0
        for case in sorted(folders):
            summary=load(root/case/"case.json")
            require(summary["fixture_case"]==case and summary["freeze_sha256"]==sha(freeze_raw),"fixture identity")
            result=read_case(root/case,summary,lambda rec:None)  # all record files validated just above
            calls=result["shared_started"]+sum(v["started"] for v in result["arms"].values())
            require(calls==summary["service_calls"],"observed and billed physical tokens")
            tokens+=calls
            if rep:
                require(result==rep["cases"][case]["checked"] and calls==rep["cases"][case]["service_tokens"],
                        "independent replay and reported scope: "+case)
            if case=="gain":
                require([2,1] in result["arms"]["R"]["selected_changed_slots"] and
                        len(set(result["arms"]["O"]["program_sha256"]))==1,"paid and selected ancestry")
        if failed:
            require(tokens==1584 and not (root/"selftest.json").exists() and
                    "KeyError: 'O'" in (HERE/"failed-135555.log").read_text(encoding="utf8"),"original red trace")
        else:
            require(tokens==rep["standin_position_tokens"]==5867 and sum(x["dual_lock"] for x in rep["cases"].values())==3,
                    "final synthetic controls")
        print(f"PASS {'retained failed' if failed else 'final'} engineering attempt: {len(folders)} "
              f"{'case' if len(folders)==1 else 'cases'}, "
              f"{len(schemas)} signed schema-checked rounds, {tokens:,} fabricated tokens")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check",required=True,action="store_true")
    p.add_argument("--checkout-bytes",action="store_true")
    p.add_argument("--private-audit-only",type=Path)
    args=p.parse_args()
    receipt=verify_delivery(args.checkout_bytes)
    check_a.check(args.private_audit_only)
    read_attempt(receipt,True)
    read_attempt(receipt,False)
    print("PASS stage 1a ends at review: real FIT/DEV, facility, official overlap and H2/H3 accesses = 0")
