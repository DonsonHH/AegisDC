"""Read-only retrieval of the completed verification receipts. Raw copied runs stay on shared storage."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[3]
LOCAL=ROOT/'.work/v6-launch-ready/attempt01'
OPTS=['-o','StrictHostKeyChecking=yes','-o','BatchMode=yes','-o','ConnectTimeout=12']


def ssh(text):return subprocess.check_output(['ssh',*OPTS,'myserver','bash -lc '+shlex.quote(text)])
def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    submission=json.loads((LOCAL/'submission.json').read_bytes());job=submission['job'];root=submission['activity']
    if not job.isdecimal():raise ValueError('Unbound scheduler identity')
    fields='JobID,JobName,Partition,State,ExitCode,NodeList,AllocCPUs,ReqMem,ElapsedRaw,TotalCPU,Start,End,Timelimit'
    accounting=ssh('sacct -nP -j '+job+' -o '+fields).decode().strip().splitlines()
    state=accounting[0].split('|')
    if state[0]!=job or state[3] not in ('COMPLETED','FAILED','TIMEOUT','CANCELLED'):raise ValueError('Wait for the same terminal job')
    files=['launch.json','submitted-job','compute-node','slurm-'+job+'.out','slurm-'+job+'.err','output/report.json','output/durable-files.json']
    small=['output/sites/'+x+'/surrogate-transport.json' for x in ('J1','J2','J3','J4','H1')]
    small+=['output/sites/'+x+'/V6-native-method-study-v1/'+y for x in ('J1','J2','J3','J4','H1') for y in ('progress.json','halt.json')]
    small+=['output/sites/H1/truncation-proof.json','output/sites/J1-receipt-only/evidence-loss-readback.json','output/sites/J4/review-addendum-results.json']
    # Qualifying a refusal can leave some evidence absent. Keep the failure without inventing a file.
    existing=ssh('cd '+shlex.quote(root)+' && for f in '+shlex.join(small)+'; do if test -f "$f"; then echo "$f"; fi; done').decode().splitlines()
    files+=existing
    seen={}
    tar_data=ssh(shlex.join(['tar','-C',root,'-cf','-',*files]))
    dest=LOCAL/'returned';dest.mkdir(exist_ok=True)
    with tarfile.open(fileobj=BytesIO(tar_data)) as tar:
        for item in tar:
            if not item.isfile() or item.name not in files:raise ValueError('Unexpected transfer entry')
            data=tar.extractfile(item).read();target=dest/item.name;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and target.read_bytes()!=data:raise ValueError('Refusing to replace a previous receipt')
            if not target.exists():target.write_bytes(data)
            seen[item.name]=sha(data)
    if set(seen)!=set(files):raise ValueError('Missing transfer')
    lines=ssh('cd '+shlex.quote(root)+' && '+shlex.join(['sha256sum','source.tar.gz',*files])).decode().splitlines()
    server={line[66:]:line[:64] for line in lines}
    if server['source.tar.gz']!=sha((LOCAL/'source.tar.gz').read_bytes()) or any(server[k]!=v for k,v in seen.items()):
        raise ValueError('Durable asset changed during retrieval')
    report=json.loads((dest/'output/report.json').read_bytes());catalog=json.loads((dest/'output/durable-files.json').read_bytes())
    if report['durable_manifest_sha256']!=seen['output/durable-files.json'] or report['launch_sha256']!=seen['launch.json']:
        raise ValueError('Return or launch identity differs')
    for name in existing:
        if catalog[name.removeprefix('output/')]['sha256']!=seen[name]:raise ValueError('Declared evidence mismatch: '+name)
    receipt=dict(job=job,private_root=root,sacct_fields=fields,sacct=accounting,server_sha256=server,downloaded=seen)
    with (dest/'retrieval.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(receipt,f,indent=2);f.write('\n')
    print(state[0],state[3:10],len(files),len(catalog),report.get('passed'),report['unexecuted'])

if __name__=='__main__':main()
