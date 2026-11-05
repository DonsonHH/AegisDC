"""Read-only ticket17 committed-data verification; no model, full-check or physics rerun."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from build_nonfixed_fixture import build, encoded, PROFILE, PLAN, RUNBOOK
from capture_nonfixed_engineering import file_sha,git_blob_sha,is_cache
from nonfixed_engineering_checks import check_package, require
from plot_nonfixed_evidence import render


def safe(root,name):
    require(type(name) is str and bool(name),'Declared path is not text')
    path=(root/name).resolve()
    require(path.is_relative_to(root.resolve()) and path!=root.resolve(),'Declared path escapes root')
    require(not is_cache(path),'A runtime cache cannot be durable evidence')
    return path


def verify(root,directory,delivery_revision):
    root,directory=root.resolve(),directory.resolve();relative=directory.relative_to(root).as_posix()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    delivery=subprocess.check_output(['git','rev-parse',delivery_revision],cwd=root,text=True).strip()
    require(head==delivery,'Use a fresh checkout of the declared delivery revision')
    read=lambda name:json.loads((directory/name).read_text(encoding='utf-8'))
    receipt,declaration=read('receipt.json'),read('declaration.json')
    require(receipt['schema']=='aegisdc-nonfixed-engineering-receipt-v1','Unknown original receipt')
    require(declaration['schema']=='aegisdc-nonfixed-delivery-declaration-v1','Unknown original declaration')
    require(receipt['engineering_capture']=='PASS','Failed original capture remains failed')
    require(receipt['delivery_gate']=='PENDING_COMMIT_AND_FRESH_CHECKOUT','Original receipt was rewritten')
    declared=declaration['declared_artifacts']
    require(len(declared)==len(set(declared)) and set(declared)==set(receipt['artifacts']),'Durable declaration/hash set differs')
    require(receipt['missing_declared_artifacts']==receipt['unexpected_durable_artifacts']==[],'Original durable delivery was incomplete')
    actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and not is_cache(p)}
    require(actual==set(declared)|{'receipt.json'},'Unexpected or missing durable file')
    for name,expected in receipt['artifacts'].items():
        require(file_sha(safe(directory,name))==expected,'Original artifact changed: '+name)
        require(git_blob_sha(root,delivery,relative+'/'+name)==expected,'Committed original differs: '+name)
    require(file_sha(directory/'receipt.json')==git_blob_sha(root,delivery,relative+'/receipt.json'),'Original receipt differs from delivery Git blob')
    execution=receipt['execution_commit']
    require(subprocess.run(['git','merge-base','--is-ancestor',execution,delivery],cwd=root).returncode==0,'Execution is not an ancestor of delivery')
    # Verify the recorded set, not a future tree enumeration: integrated adapters may add new modules.
    for group,names in declaration['pinned_paths'].items():
        require(len(names)==len(set(names)) and set(names)==set(receipt[group]),'Recorded pin set differs: '+group)
        for name,expected in receipt[group].items():
            require(file_sha(safe(root,name))==expected,'Pinned bytes drifted: '+name)
            require(git_blob_sha(root,execution,name)==expected,'Recorded execution blob differs: '+name)
            require(git_blob_sha(root,delivery,name)==expected,'Delivery source/input blob differs: '+name)
    require(receipt['python']==dict(version=sys.version,implementation=sys.implementation.name,executable_sha256=file_sha(sys.executable)),'Verification interpreter differs')
    require(receipt['numpy_version']==importlib.metadata.version('numpy'),'Verification NumPy differs')
    for source,label in [(PROFILE,'profile'),(PLAN,'private-plan'),(RUNBOOK,'runbook')]:
        require((directory/(label+'-copy.json')).read_bytes()==(root/source).read_bytes(),'Frozen input copy differs: '+label)
        require(encoded(build(root)[source])==(directory/(label+'-rebuilt.json')).read_bytes()==(root/source).read_bytes(),'Pinned authoring output differs: '+label)
    checks=check_package(directory)
    require(checks==receipt['independent_checks']==read('independent-checks.json'),'Independent literal checks differ')
    pair=read('private-noninterference.json')
    require(pair['before'][0]==pair['before'][1] and pair['after'][0]==pair['after'][1],'Saved private pair public outputs differ')
    require(pair['private_audits'][0]['events'][0]['private_source']['run_sha256']!=pair['private_audits'][1]['events'][0]['private_source']['run_sha256'],'Paired private sources were not distinct')
    for identifier in ['arrived','before-arrival','no-fixed']:
        cli=read('cli/'+identifier+'/receipt.json')
        identity=cli['source_identity']
        require(identity['git_commit']==execution and identity['implementation_has_changes'] is False,'CLI execution identity differs')
        for name,expected in identity['files'].items():
            require(receipt['runtime_sources'][name]==expected and git_blob_sha(root,execution,name)==expected,'CLI executed source differs: '+name)
        for name,expected in cli['artifacts'].items():
            require(file_sha(directory/'cli'/identifier/name)==expected,'Nested CLI original differs')
    with tempfile.TemporaryDirectory(prefix='aegisdc-17-figure-') as temporary:
        render(directory,Path(temporary))
        for name in ['observation-timing.svg','source-authority.svg']:
            require(file_sha(Path(temporary)/name)==file_sha(directory/'figures'/name),'Data-derived SVG does not reproduce')
    regression=read('full-check/summary.json')
    require(regression['overall']=='PASS' and receipt['full_regression_executions']==1,'One author full regression is required')
    require(regression['tests']==receipt['full_tests'] and regression['tests']['gate']=='PASS' and not regression['tests']['unexpected_skips'],'Saved full test gate differs')
    require(receipt['new_physics_execution'] is False and receipt['professional_execution_connected'] is False,'Fixture was promoted to physical/executor qualification')
    for name in ['registered_research_trials','model_calls','training_calls']:
        require(receipt[name]==0,'Engineering delivery claims research/model/training execution')
    return dict(schema='aegisdc-nonfixed-fresh-delivery-proof-v1',status='PASS',execution_commit=execution,
        delivery_commit=delivery,artifacts=len(declared),terminal_receipts=1,
        pinned_runtime_sources=len(receipt['runtime_sources']),
        pinned_authoring_verification_tools=len(receipt['authoring_verification_tools']),
        pinned_inputs_and_development_originals=len(receipt['frozen_inputs']),
        independent_checks=checks,actual_author_full_tests=regression['tests'],
        full_regression_rerun=False,new_physics_execution=False,original_receipt_rewritten=False,
        historical_physical_maximum_step_s=1.0,professional_execution_connected=False,
        runtime_caches_required=0,registered_research_trials=0,model_calls=0,training_calls=0,
        research_gain_claim='NOT_ESTABLISHED',field_calibration='PENDING')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--delivery',required=True)
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=verify(args.root,args.capture,args.delivery)
    if args.output:
        with args.output.open('xb') as stream:stream.write(encoded(result))
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
