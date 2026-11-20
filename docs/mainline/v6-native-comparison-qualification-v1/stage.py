"""Stage immutable Git blobs, one exclusive Slurm directory per authorized attempt."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[3]
PACK='docs/mainline/v6-native-comparison-qualification-v1'
FREEZE='5836f0f17c7189a5782835647181713a19ee68f1'
BASE='53cc32b93dd62c8ce5ffd725eed9afba167557e5'
ACTIVITY='/share/home/renly/renly-patrol-rsi/mainline/V6-native-method-qualification-20261120'
INTERPRETER='5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6'
OPTS=['-o','StrictHostKeyChecking=yes','-o','BatchMode=yes','-o','ConnectTimeout=12']

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def ssh(command):return subprocess.check_output(['ssh',*OPTS,'myserver','bash -lc '+shlex.quote(command)],text=True).strip()
def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_bytes())

def main():
    mode=sys.argv[1]
    if mode not in ('red','initial','repair'):raise ValueError('Unknown attempt')
    name={'red':'red01','initial':'initial01','repair':'repair01'}[mode]
    folder=ROOT/'.work/v6-compare-eng'/name
    pin=git('rev-parse','HEAD').decode().strip()
    runtime=BASE if mode=='red' else pin
    f=json.loads(git('cat-file','blob',FREEZE+':'+PACK+'/fixtures.json'))
    contract=json.loads(git('cat-file','blob',FREEZE+':'+PACK+'/freeze.json'))
    units={k:[u.get('unit',u.get('id')) for u in f[k]] for k in ('public','facilities','fixtures')}
    if mode=='red':
        units={k:[] for k in units}
    elif mode=='repair':
        selected=read(Path(sys.argv[2]))
        if not selected.get('reason') or not selected.get('prior_report_sha256'):
            raise ValueError('Repair requires a recorded change and the previous terminal evidence')
        for k,items in units.items():
            if not set(selected['units'][k])<=set(items):raise ValueError('Repair exceeds frozen scope')
        units=selected['units']
    specs={}
    def add(revision,paths):
        tree=git('ls-tree','-r',revision,'--',*paths).decode().splitlines()
        for line in tree:
            desc,path=line.split('\t',1);specs[path]=desc.split()[-1]
    add(runtime,['src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py','configs/materials'])
    add(pin,[PACK,'scripts/qualify_native_comparison.py','docs/mainline/v6-native-method-comparison-v1/conditions.json',*f['source_sha256']])
    ids=list(dict.fromkeys(specs.values()))
    stream=BytesIO(subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(ids)+'\n').encode(),cwd=ROOT))
    blobs={}
    for oid in ids:
        current,kind,size=stream.readline().decode().split()
        if current!=oid or kind!='blob':raise ValueError('Bad Git archive')
        blobs[oid]=stream.read(int(size));stream.read(1)
    hashes={k:sha(blobs[v]) for k,v in specs.items()}
    for k,v in contract['files'].items():
        if hashes[k]!=v:raise ValueError('Frozen oracle or inputs drift: '+k)
    folder.mkdir(parents=True)
    where=ACTIVITY+'/'+name
    archive=folder/'source.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for path,oid in specs.items():
            body=blobs[oid];info=tarfile.TarInfo(path);info.size=len(body);tar.addfile(info,BytesIO(body))
    launch=dict(mode=mode,purpose='PUBLIC_ENGINEERING',research_execution=False,units=units,implementation_revision=runtime,
        checker_revision=pin,freeze_revision=FREEZE,protocol_revision=BASE,python_sha256=INTERPRETER,output=where+'/output',
        files=hashes,archive_sha256=sha(archive.read_bytes()),budget=f['scope'])
    if mode=='repair':launch['repair']=selected
    path=folder/'launch.json';path.write_bytes((json.dumps(launch,indent=2)+'\n').encode());lh=sha(path.read_bytes())
    ssh('set -eu; umask 077; mkdir -p '+ACTIVITY+'; mkdir '+where)
    for file in (archive,path):
        subprocess.run(['scp',*OPTS,str(file),'myserver:'+where+'/'+file.name],check=True)
    cmd='set -eu; umask 077; cd '+where+'; '
    for fn,h in [('source.tar.gz',launch['archive_sha256']),('launch.json',lh)]:
        cmd+='test "$(sha256sum '+fn+' | cut -d\' \' -f1)" = '+h+'; '
    cmd+='mkdir source; tar -xzf source.tar.gz -C source; '
    submit=['sbatch','--parsable','--output='+where+'/slurm-%j.out','--error='+where+'/slurm-%j.err','source/'+PACK+'/run.sbatch',lh]
    job=ssh(cmd+'job=$('+shlex.join(submit)+'); echo "$job" | tee submitted-job')
    receipt=dict(job=job,where=where,source_revision=runtime,launch_sha256=lh,source_sha256=launch['archive_sha256'],submit=submit)
    (folder/'submission.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode())
    print(json.dumps(receipt))

if __name__=='__main__':
    main()
