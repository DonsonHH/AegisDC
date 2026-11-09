"""Build a small SHA-bound source snapshot for a remote persistent container."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

if sys.flags.optimize:raise SystemExit('Optimized source authoring is forbidden')
root=Path.cwd();parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['red','green']);args=parser.parse_args()
phase=args.phase
control=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
if subprocess.check_output(['git','status','--porcelain'],cwd=root).strip():raise SystemExit('Freeze from a clean Git tree')
protocol='docs/mainline/39c-instance-review-container-protocol-23.json'
baseline='9ad3afd8503964f5fea9582a603b952ec3adf000'
execution=baseline if phase=='red' else control
output=root/'.work/39c-review23-container'/phase
output.mkdir(parents=True,exist_ok=False)
git=lambda *values:subprocess.check_output(['git',*values],cwd=root)
names=git('ls-tree','-r','--name-only',execution,'--','src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py').decode().splitlines()
common=['.gitattributes','.gitignore','pyproject.toml','scripts/run_engineering_slice.py','tests/test_instance_review.py',
    'tests/fixtures/39c-two-instance-public-seed-21.json','docs/mainline/39c-instance-review-contract-21.md',
    'docs/mainline/39c-instance-review-protocol-21.json']
for name in common:
    expected=git('show',baseline+':'+name)
    actual=git('show',execution+':'+name)
    if actual!=expected:raise SystemExit('Red/green test/fixture/protocol changed outside frozen behavior: '+name)
names+=common
for name in [protocol,
             'evidence/mainline/engineering/39c-development/slice-22/preflight-rejection.json',
             'evidence/mainline/engineering/39c-development/tools/stage_instance_review_container_22.py',
             'evidence/mainline/engineering/39c-development/tools/run_remote_engineering_slice_22.py']:
    names.append(name)
if phase=='green':names.append('docs/mainline/39c-instance-review-green-authority-24.json')
names=sorted(set(names))
files={name:git('show',(execution if name.startswith(('src/','tests/','configs/')) or name in common else control)+':'+name) for name in names}
blob_ids={name:git('rev-parse',(execution if name.startswith(('src/','tests/','configs/')) or name in common else control)+':'+name).decode().strip() for name in names}
manifest={'schema':'aegisdc-remote-container-engineering-manifest-v1',
    'classification':'REMOTE_CONTAINER_ENGINEERING_NOT_RESEARCH',
    'protocol':protocol,'phase':phase,'attempt':('27-instance-review-container-red-v23' if phase=='red' else
        '28-instance-review-container-green-v23'),
    'execution_source':execution,'control_source':control,
    'expected_host':{'hostname':'crdnotebook-2108427285948563457-scnnxa6cio-89329','python':'3.12.7','user':'root',
        'persistent_mount':'/root/private_data','project_root':'/root/private_data/aegisdc-mainline-39c'},
    'attempt_root':'/root/private_data/aegisdc-mainline-39c/27-instance-review-container-red-v23' if phase=='red' else
        '/root/private_data/aegisdc-mainline-39c/28-instance-review-container-green-v23',
    'test':'tests/test_instance_review.py',
    'test_names':['test_instance_review.InstanceReviewTests.test_arrived_authorized_acceptance_closes_only_its_instance_without_physical_claim'],
    'tests':1,'direct_public_choice_calls':1,'facility_entries':0,'max_returned_decisions':0,
    'expected_red_text':'Unknown instance closure program','watchdog_s':120,
    'original_seed':{'job':'133380','bytes':78111,'sha256':'4f02ef6b8faf1fbbe0270b2b57bd8ce8e688c2fa5f98939ca3bc7eeebb905237'},
    'alternate_server_dependency_note':'Python3.12.7 / preinstalled NumPy2.1.2. The test imports no NumPy because no executed AegisDC source path imports it; remote runner fails if NumPy enters sys.modules.',
    'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'git_blob':blob_ids[name]} for name,data in files.items()}}
archive=output/'source-snapshot.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
    for name,data in files.items():bundle.writestr(name,data)
manifest['snapshot_bytes']=archive.stat().st_size;manifest['snapshot_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
with (output/'manifest.json').open('x',encoding='utf-8',newline='\n') as stream:
    json.dump(manifest,stream,ensure_ascii=False,indent=2);stream.write('\n')
runner=files['evidence/mainline/engineering/39c-development/tools/run_remote_engineering_slice_22.py']
with (output/'runner.py').open('xb') as stream:stream.write(runner)
print(json.dumps({'phase':phase,'execution_source':execution,'control_source':control,'files':len(files),
    'snapshot_bytes':archive.stat().st_size,'snapshot_sha256':manifest['snapshot_sha256'],
    'manifest_sha256':hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest()}))
