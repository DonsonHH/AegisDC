"""Preserve exact D-stage originals and explicitly classify development gaps."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def require(ok,message):
    if not ok:raise ValueError(message)


def read(path):return json.loads(path.read_bytes())
def digest(raw):return sha256(raw).hexdigest()
def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()


def durable(folder):
    return sorted(p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'})


def early_profile_only_source(raw):
    """Exact inverse of the recorded D inheritance correction, hash checked below."""
    source=raw.decode('utf-8')
    replacements=[
        ("_require(type(projection) is dict and type(self.inspection_program) is dict and 'profile' in self.inspection_program,\n                'Declare v4 public projection and actual inspection profiles')",
         "_require(type(projection) is dict and self.inspection_program is not None,'Declare v4 public projection and actual inspection profiles')"),
        ("            _require(background is None or type(background) is dict and 'profile' in background,'Declare the actual public background sensor profile')\n",''),
        ("if program['policy_program']['schema'] in {'aegisdc-dispatch-policy-program-v3','aegisdc-dispatch-policy-program-v4'}:",
         "if program['policy_program']['schema']=='aegisdc-dispatch-policy-program-v3':"),
        ("{'aegisdc-dispatch-policy-program-v2','aegisdc-dispatch-policy-program-v3','aegisdc-dispatch-policy-program-v4'}:",
         "{'aegisdc-dispatch-policy-program-v2','aegisdc-dispatch-policy-program-v3'}:"),
        ("if program['policy_program']['policy']=='one_observation_lookahead' and program['policy_program']['schema']!='aegisdc-dispatch-policy-program-v4':",
         "if program['policy_program']['policy']=='one_observation_lookahead':")]
    for before,after in replacements:
        require(source.count(before)==1,'Source reconstruction recipe no longer has its exact unique input')
        source=source.replace(before,after)
    return source.encode(),replacements


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--interruption-observation',type=Path,required=True)
    args=parser.parse_args();base=(ROOT/args.source).resolve();output=(ROOT/args.output).resolve()
    require(base==ROOT/'.work/26-online-development','Use the declared development source directory')
    require(not output.exists() and output.parent==ROOT/'evidence/mainline/engineering/26-candidate','Use a unique development package')
    require(args.interruption_observation.is_file(),'Preserve the independent interruption observation')
    output.mkdir();declaration=dict(schema='aegisdc-development-durable-set-v1',
        artifacts=['originals.zip','archive-members.json','classification.json','source-reconstructions.json','declaration.json'],
        terminal_receipt='receipt.json',runtime_caches='Excluded __pycache__, pyc and pyo; never delivered evidence')
    (output/'declaration.json').write_bytes(encoded(declaration))
    members={};classification=[];recoveries={};reconstruction_recipes=[];counts=Counter();complete_duration=0
    for path in durable(base):members['original/'+path.relative_to(base).as_posix()]=path.read_bytes()
    members['observation/'+args.interruption_observation.name]=args.interruption_observation.read_bytes()
    recipe,recipe_steps=early_profile_only_source((ROOT/'src/aegis_dc/policy_execution.py').read_bytes())
    reconstruction_recipes.append(dict(path='src/aegis_dc/policy_execution.py',output_sha256=digest(recipe),
        basis='Exact inverse of separately recorded public-profile/inheritance patch, accepted only when original attempt hash matches',
        replacement_steps=[dict(before=before,after=after) for before,after in recipe_steps]))
    pool={}

    def recover_source(name,expected,attempt):
        key=(name,expected)
        if key in pool:return pool[key]
        candidates=[('CURRENT_BYTES_HASH_MATCH',(ROOT/name).read_bytes())]
        for revision in dict.fromkeys((attempt['source_commit'],'13e9725a','4dee4488')):
            result=subprocess.run(['git','cat-file','blob',revision+':'+name],cwd=ROOT,capture_output=True)
            if result.returncode==0:candidates.append(('GIT_BLOB_HASH_MATCH:'+revision,result.stdout))
        if name=='src/aegis_dc/policy_execution.py':candidates.append(('EXPLICIT_INVERSE_PATCH_HASH_MATCH',recipe))
        for basis,raw in candidates:
            if digest(raw)==expected:
                member='recovered-runtime/'+expected+'/'+name;members[member]=raw
                row=dict(member=member,sha256=expected,basis=basis);pool[key]=row;return row
        return None

    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        attempt=read(folder/'attempt.json');terminal=read(folder/'terminal.json') if (folder/'terminal.json').exists() else None
        status=terminal['status'] if terminal else 'NO_TERMINAL';counts[status]+=1
        row=dict(case=folder.name,original_terminal_status=status,recorded_head=attempt['source_commit'],
            status_not_rewritten=True,recorded_runtime_files=len(attempt['source_files']),source_recovery=[],provenance_gaps=[])
        for name,expected in attempt['source_files'].items():
            snapshot=folder/'runtime-source'/name
            if snapshot.exists():
                require(digest(snapshot.read_bytes())==expected,'Original runtime snapshot differs from its attempt hash')
                row['source_recovery'].append(dict(path=name,sha256=expected,basis='ORIGINAL_CAPTURED_RUNTIME_SNAPSHOT',member='original/'+snapshot.relative_to(base).as_posix()))
            else:
                recovered=recover_source(name,expected,attempt)
                if recovered is None:row['provenance_gaps'].append('RUNTIME_BYTES_UNRECOVERED:'+name)
                else:row['source_recovery'].append(dict(path=name,**recovered))
        row['runtime_bytes_hash_verified']=len(row['source_recovery'])==len(attempt['source_files'])
        if not (folder/'test-tools.json').exists():row['provenance_gaps'].append('HISTORICAL_DEVELOPMENT_TEST_AUTHORING_TOOLS_NOT_CAPTURED')
        else:
            for name,expected in read(folder/'test-tools.json').items():require(digest((folder/'test-tools'/name).read_bytes())==expected,'Original test tool snapshot differs')
        run_file=folder/'original/run.json'
        if run_file.exists():
            run=read(run_file);require(status=='PHYSICAL_CALL_COMPLETED_NOT_TEST_ACCEPTANCE','Run and original terminal disagree')
            require(run['code_identity']['git_commit']==attempt['source_commit'],'Run execution head differs from attempt')
            for name,expected in run['code_identity']['files'].items():require(attempt['source_files'][name]==expected,'Run source hash differs from recorded attempt')
            for name,identity in run['artifacts'].items():require(digest((folder/'original'/name).read_bytes())==identity['sha256'],'Original saved run member differs')
            complete_duration+=run['inputs']['duration_s']
            row.update(classification='COMPLETED_DEVELOPMENT_INTEGRATION_NOT_TEST_ASSERTION_PASS',duration_s=run['inputs']['duration_s'],saved_run_member='original/'+run_file.relative_to(base).as_posix())
            if not (folder/'model.json').exists() or not (folder/'dispatch-program.json').exists():
                for name,raw in (('model.json',(folder/'original/scenario.json').read_bytes()),('dispatch-program.json',encoded(run['inputs']['dispatch_program']))):
                    member='recovered-executed-inputs/'+folder.name+'/'+name;members[member]=raw
                row['input_provenance']='RECOVERED_FROM_ORIGINAL_SAVED_SCENARIO_AND_EXECUTED_DISPATCH_INPUTS_NOT_CLAIMED_PREFLIGHT_INPUT_BYTES'
            else:
                require(read(folder/'model.json')==read(folder/'original/scenario.json') and read(folder/'dispatch-program.json')==run['inputs']['dispatch_program'],'Precall input differs from executed input')
                row['input_provenance']='ORIGINAL_PRECALL_INPUT_JSON_CAPTURED'
        elif status=='FAILED':
            row.update(classification='PUBLIC_DEVELOPMENT_CALL_RAISED_ERROR_NO_COMPLETED_RUN',error_type=terminal.get('error_type'),error=terminal.get('error'),completed_integration=False)
            if not (folder/'model.json').exists() or not (folder/'dispatch-program.json').exists():
                row['provenance_gaps'].append('HISTORICAL_DEVELOPMENT_REFUSAL_INPUTS_NOT_CAPTURED_AND_NOT_RECONSTRUCTED')
        elif status=='REJECTED_EXISTING_OUTPUT':
            row.update(classification='CLI_REFUSED_OVERWRITE_BEFORE_SIMULATION',completed_integration=False,input_provenance='ORIGINAL_PRECALL_INPUT_JSON_CAPTURED')
        elif terminal is None:
            row.update(classification='TRANSPORT_INTERRUPTED_OUTCOME_UNOBSERVED',completed_integration='UNKNOWN_NOT_ASSUMED_FALSE',
                input_provenance='ORIGINAL_PRECALL_INPUT_JSON_CAPTURED',observation_member='observation/'+args.interruption_observation.name)
        else:raise ValueError('Unclassified original development terminal: '+status)
        classification.append(row)
    source_recovery=dict(schema='aegisdc-development-source-recovery-v1',recipes=reconstruction_recipes,
        pooled_original_hash_matched_files=[dict(path=path,**item) for (path,_),item in sorted(pool.items())],
        no_execution=True,no_manifest_rewriting=True,not_claimed_as_original_precall_snapshots=True)
    result=dict(schema='aegisdc-candidate-development-archive-classification-v1',public_call_attempt_directories=len(classification),
        original_terminal_counts=dict(counts),known_completed_development_integrations=counts['PHYSICAL_CALL_COMPLETED_NOT_TEST_ACCEPTANCE'],
        known_completed_duration_s=complete_duration,call_outcome_unknown=counts['NO_TERMINAL'],
        constructor_or_decision_refusals_without_completed_run=counts['FAILED'],cli_pre_simulation_overwrite_refusals=counts['REJECTED_EXISTING_OUTPUT'],
        no_extra_project_runs=True,registered_research_trials=0,formal_capture=False,
        notes=['Original statuses and bytes preserved; completed physics does not imply test assertions passed (logs34 and44 remain failures).',
            'Log44 oracle correction45 reads the same original; no physical retry for that correction.',
            'CLI46 has no process, terminal or saved output; entry into physics remains unknown.47 is a separately recorded new development attempt.',
            'Some pre-existing refusal input and test-authoring snapshots were not captured. Their gaps remain explicit, not fabricated.',
            'All development runtime source bytes are accepted only by exact original hashes; inverse-patch recovery is labeled separately.',
            'Zero modeled-impairment defer does not mean an actual healthy plant: actual service deficit stays4.5s.'],cases=classification)
    (output/'classification.json').write_bytes(encoded(result));(output/'source-reconstructions.json').write_bytes(encoded(source_recovery))
    with zipfile.ZipFile(output/'originals.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for name,raw in sorted(members.items()):archive.writestr(name,raw)
    (output/'archive-members.json').write_bytes(encoded({name:dict(sha256=digest(raw),bytes=len(raw)) for name,raw in sorted(members.items())}))
    require({p.name for p in output.iterdir()}==set(declaration['artifacts']),'Durable declared set differs before terminal receipt')
    receipt=dict(schema='aegisdc-candidate-development-package-receipt-v1',classification='SAVED_ORIGINAL_PRESERVATION_ONLY_NOT_ACCEPTANCE',
        authoring_tool=Path(__file__).relative_to(ROOT).as_posix(),authoring_tool_sha256=digest(Path(__file__).read_bytes()),
        artifacts={name:digest((output/name).read_bytes()) for name in declaration['artifacts']},archive_members=len(members),
        attempts=len(classification),known_completed_integrations=counts['PHYSICAL_CALL_COMPLETED_NOT_TEST_ACCEPTANCE'],unknown_outcomes=counts['NO_TERMINAL'],
        all_recorded_runtime_hashes_recovered=all(row['runtime_bytes_hash_verified'] for row in classification),
        cases_with_historical_input_or_tool_gaps=sum(bool(row['provenance_gaps']) for row in classification),new_project_calls=0)
    (output/'receipt.json').write_bytes(encoded(receipt))
    print(json.dumps({k:v for k,v in receipt.items() if k!='artifacts'},ensure_ascii=False))


if __name__=='__main__':main()
