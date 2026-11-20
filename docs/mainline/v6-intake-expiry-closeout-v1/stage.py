"""Stage exact committed files for one explicitly budgeted Slurm attempt."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

PACK = 'docs/mainline/v6-intake-expiry-closeout-v1'
ROOT = Path(__file__).resolve().parents[3]
ACTIVITY = '/share/home/renly/renly-patrol-rsi/mainline/V6-intake-expiry-closeout-20261120'
FREEZE = 'd456ee0b13ad5a3da6d1d8236bf9405fda8c45a5'
PYTHON_SHA = '5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6'
SSH = ['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12']


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def ssh(script):
    return subprocess.check_output(['ssh',*SSH,'myserver','bash -lc '+shlex.quote(script)],text=True).strip()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    options=argparse.ArgumentParser()
    options.add_argument('attempt',choices=['01','02','03'])
    options.add_argument('--only',nargs='+',choices=['original','T1','T2','T3','T4','revision','direct_horizon','received','reference_opportunity'])
    args=options.parse_args()
    if (args.attempt=='01') != (args.only is None) or args.only and len(set(args.only))!=len(args.only):
        raise ValueError('Start once with the full list; specify affected units on a reviewed retry')
    pin=git('rev-parse','HEAD').decode().strip()
    freeze_bytes=git('cat-file','blob',FREEZE+':'+PACK+'/freeze.json')
    freeze=json.loads(freeze_bytes)
    scientific=freeze['baseline']
    runtime=['src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py']
    if git('diff','--name-only',scientific,pin,'--',*runtime) or git('cat-file','blob',pin+':'+PACK+'/freeze.json')!=freeze_bytes:
        raise ValueError('Runtime or frozen expectations differ; stop for review')
    directory=ROOT/'.work/v6-expiry-closeout'/('attempt'+args.attempt)
    directory.mkdir(parents=True)
    archive=directory/'source.tar.gz'
    git('archive','--format=tar.gz','--output='+str(archive),pin,'--',*runtime,PACK,
        'scripts/qualify_v6_intake_expiry.py',*sorted(freeze['public_source_sha256']))
    with tarfile.open(archive,'r:gz') as source:
        files={item.name:digest(source.extractfile(item).read()) for item in source if item.isfile()}
    where=ACTIVITY+'/attempt'+args.attempt
    launch=dict(schema='aegisdc-v6-expiry-launch-v1',checker_revision=pin,baseline=scientific,freeze_revision=FREEZE,
        freeze_sha256=digest(freeze_bytes),python_sha256=PYTHON_SHA,archive_sha256=digest(archive.read_bytes()),files=files,
        attempt=args.attempt,output=where+'/output',selection=args.only,resources=freeze['budget'])
    manifest=directory/'launch.json'
    manifest.write_bytes((json.dumps(launch,indent=2)+'\n').encode())
    ssh('set -eu; umask 077; mkdir -p '+ACTIVITY+'; mkdir '+where)
    for path in (archive,manifest):
        subprocess.run(['scp',*SSH,str(path),'myserver:'+where+'/'+path.name],check=True)
    launch_sha=digest(manifest.read_bytes())
    script='set -eu; umask 077; cd '+where+'; '
    for path,expected in [('source.tar.gz',launch['archive_sha256']),('launch.json',launch_sha)]:
        script+='test "$(sha256sum '+path+' | cut -d\' \' -f1)" = '+expected+'; '
    script+='mkdir source; tar -xzf source.tar.gz -C source; '
    command=['sbatch','--parsable','--output='+where+'/slurm-%j.out','--error='+where+'/slurm-%j.err',
             'source/'+PACK+'/run.sbatch',launch_sha]
    if args.only:
        command+=['--only',*args.only]
    script+='job=$('+shlex.join(command)+'); echo "$job" | tee submitted-job'
    job=ssh(script)
    receipt=dict(job=job,remote=where,launch_sha256=launch_sha,source_archive_sha256=launch['archive_sha256'],command=command)
    (directory/'submission.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode())
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':
    main()
