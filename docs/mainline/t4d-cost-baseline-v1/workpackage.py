"""Immutable identities and dedicated storage for the disclosed T4d work package."""
from pathlib import Path
import gzip
import hashlib
import json
import os
import sys

PK=Path(__file__).resolve().parent
ROOT=PK.parents[2]
C=PK.parent/'t4c-action-cost-v3'
T3=PK.parent/'t3-prior-information-v2'
T4A=PK.parent/'t4a-public-risk-v1'
BASE=Path('/share/home/renly/renly-patrol-rsi/mainline')
ACT=BASE/'T4d-cost-baseline-v1'
PREV=BASE/'T4c-action-cost-development-v3'
NATIVE=BASE/'V6-cold-launch-release-v1/source'
B_OLD=BASE/'T4a-public-risk-development-v1/public-only'
V_OLD=PREV/'public-only'
sys.path[:0]=[str(PK),str(C),str(T3),str(T4A),str(NATIVE/'src'),str(NATIVE/'scripts'),str(ROOT/'src')]


def must(test,message):
    if not test:raise ValueError(message)
def read(path):return json.loads(Path(path).read_bytes())
def unpack(path):
    with gzip.open(path,'rt',encoding='utf8') as f:return json.load(f)
def stable(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=True).encode()
def digest(obj):return hashlib.sha256(stable(obj)).hexdigest()
def filehash(path):
    with Path(path).open('rb') as fp:return hashlib.file_digest(fp,'sha256').hexdigest()
def save(path,data):
    with Path(path).open('xb') as fp:fp.write(stable(data)+b'\n')
def save_gz(path,data):
    with Path(path).open('xb') as fp:fp.write(gzip.compress(stable(data)+b'\n',compresslevel=5,mtime=0))
def job():return os.environ['SLURM_JOB_ID']
def spec():return read(PK/'settings-and-conditions.json')
def verify_source():
    job()
    must(filehash(PK/'source-manifest.json')==os.environ['T4D_SOURCE'],'published T4d source')
    m=read(PK/'source-manifest.json')
    for f,h in m['files'].items():must(filehash(ROOT/f)==h,'staged input/source '+f)
    release=read(PK.parent/'v6-stage-three-cold-launch-v1/launch-manifest.json')
    must(filehash(sys.executable)==release['python']['sha256'],'scientific interpreter')
    for f,h in release['core_files'].items():must(filehash(NATIVE/f)==h,'native runtime '+f)
    must(filehash(PREV/'dev-inputs/manifest.json')==filehash(C/'dev-manifest.json') and filehash(PREV/'development.json.gz')==filehash(C/'development.json.gz'),'immutable parent inputs and results')
    return release

def manifest():
    path=ACT/'inputs/manifest.json'
    must(filehash(path)==os.environ['T4D_INPUTS'],'pre-run publication of complete input identities')
    m=read(path)
    must(m['source']==os.environ['T4D_SOURCE'] and m['condition_list']==filehash(PK/'settings-and-conditions.json'),'settings binding')
    return m

def case_file(mode,key):return ACT/'inputs'/mode/(key+'.json')

def verify_bundle(folder,members):
    files={f.relative_to(folder).as_posix() for f in folder.rglob('*') if f.is_file()}
    must(files==set(members),'exact public import membership')
    for name,h in members.items():must(filehash(folder/name)==h,'public code '+name)
