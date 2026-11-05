"""Source-pinned public closure for ticket19 outward numeric bounds."""
import argparse
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/19-bound-correction-protocol.json'
PACKAGE='evidence/mainline/engineering/19-risk-scenarios'

def require(condition,message):
    if not condition:raise ValueError(message)

def read(path):return json.loads(path.read_bytes())
def digest(raw):return sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def blob(revision,name):return digest(git('cat-file','blob',revision+':'+name))

def write(path,value):
    with path.open('xb') as stream:
        stream.write((json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+'\n').encode('utf-8'))

def paths(protocol,source):
    runtime=git('ls-tree','-rz','--name-only',source,'src').decode().strip('\0').split('\0')
    return dict(runtime_sources=sorted(name for name in runtime if name.endswith('.py')),
        authoring_tools=[protocol['authoring_tool'],'scripts/risk_engineering_checks.py'],
        frozen_inputs=[PROTOCOL,protocol['frame'],protocol['belief_model'],protocol['risk_catalog'],
            protocol['original_check_results'],protocol['documentation'],protocol['defect_reference'],
            *protocol['development_logs']])

def check_cases(protocol):
    from aegis_dc.risk_scenarios import assess_risks
    from risk_engineering_checks import public_frames
    frame,belief,original=[read(ROOT/protocol[key]) for key in ('frame','belief_model','risk_catalog')]
    cases=[]
    def evaluate(identifier,model,expected,reason=None):
        try:
            result=assess_risks(frame,belief,model)
        except ValueError as error:
            require(expected=='REFUSED' and (reason is None or reason in str(error)),
                'Unexpected public rejection for '+identifier+': '+str(error))
            cases.append(dict(id=identifier,status='REFUSED_AS_REQUIRED',reason=str(error)))
        else:
            require(expected=='ACCEPTED','Public input unexpectedly accepted: '+identifier)
            require(result['physical_actions']==[] and not result['execution_permission'],'Correction executed a physical action')
            cases.append(dict(id=identifier,status='ACCEPTED_AS_REQUIRED',
                full_horizon_service=result['full_horizon_service'],
                first_question_bounds=result['questions'][0]['consequence_bounds']))
    model=deepcopy(original)
    model['demand']=[dict(start_s=0,end_s=1,rate=.1),dict(start_s=1,end_s=2,rate=.2)]
    for question in model['questions']:
        question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,.30000000000000004]
    exact=Fraction.from_float(.1)+Fraction.from_float(.2)
    require(Fraction.from_float(.3)<exact<Fraction.from_float(.30000000000000004),'Independent literal work witness differs')
    evaluate('nonrepresentable-work-outward',model,'ACCEPTED')
    for identifier,upper in [('work-nearest-below-rejected',.3),('work-above-minimal-rejected',.3000000000000001)]:
        changed=deepcopy(model);changed['questions'][0]['consequence_bounds']['unserved_service_unit_s']['interval']=[0,upper]
        evaluate(identifier,changed,'REFUSED','minimal outward')
    model=deepcopy(original);model['demand']=[dict(start_s=0,end_s=2,rate=1)]
    model['questions']=[model['questions'][0]]
    model['questions'][0]['window_s']=[.1,.4]
    for key in ('service_deficit_time_s','unserved_service_unit_s'):
        model['questions'][0]['consequence_bounds'][key]['interval']=[0,.30000000000000004]
    evaluate('nonrepresentable-duration-outward',model,'ACCEPTED')
    model['questions'][0]['consequence_bounds']['service_deficit_time_s']['interval']=[0,.3000000000000001]
    evaluate('duration-above-minimal-rejected',model,'REFUSED','minimal outward')
    model=deepcopy(original);model['demand']=[dict(start_s=0,end_s=2,rate=5e307)]
    for question in model['questions']:
        question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,1e308]
    evaluate('large-finite-work',model,'ACCEPTED')
    model['demand'][0]['rate']=1e308
    for question in model['questions']:
        question['consequence_bounds']['unserved_service_unit_s']['interval']=[0,sys.float_info.max]
    evaluate('work-output-overflow-rejected',model,'REFUSED','finite binary64 output range')
    require([row['id'] for row in cases]==protocol['case_ids'],'Correction case order differs from frozen protocol')
    saved=read(ROOT/protocol['original_check_results'])['results']
    current=[assess_risks(public,belief,original) for public in public_frames(frame,protocol['original_as_of_s'])]
    require(current==saved,'Corrected runtime changes the original declared finite fixture outputs')
    return dict(schema='aegisdc-ticket19-bound-correction-results-v1',status='PASS',cases=cases,
        exact_nonrepresentable_work=str(exact),original_frame_results_equal=True,original_frames_checked=len(current),
        closure_inference_calls=len(cases)+len(current),original_capture_rerun=False,
        original_capture_modified=False,new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0)

def capture(directory,protocol):
    require(not git('status','--porcelain'),'Correction execution checkout must be clean')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set explicit checkout PYTHONPATH')
    source=git('rev-parse','HEAD').decode().strip()
    pins={group:{name:blob(source,name) for name in names} for group,names in paths(protocol,source).items()}
    require(all(digest((ROOT/name).read_bytes())==h for values in pins.values() for name,h in values.items()),'Correction source differs from Git')
    directory.mkdir()
    write(directory/'attempt.json',dict(schema='aegisdc-ticket19-bound-correction-attempt-v1',classification=protocol['classification'],
        execution_commit=source,executable=sys.executable,executable_sha256=digest(Path(sys.executable).read_bytes()),
        python=sys.version,pythonpath=os.environ['PYTHONPATH'],argv=sys.argv,
        original_execution=protocol['original_execution'],original_data_delivery=protocol['original_data_delivery']))
    receipt=dict(schema='aegisdc-ticket19-bound-correction-receipt-v1',execution_commit=source,**pins,
        original_execution=protocol['original_execution'],original_data_delivery=protocol['original_data_delivery'],
        full_regression_gate='PENDING_ROOT_CORRECTED_RUNTIME_FULL',new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0)
    try:
        result=check_cases(protocol);write(directory/'correction-results.json',result);receipt['status']='PASS'
    except Exception as error:
        receipt.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=(git('rev-parse','HEAD').decode().strip()==source and
            all(digest((ROOT/name).read_bytes())==h for values in pins.values() for name,h in values.items()))
        if not receipt['source_head_and_bytes_unchanged']:receipt['status']='FAIL'
        receipt['artifacts']={p.name:digest(p.read_bytes()) for p in directory.iterdir() if p.is_file()}
        write(directory/protocol['terminal_receipt'],receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Correction source changed during execution')
    require(set(receipt['artifacts'])==set(protocol['durable_outputs']),'Correction durable set differs')
    return dict(status='PASS',execution_commit=source,cases=len(result['cases']),
        original_frames_checked=result['original_frames_checked'],original_results_equal=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();directory=(ROOT/args.output).resolve()
    require(directory.parent==ROOT/PACKAGE and not directory.exists(),'Use a new dedicated correction output')
    print(json.dumps(capture(directory,read(ROOT/PROTOCOL)),ensure_ascii=False,allow_nan=False))
