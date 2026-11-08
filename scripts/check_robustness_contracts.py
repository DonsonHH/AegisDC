"""Retain pure CLI red/green behavior evidence; never execute a facility."""
import argparse,hashlib,io,json,os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['red','green'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
out=ROOT/a.output;out.mkdir(parents=True,exist_ok=False)
git=lambda *args:subprocess.check_output(['git',*args],cwd=ROOT)
source=git('rev-parse','HEAD').decode().strip();assert not git('status','--porcelain','--untracked-files=no').strip()
names=git('ls-files','-z','src','scripts','configs','tests','docs/mainline/36-prospective-extension.json').decode().strip('\0').split('\0')
names=[n for n in names if n.endswith(('.py','.json'))]
identities=lambda:{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
before=identities();(out/'start.json').write_text(json.dumps(dict(source=source,phase=a.phase,pins=before),indent=2)+'\n',encoding='utf-8',newline='\n')
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'tests'))
log=io.StringIO();suite=unittest.TestLoader().loadTestsFromName('test_robustness_release');result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(out/'tests.log').write_text(log.getvalue(),encoding='utf-8',newline='\n')
assert before==identities() and git('rev-parse','HEAD').decode().strip()==source
expected=not result.errors and not result.skipped and (len(result.failures)==2 if a.phase=='red' else not result.failures)
receipt=dict(source=source,phase=a.phase,status='EXPECTED_RED_FAILURE' if a.phase=='red' and expected else 'PASS' if expected else 'FAILED_UNEXPECTED',
    tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),source_guard='PASS',
    admission_calls=0,physical_calls=0,selector_calls=0,nonce_reads=0,registered_research_trials=0)
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(receipt));raise SystemExit(0 if expected else 1)
