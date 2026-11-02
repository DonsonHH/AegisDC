"""Public risk episodes and single-completion replanning with return certificates."""
from copy import deepcopy
import numpy as np

from .active_inspection import ActiveInspection, CANDIDATE_FEATURES
from .contracts import DeniedOnlineTrace, digest
from .coverage_plan import ReturnPlan, InfeasibleCoverage, exact_task_gaps
from .facility_observation import eligible
from .inspection_metrics import evaluate_episode
from .patrol_task import FixedPatrolTask


class RiskEpisodes:
    def __init__(self, size, ttl=120.):
        self.high = [False] * size
        self.pending = {}
        self.events = []
        self.ttl = ttl

    def observe(self, now, risks):
        # Expired obligations must not suppress a fresh rising edge at this time.
        # Continuous positive risk still does not reopen an expired episode.
        for j, event in list(self.pending.items()):
            if now > event['expires_s']:
                event['status'] = 'expired'
                del self.pending[j]
        for j, risk in enumerate(risks):
            high = float(risk) > 0
            if high and not self.high[j] and j not in self.pending:
                event = {'event_id': len(self.events), 'task': j, 'visible_s': float(now),
                         'initial_public_risk': float(risk), 'expires_s': float(now+self.ttl),
                         'status': 'pending', 'measurement_s': None, 'measured_alarm': None}
                self.events.append(event)
                self.pending[j] = event
            self.high[j] = high

    def complete(self, completion):
        event = self.pending.get(completion['task'])
        if event is not None and completion['time_s'] >= event['visible_s']:
            event.update(status='measured', measurement_s=completion['time_s'],
                         measured_alarm=completion['alarm'], agent=completion['agent'])
            del self.pending[completion['task']]


class ResponseChecker:
    """New action adapter: owned event insertion followed by the unchanged tour.

    A non-head event visit does not discharge a later routine obligation. The
    proof updates its last-check time, checks every delayed owned obligation and
    the restored periodic cycle. This is not a three-item permutation proof.
    """
    def __init__(self, env, agent):
        self.tasks, self.agent = env.tasks, agent
        self.plan = ReturnPlan(env.graph, env.tasks, agent['tour'], env.deadlines)

    def check(self, now, position, last, cursor, target, reserved):
        if target not in self.agent['allowed'] or not eligible(self.agent['role'], self.tasks[target]):
            return {'ok': False, 'reason': 'qualification_or_ownership'}
        if target in reserved:
            return {'ok': False, 'reason': 'reservation'}
        if now+self.plan.travel_service(position,target)>1800:
            return {'ok': False, 'reason': 'episode_horizon'}
        return self.plan.check(now,position,last,cursor,candidate=target)


class ResponseTask(FixedPatrolTask):
    def __init__(self, spec, enable_events=True, ttl=120., priority='fifo', extra_visit_budget=None, risk_permutation_seed=None):
        super().__init__(spec,None)
        if extra_visit_budget is not None and (type(extra_visit_budget) is not int or extra_visit_budget < 0):
            raise ValueError('Extra visit budget must be a nonnegative integer')
        self.extra_visit_budget = extra_visit_budget
        self.extra_dispatched = 0
        self.risk_source_for_target = np.arange(len(self.tasks))
        if risk_permutation_seed is not None:
            rng = np.random.default_rng(risk_permutation_seed)
            for agent in self.agents:
                ids = np.asarray(agent['tour'])
                if len({self.tasks[j].kind for j in ids}) != 1:
                    raise ValueError('Risk permutation requires same-profession ownership')
                order = rng.permutation(ids)
                self.risk_source_for_target[order] = np.roll(order, 1)
        if priority not in ('fifo','risk','opportunity'):raise ValueError('Unknown event priority')
        self.priority=priority
        self.enable_events=enable_events
        self.cursor=[0]*len(self.agents)
        self.checkers=[ResponseChecker(self,a) for a in self.agents]
        self.risk_episodes=RiskEpisodes(len(self.tasks),ttl)
        self.dispatches=[]
        self.pending_dispatch={}
        self.decisions=[]
        self.observe_response_risk()

    def response_risk(self):
        return self.public_risk()[0][self.risk_source_for_target]

    def observe_response_risk(self):
        before = len(self.risk_episodes.events)
        self.risk_episodes.observe(self.clock, self.response_risk())
        for event in self.risk_episodes.events[before:]:
            event['signal_source_task'] = int(self.risk_source_for_target[event['task']])

    def options(self,i,reserved,guard=False):
        a=self.agents[i]
        candidates=[a['tour'][self.cursor[i]]]
        if self.enable_events:
            candidates+=sorted(j for j in self.risk_episodes.pending if j in a['allowed'] and j not in candidates)
        legal=[j for j in candidates if self.checkers[i].check(self.clock,a['position'],self.last_inspection,
               self.cursor[i],j,reserved)['ok']]
        return np.asarray(legal,dtype=int),np.zeros((len(legal),len(CANDIDATE_FEATURES))),np.ones(len(legal),dtype=bool)

    def choose(self):
        choices={};reserved=self.reserved();risks=self.response_risk()
        planned_extras = 0
        for i,a in enumerate(self.agents):
            if a['task'] is not None:continue
            head=a['tour'][self.cursor[i]]
            targets=[head]+sorted(j for j in self.risk_episodes.pending if j in a['allowed'] and j!=head) if self.enable_events else [head]
            rows=[{'task':j,'certificate':self.checkers[i].check(self.clock,a['position'],self.last_inspection,
                   self.cursor[i],j,reserved),'public_risk':float(risks[j]),
                   'event_id':self.risk_episodes.pending[j]['event_id'] if j in self.risk_episodes.pending else None}
                  for j in targets]
            budget_available = self.extra_visit_budget is None or self.extra_dispatched + planned_extras < self.extra_visit_budget
            for row in rows:
                row['budget_allowed'] = row['task'] == head or budget_available
            legal=[r for r in rows if r['certificate']['ok'] and r['budget_allowed']]
            event_choices=[r for r in legal if self.enable_events and r['event_id'] is not None]
            if self.priority=='opportunity':
                for candidate in event_choices:
                    j=candidate['task'];finish=candidate['certificate']['candidate_finish_s']
                    virtual=self.last_inspection.copy();virtual[j]=finish
                    cursor=(self.cursor[i]+1)%len(a['tour']) if j==head else self.cursor[i]
                    lost=[]
                    for other in event_choices:
                        k=other['task']
                        if k==j or other['public_risk']<=0:continue
                        expiry=self.risk_episodes.pending[k]['expires_s']
                        if other['certificate']['candidate_finish_s']>expiry:continue
                        certificate=self.checkers[i].check(finish,self.tasks[j].position_m,virtual,cursor,k,reserved)
                        if not certificate['ok'] or certificate['candidate_finish_s']>expiry:
                            lost.append(k)
                    candidate['lost_next_opportunities']=lost
            def order(row):
                age=self.risk_episodes.pending[row['task']]['visible_s']
                if self.priority=='fifo':return (age,-row['public_risk'],row['task'])
                if self.priority=='risk':return (-row['public_risk'],age,row['task'])
                return (len(row['lost_next_opportunities']),-row['public_risk'],age,row['task'])
            selected=min(event_choices,key=order) if event_choices else next((r for r in legal if r['task']==head),None)
            j=selected['task'] if selected else None
            choices[i]=j
            self.decisions.append({'time_s':self.clock,'agent':i,'routine_head':head,'selected':j,'candidates':rows})
            if j is not None:
                planned_extras += int(j != head)
                self.pending_dispatch[i]={'time_s':self.clock,'agent':i,'task':j,'routine_head':head,
                    'extra_event_visit':j!=head,'event_id':selected['event_id'],'certificate':selected['certificate']}
                self.dispatches.append(deepcopy(self.pending_dispatch[i]));reserved.add(j)
        return choices

    def step(self,choices):
        extras = sum(j is not None and j != self.agents[i]['tour'][self.cursor[i]] for i,j in choices.items())
        if self.extra_visit_budget is not None and self.extra_dispatched + extras > self.extra_visit_budget:
            raise ValueError('Extra visit dispatch budget exceeded')
        before=len(self.events)
        reward=ActiveInspection.step(self,choices)
        self.extra_dispatched += extras
        for event in self.events[before:]:
            dispatch=self.pending_dispatch.pop(event['agent'])
            if event['time_s']!=dispatch['certificate']['candidate_finish_s']:
                raise RuntimeError('Actual completion differs from return certificate')
            if event['task']==dispatch['routine_head']:
                i=event['agent'];self.cursor[i]=(self.cursor[i]+1)%len(self.agents[i]['tour'])
            event['extra_event_visit']=dispatch['extra_event_visit']
            event['response_event_id']=dispatch['event_id']
        self.observe_response_risk()
        for event in self.events[before:]:
            self.risk_episodes.complete(event)
            identity=event['response_event_id']
            if identity is not None:
                requested=self.risk_episodes.events[identity]
                if requested['status']=='expired':
                    requested.update(status='measured_late',measurement_s=event['time_s'],
                                     measured_alarm=event['alarm'],agent=event['agent'])
        return reward


def run_response(spec,enable_events=True,ttl=120.,priority='fifo',extra_visit_budget=None,risk_permutation_seed=None):
    env=ResponseTask(spec,enable_events,ttl,priority,extra_visit_budget,risk_permutation_seed);actions=[]
    while not env.done:
        trace,env.trace=env.trace,DeniedOnlineTrace()
        try:choices=env.choose()
        finally:env.trace=trace
        actions.append({'time_s':float(env.clock),'choices':{str(i):j for i,j in choices.items()}})
        env.step(choices)
    metrics,by_role,intervals=evaluate_episode(env)
    maxima,gaps=exact_task_gaps(env.tasks,env.events)
    violations=int((maxima>env.deadlines+1e-9).sum())
    if violations:raise InfeasibleCoverage('Actual initial/intermediate/terminal revisit gap failed')
    events=env.risk_episodes.events
    measured=[e for e in events if e['status']=='measured']
    metrics.update(tasks_violating_exact_gap=violations,
        extra_event_visits=sum(e['extra_event_visit'] for e in env.events),
        public_risk_episodes=len(events),event_measurements=len(measured),
        event_positive_measurements=sum(e['measured_alarm'] for e in measured),
        event_normal_measurements=sum(not e['measured_alarm'] for e in measured),
        mean_public_event_to_measurement_s=float(np.mean([e['measurement_s']-e['visible_s'] for e in measured])) if measured else None)
    return {'metrics':metrics,'by_role':by_role,'anomaly_intervals':intervals,'inspection_events':env.events,
            'public_events':events,'decisions':env.decisions,'dispatches':env.dispatches,
            'action_log':actions,'action_sha256':digest(actions),'exact_task_gaps':gaps,
            'process_sha256':env.trace.fingerprint,
            'response_config':{'extra_visit_budget':extra_visit_budget,'extra_dispatched':env.extra_dispatched,
                'risk_permutation_seed':risk_permutation_seed,'risk_source_for_target':env.risk_source_for_target.tolist()}},env


def run_response_study(args):
    """Fixed small development/confirmation protocol; no model or training calls."""
    import csv,gzip,hashlib,json
    from pathlib import Path
    from datetime import datetime,timezone
    from .reorder_execution import run_reorder
    from .cli import ROOT,write_json
    protocol_path=Path(args.protocol) if args.protocol else ROOT/'configs/risk-response.json'
    protocol=json.loads(protocol_path.read_text(encoding='utf-8'))
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    write_json(output/'protocol.json',protocol)
    write_json(output/'seal.json',{'at':datetime.now(timezone.utc).isoformat(),
        'protocol_sha256':hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}})
    rows=[];records={};attempts=[]
    def execute(phase,case,variant):
        if len(attempts)>=protocol['limits']['main_environment_evaluations']:raise RuntimeError('Budget exhausted')
        attempt={'phase':phase,'case':case['id'],'variant':variant,'status':'started'}
        attempts.append(attempt);write_json(output/'attempts.json',attempts)
        try:
            if variant=='T':
                actual,env=run_reorder(case['spec'],None,{'method':'T'})
                r={k:actual[k] for k in ('metrics','by_role','anomaly_intervals','inspection_events','action_log','action_sha256')}
                r['process_sha256']=env.trace.fingerprint
            else:r,env=run_response(case['spec'],variant!='B',60. if variant=='E60' else 120.)
            key=f"{case['id']}-{variant}"
            with gzip.open(output/(key+'.json.gz'),'wt',encoding='utf-8') as f:json.dump(r,f,allow_nan=False)
            records[key]=r
            metrics=r['metrics']
            rows.append({'phase':phase,'case':case['id'],'variant':variant,
                **{k:metrics.get(k,0) for k in ('anomaly_segments','confirmed_segments','missed_segments',
                    'consequence_weighted_censored_delay_s','travel_m','service_s','completed_inspections',
                    'tasks_violating_exact_gap','extra_event_visits','public_risk_episodes','event_measurements',
                    'event_positive_measurements','event_normal_measurements')}})
            attempt.update(status='completed',action_sha256=r['action_sha256'])
            print(phase,case['id'],variant,'missed',metrics['missed_segments'],flush=True)
        except Exception as error:
            attempt.update(status='failed',error=str(error));raise
        finally:write_json(output/'attempts.json',attempts)
    for case in protocol['development']:
        for variant in protocol['variants']:execute('development',case,variant)
        assert records[case['id']+'-T']['action_log']==records[case['id']+'-B']['action_log']
    def key(variant):
        r=[x for x in rows if x['phase']=='development' and x['variant']==variant]
        waits=[x['consequence_weighted_censored_delay_s'] for x in r if x['consequence_weighted_censored_delay_s'] is not None]
        return (sum(x['missed_segments'] for x in r)/len(r),sum(waits)/len(waits) if waits else 0,
                sum(x['travel_m'] for x in r)/len(r))
    chosen=min(['E120','E60'],key=key)
    write_json(output/'selected.json',{'at':datetime.now(timezone.utc).isoformat(),'selected':chosen,
                                     'development_keys':{v:key(v) for v in ['E120','E60']}})
    for case in protocol['confirmation']:
        for variant in ['T','B',chosen]:execute('confirmation',case,variant)
        assert records[case['id']+'-T']['action_log']==records[case['id']+'-B']['action_log']
        assert len({records[case['id']+'-'+v]['process_sha256'] for v in ['T','B',chosen]})==1
    with (output/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={'selected':chosen,'evaluations':len(attempts),'model_calls':0,'training':0,'confirmation':{}}
    for v in ['T','B',chosen]:
        r=[x for x in rows if x['phase']=='confirmation' and x['variant']==v]
        summary['confirmation'][v]={k:sum(x[k] for x in r) for k in ('anomaly_segments','confirmed_segments','missed_segments','extra_event_visits','tasks_violating_exact_gap')}
        for k in ('travel_m','service_s','completed_inspections'):
            summary['confirmation'][v]['mean_'+k]=sum(x[k] for x in r)/len(r)
    write_json(output/'summary.json',summary)
    lines=['# 新风险有效确认：首轮机制试验','',
        'T为原固定巡回，B为单项重规划但不响应事件，E为单项重规划并响应公开风险事件。',
        '新规则增加了事件检查动作权限，其收益不属于大模型或RSI。测量正常也会结束本次响应，但只有评价器匹配到异常区间的有效测量才算异常确认。','',
        '|条件|策略|异常段|确认|漏检|等待/秒|移动/米|完成检查|额外事件检查|重访违规|',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        if r['phase']=='confirmation':
            wait=r['consequence_weighted_censored_delay_s']
            lines.append(f"|{r['case']}|{r['variant']}|{r['anomaly_segments']}|{r['confirmed_segments']}|{r['missed_segments']}|{wait if wait is not None else '不适用'}|{r['travel_m']:.1f}|{r['completed_inspections']}|{r['extra_event_visits']}|{r['tasks_violating_exact_gap']}|")
    lines+=['','开发只选择事件超时60或120秒；随后封存，新确认没有继续调参。42次主比较，3次前置试运行；无模型调用与训练。',
        '必要的例行重访不标成无效重复；额外事件检查单列，正常响应测量和异常确认分别记录。全部证书、公开事件、实际测量及拒绝理由见对应gzip原件。',
        '本轮仅两个新底层种子；健康高噪声条件未触发不等于已充分验证误触发鲁棒性。公开风险阈值和事件超时仍是需要后续验证的设计选择。']
    (output/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    return summary
