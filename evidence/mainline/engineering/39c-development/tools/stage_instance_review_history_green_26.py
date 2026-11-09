"""Freeze one green-only public lifecycle projection qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

if sys.flags.optimize:raise SystemExit('Optimized source authoring is forbidden')
root=Path.cwd();parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['green']);args=parser.parse_args()
control=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
if subprocess.check_output(['git','status','--porcelain'],cwd=root).strip():raise SystemExit('Freeze from a clean Git tree')
protocol='docs/mainline/39c-instance-review-history-projection-protocol-26.json'
authority='docs/mainline/39c-instance-review-history-green-authority-26.json'
baseline='9ad3afd8503964f5fea9582a603b952ec3adf000'
test='tests/test_instance_review_authority_expiry.py'
seed='tests/fixtures/39c-two-instance-public-seed-21.json'
output=root/'.work/39c-review26-container'/('green-'+control[:8])
output.mkdir(parents=True,exist_ok=False)
git=lambda *values:subprocess.check_output(['git',*values],cwd=root)
protocol_data=json.loads(git('show',control+':'+protocol))
test_blob=git('rev-parse',control+':'+test).decode().strip()
test_bytes=git('show',control+':'+test)
seed_blob=git('rev-parse',baseline+':'+seed).decode().strip()
if test_blob!=protocol_data['fixed_test_blob'] or hashlib.sha256(test_bytes).hexdigest()!=protocol_data['fixed_test_sha256']:
    raise SystemExit('Frozen expiry test identity differs')
if git('rev-parse',control+':'+seed).decode().strip()!=seed_blob:
    raise SystemExit('The frozen seed changed after its original red')
if protocol_data['fixed_seed_blob']!=seed_blob:
    raise SystemExit('Frozen expiry seed identity differs')
red_receipt='evidence/mainline/engineering/39c-development/slice-25/red-result.json'
red=json.loads(git('show',control+':'+red_receipt))
if red['status']!='EXPECTED_RED_CONTRACT_GAP' or red['expiry_behavior_proved']:
    raise SystemExit('Protocol25 red is not the retained expected contract gap')
if hashlib.sha256(git('show',control+':'+red_receipt)).hexdigest()!=protocol_data['prior_red']['receipt_sha256']:
    raise SystemExit('Prior red receipt differs from protocol26 pin')
red_manifest='evidence/mainline/engineering/39c-development/slice-25/protocol25-red-manifest.json'
red_archive='evidence/mainline/engineering/39c-development/slice-25/protocol25-red-source-snapshot.zip'
if hashlib.sha256(git('show',control+':'+red_manifest)).hexdigest()!=protocol_data['prior_red']['manifest_sha256']:
    raise SystemExit('Prior red manifest differs from protocol26 pin')
if hashlib.sha256(git('show',control+':'+red_archive)).hexdigest()!=protocol_data['prior_red']['source_snapshot_sha256']:
    raise SystemExit('Prior red source archive differs from protocol26 pin')
runtime=git('ls-tree','-r','--name-only',control,'--','src/aegis_dc','src/patrol_rsi/__init__.py','src/patrol_rsi/contracts.py').decode().splitlines()
common=['.gitattributes','.gitignore','pyproject.toml','scripts/run_engineering_slice.py',
    'tests/fixtures/39c-two-instance-public-seed-21.json','tests/test_instance_review.py',
    'docs/mainline/39c-instance-review-contract-21.md','docs/mainline/39c-instance-review-protocol-21.json']
for name in common:
    expected=git('show',baseline+':'+name)
    if git('show',control+':'+name)!=expected:
        raise SystemExit('Red/green common seed/test contract changed: '+name)
names=sorted(set(runtime+common+[test,protocol,authority,red_receipt,
    red_manifest,red_archive,
    'evidence/mainline/engineering/39c-development/slice-25/protocol25-red-attempt.json',
    'evidence/mainline/engineering/39c-development/slice-25/protocol25-red-terminal.json',
    'evidence/mainline/engineering/39c-development/slice-25/protocol25-red-test.log',
    'evidence/mainline/engineering/39c-development/slice-25/protocol25-red-frozen-public-call-input.json',
    'docs/mainline/39c-instance-review-authority-expiry-protocol-25.json',
    'docs/mainline/39c-instance-review-history-projection-protocol-26.json',
    'evidence/mainline/engineering/39c-development/slice-24/green-result.json',
    'evidence/mainline/engineering/39c-development/slice-24/protocol24-green-terminal.json',
    'evidence/mainline/engineering/39c-development/tools/run_remote_engineering_slice_22.py',
    'evidence/mainline/engineering/39c-development/tools/stage_instance_review_authority_expiry_25.py',
    'evidence/mainline/engineering/39c-development/tools/stage_instance_review_history_green_26.py']))
test_names=protocol_data['test_names']
module=Path(test).stem
if any(not name.startswith(module+'.') for name in test_names):raise SystemExit('Selected test prefix differs')
files={name:git('show',baseline+':'+name) if name in common else git('show',control+':'+name) for name in names}
blob_ids={name:git('rev-parse',baseline+':'+name).decode().strip() if name in common else
    git('rev-parse',control+':'+name).decode().strip() for name in names}
attempt='33-instance-review-expiry-history-green-v26'
attempt_root='/root/private_data/aegisdc-mainline-39c/33-instance-review-expiry-history-green-v26'
manifest={'schema':'aegisdc-remote-container-engineering-manifest-v1',
    'classification':'REMOTE_CONTAINER_ENGINEERING_NOT_RESEARCH','protocol':protocol,'phase':'green',
    'attempt':attempt,'execution_source':control,'control_source':control,
    'expected_host':{'hostname':'crdnotebook-2108427285948563457-scnnxa6cio-89329','python':'3.12.7','user':'root',
        'persistent_mount':'/root/private_data','project_root':'/root/private_data/aegisdc-mainline-39c'},
    'attempt_root':attempt_root,'test':test,'test_names':test_names,'tests':1,'direct_public_choice_calls':1,
    'facility_entries':0,'max_returned_decisions':0,'watchdog_s':120,'fixed_seed':protocol_data['fixed_seed'],
    'prior_red_result':{'path':red_receipt,'sha256':protocol_data['prior_red']['receipt_sha256'],
        'status':'EXPECTED_RED_CONTRACT_GAP_NOT_EXPIRY_PROOF'},
    'expected_current_question':{'as_of_s':7,'question_id':'cooling-direct/question-1',
        'status':'OPEN_UNCONFIRMED','question_closed':False,'risk_closed':False,'disposition_record_ids':[]},
    'expected_historical_event':{'arrival_s':5.5,'status_at_arrival':'RISK_ACCEPTED',
        'question_closed_at_arrival':True,'risk_closed_at_arrival':False,
        'physical_restoration_claim_at_arrival':False,'record_id':'accept-risk-expiry-25'},
    'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'git_blob':blob_ids[name]} for name,data in files.items()}}
archive=output/'source-snapshot.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
    for name,data in files.items():bundle.writestr(name,data)
manifest['snapshot_bytes']=archive.stat().st_size;manifest['snapshot_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
with (output/'manifest.json').open('x',encoding='utf-8',newline='\n') as stream:
    json.dump(manifest,stream,ensure_ascii=False,indent=2);stream.write('\n')
runner=files['evidence/mainline/engineering/39c-development/tools/run_remote_engineering_slice_22.py']
with (output/'runner.py').open('xb') as stream:stream.write(runner)
print(json.dumps({'phase':'green','attempt':attempt,'execution_source':control,'files':len(files),
    'snapshot_bytes':archive.stat().st_size,'snapshot_sha256':manifest['snapshot_sha256'],
    'manifest_sha256':hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest()}))
