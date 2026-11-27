"""Construct a transfer containing only frozen code, public controls and consumed development summaries."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
REL=HERE.relative_to(ROOT).as_posix()
PARENT="docs/mainline/t11-eswa-revision/"
T11_0="e3484fd1967164bfb3fe7b5d9c0309e513e95444"
INTERPRETATION="c41ab91096c25399b24193f652dbb8b0b9d39ebd"
PROTOCOL="8dfc03a7c1df9c254f246e1d40add424a0c04218ffdd345acc2b05ade6dc7284"
SOURCES=("operations.py","runner.py","control.py","center_timing.py","native_readback.py",
         "analysis.py","worker.py","baselines.py","pomcp.py","qualification.py","account.py","qualification_session.py")
NORMATIVE=("protocol-freeze.json","protocol-addendum.md","protocol-lock.json","supplement-protocol.md",
           "method-formalization.md","design.json")

def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)

def blob(rev,path):
    return git("cat-file","blob",rev+":"+path)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def build_sources(revision):
    data={}
    pins={}
    def add(target,source_rev,path):
        data[target]=blob(source_rev,path)
        pins[target]=[source_rev,path]
    for name in SOURCES:
        add("source/"+name,revision,REL+"/"+name)
    add("source/stage0-identity.json",INTERPRETATION,REL+"/stage0-identity.json")
    add("references/interpretation-before-run.md",INTERPRETATION,REL+"/interpretation-before-run.md")
    add("registration.json",revision,REL+"/registration.json")
    for name in NORMATIVE:add("references/"+name,T11_0,PARENT+name)
    design=json.loads(data["references/design.json"])
    p=design["panel"]
    add("references/original-dev-manifest.json",p["input_revision"],p["manifest"])
    add("references/development.json.gz",p["score_revision"],p["scores"])
    add("references/baseline-freeze.json","cef45c0275ce330eaf2652362bfd5090dffd5aa6","docs/mainline/t4c-action-cost-v3/v-double-star-freeze.json")
    add("references/launch-manifest.json",T11_0,"docs/mainline/v6-stage-three-cold-launch-v1/launch-manifest.json")
    if digest(data["references/protocol-freeze.json"])!=PROTOCOL:raise ValueError("v1.1 protocol")
    m=dict(schema="T11-1-frozen-implementation-bundle-v1",implementation_revision=revision,
           accepted_parent=T11_0,interpretation_commit=INTERPRETATION,protocol_sha256=PROTOCOL,
           file_origins=pins,files={k:digest(v) for k,v in sorted(data.items())})
    return m,data

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("revision")
    p.add_argument("--write-lock",action="store_true")
    p.add_argument("--archive",type=Path)
    args=p.parse_args()
    rev=git("rev-parse","--verify",args.revision+"^{commit}").decode().strip()
    m,data=build_sources(rev)
    encoded=(json.dumps(m,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode()
    output=HERE/"source-manifest.json"
    if args.write_lock:
        with output.open("xb") as out:out.write(encoded)
    if output.read_bytes()!=encoded:raise ValueError("source manifest mismatch")
    data["source-manifest.json"]=encoded
    if args.archive:
        with tarfile.open(args.archive,"x:gz") as archive:
            for name,content in sorted(data.items()):
                member=tarfile.TarInfo(name);member.size=len(content);member.mode=0o444;member.mtime=0
                archive.addfile(member,io.BytesIO(content))
    print(digest(encoded),rev,len(m["files"]))

if __name__=="__main__":main()
