"""Private orchestration of public policy choices in one advancing facility."""
from copy import deepcopy
import math
from time import perf_counter_ns
from .decision_view import DecisionGateway
from .dispatch_policy import choose_work
from .evidence_ledger import EvidenceLedger,RECORD_FIELDS,_fields,_plain_json,_require,_text,_finite

PROGRAM_FIELDS={'schema','id','policy_program','nominal_knowledge','evidence_ledger','decision_times_s','inspection_program','intervention_program'}

class PolicySession:
    """The selector receives only a validated frame and arrived public feedback."""
    def __init__(self,program,duration_s):
        _plain_json(program)
        lifecycle=type(program) is dict and program.get('schema')=='aegisdc-policy-run-program-v3'
        live=type(program) is dict and program.get('schema') in {'aegisdc-policy-run-program-v2','aegisdc-policy-run-program-v3'}
        _fields(program,PROGRAM_FIELDS|({'sensor_program'} if live else set())|({'closure_program','preparation_requests'} if lifecycle else set()),'Policy facility run program')
        _require(program['schema'] in {'aegisdc-policy-run-program-v1','aegisdc-policy-run-program-v2','aegisdc-policy-run-program-v3'},'Unknown policy facility run schema')
        _text(program['id'],'Policy facility run id');self.program=deepcopy(program)
        self.times=program['decision_times_s']
        _require(type(self.times) is list and 1<=len(self.times)<=128,'Declare one to128 policy decision instants')
        for t in self.times:_finite(t,'Policy decision time')
        _require(0<=self.times[0] and self.times[-1]<=duration_s and all(a<b for a,b in zip(self.times,self.times[1:])),
                 'Policy decision instants must be strictly increasing within the facility horizon')
        self.nominal=program['nominal_knowledge'];self.ledger=deepcopy(program['evidence_ledger'])
        self.inspection_program=program['inspection_program'];self.intervention_program=program['intervention_program']
        self.closure_template=deepcopy(program['closure_program']) if lifecycle else None
        if self.closure_template is not None:
            _require(type(self.closure_template) is dict and self.closure_template.get('intervention_feedback')==[],
                'Declare an empty closure feedback channel; actual arrived reports are supplied by the executor')
            _require(self.closure_template.get('intervention_declaration')==self.intervention_program,
                'Closure and execution must share the same public action declaration')
        if program['policy_program']['schema']=='aegisdc-dispatch-policy-program-v3':
            _require(program['policy_program']['intervention_declaration']==self.intervention_program,
                'Policy and actual executor must share the same public intervention declaration')
        self.sensors=None
        if live and program['sensor_program'] is not None:
            from .live_sensor_execution import LiveSensorSession
            self.sensors=LiveSensorSession(program['sensor_program'],duration_s)
            registry=self.sensors.profile['ledger']
            _require(registry['facility_id']==self.ledger['facility_id'] and set(registry['entity_ids'])==set(self.ledger['entity_ids']),
                'Fixed sensor and policy public facility identities differ')
            for field in ('sources','observables'):
                existing={r['id']:r for r in self.ledger[field]}
                for row in registry[field]:
                    _require(row['id'] not in existing or row==existing[row['id']],'Conflicting fixed sensor policy registry')
                    if row['id'] not in existing:self.ledger[field].append(deepcopy(row));existing[row['id']]=row
            fixed_sources={s['id'] for s in registry['sources']}
            _require(not any(r['source_id'] in fixed_sources for r in self.ledger['records']),
                'Declare historical records separately from live fixed sensor sources')
        if program['policy_program']['schema'] in {'aegisdc-dispatch-policy-program-v2','aegisdc-dispatch-policy-program-v3'}:
            inspection_ids={b['task_id'] for b in self.inspection_program['profile']['bindings']} if self.inspection_program is not None else set()
            intervention_ids={b['task_id'] for b in self.intervention_program['bindings']} if self.intervention_program is not None else set()
            _require(not inspection_ids&intervention_ids,'One task cannot combine inspection and physical intervention')
            for candidate in program['policy_program']['candidates']:
                _text(candidate.get('kind'),'Declared policy intention kind')
                expected=inspection_ids if candidate['kind']=='inspect' else intervention_ids if candidate['kind']=='intervene' else set()
                _require(candidate['task']['id'] in expected,'Declared policy intention kind differs from its execution binding')
        if self.inspection_program is not None:
            profile=self.inspection_program['profile']['nonfixed_profile']['registry']
            _require(profile['facility_id']==self.ledger['facility_id'] and set(profile['entity_ids'])==set(self.ledger['entity_ids']),
                'Inspection and policy public registry identities differ')
            for field in ('sources','observables'):
                existing={r['id']:r for r in self.ledger[field]}
                for row in profile[field]:
                    _require(row['id'] not in existing or row==existing[row['id']],'Conflicting declared policy evidence registry')
                    if row['id'] not in existing:self.ledger[field].append(deepcopy(row));existing[row['id']]=row
            produced={r['record_id'] for r in self.inspection_program['profile']['bindings']}
            _require(not produced&{r['id'] for r in self.ledger['records']},'Do not prefill actual inspection records')
        initial=self._frame(0,None)
        profile=program['policy_program']['workforce_profile']
        self.work_program=dict(schema='aegisdc-work-program-v2',id=program['id']+'-crew',profile=deepcopy(profile),
            initial_frame=initial,submissions=[])
        self.catalog_program=dict(schema='aegisdc-work-program-v1',id=program['id']+'-declared-bindings',profile=deepcopy(profile),
            submissions=[dict(frame=deepcopy(initial),task=deepcopy(c['task'])) for c in program['policy_program']['candidates']])
        if program['policy_program']['policy']=='one_observation_lookahead':
            from .lookahead_policy import validate_execution_bindings
            validate_execution_bindings(program['policy_program'],self.inspection_program)
        self.issued=[];self.decisions=[];self.computation_audit=[];self.index=0

    def _frame(self,time_s,inspections):
        ledger=EvidenceLedger(self.ledger)
        if self.sensors is not None:
            for row in self.sensors.ledger.snapshot(time_s)['records']:ledger.ingest({k:row[k] for k in RECORD_FIELDS})
        if inspections is not None:
            for row in inspections.snapshot(time_s)['records']:ledger.ingest({k:row[k] for k in RECORD_FIELDS})
        snapshot=ledger.snapshot(time_s)
        document=dict(schema='aegisdc-evidence-ledger-v1',id=snapshot['ledger_id'],facility_id=snapshot['facility_id'],
            basis='synthetic_assumption',time_unit='s',**snapshot['static_knowledge'],
            records=[{k:r[k] for k in RECORD_FIELDS} for r in snapshot['records']])
        plan=dict(schema='aegisdc-public-preparation-plan-v1',id=self.program['id'],basis='synthetic_assumption',time_unit='s',
            decision_times_s=[time_s],requests=deepcopy(self.program.get('preparation_requests',
                self.program['policy_program'].get('options',{}).get('preparation_requests',[]))))
        return DecisionGateway(self.nominal,document,plan).next_frame()

    def process(self,time_s,workforce,inspections,interventions):
        if self.index>=len(self.times) or time_s<self.times[self.index]:return False
        _require(time_s==self.times[self.index],'Policy decisions must use their exact declared public instant')
        frame=self._frame(time_s,inspections)
        history=dict(issued=deepcopy(self.issued),work_feedback=workforce.public_feedback(time_s))
        closure=deepcopy(self.closure_template)
        if closure is not None:closure['intervention_feedback']=interventions.public_feedback(time_s) if interventions is not None else []
        started=perf_counter_ns()
        choice=choose_work(frame,self.program['policy_program'],history,intervention_declaration=self.intervention_program,closure_program=closure)
        self.computation_audit.append(dict(decision_at_s=time_s,elapsed_ns=perf_counter_ns()-started,
            model_evaluations=deepcopy(choice['model_evaluations']),candidate_count=len(choice['candidates']),
            forecast_branch_count=choice.get('forecast_branch_count',0),
            scope='DIAGNOSTIC_WALL_TIME_ONLY_NOT_PHYSICAL_TIME_OR_POLICY_INPUT'))
        self.decisions.append(dict(frame=frame,history=history,choice=deepcopy(choice)))
        self.index+=1
        if choice['chosen_candidate_id'] is None:return False
        task=choice['work_intention']
        if interventions is not None:interventions.record_issue(frame,self.work_program['profile'],task)
        workforce.submit(frame,task)
        self.issued.append(dict(candidate_id=choice['chosen_candidate_id'],issued_at_s=time_s))
        return True

    def next_event(self,time_s):
        decision=self.times[self.index] if self.index<len(self.times) else math.inf
        return min(decision,self.sensors.next_event() if self.sensors is not None else math.inf)

    def resource_ledger(self,time_s,workforce,inspections):
        if self.program['policy_program']['schema'] not in {'aegisdc-dispatch-policy-program-v3','aegisdc-dispatch-policy-program-v4'}:return None
        from .policy_budget import account
        program=self.program['policy_program'];frame=self._frame(time_s,inspections)
        return account(frame,program,dict(issued=self.issued,work_feedback=workforce.public_feedback(time_s)),
            {c['id']:c for c in program['candidates']},[])
