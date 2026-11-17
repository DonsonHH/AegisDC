"""Thin fixed-core entry, currently executable only for frozen public engineering.

Confirmation activation requires a separately reviewed custody/authorization
adapter. JSON role declarations cannot open that gate. No model is imported
until preflight has admitted the exact public input file.
"""
import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import traceback

import run_london_public_development as report

CORE_REV='1c0b0c47a5742321a3524a5b16843775cc224e3e'
INPUT_SHA='a70bbef0e1a789c65e28f6d6f3bec822d361c7a309227d528b812d55398e774b'
CORE_HASHES={
    'src/aegis_dc/__init__.py':'32c7ae44be5f74a3d9d1c44cbe6df95e58637bfe74564ef41c463e1269cd013d',
    'src/aegis_dc/london_e14.py':'1d9f8421882faf9e021badf3138505332f9a0513bea90539e6cac04bfc6d2a42',
    'src/aegis_dc/london_treatments.py':'4bce4df739e8fbb9ae5b64f1ddb5434670a9334b44941777d7d9db25b466ece2',
    'src/aegis_dc/london_treatment_score.py':'707306ffa163a90b8a6a607197eec8364da3208f6fc71cf8a3d2a0e72f85904f',
}
FIELDS=set('H tF tR P E0 vA vB cA cB capA capB capG family epoch ready connected permit exec_fault tauG tauB read_work publish ttl approval_work prep commit_work exit_work verify_work budget calendar window grant_expiry revoke work_mode approval commit verification exit_result guard compatible permissions read_modes signal_missing demand'.split())
NUMBERS=set('H P E0 capA capB capG tauG tauB read_work publish ttl approval_work prep commit_work exit_work verify_work budget grant_expiry'.split())
CLOCKS=set('H read_work publish ttl approval_work prep commit_work exit_work verify_work'.split())
BOOLS={'ready','connected','permit','exec_fault'}
BITS={'vA','vB','cA','cB'}
ENUMS=dict(family=['LEGACY_LINE','REVISED_LOCAL'],work_mode=['ONLINE','LOAD_ISOLATED'],approval=['APPROVE','DENY'],commit=['SUCCESS','FAIL'],verification=['PASS','FAIL','INCONCLUSIVE','CHANNEL_FAILED'],exit_result=['SUCCESS','FAIL'],guard=['ALLOW','BLOCK'],compatible=['ALLOW','DENY','UNKNOWN'])
BUDGET=dict(conditions=8,arms=24,policy_calls=480,cpus=1,memory_MiB=1024,wall_seconds=120)


class EntryError(ValueError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


def require(condition,code):
    if not condition:raise EntryError(code)


def strict_loads(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise EntryError('BAD_JSON')
            result[key]=value
        return result
    def forbidden(value):raise EntryError('BAD_JSON')
    try:return json.loads(raw,object_pairs_hook=pairs,parse_float=forbidden,parse_constant=forbidden)
    except (ValueError,TypeError,UnicodeError) as error:raise EntryError('BAD_JSON') from error


def number(value):
    require(type(value) in (int,str),'BAD_CONFIG')
    try:
        rational=Fraction(value)
    except (ValueError,ZeroDivisionError) as error:raise EntryError('BAD_CONFIG') from error
    return ['q',rational.numerator,rational.denominator]


def canonical_config(common):
    """Schema-aware exact identity; does not mutate the model's input."""
    require(type(common) is dict and set(common)==FIELDS,'BAD_CONFIG')
    result={}
    for name in NUMBERS:
        if name in CLOCKS:require(type(common[name]) is int,'BAD_CONFIG')
        result[name]=number(common[name])
    require(common['H']==20,'BAD_CONFIG')
    for name in ('tF','tR'):
        result[name]=['null'] if common[name] is None else number(common[name])
    for name in BOOLS:
        require(type(common[name]) is bool,'BAD_CONFIG');result[name]=['bool',common[name]]
    for name in BITS|{'epoch'}:
        require(type(common[name]) is int and common[name] in ((0,) if name=='epoch' else (0,1)),'BAD_CONFIG')
        result[name]=['int',common[name]]
    for name,values in ENUMS.items():
        require(type(common[name]) is str and common[name] in values,'BAD_CONFIG');result[name]=['str',common[name]]
    for name,keys,values in [('permissions',{'read','propose','verify','direct'},{'ALLOW','DENY','UNKNOWN'}),('read_modes',{'READ_POS','READ_VOLT','READ_CONFIG'},{'DEFINITE','INCONCLUSIVE','CHANNEL_FAILED'})]:
        value=common[name]
        require(type(value) is dict and set(value)==keys and all(type(v) is str and v in values for v in value.values()),'BAD_CONFIG')
        result[name]={k:['str',v] for k,v in value.items()}
    require(type(common['window']) is list and len(common['window'])==2 and all(type(x) is int for x in common['window']),'BAD_CONFIG')
    result['window']=[number(x) for x in common['window']]
    for name in ('calendar','demand'):
        require(type(common[name]) is list,'BAD_CONFIG');result[name]=[]
        for row in common[name]:
            require(type(row) is list and len(row)==2,'BAD_CONFIG')
            if name=='calendar':require(all(type(x) is int for x in row),'BAD_CONFIG')
            else:require(type(row[1]) is int and row[1] in (0,1),'BAD_CONFIG')
            result[name].append([number(x) for x in row])
    revoke=common['revoke']
    require(revoke is None or type(revoke) is list and len(revoke)==2 and revoke[1] in ('READ_ROLE','FIX_GRANT'),'BAD_CONFIG')
    result['revoke']=['null'] if revoke is None else [number(revoke[0]),['str',revoke[1]]]
    missing=common['signal_missing']
    require(type(missing) is list and all(type(x) is str and x in ('zVA','zVB','zCA','zCB','zSA','zSB') for x in missing) and len(missing)==len(set(missing)),'BAD_CONFIG')
    result['signal_missing']=[['str',x] for x in sorted(missing)]
    return json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def config_hash(common):
    return hashlib.sha256(canonical_config(common).encode()).hexdigest()


def validate_package(data):
    require(type(data) is dict and set(data)=={'schema','purpose','conditions'},'BAD_PACKAGE')
    require(data['purpose']=='PUBLIC_ENGINEERING','PURPOSE_REJECTED')
    require(data['schema']=='aegisdc-confirmation-entry-engineering-v1' and type(data['conditions']) is list and 1<=len(data['conditions'])<=8,'BAD_PACKAGE')
    ids=set();seen=set()
    for row in data['conditions']:
        require(type(row) is dict and set(row)=={'condition_id','common'},'BAD_PACKAGE')
        name=row['condition_id']
        require(type(name) is str and re.fullmatch(r'X[0-9]{2}',name) and name not in ids,'BAD_PACKAGE')
        ids.add(name);digest=config_hash(row['common'])
        require(digest not in seen,'DUPLICATE_INPUT');seen.add(digest)
    return data


def contained(root,relative):
    require(type(relative) is str,'SOURCE_PATH')
    path=(root/relative).resolve()
    require(root.resolve() in path.parents,'SOURCE_PATH')
    return path


def preflight(root,manifest_path,manifest_sha,output):
    require(report.file_sha(manifest_path)==manifest_sha,'MANIFEST_HASH')
    manifest=strict_loads(manifest_path.read_bytes())
    require(manifest.get('purpose')=='PUBLIC_ENGINEERING','PURPOSE_REJECTED')
    require(manifest.get('schema')=='aegisdc-confirmation-entry-launch-v1','BAD_MANIFEST')
    require(Path(manifest['output_directory']).resolve()==output.resolve(),'OUTPUT_PATH')
    require(report.file_sha(Path(sys.executable).resolve())==manifest['python_sha256'],'PYTHON_HASH')
    require(manifest['core_revision']==CORE_REV and manifest['budget']==BUDGET and manifest['arm_order']==['I','D','P'],'BAD_MANIFEST')
    require(manifest['condition_order']==[f'X{x:02}' for x in range(1,9)],'BAD_MANIFEST')
    require(os.environ.get('SLURM_CPUS_PER_TASK')=='1' and os.environ.get('SLURM_MEM_PER_NODE')=='1024','ALLOCATION')
    files=manifest['files'];input_path=manifest['input']['path']
    required=set(CORE_HASHES)|{'scripts/london_confirmation_entry.py','scripts/run_london_public_development.py',input_path}
    require(required.issubset(files),'BAD_MANIFEST')
    for name,meta in files.items():
        if name==input_path:continue
        path=contained(root,name)
        require(path.is_file() and report.file_sha(path)==meta['sha256'],'SOURCE_HASH')
        if name in CORE_HASHES:require(meta['sha256']==CORE_HASHES[name],'CORE_HASH')
    path=contained(root,input_path)
    digest=report.file_sha(path)
    require(digest==manifest['input']['sha256']==files[input_path]['sha256'],'INPUT_HASH')
    require(digest==INPUT_SHA,'INPUT_NOT_FROZEN')
    data=validate_package(strict_loads(path.read_bytes()))
    require([x['condition_id'] for x in data['conditions']]==manifest['condition_order'],'BAD_PACKAGE')
    return data


def create_output(path):
    try:path.mkdir(parents=True,exist_ok=False)
    except FileExistsError as error:raise EntryError('OUTPUT_EXISTS') from error


def execute_batch(data,run_condition,output,manifest):
    """Common archive/stop seam; injected callbacks are private checker fixtures."""
    validate_package(data)
    rows=[report.not_executed(c['condition_id'],'Not yet started') for c in data['conditions']]
    terminal=dict(status='RUNNING',classification='PUBLIC_ENGINEERING_NOT_RESEARCH',core_revision=CORE_REV,
        entry_revision=manifest['entry_revision'],rows=rows,records=[],confirmation_runs=0,
        counts=dict(runner_calls=0,constructor_attempts=0,plant_entry_calls=0,policy_calls=0,scorer_calls=0))
    report.save(output/'started.json',dict(conditions=data,manifest=manifest))
    halted=False
    for index,condition in enumerate(data['conditions']):
        name=condition['condition_id']
        if halted:
            rows[index]=report.not_executed(name,'Stopped after preceding error; no model call');continue
        report.save(output/(name+'-started.json'),dict(index=index,condition=condition))
        record=dict(condition=deepcopy(condition),canonical_config_sha256=config_hash(condition['common']))
        terminal['counts']['runner_calls']+=1;actual=None;fatal=[]
        try:
            actual=run_condition(deepcopy(condition['common']),order=['I','D','P'])
        except BaseException as error:
            record['exception']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
        raw_path=output/(name+'-raw.json')
        report.save(raw_path,dict(condition=condition,actual=actual,exception=record.get('exception')))
        record['raw_file']=raw_path.name;record['raw_sha256']=report.file_sha(raw_path)
        try:
            if actual is None:raise RuntimeError('CORE_RETURN_MISSING')
            for key in ('constructor_attempts','plant_entry_calls','policy_calls','scorer_calls'):
                terminal['counts'][key]+=actual.get('counts',{}).get(key,0)
            fatal=report.inspect_result(actual,condition['common'],name)
            if terminal['counts']['policy_calls']>BUDGET['policy_calls']:fatal.append('POLICY_BUDGET')
            summary=report.summarize(name,actual,fatal)
        except BaseException as error:
            fatal.append('ENTRY_OR_CORE_EXCEPTION')
            record['exception']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
            summary=report.not_executed(name,'Started; error retained')
            summary.update(status='ERROR',comparison_status='STOPPED_ON_ERROR',fatal_findings=fatal)
        record['summary']=summary;record['fatal_findings']=fatal
        report.save(output/(name+'.json'),record);rows[index]=summary
        terminal['records'].append(dict(condition_id=name,file=name+'.json',sha256=report.file_sha(output/(name+'.json'))))
        halted=bool(fatal)
        if halted:terminal['halted_at']=name
        for following in range(index+1,len(rows)):
            rows[following]=report.not_executed(data['conditions'][following]['condition_id'],'Stopped after error' if halted else 'Not yet started')
        report.save(output/f'progress-{index+1:02}.json',terminal)
    terminal['status']='STOPPED_ON_ERROR' if halted else 'COMPLETED_PUBLIC_ENGINEERING'
    report.save(output/'terminal.json',terminal)
    return terminal


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--manifest-sha',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(bool(os.environ.get('SLURM_JOB_ID')) and socket.gethostname().split('.')[0]!='mu01','ALLOCATION')
    root=Path(__file__).resolve().parents[1];create_output(args.output)
    try:
        data=preflight(root,args.manifest,args.manifest_sha,args.output)
        manifest=strict_loads(args.manifest.read_bytes())
        sys.path.insert(0,str(root/'src'));core=importlib.import_module('aegis_dc.london_treatments')
        result=execute_batch(data,core.run_condition,args.output,manifest)
        return 0 if result['status']=='COMPLETED_PUBLIC_ENGINEERING' else 1
    except BaseException as error:
        report.save(args.output/'entry-error.json',dict(status='PRE_EXECUTION_OR_ARCHIVE_ERROR',error=type(error).__name__,message=str(error),traceback=traceback.format_exc(),confirmation_runs=0))
        return 1


if __name__=='__main__':raise SystemExit(main())
