"""Run the frozen pre36 finite API engineering checks with retained attempts."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--phase', choices=['red','green','compatibility'], required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
out = args.output if args.output.is_absolute() else ROOT/args.output
out.mkdir(parents=True, exist_ok=False)
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
git=lambda *v:subprocess.check_output(['git',*v],cwd=ROOT)
source=git('rev-parse','HEAD').decode().strip()
paths=sorted(p for directory in ['src','configs','tests'] for p in (ROOT/directory).rglob('*')
    if p.is_file() and p.suffix in ['.py','.json'] and '__pycache__' not in p.parts)
paths += [Path(__file__),ROOT/'docs/mainline/audits/20261108-pre36/closure-review-engineering-plan.json']
def identities():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=identities()
start=dict(phase=args.phase,source=source,started_utc=datetime.now(timezone.utc).isoformat(),
    engineering_scope='Finite closure/risk/belief API calculations; no plant, selector, RNG or registered trial.',source_sha256=before)
(out/'start.json').write_text(json.dumps(start,indent=2)+'\n',encoding='utf-8',newline='\n')
old=git('show','2dfe5537e4f95fa605f325b060ef32223dafb4f6:src/aegis_dc/verified_closure.py')
current=(ROOT/'src/aegis_dc/verified_closure.py').read_bytes()
assert (old==current) == (args.phase=='red'),'Wrong source for declared red/green phase'
from aegis_dc import verified_closure
counts={'closure_assessment_calls':0}
original=verified_closure.assess_closure
def observed_assessment(*values,**options):
    counts['closure_assessment_calls']+=1
    return original(*values,**options)
verified_closure.assess_closure=observed_assessment
loader=unittest.TestLoader()
suite=loader.loadTestsFromName('test_pre36_closure_review_time')
if args.phase=='compatibility':suite=unittest.TestSuite([loader.loadTestsFromName('test_verified_closure'),suite])
log=io.StringIO()
try:result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
finally:verified_closure.assess_closure=original
(out/'tests.log').write_text(log.getvalue(),encoding='utf-8',newline='\n')
after=identities();assert after==before and git('rev-parse','HEAD').decode().strip()==source,'Source changed during engineering check'
raw_pass=not result.failures and not result.errors and not result.skipped
expected=(bool(result.failures) and not result.errors and not result.skipped) if args.phase=='red' else raw_pass
receipt=dict(status=('EXPECTED_RED_ASSERTION_FAILURE' if args.phase=='red' else 'PASS') if expected else 'FAILED_UNEXPECTED',
    phase=args.phase,source=source,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
    raw_suite_outcome='PASS' if raw_pass else 'FAIL',**counts,source_guard='PASS',
    physical_calls=0,selector_calls=0,training_llm_calls=0,random_or_nonce_reads=0,registered_research_trials=0,
    internal_scope='Existing finite public risk/belief computations are part of these engineering API calls, not independent research evaluations.')
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(receipt));raise SystemExit(0 if expected else 1)
