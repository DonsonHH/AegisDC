"""Stage the pinned runtime, fresh role mounts and engineering-only preflight on the scoring host."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import sandbox

PY = Path("/share/home/renly/miniconda3")
PARENT = Path("/share/home/renly/renly-patrol-rsi/mainline/T4c-action-cost-development-v3/public-only")
PK = Path(__file__).resolve().parent
R1 = PK.parents[1]/"r1"
ROOT = PK.parents[4]
BASE = Path("/share/home/renly/renly-patrol-rsi/mainline/T8-stage1b-procedural-v1")
STUDY = BASE/"scoring"


def require(test,why):
    if not test:raise ValueError(why)


def compact(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()


def read(path):
    return json.loads(Path(path).read_bytes())


def save(path,obj):
    with Path(path).open("xb") as f:
        f.write(compact(obj)+b"\n");f.flush();os.fsync(f.fileno())


def pinned_copy(src,dest,expected=None,executable=False):
    src,dest=Path(src),Path(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    require(not dest.exists(),"immutable staging collision")
    with src.open("rb") as r,dest.open("xb") as w:shutil.copyfileobj(r,w)
    if expected is not None:require(sandbox.filehash(dest)==expected,"staged source hash")
    dest.chmod(0o555 if executable else 0o444)


def build_image():
    os.umask(0o022)
    lock=read(PK/"source-lock.json")
    require(sandbox.filehash(PK/"source-lock.json")==os.environ["T8_IMAGE_SOURCE"],"image source manifest")
    version=STUDY/"images"/os.environ["T8_IMAGE_SOURCE"]
    version.mkdir(parents=True,exist_ok=False)
    image=version/"image"
    image.mkdir(mode=0o755,exist_ok=False)
    require({p.relative_to(PARENT).as_posix() for p in PARENT.rglob("*") if p.is_file()}==
            set(lock["public_members"]), "original parent bundle membership")
    for group,src_root,out_root in (("public_members",PARENT,image/"parent"),
                                    ("core_members",Path(sandbox.CORE),image/"core"),
                                    ("native_members",ROOT,image/"native")):
        for name,h in lock[group].items():pinned_copy(src_root/name,out_root/name,h)
    for name in ("public_roles.py","access_audit.py","native_role.py"):
        pinned_copy(PK/name,image/"code"/name,lock["scoring_files"][name])
    pinned_copy(R1/"fit_program.py",image/"code/fit_program.py",lock["r1_files"]["fit_program.py"])
    runtime=image/"runtime"
    py=runtime/"py"
    pinned_copy(PY/"bin/python",py/"bin/python3.13",lock["native_python"],True)
    pinned_copy("/usr/bin/setpriv",py/"bin/setpriv",executable=True)
    stdlib=PY/"lib/python3.13"
    for folder,dirs,files in os.walk(stdlib):
        dirs[:]=[d for d in dirs if d not in ("site-packages","__pycache__","test","tests","idlelib","tkinter","turtledemo","ensurepip")]
        for name in files:
            if name.endswith((".py",".so")):
                src=Path(folder)/name
                pinned_copy(src,py/"lib/python3.13"/src.relative_to(stdlib))
    extensions=stdlib/"lib-dynload"
    inspect=[PY/"bin/python",Path("/usr/bin/setpriv")]
    for prefix in ("_hashlib","zlib","_bz2","_lzma","_socket","_ssl","_decimal","_ctypes","math","binascii","_uuid"):
        inspect.extend(extensions.glob(prefix+".*.so"))
    site=stdlib/"site-packages"
    for src in (site/"cryptography").rglob("*"):
        if src.is_file() and src.suffix in (".py",".so") and "__pycache__" not in src.parts:
            pinned_copy(src,image/"audit-crypto"/src.relative_to(site))
            if src.suffix==".so":inspect.append(src)
    for src in site.glob("_cffi_backend*.so"):
        pinned_copy(src,image/"audit-crypto"/src.name)
        inspect.append(src)
    env=dict(os.environ,LC_ALL="C")
    linked=subprocess.check_output(["ldd",*map(str,inspect)],text=True,env=env)
    require("not found" not in linked,"missing runtime shared library")
    libraries={}
    for line in linked.splitlines():
        m=re.match(r"^\s*(?:(\S+)\s+=>\s+)?(/\S+)\s+\(",line)
        if m:
            source=Path(m[2]).resolve()
            name=m[1] or Path(m[2]).name
            target=py/"lib"/name if source.is_relative_to(PY) else runtime/"syslib"/name
            if target in libraries:require(source==libraries[target],"ambiguous runtime dependency")
            libraries[target]=source
    for dest,src in libraries.items():pinned_copy(src,dest,executable=True)
    (image/"policy.bpf").write_bytes(sandbox.filter_bytes())
    for p in [image,*image.rglob("*")]:
        if p.is_dir():p.chmod(0o755)
    manifests={p.relative_to(image).as_posix():sandbox.filehash(p) for p in image.rglob("*") if p.is_file()}
    save(version/"image-manifest.json",manifests)
    print("STAGED",len(manifests),"runtime and source files",hashlib.sha256(compact(manifests)).hexdigest())


def copy_for_job(scratch):
    image=scratch/"image"
    version=STUDY/"images"/os.environ["T8_IMAGE_SOURCE"]
    manifests=read(version/"image-manifest.json")
    require(os.environ["T8_IMAGE"]==hashlib.sha256(compact(manifests)).hexdigest(),"published runtime image identity")
    shutil.copytree(version/"image",image)
    actual={p.relative_to(image).as_posix():sandbox.filehash(p) for p in image.rglob("*") if p.is_file()}
    require(actual==manifests,"job-local image readback")
    credential=scratch/"audit-credential"
    shutil.copyfile(STUDY/"technical-keys"/"audit",credential)
    credential.chmod(0o400)
    return image


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage",action="store_true",required=True)
    p.parse_args()
    build_image()
