"""Frozen engineering qualification only; rejects development/confirmation files."""
import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import sys
import traceback
from qualify_london_e14 import canonical, detached, field, write

VIEW_KEYS={'view_schema','time','pre_open','pending','terminal_failure','phase','records','receipts','history','attempted','known_epoch','certificate','context'}
FORBIDDEN_KEYS={'condition_id','condition_label','common','tF','tR','next_event','next_private_event','family','ready','exec_fault','approval','commit','verification','guard'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def validate_engineering(data):
    if data.get('schema') not in ('aegisdc-idp-engineering-v1','aegisdc-idp-engineering-guards-v1') or data.get('classification')!='ENGINEERING_ONLY':
        raise ValueError('Only frozen engineering inputs are authorized here')
    if data.get('public_tick_seconds')!=1 or not data.get('units') or type(data.get('pairs')) is not list or data['schema']=='aegisdc-idp-engineering-v1' and not data['pairs']:
        raise ValueError('Incomplete frozen engineering manifest')
    if len({u['id'] for u in data['units']})!=len(data['units']):raise ValueError('Repeated unit identity')
    for u in data['units']:
        if u['kind']=='triplet':
            if set(u['expected'])!={'I','D','P'} or any(not e for e in u['expected'].values()):raise ValueError('Missing independent arm expectations')
        elif u['kind']=='score':
            if not u['expected']:raise ValueError('Missing score expectations')
        elif u['kind']=='runner_fault':
            if data['schema']!='aegisdc-idp-engineering-guards-v1' or u['input']['fault'] not in ('advance_H','final_audit') or not u['expected']:raise ValueError('Invalid private fault fixture')
        else:raise ValueError('Unsupported qualification kind')

def private_keys(value):
    if isinstance(value,dict):
        return sorted(set(value)&FORBIDDEN_KEYS | {k for v in value.values() for k in private_keys(v)})
    if isinstance(value,list):return sorted({k for v in value for k in private_keys(v)})
    return []

def unit_run(module,score_module,u,totals):
    row=dict(id=u['id'],kind=u['kind'],input=deepcopy(u['input']),status='FAIL',assertions=[],failures=[])
    totals['units_executed']+=1
    def check(label,actual,expected):
        ok=canonical(actual)==canonical(expected);totals['assertions']+=1
        row['assertions'].append(dict(label=label,actual=detached(actual),expected=detached(expected),matches=ok))
        if not ok:row['failures'].append(label)
    try:
        if u['kind']=='score':
            totals['scorer_calls']+=1
            x=u['input'];actual=detached(score_module.score_arm(deepcopy(x['audit']),deepcopy(x['run']),x['isolation_ok'],deepcopy(x['audit']['original_input'])))
            row['actual']=actual
            for path,expected in u['expected'].items():check(path,field(actual,path),expected)
        elif u['kind']=='runner_fault':
            # Evaluator-only one-shot injection after the strategy has stopped.
            # Never pass the fixture label or injection plan to choose().
            row['fault_injection']=dict(target_arm='I',location=u['input']['fault'],scope='Evaluator-only one-shot failure; not a scientific treatment difference')
            base=module.E14Run;created=0
            class FaultWorld(base):
                def __init__(self,config):
                    nonlocal created
                    created+=1;self._target=created==1;self._injected=False
                    super().__init__(config)
                def advance(self,time):
                    if self._target and not self._injected and u['input']['fault']=='advance_H' and Fraction(time)==20:
                        self._injected=True;raise RuntimeError('INJECTED_FINAL_ADVANCE_FAILURE')
                    return super().advance(time)
                def audit(self):
                    if self._target and not self._injected and u['input']['fault']=='final_audit' and self.time==20:
                        self._injected=True;raise RuntimeError('INJECTED_FINAL_AUDIT_FAILURE')
                    return super().audit()
            totals['runner_calls']+=1;module.E14Run=FaultWorld
            try:actual=detached(module.run_condition(deepcopy(u['input']['common']),order=u['input']['order']))
            finally:module.E14Run=base
            row['actual']=actual
            for name in ('constructor_attempts','plant_entry_calls','policy_calls','scorer_calls'):totals[name]+=actual['counts'][name]
            check('all-arm-records-retained',sorted(actual['arms']),['D','I','P'])
            check('injected-arm-error-retained',bool(actual['arms']['I']['errors']),True)
            check('global-error-retained',bool(actual['errors']),True)
            for arm in ('D','P'):check(arm+':no-error',actual['arms'][arm]['errors'],[])
            for path,expected in u['expected'].items():check(path,field(actual,path),expected)
            failed=[c for c in actual['calls'] if 'error' in c]
            check('exact-one-injected-call',len(failed),1)
            check('injected-error',failed[0]['error']['message'],'INJECTED_FINAL_ADVANCE_FAILURE' if u['input']['fault']=='advance_H' else 'INJECTED_FINAL_AUDIT_FAILURE')
        else:
            totals['runner_calls']+=1
            actual=detached(module.run_condition(deepcopy(u['input']['common']),order=u['input']['order']))
            row['actual']=actual
            counts=actual['counts']
            for name in ('constructor_attempts','plant_entry_calls','policy_calls','scorer_calls'):totals[name]+=counts[name]
            check('runner-errors',actual['errors'],[])
            for name in ('initial_public_equal','initial_private_equal','input_unchanged','all_other_states_unchanged'):
                check('isolation:'+name,actual['isolation'][name],True)
            for kind,ids in actual['isolation']['object_ids'].items():check('distinct:'+kind,len(set(ids.values())),3)
            for pair in actual['isolation']['snapshots']:
                before=actual['calls'][pair['before_call']]['actual'];after=actual['calls'][pair['after_call']]['actual']
                check('other-state:'+str(pair['before_call']),before,after)
            initial=list(actual['initial_public_views'].values())
            for view in initial[1:]:check('initial-public',view,initial[0])
            for arm,expected in u['expected'].items():
                arm_result=actual['arms'][arm]
                for path,want in expected.items():check(arm+':'+path,field(arm_result,path),want)
                check(arm+':errors',arm_result['errors'],[])
                check(arm+':full-window',arm_result['final_audit']['time'],u['input']['common']['H'])
                check(arm+':original-config',arm_result['final_audit']['original_input'],u['input']['common'])
                cap={'I':5,'D':2,'P':0}[arm]
                check(arm+':request-cap',len(arm_result['requests'])<=cap,True)
                actions=arm_result['requested_actions'];check(arm+':no-action-retry',len(actions)==len(set(actions)),True)
                for i,frame in enumerate(arm_result['public_trace']):
                    view=frame['view'];t=Fraction(view['time']);tf=u['input']['common']['tF']
                    check(f'{arm}:{i}:view-keys',sorted(view),sorted(VIEW_KEYS))
                    check(f'{arm}:{i}:no-private-fields',private_keys(view),[])
                    check(f'{arm}:{i}:no-private-label',u['id'] in canonical(view),False)
                    check(f'{arm}:{i}:public-clock',t.denominator==1 and 0<=t<20,True)
                    check(f'{arm}:{i}:pre-only',view['pre_open'] and (tf is None or t<Fraction(tf)),True)
                    if frame['payload'] and frame['payload']['action']=='VERIFY_CTRL':
                        payload=frame['payload'];receipts=[r for r in view['receipts'] if r['record_kind']=='EXECUTION_RECEIPT' and r['status']=='EXECUTED_UNVERIFIED' and Fraction(r['available_at'])<=t]
                        check(f'{arm}:{i}:public-parent',any(payload['execution_id']==r['execution_id'] and payload['target_config_epoch']==r['target_config_epoch'] for r in receipts),True)
                    if frame['payload'] and frame['payload'].get('mode')=='EVIDENCE':
                        known=[r['record_id'] for r in view['records'] if r['status']=='KNOWN' and r['action'] in ('READ_POS','READ_VOLT','READ_CONFIG')]
                        check(f'{arm}:{i}:public-evidence',frame['payload']['evidence_ids'],known)
            recorded={k:sum(c['kind']==kind for c in actual['calls']) for k,kind in [('constructor_attempts','constructor'),('plant_entry_calls','plant'),('policy_calls','policy'),('scorer_calls','scorer')]}
            check('call-ledger-counts',counts,recorded)
    except Exception as error:
        row['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc());row['failures'].append('unit-exception')
    row['status']='PASS' if not row['failures'] else 'FAIL';totals['units_passed' if row['status']=='PASS' else 'units_failed']+=1
    return row

def main():
    p=argparse.ArgumentParser();p.add_argument('--cases',type=Path,required=True);p.add_argument('--sha',required=True);p.add_argument('--source',required=True);p.add_argument('--source-manifest-sha',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Remote allocation required')
    root=Path(__file__).resolve().parents[1];a.cases=a.cases.resolve();a.output.mkdir(parents=True,exist_ok=False)
    totals=dict(units_executed=0,units_passed=0,units_failed=0,runner_calls=0,constructor_attempts=0,plant_entry_calls=0,policy_calls=0,scorer_calls=0,assertions=0,pairs_passed=0,pairs_failed=0)
    result=dict(status='PRE_EXECUTION_FAILURE',source_commit=a.source,input_sha256=sha(a.cases),job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),counts=totals,units=[],pairs=[],research_runs=0,confirmation_results_accessed=False);code=1
    try:
        if result['input_sha256']!=a.sha:raise ValueError('Frozen input mismatch')
        inputs=json.loads(a.cases.read_text(encoding='utf-8'));validate_engineering(inputs)
        manifest_path=root/'execution-source.json'
        if sha(manifest_path)!=a.source_manifest_sha:raise ValueError('Manifest mismatch')
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['source_commit']!=a.source:raise ValueError('Revision mismatch')
        required={'src/aegis_dc/__init__.py','src/aegis_dc/london_e14.py','src/aegis_dc/london_treatments.py','src/aegis_dc/london_treatment_score.py','scripts/qualify_london_e14.py','scripts/qualify_london_treatments.py',str(a.cases.relative_to(root))}
        if not required.issubset(manifest['files']):raise ValueError('Runner/scorer not present in pinned source')
        for f,meta in manifest['files'].items():
            if sha(root/f)!=meta['sha256']:raise ValueError('Source/input drift: '+f)
        result['verified_execution_source']=manifest;result['source_manifest_sha256']=a.source_manifest_sha
        sys.path.insert(0,str(root/'src'));module=importlib.import_module('aegis_dc.london_treatments');scorer=importlib.import_module('aegis_dc.london_treatment_score')
        rows={}
        for u in inputs['units']:
            row=unit_run(module,scorer,u,totals);rows[u['id']]=row
            name=u['id']+'.json';write(a.output/name,row)
            result['units'].append(dict(id=u['id'],kind=u['kind'],status=row['status'],assertions=len(row['assertions']),failures=row['failures'],file=name,sha256=sha(a.output/name)))
        for pair in inputs['pairs']:
            row=dict(id=pair['id'],units=pair['units'],assertions=[]);ok=True
            for path in pair['paths']:
                totals['assertions']+=1
                try:
                    left,right=[field(rows[k]['actual'],path) for k in pair['units']]
                    if 'prefix' in pair:left,right=left[:pair['prefix']],right[:pair['prefix']]
                    match=canonical(left)==canonical(right);ok=ok and match
                    row['assertions'].append(dict(path=path,prefix=pair.get('prefix'),left_sha256=hashlib.sha256(canonical(left).encode()).hexdigest(),right_sha256=hashlib.sha256(canonical(right).encode()).hexdigest(),matches=match))
                except Exception as error:ok=False;row['assertions'].append(dict(path=path,matches=False,error=str(error)))
            row['status']='PASS' if ok else 'FAIL';result['pairs'].append(row);totals['pairs_passed' if ok else 'pairs_failed']+=1
        result['source_unchanged']=all(sha(root/f)==meta['sha256'] for f,meta in manifest['files'].items())
        result['status']='PASS_BOUNDED_RUNNER_ENGINEERING' if not totals['units_failed'] and not totals['pairs_failed'] and result['source_unchanged'] else 'FAIL';code=0 if result['status'].startswith('PASS') else 1
    except Exception as error:result['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    write(a.output/'terminal.json',result);print(json.dumps(dict(status=result['status'],counts=totals,output=str(a.output))));return code

if __name__=='__main__':raise SystemExit(main())
