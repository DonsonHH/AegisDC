"""Stage immutable Git blobs; reserve one unique attempt before submitting Slurm."""
from pathlib import Path
from io import BytesIO
import hashlib,json,tarfile,subprocess,sys,shlex
from copy import deepcopy
p=Path('.work/v6-intake')
remote='/share/home/renly/renly-patrol-rsi/mainline/V6-intake-20261120'
attempt,mode=sys.argv[1:3]
assert attempt.isalnum() and mode in ('red','green','saved')
def git(*args):return subprocess.check_output(['git',*args])
def commit(rev):return git('rev-parse',rev).decode().strip()
def sha(b):return hashlib.sha256(b).hexdigest()
pin=commit('HEAD'); source=commit('b5a2e9ad') if mode=='red' else pin
old='evidence/mainline/engineering/39c-development/slice-53/green/joint/'
pack='docs/mainline/v6-intake-engineering-v1'
rs={}
for rev,paths in [(source,['src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py','configs/materials','configs/full-facility-mainline-reserve-v6.json']),
          (pin,['scripts/qualify_v6_intake.py',pack,old+'frozen-call-input.json',old+'public-decisions.json'])]:
    tree=git('ls-tree','-r',rev,'--',*paths).decode().splitlines()
    for row in tree:
        head,path=row.split('\t',1)
        if path not in rs:rs[path]=head.split()[-1]
# Read exact blobs in one batch, including explicit files from two Git identities for expected red.
unique=list(dict.fromkeys(rs.values()))
batch=subprocess.run(['git','cat-file','--batch'],input=('\n'.join(unique)+'\n').encode(),stdout=subprocess.PIPE,check=True).stdout
blobs={}; at=0
for oid in unique:
    newline=batch.index(b'\n',at); size=int(batch[at:newline].split()[-1]);at=newline+1
    blobs[oid]=batch[at:at+size];at+=size+1
meta=dict(execution_revision=source,checker_revision=pin,freeze_revision=commit('4539a48e'),attempt=attempt,mode=mode,
          files={k:sha(blobs[v]) for k,v in rs.items()},git_blobs=rs,
          interpreter_sha256='5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6')
manifest=(json.dumps(meta,indent=2)+'\n').encode()
folder=p/attempt;folder.mkdir()
archive=folder/'source.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for path,body in [(k,blobs[v]) for k,v in rs.items()]+[('source-manifest.json',manifest)]:
        info=tarfile.TarInfo(path); info.size=len(body);tar.addfile(info,BytesIO(body))
here=remote+'/'+attempt
extra=sys.argv[3:]
args=['/share/home/renly/miniconda3/bin/python','-B','scripts/qualify_v6_intake.py','--mode',mode,'--output',here+'/output','--source-manifest','source-manifest.json','--source-sha',sha(manifest)]+extra
job='''#!/bin/bash
#SBATCH --partition=cu
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --job-name=v6-intake
set -eu
umask 077
cd '''+shlex.quote(here+'/source')+'''
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1
hostname > ../compute-node
exec '''+shlex.join(args)+'\n'
(folder/'run.sh').write_bytes(job.encode())
(folder/'source-manifest.json').write_bytes(manifest)
def ssh(*args):
    return subprocess.check_output([sys.executable,'-B','.work/e14-20261115/remote.py',*args],text=True,encoding='utf-8').strip()
print(ssh('cmd',f'set -eu; umask 077; mkdir -p {remote}; mkdir {here}'),flush=True)
print(ssh('put',str(archive),here+'/source.tar.gz'),flush=True)
print(ssh('put',str(folder/'run.sh'),here+'/run.sh'),flush=True)
script=f'set -eu; umask 077; cd {here}; test "$(sha256sum source.tar.gz | cut -d\' \' -f1)" = "{sha(archive.read_bytes())}"; mkdir source; tar -xzf source.tar.gz -C source; sbatch --parsable -o {here}/slurm-%j.out -e {here}/slurm-%j.err run.sh'
jobid=ssh('cmd',script)
(folder/'submission.json').write_text(json.dumps(dict(job=jobid,root=here,manifest_sha256=sha(manifest),archive_sha256=sha(archive.read_bytes()),args=args),indent=2))
print(jobid, source, pin, here,flush=True)

