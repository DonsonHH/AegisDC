"""Verify commit -> tree -> blob membership without a Git checkout on the compute node."""
import base64
import hashlib
from pathlib import Path

CORE = "1c0b0c47a5742321a3524a5b16843775cc224e3e"
PROTOCOL = "4182f423bba954fce680a5268e4111a6b58bd989"
FREEZE = "c32f00e7ba6c1b5cdce651ea03b2e702e1faaa25"
PINS = {
    "docs/mainline/review-gated/R5/ordinary-v2-qualification/before-execution.md": "af014ff4c2321125b61ffae5c0ebb31932b6fbc7a20dd95ded5ba0d5357e45da",
    "docs/mainline/review-gated/R5/ordinary-v2-qualification/expected.json": "fe163ebffb76f2bad35783f540472c344e9555185266d67347a379d5fd0e39cc",
    "docs/mainline/review-gated/R5/ordinary-v2-qualification/fixtures.json": "0c6592900d1e2c2730cd459501dca25e82c4ad6bd97e698f9bd11ec823b31082",
    "docs/mainline/review-gated/R5/ordinary-v2-qualification/freeze.json": "8464e182b5a36c51ca8a3dcd85f4e03b271ccc043df54af974c37e6758689c2f",
    "src/aegis_dc/__init__.py": "32c7ae44be5f74a3d9d1c44cbe6df95e58637bfe74564ef41c463e1269cd013d",
    "src/aegis_dc/london_e14.py": "1d9f8421882faf9e021badf3138505332f9a0513bea90539e6cac04bfc6d2a42",
    "src/aegis_dc/london_treatments.py": "4bce4df739e8fbb9ae5b64f1ddb5434670a9334b44941777d7d9db25b466ece2",
    "src/aegis_dc/london_treatment_score.py": "707306ffa163a90b8a6a607197eec8364da3208f6fc71cf8a3d2a0e72f85904f",
    "docs/mainline/review-gated/R5/ordinary-improvement-v2/README.md": "dac05dde3e8be10ef2b6f00025d9b3bcde040fe20da1a27ce9128d4dadfb0888",
    "docs/mainline/review-gated/R5/ordinary-improvement-v2/qualification.md": "8665a75401b014c31572e22ee5b03b164e2aa446122939bfeda0f7537c556b23"
}
MODULES = {"src/aegis_dc/ordinary/"+n+".py" for n in (
    "__init__","policy","episode","archive","feedback","ledger","selection")}
TOOLS = {"scripts/"+n+".py" for n in (
    "ordinary_v2_identity","qualify_london_ordinary_v2","ordinary_v2_fixture_io",
    "ordinary_v2_witnesses","run_london_ordinary_v2")}
REQUIRED = set(PINS) | MODULES | TOOLS | {"scripts/qualify_ordinary_v2.slurm"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def oid(kind, data):
    return hashlib.sha1(kind.encode()+b" "+str(len(data)).encode()+b"\0"+data).hexdigest()


def children(raw):
    entries = {}
    i = 0
    while i < len(raw):
        end = raw.index(b"\0",i)
        mode,leaf = raw[i:end].split(b" ",1)
        child = raw[end+1:end+21]
        if len(child)!=20:
            raise ValueError("Truncated Git tree")
        entries[leaf] = (mode,child.hex())
        i = end+21
    return entries


def verify_source(root, manifest):
    if set(manifest["files"]) != REQUIRED:
        raise ValueError("Incomplete or unexpected source bundle")
    proof = manifest["git_proof"]
    commit = base64.b64decode(proof["commit"],validate=True)
    if oid("commit",commit)!=manifest["execution_revision"]:
        raise ValueError("Execution Git commit mismatch")
    first = commit.splitlines()[0].split()
    if first[0]!=b"tree":
        raise ValueError("Missing commit tree")
    root_oid = first[1].decode()
    trees = {}
    for expected,encoded in proof["trees"].items():
        raw=base64.b64decode(encoded,validate=True)
        if oid("tree",raw)!=expected:
            raise ValueError("Invalid Git tree proof")
        trees[expected]=children(raw)
    for name,meta in manifest["files"].items():
        pointer=root_oid
        parts=name.split("/")
        for i,part in enumerate(parts):
            mode,pointer=trees[pointer][part.encode()]
            if mode not in ((b"40000",) if i<len(parts)-1 else (b"100644",b"100755")):
                raise ValueError("Wrong Git object type: "+name)
        data=(root/name).read_bytes()
        actual=hashlib.sha256(data).hexdigest()
        if (pointer!=meta["blob"] or oid("blob",data)!=pointer or actual!=meta["sha256"]
                or len(data)!=meta["bytes"] or actual!=PINS.get(name,actual)):
            raise ValueError("Pinned execution byte mismatch: "+name)
