"""File identities and immutable V6/T2 sources for the T3 extension."""
from pathlib import Path
import hashlib
import json
import os
import sys

PK=Path(__file__).resolve().parent
ROOT=PK.parents[2]
T2=PK.parent/'t2-minute-facility-v1'
CORE=Path('/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source')
REMOTE=Path('/share/home/renly/renly-patrol-rsi/mainline/T3-prior-information-v2-20261121')
for path in (T2, T2/'production'):
    sys.path.insert(1,str(path))
from facility_inputs import templates, materialize

H=3600
CLOCK=tuple(range(0,H+1,60))
BIZ=(900,1800,2700,3600)
ROLES=('P','PERIODIC','ALARM','ORACLE')


def load(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def write(path,obj):
    with Path(path).open('x',encoding='utf8') as f:
        json.dump(obj,f,separators=(',',':'),ensure_ascii=False,allow_nan=False);f.write('\n')


def insist(ok,reason):
    if not ok:raise ValueError(reason)


def next_tick(t):
    return next((v for v in CLOCK if v>=t),None)


def slurm():
    insist(os.environ.get('SLURM_JOB_ID'),'Slurm allocation required')
    return os.environ['SLURM_JOB_ID']
