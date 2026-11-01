"""Three-task committed reordering, without discretionary inspection insertion."""
from copy import deepcopy
import numpy as np

from .active_inspection import ActiveInspection, CANDIDATE_FEATURES
from .coverage_plan import InfeasibleCoverage, exact_task_gaps
from .improver_task import ImproverTask, PatrolProgram
from .inspection_metrics import evaluate_episode
from .local_reorder import RoundLedger, LocalPlanChecker
from .local_score import ScoreExpression, BASE_EXPRESSION
from .facility_observation import eligible
from .multistep_execution import DeniedOnlineTrace
from .multistep_workflow import digest


class ReorderTask(ImproverTask):
    def __init__(self,spec,predictor):
        super().__init__(spec,PatrolProgram(),predictor)
        self.ledgers=[RoundLedger(a['tour']) for a in self.agents]
        self.local_checks=[LocalPlanChecker(self.graph,self.tasks,a['tour'],self.deadlines,a['role']) for a in self.agents]
        self.local_pending={};self.local_dispatches=[];self.obligation_events=[];self.local_decisions=[]
        self.numeric_failures=[]
        owned=[j for a in self.agents for j in a['tour']]
        if sorted(owned)!=list(range(len(self.tasks))):raise ValueError('Original disjoint ownership required')
        self.local_initial=[check.check(self.clock,a['position'],self.last_inspection,list(a['tour']),list(a['tour'])[:3],set())
            for a,check in zip(self.agents,self.local_checks)]
        if not all(v['ok'] for v in self.local_initial):raise InfeasibleCoverage('Initial obligations infeasible')

    def options(self,i,reserved,guard=False):
        agent=self.agents[i];ledger=self.ledgers[i]
        if agent['task'] is not None:raise ValueError('Busy inspector')
        ids=[]
        if ledger.committed:
            j=ledger.committed[0]
            _,duration=self.local_checks[i].travel_service(agent['position'],j)
            if j not in reserved and self.clock+duration<=1800.+1e-9:ids=[j]
        return np.asarray(ids,dtype=int),np.zeros((len(ids),len(CANDIDATE_FEATURES)),dtype=np.float32),np.ones(len(ids),dtype=bool)

    def step(self,choices):
        prepared=[];reserved=self.reserved()
        for i,j in choices.items():
            ledger=self.ledgers[i];agent=self.agents[i]
            if j is None:
                if min(max(0.,self.last_inspection[k])+self.deadlines[k] for k in ledger.tour)<min(1800.,self.clock+5)-1e-9:
                    raise InfeasibleCoverage('Terminal/idle obligation expiry')
                continue
            if ledger.inflight is not None or not ledger.committed or ledger.committed[0]!=j:raise ValueError('Committed head obligation only')
            if j not in agent['allowed'] or not eligible(agent['role'],self.tasks[j]) or agent['role']!=self.local_checks[i].role:
                raise InfeasibleCoverage('Current ownership/profession/access failed')
            cert=self.local_checks[i].check(self.clock,agent['position'],self.last_inspection,ledger.remaining,ledger.committed,reserved)
            if not cert['ok']:raise InfeasibleCoverage('Current committed continuation failed')
            prepared.append({'agent':i,'task':int(j),'round_id':ledger.round_id,'dispatch_time_s':float(self.clock),
                'position':list(agent['position']),'remaining_before':list(ledger.remaining),'committed_before':list(ledger.committed),
                'certificate':cert})
            reserved.add(j)
        old_count=len(self.events)
        reward=ActiveInspection.step(self,choices)
        for row in prepared:
            self.ledgers[row['agent']].dispatch(row['task']);self.local_pending[row['agent']]=row;self.local_dispatches.append(row)
        for e in self.events[old_count:]:
            pending=self.local_pending.pop(e['agent']);ledger=self.ledgers[e['agent']]
            if pending['task']!=e['task'] or pending['round_id']!=ledger.round_id:raise RuntimeError('Wrong obligation completion')
            expected=pending['certificate']['segment_completion_s'][0]
            if e['time_s']!=expected:raise RuntimeError('Actual service/path duration differs from certificate')
            key=ledger.complete(e['task'])
            self.obligation_events.append({'agent':e['agent'],'round_id':key[0],'task':key[1],'time_s':e['time_s']})
            previous=self.measured_alert.get(e['task']);current=bool(e['alarm'])
            e['measurement_transition']='new_measured_alert' if current and not previous else 'persistent_recheck' if current else 'recovery_confirmation' if previous else 'normal_check'
            self.measured_alert[e['task']]=current
        self.supply_monitor.update(self.current_packet)
        return reward


def public_tasks(env):
    risk,_=env.public_risk();obs=env.state.observer
    recent={e['task']:e for e in env.events}
    result={}
    for j,task in enumerate(env.tasks):
        if task.kind=='thermal':stamp=float(obs.temperature_stamp[task.index]);source='remote_or_qualified_temperature_or_frozen_estimate'
        elif task.kind=='cooling':stamp=float(obs.flow_stamp[task.index]);source='observed_or_nominal_flow'
        else:stamp=float(recent[j]['time_s']) if j in recent else -1.;source='qualified_'+task.kind if stamp>=0 else 'initial_nominal_or_unobserved'
        result[j]={'task':j,'kind':task.kind,'risk':float(risk[j]),'weight':float(env.asset_weights[j]/2),
            'last_check_s':float(env.last_inspection[j]),'deadline_s':float(env.deadlines[j]),
            'direct_available':stamp>=0,'direct_time_s':stamp if stamp>=0 else None,
            'direct_age_s':float(env.clock-stamp) if stamp>=0 else None,'source':source,
            'freshness':min((env.clock-stamp)/300.,1.) if stamp>=0 else 1.}
    return result


def features_for(certificate,snapshot,tour,now):
    n=len(tour);risk_delay=pressure=freshness=0.;peak=0.
    for j in tour:
        row=snapshot[j];finish=certificate['first_completion_s'][j]
        delay=(finish-now)/row['deadline_s'];ratio=(finish-max(0.,row['last_check_s']))/row['deadline_s']
        risk_delay+=row['weight']*row['risk']*delay;pressure+=ratio*ratio
        freshness+=row['weight']*row['freshness']*delay;peak=max(peak,ratio)
    return {'risk_delay':float(risk_delay/n),'deadline_pressure':float(pressure/n),'deadline_peak':float(peak),
        'travel_cost':float(certificate['segment_and_bridge_travel_s']/300.),'freshness_delay':float(freshness/n)}


def lower(a,b):
    for x,y in zip(a,b):
        if x<y-1e-9:return True
        if x>y+1e-9:return False
    return False


def choose_local(env,method,expression):
    choices={};snapshot=None
    for i,agent in enumerate(env.agents):
        if agent['task'] is not None:continue
        ledger=env.ledgers[i]
        if not ledger.committed:
            if snapshot is None:snapshot=public_tasks(env)
            candidates=env.local_checks[i].candidates(env.clock,agent['position'],env.last_inspection,ledger.remaining,env.reserved())
            original=next(v for v in candidates if v['original'])
            if not original['certificate']['ok']:raise InfeasibleCoverage('Protected original continuation must remain available')
            legal=[v for v in candidates if v['certificate']['ok']]
            legal.sort(key=lambda v:(not v['original'],v['order']))
            for c in legal:
                c['features']=features_for(c['certificate'],snapshot,ledger.tour,env.clock)
            numeric_error=None
            try:
                for c in legal:
                    f=c['features']
                    c['score']=[f['deadline_peak'],f['deadline_pressure'],f['travel_cost']] if method=='D' else [expression.evaluate(f)]
            except ValueError as error:
                numeric_error=str(error);env.numeric_failures.append({'time_s':float(env.clock),'agent':i,'error':str(error)})
            selected=original
            if method!='T' and numeric_error is None:
                selected=legal[0]
                for c in legal[1:]:
                    if lower(c['score'],selected['score']):selected=c
            baseline=original['certificate']['first_completion_s'];actual=selected['certificate']['first_completion_s']
            change=[{'task':j,'delta_completion_s':float(actual[j]-baseline[j])} for j in ledger.tour]
            env.local_decisions.append({'time_s':float(env.clock),'agent':i,'round_id':ledger.round_id,
                'remaining_before':list(ledger.remaining),'window':ledger.window(),'candidates':candidates,
                'selected_order':list(selected['order']),'selected_original':selected['original'],
                'legal_permutations':len(legal),'legal_nonoriginal':sum(not c['original'] for c in legal),
                'public_tasks':[deepcopy(snapshot[j]) for j in ledger.tour],
                'completion_deltas_vs_original':change,'numeric_error':numeric_error})
            ledger.commit(selected['order'])
        ids,_,_=env.options(i,env.reserved())
        choices[i]=int(ids[0]) if len(ids) else None
    return choices


def run_reorder(spec,predictor,policy):
    method=policy['method']
    if method not in ('T','D','expression'):raise ValueError('Frozen scheduler type')
    expression=ScoreExpression(policy.get('score_expression',BASE_EXPRESSION))
    env=ReorderTask(spec,predictor);actions=[]
    while not env.done:
        trace=env.trace;env.trace=DeniedOnlineTrace()
        try:choices=choose_local(env,method,expression)
        finally:env.trace=trace
        actions.append({'time_s':float(env.clock),'choices':{str(i):j for i,j in choices.items()}})
        env.step(choices)
    metrics,by_role,intervals=evaluate_episode(env);maxima,gaps=exact_task_gaps(env.tasks,env.events)
    metrics.update(tasks_violating_exact_gap=int((maxima>env.deadlines+1e-9).sum()),
        maximum_exact_gap_s=float(maxima.max()),maximum_exact_gap_ratio=float((maxima/env.deadlines).max()),
        extra_checks=0,completed_rounds_total=sum(v.round_id for v in env.ledgers),
        current_round_unfinished_obligations=sum(len(v.remaining) for v in env.ledgers),
        unfinished_committed_tasks=sum(len(v.committed) for v in env.ledgers),
        numeric_scoring_failures=len(env.numeric_failures),estimator_calls=env.estimator_calls,
        local_plan_count=len(env.local_decisions),reordered_plans=sum(not v['selected_original'] for v in env.local_decisions),
        decision_points_with_alternative=sum(v['legal_nonoriginal']>0 for v in env.local_decisions))
    if metrics['tasks_violating_exact_gap']:raise InfeasibleCoverage('Full actual initial/intermediate/terminal gap failed')
    record={'specification':dict(spec),'policy':policy,'metrics':metrics,'by_role':by_role,'anomaly_intervals':intervals,
        'action_log':actions,'assignments':env.assignments,'inspection_events':env.events,'exact_task_gaps':gaps,
        'initial_local_certificates':env.local_initial,'local_decisions':env.local_decisions,'local_dispatches':env.local_dispatches,
        'obligation_events':env.obligation_events,'numeric_failures':env.numeric_failures,
        'round_ledgers':[{'agent':i,'round_id':v.round_id,'remaining':v.remaining,'committed':v.committed,'inflight':v.inflight,
            'settled_obligations':[list(k) for k in v.completed]} for i,v in enumerate(env.ledgers)],
        'scalar_trace':env.scalar_trace,'process':env.trace.metadata,'service_evidence_events':env.supply_monitor.events,
        'action_sha256':digest(actions),'extra_checks_enabled':False,'PPO_scoring_calls':0,
        'team':{'count':len(env.agents),'per_agent':[{k:a[k] for k in ('id','role','zone','travel_m','service_s','idle_s','completed')} for a in env.agents]}}
    return record,env
