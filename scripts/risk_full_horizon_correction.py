"""Separate revision2 public closure for complete-horizon numeric output limits."""
import argparse
from copy import deepcopy
from pathlib import Path
import sys
import tempfile

from risk_bound_correction import ROOT, PACKAGE, read, digest, git, blob, write, require, check_cases
import json
import os
import subprocess

PROTOCOL='docs/mainline/19-bound-correction-protocol-v2.json'

def paths(protocol,source):
    runtime=git('ls-tree','-rz','--name-only',source,'src').decode().strip('\0').split('\0')
    return dict(runtime_sources=sorted(name for name in runtime if name.endswith('.py')),
        authoring_tools=[protocol['authoring_tool'],protocol['previous_authoring_tool'],'scripts/risk_engineering_checks.py'],
        frozen_inputs=[PROTOCOL,protocol['previous_protocol'],protocol['frame'],protocol['belief_model'],protocol['risk_catalog'],
            protocol['original_check_results'],protocol['documentation'],protocol['defect_reference'],*protocol['development_logs']])

def exercise(protocol):
    from aegis_dc.risk_scenarios import assess_risks
    previous=deepcopy(protocol);previous['case_ids']=protocol['previous_case_ids']
    prior_result=check_cases(previous)
    frame,belief,model=[read(ROOT/protocol[key]) for key in ('frame','belief_model','risk_catalog')]
    model['demand']=[dict(start_s=0,end_s=2,rate=1e308)]
    for question in model['questions']:
        question['window_s']=[0,1]
        question['consequence_bounds']['service_deficit_time_s']['interval']=[0,1]
        question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,1e308]
    cases=[]
    for identifier,questions in [('full-horizon-overflow-short-question',model['questions']),
                                 ('full-horizon-overflow-no-questions',[])]:
        changed=deepcopy(model);changed['questions']=questions
        try:
            assess_risks(frame,belief,changed)
        except ValueError as error:
            require('finite binary64 output range' in str(error),'Unexpected full-horizon input refusal')
            cases.append(dict(id=identifier,status='REFUSED_AS_REQUIRED',error_type=type(error).__name__,reason=str(error)))
        else:
            raise ValueError('Complete-horizon overflow was accepted')
    finite=deepcopy(model);finite['questions']=[];finite['demand'][0]['rate']=5e307
    result=assess_risks(frame,belief,finite)
    require(result['full_horizon_service']['offered_service_unit_s']['value']==1e308,'Large finite common demand was not retained')
    require(result['physical_actions']==[] and not result['execution_permission'],'Numeric closure caused a physical action')
    cases.append(dict(id='large-finite-horizon-no-questions',status='ACCEPTED_AS_REQUIRED',
        full_horizon_service=result['full_horizon_service']))
    model['questions']=[]
    with tempfile.TemporaryDirectory() as temporary:
        files=[Path(temporary)/name for name in ('frame.json','belief.json','catalog.json')]
        for path,value in zip(files,(frame,belief,model)):
            path.write_text(json.dumps(value),encoding='utf-8')
        args=['-B','-X','utf8','-m','aegis_dc.risk_scenarios','--frame',str(files[0]),
              '--belief-model',str(files[1]),'--catalog',str(files[2])]
        cli=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True)
    require(cli.returncode==2 and cli.stdout==b'' and b'Traceback' not in cli.stderr
            and b'finite binary64 output range' in cli.stderr,'CLI did not decline complete-horizon overflow cleanly')
    cases.append(dict(id='cli-overflow-no-traceback',status='REFUSED_AS_REQUIRED',exit_code=cli.returncode,
        stdout_bytes=len(cli.stdout),stderr_sha256=digest(cli.stderr)))
    require([row['id'] for row in cases]==protocol['case_ids'],'Revision2 case order differs')
    return dict(schema='aegisdc-ticket19-full-horizon-correction-results-v2',status='PASS',cases=cases,
        previous_numeric_closure=prior_result,api_cases=3,cli_cases=1,previous_cases=7,original_frames_equal=4,
        closure_calls=15,original_captures_rerun=False,new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0),cli

def capture(directory,protocol):
    require(not git('status','--porcelain'),'Revision2 execution checkout must be clean')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set explicit checkout PYTHONPATH')
    source=git('rev-parse','HEAD').decode().strip()
    pins={group:{name:blob(source,name) for name in names} for group,names in paths(protocol,source).items()}
    require(all(digest((ROOT/name).read_bytes())==h for values in pins.values() for name,h in values.items()),'Revision2 source differs from Git')
    directory.mkdir()
    write(directory/'attempt.json',dict(schema='aegisdc-ticket19-bound-correction-attempt-v2',classification=protocol['classification'],
        execution_commit=source,executable=sys.executable,executable_sha256=digest(Path(sys.executable).read_bytes()),
        python=sys.version,pythonpath=os.environ['PYTHONPATH'],argv=sys.argv,original_execution=protocol['original_execution'],
        previous_execution=protocol['previous_execution'],first_root_regression_source=protocol['first_root_regression_source']))
    receipt=dict(schema='aegisdc-ticket19-bound-correction-receipt-v2',execution_commit=source,**pins,
        original_execution=protocol['original_execution'],previous_execution=protocol['previous_execution'],
        first_root_regression_source=protocol['first_root_regression_source'],
        full_regression_gate='PENDING_NEW_ROOT_CORRECTED_RUNTIME_FULL',new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0)
    try:
        result,cli=exercise(protocol)
        write(directory/'correction-results.json',result)
        for name,raw in [('cli-stdout.raw',cli.stdout),('cli-stderr.raw',cli.stderr)]:
            with (directory/name).open('xb') as stream:stream.write(raw)
        receipt['status']='PASS'
    except Exception as error:
        receipt.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=(git('rev-parse','HEAD').decode().strip()==source and
            all(digest((ROOT/name).read_bytes())==h for values in pins.values() for name,h in values.items()))
        if not receipt['source_head_and_bytes_unchanged']:receipt['status']='FAIL'
        receipt['artifacts']={p.name:digest(p.read_bytes()) for p in directory.iterdir() if p.is_file()}
        write(directory/protocol['terminal_receipt'],receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Revision2 source changed during execution')
    require(set(receipt['artifacts'])==set(protocol['durable_outputs']),'Revision2 durable set differs')
    return dict(status='PASS',execution_commit=source,new_cases=4,previous_cases=7,original_frames_equal=4,cli_exit_code=2)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();directory=(ROOT/args.output).resolve()
    require(directory.parent==ROOT/PACKAGE and not directory.exists(),'Use a new dedicated revision2 output')
    print(json.dumps(capture(directory,read(ROOT/PROTOCOL)),ensure_ascii=False,allow_nan=False))
