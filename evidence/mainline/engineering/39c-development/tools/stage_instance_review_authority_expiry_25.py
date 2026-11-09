"""Freeze one public expired-authority qualification for the remote container."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

if sys.flags.optimize:raise SystemExit('Optimized source authoring is forbidden')
root=Path.cwd();parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['red','green']);args=parser.parse_args()
phase=args.phase;control=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
if subprocess.check_output(['git','status','--porcelain'],cwd=root).strip():raise SystemExit('Freeze from a clean Git tree')
protocol='docs/mainline/39c-instance-review-authority-expiry-protocol-25.json'
execution={'red':'9ad3afd8503964f5fea9582a603b952ec3adf000',
           'green':'d823a68f5af03d5d464d1f2dd45d14fbe5b9e8f0'}[phase]
test='tests/test_instance_review_authority_expiry.py'
seed='tests/fixtures/39c-two-instance-public-seed-21.json'
output=root/'.work/39c-review25-container'/(phase+'-'+control[:8])
output.mkdir(parents=True,exist_ok=False)
git=lambda *values:subprocess.check_output(['git',*values],cwd=root)
for name in ['.gitattributes','.gitignore','pyproject.toml','scripts/run_engineering_slice.py',
             seed,'tests/test_instance_review.py','docs/mainline/39c-instance-review-contract-21.md',
             'docs/mainline/39c-instance-review-protocol-21.json']:
    expected=git('show','9ad3afd8503964f5fea9582a603b952ec3adf000:'+name)
    if git('show',execution+':'+name)!=expected:
        raise SystemExit('Frozen common test/seed/contract changed: '+name)
    if git('show',control+':'+name)!=expected:
        raise SystemExit('Control test/seed/contract differs: '+name)
protocol_data=json.loads(git('show',control+':'+protocol))
if protocol_data['test']['git_blob']!=git('rev-parse',control+':'+test).decode().strip():
    raise SystemExit('Negative test blob differs from frozen protocol')
if hashlib.sha256(git('show',control+':'+test)).hexdigest()!=protocol_data['test']['sha256']:
    raise SystemExit('Negative test SHA-256 differs from frozen protocol')
if protocol_data['seed']['git_blob']!=git('rev-parse',execution+':'+seed).decode().strip():
    raise SystemExit('Seed identity differs from frozen protocol')
runtime=git('ls-tree','-r','--name-only',execution,'--','src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py').decode().splitlines()
common=['.gitattributes','.gitignore','pyproject.toml','scripts/run_engineering_slice.py',seed,
    'tests/test_instance_review.py','docs/mainline/39c-instance-review-contract-21.md',
    'docs/mainline/39c-instance-review-protocol-21.json']
names=sorted(set(runtime+common+[test,protocol,
    'evidence/mainline/engineering/39c-development/tools/run_remote_engineering_slice_22.py',
    'evidence/mainline/engineering/39c-development/tools/stage_instance_review_authority_expiry_25.py']))
test_names=protocol_data['test']['test_names'];module=Path(test).stem
if any(not name.startswith(module+'.') for name in test_names):raise SystemExit('Selected test module prefix differs')
if test_names!=['test_instance_review_authority_expiry.InstanceReviewAuthorityExpiryTests.test_expired_current_authority_does_not_close_question']:
    raise SystemExit('Frozen negative test name differs')
def source_for(name):
    if name in common or name.startswith(('src/','configs/')):return execution
    if name==test:return control
    return control
files={name:git('show',source_for(name)+':'+name) for name in names}
blob_ids={name:git('rev-parse',source_for(name)+':'+name).decode().strip() for name in names}
attempt=('31-instance-review-expiry-red-v25' if phase=='red' else '32-instance-review-expiry-green-v25')
output_root=('/root/private_data/aegisdc-mainline-39c/31-instance-review-expiry-red-v25' if phase=='red' else
    '/root/private_data/aegisdc-mainline-39c/32-instance-review-expiry-green-v25')
manifest={'schema':'aegisdc-remote-container-engineering-manifest-v1',
    'classification':'REMOTE_CONTAINER_ENGINEERING_NOT_RESEARCH','protocol':protocol,'phase':phase,'attempt':attempt,
    'execution_source':execution,'control_source':control,
    'expected_host':{'hostname':'crdnotebook-2108427285948563457-scnnxa6cio-89329','python':'3.12.7','user':'root',
        'persistent_mount':'/root/private_data','project_root':'/root/private_data/aegisdc-mainline-39c'},
    'attempt_root':output_root,'test':test,'test_names':test_names,'tests':1,'direct_public_choice_calls':1,
    'facility_entries':0,'max_returned_decisions':0,'expected_red_text':'Unknown instance closure program',
    'watchdog_s':120,'fixed_seed':protocol_data['seed'],
    'alternate_server_dependency_note':'Python3.12.7 / preinstalled NumPy2.1.2; this frozen public test must not import NumPy.',
    'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'git_blob':blob_ids[name]} for name,data in files.items()}}
archive=output/'source-snapshot.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
    for name,data in files.items():bundle.writestr(name,data)
manifest['snapshot_bytes']=archive.stat().st_size;manifest['snapshot_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
with (output/'manifest.json').open('x',encoding='utf-8',newline='\n') as stream:
    json.dump(manifest,stream,ensure_ascii=False,indent=2);stream.write('\n')
runner=files['evidence/mainline/engineering/39c-development/tools/run_remote_engineering_slice_22.py']
with (output/'runner.py').open('xb') as stream:stream.write(runner)
print(json.dumps({'phase':phase,'attempt':attempt,'execution_source':execution,'control_source':control,
    'files':len(files),'snapshot_bytes':archive.stat().st_size,
    'snapshot_sha256':manifest['snapshot_sha256'],
    'manifest_sha256':hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest()}))
