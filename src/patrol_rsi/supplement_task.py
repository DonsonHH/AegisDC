"""Matched-observation benchmark adapter; historical study modules stay frozen."""
from collections import Counter, deque
import math
import time

import numpy as np

from .active_inspection import ActiveInspection, CANDIDATE_FEATURES
from .contracts import DeniedOnlineTrace, digest
from .coverage_plan import exact_task_gaps
from .inspection_metrics import evaluate_episode
from .patrol_task import FixedPatrolTask
from .risk_response import ResponseChecker, ResponseTask, RiskEpisodes

BENCHMARK_FEATURES=CANDIDATE_FEATURES+('event_wait_ratio','routine_head','pending_event','remaining_extra_fraction','return_min_slack_ratio')
RACK_ROWS=np.asarray([(r//8//4)*2+(r%8)//4 for r in range(128)])
RACK_COLUMNS=np.asarray([((r//8)%4)*4+r%4 for r in range(128)])

def to_grid(values):
    """Place the 128 rack values at the declared 8x16 discrete device grid."""
    values=np.asarray(values)
    if values.shape[0]!=128:raise ValueError('Benchmark grid requires128 racks')
    grid=np.empty((8,16,*values.shape[1:]),dtype=values.dtype)
    grid[RACK_ROWS,RACK_COLUMNS]=values
    return grid


def from_grid(values):
    values=np.asarray(values)
    if values.shape[:2]!=(8,16):raise ValueError('Expected8x16 device grid')
    return values[RACK_ROWS,RACK_COLUMNS].copy()


class SupplementTask(ResponseTask):
    """One shared legal candidate builder for Tour/FIFO/Greedy/shared PPO."""
    def __init__(self,spec,method='fifo',predictor=None,collect_context=False):
        if method not in ('tour','fifo','greedy','ppo'):raise ValueError('Unknown benchmark scheduler')
        self.method=method
        self.context=deque(maxlen=4)
        self.collect_context=collect_context
        self.latest_timing={}
        self.latest_input=None
        self.last_samples=[]
        self.last_logprob=self.last_entropy=0.
        self._validating=False
        self._approved={};self._chosen={}
        self._unconsumed_plan=False
        self.choice_opportunities=0
        internal=dict(spec,estimator='history' if predictor is not None else 'nominal')
        # ResponseTask's old constructor always passes predictor=None. Its
        # unchanged execution/episode lifecycle is reused below, not its init.
        FixedPatrolTask.__init__(self,internal,predictor=predictor)
        self.response_rule=None;self.priority='fifo'
        self.extra_visit_budget=12;self.extra_dispatched=0
        self.risk_source_for_target=np.arange(len(self.tasks))
        self.enable_events=method!='tour'
        self.cursor=[0]*len(self.agents)
        self.checkers=[ResponseChecker(self,a) for a in self.agents]
        self.risk_episodes=RiskEpisodes(len(self.tasks),120.)
        self.dispatches=[];self.pending_dispatch={};self.decisions=[];self.binary_decisions=[]
        self.observe_response_risk()

    def _update(self,completed):
        start=time.perf_counter()
        self._risk_cache=None
        self.current_packet=self.packet()
        packet_end=time.perf_counter()
        self.observation=self.state.update(self.current_packet,completed)
        nominal=self.state.observer.predicted_temperature.copy()
        nominal_end=time.perf_counter()
        prep_ms=0.
        if self.predictor is not None or self.collect_context:
            self.context.append(self.state.features(self.current_packet).copy())
            history=[self.context[0]]*(4-len(self.context))+list(self.context)
            context=np.concatenate(history,axis=-1)
            values=np.concatenate((context,((nominal-50)/20)[:,None]),axis=-1)
            self.latest_input=np.transpose(to_grid(values),(2,0,1)).astype(np.float32)
            prep_ms=(time.perf_counter()-nominal_end)*1000
        neural_ms=None
        correction_ms=0.
        if self.predictor is not None:
            begin=time.perf_counter()
            prediction=np.asarray(self.predictor(self.latest_input,nominal),dtype=float)
            neural_ms=(time.perf_counter()-begin)*1000
            if prediction.shape!=(128,) or not np.isfinite(prediction).all():raise ValueError('Invalid benchmark temperature estimate')
            self.inference_seconds+=neural_ms/1000;self.estimator_calls+=1
            correction_start=time.perf_counter()
            self.current_history=prediction.copy()
            fresh=self.state.observer.temperature_stamp==self.clock
            self.current_history[fresh]=self.state.observer.last_temperature[fresh]
            correction_ms=(time.perf_counter()-correction_start)*1000
        else:self.current_history=nominal
        packet_ms=(packet_end-start)*1000;nominal_ms=(nominal_end-packet_end)*1000
        self.latest_timing={'estimator_total_ms':packet_ms+nominal_ms+(prep_ms+(neural_ms or 0)+correction_ms if self.predictor is not None else 0),
            'public_packet_ms':packet_ms,'nominal_update_ms':nominal_ms,'neural_input_ms':prep_ms if self.predictor is not None else None,
            'logger_context_ms':prep_ms if self.predictor is None and self.collect_context else None,
            'neural_predict_ms':neural_ms,'fresh_correction_ms':correction_ms,
            'instrumented_update_ms':(time.perf_counter()-start)*1000}

    def candidate_rows(self,i,reserved,planned_extras=0):
        agent=self.agents[i];head=agent['tour'][self.cursor[i]]
        targets=[head]
        if self.enable_events:targets+=sorted(j for j in self.risk_episodes.pending if j in agent['allowed'] and j!=head)
        risks=self.response_risk();rows=[]
        for task in targets:
            certificate=self.checkers[i].check(self.clock,agent['position'],self.last_inspection,self.cursor[i],task,reserved)
            event=self.risk_episodes.pending.get(task)
            rows.append({'task':task,'certificate':certificate,'public_risk':float(risks[task]),
                         'event_id':event['event_id'] if event is not None else None,
                         'visible_s':event['visible_s'] if event is not None else None,
                         'budget_allowed':task==head or self.extra_dispatched+planned_extras<self.extra_visit_budget})
        return rows

    def public_candidate_features(self,i,rows,reserved,planned_extras=0):
        ids,features,_=ActiveInspection.options(self,i,reserved,guard=False)
        positions={int(task):position for position,task in enumerate(ids)}
        if any(row['task'] not in positions for row in rows):raise RuntimeError('Certified candidate missing public features')
        if not rows:return np.empty((0,len(BENCHMARK_FEATURES)),dtype=np.float32)
        head=self.agents[i]['tour'][self.cursor[i]]
        remaining=max(0,self.extra_visit_budget-self.extra_dispatched-planned_extras)/max(1,self.extra_visit_budget)
        return np.asarray([np.r_[features[positions[row['task']]],
            0. if row['visible_s'] is None else (self.clock-row['visible_s'])/120.,
            float(row['task']==head),float(row['event_id'] is not None),remaining,
            min(4.,row['certificate']['minimum_projected_slack_s']/600.)] for row in rows],dtype=np.float32)

    def value_features(self):
        base=ActiveInspection.value_features(self)
        remaining=max(0,self.extra_visit_budget-self.extra_dispatched)/max(1,self.extra_visit_budget)
        return np.r_[base,remaining,len(self.risk_episodes.pending)/len(self.tasks)].astype(np.float32)

    def options(self,i,reserved,guard=False):
        if self._validating:
            rows,features=self._approved[i]
        else:
            rows=[r for r in self.candidate_rows(i,reserved) if r['certificate']['ok'] and r['budget_allowed']]
            features=self.public_candidate_features(i,rows,reserved)
        return np.asarray([r['task'] for r in rows],dtype=int),features,np.ones(len(rows),dtype=bool)

    def choose(self,policy=None,stochastic=False):
        if self._unconsumed_plan:raise RuntimeError('Previous certified plan must be executed before choosing again')
        if self.method=='ppo' and policy is None:raise ValueError('PPO benchmark requires an actual frozen/training policy')
        choices={};reserved=self.reserved();planned=0
        self._approved={};self.last_samples=[];self.last_logprob=self.last_entropy=0.
        for i,agent in enumerate(self.agents):
            if agent['task'] is not None:continue
            head=agent['tour'][self.cursor[i]]
            candidates=self.candidate_rows(i,reserved,planned)
            legal=[r for r in candidates if r['certificate']['ok'] and r['budget_allowed']]
            features=self.public_candidate_features(i,legal,reserved,planned)
            self._approved[i]=(legal,features.copy())
            events=[r for r in legal if r['event_id'] is not None]
            routine=next((r for r in legal if r['task']==head),None)
            selected=None
            if len(legal)>1:self.choice_opportunities+=1
            if self.method=='ppo' and legal:
                import torch
                with torch.inference_mode():
                    distribution=policy.distribution(torch.as_tensor(features),torch.ones(len(legal),dtype=torch.bool))
                    action=distribution.sample() if stochastic else distribution.logits.argmax()
                    selected=legal[int(action)]
                    self.last_logprob+=float(distribution.log_prob(action));self.last_entropy+=float(distribution.entropy())
                self.last_samples.append({'features':features.copy(),'mask':np.ones(len(legal),dtype=bool),'action':int(action)})
            elif self.method=='tour':selected=routine
            elif self.method=='greedy' and legal:
                selected=min(legal,key=lambda r:(-r['public_risk']/max(5.,r['certificate']['candidate_finish_s']-self.clock),r['task']!=head,
                    r['visible_s'] if r['visible_s'] is not None else math.inf,r['task']))
            elif events:selected=min(events,key=lambda r:(r['visible_s'],-r['public_risk'],r['task']))
            else:selected=routine
            task=selected['task'] if selected is not None else None;choices[i]=task
            self.decisions.append({'time_s':self.clock,'agent':i,'routine_head':head,'selected':task,'candidates':candidates})
            if task is not None:
                planned+=int(task!=head)
                dispatch={'time_s':self.clock,'agent':i,'task':task,'routine_head':head,'extra_event_visit':task!=head,
                          'event_id':selected['event_id'],'certificate':selected['certificate']}
                self.pending_dispatch[i]=dispatch;self.dispatches.append(dispatch);reserved.add(task)
        self._chosen=dict(choices)
        self._unconsumed_plan=True
        return choices

    def step(self,choices):
        if not self._unconsumed_plan or choices!=self._chosen:raise ValueError('Execution must use the committed certified benchmark choices')
        self._validating=True
        try:
            reward=ResponseTask.step(self,choices)
            self._unconsumed_plan=False
            return reward
        finally:self._validating=False


def safety_audit(env):
    """Audit actual assignments and intervals instead of trusting constant flags."""
    active=[];invalid=duplicates=0;assignment_mismatch=0;agent_overlap=0
    assignments={(a['time_s'],a['agent'],a['task']):a for a in env.assignments}
    for dispatch in env.dispatches:
        now=dispatch['time_s'];active=[r for r in active if r[1]>now+1e-9]
        agent=env.agents[dispatch['agent']];task=env.tasks[dispatch['task']];cert=dispatch['certificate']
        invalid+=int(dispatch['task'] not in agent['tour'] or agent['role']!=task.required_role or not cert['ok'])
        duplicates+=int(any(row[0]==dispatch['task'] for row in active))
        agent_overlap+=int(any(row[2]==dispatch['agent'] for row in active))
        invalid+=int(cert['candidate_finish_s']>1800+1e-9 or cert['candidate_finish_s']>cert['candidate_due_s']+1e-9 or any(a>b+1e-9 for a,b in zip(cert['fallback_completion_s'],cert['fallback_due_s'])))
        assignment=assignments.get((now,dispatch['agent'],dispatch['task']))
        assignment_mismatch+=int(assignment is None or assignment['service_s']!=task.service_s)
        if assignment is not None:
            distance=env.graph.path(tuple(assignment['source']),task.position_m)[0]
            assignment_mismatch+=int(abs(distance-assignment['distance_m'])>1e-8 or tuple(assignment['target'])!=task.position_m or
                cert['candidate_finish_s']!=now+math.ceil((distance+task.service_s)/5-1e-10)*5)
        active.append((dispatch['task'],cert['candidate_finish_s'],dispatch['agent']))
    completions=Counter((e['agent'],e['task'],e['time_s']) for e in env.events)
    expected=Counter((d['agent'],d['task'],d['certificate']['candidate_finish_s']) for d in env.dispatches)
    invalid+=sum((expected-completions).values())+sum((completions-expected).values())
    actual_assignments=Counter((a['time_s'],a['agent'],a['task']) for a in env.assignments)
    expected_assignments=Counter((d['time_s'],d['agent'],d['task']) for d in env.dispatches)
    assignment_mismatch+=sum((actual_assignments-expected_assignments).values())+sum((expected_assignments-actual_assignments).values())
    for event in env.events:
        task=env.tasks[event['task']]
        invalid+=int(not event['calibrated'] or event['role']!=task.required_role or event['access']!=task.access or not 0<event['time_s']<=1800)
    invalid+=agent_overlap+assignment_mismatch
    maxima,gaps=exact_task_gaps(env.tasks,env.events)
    budget=sum(d['extra_event_visit'] for d in env.dispatches)
    result={'invalid_assignments_audited':invalid,'duplicate_reservations_audited':duplicates,
            'revisit_violations_audited':int((maxima>env.deadlines+1e-9).sum()),
            'extra_dispatches_audited':budget,'budget_violations_audited':int(budget>env.extra_visit_budget),
            'assignment_mismatches_audited':assignment_mismatch,'agent_overlap_audited':agent_overlap}
    if any(result[k] for k in result if k.endswith('violations_audited') or k in ('invalid_assignments_audited','duplicate_reservations_audited')):
        raise RuntimeError('Benchmark safety audit failed: '+str(result))
    return result,gaps


def run_episode(spec,method='fifo',predictor=None,policy=None,stochastic=False,collect_training=False):
    env=SupplementTask(spec,method,predictor,collect_context=collect_training)
    temperature=[];truth=[];fresh=[];inputs=[];timing=[];actions=[];rollout=[]
    def capture():
        temperature.append(env.current_history.copy())
        truth.append(env.trace.arrays['rack_temperature_c'][env.tick].copy())
        fresh.append(env.state.observer.temperature_stamp==env.clock)
        timing.append(dict(env.latest_timing))
        if collect_training:inputs.append(env.latest_input.copy())
    capture()
    while not env.done:
        trace=env.trace;env.trace=DeniedOnlineTrace()
        start=time.perf_counter()
        try:
            public=env.value_features().copy()
            if policy is not None and stochastic:
                import torch
                with torch.inference_mode():value=float(policy.values(torch.as_tensor(public)))
            else:value=0.
            choices=env.choose(policy,stochastic)
        finally:env.trace=trace
        policy_ms=(time.perf_counter()-start)*1000
        actions.append({'time_s':float(env.clock),'choices':{str(i):j for i,j in choices.items()}})
        samples=env.last_samples;logprob=env.last_logprob;entropy=env.last_entropy
        step_start=time.perf_counter()
        reward=env.step(choices)
        step_ms=(time.perf_counter()-step_start)*1000
        if policy is not None and stochastic:rollout.append({'public_value':public,'value':value,'reward':reward,'samples':samples,'logprob':logprob,'entropy':entropy})
        timing[-1]['policy_total_ms']=policy_ms
        timing[-1]['instrumented_execution_step_ms']=step_ms
        timing[-1]['online_control_cycle_ms']=policy_ms+step_ms
        capture()
    metrics,roles,intervals=evaluate_episode(env)
    audit,gaps=safety_audit(env)
    metrics.update(audit,extra_event_visits=sum(e['extra_event_visit'] for e in env.events),choice_opportunities=env.choice_opportunities,
                   tasks_violating_exact_gap=audit['revisit_violations_audited'],history_estimator_inference_s=env.inference_seconds)
    record={'spec':dict(spec),'method':method,'estimator':'physics_residual_cvae_unet' if predictor is not None else 'nominal',
            'metrics':metrics,'by_role':roles,'anomaly_intervals':intervals,'inspection_events':env.events,
            'dispatches':env.dispatches,'decisions':env.decisions,'public_events':env.risk_episodes.events,
            'assignments':env.assignments,'scalar_trace':env.scalar_trace,'process_metadata':env.trace.metadata,
            'exact_task_gaps':gaps,'action_log':actions,'action_sha256':digest(actions),'process_sha256':env.trace.fingerprint,
            'asset_weights':env.asset_weights.tolist(),'rack_weights':env.trace.arrays['asset_weights'].tolist(),
            'deadlines_s':env.deadlines.tolist(),'role_order':[t.kind for t in env.tasks],'timing':timing,
            'estimation_clock_s':list(range(5,1801,5)),'matched_refresh_s':5}
    from .inspection_metrics import task_labels
    labels,_=task_labels(env)
    arrays={'predicted_temperature_c':np.asarray(temperature),'true_temperature_c':np.asarray(truth),
            'offline_task_positive_labels':labels,
            'fresh_measurement_mask':np.asarray(fresh),'rack_weights':env.trace.arrays['asset_weights'].copy()}
    if collect_training:
        arrays['public_context']=np.asarray(inputs,dtype=np.float32)
        for name in ['contact_temperature_c','rack_flow_kg_s','secondary_supply_c','primary_supply_c','process_scalars']:
            arrays['offline_'+name]=env.trace.arrays[name].copy()
    if arrays['predicted_temperature_c'].shape!=(360,128) or len(actions)!=359:raise RuntimeError('Clock alignment failed')
    return record,arrays,rollout
