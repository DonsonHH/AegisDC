"""Reserved paths, canonical formats, and preregistered source identities for T5."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

PK = Path(__file__).resolve().parent
ROOT = PK.parents[2]
MAINLINE = PK.parent
SHARE = Path("/share/home/renly/renly-patrol-rsi/mainline")
ACT = SHARE/"T5-ordinary-improvement-development-v1"
CORE = SHARE/"V6-cold-launch-release-v1/source"
V3_DEV = SHARE/"T4c-action-cost-development-v3"
T4B = MAINLINE/"t4b-holdout-confirmation-v2"
T4C = MAINLINE/"t4c-action-cost-v3"
T4D = MAINLINE/"t4d-cost-baseline-v1"
T3 = MAINLINE/"t3-prior-information-v2"
T4A = MAINLINE/"t4a-public-risk-v1"
LOCK = PK/"source-freeze.json"
PUBLIC = ACT/"public-only"
TRACKS = ("MAIN","HOT")
METRICS = ("L","U","person","tool","fee")
sys.path[:0] = list(map(str,(PK,T4D,T4C,T3,T4A,CORE/"src",CORE/"scripts",ROOT/"src",T4B)))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_bytes())


def compact(data):
    return json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(compact(data)).hexdigest()


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def write(path,data):
    with Path(path).open("xb") as f:
        f.write(compact(data)+b"\n")
        f.flush()
        os.fsync(f.fileno())


def write_gz(path,data):
    with Path(path).open("xb") as f:
        f.write(gzip.compress(compact(data)+b"\n",compresslevel=5,mtime=0))


def job():
    return os.environ["SLURM_JOB_ID"]


def settings():
    return read(PK/"design.json"),read(PK/"parameter-space.json"),read(PK/"U.json")["U"]


def verify_sources(on_slurm=True):
    if on_slurm:
        job()
    expected=os.environ["T5_SOURCE_SHA"]
    require(sha(LOCK)==expected,"pinned purpose and source freeze")
    m=read(LOCK)
    for path,value in m["files"].items():
        require(sha(ROOT/path)==value,"source file identity "+path)
    release=read(MAINLINE/"v6-stage-three-cold-launch-v1/launch-manifest.json")
    require(sha(sys.executable)==release["python"]["sha256"],"native interpreter")
    if on_slurm:
        for path,value in release["core_files"].items():
            require(sha(CORE/path)==value,"native core identity "+path)
    return release["core_tree"]


def operative(x):
    return digest({k:x[k] for k in ("native","attachment","maintenance")})


def cases():
    path=ACT/"inputs.json"
    require(sha(path)==os.environ["T5_INPUT_SHA"],"published input commitments")
    m=read(path)
    require(m["source_sha256"]==sha(LOCK) and len(m["order"]["FIT"])==36 and len(m["order"]["DEV"])==48,
            "complete frozen development panel")
    return m


def read_case(key, manifest):
    path=ACT/"inputs"/(key+".json")
    require(sha(path)==manifest["conditions"][key]["sha256"],"condition byte identity")
    return read(path)


def bundle_paths():
    prior=read(T4D/"input-manifest.json")
    declared=prior["role_bundles"]["BASE"]
    b_root=SHARE/"T4a-public-risk-development-v1/public-only"
    dev_v=V3_DEV/"public-only"
    d_root=SHARE/"T4d-cost-baseline-v1/bundles"/declared["B_COST"]
    roles={"B":b_root,"B_COST":d_root,"V_COST":dev_v,"V_COST_NOPROBE":dev_v,"P":dev_v}
    return {role:(declared.get(role,declared["V_COST"]),path) for role,path in roles.items()},prior["bundle_members"]


def verify_bundles(learned=False):
    refs, members=bundle_paths()
    for bundle,folder in sorted(set(refs.values())):
        pins=members[bundle]
        require(digest(pins)==bundle and {f.relative_to(folder).as_posix() for f in folder.rglob("*") if f.is_file()}==set(pins),
                "exact registered predecessor bundle")
        for path,value in pins.items():
            require(sha(folder/path)==value,"frozen public predecessor source")
    if learned:
        pins=read(ACT/"worker-bundle.json")["members"]
        expected=dict(members[refs["V_COST"][0]])
        for path,value in read(LOCK)["files"].items():
            if path.startswith("src/aegis_improvement/") and path.endswith(".py") and not path.endswith("improver.py"):
                expected[path.removeprefix("src/")]=value
        expected["parameter-space.json"]=sha(PK/"parameter-space.json")
        for leaf in ("__init__.py","rule.py"):
            relative="aegis_cost_baseline/"+leaf
            expected[relative]=sha(ROOT/"src"/relative)
        require(pins==expected and {f.relative_to(PUBLIC).as_posix() for f in PUBLIC.rglob("*") if f.is_file()}==set(pins),
                "exact registered improvement bundle")
        for path,value in pins.items():
            require(sha(PUBLIC/path)==value,"isolated worker file")
    return refs,members
