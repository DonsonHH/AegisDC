"""Keep development inputs, immutable dependencies and receipts in their registered locations."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

PK = Path(__file__).resolve().parent
ROOT = PK.parents[2]
ML = PK.parent
T3 = ML/"t3-prior-information-v2"
T4A = ML/"t4a-public-risk-v1"
T4B = ML/"t4b-holdout-confirmation-v2"
T4C = ML/"t4c-action-cost-v3"
T4D = ML/"t4d-cost-baseline-v1"
V1 = ML/"t5-ordinary-improvement-development-v1"
REMOTE = Path("/share/home/renly/renly-patrol-rsi/mainline")
ACT = REMOTE/"T5-ordinary-improvement-development-v2"
CORE = REMOTE/"V6-cold-launch-release-v1/source"
LOCK = PK/"stage-a.json"
METRICS = ("L","U","person","tool","fee")
sys.path[:0] = list(map(str,(PK,V1,T4D,T4C,T3,T4A,CORE/"src",CORE/"scripts",ROOT/"src",T4B)))


def need(ok, description):
    if not ok:
        raise ValueError(description)


def read(path):
    return json.loads(Path(path).read_bytes())


def packed(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(packed(value)).hexdigest()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def put(path,value):
    with Path(path).open("xb") as out:
        out.write(packed(value)+b"\n")
        out.flush()
        os.fsync(out.fileno())


def put_gz(path,value):
    with Path(path).open("xb") as out:
        out.write(gzip.compress(packed(value)+b"\n",compresslevel=5,mtime=0))


def job():
    return os.environ["SLURM_JOB_ID"]


def config():
    return read(PK/"design.json"),read(PK/"space.json"),read(PK/"U.json")["U"]


def verify_sources(on_compute=True):
    need(sha(LOCK)==os.environ["T5V2_SOURCE"],"published Stage A")
    for file, expected in read(LOCK)["files"].items():
        need(sha(ROOT/file)==expected,"source identity: "+file)
    release=read(ML/"v6-stage-three-cold-launch-v1/launch-manifest.json")
    need(sha(sys.executable)==release["python"]["sha256"],"pinned main interpreter")
    if on_compute:
        job()
        for file,h in release["core_files"].items():
            need(sha(CORE/file)==h,"native release: "+file)
    return release["core_tree"]


def operative(case):
    return digest({k:case[k] for k in ("native","attachment","maintenance")})


def panel():
    path=ACT/"inputs.json"
    need(sha(path)==os.environ["T5V2_INPUTS"],"published panel commitments")
    info=read(path)
    need(info["source"]==sha(LOCK) and [len(info["order"][k]) for k in ("FIT","DEV")]==[12,24],"fixed panel")
    return info


def case_at(key,info):
    path=ACT/"inputs"/(key+".json")
    pin=info["cases"][key]
    need(sha(path)==pin["sha256"],"input identity")
    return read(path)


def references():
    parent=read(T4D/"input-manifest.json")
    mapping=parent["role_bundles"]["BASE"]
    lookup=parent["bundle_members"]
    return {
        "B": (mapping["B"],REMOTE/"T4a-public-risk-development-v1/public-only",lookup[mapping["B"]]),
        "B_COST": (mapping["B_COST"],REMOTE/"T4d-cost-baseline-v1"/"bundles"/mapping["B_COST"],lookup[mapping["B_COST"]]),
        "V_COST": (mapping["V_COST"],REMOTE/"T4c-action-cost-development-v3/public-only",lookup[mapping["V_COST"]]),
        "V_COST_NOPROBE": (mapping["V_COST"],REMOTE/"T4c-action-cost-development-v3/public-only",lookup[mapping["V_COST"]]),
    }


def verify_bundle(root,pins):
    files={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    need(files==set(pins),"isolated code membership")
    for file,h in pins.items():
        need(sha(root/file)==h,"isolated code: "+file)
    return digest(pins)


def verify_learned(track):
    info=read(ACT/"bundle-index.json")[track]
    need(verify_bundle(ACT/"public"/track,info["files"])==info["sha256"],"isolated policy bundle")
    return info["sha256"]
