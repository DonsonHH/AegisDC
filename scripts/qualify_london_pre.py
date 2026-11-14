"""Remote v2 checker: public/evaluator entry points against frozen literal answers.

No expected physical/observation logic is imported from the candidate model.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback


def digest(path):
    return sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def field(value, path):
    for part in path.split('.'):
        value = value[part]
    return value


def semantic_result(row):
    return ({key:field(row['actual'],key) for key in row['selected_fields']}
            if row.get('selected_fields') else row['actual'])


def invoke(model, operation):
    args = operation['args']
    name = operation['op']
    if name == 'mechanics': return model.mechanics()
    if name == 'view': return model.public_view()
    if name == 'audit': return model.audit()
    if name == 'advance': return model.advance(args['event'])
    if name == 'request': return model.request(args['payload'])
    if name == 'material': return model.audit_material(args['payload'])
    raise ValueError('Unknown checker operation: ' + name)


def run_case(module, case, ledger):
    result = dict(id=case['id'], source_refs=case['source_refs'], status='FAIL',
                  constructor_attempts=1, constructed=0, entry_calls=0, assertions=0,
                  failures=[], steps=[])
    payload=case['input']
    ledger['executed_units']+=1
    ledger['constructor_attempts']+=1
    try:
        if case['kind'] in ('physical','invalid_world'):
            model=module.PhysicalWorld(payload['world'])
        elif case['kind']=='pre':
            model=module.PRESession(payload['world'], payload['context'], payload['mode'])
        elif case['kind']=='challenge':
            model=module.ChallengeRun(payload['world'], payload['context'], payload['mode'])
        else: raise ValueError('Unknown case kind')
        result['constructed']=1
    except Exception as error:
        result['constructor_error']=dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())
        result['assertions']+=1
        ledger['executed_assertions']+=1
        if type(error).__name__==case.get('expected_constructor_error'):
            result['status']='PASS'
        else:
            result['failures'].append('Unexpected constructor error')
        return result
    if 'expected_constructor_error' in case:
        result['assertions']+=1
        ledger['executed_assertions']+=1
        result['failures'].append('Constructor accepted forbidden input')
        return result
    values={}
    for step in case['steps']:
        row=dict(label=step['label'], operation=step['op'], arguments=step['args'])
        result['entry_calls']+=1
        ledger['model_entry_calls']+=1
        try:
            # Detach every observed result immediately; later model mutation
            # must not rewrite previously captured evidence or identity baselines.
            actual=json.loads(canonical(invoke(model,step)))
            row['actual']=actual
            values[step['label']]=actual
            if 'expected' in step:
                observed=({key:field(actual,key) for key in step['select']} if 'select' in step else actual)
                row.update(expected=step['expected'], selected_fields=step.get('select'),
                           matches=canonical(observed)==canonical(step['expected']))
                result['assertions']+=1
                ledger['executed_assertions']+=1
                if not row['matches']:result['failures'].append(step['label']+': literal mismatch')
            if 'same_as' in step:
                relation=step['same_as']
                row['same_instance']=field(actual,relation['path'])==field(values[relation['label']],relation['reference_path'])
                result['assertions']+=1
                ledger['executed_assertions']+=1
                if not row['same_instance']:result['failures'].append(step['label']+': identity changed')
        except Exception as error:
            row['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
            result['failures'].append(step['label']+': unexpected error')
        result['steps'].append(row)
    result['status']='PASS' if not result['failures'] else 'FAIL'
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--expected-input-sha',required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--only',nargs='*')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':
        raise SystemExit('Execute only inside an allocated remote compute node')
    args.output.mkdir(parents=True,exist_ok=False)
    paths=[root/'src/aegis_dc/__init__.py',root/'src/aegis_dc/london_pre.py',Path(__file__),args.cases]
    before={str(p.relative_to(root)):digest(p) for p in paths}
    summary=dict(classification='BOUNDED_R2_ENGINEERING_QUALIFICATION_NOT_METHOD_OR_RSI_EXPERIMENT',
        status='PRE_EXECUTION_FAILURE',source_commit=args.source,job_id=os.environ['SLURM_JOB_ID'],
        hostname=socket.gethostname(),python=sys.version,python_sha256=digest(Path(sys.executable)),
        started_at_utc=datetime.now(timezone.utc).isoformat(),before_sha256=before,
        selected_units=0,executed_units=0,passed_units=0,failed_units=0,executed_assertions=0,
        selected_pair_assertions=0,pair_passed=0,pair_failed=0,constructor_attempts=0,model_entry_calls=0,
        model_qualified=False,registered_research_trials=0,research_model_calls=0)
    results=[]
    try:
        actual_source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        if actual_source!=args.source:raise ValueError('Source commit mismatch')
        if subprocess.check_output(['git','status','--porcelain'],cwd=root).strip():raise ValueError('Dirty source checkout')
        if digest(args.cases)!=args.expected_input_sha:raise ValueError('Frozen input SHA mismatch')
        for path in paths:
            if path.is_file():
                committed=subprocess.check_output(['git','show','HEAD:'+path.relative_to(root).as_posix()],cwd=root)
                if path.read_bytes()!=committed:raise ValueError('Execution bytes differ from committed blob: '+str(path))
        packet=json.loads(args.cases.read_text(encoding='utf-8'))
        all_cases=packet['cases'];ids=[c['id'] for c in all_cases]
        if len(set(ids))!=len(ids):raise ValueError('Duplicate unit IDs')
        if args.only and not set(args.only)<=set(ids):raise ValueError('Unknown selection')
        cases=[c for c in all_cases if not args.only or c['id'] in args.only]
        chosen={c['id'] for c in cases}
        pairs=[p for p in packet['pair_assertions'] if {p['left'],p['right']}<=chosen]
        summary.update(selected_units=len(cases),selected_pair_assertions=len(pairs),
                       deferred=packet['deferred'],selection=args.only or 'ALL')
        save(args.output/'attempt.json',summary)
        save(args.output/'frozen-inputs.json',packet)
        sys.path.insert(0,str(root/'src'))
        module=importlib.import_module('aegis_dc.london_pre')
        if Path(module.__file__).resolve()!=paths[1].resolve():raise ValueError('Wrong model import location')
        summary['status']='EXECUTING'
        summary['failed_ids']=[]
        for case in cases:
            result=run_case(module,case,summary);results.append(result)
            summary['passed_units']+=int(result['status']=='PASS')
            summary['failed_units']+=int(result['status']!='PASS')
            if result['status']!='PASS':summary['failed_ids'].append(result['id'])
            save(args.output/(case['id']+'.json'),dict(input=case,result=result))
        by_id={r['id']:r for r in results}
        pair_results=[]
        for pair in pairs:
            left,right=by_id[pair['left']],by_id[pair['right']]
            outcome=dict(definition=pair,status='FAIL',labels=[])
            for label in pair['labels']:
                summary['executed_assertions']+=1
                a=next((s for s in left['steps'] if s['label']==label),{})
                b=next((s for s in right['steps'] if s['label']==label),{})
                match='actual' in a and 'actual' in b and canonical(semantic_result(a))==canonical(semantic_result(b))
                outcome['labels'].append(dict(label=label,matches=match))
            if left['status']==right['status']=='PASS' and all(x['matches'] for x in outcome['labels']):outcome['status']='PASS'
            pair_results.append(outcome)
            summary['pair_passed']+=int(outcome['status']=='PASS')
            summary['pair_failed']+=int(outcome['status']!='PASS')
            save(args.output/f'pair-{len(pair_results):03}.json',outcome)
        save(args.output/'pairs.json',pair_results)
        summary.update(executed_units=len(results),passed_units=sum(x['status']=='PASS' for x in results),
            failed_units=sum(x['status']!='PASS' for x in results),
            executed_assertions=sum(x['assertions'] for x in results)+sum(len(x['labels']) for x in pair_results),
            constructor_attempts=sum(x['constructor_attempts'] for x in results),
            model_entry_calls=sum(x['entry_calls'] for x in results),
            pair_passed=sum(x['status']=='PASS' for x in pair_results),pair_failed=sum(x['status']!='PASS' for x in pair_results),
            failed_ids=[x['id'] for x in results if x['status']!='PASS'])
        summary['status']=('PASS_SELECTED_UNITS' if args.only else 'PASS_DECLARED_FINITE_SCOPE') if summary['failed_units']==summary['pair_failed']==0 else 'FAIL_RETAINED'
    except Exception as error:
        summary['status']='FAIL_AFTER_EXECUTION' if summary['executed_units'] else 'PRE_EXECUTION_FAILURE'
        summary['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    finally:
        after={str(p.relative_to(root)):digest(p) for p in paths}
        summary.update(after_sha256=after,source_bytes_unchanged=before==after,
                       unfinished_units=summary['executed_units']-summary['passed_units']-summary['failed_units'],
                       ended_at_utc=datetime.now(timezone.utc).isoformat())
        if before!=after:summary['status']='FAIL_SOURCE_CHANGED'
        summary['artifacts']={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(args.output.iterdir()) if p.is_file()}
        save(args.output/'terminal.json',summary)
        print(json.dumps(summary,ensure_ascii=False))
    return 0 if summary['status'] in ('PASS_DECLARED_FINITE_SCOPE','PASS_SELECTED_UNITS') else 1


if __name__=='__main__':raise SystemExit(main())
