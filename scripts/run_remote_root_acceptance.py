"""One exact-source integrated engineering acceptance inside a Slurm allocation."""
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

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def identities():
    names = git('ls-files', '-z', 'src', 'scripts', 'tests', 'configs').decode().strip('\0').split('\0')
    names = sorted(name for name in names if name.endswith(('.py', '.json')))
    raw = subprocess.check_output(
        ['git', 'cat-file', '--batch'], cwd=ROOT, input=''.join('HEAD:' + name + '\n' for name in names).encode())
    records, offset = {}, 0
    for name in names:
        end = raw.index(b'\n', offset)
        header = raw[offset:end].split()
        assert len(header) == 3 and header[1] == b'blob', name
        size = int(header[2]); start = end + 1
        blob = raw[start:start + size]
        actual = (ROOT / name).read_bytes()
        assert actual == blob, 'Runtime source/input/tool bytes differ from Git: ' + name
        records[name] = dict(bytes=len(actual), sha256=hashlib.sha256(actual).hexdigest(), git_blob=header[0].decode())
        offset = start + size + 1
    assert offset == len(raw)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] == 'mu01':
        raise SystemExit('Root acceptance requires a Slurm compute allocation')
    output = args.output.resolve()
    assert output.parent == ROOT / 'runs' and not output.exists()
    output.mkdir()
    terminal = dict(status='FAILED', source_commit=args.source)
    save(output / 'attempt.json', dict(classification='INTEGRATED_ENGINEERING_REGRESSION_NOT_REGISTERED_RESEARCH',
        source_commit=args.source, slurm_job_id=os.environ['SLURM_JOB_ID'], node=socket.gethostname(),
        started_at_utc=datetime.now(timezone.utc).isoformat(), new_research_trials=0,
        scope='One complete regression, including existing untrained neural contract checks; no research training or LLM experiment.'))
    try:
        if sys.flags.optimize:
            raise ValueError('Root source and environment guards require non-optimized Python')
        assert git('rev-parse', 'HEAD').decode().strip() == args.source
        assert Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve() == ROOT
        assert git('branch', '--show-current').decode().strip() == 'donson/full-facility-mainline'
        assert not git('status', '--porcelain').strip()
        assert sys.version_info[:3] == (3, 13, 9), 'Use the frozen Python version'
        environment = Path('/share/home/renly/renly-patrol-rsi/environments/aegisdc-verify-20261109')
        assert Path(sys.prefix).resolve() == environment.resolve(), 'Use the isolated frozen verification environment'
        assert Path(sys.executable).parent == environment / 'bin', 'Use its declared Python entry point'
        assert git('rev-parse', '--is-shallow-repository').decode().strip() == 'false'
        git('cat-file', '-e', '2dfe5537e4f95fa605f325b060ef32223dafb4f6^{commit}')
        assert git('rev-parse', 'pre-meeting-20261103^{}').decode().strip() == '076d9aa15c5bc99a5b7985f296e15543b7b0f3d7'
        before = identities()
        save(output / 'source-manifest-before.json', before)
        sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
        os.environ['PYTHONPATH'] = str(ROOT / 'src')
        import numpy
        import torch
        assert numpy.__version__ == '2.3.5' and torch.__version__ == '2.6.0+cpu'
        from acceptance import verify
        # acceptance.verify owns a fresh output directory and retains all test logs.
        result = verify(ROOT, output / 'acceptance')
        after = identities()
        assert before == after and git('rev-parse', 'HEAD').decode().strip() == args.source
        assert not git('status', '--porcelain').strip()
        save(output / 'source-guard.json', dict(source=args.source, guarded_files=len(before),
            source_guard='PASS_BEFORE_AND_AFTER', python=sys.version, executable=sys.executable,
            executable_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            numpy=numpy.__version__, torch=torch.__version__, actual_branch='donson/full-facility-mainline',
            source_manifest='source-manifest-before.json', caches='EXCLUDED_NOT_DELIVERED'))
        tests = result.get('tests', {})
        passed = (result['overall'] == 'PASS' and tests.get('run', 0) >= 500
                  and tests.get('skipped') == tests.get('failures') == tests.get('errors') == 0)
        terminal.update(status='PASS' if passed else 'FAILED', tests=tests,
                        verified_original_files=result.get('verified_original_files'), error=result.get('error'),
                        source_guard='PASS_BEFORE_AND_AFTER', new_research_trials=0)
        print(json.dumps({key: terminal[key] for key in ('status', 'tests', 'verified_original_files', 'source_guard')}))
        if not passed:
            raise RuntimeError('Integrated acceptance did not meet its frozen zero-skip/zero-failure gate')
    except BaseException as error:
        terminal.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal['output_files'] = {p.relative_to(output).as_posix(): dict(bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in output.rglob('*') if p.is_file()}
        terminal['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(output / 'terminal.json', terminal)


if __name__ == '__main__':
    main()
