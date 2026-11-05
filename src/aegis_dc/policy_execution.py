"""Private orchestration of public policy choices in one advancing facility."""
from copy import deepcopy
import math
from .decision_view import DecisionGateway
from .dispatch_policy import choose_work
from .evidence_ledger import EvidenceLedger,RECORD_FIELDS,_fields,_plain_json,_require,_text,_finite

PROGRAM_FIELDS={'schema','id','policy_program','nominal_knowledge','evidence_ledger','decision_times_s','inspection_program','intervention_program'}

class PolicySession:
    """The selector receives only a validated frame and arrived public feedback."""
    def __init__(self,program,duration_s):
        _plain_json(program);_fields(program,PROGRAM_FIELDS,'Policy facility run program')
        _require(program['schema']=='aegisdc-policy-run-program-v1','Unknown policy facility run schema')
        _text(program['id'],'Policy facility run id');self.program=deepcopy(program)
        self.times=program['decision_times_s']
        _require(type(self.times) is list and 1<=len(self.times)<=128,'Declare one to128 policy decision instants')
        for t in self.times:_finite(t,'Policy decision time')
        _require(0<=self.times[0] and self.times[-1]<=duration_s and all(a<b for a,b in zip(self.times,self.times[1:])),
                 'Policy decision instants must be strictly increasing within the facility horizon')
        self.nominal=program['nominal_knowledge'];self.ledger=deepcopy(program['evidence_ledger'])
        self.inspection_program=program['inspection_program'];self.intervention_program=program['intervention_program']
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
        self.issued=[];self.decisions=[];self.index=0

    def _frame(self,time_s,inspections):
        ledger=EvidenceLedger(self.ledger)
        if inspections is not None:
            for row in inspections.snapshot(time_s)['records']:ledger.ingest({k:row[k] for k in RECORD_FIELDS})
        snapshot=ledger.snapshot(time_s)
        document=dict(schema='aegisdc-evidence-ledger-v1',id=snapshot['ledger_id'],facility_id=snapshot['facility_id'],
            basis='synthetic_assumption',time_unit='s',**snapshot['static_knowledge'],
            records=[{k:r[k] for k in RECORD_FIELDS} for r in snapshot['records']])
        plan=dict(schema='aegisdc-public-preparation-plan-v1',id=self.program['id'],basis='synthetic_assumption',time_unit='s',
            decision_times_s=[time_s],requests=[])
        return DecisionGateway(self.nominal,document,plan).next_frame()

    def process(self,time_s,workforce,inspections,interventions):
        if self.index>=len(self.times) or time_s<self.times[self.index]:return False
        _require(time_s==self.times[self.index],'Policy decisions must use their exact declared public instant')
        frame=self._frame(time_s,inspections)
        history=dict(issued=deepcopy(self.issued),work_feedback=workforce.public_feedback(time_s))
        choice=choose_work(frame,self.program['policy_program'],history)
        self.decisions.append(dict(frame=frame,history=history,choice=deepcopy(choice)))
        self.index+=1
        if choice['chosen_candidate_id'] is None:return False
        task=choice['work_intention']
        if interventions is not None:interventions.record_issue(frame,self.work_program['profile'],task)
        workforce.submit(frame,task)
        self.issued.append(dict(candidate_id=choice['chosen_candidate_id'],issued_at_s=time_s))
        return True

    def next_event(self,time_s):
        return self.times[self.index] if self.index<len(self.times) else math.inf
