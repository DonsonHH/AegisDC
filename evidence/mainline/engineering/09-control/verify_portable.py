"""Audit the committed durable ticket-09 evidence; no imports or simulation calls."""
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import sys

SCRIPT=Path(__file__).resolve()
ROOT=SCRIPT.parents[4]
BASE=SCRIPT.parent
EXPECTED_CACHES={
    'evidence/mainline/engineering/09-control/__pycache__/capture_engineering.cpython-312.pyc',
    'evidence/mainline/engineering/09-control/__pycache__/full_acceptance.cpython-312.pyc'}


def require(condition,message):
    if not condition:raise ValueError(message)


def digest(path):return sha256(path.read_bytes()).hexdigest()


def git_bytes(revision,name):
    return subprocess.check_output(['git','cat-file','blob',revision+':'+name],cwd=ROOT)


def committed_file(name,expected=None):
    path=ROOT/name
    require(path.resolve().is_relative_to(ROOT),'Evidence path leaves the checkout: '+name)
    actual=digest(path)
    require(actual==sha256(git_bytes('HEAD',name)).hexdigest(),'Working bytes differ from committed delivery: '+name)
    if expected is not None:require(actual==expected,'Persistent evidence SHA mismatch: '+name)
    return actual


def read_json(path):
    def invalid(value):raise ValueError('Nonfinite JSON constant: '+value)
    return json.loads(path.read_text(encoding='utf-8'),parse_constant=invalid)


def main():
    program=str(SCRIPT.relative_to(ROOT)).replace('\\','/')
    program_sha=committed_file(program)
    manifest_path=BASE/'portable-inventory-v2.json'
    manifest_sha=committed_file(str(manifest_path.relative_to(ROOT)).replace('\\','/'))
    portable=read_json(manifest_path)
    require(portable['schema']=='aegisdc-control-portable-inventory-v2','Unknown portable schema')
    original=portable['original_inventory']
    committed_file(original['path'],original['sha256'])
    local=read_json(ROOT/original['path'])
    old=local['prior_engineering_files_sha256'];durable=portable['durable_files_sha256']
    excluded=portable['excluded_non_delivery']
    require(len(old)==164 and len(durable)==162 and len(excluded)==2,'Inventory count mismatch')
    require({r['path'] for r in excluded}==EXPECTED_CACHES,'Unexpected or missing cache exclusions')
    require(set(durable).isdisjoint(EXPECTED_CACHES) and set(durable)|EXPECTED_CACHES==set(old),'Classification must cover exactly the original inventory')
    require(all(old[name]==value for name,value in durable.items()),'Durable classification changed an original SHA')
    delivery_paths=set(subprocess.check_output(['git','ls-tree','-r','--name-only',portable['delivery_commit']],cwd=ROOT,text=True).splitlines())
    current_paths=set(subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD'],cwd=ROOT,text=True).splitlines())
    cache_observations=[]
    for item in excluded:
        name=item['path']
        require(item['original_observed_sha256']==old[name] and item['git_tracked_at_delivery'] is False,'Cache classification altered the original observation')
        require(name not in delivery_paths and name not in current_paths,'A tracked file cannot be excluded as non-delivery cache')
        path=ROOT/name
        cache_observations.append({'path':name,'state':'present' if path.exists() else 'absent',
            'current_sha256':digest(path) if path.exists() else None,
            'matches_author_local_observation':digest(path)==old[name] if path.exists() else None})
    for name,value in durable.items():
        require(name in delivery_paths,'Durable file absent from original delivery: '+name)
        require(sha256(git_bytes(portable['delivery_commit'],name)).hexdigest()==value,'Original delivery blob mismatch: '+name)
        committed_file(name,value)
    for name,row in local['frozen_legacy_inputs'].items():
        committed_file(name,row['sha256'])
        blob=subprocess.check_output(['git','rev-parse','HEAD:'+name],cwd=ROOT,text=True).strip()
        require(blob==row['git_blob'],'Legacy input Git blob mismatch: '+name)
    record_path=BASE/'fixtures-363c5edf/receipt.json'
    committed_file(str(record_path.relative_to(ROOT)).replace('\\','/'))
    record=read_json(record_path);execution=portable['execution_commit']
    require(record['source_commit']==local['committed_execution']==execution,'Recorded execution identity mismatch')
    for name,value in record['artifacts'].items():
        committed_file(str((record_path.parent/name).relative_to(ROOT)).replace('\\','/'),value)
    book=read_json(BASE/'runbook-v1.json')
    declared={case['id']:case['expected_summary'] for case in book['cases']}
    require(set(declared)==set(record['runs']) and len(declared)==12,'Frozen runbook/case mismatch')
    source_current_matches=True;max_energy=max_mass=0.0
    for name,observed in record['runs'].items():
        folder=record_path.parent/name;run=read_json(folder/'run.json')
        require(run['code_identity']['git_commit']==execution and run['code_identity']['implementation_has_changes'] is False,'Run is not the original clean execution: '+name)
        for source,value in run['code_identity']['files'].items():
            require(sha256(git_bytes(execution,source)).hexdigest()==value,'Recorded execution source blob mismatch: '+source)
            source_current_matches &= (ROOT/source).is_file() and digest(ROOT/source)==value
        for artifact,identity in run['artifacts'].items():
            path=folder/artifact
            require(digest(path)==identity['sha256'],'Run artifact identity mismatch: '+name+'/'+artifact)
            if artifact.endswith('.jsonl'):require(len(path.read_text(encoding='utf-8').splitlines())==identity['records'],'Record-count mismatch: '+name+'/'+artifact)
        trace=[read_json_line for read_json_line in map(json.loads,(folder/'private-state.jsonl').read_text(encoding='utf-8').splitlines())]
        balances=list(map(json.loads,(folder/'balances.jsonl').read_text(encoding='utf-8').splitlines()))
        require(all(len(row['domains'])==8 for row in trace),'Incomplete facility trace')
        require(all(row['domains']['control_monitoring']['local_measurement']['visibility']=='LOCAL_PLANT_ONLY' for row in trace),'Local record visibility mismatch')
        require(run['state_visibility']=='PRIVATE_PLANT_EVALUATOR_ONLY','Evaluator visibility mismatch')
        require(run['model_calls']==run['training_calls']==run['research_trials']==0,'Unexpected research/model/training count')
        require(observed['expected_summary']==declared[name],'Receipt expectation differs from frozen runbook')
        for key,value in declared[name].items():require(abs(run['summary'][key]-value)<1e-8,'Independent account mismatch: '+name+'/'+key)
        for row in balances:
            before=math.fsum(row['storage_before_J'].values());after=math.fsum(row['storage_after_J'].values())
            energy=after-before-row['boundary_input_J']+row['boundary_output_J']
            require(abs(energy)<0.01,'Recomputed facility energy account failed: '+name)
            max_energy=max(max_energy,abs(energy))
            for account in row['mass_accounts_kg'].values():
                residual=math.fsum([account['before_kg'],account['in_kg'],-account['out_kg'],-account['after_kg']])
                require(abs(residual)<1e-8,'Recomputed medium mass account failed: '+name)
                max_mass=max(max_mass,abs(residual))
        require(abs(run['summary']['whole_run_energy_residual_J'])<0.01,'Whole-run account failed: '+name)
    refused=read_json(record_path.parent/'expected-refusals.json')
    require(len(refused)==record['expected_refusals']==6,'Refusal count mismatch')
    require(all(r['outcome']=='EXPECTED_REFUSAL' and r['successful_trajectory_returned'] is False and r['error'] for r in refused),'Refusal lifecycle mismatch')
    print(json.dumps({'status':'PASS','schema':portable['schema'],
        'checked_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'verifier_sha256':program_sha,'portable_manifest_sha256':manifest_sha,
        'original_inventory_sha256':original['sha256'],'durable_files_hash_and_git_blob_checked':len(durable),
        'excluded_non_delivery':cache_observations,'legacy_inputs_hash_and_git_blob_checked':len(local['frozen_legacy_inputs']),
        'engineering_artifacts_hash_and_git_blob_checked':len(record['artifacts']),'saved_cases_checked':len(record['runs']),
        'expected_refusals_checked':len(refused),'actual_execution_commit':execution,
        'source_verification':'RECORDED_EXECUTION_COMMIT_GIT_BLOBS','current_source_matches_execution':bool(source_current_matches),
        'recomputed_max_step_energy_residual_J':max_energy,'recomputed_max_mass_residual_kg':max_mass,
        'new_simulations':0,'new_research_trials':0,'full_regression_repeated':False,
        'M1_gate':'IN_PROGRESS','overall_goal':'ACTIVE'},indent=2,allow_nan=False))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print(json.dumps({'status':'FAIL','error':str(error),'new_simulations':0}),file=sys.stderr)
        sys.exit(1)
