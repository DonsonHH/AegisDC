"""Run the single integrated root engineering/evidence acceptance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'bcacbf78e4f071acd0a130c8dec85f5c95e4cc73'
OUTPUT = ROOT / 'runs/mainline-M2-root-acceptance-20261105-01'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def identities():
    names = git('ls-files', 'src', 'scripts', 'tests').splitlines()
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in names if name.endswith('.py')}


assert git('rev-parse', 'HEAD') == SOURCE
assert git('branch', '--show-current') == 'donson/full-facility-mainline'
assert not git('status', '--porcelain')
assert not OUTPUT.exists()
before = identities()
sys.path[:0] = [str(ROOT / '.work/benchmark-neural-deps'),
                str(ROOT / 'src'), str(ROOT / 'scripts')]
os.environ['PYTHONPATH'] = str(ROOT / 'src')
import numpy
import torch
from acceptance import verify

result = verify(ROOT, OUTPUT)
after = identities()
head_after = git('rev-parse', 'HEAD')
guard = dict(source_commit_before=SOURCE, source_commit_after=head_after,
             actual_python_sources=before, sources_unchanged=before == after,
             head_unchanged=head_after == SOURCE,
             python_executable=sys.executable, python_version=sys.version,
             python_executable_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
             numpy=numpy.__version__, torch=torch.__version__,
             scope='Integrated engineering regression and historical evidence checks; no registered research, training or LLM experiment.')
with (OUTPUT / 'source-guard.json').open('x', encoding='utf-8', newline='\n') as stream:
    stream.write(json.dumps(guard, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
passed = (result['overall'] == 'PASS' and before == after and head_after == SOURCE
          and result['tests']['skipped'] == 0 and result['tests']['failures'] == 0
          and result['tests']['errors'] == 0)
print(json.dumps(dict(source=SOURCE, overall=result['overall'], tests=result.get('tests'),
                      verified_original_files=result.get('verified_original_files'),
                      source_guard='PASS' if before == after and head_after == SOURCE else 'FAIL',
                      guarded_python_files=len(before), output=str(OUTPUT),
                      error=result.get('error'), root_gate='PASS' if passed else 'FAIL'),
                 ensure_ascii=False, allow_nan=False))
raise SystemExit(0 if passed else 1)
