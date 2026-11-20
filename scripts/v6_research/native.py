"""Verified native returns and saved scores at the research-purpose arm boundary."""
import os
from pathlib import Path
import sys

from aegis_dc.native_compare_inputs import file_hash, read, write_new
from aegis_dc.native_compare_run import run_order
from aegis_dc.native_compare_score import read_native, score_arm
from patrol_rsi.contracts import digest
from .binding import ARMS, REAL, SURROGATE, GateError, check


def native_files(release):
    return {k:v for k,v in release.manifest['runtime_and_material_sha256'].items()
            if (k.startswith('src/aegis_dc/') and k.count('/')==2 and k.endswith('.py')) or k=='src/patrol_rsi/contracts.py'}


def verify_return(release,case,arm,run,scenario):
    pins=release.conditions.rows[case]['arms'][arm]
    source=run['code_identity']
    check(source['files']==native_files(release),'RETURN_SOURCE_FILES')
    check(source['source_tree_sha256']==digest(source['files'])==release.manifest['native_source_tree'],'RETURN_SOURCE_TREE')
    check(run['scenario_sha256']==pins['scenario']==digest(scenario),'RETURN_SCENARIO')
    inputs=run['inputs']
    for field,ident,code in [('dispatch_program','dispatch','RETURN_DISPATCH'),('business_program','business','RETURN_BUSINESS'),
                              ('boundary_events','events','RETURN_EVENTS')]:
        check(digest(inputs[field])==pins[ident],code)
    check(digest(inputs['dispatch_program']['policy_program'])==pins['policy_program'],'RETURN_DISPATCH')
    check(type(inputs.get('duration_s')) in (int,float) and inputs['duration_s']==10 and run['summary']['duration_s']==10,'RETURN_HORIZON')
    check(type(inputs.get('maximum_step_s')) in (int,float) and inputs['maximum_step_s']==0.01,'RETURN_STEP')
    check(inputs.get('action_commands',[])==[],'RETURN_COMMANDS')
    check(inputs.get('work_requests')==[],'RETURN_WORK_REQUESTS')
    check(digest(run['business_evaluation']['run_binding'])==digest(inputs['business_program']['run_binding']),'RETURN_BUSINESS')


def execute_case(release,case,jobdir,purpose,substitute=None):
    check((purpose==REAL and substitute is None) or (purpose==SURROGATE and callable(substitute)), 'PURPOSE')
    order=[(case,arm) for arm in ARMS]
    snapshots={}
    def prepare(condition,arm,path):
        call=release.conditions.call(condition,arm)
        check(set(call)=={'scenario','dispatch_program','business_program','boundary_events','duration_s','step_s'},'CALL_SHAPE')
        pins=release.conditions.rows[condition]['arms'][arm]
        check(digest(call)==pins['complete_call'] and call['duration_s']==10 and call['step_s']==0.01,'CALL_IDENTITY')
        cmd=[sys.executable,'-B','-m','aegis_dc','simulate']
        for flag,value in [('model',call['scenario']),('dispatch-program',call['dispatch_program']),
                ('business-program',call['business_program']),('inputs',dict(schema='aegisdc-engineering-inputs-v1',work_requests=[],boundary_events=call['boundary_events']))]:
            filename=path/(flag+'.json')
            write_new(filename,value)
            cmd+=['--'+flag,str(filename)]
        cmd+=['--duration',str(call['duration_s']),'--step',str(call['step_s']),'--output',str(path/'run')]
        actual_python=file_hash(Path(sys.executable).resolve())
        check(actual_python==release.manifest['python']['sha256'],'PYTHON_IDENTITY')
        write_new(path/'execution-binding.json',dict(purpose=purpose,manifest_sha256=release.sha,
            native_source_tree=release.manifest['native_source_tree'],python=release.manifest['python'],
            actual_worker_python_sha256=actual_python,native_argv=cmd))
        if purpose==SURROGATE:
            cmd=substitute(condition,arm,path,cmd)
        return cmd,pins['complete_call']
    def receive(condition,arm,path):
        raw_sha=file_hash(path/'run/run.json')
        run,trace,balances=read_native(path/'run')
        check(file_hash(path/'run/run.json')==raw_sha,'RETURN_CHANGED')
        verify_return(release,condition,arm,run,read(path/'run/scenario.json'))
        pins=release.conditions.rows[condition]['arms'][arm]
        check(read(path/'call.json')['input_sha256']==pins['complete_call'],'CALL_IDENTITY')
        for name,key in [('model','scenario'),('dispatch-program','dispatch'),('business-program','business')]:
            check(digest(read(path/(name+'.json')))==pins[key],'CALL_IDENTITY',name)
        supplied=read(path/'inputs.json')
        check(set(supplied)=={'schema','work_requests','boundary_events'} and supplied['work_requests']==[]
              and supplied['schema']=='aegisdc-engineering-inputs-v1' and digest(supplied['boundary_events'])==pins['events'],'CALL_IDENTITY')
        decisions=run.get('policy_public_decisions')
        work=run.get('work_records')
        valid_decisions=(isinstance(decisions,list) and all(isinstance(d,dict) and isinstance(d.get('frame'),dict)
            and type(d['frame'].get('as_of_s')) in (int,float) and isinstance(d.get('choice'),dict)
            and isinstance(d.get('history'),dict) for d in decisions))
        valid_work=isinstance(work,list) and all(isinstance(w,dict) and isinstance(w.get('id'),str) for w in work)
        receipt=dict(native_sha256=raw_sha,source_tree=run['code_identity']['source_tree_sha256'],
            full_input=pins['complete_call'],internal_policy_calls=len(decisions) if valid_decisions else None,
            manual_issues=len(work) if valid_work else None,trace_records=len(trace),balance_records=len(balances))
        snapshots[arm]=(run,trace,balances)
        write_new(path/'native-return.json',receipt)
        return receipt
    def evaluate(condition,arm,path,returned):
        check(returned['internal_policy_calls']==20 and type(returned['manual_issues']) is int,'ARM_BUDGET')
        limit=0 if arm=='P' else 3*(2 if case=='C17' else 1)
        check(0<=returned['manual_issues']<=limit,'ARM_BUDGET')
        check(file_hash(path/'run/run.json')==returned['native_sha256'],'RETURN_CHANGED')
        scored=score_arm(*snapshots.pop(arm))
        check(scored['internal_policy_calls']==returned['internal_policy_calls'],'ARM_BUDGET')
        scored.update(condition=condition,treatment=arm,native_sha256=returned['native_sha256'],input_sha256=returned['full_input'],
                      native_source=returned['source_tree'])
        write_new(path/'score.json',scored)
        check(not scored['violations'],'HARD_CONSTRAINT')
        if arm=='H':
            v=read(path.parent/(case+'-V')/'score.json')
            check(v['input_sha256']==scored['input_sha256'] and v['semantic_sha256']==scored['semantic_sha256'],'VH_MISMATCH')
    return run_order(jobdir/'arms',order,prepare,receive,on_complete=evaluate)
