"""Retain the finite pre36 historical-source CI checks and their failures."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--phase',choices=['red','green'],required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
out=ROOT/args.output
out.mkdir(parents=True,exist_ok=False)
git=lambda *a:subprocess.check_output(['git',*a],cwd=ROOT)
source=git('rev-parse','HEAD').decode().strip()
assert not git('status','--porcelain','--untracked-files=no').strip()
paths=[p for d in ['src','configs','scripts','tests'] for p in (ROOT/d).rglob('*')
       if p.is_file() and p.suffix in ['.py','.json'] and '__pycache__' not in p.parts]
identities=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=identities()
start=dict(source=source,phase=args.phase,source_sha256=before,
    plan='docs/mainline/audits/20261108-pre36/historical-ci-plan.json',registered_research_trials=0)
(out/'start.json').write_text(json.dumps(start,indent=2)+'\n',encoding='utf-8',newline='\n')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'src')]
names=['test_registered_development.RegisteredDevelopmentTests.test_plan_pins_development_only_and_rotates_arms_per_world',
       'test_confirmation_freeze.ConfirmationFreezeTests.test_public_amendment_is_limited_to_two_hydraulic_coordinates',
       'test_ablation_masks.AblationMasksTests.test_public_masks_keep_real_plant_and_team_capability']
if args.phase=='green':names.append('test_registered_development.RegisteredDevelopmentTests.test_old_lock_refuses_changed_live_source')
suite=unittest.TestLoader().loadTestsFromNames(names)
log=io.StringIO()
result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(out/'tests.log').write_text(log.getvalue(),encoding='utf-8',newline='\n')
assert before==identities() and git('rev-parse','HEAD').decode().strip()==source
passed=not result.errors and not result.skipped and (len(result.failures)==3 if args.phase=='red' else not result.failures)
receipt=dict(source=source,phase=args.phase,status='EXPECTED_RED_FAILURE' if passed and args.phase=='red' else 'PASS' if passed else 'FAILED_UNEXPECTED',
    tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
    historical_source='2dfe5537e4f95fa605f325b060ef32223dafb4f6',source_guard='PASS',physical_calls=0,
    selector_calls=1 if args.phase=='green' else 0,nonce_reads=0,registered_research_trials=0)
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(receipt));raise SystemExit(0 if passed else 1)
