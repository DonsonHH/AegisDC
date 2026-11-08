"""Run one frozen development slice in Slurm and retain red/green outcomes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback
import unittest


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AccountedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.public_choice_calls = 0
        self.facility_calls = 0
        self.returned_decisions = 0

    def stopTest(self, test):
        self.public_choice_calls += getattr(test, 'public_choice_calls', 0)
        self.facility_calls += getattr(test, 'facility_calls', 0)
        self.returned_decisions += getattr(test, 'returned_decisions', 0)
        super().stopTest(test)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] == 'mu01':
        raise SystemExit('Engineering evaluation requires a Slurm compute allocation')
    root = args.manifest.resolve().parent
    frozen_manifest_sha256 = sha256(args.manifest)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    evaluation = manifest.get('evaluation', dict(test_pattern='test_problem_tasks.py',
        direct_public_choice_calls=1, facility_calls=0, maximum_returned_decisions=0,
        red_error='Dispatch policy program fields'))
    args.output.mkdir(exist_ok=False)
    save(args.output / 'attempt.json', dict(
        classification='ENGINEERING_DEVELOPMENT_NOT_RESEARCH_TRIAL',
        attempt=manifest['attempt'], phase=manifest['phase'],
        source_commit=manifest['source_commit'], manifest_sha256=sha256(args.manifest),
        started_at_utc=datetime.now(timezone.utc).isoformat(),
        slurm_job_id=os.environ['SLURM_JOB_ID'], node=socket.gethostname(),
        python=sys.version, python_executable=sys.executable,
        charged_public_choice_calls=evaluation['direct_public_choice_calls'],
        charged_facility_calls=evaluation['facility_calls'],
        maximum_returned_decisions=evaluation['maximum_returned_decisions'],
        maximum_model_calls=0, new_statistical_units=0,
    ))
    terminal = dict(status='FAILED', attempt=manifest['attempt'], source_commit=manifest['source_commit'])
    try:
        def guard():
            if sha256(args.manifest) != frozen_manifest_sha256:
                raise ValueError('The frozen attempt manifest changed')
            for name, record in manifest['files'].items():
                path = root / name
                if not path.resolve().is_relative_to(root) or path.is_symlink():
                    raise ValueError('Source path escapes the frozen stage')
                if path.stat().st_size != record['bytes'] or sha256(path) != record['sha256']:
                    raise ValueError('Frozen source/input/tool differs: ' + name)
            if manifest.get('execution_git_snapshot'):
                head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
                top = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=root, text=True).strip()
                dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', 'src/aegis_dc',
                                                  'src/patrol_rsi/contracts.py'], cwd=root, text=True).strip()
                if head != manifest['source_commit'] or Path(top).resolve() != root or dirty:
                    raise ValueError('Actual execution checkout differs from the frozen source revision')
        guard()
        if Path(__file__).resolve() != root / 'scripts/run_engineering_slice.py':
            raise ValueError('Execute the pinned engineering tool in its own stage')
        sys.path.insert(0, str(root / 'src'))
        pattern = evaluation['test_pattern']
        if Path(pattern).name != pattern or not pattern.startswith('test_') or not pattern.endswith('.py'):
            raise ValueError('Declare one test file in the frozen tests directory')
        os.environ['AEGIS_ENGINEERING_RESULT_DIR'] = str(args.output.resolve())
        suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern=pattern)
        with (args.output / 'test.log').open('x', encoding='utf-8', newline='\n') as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=AccountedResult).run(suite)
        guard()
        for name, module in list(sys.modules.items()):
            if name == 'aegis_dc' or name.startswith('aegis_dc.') or name == 'patrol_rsi.contracts':
                if not Path(module.__file__).resolve().is_relative_to(root / 'src'):
                    raise ValueError('Project module imported outside the frozen stage: ' + name)
        terminal.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                        skips=len(result.skipped), direct_public_choice_calls=result.public_choice_calls,
                        internal_public_choice_calls=None if result.facility_calls else 0,
                        returned_decisions=result.returned_decisions,
                        new_facility_calls=result.facility_calls, new_model_calls=0, new_research_trials=0,
                        test_log_sha256=sha256(args.output / 'test.log'),
                        source_guard='PASS_BEFORE_AND_AFTER',
                        attempt_sha256=sha256(args.output / 'attempt.json'))
        if (result.testsRun != evaluation.get('tests_run', 1) or result.public_choice_calls != evaluation['direct_public_choice_calls']
                or result.facility_calls != evaluation['facility_calls'] or result.skipped
                or result.returned_decisions > evaluation['maximum_returned_decisions']):
            raise ValueError('Engineering slice execution denominator/call count differs')
        log = (args.output / 'test.log').read_text(encoding='utf-8')
        if manifest['phase'] == 'red':
            if result.wasSuccessful() or evaluation['red_error'] not in log:
                raise ValueError('Red phase did not expose the declared missing public contract')
            status = 'EXPECTED_RED_CONTRACT_GAP'
        elif manifest['phase'] == 'green':
            if not result.wasSuccessful():
                raise ValueError('Green phase did not pass the unchanged public behavior')
            status = 'GREEN_BEHAVIOR_PASSED'
        elif manifest['phase'] == 'qualification':
            if not result.wasSuccessful():
                raise ValueError('Existing-behavior qualification did not pass')
            status = 'QUALIFICATION_BEHAVIORS_PASSED'
        else:
            raise ValueError('Unknown frozen development phase')
        terminal['status'] = status
        print(json.dumps({key: terminal[key] for key in ('status', 'tests_run', 'new_facility_calls', 'new_research_trials')}))
    except BaseException as error:
        terminal.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal['output_files'] = {p.relative_to(args.output).as_posix(): dict(bytes=p.stat().st_size,
            sha256=sha256(p)) for p in args.output.rglob('*') if p.is_file()}
        terminal['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(args.output / 'terminal.json', terminal)


if __name__ == '__main__':
    main()
