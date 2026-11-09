"""Run one frozen public-only engineering slice in a verified remote container."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
from importlib.metadata import version as package_version
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import traceback
import unittest
import zipfile


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


class AccountedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.choice_calls = 0
        self.facility_entries = 0
        self.returned_decisions = 0

    def stopTest(self, test):
        self.choice_calls += getattr(test, 'public_choice_calls', 0)
        self.facility_entries += getattr(test, 'facility_calls', 0)
        self.returned_decisions += getattr(test, 'returned_decisions', 0)
        super().stopTest(test)


def main():
    if sys.flags.optimize:raise SystemExit('Optimized evidence execution is forbidden')
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--snapshot',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();manifest=json.loads(args.manifest.read_bytes());manifest_sha=sha(args.manifest)
    attempt=manifest['attempt'];phase=manifest['phase'];expected=manifest['expected_host']
    persistent_mount=Path(expected['persistent_mount']).resolve()
    persistent_root=Path(expected['project_root']).resolve()
    if (os.geteuid()!=0 or socket.gethostname()!=expected['hostname'] or platform.python_version()!=expected['python']
            or os.environ.get('SLURM_JOB_ID') or not persistent_mount.is_mount()
            or not persistent_root.is_relative_to(persistent_mount)):
        raise SystemExit('Remote persistent-container identity/environment differs from frozen protocol')
    if importlib.util.find_spec('numpy') is None:
        raise SystemExit('Preinstalled NumPy dependency is missing; no install or local fallback')
    numpy_distribution=package_version('numpy')
    if not args.output.resolve().is_relative_to(persistent_root) or args.output.is_symlink():
        raise SystemExit('Output must stay under the declared persistent private volume')
    args.output.mkdir(mode=0o700,parents=False,exist_ok=False)
    save(args.output/'attempt.json',dict(classification='REMOTE_CONTAINER_ENGINEERING_NOT_RESEARCH',attempt=attempt,
        phase=phase,execution_source=manifest['execution_source'],control_source=manifest['control_source'],
        manifest_sha256=manifest_sha,started_at_utc=datetime.now(timezone.utc).isoformat(),
        node=socket.gethostname(),python=sys.version,python_executable=sys.executable,
        numpy_distribution=numpy_distribution,numpy_imported_before_test=('numpy' in sys.modules),
        slurm_job_id=None,gpu_used=False,direct_public_choice_calls_budget=1,new_facility_entries_budget=0,
        max_returned_native_decisions=0))
    terminal=dict(status='FAILED',attempt=attempt,phase=phase,execution_source=manifest['execution_source'])
    snapshot_root=args.output/'snapshot'
    try:
        if 'numpy' in sys.modules:raise ValueError('NumPy was imported before the frozen project test')
        signal.signal(signal.SIGALRM,lambda _signum,_frame: (_ for _ in ()).throw(TimeoutError('Frozen container attempt exceeded watchdog')))
        signal.alarm(manifest['watchdog_s'])
        if sha(args.manifest)!=manifest_sha:raise ValueError('Attempt manifest changed')
        archive_sha=sha(args.snapshot)
        if archive_sha!=manifest['snapshot_sha256'] or args.snapshot.stat().st_size!=manifest['snapshot_bytes']:
            raise ValueError('Frozen source snapshot archive differs')
        snapshot_root.mkdir(mode=0o700)
        with zipfile.ZipFile(args.snapshot) as archive:
            names=archive.namelist()
            if sorted(names)!=sorted(manifest['files']):raise ValueError('Frozen archive paths differ from manifest')
            for name in names:
                if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Source snapshot path escaped')
                destination=snapshot_root/name;destination.parent.mkdir(parents=True,exist_ok=True)
                with destination.open('xb') as stream:stream.write(archive.read(name))
        def guard():
            if sha(args.manifest)!=manifest_sha:raise ValueError('Frozen manifest changed')
            for name,record in manifest['files'].items():
                path=snapshot_root/name
                if not path.resolve().is_relative_to(snapshot_root) or path.stat().st_size!=record['bytes'] or sha(path)!=record['sha256']:
                    raise ValueError('Frozen snapshot file differs: '+name)
        guard()
        test_path=snapshot_root/manifest['test']
        sys.path.insert(0,str(snapshot_root/'src'));sys.path.insert(0,str(snapshot_root/'tests'))
        os.environ['AEGIS_ENGINEERING_RESULT_DIR']=str(args.output.resolve())
        module=Path(manifest['test']).stem
        prefix=module+'.'
        names=manifest['test_names']
        if not names or any(not name.startswith(prefix) for name in names):raise ValueError('Selected test does not match snapshot')
        suite=unittest.defaultTestLoader.loadTestsFromNames(names)
        if (args.output/'test.log').exists():raise FileExistsError('test.log already exists')
        with (args.output/'test.log').open('x',encoding='utf-8',newline='\n') as stream:
            result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AccountedResult).run(suite)
        guard()
        if 'numpy' in sys.modules:raise ValueError('This frozen selection-only test imported NumPy; no dependency substitution is allowed')
        if result.testsRun!=manifest['tests'] or result.choice_calls!=manifest['direct_public_choice_calls'] or result.facility_entries!=0 or result.returned_decisions!=0 or result.skipped:
            raise ValueError('Actual direct-call/facility-entry/test budget differs')
        log=(args.output/'test.log').read_text(encoding='utf-8')
        if phase=='red':
            if result.wasSuccessful() or manifest['expected_red_text'] not in log:raise ValueError('Expected frozen red contract gap absent')
            terminal['status']='EXPECTED_RED_CONTRACT_GAP'
        elif phase=='green':
            if not result.wasSuccessful():raise ValueError('Green test failed')
            terminal['status']='GREEN_BEHAVIOR_PASSED'
        else:raise ValueError('Unknown phase')
        terminal.update(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),
            direct_public_choice_calls=result.choice_calls,new_facility_entries=result.facility_entries,
            numpy_imported_by_test=('numpy' in sys.modules),numpy_distribution=numpy_distribution,
            completed_native_horizons=0,returned_native_decisions=0,new_model_calls=0,new_research_trials=0,
            test_log_sha256=sha(args.output/'test.log'),source_guard='PASS_BEFORE_AND_AFTER')
    except BaseException as error:
        terminal.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),
            tests_run=locals().get('result').testsRun if locals().get('result') else 0,
            direct_public_choice_calls=locals().get('result').choice_calls if locals().get('result') else 0,
            new_facility_entries=0,completed_native_horizons=0,returned_native_decisions=0,new_research_trials=0)
        raise
    finally:
        signal.alarm(0)
        terminal['output_files']={path.relative_to(args.output).as_posix():dict(bytes=path.stat().st_size,sha256=sha(path))
            for path in args.output.rglob('*') if path.is_file()}
        terminal['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        save(args.output/'terminal.json',terminal)
    print(json.dumps({key:terminal.get(key) for key in ('status','attempt','execution_source','tests_run','failures','errors',
        'direct_public_choice_calls','new_facility_entries','new_research_trials')}))


if __name__=='__main__':main()
