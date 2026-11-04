"""Read the sealed originals after integration without rerunning the plant."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from capture_engineering import fresh_read

ROOT=Path(__file__).resolve().parents[4]
BASE=Path(__file__).resolve().parent
local=json.loads((BASE/'receipt-363c5edf.json').read_text(encoding='utf-8'))
record=json.loads((BASE/'fixtures-363c5edf/receipt.json').read_text(encoding='utf-8'))
for name,expected in local['prior_engineering_files_sha256'].items():
    assert sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
for name,recorded in local['frozen_legacy_inputs'].items():
    assert sha256((ROOT/name).read_bytes()).hexdigest()==recorded['sha256'],name
    assert subprocess.check_output(['git','rev-parse','HEAD:'+name],cwd=ROOT,text=True).strip()==recorded['git_blob'],name
for name,expected in record['artifacts'].items():
    assert sha256((BASE/'fixtures-363c5edf'/name).read_bytes()).hexdigest()==expected,name
for name,run in record['runs'].items():
    fresh_read(BASE/'fixtures-363c5edf'/name,record['source_commit'],run['expected_summary'])
print(json.dumps({'status':'PASS','current_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'original_execution_commit':record['source_commit'],'source_files_match_frozen_execution':True,
    'prior_engineering_files_rehashed':len(local['prior_engineering_files_sha256']),
    'legacy_inputs_hash_and_git_blob_checked':len(local['frozen_legacy_inputs']),
    'engineering_files_rehashed':len(record['artifacts']),'saved_cases_fresh_read':len(record['runs']),
    'full_regression_repeated':False,'research_trials':0,'M1_gate':'IN_PROGRESS','overall_goal':'ACTIVE'},indent=2))
