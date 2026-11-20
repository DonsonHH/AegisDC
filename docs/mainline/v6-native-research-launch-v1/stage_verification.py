"""Transfer exact Git blobs and submit the single budgeted launch-verification allocation."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[3]
PACK='docs/mainline/v6-native-research-launch-v1'
OLD='docs/mainline/v6-native-comparison-qualification-v1'
BASE='984071352142239201e3b69a449207ec35cd7cfa'
FREEZE='4daac1bcd467dc1ac7cb785946025f76a8da888e'
ACTIVITY='/share/home/renly/renly-patrol-rsi/mainline/V6-research-launch-verification-20261120'
OPTS=['-o','StrictHostKeyChecking=yes','-o','BatchMode=yes','-o','ConnectTimeout=12']


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def blob(rev,path):return git('cat-file','blob',rev+':'+path)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def ssh(command):return subprocess.check_output(['ssh',*OPTS,'myserver','bash -lc '+shlex.quote(command)],text=True).strip()


def main():
    pin=git('rev-parse','HEAD').decode().strip()
    freeze=json.loads(blob(FREEZE,PACK+'/freeze.json'))
    manifest_raw=blob(pin,PACK+'/research-manifest.json')
    manifest=json.loads(manifest_raw)
    inputs=['src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py','configs/materials',
            PACK,'scripts/v6_research_launch.py','scripts/v6_research','docs/mainline/v6-native-method-comparison-v1',
            OLD+'/acceptance-20261120.json',OLD+'/research-manifest.json',OLD+'/result.json',
            'docs/mainline/v6-intake-engineering-v1/inputs.json','docs/mainline/v6-intake-engineering-v1/input-binding-addendum.json']
    tree=git('ls-tree','-r',pin,'--',*inputs).decode().splitlines()
    objs={row.split('\t',1)[1]:row.split('\t',1)[0].split()[-1] for row in tree}
    oids=list(dict.fromkeys(objs.values()))
    stream=BytesIO(subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(oids)+'\n').encode(),cwd=ROOT))
    hashes={}
    for oid in oids:
        current,kind,size=stream.readline().decode().split()
        if current!=oid or kind!='blob':raise ValueError('Bad Git identity')
        hashes[oid]=sha(stream.read(int(size)));stream.read(1)
    files={name:hashes[oid] for name,oid in objs.items()}
    for name,expected in (manifest['runtime_and_material_sha256']|manifest['launcher_sha256']|freeze['source_inputs']).items():
        if files[name]!=expected:raise ValueError('Staging changed '+name)
    if files[PACK+'/freeze.json']!=sha(blob(FREEZE,PACK+'/freeze.json')):raise ValueError('Original freeze changed')
    local=ROOT/'.work/v6-launch-ready/attempt01';local.mkdir(parents=True)
    where=ACTIVITY+'/attempt01'
    if manifest['release_root']!=where+'/source':raise ValueError('Unexpected release root')
    archive=local/'source.tar.gz'
    git('archive','--format=tar.gz','--output='+str(archive),pin,'--',*inputs)
    info=dict(schema='aegisdc-launch-readiness-scheduled-verification-v1',purpose='PUBLIC_LAUNCH_SURROGATE',source_revision=pin,
        freeze_revision=FREEZE,freeze_sha256=files[PACK+'/freeze.json'],manifest_sha256=sha(manifest_raw),
        readied_launch_revision=manifest['launch_source_revision'],python_sha256=manifest['python']['sha256'],
        review_addendum_sha256=files[PACK+'/review-addendum.json'],scheduler_budget=freeze['budget'],
        source_archive_sha256=sha(archive.read_bytes()),output=where+'/output',files=files)
    launch=local/'launch.json';launch.write_bytes((json.dumps(info,indent=2)+'\n').encode());lh=sha(launch.read_bytes())
    ssh('set -eu; umask 077; mkdir '+ACTIVITY+'; mkdir '+where)
    for f in (archive,launch):
        subprocess.run(['scp',*OPTS,str(f),'myserver:'+where+'/'+f.name],check=True)
    script='set -eu; umask 077; cd '+where+'; '
    for name,digest in [('source.tar.gz',info['source_archive_sha256']),('launch.json',lh)]:
        script+='test "$(sha256sum '+name+' | cut -d\' \' -f1)" = '+digest+'; '
    script+='mkdir source; tar -xzf source.tar.gz -C source; '
    command=['sbatch','--parsable','--output='+where+'/slurm-%j.out','--error='+where+'/slurm-%j.err','source/'+PACK+'/verify.sbatch',lh]
    job=ssh(script+'job=$('+shlex.join(command)+'); echo "$job" | tee submitted-job')
    receipt=dict(job=job,activity=where,manifest_sha256=sha(manifest_raw),launch_sha256=lh,source_sha256=info['source_archive_sha256'],command=command)
    (local/'submission.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode())
    print(json.dumps(receipt))

if __name__=='__main__':main()
