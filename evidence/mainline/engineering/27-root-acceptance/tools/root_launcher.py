"""Single integrated ticket 27 engineering regression; does not replay formal 27 captures."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'a97d09eb19b7d64b38f2042075221627f9255fa7'
RUN = ROOT / '.work/27-root-full-launch-01'
OUTPUT = 'runs/mainline-M4-27-root-acceptance-20261107-01'


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


assert not RUN.exists() and not (ROOT / OUTPUT).exists()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SOURCE
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)
RUN.mkdir()
prefix = RUN / 'fresh-cache-prefix'
assert not prefix.exists()
command = [sys.executable, '-B', '-X', 'utf8', '.work/run_27_root_acceptance.py', '--source', SOURCE, '--output', OUTPUT]
env = dict(os.environ, PYTHONPYCACHEPREFIX=str(prefix), PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0')
write(RUN / 'attempt.json', dict(status='STARTED', source=SOURCE, command=command, cwd=str(ROOT),
    environment={key: env[key] for key in ('PYTHONPYCACHEPREFIX', 'PYTHONDONTWRITEBYTECODE', 'PYTHONHASHSEED')},
    cache_prefix_existed_before=False, python_executable_sha256=sha256(Path(sys.executable).read_bytes()).hexdigest(),
    runner_sha256=sha256((ROOT / '.work/run_27_root_acceptance.py').read_bytes()).hexdigest(),
    launcher_sha256=sha256(Path(__file__).read_bytes()).hexdigest(), utc=datetime.now(timezone.utc).isoformat(),
    classification='SINGLE_INTEGRATED_ENGINEERING_REGRESSION_NOT_FORMAL_CAPTURE', fixture_baseline={name: sorted(path.name for path in (ROOT / '.work' / name).glob('*')) for name in ('26-online-development', '27-development', '27-replay-development')}))
with (RUN / 'stdout.txt').open('x', encoding='utf-8') as stdout, (RUN / 'stderr.txt').open('x', encoding='utf-8') as stderr:
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
    write(RUN / 'process.json', dict(pid=process.pid, source=SOURCE))
    returncode = process.wait()
write(RUN / 'terminal.json', dict(status='COMPLETED' if returncode == 0 else 'FAILED', returncode=returncode,
    source=SOURCE, utc=datetime.now(timezone.utc).isoformat(),
    summary_exists=(ROOT / OUTPUT / 'summary.json').exists(),
    stdout_sha256=sha256((RUN / 'stdout.txt').read_bytes()).hexdigest(), stderr_sha256=sha256((RUN / 'stderr.txt').read_bytes()).hexdigest()))
print((RUN / 'stdout.txt').read_text(encoding='utf-8'))
if returncode:
    print((RUN / 'stderr.txt').read_text(encoding='utf-8'))
raise SystemExit(returncode)
