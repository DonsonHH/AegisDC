"""Independent literal checker for the public confirmation-entry engineering pack.

Only green mode calls the frozen core. Verify mode reads saved records; red mode
checks the absent implementation. Expectations are read from the prior freeze.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import traceback

PACK='docs/mainline/review-gated/R4/confirmation-entry-v1/'
CORE=['src/aegis_dc/__init__.py','src/aegis_dc/london_e14.py','src/aegis_dc/london_treatments.py','src/aegis_dc/london_treatment_score.py']
CORE_REV='1c0b0c47a5742321a3524a5b16843775cc224e3e'
PY_SHA='5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2,allow_nan=False)
        handle.write('\n')


def at(value,path):
    for part in path.split('.'):
        value=value[int(part)] if isinstance(value,list) else value[part]
    return value


def same(left,right):
    return json.dumps(left,sort_keys=True,allow_nan=False)==json.dumps(right,sort_keys=True,allow_nan=False)


def compare(actual,expected):
    rows=[]
    for path,want in expected.items():
        try:
            got=at(actual,path)
            rows.append(dict(path=path,expected=want,actual=got,matches=same(got,want)))
        except (KeyError,IndexError,TypeError) as error:
            rows.append(dict(path=path,expected=want,error=str(error),matches=False))
    return rows


def counted(callback,ledger):
    """Account outside the archiver, even if it cannot return a terminal."""
    ledger.update(calls=0,returned=0,unreturned=0,unknown_count_calls=0,reported_counts_scope='KNOWN_REPORTED_SUBTOTAL_ONLY',reported_internal_counts={k:0 for k in ('constructor_attempts','plant_entry_calls','policy_calls','scorer_calls')})
    def call(common,order):
        ledger['calls']+=1;ledger['unreturned']+=1
        value=callback(common,order=order)
        ledger['returned']+=1;ledger['unreturned']-=1
        counts=value.get('counts') if isinstance(value,dict) else None
        if not isinstance(counts,dict) or any(type(counts.get(k)) is not int or counts[k]<0 for k in ledger['reported_internal_counts']):
            ledger['unknown_count_calls']+=1
        else:
            for key in ledger['reported_internal_counts']:ledger['reported_internal_counts'][key]+=counts[key]
        return value
    return call


def launch(root,output,identity):
    return dict(schema='aegisdc-confirmation-entry-launch-v1',purpose='PUBLIC_ENGINEERING',
        core_revision=CORE_REV,entry_revision=identity['source_commit'],
        input=dict(path=PACK+'inputs.json',sha256=sha(root/PACK/'inputs.json')),
        files=deepcopy(identity['files']),python_sha256=PY_SHA,output_directory=str(output.resolve()),
        condition_order=[f'X{x:02}' for x in range(1,9)],arm_order=['I','D','P'],
        budget=dict(conditions=8,arms=24,policy_calls=480,cpus=1,memory_MiB=1024,wall_seconds=120))


def interface_checks(entry,root,output,identity,fixtures,data):
    results=[]
    baseline=data['conditions'][0]['common']
    for unit in fixtures['units']:
        loc=output/unit['id'];loc.mkdir()
        row=dict(id=unit['id'],input=unit,model_calls=0,callback_calls=0)
        op=unit['operation'];change=unit['change']
        try:
            if op=='parse':
                value=entry.strict_loads(change)
            elif op in ('normalize_equal','invalid_config','normalize_reordered_keys'):
                other=deepcopy(baseline)
                if op=='normalize_reordered_keys':other=dict(reversed(list(other.items())))
                else:other.update(change)
                value=entry.config_hash(baseline)==entry.config_hash(other)
            elif op=='package':
                altered=deepcopy(data)
                if change=='duplicate_condition_id':altered['conditions'][1]['condition_id']=altered['conditions'][0]['condition_id']
                else:altered['conditions'][1]['common']=deepcopy(altered['conditions'][0]['common'])
                value=entry.validate_package(altered)
            elif op in ('preflight','purpose'):
                source=loc/'source';source.mkdir()
                for name in identity['files']:
                    dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,dest)
                dest=loc/'run';manifest=launch(source,dest,identity)
                if op=='purpose':manifest['purpose']=change;manifest['input']['path']='MUST_NOT_BE_READ.json'
                elif change.startswith('input_append_space'):
                    path=source/manifest['input']['path'];path.write_bytes(path.read_bytes()+b' ')
                    if change.endswith('update_manifest_hash'):
                        manifest['input']['sha256']=sha(path)
                        manifest['files'][manifest['input']['path']]['sha256']=sha(path)
                elif change=='core_file_append_space_keep_hash':
                    path=source/CORE[1];path.write_bytes(path.read_bytes()+b' ')
                elif change=='python_sha_all_zero':manifest['python_sha256']='0'*64
                elif change=='manifest_output_different_directory':manifest['output_directory']=str(loc/'different')
                path=loc/'launch.json';save(path,manifest)
                digest='0'*64 if change=='manifest_expected_sha_all_zero' else sha(path)
                value=entry.preflight(source,path,digest,dest)
            elif op=='output':
                path=loc/'existing';path.mkdir();(path/'sentinel').write_text('preserve')
                try:value=entry.create_output(path)
                finally:row['sentinel_preserved']=(path/'sentinel').read_text()=='preserve'
            elif op=='batch_callback':
                package=deepcopy(data);package['conditions']=package['conditions'][:2]
                dest=loc/'batch';entry.create_output(dest)
                def fake(common,order):
                    row['callback_calls']+=1
                    if unit['id']=='U26':raise RuntimeError('PUBLIC_FIXTURE')
                    return {}
                terminal=entry.execute_batch(package,fake,dest,{'entry_revision':identity['source_commit']})
                value=dict(status=terminal['status'],rows=[r['status'] for r in terminal['rows']],
                    raw_saved=(dest/'X01.json').is_file(),started_saved=(dest/'X01-started.json').is_file(),terminal_saved=(dest/'terminal.json').is_file())
                row['archive_files']={p.name:sha(p) for p in dest.iterdir() if p.is_file()}
            elif op=='checker_selftest':
                checks=compare(change['actual'],change['expected']);value=all(x['matches'] for x in checks);row['checks']=checks
            else:raise RuntimeError('Unknown frozen interface operation')
        except entry.EntryError as error:
            value=error.code
        except Exception as error:
            value=dict(unexpected=type(error).__name__,message=str(error),traceback=traceback.format_exc())
        row.update(actual=value,expected=unit['expected'])
        row['core_not_imported']='aegis_dc.london_treatments' not in sys.modules
        row['matches']=same(value,unit['expected']) and row['callback_calls']==unit['callback_calls'] and row.get('sentinel_preserved',True) and row['core_not_imported']
        save(loc/'result.json',row);results.append(row)
    return results


def archive_fault_check(entry,output,data,fixture):
    dest=output/'U30';entry.create_output(dest);ledger={};original=entry.report.save
    def fail_once(path,value):
        if path.name=='X01-raw.json':raise OSError('PUBLIC_ARCHIVE_FAILURE')
        return original(path,value)
    package=deepcopy(data);package['conditions']=package['conditions'][:2]
    caught=None
    try:
        entry.report.save=fail_once
        entry.execute_batch(package,counted(lambda common,order:deepcopy(fixture['callback']),ledger),dest,{'entry_revision':'PUBLIC_FIXTURE'})
    except OSError as error:caught=type(error).__name__
    finally:entry.report.save=original
    actual=dict(callback_calls=ledger['calls'],model_calls=0,suffix_started=(dest/'X02-started.json').exists(),exception=caught,
        start_record_retained=(dest/'X01-started.json').exists(),independent_call_count_retained=ledger['calls'],reported_internal_counts=ledger['reported_internal_counts'])
    result=dict(id='U30',input=fixture,actual=actual,expected=fixture['expected'],matches=same(actual,fixture['expected']))
    save(dest/'result.json',result);return result


def inspect_saved(directory,expectations,fixtures):
    terminal=json.loads((directory/'terminal.json').read_text())
    units=[];actuals={};counts=dict(runner_calls=0,constructor_attempts=0,plant_entry_calls=0,policy_calls=0,scorer_calls=0)
    for unit in expectations['units']:
        path=directory/(unit['id']+'.json');record=json.loads(path.read_text());raw_path=directory/record['raw_file']
        raw=json.loads(raw_path.read_text());actual=raw['actual'];actuals[unit['id']]=actual
        checks=[]
        checks.append(dict(path='raw_sha256',actual=sha(raw_path),expected=record['raw_sha256'],matches=sha(raw_path)==record['raw_sha256']))
        for arm,expected in unit['expected'].items():
            checks += [dict(arm=arm,**x) for x in compare(actual['arms'][arm],expected)]
        ledger={name:sum(c['kind']==kind for c in actual['calls']) for name,kind in [('constructor_attempts','constructor'),('plant_entry_calls','plant'),('policy_calls','policy'),('scorer_calls','scorer')]}
        checks.append(dict(path='call_ledger_counts',actual=actual['counts'],expected=ledger,matches=same(actual['counts'],ledger)))
        record_meta=next(r for r in terminal['records'] if r['condition_id']==unit['id'])
        checks.append(dict(path='record_sha256',actual=sha(path),expected=record_meta['sha256'],matches=sha(path)==record_meta['sha256']))
        counts['runner_calls']+=1
        for name,n in ledger.items():counts[name]+=n
        units.append(dict(id=unit['id'],assertions=checks,passed=all(x['matches'] for x in checks)))
    pairs=[]
    for pair in expectations['pairs']:
        checks=[]
        for path in pair['paths']:
            left,right=[at(actuals[name],path) for name in pair['units']]
            checks.append(dict(path=path,matches=same(left,right)))
        pairs.append(dict(id=pair['id'],assertions=checks,passed=all(x['matches'] for x in checks)))
    total_checks=[dict(name='terminal_counts',matches=same(counts,terminal['counts'])),
        dict(name='constructor_count',matches=counts['constructor_attempts']==fixtures['expected_core_arm_runs']),
        dict(name='policy_count',matches=counts['policy_calls']==fixtures['expected_policy_calls']),
        dict(name='terminal_status',matches=terminal['status']=='COMPLETED_PUBLIC_ENGINEERING'),
        dict(name='noncompliant_retained',matches=[r['condition_id'] for r in terminal['rows'] if r['comparison_status']=='NONCOMPLIANT_NOT_VALID_GAIN']==fixtures['expected_noncompliant'])]
    return dict(units=units,pairs=pairs,counts=counts,totals=total_checks,
        passed=all(u['passed'] for u in units+pairs) and all(c['matches'] for c in total_checks))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['red','green','verify'],required=True)
    parser.add_argument('--source-manifest-sha',required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--saved',type=Path)
    args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Remote allocation required')
    root=Path(__file__).resolve().parents[1];args.output.mkdir(parents=True,exist_ok=False)
    result=dict(mode=args.mode,status='FAIL',job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),research_runs=0,confirmation_runs=0,model_calls=0)
    try:
        source_path=root/'execution-source.json'
        if sha(source_path)!=args.source_manifest_sha:raise ValueError('SOURCE_MANIFEST_HASH')
        identity=json.loads(source_path.read_text());result['source_identity']=identity
        for name,meta in identity['files'].items():
            if sha(root/name)!=meta['sha256']:raise ValueError('SOURCE_DRIFT:'+name)
        if sha(Path(sys.executable).resolve())!=PY_SHA:raise ValueError('PYTHON_DRIFT')
        if args.mode=='red':
            if (root/'scripts/london_confirmation_entry.py').exists():raise ValueError('RED_EXPECTED_MISSING_ENTRY')
            result.update(status='EXPECTED_RED_MISSING_ENTRY',model_calls=0)
        else:
            entry=importlib.import_module('london_confirmation_entry')
            data=json.loads((root/PACK/'inputs.json').read_text())
            expected=json.loads((root/PACK/'expected.json').read_text())
            fixtures=json.loads((root/PACK/'interface-fixtures.json').read_text())
            if args.mode=='green':
                result['interfaces']=interface_checks(entry,root,args.output,identity,fixtures,data)
                result['interfaces'].append(archive_fault_check(entry,args.output,data,json.loads((root/PACK/'interface-addendum.json').read_text())))
                if not all(r['matches'] for r in result['interfaces']):raise ValueError('INTERFACE_FAILURE_NO_CORE_STARTED')
                dest=args.output/'batch';entry.create_output(dest)
                manifest=launch(root,dest,identity);manifest_path=args.output/'launch.json';save(manifest_path,manifest)
                admitted=entry.preflight(root,manifest_path,sha(manifest_path),dest)
                sys.path.insert(0,str(root/'src'));core=importlib.import_module('aegis_dc.london_treatments')
                result['independent_model_accounting']={}
                try:terminal=entry.execute_batch(admitted,counted(core.run_condition,result['independent_model_accounting']),dest,manifest)
                finally:
                    result['model_calls']=result['independent_model_accounting']['calls']
                    result['unknown_internal_counts_for_calls']=result['independent_model_accounting']['unreturned']
                result['core_counts']=terminal['counts']
            else:
                if args.saved is None:raise ValueError('Saved output required')
                dest=args.saved
                ledger={};counted(lambda common,order:{},ledger)(data['conditions'][0]['common'],['I','D','P'])
                result['malformed_count_regression']=dict(input='Original U27 empty return, no model',actual=ledger,expected_unknown_count_calls=1,
                    passed=ledger['calls']==1 and ledger['unknown_count_calls']==1 and ledger['unreturned']==0)
                result['archive_count_regression']=archive_fault_check(entry,args.output,data,json.loads((root/PACK/'interface-addendum.json').read_text()))
            result['verification']=inspect_saved(dest,expected,fixtures)
            result['status']='PASS_FINITE_PUBLIC_ENGINEERING' if result['verification']['passed'] else 'FAIL_EXPECTATION'
            if args.mode=='verify' and not (result['malformed_count_regression']['passed'] and result['archive_count_regression']['matches']):result['status']='FAIL_COUNT_REGRESSION'
        result['source_unchanged']=all(sha(root/f)==meta['sha256'] for f,meta in identity['files'].items())
        if not result['source_unchanged']:result['status']='SOURCE_CHANGED'
    except Exception as error:
        result['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    save(args.output/'qualification.json',result)
    print(json.dumps({k:result[k] for k in ['mode','status','job_id','model_calls']}))
    return 0 if result['status']=='PASS_FINITE_PUBLIC_ENGINEERING' else 1


if __name__=='__main__':raise SystemExit(main())
