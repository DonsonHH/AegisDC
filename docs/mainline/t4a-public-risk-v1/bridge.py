"""Trusted host adapter: a new closed public-only interpreter per position."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PK=Path(__file__).resolve().parent
ROOT=PK.parents[2]
T3=PK.parent/'t3-prior-information-v2'
ACTIVITY=Path('/share/home/renly/renly-patrol-rsi/mainline/T4a-public-risk-development-v1')
CORE=Path('/share/home/renly/renly-patrol-rsi/mainline/V6-cold-launch-release-v1/source')
PREVIOUS=Path('/share/home/renly/renly-patrol-rsi/mainline/T3-prior-information-v2-20261121')
BUNDLE=ACTIVITY/'public-only'
ARMS=('V1','V2','V3','PA','B')
SHIM=b'H=3600\nCLOCK=tuple(range(0,3601,60))\nBIZ=(900,1800,2700,3600)\ndef next_tick(t):return next((v for v in CLOCK if v>=t),None)\n'
def read(p):return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def packed(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(v):return hashlib.sha256(packed(v)).hexdigest()
def require(ok,label):
    if not ok:raise ValueError(label)
def write(p,v):
    with Path(p).open('xb') as f:f.write(packed(v)+b'\n')


def inputs():
    return read(T3/'development-inputs.json')


def frozen():
    require(os.environ.get('SLURM_JOB_ID'),'Slurm allocation required')
    m=read(PK/'freeze.json')
    for k,h in m['files'].items():require(sha(ROOT/k)==h,'source/data '+k)
    pin=read(ROOT/'docs/mainline/v6-stage-three-cold-launch-v1/launch-manifest.json')
    require(sha(Path(sys.executable))==pin['python']['sha256'],'interpreter')
    for k,h in pin['core_files'].items():require(sha(CORE/k)==h,'frozen facility '+k)
    require(sha(PREVIOUS/'development-inputs/manifest.json')==sha(T3/'development-inputs.json') and
            sha(PREVIOUS/'development-result.json.gz')==sha(T3/'development-result.json.gz'),'previous panel')
    return m,pin


def bundle_files(m):
    members={name.removeprefix('src/'):h for name,h in m['files'].items() if name.startswith('src/aegis_risk_dispatch/')}
    members['common.py']=hashlib.sha256(SHIM).hexdigest()
    members['public_work.py']=m['files'][(T3.relative_to(ROOT)/'public_work.py').as_posix()]
    for n in ('__init__.py','joint_messages.py','joint_evidence.py','joint_resources.py'):
        members['aegis_dc/'+n]=m['files']['src/aegis_dc/'+n]
    return members


def check_bundle(m,create=False):
    members=bundle_files(m)
    if create:
        BUNDLE.mkdir()
        for name in members:
            path=BUNDLE/name;path.parent.mkdir(exist_ok=True)
            if name=='common.py':b=SHIM
            elif name=='public_work.py':b=(T3/name).read_bytes()
            else:b=(ROOT/'src'/name).read_bytes()
            with path.open('xb') as f:f.write(b)
    require({f.relative_to(BUNDLE).as_posix() for f in BUNDLE.rglob('*') if f.is_file()}==set(members),'public folder exact membership')
    for n,h in members.items():require(sha(BUNDLE/n)==h,'public bundle '+n)
    return digest(members)


class PublicProcess:
    def __init__(self,role,stderr_path):
        require(role in ARMS,'public role')
        self.role=role;self.stderr=Path(stderr_path).open('x')
        self.child=subprocess.Popen([sys.executable,'-I','-S','-B',str(BUNDLE/'aegis_risk_dispatch/worker.py'),role],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,cwd=BUNDLE,
            env={'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1'})
        self.static=None;self.events=[]
    def message(self,val):
        self.child.stdin.write(packed(val)+b'\n');self.child.stdin.flush()
        line=self.child.stdout.readline()
        if not line:raise RuntimeError('public worker terminated before a response')
        return json.loads(line)
    def choose(self,pub,view,role,plan):
        require(role==self.role and not plan,'no external plan may enter dispatch')
        static=digest(pub)
        if self.static is None:
            require(self.message({'public':pub})=={'ready':True,'role':role},'public handshake');self.static=static
        require(static==self.static,'static public configuration changed')
        result=self.message({'view':view})
        self.events.append([view['time'],digest(view),digest(result)])
        return result
    def close(self,failed=False):
        if self.child.poll() is None:
            try:self.child.stdin.write(b'{"close":true}\n');self.child.stdin.flush()
            except BrokenPipeError:pass
        self.child.stdin.close();ret=self.child.wait(timeout=15)
        self.child.stdout.close();self.stderr.close()
        if not failed:require(ret==0,'worker exit status')
