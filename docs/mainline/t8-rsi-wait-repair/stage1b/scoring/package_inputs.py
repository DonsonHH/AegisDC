"""Export only pinned evaluator code, public worker code and the released FIT control documents."""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

PK=Path(__file__).resolve().parent
ROOT=PK.parents[4]
PREFIX="docs/mainline/t8-rsi-wait-repair/"
SCORING=PREFIX+"stage1b/scoring/"
BASE="3487276af9e9759357771d16eb45feceaa3c948a"
PI_RELEASE="7518bc3f66a03eb56b68640aa8fd5e0a6d169a01"
PARENT_FREEZE="docs/mainline/t4c-action-cost-v3/v-double-star-freeze.json"
CORE_FREEZE="docs/mainline/v6-stage-three-cold-launch-v1/launch-manifest.json"
NATIVE_PATHS={
    "t2-minute-facility-v1":("facility_inputs.py",),
    "t3-prior-information-v2":("common.py","public_work.py","incident_facility.py","score_saved.py"),
    "t4a-public-risk-v1":("bridge.py","run_panel.py"),
    "t4c-action-cost-v3":("native_v3.py","plant_cost.py"),
}
R1=("fit_program.py","fit_evidence.py","fit_loop.py","fit_broker.py","read_fit.py","public_fixture.py")
IMAGE_CODE=("public_roles.py","native_role.py","access_audit.py","positions.py","sandbox.py","prepare_runtime.py")


def blob(rev,path):
    return subprocess.check_output(["git","cat-file","blob",rev+":"+path],cwd=ROOT)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def packed(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()


def fixtures():
    t4="docs/mainline/t4c-action-cost-v3/"
    manifest=json.loads(blob(BASE,t4+"eng-manifest.json"))
    archive=blob(BASE,t4+"eng-inputs.jsonl.gz")
    assert sha(archive)==manifest["input_archive"]
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as stream:
        for line in stream:
            k,v=json.loads(line)
            if k=="5-wrong":
                v["plan"]={int(t):a for t,a in v["plan"].items()}
                assert sha(packed(v)+b"\n")==manifest["files"][k]
                prog=v["case"]["native"]["dispatch_program"]
                return {"public":prog["public"],"view":{"time":0,"records":[r for r in prog["channel"] if r["arrived"]<=0],
                        "work":[],"paid":[],"writes":[],"fixed":[],"issued":[]}}
    raise ValueError("missing public engineering example")


def image_lock():
    parent_bytes=blob(BASE,PARENT_FREEZE)
    assert sha(parent_bytes)=="17e5e4c98b46b7859621608efa3ea3378baf5f5be6209c28a91dee998f55c462"
    parent=json.loads(parent_bytes)
    release=blob(BASE,CORE_FREEZE);assert sha(release)==parent["sources"][CORE_FREEZE]
    core=json.loads(release)
    names=["docs/mainline/"+directory+"/"+n for directory,files in NATIVE_PATHS.items() for n in files]
    names+=["src/aegis_action_cost/__init__.py","src/aegis_action_cost/permit.py"]
    native={n:parent["sources"][n] for n in names}
    assert all(sha(blob(BASE,n))==h for n,h in native.items())
    current={n:sha((PK/n).read_bytes()) for n in IMAGE_CODE}
    sources={n:sha(blob(PI_RELEASE,PREFIX+"r1/"+n)) for n in R1}
    assert sha(packed(parent["public_bundle_files"]))==parent["public_bundle_sha256"]
    return {"base":BASE,"signed_overlap_release":PI_RELEASE,"native_python":core["python"]["sha256"],
            "native_tree":parent["native_runtime"],"parent_bundle":parent["public_bundle_sha256"],
            "public_members":parent["public_bundle_files"],"native_members":native,
            "core_members":{n:h for n,h in core["core_files"].items() if
                n.startswith("src/") or n in ("configs/materials/reference-r134a-saturation.json","scripts/audit_v6_joint.py")},
            "engineering_example":sha(packed(fixtures())+b"\n"),"r1_files":sources,"scoring_files":current}


def export(revision,target):
    lock=json.loads(blob(revision,SCORING+"source-lock.json"))
    files={n:blob(BASE,n) for n in lock["native_members"]}
    assert all(sha(v)==lock["native_members"][n] for n,v in files.items())
    for key,h in lock["r1_files"].items():
        name=PREFIX+"r1/"+key;files[name]=blob(PI_RELEASE,name);assert sha(files[name])==h
    for p in subprocess.check_output(["git","ls-tree","-r","--name-only",revision,"--",SCORING],cwd=ROOT).decode().splitlines():
        files[p]=blob(revision,p)
    for n,h in lock["scoring_files"].items():assert sha(files[SCORING+n])==h
    for n in ["r0/design.json","r0/registration.json","r0/round-ledger.schema.json",
              "stage1b/fit-shared-account.json","custody/authority.json","custody/catalogue-coverage.json",
              "stage1b/fit-overlap/input-freeze.json","stage1b/fit-overlap/request.json","stage1b/fit-overlap/receipt.json",
              "stage1b/fit-overlap/receipt.sig","stage1b/fit-overlap/signature-provenance.json"]:
        p=PREFIX+n;files[p]=blob(PI_RELEASE,p)
    fx=packed(fixtures())+b"\n";assert sha(fx)==lock["engineering_example"]
    files[SCORING+"engineering-example.json"]=fx
    files[SCORING+"export.json"]=packed({"revision":revision,"members":{p:sha(v) for p,v in files.items()}})+b"\n"
    with tarfile.open(target,"x") as tar:
        for p,raw in sorted(files.items()):
            member=tarfile.TarInfo(p);member.size=len(raw);member.mode=0o644;tar.addfile(member,io.BytesIO(raw))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--lock",action="store_true")
    modes.add_argument("--export",metavar="GIT_REVISION")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.lock:
        (PK/"source-lock.json").write_bytes((json.dumps(image_lock(),indent=2,sort_keys=True)+"\n").encode())
    elif args.output:
        export(args.export,args.output)
    else:p.error("--export requires --output")
