"""Locations, immutable input identities and exclusive, time-stamped return records."""
from pathlib import Path
import gzip
import hashlib
import json
import os
import sys

PK=Path(__file__).resolve().parent
ROOT=PK.parents[2]
T3=PK.parent/'t3-prior-information-v2'
T4=PK.parent/'t4a-public-risk-v1'
SRC=ROOT/'src'/'aegis_action_cost'
BASE=Path('/share/home/renly/renly-patrol-rsi/mainline')
ACT=BASE/'T4c-action-cost-development-v3'
CORE=BASE/'V6-cold-launch-release-v1'/'source'
OLD_BUNDLE=BASE/'T4a-public-risk-development-v1'/'public-only'
BUNDLE=ACT/'public-only'
BUNDLE_NAMES=('VSTAR','VSTAR_NOPROBE','V_COST','V_COST_NOPROBE','PA','B','BPLUS','P','PERIODIC','ALARM')
ROLES=(*BUNDLE_NAMES,'ORACLE')
sys.path[:0]=[str(PK),str(T3),str(T4),str(CORE/'src'),str(CORE/'scripts'),str(ROOT/'src')]


def read(path):return json.loads(Path(path).read_bytes())
def compact(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def hash_obj(v):return hashlib.sha256(compact(v)).hexdigest()
def sha(path):
    with Path(path).open('rb') as fp:return hashlib.file_digest(fp,'sha256').hexdigest()
def check(ok,msg):
    if not ok:raise ValueError(msg)
def write(path,value):
    with Path(path).open('xb') as fp:fp.write(compact(value)+b'\n')
def gzwrite(path,value):
    with Path(path).open('xb') as fp:fp.write(gzip.compress(compact(value)+b'\n',compresslevel=5,mtime=0))
def job():
    return os.environ['SLURM_JOB_ID']
def sealed_manifest(phase):
    lock=PK/'input-commitments.json'
    check(phase in ('eng','dev') and sha(lock)==os.environ['T4C_INPUT_LOCK'],'published complete input commitments')
    binding=read(lock);m=ACT/(phase+'-inputs')/'manifest.json'
    check(binding['source_freeze']==sha(PK/'freeze.json') and sha(m)==binding[phase]['manifest_sha256'],'pre-role complete manifest')
    result=read(m)
    check(result['purpose']==phase and result['source_freeze']==binding['source_freeze']
          and result['input_archive']==binding[phase]['archive_sha256'],'phase and input archive')
    return result
def pinned():
    job()
    f=read(PK/'freeze.json')
    for k,h in f['files'].items():check(sha(ROOT/k)==h,'registered byte identity: '+k)
    release=read(ROOT/'docs/mainline/v6-stage-three-cold-launch-v1/launch-manifest.json')
    for k,h in release['core_files'].items():check(sha(CORE/k)==h,'native source: '+k)
    check(sha(sys.executable)==release['python']['sha256'],'native interpreter')
    return f
