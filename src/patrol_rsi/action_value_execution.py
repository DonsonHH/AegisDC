"""Tour-only collection and one frozen local intervention; no online learned policy."""
from copy import deepcopy
import json
import zlib
from unittest.mock import patch
import numpy as np

from .correction_execution import evidence,native,STATE_EXCLUDED
from .baseline_correction import Rule,relative_features,choose_advantage,advantage
from .local_score import ScoreExpression,BASE_EXPRESSION
from .reorder_execution import run_reorder,features_for,lower
from .action_value_features import features,public_discrimination,ROW_KEYS
from .multistep_workflow import digest

EXCLUDED=set(STATE_EXCLUDED)|{'av_sampler','av_actions','av_intervention_verified'}


def full_state(env):return native({k:v for k,v in vars(env).items() if k not in EXCLUDED})


def feature_view(snapshot):return {j:{k:row[k] for k in ROW_KEYS} for j,row in snapshot.items()}


def public_snapshot(env):
    snapshot=evidence(env)
    for j,row in snapshot.items():
        task=env.tasks[j];indices=[task.index] if task.kind=='thermal' else list(range(task.index*8,task.index*8+8))
        row['nominal_temperature_c']=float(np.mean(env.state.observer.predicted_temperature[indices]))
        row['raw_cvae_temperature_c']=float(np.mean(env.av_raw_cvae[indices])) if env.av_raw_cvae is not None else None
        row['raw_cvae_time_s']=env.av_raw_cvae_time_s
    return snapshot


class RootSampler:
    def __init__(self):self.first_a=None;self.best_b=[];self.maximum=-float('inf')

    def consider(self,view,state_factory,prefix):
        if view['legal_nonoriginal']==0:return
        a=self.first_a is None and (view['shadow_H']!=view['window'] or view['shadow_R']!=view['window'])
        d=view['discrimination']
        if d>self.maximum:
            self.maximum=d;self.best_b=[r for r in self.best_b if r['discrimination']>=self.maximum-1e-9]
        b=d>1e-9 and d>=self.maximum-1e-9
        if not a and not b:return
        value=deepcopy(view);snapshot=state_factory();value['state_sha256']=digest(snapshot)
        value['_compressed_state']=zlib.compress(json.dumps(snapshot,separators=(',',':'),allow_nan=False).encode())
        value['prefix_action_sha256']=digest(prefix);value['prefix_steps']=len(prefix)
        value['state_excluded']={**STATE_EXCLUDED,**{k:'Action-value audit only' for k in EXCLUDED-set(STATE_EXCLUDED)}}
        if a:self.first_a=value
        if b:self.best_b.append(value)

    def selected(self):
        out=[]
        def expand(value,kind):
            copy={k:deepcopy(v) for k,v in value.items() if k!='_compressed_state'}
            copy.update(root_type=kind,state_snapshot=json.loads(zlib.decompress(value['_compressed_state'])))
            return copy
        if self.first_a is not None:out.append(expand(self.first_a,'A'))
        other=next((v for v in sorted(self.best_b,key=lambda v:(v['time_s'],v['agent'])) if self.first_a is None or (v['time_s'],v['agent'])!=(self.first_a['time_s'],self.first_a['agent'])),None)
        if other is not None:out.append(expand(other,'B'))
        return out


def select(env,holder,collect,intervention):
    holder['env']=env
    if not hasattr(env,'av_sampler'):
        env.av_sampler=RootSampler();env.av_actions=[];env.av_raw_cvae=None;env.av_raw_cvae_time_s=None
    snapshot=None;views={}
    for i,agent in enumerate(env.agents):
        if agent['task'] is not None or env.ledgers[i].committed:continue
        if snapshot is None:snapshot=public_snapshot(env)
        ledger=env.ledgers[i];pool=env.local_checks[i].candidates(env.clock,agent['position'],env.last_inspection,ledger.remaining,env.reserved())
        original=next(c for c in pool if c['original']);legal=sorted([c for c in pool if c['certificate']['ok']],key=lambda c:(not c['original'],c['order']))
        if not original['certificate']['ok']:raise ValueError('Original continuation infeasible')
        own={j:snapshot[j] for j in ledger.tour};rows=feature_view(own);rbest=legal[0];expr=ScoreExpression(BASE_EXPRESSION)
        for c in legal:
            c['features']=features_for(c['certificate'],snapshot,ledger.tour,env.clock)
            c['score']=[expr.evaluate(c['features'])]
            c['correction']=relative_features(original['certificate'],c['certificate'],snapshot,ledger.tour,env.clock,Rule())
            g,a=advantage(c['correction'],Rule());c['gain']=g;c['advantage']=a
            c['h_preference']=a if g>1e-9 and a>1e-9 else 0.
            c['action_value_features']=features(rows,original['certificate'],c['certificate'],env.clock).tolist()
            if lower(c['score'],rbest['score']):rbest=c
        hbest=choose_advantage(legal,Rule())
        views[i]={'time_s':float(env.clock),'agent':i,'round_id':ledger.round_id,'remaining_before':list(ledger.remaining),
            'window':ledger.window(),'candidates':pool,'legal_permutations':len(legal),
            'legal_nonoriginal':sum(not c['original'] for c in legal),'shadow_H':hbest['order'],'shadow_R':rbest['order'],
            'discrimination':public_discrimination(rows,original['certificate'],legal),
            'public_tasks':list(own.values()),'feature_rows':rows}
    pre=None
    def state():
        nonlocal pre
        if pre is None:pre=full_state(env)
        return deepcopy(pre)
    # Entire candidate views and root snapshots precede all same-tick commits.
    if collect:
        for view in views.values():env.av_sampler.consider(view,state,env.av_actions)
    if intervention is not None and env.clock==intervention['time_s']:
        i=intervention['agent'];v=views.get(i)
        if v is None or v['round_id']!=intervention['round_id'] or v['window']!=intervention['window']:raise ValueError('Frozen branch root ledger')
        if digest(state())!=intervention['state_sha256'] or digest(env.av_actions)!=intervention['prefix_action_sha256']:raise ValueError('Branch complete prefix/state mismatch')
        env.av_intervention_verified={'state_sha256':digest(state()),'state_snapshot':state(),
            'prefix_action_sha256':digest(env.av_actions),'prefix_steps':len(env.av_actions),'executed_order':intervention['execute_order']}
    choices={}
    for i,agent in enumerate(env.agents):
        if agent['task'] is not None:continue
        ledger=env.ledgers[i]
        if i in views:
            v=views[i];original=next(c for c in v['candidates'] if c['original']);selected=original
            if intervention is not None and env.clock==intervention['time_s'] and i==intervention['agent']:
                selected=next(c for c in v['candidates'] if c['certificate']['ok'] and c['order']==intervention['execute_order'])
            first=original['certificate']['first_completion_s'];actual=selected['certificate']['first_completion_s']
            env.local_decisions.append({**v,'selected_order':selected['order'],'selected_original':selected['original'],
                'completion_deltas_vs_original':[{'task':j,'delta_completion_s':float(actual[j]-first[j]),
                    'target_round':ledger.round_id+(j not in ledger.remaining)} for j in ledger.tour],'numeric_error':None})
            ledger.commit(selected['order'])
        ids,_,_=env.options(i,env.reserved());choices[i]=int(ids[0]) if len(ids) else None
    env.av_actions.append({'time_s':float(env.clock),'choices':{str(i):j for i,j in choices.items()}})
    return choices


def execute(spec,predictor,collect,intervention=None):
    holder={};calls=[]
    def recorded_predictor(context):
        out=predictor(context);env=holder.get('env')
        if env is None:raise ValueError('Unexpected pre-selector CVAE call')
        env.av_raw_cvae=np.asarray(out,dtype=float).copy();env.av_raw_cvae_time_s=float(env.clock)
        calls.append(env.clock);return out
    with patch('patrol_rsi.reorder_execution.choose_local',side_effect=lambda env,*_:select(env,holder,collect,intervention)):
        record,env=run_reorder(spec,recorded_predictor,{'method':'T'})
    if len(calls)!=env.estimator_calls or len(calls)!=60:raise ValueError('Exactly original CVAE call schedule')
    record['action_value_roots']=env.av_sampler.selected() if collect else []
    record['intervention_verified']=getattr(env,'av_intervention_verified',None)
    record['raw_cvae_call_times']=calls
    if intervention is not None and record['intervention_verified'] is None:raise ValueError('Frozen intervention not executed')
    if record['action_log']!=env.av_actions:raise ValueError('Actual prefix logging')
    return record,env
