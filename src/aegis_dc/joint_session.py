"""Opt-in bridge: native work, action and sampling on one continuously advancing V6 plant."""
from copy import deepcopy
from math import inf
from time import perf_counter_ns

from .decision_view import DecisionGateway
from .joint_evidence import at_time, require
from .joint_policy import choose, validate
from .joint_messages import native_message
from .workforce_dispatch import CrewWorkforce


class JointInspection:
    def __init__(self,scenario,catalog,program):
        require(set(program)=={'schema','bindings'},'Joint inspection program')
        tasks={r['task']['id']:r['task'] for r in catalog['submissions']}
        interfaces={r['id']:r for d in scenario['domains'] for r in d['work_interfaces']}
        self.bindings={};self.rows=[];self.audit=[];self.done=set();self.time=-1
        for b in program['bindings']:
            t=tasks[b['task']];kind,origin,phase=t['id'].split('/')
            require(set(b)==set('task target interface tool worker qualification minimum_work_s fields ttl latency'.split())
                and t['id'] not in self.bindings and phase in ('I','R') and
                b['target']==t['target_id'] and b['interface']==t['work_interface_id'] and
                t['crew']==[{'worker_id':b['worker'],'qualification_id':b['qualification']}] and
                t['tool_carrier_id']==b['worker'] and interfaces[b['interface']]['tool_ids']==[b['tool']] and
                b['target'] in interfaces[b['interface']]['target_ids'] and b['minimum_work_s']>0 and b['ttl']>0 and b['latency']>0,
                'Joint paid task must bind a real scoped worker, tool and target')
            allowed={'g','e'} if (kind,b['target'],b['interface'])==('N','network','inspect_it_service') else (
                {'q'} if (kind,b['target'],b['interface'])==('C','intake_pump','inspect_facility_cooling') else set())
            require(set(b['fields'])==allowed and allowed,'Closed paid signal binding')
            self.bindings[t['id']]=deepcopy(b)

    def process(self,time_s,workforce,point):
        require(type(workforce) is CrewWorkforce and time_s==point['time_s']==workforce.last_time and
                time_s>=self.time,'Joint sample requires live native work and a contemporaneous plant point')
        self.time=time_s
        for work in workforce.records:
            task=work['id']
            if task in self.done or task not in self.bindings or work['status'] not in ('completed','rejected','aborted'):continue
            self.done.add(task);b=self.bindings[task]
            if work['status']!='completed':
                self.audit.append(dict(task=task,status=work['status'],sampled=[]));continue
            require(time_s==work['completed_at_s'] and time_s>=work['work_started_at_s']+b['minimum_work_s']
                    and work['tool_carrier_id']==b['worker'] and work['target_id']==b['target'],'Paid work identity/duration')
            kind,origin,phase=task.split('/');bundle=f'{task}@{time_s:g}';sampled=[]
            for field,grant in sorted(b['fields'].items()):
                permitted=grant is not None and grant[0]<=work['issued_at_s']<=time_s<grant[1]
                value=None
                if permitted:
                    if field=='q':value=point['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s']
                    elif field=='e':value=point['domains']['it_service']['capacities']['network']
                    else:value=workforce.p['network_service_capacity']
                    sampled.append(field)
                self.rows.append(dict(task=task,instance=kind+'/'+origin,phase=phase,field=field,target=b['target'],
                    unit='m3/s' if field=='q' else '1',interval=None if value is None else [value,value],
                    at=time_s,arrived=time_s+b['latency'],until=time_s+b['ttl'],bundle=bundle,origin='paid:'+bundle,
                    source='onsite-'+kind,disposition='MEASURED' if permitted else 'FIELD_UNAVAILABLE'))
            self.audit.append(dict(task=task,at=time_s,status='completed',bundle=bundle,sampled=sampled))

    def public_feedback(self,t):
        require(0<=t<=self.time,'Inspection query outside current clock')
        return deepcopy([r for r in self.rows if r['arrived']<=t])

    def snapshot(self,t):
        return dict(records=self.public_feedback(t),as_of_s=t)

    def public_models(self):
        return dict(schema='aegisdc-joint-paid-declarations-v1',bindings=deepcopy(list(self.bindings.values())))

    def private_audit(self):
        return dict(visibility='PRIVATE_PLANT_EVALUATOR_ONLY',events=deepcopy(self.audit))


class JointSensors:
    def __init__(self,cfg):
        self.cfg=cfg;self.index=0;self.rows=[];self.audit=[]

    def next_event(self):
        epochs=self.cfg['fixed_epochs']
        return epochs[self.index] if self.index<len(epochs) else inf

    def process(self,t,snapshot):
        if t<self.next_event():return
        require(t==self.next_event()==snapshot['time_s'],'Fixed sampling at actual native epoch')
        d=snapshot['domains']
        values=dict(lake=d['facility_cooling']['lake_mass_flow_kg_s'],network=d['it_service']['capacities']['network'],
                    service=d['it_service']['delivered'])
        for f in self.cfg['fixed_on']:
            value=values[f]
            self.rows.append(dict(field=f,at=t,arrived=t+self.cfg['latency'],until=t+self.cfg['fixed_ttl'],
                interval=[value,value],origin=f'fixed:{f}@{t:g}',source='fixed-'+f))
        self.audit.append(dict(at=t,sampled=list(self.cfg['fixed_on'])));self.index+=1


class JointSession:
    def __init__(self,program,duration_s):
        require(set(program)==set('schema id policy_program nominal_knowledge workforce_profile evidence_ledger order_channel task_catalog intervention_program inspection_program'.split()),'Joint native program')
        self.program=deepcopy(program);self.cfg=self.program['policy_program'];validate(self.cfg)
        require(duration_s==self.cfg['horizon'],'Native/declared clock mismatch')
        self.orders=self.program['order_channel'];self.profile=self.program['workforce_profile']
        self.catalog={r['id']:r for r in self.program['task_catalog']}
        require(len(self.catalog)==len(self.program['task_catalog']),'Duplicate native joint task')
        self.issued=[];self.decisions=[];self.computation_audit=[];self.index=0
        self.inspection_program=self.program['inspection_program'];self.intervention_program=self.program['intervention_program']
        actual_writes={r['task_id']:r for r in self.intervention_program['bindings']}
        grants={r['id']:r for r in self.intervention_program['profile']['authorizations']}
        reads={b['task']:b for b in self.inspection_program['bindings']}
        require(set(actual_writes)|set(reads)==set(self.catalog) and not set(actual_writes)&set(reads),'Joint catalog/executor coverage')
        for name,t in self.catalog.items():
            kind,origin,phase=name.split('/');typ=self.cfg['types'][kind]
            require(phase in ('I','A','R') and t['crew']==[dict(worker_id=typ['worker'],qualification_id=typ['qualification'])]
                and t['target_id']==(typ['asset'] if phase=='A' else typ['target']) and t['work_interface_id']==typ['interface'],
                'Target/crew/phase mismatch')
            if phase=='A':
                binding=actual_writes[name];grant=grants[binding['authorization_id']]
                require(binding['operation_id']==typ['operation'] and binding['setting']==typ['setting'] and
                    typ['write']==[grant['starts_at_s'],grant['expires_at_s']],'Write grant/binding mismatch')
            else:
                require(typ['read']==reads[name]['fields'] and typ['tool']==reads[name]['tool']
                    and reads[name]['ttl']==self.cfg['paid_ttl'] and reads[name]['latency']==self.cfg['latency'],'Paid read grant mismatch')
        self.sensors=JointSensors(self.cfg)
        initial=self.frame(0)
        self.work_program=dict(schema='aegisdc-work-program-v2',id='joint-crew',profile=self.profile,initial_frame=initial,submissions=[])
        self.catalog_program=dict(schema='aegisdc-work-program-v1',id='joint-native-catalog',profile=self.profile,
            submissions=[dict(frame=initial,task=t) for t in self.catalog.values()])

    def frame(self,t):
        plan=dict(schema='aegisdc-public-preparation-plan-v1',id='joint-work',basis='synthetic_assumption',time_unit='s',
                  decision_times_s=[t],requests=[])
        return DecisionGateway(self.program['nominal_knowledge'],self.program['evidence_ledger'],plan).next_frame()

    def next_event(self,t):
        clock=self.cfg['clock']
        return min(clock[self.index] if self.index<len(clock) else inf,self.sensors.next_event())

    def process(self,t,workforce,inspections,interventions):
        if self.index>=len(self.cfg['clock']) or t<self.cfg['clock'][self.index]:return False
        require(t==self.cfg['clock'][self.index],'Joint public clock')
        work=[row for raw in workforce.public_feedback(t)
              if (row:=native_message(self.cfg,self.issued,raw,'work',t)) is not None]
        writes=[row for raw in interventions.public_feedback(t)
                if (row:=native_message(self.cfg,self.issued,raw,'write',t)) is not None]
        view=at_time(dict(orders=self.orders,issued=self.issued,work=work,writes=writes,paid=inspections.public_feedback(t),
                          fixed=self.sensors.rows),t)
        start=perf_counter_ns()
        choice=choose(deepcopy(self.cfg),deepcopy(view))
        self.computation_audit.append(dict(at=t,elapsed_ns=perf_counter_ns()-start))
        self.decisions.append(dict(view=view,decision=deepcopy(choice)));self.index+=1
        row=choice['request']
        if row is None:return False
        task=self.catalog[row['task']];frame=self.frame(t)
        interventions.record_issue(frame,self.profile,task)
        workforce.submit(frame,task);self.issued.append(row)
        return True
