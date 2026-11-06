"""Saved-only verification of D-stage originals, recovery proofs and explicit gaps."""
import argparse
from hashlib import sha256
import json
from pathlib import Path,PurePosixPath
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def require(ok,message):
    if not ok:raise ValueError(message)


def digest(raw):return sha256(raw).hexdigest()
def read(path):return json.loads(path.read_bytes())


def verify(folder,delivery=None):
    declaration=read(folder/'declaration.json');receipt=read(folder/'receipt.json')
    names={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    require(names==set(declaration['artifacts'])|{'receipt.json'} and set(receipt['artifacts'])==set(declaration['artifacts']),'Declared package set differs')
    for name,expected in receipt['artifacts'].items():require(digest((folder/name).read_bytes())==expected,'Package artifact differs: '+name)
    require(digest((ROOT/receipt['authoring_tool']).read_bytes())==receipt['authoring_tool_sha256'],'Packager bytes differ')
    if delivery is not None:
        require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==delivery,'Wrong delivery checkout')
        require(not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT),'Use a clean delivery checkout')
        for name in names:
            path=(folder/name).relative_to(ROOT).as_posix()
            require((folder/name).read_bytes()==subprocess.check_output(['git','cat-file','blob',delivery+':'+path],cwd=ROOT),'Committed package blob differs')
    members=read(folder/'archive-members.json');classification=read(folder/'classification.json')
    counts={};sources=0
    with zipfile.ZipFile(folder/'originals.zip') as archive:
        require(len(archive.namelist())==len(set(archive.namelist())) and set(archive.namelist())==set(members),'ZIP member set differs')
        for name,identity in members.items():
            path=PurePosixPath(name)
            require(not path.is_absolute() and '..' not in path.parts and '__pycache__' not in path.parts and path.suffix not in {'.pyc','.pyo'},'Invalid durable ZIP member')
            raw=archive.read(name);require(digest(raw)==identity['sha256'] and len(raw)==identity['bytes'],'ZIP member identity differs')
        for case in classification['cases']:
            prefix='original/'+case['case']+'/'
            attempt=json.loads(archive.read(prefix+'attempt.json'));status=case['original_terminal_status']
            counts[status]=counts.get(status,0)+1
            if status=='NO_TERMINAL':
                require(prefix+'terminal.json' not in members and case['classification']=='TRANSPORT_INTERRUPTED_OUTCOME_UNOBSERVED','Unobserved case was relabeled')
                observation=json.loads(archive.read(case['observation_member']))
                require(observation['status']=='TRANSPORT_INTERRUPTED_OUTCOME_UNOBSERVED' and not observation['original_terminal_exists'],'Interruption observation differs')
            else:require(json.loads(archive.read(prefix+'terminal.json'))['status']==status,'Original terminal status was rewritten')
            require({s['path'] for s in case['source_recovery']}==set(attempt['source_files']),'Runtime source reconstruction incomplete')
            for source in case['source_recovery']:
                require(digest(archive.read(source['member']))==source['sha256']==attempt['source_files'][source['path']],'Actual recorded runtime hash differs')
                sources+=1
            if case['classification']=='COMPLETED_DEVELOPMENT_INTEGRATION_NOT_TEST_ASSERTION_PASS':
                run=json.loads(archive.read(prefix+'original/run.json'))
                require(run['code_identity']['git_commit']==attempt['source_commit'],'Actual executed head differs')
                for name,identity in run['artifacts'].items():require(digest(archive.read(prefix+'original/'+name))==identity['sha256'],'Original saved run artifact differs')
                for name,expected in run['code_identity']['files'].items():require(attempt['source_files'][name]==expected,'Run runtime hash differs')
        observation_names=[n for n in members if n.startswith('observation/')]
        require(len(observation_names)==1,'Interruption observation set differs')
        observation=json.loads(archive.read(observation_names[0]));observed=PurePosixPath(observation['case_folder']).name
        for name,identity in observation['files'].items():require(digest(archive.read('original/'+observed+'/'+name))==identity['sha256'],'Interrupted original differs from observed bytes')
    require(counts==classification['original_terminal_counts'],'Attempt status accounting differs')
    require(receipt['attempts']==classification['public_call_attempt_directories']==len(classification['cases']),'Attempt counts differ')
    require(receipt['known_completed_integrations']==counts.get('PHYSICAL_CALL_COMPLETED_NOT_TEST_ACCEPTANCE',0) and receipt['unknown_outcomes']==counts.get('NO_TERMINAL',0),'Completed/unknown counts differ')
    return dict(status='PASS_WITH_DECLARED_HISTORICAL_DEVELOPMENT_GAPS',package=folder.relative_to(ROOT).as_posix(),
        archive_members=len(members),public_attempt_directories=len(classification['cases']),known_completed_integrations=receipt['known_completed_integrations'],
        completed_duration_s=classification['known_completed_duration_s'],unobserved_outcomes=receipt['unknown_outcomes'],
        validation_error_calls=counts.get('FAILED',0),cli_pre_simulation_overwrite_refusals=counts.get('REJECTED_EXISTING_OUTPUT',0),
        runtime_file_hashes_checked=sources,historical_input_or_tool_gap_cases=receipt['cases_with_historical_input_or_tool_gaps'],
        committed_delivery=delivery,new_project_calls=0,formal_capture=False,ticket_acceptance=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,required=True);parser.add_argument('--delivery-commit')
    args=parser.parse_args();folder=(ROOT/args.package).resolve();print(json.dumps(verify(folder,args.delivery_commit),ensure_ascii=False))
