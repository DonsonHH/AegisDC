"""Capture ticket19 finite engineering checks or verify committed saved evidence."""
import argparse
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from plot_risk_engineering import render

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='docs/mainline/19-risk-engineering-protocol.json'
PACKAGE='evidence/mainline/engineering/19-risk-scenarios'


def require(value,message):
    if not value:raise ValueError(message)


def read(path):return json.loads(path.read_bytes())
def digest(raw):return sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def blob(revision,name):return digest(git('cat-file','blob',revision+':'+name))


def write(path,value):
    raw=value if isinstance(value,bytes) else (json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+'\n').encode('utf-8')
    with path.open('xb') as stream:stream.write(raw)


def paths(protocol,revision):
    names=git('ls-tree','-rz','--name-only',revision,'src',PACKAGE+'/development').decode().strip('\0').split('\0')
    return dict(runtime_sources=sorted(n for n in names if n.startswith('src/') and n.endswith('.py')),
        authoring_verification_tools=protocol['tools'],
        frozen_inputs=sorted([PROTOCOL,*[protocol[k] for k in ('frame','belief_model','risk_catalog','expected_witness','window_witness','joint_witness')],
            *protocol['frozen_documents'],PACKAGE+'/.gitattributes',*[n for n in names if n.endswith('.log')]]))


def durable(directory):return {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}}


def capture(directory,protocol):
    require(not git('status','--porcelain'),'Capture checkout must be clean')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==ROOT/'src','Set explicit checkout PYTHONPATH')
    source=git('rev-parse','HEAD').decode().strip()
    pins={group:{name:blob(source,name) for name in names} for group,names in paths(protocol,source).items()}
    require(all(digest((ROOT/name).read_bytes())==h for values in pins.values() for name,h in values.items()),'Execution source differs from committed bytes')
    directory.mkdir()
    write(directory/'attempt.json',dict(schema='aegisdc-risk-engineering-attempt-v1',classification='ENGINEERING_ONLY',
        execution_commit=source,output=directory.relative_to(ROOT).as_posix(),executable=sys.executable,
        executable_sha256=digest(Path(sys.executable).read_bytes()),python=sys.version,pythonpath=os.environ['PYTHONPATH'],
        argv=sys.argv,new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0))
    receipt=dict(schema='aegisdc-risk-engineering-receipt-v1',execution_commit=source,**pins,
        global_regression_gate='PENDING_ROOT_INTEGRATED_FULL_WITH_TORCH',field_calibration='PENDING',
        new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0)
    try:
        from risk_engineering_checks import exercise
        result,frame=exercise(ROOT,protocol)
        write(directory/'check-results.json',result)
        args=['-B','-X','utf8','-m','aegis_dc.risk_scenarios','--frame',protocol['frame'],'--belief-model',protocol['belief_model'],'--catalog',protocol['risk_catalog']]
        cli=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True)
        write(directory/'cli-stdout.raw',cli.stdout);write(directory/'cli-stderr.raw',cli.stderr)
        receipt.update(cli_argv=args,cli_exit_code=cli.returncode)
        require(cli.returncode==0 and not cli.stderr,'Risk CLI failed')
        cli_result=json.loads(cli.stdout)
        require(cli_result['full_horizon_service']==result['results'][-1]['full_horizon_service'],'CLI and finite engineering result differ')
        for name,raw in render(directory).items():write(directory/name,raw)
        require(durable(directory)==set(protocol['durable_outputs']),'Capture durable set differs from protocol')
        receipt['status']='PASS'
    except Exception as error:
        receipt.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:
        receipt['source_head_and_bytes_unchanged']=(git('rev-parse','HEAD').decode().strip()==source and
            all(digest((ROOT/name).read_bytes())==h for values in pins.values() for name,h in values.items()))
        if not receipt['source_head_and_bytes_unchanged']:receipt['status']='FAIL'
        receipt['artifacts']={name:digest((directory/name).read_bytes()) for name in sorted(durable(directory))}
        write(directory/protocol['terminal_receipt'],receipt)
    require(receipt['source_head_and_bytes_unchanged'],'Source or HEAD changed during capture')
    return dict(status=receipt['status'],execution_commit=source,artifacts=len(receipt['artifacts']),
        frames=len(result['results']),windows=len(result['window_checks']),maximum_absolute_error=result['maximum_absolute_error'])


def verify(directory,protocol,delivery):
    require(git('rev-parse','HEAD').decode().strip()==delivery,'Checkout requested delivery')
    receipt=read(directory/protocol['terminal_receipt']);source=receipt['execution_commit']
    require(receipt['status']=='PASS' and receipt['source_head_and_bytes_unchanged'] and receipt['cli_exit_code']==0,'Original capture did not pass')
    require(receipt['global_regression_gate']=='PENDING_ROOT_INTEGRATED_FULL_WITH_TORCH','Original full-regression gate changed')
    relative=directory.relative_to(ROOT).as_posix()
    require(durable(directory)==set(protocol['durable_outputs'])|{protocol['terminal_receipt']},'Durable delivery differs')
    require(set(receipt['artifacts'])==set(protocol['durable_outputs']),'Declared artifact hash set differs')
    for name in durable(directory):
        raw=(directory/name).read_bytes();require(digest(raw)==blob(delivery,relative+'/'+name),'Delivery blob differs: '+name)
        if name in receipt['artifacts']:require(digest(raw)==receipt['artifacts'][name],'Original bytes differ')
    for group,names in paths(protocol,source).items():
        require(set(names)==set(receipt[group]),'Pinned role set differs')
        for name,h in receipt[group].items():require(h==blob(source,name)==blob(delivery,name)==digest((ROOT/name).read_bytes()),'Pinned source differs: '+name)
    data=read(directory/'check-results.json');expected=read(ROOT/protocol['expected_witness'])
    mapping=dict(offered='offered_service_unit_s',delivered='delivered_service_unit_s',unserved='unserved_service_unit_s',deficit_time_s='service_deficit_time_s')
    require([r['as_of_s'] for r in data['results']]==protocol['as_of_s'],'Decision instants differ')
    last=data['results'][-1]
    for a,b in mapping.items():require(abs(last['full_horizon_service'][b]['value']-float(Fraction(expected['expected'][a])))<=protocol['absolute_numeric_tolerance'],'Independent expected account differs')
    joint=read(ROOT/protocol['joint_witness'])
    require(abs(data['joint_witness_result']['portfolio']['consequences']['service_deficit_time_s']['value']-float(Fraction(joint['expected_joint_union_deficit_time_s'])))<=protocol['absolute_numeric_tolerance'],'Shared joint outcome was counted more than once')
    for result in data['results']:
        require(result['physical_actions']==[] and not result['execution_permission'] and len(result['domain_ids'])==8,'Saved public scope differs')
        require(len(result['questions'])==8 and len(result['portfolio']['unmodeled_question_ids'])==6,'Saved complete-domain question set differs')
        for q in result['questions']:
            require(q['option_assessments'] and q['impact_description'] and q['conditional_consequence'],'Saved question incomplete')
            require(all(not x['execution_permission'] for x in q['option_assessments']),'Saved option execution permission changed')
            if q['quantification']=='UNMODELED':require(q['probability']['value'] is None and q['consequences']['service_deficit_time_s']['value'] is None,'Unknown risk became zero')
    window=read(ROOT/protocol['window_witness']);require(len(data['window_checks'])==sum(len(c['windows']) for c in window['cases'].values()),'Window cases missing')
    for row in data['window_checks']:
        case=window['cases'][row['case']];require(row['source_sha256']==digest((ROOT/row['source']).read_bytes())==case['run_sha256'],'Original08 case differs')
        for a,b in mapping.items():require(abs(row['actual'][b]['value']-float(Fraction(row['expected'][a])))<=protocol['absolute_numeric_tolerance'],'Saved window account differs')
    for name,raw in render(directory).items():require((directory/name).read_bytes()==raw,'Saved SVG differs')
    require((directory/'cli-stderr.raw').read_bytes()==b'','CLI stderr changed')
    cli=read(directory/'cli-stdout.raw');require(cli['full_horizon_service']==last['full_horizon_service'],'Saved CLI accounts differ')
    return dict(schema='aegisdc-risk-fresh-delivery-proof-v1',status='PASS',execution_commit=source,delivery_commit=delivery,
        durable_artifacts=len(receipt['artifacts']),terminal_receipts=1,pinned_paths={k:len(v) for k,v in receipt.items() if k in paths(protocol,source)},
        frames=len(data['results']),service_windows=len(data['window_checks']),svg_figures=2,
        source_head_and_bytes_unchanged=True,inference_rerun=False,full_regression_rerun=False,
        global_regression_gate='PENDING_ROOT_INTEGRATED_FULL_WITH_TORCH',field_calibration='PENDING',
        new_physical_runs=0,registered_research_trials=0,llm_calls=0,training_calls=0,runtime_caches_required=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['capture','verify'])
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--delivery')
    args=parser.parse_args();protocol=read(ROOT/PROTOCOL);directory=(ROOT/args.capture).resolve()
    require(directory.parent==ROOT/PACKAGE,'Use dedicated ticket19 capture directory')
    result=capture(directory,protocol) if args.mode=='capture' else verify(directory,protocol,args.delivery)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()
