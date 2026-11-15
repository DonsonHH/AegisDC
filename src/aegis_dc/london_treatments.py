"""Bounded I/D/P runner. Policies get only treatment and detached v2 views.

The private evaluator owns clocks, models and scoring. A fixed public tick
schedule, not the next private event, determines possible policy invocations.
No research dataset loader, parameter search, effect aggregation or sealed
confirmation entry exists in this module.
"""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import traceback
from .london_e14 import E14Run, decide, PUBLIC_VIEW_SCHEMA
from .london_treatment_score import score_arm

ARMS=('I','D','P');CAPS={'I':5,'D':2,'P':0}
VIEW_KEYS={'view_schema','time','pre_open','pending','terminal_failure','phase','records','receipts','history','attempted','known_epoch','certificate','context'}
CONTEXT_KEYS={'permissions','compatible','window','available','read_reserve','verify_reserve','acquisition_plans','chain_reserve','chain_finish','chain_resource_end','read_parameters_known','chain_parameters_known'}
FORBIDDEN={'condition_id','condition_label','common','tF','tR','next_event','next_private_event','family','ready','exec_fault','approval','commit','verification','guard'}

def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False)
def snapshot(x):return json.loads(canonical(x))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()

def validate_view(view):
    if type(view) is not dict or set(view)!=VIEW_KEYS or view['view_schema']!=PUBLIC_VIEW_SCHEMA:
        raise ValueError('Policy accepts only the exact live public v2 envelope')
    if set(view['context'])!=CONTEXT_KEYS:raise ValueError('Unexpected public context fields')
    def visit(x):
        if isinstance(x,dict):
            if set(x)&FORBIDDEN:raise ValueError('Private condition field in public packet')
            for v in x.values():visit(v)
        elif isinstance(x,list):
            for v in x:visit(v)
    visit(view)

def fix_feasibility(view,mode):
    c=view['context'];p=c['permissions'];roles=['propose','read','verify']+(['direct'] if mode=='DIRECT' else [])
    if not c['chain_parameters_known'] or c['compatible']=='UNKNOWN' or any(p[x]=='UNKNOWN' for x in roles):return 'INSUFFICIENT_INFORMATION'
    if c['compatible']!='ALLOW' or any(p[x]!='ALLOW' for x in roles):return 'INFEASIBLE'
    if Fraction(c['available'])<Fraction(c['chain_reserve']) or Fraction(c['chain_finish'])>=Fraction(c['window'][1]) or Fraction(c['chain_resource_end'])>Fraction(c['window'][1]):return 'INFEASIBLE'
    return None

def choose(treatment,public_view):
    """Public-only fixed treatment rule; no config/model/evaluator argument."""
    if treatment not in ARMS:raise ValueError('Unknown treatment')
    validate_view(public_view)
    def out(action,mode=None,reason=None):return dict(action=action,mode=mode,reason=reason or action)
    if treatment=='P':return out('NO_NEW_ACTIONS')
    base=decide(public_view,'B1')
    if treatment=='I':
        if base['action']=='PROPOSE_FIX':
            blocked=fix_feasibility(public_view,'EVIDENCE')
            if blocked:return out(blocked)
        return base
    if not public_view['pre_open'] or public_view['terminal_failure'] or public_view['pending'] or public_view['phase']=='AWAITING_VERIFY' or base['action']=='NO_ACTION_CURRENT_SCOPE':return base
    if 'FIX_CTRL' in public_view['attempted']:return out('STOP_UNRESOLVED')
    blocked=fix_feasibility(public_view,'DIRECT')
    return out(blocked) if blocked else out('PROPOSE_FIX','DIRECT','PUBLIC_DIRECT_CATALOG')

def make_request(decision,view,index):
    action='FIX_CTRL' if decision['action']=='PROPOSE_FIX' else decision['action']
    if action not in ('READ_POS','READ_VOLT','READ_CONFIG','FIX_CTRL','VERIFY_CTRL'):raise ValueError('Not a request action')
    payload=dict(action=action,request_id='rq-'+str(index),problem_id='q-1',target='feeder-B' if action in ('READ_POS','READ_VOLT') else 'ctrl-1')
    if action=='FIX_CTRL':
        payload['mode']=decision['mode']
        if decision['mode']=='EVIDENCE':payload['evidence_ids']=[r['record_id'] for r in view['records'] if r['status']=='KNOWN' and r['action'] in ('READ_POS','READ_VOLT','READ_CONFIG')]
    if action=='VERIFY_CTRL':
        receipt=next(r for r in reversed(view['receipts']) if r['record_kind']=='EXECUTION_RECEIPT' and r['status']=='EXECUTED_UNVERIFIED')
        payload.update(execution_id=receipt['execution_id'],target_config_epoch=receipt['target_config_epoch'])
    return payload

def reached_stage(audit,run):
    actions=[r['payload']['action'] for r in run['requests']]
    fix='FIX_CTRL' in actions;grant=audit['internal_approval'];commit=audit['commit_result'];verification=audit['verification_result']
    published=[r for r in audit['observations'] if r['action']=='VERIFY_CTRL']
    executions=[r for r in audit['receipts'] if r['record_kind']=='EXECUTION_RECEIPT' and r['status']=='EXECUTED_UNVERIFIED']
    parent=None if not published else all(any(r['parent_execution_id']==e['execution_id'] and r['config_epoch']==e['target_config_epoch'] for e in executions) for r in published)
    visible={r['record_id'] for frame in run['public_trace'] for r in frame['view']['records'] if r['action'].startswith('READ_')}
    prepared=any(s['occupied'] and s['work_action']=='FIX_CTRL' and s['work_stage']=='PREPARING' for s in audit['segments'])
    if run['arm']=='P':stage='BACKGROUND_ONLY'
    elif audit['phase']=='EXITING' and audit['resource_overrun']:stage='EXIT_INCOMPLETE'
    elif verification=='PASS':stage='VERIFIED'
    elif verification=='FAIL':stage='VERIFICATION_FAILED'
    elif verification=='INCONCLUSIVE':stage='VERIFY_INCONCLUSIVE'
    elif verification=='ABORTED':stage='VERIFY_ABORTED'
    elif commit=='FAIL':stage='COMMIT_FAILED'
    elif commit=='SUCCESS':stage='EXECUTED_UNVERIFIED'
    elif grant and grant['decision']=='DENY':stage='APPROVAL_DENIED'
    elif fix:stage='NOT_IMPLEMENTED'
    elif actions:stage='INSPECTION_STOP'
    else:stage='NO_ACTION'
    return dict(stage=stage,fix_requested=fix,approved=bool(grant and grant['decision']=='APPROVE'),preparation_started=prepared,
                commit_result=commit,commit_attempted=commit in ('SUCCESS','FAIL'),verification_requested='VERIFY_CTRL' in actions,
                verification_result=verification,verification_published=bool(published),verification_parent_valid=parent,
                read_results_published=sum(r['action'].startswith('READ_') for r in audit['observations']),read_records_visible_to_policy=len(visible))

def validate_config(config):
    if type(config.get('H')) is not int or config['H']!=20:raise ValueError('Runner v1 has fixed public H=20')
    clocks=['read_work','verify_work','approval_work','publish','prep','commit_work','exit_work','ttl']
    if any(type(config[k]) is not int for k in clocks):raise ValueError('Public recipes require integer-second clock alignment')
    if any(type(t) is not int for t in config['window']) or any(type(t) is not int for row in config['calendar'] for t in row):raise ValueError('Public windows/reservations must align to the public clock')

def run_condition(common,order=('I','D','P')):
    """Private evaluator: one common condition, three independent full runs."""
    calls=[];counts=dict(constructor_attempts=0,plant_entry_calls=0,policy_calls=0,scorer_calls=0)
    records={arm:dict(arm=arm,public_trace=[],requests=[],stop=None,errors=[],final_audit=None,checkpoint_audit=None,last_available_audit=None,score=dict(trace_status='NOT_SCORED',L=None,U=None,hard_constraints_ok=False)) for arm in ARMS}
    result=dict(arms=records,calls=calls,counts=counts,errors=[],initial_public_views={},initial_private_audits={},isolation={})
    frozen_common=deepcopy(common);before_input=canonical(frozen_common)
    def call(kind,arm,name,fn,args,wire_args):
        key={'constructor':'constructor_attempts','plant':'plant_entry_calls','policy':'policy_calls','scorer':'scorer_calls'}[kind]
        counts[key]+=1;row=dict(kind=kind,arm=arm,name=name,arguments=snapshot(wire_args));calls.append(row)
        try:
            value=fn(*args)
            if kind=='constructor':row['actual']={'created':True};return value
            row['actual']=snapshot(value);return snapshot(value)
        except Exception as e:
            row['error']=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc());raise
    def plant(arm,name,*args):
        value=call('plant',arm,name,getattr(models[arm],name),args,dict(args=snapshot(list(args))))
        if name=='audit':
            records[arm]['last_available_audit']=deepcopy(value)
            records[arm]['last_available_audit_call']=len(calls)-1
        return value
    try:
        validate_config(common)
        if len(order)!=3 or set(order)!=set(ARMS):raise ValueError('Order must be a permutation of I/D/P')
        models={}
        for arm in ARMS:models[arm]=call('constructor',arm,'E14Run',E14Run,(deepcopy(frozen_common),),dict(config=frozen_common))
        fields={'model':lambda m:m,'state':lambda m:m._state,'config':lambda m:m.c,'permissions':lambda m:m.c['permissions'],'queue':lambda m:m.queue,'requests':lambda m:m.requests,'observations':lambda m:m.observations,'receipts':lambda m:m.receipts,'segments':lambda m:m.segments}
        ids={name:{arm:id(get(models[arm])) for arm in ARMS} for name,get in fields.items()}
        for arm in ARMS:
            result['initial_public_views'][arm]=plant(arm,'public_view');result['initial_private_audits'][arm]=plant(arm,'audit')
        first_public=result['initial_public_views']['I']
        normalized=[]
        for a in result['initial_private_audits'].values():
            x=deepcopy(a);x.pop('state_identity');normalized.append(x)
        isolation=dict(object_ids=ids,initial_public_equal=all(canonical(v)==canonical(first_public) for v in result['initial_public_views'].values()),initial_private_equal=all(canonical(v)==canonical(normalized[0]) for v in normalized),snapshots=[],all_other_states_unchanged=True,input_unchanged=True)
        result['isolation']=isolation
        for arm in order:
            saved={}
            for other in ARMS:
                if other!=arm:
                    index=len(calls);saved[other]=(index,plant(other,'audit'))
            record=records[arm]
            model=models[arm]
            try:
                for tick in range(21):
                    view=plant(arm,'public_view') if tick==0 else plant(arm,'advance',tick)
                    # The environment owns cutoff; it never calls the strategy
                    # after PRE closes, even if a record arrives in that step.
                    if not view['pre_open']:
                        record['stop']=dict(reason='ENV_PRE_CUTOFF',time=tick);break
                    if tick==20:raise RuntimeError('No legal environment stop at H')
                    validate_view(view)
                    decision=call('policy',arm,'choose',choose,(arm,deepcopy(view)),dict(treatment=arm,public_view=view))
                    frame=dict(time=tick,view=view,decision=decision,payload=None,reply=None);record['public_trace'].append(frame)
                    action=decision['action']
                    if action=='WAIT_PENDING':continue
                    if action in ('NO_ACTION_CURRENT_SCOPE','INSUFFICIENT_INFORMATION','INFEASIBLE','STOP_UNRESOLVED','STOP','NO_NEW_ACTIONS'):
                        record['stop']=dict(reason=action,time=tick);break
                    payload=make_request(decision,view,len(record['requests'])+1)
                    if len(record['requests'])>=CAPS[arm] or payload['action'] in [r['payload']['action'] for r in record['requests']]:raise RuntimeError('Action quota/retry violation')
                    if arm=='D' and payload['action'] not in ('FIX_CTRL','VERIFY_CTRL'):raise RuntimeError('Direct treatment attempted diagnosis')
                    if arm=='P':raise RuntimeError('Protection treatment attempted an operator action')
                    reply=plant(arm,'request',payload);frame.update(payload=payload,reply=reply)
                    record['requests'].append(dict(time=tick,payload=payload,reply=reply,frame_index=len(record['public_trace'])-1))
                    if reply['status']!='ADMITTED':
                        legal={'ACCESS_DENIED','BUDGET_UNAVAILABLE','NOT_STARTED_RESOURCE','WINDOW_UNAVAILABLE','INSUFFICIENT_INFORMATION','PRE_CLOSED'}
                        if reply['status'] not in legal:record['errors'].append('Request contract error: '+reply['status'])
                        record['stop']=dict(reason='REQUEST_REJECTED',time=tick,request_status=reply['status']);break
                if record['stop'] is None:raise RuntimeError('Strategy did not stop')
            except Exception as e:
                record['errors'].append(dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
                record['stop']=dict(reason='RUNNER_ERROR',time=model.time.numerator if model.time.denominator==1 else str(model.time))
            # Evaluation continues without any strategy invocation or response
            # action: original protection, recovery and safe exit remain active.
            record['requested_actions']=[r['payload']['action'] for r in record['requests']]
            record['request_times']=[r['time'] for r in record['requests']];record['policy_times']=[f['time'] for f in record['public_trace']]
            def failure(phase,error):
                record['errors'].append(dict(phase=phase,type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
            try:record['checkpoint_audit']=plant(arm,'audit')
            except Exception as e:failure('STOP_CHECKPOINT',e)
            try:
                if model.time<20:plant(arm,'advance',20)
            except Exception as e:failure('FINAL_ADVANCE',e)
            try:
                record['final_audit']=plant(arm,'audit')
                record['final_audit_status']='COMPLETE' if record['final_audit']['time']==20 else 'PARTIAL_AFTER_ERROR'
            except Exception as e:
                failure('FINAL_AUDIT',e);record['final_audit_status']='MISSING_AFTER_ERROR'
            stage_audit=record['final_audit'] or record['last_available_audit']
            try:
                record['reached']=reached_stage(stage_audit,record)
                record['reached_basis']=dict(kind='FINAL_AUDIT' if record['final_audit'] is not None else 'CHECKPOINT_ONLY',time=stage_audit['time'])
            except Exception as e:failure('STAGE_EXTRACTION',e);record['reached']=dict(stage='UNKNOWN_AFTER_ERROR')
            if record['errors']:result['errors'].append(dict(arm=arm,errors=deepcopy(record['errors'])))
            for other,(before_index,before) in saved.items():
                after_index=len(calls);after=plant(other,'audit')
                isolation['snapshots'].append(dict(running_arm=arm,other=other,before_call=before_index,after_call=after_index))
                isolation['all_other_states_unchanged'] &= canonical(before)==canonical(after)
        isolation['input_unchanged']=canonical(common)==before_input and all(canonical((r['final_audit'] or r['last_available_audit'])['original_input'])==before_input for r in result['arms'].values())
        isolated=all(len(set(x.values()))==3 for x in ids.values()) and all(isolation[k] for k in ['initial_public_equal','initial_private_equal','all_other_states_unchanged','input_unchanged'])
        # Scoring is deliberately after *all* policy runs; no preceding arm's
        # score can enter another arm's policy input or closure.
        for arm in ARMS:
            r=result['arms'][arm]
            if r['final_audit'] is None:
                r['score']=dict(trace_status='UNSCORED_AFTER_AUDIT_ERROR',L=None,U=None,hard_constraints_ok=False)
                continue
            try:
                r['score']=call('scorer',arm,'score_arm',score_arm,(deepcopy(r['final_audit']),deepcopy(r),isolated,deepcopy(frozen_common)),dict(audit=r['final_audit'],run=deepcopy(r),isolation_ok=isolated,frozen_input=frozen_common))
            except Exception as e:
                r['errors'].append(dict(phase='SCORING',type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
                result['errors'].append(dict(arm=arm,errors=deepcopy(r['errors'])))
                r['score']=dict(trace_status='UNSCORED_AFTER_SCORER_ERROR',L=None,U=None,hard_constraints_ok=False)
        result['common_input_sha256']=digest(common);result['execution_order']=list(order)
    except Exception as e:result['errors'].append(dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
    return snapshot(result)
