"""Launch the frozen ticket 27 engineering capture once, with exact records."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path('C:/Users/Donson/.codex/worktrees/mainline27-full-loop/Renly')
SOURCE = '36ae97cc17e4b9297017289e285d00abaee29929'
LAUNCH = ROOT / '.work/27-frozen-launch-20261107-02'
OUTPUT = ROOT / 'evidence/mainline/engineering/27-full-loop/capture-20261107-02'


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SOURCE
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)
assert not OUTPUT.exists()
LAUNCH.mkdir(exist_ok=False)
prefix = LAUNCH / 'fresh-cache-prefix'
assert not prefix.exists()
argv = [sys.executable, '-B', '-X', 'utf8', 'scripts/full_loop_delivery.py', 'capture']
environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONPYCACHEPREFIX=str(prefix),
    PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0')
write(LAUNCH / 'attempt.json', dict(status='STARTED', source=SOURCE, argv=argv, cwd=str(ROOT),
    launcher_sha256=sha256(Path(__file__).read_bytes()).hexdigest(), cache_prefix_existed_before=False,
    executable_sha256=sha256(Path(sys.executable).read_bytes()).hexdigest(),
    environment={key: environment[key] for key in ('PYTHONPATH', 'PYTHONPYCACHEPREFIX', 'PYTHONDONTWRITEBYTECODE', 'PYTHONHASHSEED')},
    utc=datetime.now(timezone.utc).isoformat(), classification='FROZEN_27_ENGINEERING_ATTEMPT_NOT_RESEARCH_TRIAL'))
with (LAUNCH / 'stdout.txt').open('x', encoding='utf-8') as stdout, (LAUNCH / 'stderr.txt').open('x', encoding='utf-8') as stderr:
    process = subprocess.Popen(argv, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr)
    write(LAUNCH / 'process.json', dict(pid=process.pid, source=SOURCE))
    returncode = process.wait()
write(LAUNCH / 'terminal.json', dict(status='COMPLETED' if returncode == 0 else 'FAILED', source=SOURCE,
    returncode=returncode, receipt_exists=(OUTPUT / 'receipt.json').exists(), utc=datetime.now(timezone.utc).isoformat(),
    stdout_sha256=sha256((LAUNCH / 'stdout.txt').read_bytes()).hexdigest(),
    stderr_sha256=sha256((LAUNCH / 'stderr.txt').read_bytes()).hexdigest()))
print((LAUNCH / 'stdout.txt').read_text(encoding='utf-8'))
if returncode:
    print((LAUNCH / 'stderr.txt').read_text(encoding='utf-8'))
raise SystemExit(returncode)
