"""Launch the fixed ticket 28 engineering packet only after its two sealed reviews."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('C:/Users/Donson/.codex/worktrees/mainline28-negative-controls/Renly')
SOURCE = '815294edb4befd6717a412c9fe48deac84157b4a'
EVIDENCE_ROOT = Path('C:/Users/Donson/Documents/ChatGPT/Renly/.work')
LAUNCH = ROOT / '.work/28-frozen-launch-20261107-02'
OUTPUT = ROOT / 'evidence/mainline/engineering/28-negative-controls/capture-20261107-02'
REVIEWS = {axis: EVIDENCE_ROOT / f'28-frozen-{axis.lower()}-review-02/review.json' for axis in ('Spec','Standards')}


def write(path, value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip() == SOURCE
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)
for axis, path in REVIEWS.items():
    value = json.loads(path.read_bytes())
    assert value['axis'] == axis and value.get('source',value.get('data')) == SOURCE
    assert value['status'].startswith('PASS') and not value['unresolved'] and value['checks'] > 0
assert not LAUNCH.exists() and not OUTPUT.exists()
LAUNCH.mkdir(parents=True)
argv = [sys.executable,'-B','-X','utf8','scripts/negative_control_delivery.py','capture',
        '--spec-review',str(REVIEWS['Spec']),'--standards-review',str(REVIEWS['Standards'])]
prefix = LAUNCH / 'fresh-cache-prefix'
assert not prefix.exists()
env = dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONPYCACHEPREFIX=str(prefix),
           PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0')
write(LAUNCH/'attempt.json',dict(status='STARTED',source=SOURCE,argv=argv,cwd=str(ROOT),
    launcher_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
    executable_sha256=sha256(Path(sys.executable).read_bytes()).hexdigest(),
    environment={key:env[key] for key in ('PYTHONPATH','PYTHONPYCACHEPREFIX','PYTHONDONTWRITEBYTECODE','PYTHONHASHSEED')},
    cache_prefix_existed_before=False,review_hashes={axis:sha256(path.read_bytes()).hexdigest() for axis,path in REVIEWS.items()},
    utc=datetime.now(timezone.utc).isoformat(),classification='FROZEN_28_FINITE_ENGINEERING_NOT_EFFECT_COMPARISON'))
with (LAUNCH/'stdout.txt').open('x',encoding='utf-8') as stdout, (LAUNCH/'stderr.txt').open('x',encoding='utf-8') as stderr:
    child = subprocess.Popen(argv,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
    write(LAUNCH/'process.json',dict(pid=child.pid,source=SOURCE))
    code = child.wait()
write(LAUNCH/'terminal.json',dict(status='COMPLETED' if code == 0 else 'FAILED',source=SOURCE,returncode=code,
    receipt_exists=(OUTPUT/'receipt.json').exists(),utc=datetime.now(timezone.utc).isoformat(),
    stdout_sha256=sha256((LAUNCH/'stdout.txt').read_bytes()).hexdigest(),
    stderr_sha256=sha256((LAUNCH/'stderr.txt').read_bytes()).hexdigest()))
print((LAUNCH/'stdout.txt').read_text(encoding='utf-8'))
if code:
    print((LAUNCH/'stderr.txt').read_text(encoding='utf-8'))
raise SystemExit(code)
