"""Guard the actual public-test execution dependencies for ticket-11 review."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
repo=Path('C:/Users/Donson/Documents/ChatGPT/Renly/.work/worktrees/full-site-11')
freeze='b135ecffb5fe5c3fecaa44859afbf925b8549bb1'
output=Path('C:/Users/Donson/AppData/Local/Temp/aegisdc-review-11-spec-attachments/guarded-targets-b135-01')
output.mkdir(exist_ok=False)
def git(*args):return subprocess.check_output(['git',*args],cwd=repo)
tracked=git('ls-tree','-r','--name-only',freeze).decode().splitlines()
names=[p for p in tracked if p.startswith('src/aegis_dc/') or p in (
    'src/patrol_rsi/contracts.py','tests/test_mainline_coupled.py',
    'docs/mainline/11-coupled-runbook.json','configs/full-facility-mainline-reserve-v6.json',
    'configs/materials/reference-r134a-saturation.json')]
expected={name:sha256(git('cat-file','blob',freeze+':'+name)).hexdigest() for name in names}
def guard():
    actual={name:sha256((repo/name).read_bytes()).hexdigest() for name in names}
    assert actual==expected,'Test dependency bytes changed from the frozen source'
    assert not git('status','--porcelain','--',*names).decode().strip(),'Protected paths are changing'
    return {'head':git('rev-parse','HEAD').decode().strip(),'protected_file_sha256':actual}
before=guard()
command=[sys.executable,'-B','-X','utf8','-m','unittest','discover','-s','tests','-p','test_mainline_coupled.py','-v']
result=subprocess.run(command,cwd=repo,env=dict(os.environ,PYTHONPATH=str(repo/'src'),
    PYTHONDONTWRITEBYTECODE='1'),capture_output=True)
(output/'stdout.txt').write_bytes(result.stdout);(output/'stderr.txt').write_bytes(result.stderr)
after=guard()
count=int(re.search(r'Ran (\d+) tests',result.stderr.decode('utf-8')).group(1))
record={'classification':'SOURCE_GUARDED_FOCUSED_ENGINEERING_REVIEW_NOT_FULL_REGRESSION',
    'frozen_test_dependency_commit':freeze,'before':before,'after':after,
    'command':command,'working_directory':str(repo),'executed_tests':count,'exit_code':result.returncode,
    'stdout_sha256':sha256(result.stdout).hexdigest(),'stderr_sha256':sha256(result.stderr).hexdigest(),
    'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
    'note':'Guard covers actual test/runtime/config/runbook dependencies. Plot-only revisions are independently reviewed, not misattributed as test execution.',
    'full_regression_run':False,'registered_research_trials':0}
p=output/'receipt.json'
with p.open('x',encoding='utf-8') as stream:stream.write(json.dumps(record,indent=2,allow_nan=False)+'\n')
assert result.returncode==0 and count==17,'Focused tests failed; original stdout/stderr retained'
print(json.dumps({'status':'PASS','tests':count,'protected_files':len(names),'receipt':str(p),'sha256':sha256(p.read_bytes()).hexdigest()}))
