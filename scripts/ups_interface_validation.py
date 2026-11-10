"""Freeze one UPS interface test locally; execute it only on the private CPU host."""
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

TOOL='scripts/ups_interface_validation.py'
TEST='tests/test_ups_return_to_service.py'
SELECTOR='test_ups_return_to_service.UPSReturnToServiceTests.test_native_read_restore_authority_and_verification_boundary'
REMOTE='/root/private_data/aegisdc-ups-a2-20261111-01'
INPUTS=['configs/full-facility-mainline-reserve-v6.json','configs/full-facility-nonfixed-evidence-v1.json',
        'configs/full-facility-decision-v1/public-nominal.json','configs/full-facility-decision-v1/common-ledger.json',
        'configs/materials/reference-r134a-saturation.json']


def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,message):
    if not ok:raise ValueError(message)
def git(*args):return subprocess.check_output(['git',*args])
def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def prepare(args):
    revision=git('rev-parse','HEAD').decode().strip()
    names=git('ls-tree','-r','--name-only',revision,'--','src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py').decode().splitlines()
    contents={p:git('show',revision+':'+p) for p in sorted(names+INPUTS+[TOOL,TEST])}
    out=Path('.work/ups-a2')/args.phase/revision[:12];out.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(out/'snapshot.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name,raw in contents.items():z.writestr(name,raw)
    manifest=dict(classification='ENGINEERING_INTERFACE_ONLY_NOT_RESEARCH',phase=args.phase,source_commit=revision,remote=REMOTE,selector=SELECTOR,
        files={p:dict(bytes=len(raw),sha256=sha(raw),git_blob=git('rev-parse',revision+':'+p).decode().strip()) for p,raw in contents.items()},
        snapshot_sha256=sha((out/'snapshot.zip').read_bytes()),runner_sha256=sha(contents[TOOL]))
    save(out/'manifest.json',manifest);(out/'runner.py').write_bytes(contents[TOOL])
    print(json.dumps(dict(stage=str(out),source_commit=revision,manifest_sha256=sha((out/'manifest.json').read_bytes()),
        snapshot_sha256=manifest['snapshot_sha256'],runner_sha256=manifest['runner_sha256'])))


def run(args):
    need(os.geteuid()==0 and socket.gethostname()=='crdnotebook-2108427285948563457-scnnxa6cio-81507'
        and platform.python_version()=='3.12.7' and Path('/root/private_data').is_mount() and not os.environ.get('SLURM_JOB_ID'),
        'Use the verified private CPU interpreter/container;no local evaluation fallback')
    raw=args.manifest.read_bytes();m=json.loads(raw);need(m['remote']==REMOTE,'Unexpected output root')
    out=Path(REMOTE)/m['phase'];out.mkdir(mode=0o700,exist_ok=False);snapshot=out/'snapshot';snapshot.mkdir()
    result=dict(status='FAILED',phase=m['phase'],source_commit=m['source_commit'],node=socket.gethostname(),python=sys.version,
        started_utc=datetime.now(timezone.utc).isoformat(),manifest_sha256=sha(raw),snapshot_sha256=m['snapshot_sha256'],runner_sha256=m['runner_sha256'],
        source_materialization='Fresh declared Git blobs;Git metadata omitted;runtime source maps checked against execution commit blobs',
        cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),memory_max=Path('/sys/fs/cgroup/memory.max').read_text().strip(),
        new_registered_research_runs=0,new_neural_or_llm_calls=0,tests_selected=1)
    try:
        need(not sys.flags.optimize and sha(Path(__file__).read_bytes())==m['runner_sha256'],'Pinned normal runner differs')
        need(sha(args.snapshot.read_bytes())==m['snapshot_sha256'],'Archive differs')
        with zipfile.ZipFile(args.snapshot) as z:
            names=z.namelist();need(len(names)==len(set(names)) and sorted(names)==sorted(m['files']),'Declared archive roles differ')
            for name in names:
                need(not Path(name).is_absolute() and '..' not in Path(name).parts,'Archive path escape')
                p=snapshot/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
        def guard():
            for p,rec in m['files'].items():
                actual=(snapshot/p).read_bytes();need(len(actual)==rec['bytes'] and sha(actual)==rec['sha256'],'Frozen input/source differs:'+p)
        guard();env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(snapshot/'src'),str(snapshot/'tests')]),PYTHONDONTWRITEBYTECODE='1',AEGIS_A2_RESULTS_DIR=str(out))
        command=[sys.executable,'-m','unittest',m['selector'],'-v'];result['command']=command
        completed=subprocess.run(command,cwd=snapshot,env=env,text=True,capture_output=True,timeout=180)
        log=completed.stdout+completed.stderr;(out/'test.log').write_text(log,encoding='utf-8',newline='\n')
        result.update(test_exit_code=completed.returncode,test_log_sha256=sha((out/'test.log').read_bytes()))
        if (out/'metrics.json').exists():result['metrics']=json.loads((out/'metrics.json').read_bytes())
        guard();need(sha(args.manifest.read_bytes())==sha(raw),'Manifest changed');result['source_guard']='PASS_BEFORE_AND_AFTER'
        need('Ran 1 test' in log,'Exactly one unchanged test must execute')
        if m['phase']=='red':
            need(completed.returncode!=0 and 'Instrument output/signal does not match a declared SI observable' in log,'Expected absent UPS signal was not observed')
            result['status']='EXPECTED_RED_MISSING_UPS_SIGNAL'
        else:
            need(completed.returncode==0,'Frozen UPS interface test failed')
            metrics=result['metrics'];need((metrics['facility_entries'],metrics['completed_windows'],metrics['completed_simulated_s'])==(7,4,24),'Engineering accounting differs')
            expected={p:r['sha256'] for p,r in m['files'].items() if p.startswith('src/aegis_dc/') and p.endswith('.py') or p=='src/patrol_rsi/contracts.py'}
            for case in metrics['cases']:
                if case['status']=='COMPLETED':
                    record=json.loads((out/case['case']/'run.json').read_bytes())
                    need(record['code_identity']['files']==expected,'Runtime source does not match its execution revision')
            result.update(status='GREEN_UPS_NATIVE_INTERFACE_PASSED',runtime_source_identity='PASS_FOR_ALL_COMPLETED_WINDOWS')
    except BaseException as error:
        result['error']=repr(error);raise
    finally:
        result['finished_utc']=datetime.now(timezone.utc).isoformat();save(out/'result.json',result)
    print(json.dumps({key:result[key] for key in ('status','phase','source_commit','new_registered_research_runs')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--phase',choices=['red','green'],required=True)
    a=sub.add_parser('run');a.add_argument('--manifest',type=Path,required=True);a.add_argument('--snapshot',type=Path,required=True)
    args=p.parse_args();prepare(args) if args.command=='prepare' else run(args)
