"""Download only durable manifests, small per-arm endpoint summaries and attempt ledgers."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

base='/share/home/renly/renly-patrol-rsi/mainline/V6-native-method-qualification-20261120'
local=Path('.work/v6-compare-eng')
opts=['-o','StrictHostKeyChecking=yes','-o','BatchMode=yes','-o','ConnectTimeout=12']
def remote(command):
    return subprocess.check_output(['ssh',*opts,'myserver','bash -lc '+shlex.quote(command)])
def sha(b):return hashlib.sha256(b).hexdigest()
def write(path,b):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=b:raise ValueError('Existing receipt differs: '+str(path))
    if not path.exists():path.write_bytes(b)
def collect(attempt):
    folder=local/attempt
    info=json.loads((folder/'submission.json').read_bytes())
    job=info['job'];assert job.isdigit()
    here=base+'/'+attempt
    accounting=remote('sacct -nP -j '+job+' -o JobID,State,ExitCode,NodeList,AllocCPUs,ReqMem,ElapsedRaw,TotalCPU,MaxRSS,Start,End,Timelimit')
    main=accounting.decode().strip().splitlines()[0].split('|')
    if main[1] not in ('COMPLETED','FAILED','TIMEOUT','CANCELLED'):raise ValueError('No terminal status: '+str(main))
    files=['launch.json','submitted-job','compute-node','slurm-'+job+'.out','slurm-'+job+'.err','output/report.json','output/durable-files.json']
    if attempt!='red01':
        files+=['terminal-account.json','output/native/ledger.json','output/native/events.jsonl','output/native/saved-evaluation.json']
    if attempt=='initial01':
        files+=['output/substitute-Z4/injected-batch/ledger.json','output/substitute-Z4/injected-batch/events.jsonl']
    directory=folder/'collected'
    def get(names):
        received=remote(shlex.join(['tar','-C',here,'-cf','-',*names]))
        with tarfile.open(fileobj=BytesIO(received),mode='r:') as archive:
            found={}
            for member in archive:
                if member.name not in names or not member.isfile():raise ValueError('Unexpected archive element')
                b=archive.extractfile(member).read(); write(directory/member.name,b);found[member.name]=sha(b)
        if set(found)!=set(names):raise ValueError('Missing archived summary')
        return found
    hashes=get(files)
    catalog=json.loads((directory/'output/durable-files.json').read_bytes()); report=json.loads((directory/'output/report.json').read_bytes())
    if report['durable_manifest_sha256']!=hashes['output/durable-files.json']:raise ValueError('Durable manifest identity differs')
    scores=['output/'+path for path in catalog if path.startswith('native/') and path.endswith('/score.json')]
    if scores:hashes.update(get(scores))
    for path,h in hashes.items():
        if path.startswith('output/') and path[7:] in catalog and catalog[path[7:]]['sha256']!=h:raise ValueError(path)
    identity_names=['source.tar.gz',*files]
    raw=remote('cd '+shlex.quote(here)+' && '+shlex.join(['sha256sum',*identity_names])).decode()
    server={line[66:]:line[:64] for line in raw.splitlines()}
    if server['source.tar.gz']!=sha((folder/'source.tar.gz').read_bytes()) or server['launch.json']!=info['launch_sha256']:
        raise ValueError('Published source archive drift')
    if any(server[k]!=hashes[k] for k in files):raise ValueError('Transferred summary differs')
    write(directory/'retrieval.json',(json.dumps(dict(remote=here,job=job,sacct_fields='JobID|State|ExitCode|NodeList|AllocCPUs|ReqMem|ElapsedRaw|TotalCPU|MaxRSS|Start|End|Timelimit',sacct=accounting.decode().strip().splitlines(),server_sha256=server,downloaded_sha256=hashes),indent=2)+'\n').encode())
    print(attempt,main[:8],len(scores),report['public_returned'],report['facility_returned'],report['internal_policy_known'],report.get('passed'))
for name in sys.argv[1:]:collect(name)
