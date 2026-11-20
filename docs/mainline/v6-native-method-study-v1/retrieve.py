"""Read the locked native panel or retained stop. Transfer journals, compact scores and selected actual stages."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
L=ROOT/'docs/mainline/v6-native-research-launch-v1/research-manifest.json'
REVIEW='288c325fcba196c0eab3426a0e10730d13d77bd0'
CONTROL='/share/home/renly/renly-patrol-rsi/mainline/launch-receipts/v6-study-'+REVIEW[:12]
OPTS=['-o','StrictHostKeyChecking=yes','-o','BatchMode=yes','-o','ConnectTimeout=12']


def ssh(script, stdin=None):
    return subprocess.check_output(['ssh',*OPTS,'myserver','bash -lc '+shlex.quote(script)],input=stdin)


def sha(data):return hashlib.sha256(data).hexdigest()
def get(path):return json.loads(path.read_bytes())
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('Conflicting evidence: '+str(path))
    else:path.write_bytes(data)


def transfer(remote, wanted, local):
    # All names originate in the frozen panel or a recorded decimal Slurm ID.
    choices=shlex.join(wanted)
    names=ssh('cd '+shlex.quote(remote)+' && for f in '+choices+'; do if test -f "$f"; then echo "$f"; fi; done').decode().splitlines()
    if not names:return {}
    archive=ssh(shlex.join(['tar','-C',remote,'-cf','-',*names]))
    got={}
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        for member in tar:
            if not member.isfile() or member.name not in names:raise ValueError('Unexpected transfer member')
            data=tar.extractfile(member).read();save(local/member.name,data);got[member.name]=sha(data)
    checked=ssh('cd '+shlex.quote(remote)+' && '+shlex.join(['sha256sum',*names])).decode().splitlines()
    actual={line[66:]:line[:64] for line in checked}
    if got!=actual or set(got)!=set(names):raise ValueError('Transferred bytes differ')
    return got


def main(output):
    m=get(L);activity=m['activity_root'];consume=m['consumption_root']
    if sha(L.read_bytes())!='59080339a1846f242e0b8664e80a59b91ac623c768010ad1652e7d648c3b3301':
        raise ValueError('Manifest identity differs')
    ssh('test -f '+shlex.quote(CONTROL+'/controller.exit')+' && { test -f '+shlex.quote(activity+'/finished.json')+
        ' || test -f '+shlex.quote(activity+'/halt.json')+'; }')
    primary=transfer(activity,['admission.json','manifest-binding.json','controller.json','progress.json','finished.json','halt.json','accounting-unresolved.json'],output/'study')
    consumption=transfer(consume,['consumption.json'],output/'consume')
    controller=transfer(CONTROL,['controller.pid','wrapper.pid','controller.sh','controller.stdout','controller.stderr','controller.exit'],output/'control')
    progress=get(output/'study/progress.json')
    # The official status path is read-only and retains nullable totals and all suffix positions.
    status_bytes=ssh('cd '+shlex.quote(m['release_root'])+' && '+shlex.join([m['python']['path'],'-I','-B','scripts/v6_research_launch.py','status','--manifest-sha',sha(L.read_bytes())]))
    save(output/'official-status.json',status_bytes)
    status=json.loads(status_bytes)
    if not (len(progress['rows'])==len(status['rows'])==85 and status['manifest_sha256']==progress['manifest_sha256']==sha(L.read_bytes())):
        raise ValueError('Case ledger identity or denominator differs')
    roles=['scheduler-command.json','reserved.json','submitted.json','release-requested.json','worker-claim.json','worker-result.json','scheduler-terminal.json','committed.json','panel.json','arms/ledger.json','arms/events.jsonl']
    jobs=[];all_names=[]
    for j in status['jobs']:
        case=j['case'];job=j.get('submitted')
        if case not in [row['condition'] for row in m['groups']]:raise ValueError('Unregistered job')
        prefix='jobs/'+case+'/'
        names=[prefix+r for r in roles]
        if job:
            if not job.isdecimal():raise ValueError('Invalid scheduler ID')
            jobs.append(job);names.extend([prefix+'slurm-'+job+ext for ext in ('.out','.err')])
        for arm in ('V','D','K','H','P'):
            folder=prefix+'arms/'+case+'-'+arm+'/'
            names+=[folder+k for k in ('execution-binding.json','call.json','native-return.json','score.json','stderr')]
        all_names.extend(names)
    # Several bounded transfers keep login-node commands below argument limits.
    perjob={}
    for start in range(0,len(all_names),125):
        perjob.update(transfer(activity,all_names[start:start+125],output/'study'))
    projector=HERE/'read_saved_fields.py'
    projected=ssh(shlex.join([m['python']['path'],'-I','-B','-',activity,CONTROL]),stdin=projector.read_bytes())
    save(output/'actual-stages.jsonl',projected)
    lines=[json.loads(x) for x in projected.splitlines()]
    if [x['unit'] for x in lines]!=[x['unit'] for x in status['rows']]:raise ValueError('Stage projection missing a position')
    order=['JobID','JobName','Partition','State','ExitCode','NodeList','AllocCPUs','ReqMem','ElapsedRaw','TotalCPU','Start','End','Timelimit','Restarts']
    if jobs:
        # Slurm 22.05 exposes restart/requeue through each worker allocation receipt.
        order=order[:-1]
        sacct=ssh(shlex.join(['sacct','-nP','-j',','.join(jobs),'-o',','.join(order)])).decode().strip().splitlines()
    else:sacct=[]
    receipt=dict(schema='aegisdc-native-study-retrieval-v1',manifest=sha(L.read_bytes()),approval_revision=REVIEW,
        private_activity=activity,private_consumption=consume,controller_receipt_directory=CONTROL,
        study_files_sha256=primary,consumption_sha256=consumption,controller_files_sha256=controller,
        per_job_files_sha256=perjob,sacct_fields=order,sacct=sacct,official_status_sha256=sha(status_bytes),
        stage_projection_sha256=sha(projected),projection_tool_sha256=sha(projector.read_bytes()),collector_sha256=sha(Path(__file__).read_bytes()))
    save(output/'retrieval.json',(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n').encode())
    print('sealed',bool(primary.get('finished.json')),'jobs',len(jobs),'positions',len(lines),'files',len(perjob),'stages',len(projected))


if __name__=='__main__':main(Path(sys.argv[1]))
