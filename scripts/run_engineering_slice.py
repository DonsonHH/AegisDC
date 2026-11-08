"""Run one frozen development slice in Slurm and retain red/green outcomes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
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

    def stopTest(self, test):
        self.public_choice_calls += getattr(test, 'public_choice_calls', 0)
        super().stopTest(test)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] == 'mu01':
        raise SystemExit('Engineering evaluation requires a Slurm compute allocation')
    root = args.manifest.resolve().parent
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    args.output.mkdir(exist_ok=False)
    save(args.output / 'attempt.json', dict(
        classification='ENGINEERING_DEVELOPMENT_NOT_RESEARCH_TRIAL',
        attempt=manifest['attempt'], phase=manifest['phase'],
        source_commit=manifest['source_commit'], manifest_sha256=sha256(args.manifest),
        started_at_utc=datetime.now(timezone.utc).isoformat(),
        slurm_job_id=os.environ['SLURM_JOB_ID'], node=socket.gethostname(),
        python=sys.version, python_executable=sys.executable,
        charged_public_choice_calls=1, maximum_facility_calls=0,
        maximum_model_calls=0, new_statistical_units=0,
    ))
    terminal = dict(status='FAILED', attempt=manifest['attempt'], source_commit=manifest['source_commit'])
    try:
        def guard():
            for name, record in manifest['files'].items():
                path = root / name
                if not path.resolve().is_relative_to(root) or path.is_symlink():
                    raise ValueError('Source path escapes the frozen stage')
                if path.stat().st_size != record['bytes'] or sha256(path) != record['sha256']:
                    raise ValueError('Frozen source/input/tool differs: ' + name)
        guard()
        if Path(__file__).resolve() != root / 'scripts/run_engineering_slice.py':
            raise ValueError('Execute the pinned engineering tool in its own stage')
        sys.path.insert(0, str(root / 'src'))
        suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern='test_problem_tasks.py')
        with (args.output / 'test.log').open('x', encoding='utf-8', newline='\n') as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=AccountedResult).run(suite)
        guard()
        for name, module in list(sys.modules.items()):
            if name == 'aegis_dc' or name.startswith('aegis_dc.') or name == 'patrol_rsi.contracts':
                if not Path(module.__file__).resolve().is_relative_to(root / 'src'):
                    raise ValueError('Project module imported outside the frozen stage: ' + name)
        if result.testsRun != 1 or result.public_choice_calls != 1 or result.skipped:
            raise ValueError('Engineering slice execution denominator/call count differs')
        log = (args.output / 'test.log').read_text(encoding='utf-8')
        if manifest['phase'] == 'red':
            if result.wasSuccessful() or 'Dispatch policy program fields' not in log:
                raise ValueError('Red phase did not expose the declared missing public contract')
            status = 'EXPECTED_RED_CONTRACT_GAP'
        elif manifest['phase'] == 'green':
            if not result.wasSuccessful():
                raise ValueError('Green phase did not pass the unchanged public behavior')
            status = 'GREEN_BEHAVIOR_PASSED'
        else:
            raise ValueError('Unknown frozen development phase')
        terminal.update(status=status, tests_run=result.testsRun, failures=len(result.failures),
                        errors=len(result.errors), skips=len(result.skipped),
                        public_choice_calls=result.public_choice_calls,
                        new_facility_calls=0, new_model_calls=0, new_research_trials=0,
                        test_log_sha256=sha256(args.output / 'test.log'),
                        source_guard='PASS_BEFORE_AND_AFTER',
                        attempt_sha256=sha256(args.output / 'attempt.json'))
        print(json.dumps({key: terminal[key] for key in ('status', 'tests_run', 'public_choice_calls', 'new_research_trials')}))
    except BaseException as error:
        terminal.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(args.output / 'terminal.json', terminal)


if __name__ == '__main__':
    main()
