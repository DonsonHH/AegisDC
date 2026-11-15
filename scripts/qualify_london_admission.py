"""Bounded fixed-operation interface checker; not a research policy runner."""
import argparse
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import sys
import traceback
from qualify_london_e14 import canonical, detached, field, write


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def unit_run(module,unit,totals):
    r=dict(id=unit['id'],kind=unit['kind'],input=deepcopy(unit['input']),status='FAIL',constructor_attempts=0,entry_calls=0,assertions=0,steps=[],cycles={},failures=[])
    totals['units_executed']+=1
    def call(fn,*args):
        r['entry_calls']+=1;totals['entry_calls']+=1
        return detached(fn(*args))
    def compare(label,actual,expected):
        r['assertions']+=1;totals['assertions']+=1
        ok=canonical(actual)==canonical(expected)
        if not ok:r['failures'].append(label)
        return dict(label=label,actual=actual,expected=expected,matches=ok)
    try:
        data=unit['input']
        if unit['kind']=='invalid_view':
            actual=None
            try:call(module.decide,deepcopy(data['view']),data['method'])
            except Exception as e:actual=type(e).__name__
            r['steps'].append(dict(operation='invalid_view',assertions=[compare('explicit-version-refusal',actual,unit['expected_error'])]))
        else:
            r['constructor_attempts']+=1;totals['constructor_attempts']+=1
            model=module.E14Run(deepcopy(data['config']));state=model._state
            for index,s in enumerate(unit['steps']):
                a=deepcopy(s['args']);row=dict(index=index,operation=s['op'],arguments=a,assertions=[])
                try:
                    if s['op']=='advance':actual=call(model.advance,a['time'])
                    elif s['op']=='request':actual=call(model.request,a['payload'])
                    elif s['op']=='audit':actual=call(model.audit)
                    elif s['op']=='cycle':
                        view=call(model.public_view);decision=call(module.decide,deepcopy(view),data['method']);action=decision['action'];payload=None;reply=None
                        if action in ('READ_POS','READ_VOLT','READ_CONFIG','VERIFY_CTRL','PROPOSE_FIX'):
                            wire='FIX_CTRL' if action=='PROPOSE_FIX' else action
                            payload=dict(action=wire,request_id=a['request_id'],problem_id='q-1',target='feeder-B' if wire in ('READ_POS','READ_VOLT') else 'ctrl-1')
                            if wire=='FIX_CTRL':payload['mode']=decision['mode']
                            if wire=='VERIFY_CTRL':
                                e=next(x for x in reversed(view['receipts']) if x['record_kind']=='EXECUTION_RECEIPT' and x['status']=='EXECUTED_UNVERIFIED')
                                payload.update(execution_id=e['execution_id'],target_config_epoch=e['target_config_epoch'])
                            reply=call(model.request,payload)
                        actual=dict(view=view,decision=decision,payload=payload,reply=reply);r['cycles'][a['label']]=deepcopy(actual)
                    else:raise ValueError('Unknown frozen operation')
                    row['actual']=detached(actual)
                    if 'expected' in s:
                        for path,expected in s['expected'].items():
                            try:observed=field(actual,path)
                            except (KeyError,TypeError,IndexError):observed={'missing_field':path}
                            row['assertions'].append(compare('literal:'+path,observed,expected))
                    row['assertions'].append(compare('continuous-state',model._state is state,True))
                except Exception as e:
                    row['error']=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc());r['failures'].append('step-'+str(index))
                r['steps'].append(row)
            r['public']=call(model.public_view);r['audit']=call(model.audit)
    except Exception as e:r['error']=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc());r['failures'].append('unit-exception')
    r['status']='PASS' if not r['failures'] else 'FAIL';totals['units_passed' if r['status']=='PASS' else 'units_failed']+=1
    return r


def main():
    p=argparse.ArgumentParser();p.add_argument('--cases',type=Path,required=True);p.add_argument('--sha',required=True);p.add_argument('--source',required=True);p.add_argument('--source-manifest-sha',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Remote Slurm allocation required')
    root=Path(__file__).resolve().parents[1];a.cases=a.cases.resolve();a.output.mkdir(parents=True,exist_ok=False)
    totals=dict(units_executed=0,units_passed=0,units_failed=0,constructor_attempts=0,entry_calls=0,assertions=0,pairs_passed=0,pairs_failed=0)
    result=dict(status='PRE_EXECUTION_FAILURE',source_commit=a.source,input_sha256=digest(a.cases),job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),counts=totals,units=[],pairs=[],research_experiments=0);code=1
    try:
        if result['input_sha256']!=a.sha:raise ValueError('Frozen input mismatch')
        identity=root/'execution-source.json'
        if digest(identity)!=a.source_manifest_sha:raise ValueError('Source manifest mismatch')
        manifest=json.loads(identity.read_text(encoding='utf-8'))
        if manifest['source_commit']!=a.source:raise ValueError('Execution revision mismatch')
        required={'src/aegis_dc/__init__.py','src/aegis_dc/london_e14.py','scripts/qualify_london_e14.py','scripts/qualify_london_admission.py',str(a.cases.relative_to(root))}
        if not required.issubset(manifest['files']):raise ValueError('Missing runtime identity')
        for f,info in manifest['files'].items():
            if digest(root/f)!=info['sha256']:raise ValueError('Source differs from commit: '+f)
        result['source_manifest_sha256']=a.source_manifest_sha;result['verified_execution_source']=manifest
        sys.path.insert(0,str(root/'src'));module=importlib.import_module('aegis_dc.london_e14');frozen=json.loads(a.cases.read_text(encoding='utf-8'));rows={}
        for u in frozen['units']:
            row=unit_run(module,u,totals);rows[u['id']]=row;filename=u['id']+'.json';write(a.output/filename,row)
            result['units'].append(dict(id=u['id'],status=row['status'],entry_calls=row['entry_calls'],assertions=row['assertions'],constructor_attempts=row['constructor_attempts'],failures=row['failures'],file=filename,sha256=digest(a.output/filename)))
        for pair in frozen['pairs']:
            row=dict(id=pair['id'],units=pair['units'],assertions=[]);ok=True
            for path in pair['paths']:
                totals['assertions']+=1
                try:
                    left,right=[field(rows[x],path) for x in pair['units']];match=canonical(left)==canonical(right);ok=ok and match
                    row['assertions'].append(dict(path=path,left=left,right=right,matches=match))
                except Exception as e:ok=False;row['assertions'].append(dict(path=path,matches=False,error=str(e)))
            row['status']='PASS' if ok else 'FAIL';result['pairs'].append(row);totals['pairs_passed' if ok else 'pairs_failed']+=1
        result['source_unchanged']=all(digest(root/f)==info['sha256'] for f,info in manifest['files'].items())
        result['status']='PASS_FINITE_INTERFACE_SCOPE' if not totals['units_failed'] and not totals['pairs_failed'] and result['source_unchanged'] else 'FAIL';code=0 if result['status'].startswith('PASS') else 1
    except Exception as e:result['error']=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    write(a.output/'terminal.json',result);print(json.dumps(dict(status=result['status'],counts=totals,output=str(a.output))));return code


if __name__=='__main__':raise SystemExit(main())
