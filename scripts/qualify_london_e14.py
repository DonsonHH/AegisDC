"""Independent checker against frozen E1-E4 literals; Slurm execution only."""
import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback


def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False)
def detached(x):return json.loads(canonical(x))
def field(x,path):
    for part in path.split('.'):x=x[part]
    return x
def selected(x,paths):return {p:field(x,p) for p in paths}
def literal_matches(actual,expected):return canonical(actual)==canonical(expected)
def write(path,x):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def independent_balances(audit):
    """Integrate returned constant segments independently of model routines."""
    load=ups=loss=unserved=Fraction(0)
    cursor=Fraction(0)
    for s in audit['segments']:
        start,end=Fraction(s['start']),Fraction(s['end'])
        if start!=cursor or end<=start:raise AssertionError('Non-continuous output segments')
        dt=end-start;cursor=end;p=Fraction(s['power']);d=Fraction(s['demand']);v=Fraction(s['service'])
        if not 0<=v<=d or p<0:raise AssertionError('Invalid output bounds')
        load+=dt*p
        if s['source']=='UPS':ups+=dt*p
        loss+=dt*(d-v)/d if d else 0
        unserved+=dt*(d-v)
    return dict(trace_continuous=cursor==Fraction(audit['time']),load=load==Fraction(audit['load_energy']),ups=ups==Fraction(audit['ups_energy']),energy=Fraction(audit['original_input']['E0'])-Fraction(audit['E'])==ups,loss=loss==Fraction(audit['L']),unserved=unserved==Fraction(audit['U']),energy_nonnegative=Fraction(audit['E'])>=0)


def run_unit(module,unit,totals):
    row=dict(id=unit['id'],refs=unit['refs'],input=deepcopy(unit['input']),kind=unit['kind'],status='FAIL',constructor_attempts=0,entry_calls=0,assertions=0,failures=[],steps=[],saved={})
    def assertion(name,actual,expected):
        row['assertions']+=1;totals['assertions']+=1
        match=literal_matches(actual,expected)
        if not match:row['failures'].append(name)
        return dict(name=name,actual=detached(actual),expected=detached(expected),matches=match)
    def call(name,fn,*args,**kwargs):
        row['entry_calls']+=1;totals['entry_calls']+=1
        return detached(fn(*args,**kwargs))
    totals['units_executed']+=1
    try:
        data=unit['input']
        if unit['kind']=='decision':
            value=call('decide',module.decide,deepcopy(data['view']),data['method'])
            row['decision']=value
            row['steps'].append(dict(operation='decide',arguments=dict(view=data['view'],method=data['method']),actual=value,assertion=assertion('literal-decision',value,data['expected'])))
        elif unit['kind']=='control':
            try:
                # private_fixture is deliberately not a control input.
                value=call('local_control',module.local_control,data['family'],deepcopy(data['signals']),data['time'])
                row['steps'].append(dict(operation='local_control',actual=value,assertion=assertion('local-control',value,data['expected'])))
                if data['expected_error']:assertion('expected-rejection',None,data['expected_error'])
            except Exception as error:
                row['steps'].append(dict(operation='local_control',exception=dict(type=type(error).__name__,message=str(error)),assertion=assertion('local-rejection',type(error).__name__,data['expected_error'])))
        elif unit['kind']=='run':
            row['constructor_attempts']+=1;totals['constructor_attempts']+=1
            model=module.E14Run(deepcopy(data));state_object=model._state
            row['constructed']=True
            for number,operation in enumerate(unit['steps']):
                op=operation['op'];args=deepcopy(operation['args'])
                observed=dict(index=number,operation=op,arguments=args,assertions=[])
                try:
                    if op=='advance':actual=call(op,model.advance,args['time'])
                    elif op=='request':actual=call(op,model.request,args['payload'])
                    elif op=='audit':actual=call(op,model.audit)
                    elif op in ('view_select','save_view'):actual=call(op,model.public_view)
                    elif op=='copy':actual=call(op,model.copy_record,args['record_id'],args['copy_id'])
                    elif op in ('record','receipt','internal_approval','conservation'):
                        raw=call(op,model.audit)
                        observed['full_audit']=raw
                        if op=='record':actual=raw['observations'][args['index']]
                        elif op=='receipt':actual=next(r for r in raw['receipts'] if r['record_kind']==args['kind'])
                        elif op=='internal_approval':actual=raw['internal_approval']
                        else:
                            actual=independent_balances(raw)
                            for name,ok in actual.items():observed['assertions'].append(assertion(name,ok,True))
                    else:raise ValueError('Unknown frozen operation: '+op)
                    actual=detached(actual);observed['actual']=actual
                    if op=='save_view':row['saved'][args['label']]=actual
                    if 'expected' in operation:
                        subset=selected(actual,operation['select']) if operation.get('select') else actual
                        observed['assertions'].append(assertion('literal',subset,operation['expected']))
                    observed['assertions'].append(assertion('continuous-state-object',model._state is state_object,True))
                except Exception as error:
                    observed['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
                    row['failures'].append('step-'+str(number)+'-'+op)
                row['steps'].append(observed)
            row['public']=call('final_public_view',model.public_view)
            row['audit']=call('final_audit',model.audit)
        else:raise ValueError('Unknown frozen unit kind')
    except Exception as error:
        row['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
        row['failures'].append('construction-or-unit-exception')
    row['status']='PASS' if not row['failures'] else 'FAIL'
    totals['units_passed' if row['status']=='PASS' else 'units_failed']+=1
    return row


def main():
    p=argparse.ArgumentParser();p.add_argument('--cases',type=Path,required=True);p.add_argument('--sha',required=True);p.add_argument('--source',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Allocated remote compute node required')
    a.cases=a.cases.resolve();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
    totals=dict(units_executed=0,units_passed=0,units_failed=0,constructor_attempts=0,entry_calls=0,assertions=0,pairs_passed=0,pairs_failed=0)
    result=dict(status='PRE_EXECUTION_FAILURE',source_commit=a.source,input_sha256=digest(a.cases),job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),python=sys.version,counts=totals,units=[],pairs=[],research_experiments=0)
    exit_code=1
    try:
        if result['input_sha256']!=a.sha:raise ValueError('Frozen input identity mismatch')
        root=Path(__file__).resolve().parents[1]
        result['runtime_sha256']={str(f.relative_to(root)):digest(f) for f in [root/'src/aegis_dc/london_e14.py',Path(__file__),a.cases] if f.exists()}
        sys.path.insert(0,str(root/'src'))
        module=importlib.import_module('aegis_dc.london_e14')
        frozen=json.loads(a.cases.read_text(encoding='utf-8'))
        result['declared_units']=len(frozen['units']);result['declared_pairs']=len(frozen['pairs'])
        rows={}
        for unit in frozen['units']:
            row=run_unit(module,unit,totals);rows[unit['id']]=row
            filename=unit['id']+'.json';write(a.output/filename,row)
            result['units'].append(dict(id=unit['id'],status=row['status'],entry_calls=row['entry_calls'],assertions=row['assertions'],failures=row['failures'],file=filename,sha256=digest(a.output/filename)))
        for pair in frozen['pairs']:
            item=dict(id=pair['id'],units=pair['units'],assertions=[]);good=True
            for path in pair['paths']:
                totals['assertions']+=1
                try:
                    left,right=[field(rows[key],path) for key in pair['units']]
                    match=literal_matches(left,right)
                    item['assertions'].append(dict(path=path,left=left,right=right,matches=match))
                    good=good and match
                except Exception as error:
                    good=False;item['assertions'].append(dict(path=path,error=str(error),matches=False))
            item['status']='PASS' if good else 'FAIL';result['pairs'].append(item)
            totals['pairs_passed' if good else 'pairs_failed']+=1
        result['source_unchanged']=all(digest(root/f)==h for f,h in result['runtime_sha256'].items())
        result['status']='PASS_DECLARED_FINITE_SCOPE' if not totals['units_failed'] and not totals['pairs_failed'] and result['source_unchanged'] else 'FAIL'
        exit_code=0 if result['status']=='PASS_DECLARED_FINITE_SCOPE' else 1
    except Exception as error:result['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    finally:
        write(a.output/'terminal.json',result)
        print(json.dumps(dict(status=result['status'],counts=totals,output=str(a.output)),ensure_ascii=False))
    return exit_code


if __name__=='__main__':raise SystemExit(main())
