"""Frozen bindings and durable record helpers for the v3a diagnostic."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

PK = Path(__file__).resolve().parent
ROOT = PK.parents[2]
ML = PK.parent
V2 = ML/"t5-ordinary-improvement-development-v2"
V1 = ML/"t5-ordinary-improvement-development-v1"
T4B = ML/"t4b-holdout-confirmation-v2"
T4C = ML/"t4c-action-cost-v3"
T4D = ML/"t4d-cost-baseline-v1"
T4A = ML/"t4a-public-risk-v1"
T3 = ML/"t3-prior-information-v2"
SHARE = Path("/share/home/renly/renly-patrol-rsi/mainline")
ACT = SHARE/"T5-landscape-diagnostic-v3a"
V2_REMOTE = SHARE/"T5-ordinary-improvement-development-v2"
NATIVE = SHARE/"V6-cold-launch-release-v1/source"
LOCK = PK/"source-freeze.json"
EPS = 1e-7
sys.path[:0] = list(map(str, (PK,V2,V1,T4D,T4C,T3,T4A,NATIVE/"src",NATIVE/"scripts",ROOT/"src",T4B)))


def check(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_bytes())


def packed(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(packed(obj)).hexdigest()


def sha(path):
    with Path(path).open("rb") as reader:
        return hashlib.file_digest(reader,"sha256").hexdigest()


def write(path, obj):
    with Path(path).open("xb") as stream:
        stream.write(packed(obj)+b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def write_gz(path, obj):
    with Path(path).open("xb") as stream:
        stream.write(gzip.compress(packed(obj)+b"\n",compresslevel=5,mtime=0))


def job():
    return os.environ["SLURM_JOB_ID"]


def config():
    return read(PK/"design.json")


def role_list(cfg):
    r=cfg["roles"]
    return [*r["random"],*r["reference"],r["oracle"]]


def check_source(compute=True):
    check(sha(LOCK)==os.environ["V3A_SOURCE"],"published scientific release identity")
    source=read(LOCK)
    for name,expected in source["files"].items():
        check(sha(ROOT/name)==expected,"source identity: "+name)
    release=read(ML/"v6-stage-three-cold-launch-v1/launch-manifest.json")
    check(sha(sys.executable)==release["python"]["sha256"],"registered interpreter")
    if compute:
        job()
        for name,expected in release["core_files"].items():
            check(sha(NATIVE/name)==expected,"native runtime: "+name)
    return release["core_tree"]


def verify_workers():
    from context_v2 import references, verify_bundle, verify_learned

    identities=read(LOCK)["predecessor_evidence"]
    check(sha(V2_REMOTE/"bundle-index.json")==identities["bundle_index"],"v2 accepted bundle index")
    check(sha(V2_REMOTE/"public-checks/histories.json")==identities["histories"],"three registered public histories")
    checked={k:verify_learned(k) for k in ("manual","learned")}
    for role,(identity,path,pins) in references().items():
        if role in ("B_COST","V_COST","P"):
            check(verify_bundle(path,pins)==identity,"registered benchmark: "+role)
            checked[role]=identity
    return checked


def seed_bytes(purpose):
    entry=read(PK/"random-commitments.json")["streams"][purpose]
    raw=(ACT/"private"/(purpose+".bin")).read_bytes()
    check(len(raw)==entry["bytes"] and hashlib.sha256(raw).hexdigest()==entry["sha256"],"private development source: "+purpose)
    return raw


def stream_int(raw,domain,substream):
    msg=raw+b"|"+(domain+"|"+substream).encode()
    return int.from_bytes(hashlib.sha256(msg).digest(),"big")


def operative(case):
    return digest({name:case[name] for name in ("native","attachment","maintenance")})


def old_identities(cfg):
    result={}
    for tag,source in cfg["reference_inputs"].items():
        rows=read(ROOT/source["path"])[source["field"]]
        check(len(rows)==source["n"],"complete prior public commitments")
        result[tag]=({r["sha256"] for r in rows.values()},{r["operative_sha256"] for r in rows.values()})
    return result


def manifest():
    path=ACT/"panel-and-strategies.json"
    check(sha(path)==os.environ["V3A_PANEL"],"published panel and strategy collection")
    m=read(path)
    check(m["source"]==sha(LOCK) and len(m["order"])==36 and len(m["vectors"])==48
          and len(set(v["behavior"] for v in m["vectors"].values()))==48,"complete stage A identity")
    return m


def case_at(key,m):
    path=ACT/"inputs"/(key+".json")
    check(sha(path)==m["conditions"][key]["sha256"],"registered condition")
    return read(path)


def binding(label,m):
    if label in m["vectors"]:
        return dict(track="MAIN",theta=m["vectors"][label]["theta"],no_probe=False),False
    if label in ("M","M_HOT"):
        r=read(V2/"manual-references.json")["references"][label]
        check(digest(r["theta"])==r["descriptor_sha256"],"manual reference identity")
        return dict(track=r["track"],theta=r["theta"],no_probe=False),True
    if label.startswith(("MAIN-U-","MAIN-R-")):
        r=read(V2/"locked.json")["arms"][label]
        check(digest(r["vector"])==r["descriptor_sha256"],"v2 fixed reference")
        return dict(track="MAIN",theta=r["vector"],no_probe=False),False
    check(label in ("B_COST","V_COST","P","ORACLE"),"registered control")
    return None,False


def batches(m, cfg):
    # Each lane receives one or two complete six-family passes.
    order=m["order"];first=order[:6]
    names=cfg["pilot"]["labels"]
    tasks={f"pilot-{i:02}":[[(label,key)] for label in names] for i,key in enumerate(first,1)}
    for label in role_list(cfg):
        keys=order[6:] if label in names else order
        n=cfg["scheduler"]["main_piloted_cpus"] if label in names else cfg["scheduler"]["main_full_cpus"]
        passes=[keys[i:i+6] for i in range(0,len(keys),6)]
        lanes=[[(label,k) for block in passes[i::n] for k in block] for i in range(n)]
        check(all(len(lane)==len(keys)//n for lane in lanes),"balanced facility lanes")
        tasks["score-"+label]=lanes
    if m["identity_only_keys"]:
        tasks["identity-witness"]=[[("P",k) for k in m["identity_only_keys"]]]
    return tasks
