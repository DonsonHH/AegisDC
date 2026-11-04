"""Capture one fresh ticket-09 command without rewriting an earlier attempt."""
import json
import os
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
name, *arguments = sys.argv[1:]
if arguments and arguments[0] == '--':
    arguments.pop(0)
out = Path(__file__).resolve().parent / name
out.mkdir(parents=True, exist_ok=False)
paths = [*sorted((ROOT / 'src/aegis_dc').glob('*.py')),
         ROOT / 'tests/test_mainline_control.py']
files = {str(p.relative_to(ROOT)).replace('\\', '/'): sha256(p.read_bytes()).hexdigest()
         for p in paths if p.is_file()}
command = [sys.executable, '-B', '-X', 'utf8', *arguments]
process = subprocess.run(command, cwd=ROOT,
    env=dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1'), capture_output=True)
(out / 'stdout.txt').write_bytes(process.stdout)
(out / 'stderr.txt').write_bytes(process.stderr)
receipt = {'command': command, 'cwd': str(ROOT), 'exit_code': process.returncode,
    'git_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
    'source_files_sha256': files,
    'source_dirty': bool(subprocess.check_output(['git','status','--porcelain','--','src/aegis_dc'], cwd=ROOT, text=True).strip()),
    'scope': 'ENGINEERING_CHECK_NOT_RESEARCH',
    'stdout_sha256': sha256(process.stdout).hexdigest(), 'stderr_sha256': sha256(process.stderr).hexdigest()}
(out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'attempt': name, 'exit_code': process.returncode}))
print(process.stderr.decode('utf-8', errors='replace')[-2200:])
sys.exit(process.returncode)
