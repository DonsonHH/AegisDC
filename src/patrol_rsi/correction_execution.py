"""Adapt only selection; the archived physical execution and safety kernel stay intact."""
from copy import deepcopy
from dataclasses import asdict,is_dataclass
import math
import numpy as np

from .baseline_correction import Rule,rule_from_dict,relative_features,choose_advantage,advantage
from .local_score import ScoreExpression,BASE_EXPRESSION
from .reorder_execution import public_tasks,features_for,lower,run_reorder
from .contracts import digest


def native(x):
    if isinstance(x,np.ndarray):return {'dtype':str(x.dtype),'shape':list(x.shape),'values':native(x.tolist())}
    if isinstance(x,np.generic):return native(x.item())
    if type(x) is float and not math.isfinite(x):return {'nonfinite_sentinel':str(x)}
    if x is None or type(x) in (str,int,float,bool):return x
    if isinstance(x,dict):return {str(k):native(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [native(v) for v in x]
    if isinstance(x,set):return sorted(native(v) for v in x)
    if is_dataclass(x):return native(asdict(x))
    if hasattr(x,'__dict__'):return native(vars(x))
    raise TypeError('Unregistered state serialization: '+type(x).__name__)


STATE_EXCLUDED={
    'graph':'fixed geometry SHA','trace':'fixed plant fingerprint; future plant not policy state',
    'predictor':'fixed model SHA; deterministic stateless inference',
    'plans':'immutable original planner geometry/tours','local_checks':'immutable planner geometry/tours',
    'inference_seconds':'wall-clock performance only',
    'local_decisions':'audit log only','local_dispatches':'audit log only','obligation_events':'audit log only',
    'root_candidates':'root audit only','correction_actions':'prefix audit only',
    'intervention_verified':'paired audit only'}


def state_snapshot(env):
    return native({k:v for k,v in vars(env).items() if k not in STATE_EXCLUDED})


def evidence(env):
    rows=public_tasks(env);now=float(env.clock)
    thermal={j:row for j,row in rows.items() if row['kind']=='thermal'}
    def thermal_source(row):
        source=row['risk_value_source'];stamp=row['value_output_time_s']
        group='model' if source=='frozen_CVAE_mean' else 'direct' if source=='direct_assimilated_temperature' else 'unknown'
        if stamp is None:group='unknown'
        return group,stamp,source
    for j,row in rows.items():
        task=env.tasks[j];pod=task.index//8 if task.kind=='thermal' else task.index
        components=[]
        for name,value in row['risk_components'].items():
            contributors=[];group='unknown';stamp=None;source='missing_initial_nominal'
            if name=='thermal_excess':group,stamp,source=thermal_source(row)
            elif name in ('flow_deficit','contact_heat','verified_bias_or_initial_zero'):
                if row['direct_available']:group='direct';stamp=row['direct_time_s'];source=row['source']
            elif name in ('public_power_gap_scaled','public_pod_power_gap'):
                group='power';stamp=float(env.current_packet['time_s']);source='public_IT_supply_demand'
                contributors=[{'rack':int(task.index)}] if task.kind=='thermal' else [{'rack':k} for k in range(pod*8,pod*8+8)]
            elif name=='same_branch_thermal_scaled':
                branch=[thermal[k] for k in range(pod*8,pod*8+8)]
                peak=max(r['risk_components']['thermal_excess'] for r in branch)
                selected=[r for r in branch if abs(r['risk_components']['thermal_excess']-peak)<=1e-12]
                origins=[thermal_source(r) for r in selected]
                contributors=[{'rack':r['task'],'group':g,'time_s':s,'source':src} for r,(g,s,src) in zip(selected,origins)]
                if all(g!='unknown' and s is not None for g,s,_ in origins):
                    group='cross';stamp=min(s for _,s,_ in origins);source='same_pod_thermal_max'
            if stamp is not None and not 0<=stamp<=now:raise ValueError('Future/invalid evidence timestamp')
            components.append({'name':name,'group':group,'value':float(value) if group!='unknown' else None,
                'time_s':stamp,'age_s':now-stamp if stamp is not None else None,'source':source,
                'contributors':contributors,'missing_reason':'No valid measured/model provenance' if group=='unknown' else None})
        row['evidence_components']=components
    return rows


def correction_selector(env,policy,intervention):
    if not hasattr(env,'root_candidates'):env.root_candidates={};env.correction_actions=[]
    choices={};snapshot=None;pre_state=None
    if any(a['task'] is None and not ledger.committed for a,ledger in zip(env.agents,env.ledgers)):
        snapshot=evidence(env)
        if policy['kind']=='T' and len(env.root_candidates)<2 or intervention is not None and env.clock==intervention['time_s']:
            pre_state=state_snapshot(env)
    for i,agent in enumerate(env.agents):
        if agent['task'] is not None:continue
        ledger=env.ledgers[i]
        if not ledger.committed:
            if snapshot is None:snapshot=evidence(env)
            candidates=env.local_checks[i].candidates(env.clock,agent['position'],env.last_inspection,ledger.remaining,env.reserved())
            original=next(c for c in candidates if c['original']);legal=[c for c in candidates if c['certificate']['ok']]
            if not original['certificate']['ok']:raise ValueError('Original safe continuation unavailable')
            for c in legal:c['features']=features_for(c['certificate'],snapshot,ledger.tour,env.clock)
            legal.sort(key=lambda c:(not c['original'],c['order']))
            # pre_state was captured before ANY free inspector committed.
            if policy['kind']=='T' and len(legal)>1:
                category='positive' if any(snapshot[j]['risk']>0 for j in ledger.tour) else 'zero'
                if category not in env.root_candidates:
                    rbest=legal[0];expr=ScoreExpression(BASE_EXPRESSION)
                    for c in legal[1:]:
                        if expr.evaluate(c['features'])<expr.evaluate(rbest['features'])-1e-9:rbest=c
                    if rbest['original']:
                        rbest=next(c for c in legal if not c['original'])
                        for c in legal:
                            if not c['original'] and expr.evaluate(c['features'])<expr.evaluate(rbest['features'])-1e-9:rbest=c
                    env.root_candidates[category]={'time_s':float(env.clock),'agent':i,'round_id':ledger.round_id,
                        'window':ledger.window(),'alternative_order':rbest['order'],'candidate_pool':deepcopy(candidates),
                        'public_tasks':[deepcopy(snapshot[j]) for j in ledger.tour],
                        'state_sha256':digest(pre_state),'state_snapshot':deepcopy(pre_state),
                        'prefix_action_sha256':digest(env.correction_actions),'prefix_actions':deepcopy(env.correction_actions),
                        'state_exclusions':STATE_EXCLUDED,'root_risk_class':category}
            selected=original;error=None
            rule=rule_from_dict(policy['rule']) if policy['kind']=='correction' else Rule()
            try:
                for c in legal:
                    c['correction']=relative_features(original['certificate'],c['certificate'],snapshot,ledger.tour,env.clock,rule)
                    g,a=advantage(c['correction'],rule);c['gain']=g;c['advantage']=a
                    c['score']=[ScoreExpression(BASE_EXPRESSION).evaluate(c['features'])]
                if policy['kind']=='R':
                    for c in legal[1:]:
                        if lower(c['score'],selected['score']):selected=c
                elif policy['kind']=='correction':selected=choose_advantage(legal,rule)
            except ValueError as exc:
                error=str(exc);env.numeric_failures.append({'time_s':float(env.clock),'agent':i,'error':error});selected=original
            if intervention is not None and env.clock==intervention['time_s'] and i==intervention['agent']:
                if ledger.round_id!=intervention['round_id'] or ledger.window()!=intervention['window']:raise ValueError('Intervention root ledger mismatch')
                if digest(pre_state)!=intervention['state_sha256'] or digest(env.correction_actions)!=intervention['prefix_action_sha256']:raise ValueError('Real identical state/prefix required')
                selected=next(c for c in legal if c['order']==intervention['execute_order'])
                env.intervention_verified={'state_sha256':digest(pre_state),'prefix_action_sha256':digest(env.correction_actions),
                    'state_snapshot':deepcopy(pre_state),'prefix_steps':len(env.correction_actions),'executed_order':selected['order']}
            first=original['certificate']['first_completion_s'];actual=selected['certificate']['first_completion_s']
            env.local_decisions.append({'time_s':float(env.clock),'agent':i,'round_id':ledger.round_id,
                'remaining_before':list(ledger.remaining),'window':ledger.window(),'candidates':candidates,
                'selected_order':list(selected['order']),'selected_original':selected['original'],
                'legal_permutations':len(legal),'legal_nonoriginal':sum(not c['original'] for c in legal),
                'public_tasks':[deepcopy(snapshot[j]) for j in ledger.tour],
                'completion_deltas_vs_original':[{'task':j,'target_round':ledger.round_id+(j not in ledger.remaining),
                    'delta_completion_s':float(actual[j]-first[j])} for j in ledger.tour],'numeric_error':error})
            ledger.commit(selected['order'])
        ids,_,_=env.options(i,env.reserved());choices[i]=int(ids[0]) if len(ids) else None
    env.correction_actions.append({'time_s':float(env.clock),'choices':{str(i):j for i,j in choices.items()}})
    return choices


def execute_correction(spec,predictor,policy,intervention=None):
    record,env=run_reorder(spec,predictor,{'method':'T'},
        selector=lambda env,*_:correction_selector(env,policy,intervention))
    record['policy']=deepcopy(policy)
    record['root_candidates']=env.root_candidates if policy['kind']=='T' and intervention is None else {}
    record['intervention_verified']=getattr(env,'intervention_verified',None)
    if intervention is not None and record['intervention_verified'] is None:raise ValueError('Frozen intervention not executed')
    if record['action_log']!=env.correction_actions:raise ValueError('Prefix action logging differs from actual actions')
    return record,env
