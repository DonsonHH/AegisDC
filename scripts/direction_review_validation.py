"""Package locally,validate one bounded public-interface test on the existing CPU server."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import zipfile

TOOL='scripts/direction_review_validation.py'
MANIFEST='configs/facility-risk-baseline-v1.json'
TEST='tests/test_facility_risk_baseline.py'
SELECTOR='test_facility_risk_baseline.FacilityRiskBaselineTests.test_eight_domain_catalogue_separates_risk_value_unknowns_and_time_alignment'
REMOTE='/root/private_data/aegisdc-direction-correction-20261110-01'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args])
def need(value,message):
    if not value:raise ValueError(message)
def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def prepare(args):
    root=Path(git('rev-parse','--show-toplevel').decode().strip()).resolve();need(Path.cwd().resolve()==root,'Use canonical Git root')
    control=git('rev-parse','HEAD').decode().strip();runtime=control if args.runtime=='control' else args.runtime
    need(git('rev-parse',runtime+'^{commit}').decode().strip()==runtime,'Pin full runtime revision')
    config=json.loads(git('show',control+':'+MANIFEST))
    runtime_paths=git('ls-tree','-r','--name-only',runtime,'--','src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py').decode().splitlines()
    controls=[MANIFEST,TEST,TOOL,*config['references'].values()]
    revisions={name:runtime for name in runtime_paths};need(not set(controls)&set(revisions),'Control must not override runtime')
    revisions.update({name:control for name in controls})
    contents={name:git('show',revision+':'+name) for name,revision in sorted(revisions.items())}
    destination=root/'.work/direction-review-validation'/args.phase/control[:12];destination.mkdir(parents=True,exist_ok=False)
    archive=destination/'snapshot.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for name,raw in contents.items():z.writestr(name,raw)
    m=dict(classification='BOUNDED_DIRECTION_REVIEW_NOT_FACILITY_OR_RESEARCH_RUN',phase=args.phase,
        runtime=runtime,control=control,root=REMOTE,selector=SELECTOR,
        files={name:dict(bytes=len(raw),sha256=sha(raw),git_blob=git('rev-parse',revisions[name]+':'+name).decode().strip()) for name,raw in contents.items()},
        snapshot_sha256=sha(archive.read_bytes()),runner_sha256=sha(contents[TOOL]))
    save(destination/'manifest.json',m);(destination/'runner.py').write_bytes(contents[TOOL])
    print(json.dumps(dict(stage=str(destination),manifest_sha256=sha((destination/'manifest.json').read_bytes()),
        snapshot_sha256=m['snapshot_sha256'],runner_sha256=m['runner_sha256'],control=control,runtime=runtime)))


def run(args):
    need(not sys.flags.optimize,'Use normal interpreter')
    raw_manifest=args.manifest.read_bytes();m=json.loads(raw_manifest);root=Path(m['root'])
    need(os.geteuid()==0 and socket.gethostname()=='crdnotebook-2108427285948563457-scnnxa6cio-81507'
         and platform.python_version()=='3.12.7' and not os.environ.get('SLURM_JOB_ID')
         and Path('/root/private_data').is_mount() and str(root)==REMOTE,'Private CPU identity/mount differs')
    output=root/m['phase'];output.mkdir(mode=0o700,exist_ok=False);snapshot=output/'snapshot';snapshot.mkdir()
    result=dict(status='FAILED',phase=m['phase'],runtime=m['runtime'],control=m['control'],
        started_utc=datetime.now(timezone.utc).isoformat(),node=socket.gethostname(),python=sys.version,
        new_facility_runs=0,new_neural_or_llm_calls=0,new_registered_research_runs=0,
        counting_basis='Configuration-only CLI calls,source reviewed;no facility runner or model inference in the new entry',
        inputs=m['files'],manifest_sha256=sha(raw_manifest),snapshot_sha256=m['snapshot_sha256'])
    try:
        need(sha(Path(__file__).read_bytes())==m['runner_sha256'],'Executed controller differs')
        need(sha(args.snapshot.read_bytes())==m['snapshot_sha256'],'Snapshot archive differs')
        with zipfile.ZipFile(args.snapshot) as z:
            names=z.namelist();need(len(names)==len(set(names)) and sorted(names)==sorted(m['files']),'Archive roles differ')
            for name in names:
                need(not Path(name).is_absolute() and '..' not in Path(name).parts,'Archive path escaped')
                path=snapshot/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(name))
        def guard():
            for name,rec in m['files'].items():
                raw=(snapshot/name).read_bytes();need(len(raw)==rec['bytes'] and sha(raw)==rec['sha256'],'Frozen source differs:'+name)
        guard();env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join([str(snapshot/'src'),str(snapshot/'tests')]),
            AEGIS_BASELINE_RESULT_PATH=str(output/'baseline-output.json'))
        command=[sys.executable,'-m','unittest',m['selector'],'-v']
        completed=subprocess.run(command,cwd=snapshot,env=env,text=True,capture_output=True,timeout=120)
        log=completed.stdout+completed.stderr;(output/'test.log').write_text(log,encoding='utf-8',newline='\n')
        guard();need(sha(args.manifest.read_bytes())==sha(raw_manifest),'Manifest changed')
        need('Ran 1 test' in log,'Expected one selected public-interface test')
        if m['phase']=='red':
            need(completed.returncode!=0 and "invalid choice: 'risk-baseline'" in log,'Expected old CLI red absent')
            result['status']='EXPECTED_RED_ENTRYPOINT_ABSENT'
        else:
            need(completed.returncode==0,'Baseline public-interface test failed')
            result.update(status='GREEN_BASELINE_INTERFACE_PASSED',baseline=json.loads((output/'baseline-output.json').read_bytes()))
        result.update(test_exit_code=completed.returncode,tests=1,test_log_sha256=sha((output/'test.log').read_bytes()),source_guard='PASS_BEFORE_AND_AFTER')
    except BaseException as error:
        result['error']=repr(error);raise
    finally:
        result['finished_utc']=datetime.now(timezone.utc).isoformat();save(output/'result.json',result)
    print(json.dumps({key:result[key] for key in ('status','phase','runtime','tests','new_facility_runs','new_registered_research_runs')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--phase',choices=['red','green'],required=True);a.add_argument('--runtime',required=True)
    a=sub.add_parser('run');a.add_argument('--manifest',type=Path,required=True);a.add_argument('--snapshot',type=Path,required=True)
    args=p.parse_args();prepare(args) if args.command=='prepare' else run(args)
