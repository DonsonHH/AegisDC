"""Evidence-only work intentions and opt-in private timed crew execution."""
from copy import deepcopy
import math

from .decision_view import validate_current_frame, _assessment
from .evidence_ledger import _plain_json
from .thermodynamics import finite_number
from .workforce import Workforce

PROFILE_FIELDS = {'schema','id','facility_id','nominal_knowledge_id','basis','source_note','time_unit',
                  'access_check_s','feedback_latency_s','walk_times_s','work_times_s','shifts'}
TASK_FIELDS = {'id','work_interface_id','target_id','crew','tool_carrier_id','deadline_s','source_note'}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def fields(value, names, label):
    require(type(value) is dict and set(value)==names, label+' fields differ from the closed contract')

def text(value, label):
    require(type(value) is str and bool(value.strip()), label+' requires nonempty text')

def validate_profile(profile, knowledge):
    _plain_json(profile); fields(profile,PROFILE_FIELDS,'Workforce profile')
    require(profile['schema']=='aegisdc-workforce-profile-v1' and profile['basis']=='synthetic_assumption'
            and profile['time_unit']=='s', 'Declare synthetic workforce timing in SI seconds')
    for key in ('id','source_note'):text(profile[key],key)
    require(profile['facility_id']==knowledge['facility_id'] and profile['nominal_knowledge_id']==knowledge['id'],
            'Workforce profile differs from public facility/nominal identity')
    finite_number(profile['access_check_s'],'Access check',positive=True)
    require(finite_number(profile['feedback_latency_s'],'Feedback latency')>=0,'Negative feedback latency')
    for name, identifiers in (('walk_times_s',{e['id'] for e in knowledge['graphs']['access']}),
                              ('work_times_s',{w['id'] for w in knowledge['work_interfaces']})):
        require(type(profile[name]) is dict and set(profile[name])==identifiers,'Timing IDs differ: '+name)
        for value in profile[name].values():finite_number(value,name,positive=True)
    workers={e['id'] for e in knowledge['entities'] if e['kind']=='worker'}
    require(type(profile['shifts']) is dict and set(profile['shifts'])==workers,'Declare each worker shift')
    for shift in profile['shifts'].values():
        require(type(shift) is list and len(shift)==2,'Shift must be [start,end]')
        start,end=(finite_number(x,'Shift') for x in shift)
        require(0<=start<end,'Shift interval must be positive and nonnegative')
    return deepcopy(profile)

def prepare_work(frame, profile, task):
    """Assess one issued intention from current public records; no plant query."""
    frame=validate_current_frame(frame);profile=validate_profile(profile,frame['nominal_knowledge'])
    _plain_json(task);fields(task,TASK_FIELDS,'Crew intention')
    for key in TASK_FIELDS-{'crew','deadline_s'}:text(task[key],key)
    require(finite_number(task['deadline_s'],'Work deadline')>=frame['as_of_s'],'Deadline precedes issue time')
    require(type(task['crew']) is list and bool(task['crew']),'Declare a nonempty crew')
    entities={e['id']:e for e in frame['nominal_knowledge']['entities']}
    interfaces={w['id']:w for w in frame['nominal_knowledge']['work_interfaces']}
    require(task['work_interface_id'] in interfaces and task['target_id'] in entities,'Unknown work identity')
    crew=[];reasons=[];assessments=[]
    for role in task['crew']:
        fields(role,{'worker_id','qualification_id'},'Crew role')
        for key in role:text(role[key],key)
        worker=entities.get(role['worker_id'])
        require(worker is not None and worker['kind']=='worker','Crew member must be a declared worker')
        require(role['worker_id'] not in crew,'A worker cannot fill two simultaneous crew roles')
        crew.append(role['worker_id'])
        if role['qualification_id'] not in frame['nominal_knowledge']['qualification_ids']:
            raise ValueError('Unknown crew qualification')
        if role['qualification_id'] not in worker['qualification_ids']:
            reasons.append('crew_qualification_mismatch:'+role['worker_id'])
        assessment=_assessment(frame,dict(id=task['id'],worker_id=role['worker_id'],
            work_interface_id=task['work_interface_id'],target_id=task['target_id']))
        assessments.append(assessment)
        # The lead/carrier qualifies for the interface; assistants meet their declared role.
        ignored={'nominal_tool_capability_mismatch'}
        if role['worker_id']!=task['tool_carrier_id']:ignored.add('nominal_qualification_mismatch')
        reasons.extend(x+':'+role['worker_id'] for x in assessment['public_reasons'] if x not in ignored)
    require(task['tool_carrier_id'] in crew,'Tool carrier must be a crew member')
    carrier=entities[task['tool_carrier_id']]
    if not set(interfaces[task['work_interface_id']]['tool_ids'])<=set(carrier['tool_ids']):
        reasons.append('nominal_tool_capability_mismatch:'+carrier['id'])
    return dict(schema='aegisdc-work-intention-assessment-v1',task_id=task['id'],as_of_s=frame['as_of_s'],
        legal_for_planning=not reasons,public_reasons=sorted(set(reasons)),
        considered_record_ids=sorted({r for a in assessments for r in a['considered_record_ids']}),
        execution_permission=False,dynamic_execution='PRIVATE_EXECUTOR_CHECKS_REMAIN_REQUIRED',
        basis='CURRENT_PUBLIC_FRAME_AND_DECLARED_STATIC_WORKFORCE_PROFILE_ONLY')

class CrewWorkforce(Workforce):
    """The same facility resources, extended with incremental queues and crew rendezvous."""
    def __init__(self,scenario,parameters,program,duration_s):
        super().__init__(scenario,parameters,[],duration_s)
        _plain_json(program);fields(program,{'schema','id','profile','submissions'},'Work program')
        require(program['schema']=='aegisdc-work-program-v1','Unknown work program schema')
        text(program['id'],'Program id')
        require(type(program['submissions']) is list,'Submissions must be a list')
        require(bool(program['submissions']),'Declare at least one issued work intention')
        first=validate_current_frame(program['submissions'][0]['frame'])
        self.profile=validate_profile(program['profile'],first['nominal_knowledge'])
        require(scenario['id']==self.profile['facility_id'],'Physical/public facility identities differ')
        nominal=first['nominal_knowledge'];self.nominal=deepcopy(nominal);nominal_entities={x['id']:x for x in nominal['entities']}
        require(set(self.entities)==set(nominal_entities),'Physical/public entity identities differ')
        for worker in self.workers:
            require(self.entities[worker]['qualification_ids']==nominal_entities[worker]['qualification_ids']
                    and self.entities[worker]['tool_ids']==nominal_entities[worker]['tool_ids'],
                    'Physical/public worker capabilities differ')
        public_interfaces={w['id']:w for w in nominal['work_interfaces']}
        require(set(self.interfaces)==set(public_interfaces),'Physical/public work interface identities differ')
        for key,interface in self.interfaces.items():
            require(all(interface[name]==public_interfaces[key][name] for name in
                        ('target_ids','qualification_id','tool_ids')),'Physical/public work interface differs')
        public_routes={e['id']:e for e in nominal['graphs']['access']}
        require(set(public_routes)=={e['id'] for e in scenario['graphs']['access']},'Physical/public route identities differ')
        for edge in scenario['graphs']['access']:
            require(all(edge[name]==public_routes[edge['id']][name] for name in
                        ('from','to','bidirectional','requires_qualification_ids')),'Physical/public access graph differs')
            require(self.profile['walk_times_s'][edge['id']]==parameters[edge['duration_parameter']],
                    'Declared walking time differs from physical interface')
        for interface in self.interfaces.values():
            require(self.profile['work_times_s'][interface['id']]==parameters[interface['duration_parameter']],
                    'Declared work time differs from physical interface')
        self.feedback=[];self.pending=[];self.submitted=set();self.jobs={};self.last_time=-math.inf
        self.duration=duration_s;self.requests=[]
        for submission in program['submissions']:
            fields(submission,{'frame','task'},'Work submission')
            frame=validate_current_frame(submission['frame'])
            require(frame['nominal_knowledge']==nominal,'Program public nominal knowledge changed')
            require(0<=frame['as_of_s']<=duration_s,'Issue time outside the facility run')
            prepare_work(frame,self.profile,submission['task'])
            self.requests.append(deepcopy(submission))
        self.requests.sort(key=lambda x:x['frame']['as_of_s'])
        self.program=deepcopy(program)

    def submit(self,frame,task):
        """Admit a currently issued public intention without restarting the executor."""
        require(frame['as_of_s']==self.last_time,'Submission must be issued at the current executor instant')
        require(frame['nominal_knowledge']==self.nominal,'Issued static knowledge differs from the bound public registry')
        assessment=prepare_work(frame,self.profile,task)
        require(task['id'] not in self.submitted,'Duplicate task identity')
        self.submitted.add(task['id'])
        record=dict(deepcopy(task),issued_at_s=self.last_time,accepted=assessment['legal_for_planning'],
                    status='queued' if assessment['legal_for_planning'] else 'rejected',
                    public_assessment=assessment,effect='ENGINEERING_WORK_RECORD_ONLY_NO_REPAIR_OR_EVIDENCE')
        self.records.append(record)
        if not assessment['legal_for_planning']:
            record.update(finished_at_s=self.last_time,reason='public_static_or_reported_restriction');return
        key=(task['work_interface_id'],task['target_id'])
        if any((r['work_interface_id'],r['target_id'])==key and r['status'] not in {'completed','aborted','rejected'}
               for r in self.records if r is not record):
            record.update(status='rejected',accepted=False,finished_at_s=self.last_time,reason='duplicate_open_work');return
        self.pending.append(record)

    def _finish(self,job,time,status,reason):
        record=job['record'];record.update(status=status,finished_at_s=time)
        if status=='completed':record['completed_at_s']=time
        if reason:record['reason']=reason
        for worker in job['crew']:
            self.workers[worker].update(status='idle',request_id=None)
        for identifier in job['tools']:
            self.tools[identifier].update(reserved_by=None,carried_by=None)
        self.feedback.append(dict(task_id=record['id'],source_id='workforce-execution-report',
            observed_at_s=time,arrived_at_s=time+self.profile['feedback_latency_s'],
            status=status,reason=reason,location_id=job['target'] if status=='completed' else None,
            origin_id='workforce:'+record['id'],coverage='THIS_ISSUED_TASK_ONLY',
            basis='SYNTHETIC_FINITE_TIMED_EXECUTION_CHANNEL'))
        del self.jobs[record['id']]

    def _moves(self,worker,carrier,tools,target,time):
        location=self.workers[worker]['location_id'];moves=[]
        destinations=([self.tools[t]['location_id'] for t in tools] if worker==carrier else [])+[target]
        quals=set(self.entities[worker]['qualification_ids'])
        for destination in destinations:
            route=self._path(location,destination,quals,set())
            if route is None:return None
            for start,end,duration in route:
                moves.append(dict(from_id=start,to_id=end,departs_at_s=time,
                    gate_at_s=time+duration,arrives_at_s=time+duration+self.profile['access_check_s']))
                time+=duration+self.profile['access_check_s'];location=end
        if not moves:
            moves.append(dict(from_id=location,to_id=target,departs_at_s=time,gate_at_s=time,
                              arrives_at_s=time+self.profile['access_check_s']))
        return moves

    def _start_queued(self,time):
        for record in list(self.pending):
            if time>=record['deadline_s']:
                record.update(status='rejected',accepted=False,finished_at_s=time,reason='deadline_expired_in_queue')
                self.pending.remove(record);continue
            crew=[r['worker_id'] for r in record['crew']];interface=self.interfaces[record['work_interface_id']]
            tools=interface['tool_ids'];shifts=[self.profile['shifts'][w] for w in crew]
            if time<max(s[0] for s in shifts):continue
            if any(self.workers[w]['status']!='idle' for w in crew) or any(self.tools[t]['reserved_by'] for t in tools):continue
            target_entity=self.entities[record['target_id']]
            target=target_entity['id'] if target_entity['kind']=='location' else target_entity['location_id']
            moves={w:self._moves(w,record['tool_carrier_id'],tools,target,time) for w in crew}
            if any(m is None for m in moves.values()):
                record.update(status='rejected',accepted=False,finished_at_s=time,reason='static_access_unreachable');self.pending.remove(record);continue
            start=max(m[-1]['arrives_at_s'] for m in moves.values());end=start+self.profile['work_times_s'][interface['id']]
            if end>min(record['deadline_s'],*(s[1] for s in shifts),self.p['shift_end_time']):
                record.update(status='rejected',accepted=False,finished_at_s=time,reason='shift_or_deadline_unavailable');self.pending.remove(record);continue
            record.update(status='travelling',started_at_s=time,planned_work_start_s=start,scheduled_completion_at_s=end,
                          paths=deepcopy(moves),queue_wait_s=time-record['issued_at_s'])
            job=dict(record=record,crew=crew,tools=tools,target=target,moves=moves,index={w:0 for w in crew},work_start=None)
            self.jobs[record['id']]=job;self.pending.remove(record)
            for w in crew:self.workers[w].update(status='travelling',request_id=record['id'])
            for t in tools:self.tools[t].update(reserved_by=record['id'],carried_by=None)
            self._pickup_carried(job)

    def _pickup_carried(self,job):
        carrier=job['record']['tool_carrier_id']
        for t in job['tools']:
            if self.tools[t]['location_id']==self.workers[carrier]['location_id']:
                self.tools[t]['carried_by']=carrier

    def _advance_crews(self,time,blocked):
        for job in list(self.jobs.values()):
            record=job['record']
            if job['work_start'] is not None:
                if job['target'] in blocked:self._finish(job,time,'aborted','onsite_safety_stop')
                elif time>=record['scheduled_completion_at_s']:self._finish(job,time,'completed',None)
                continue
            failed=False
            for w in job['crew']:
                moves=job['moves'][w];index=job['index'][w]
                while index<len(moves) and moves[index]['arrives_at_s']<=time:
                    move=moves[index]
                    if move['to_id'] in blocked:
                        self._finish(job,time,'aborted','access_check_blocked');failed=True;break
                    self.workers[w]['location_id']=move['to_id']
                    for t in job['tools']:
                        if self.tools[t]['carried_by']==w:self.tools[t]['location_id']=move['to_id']
                    self._pickup_carried(job);index+=1;job['index'][w]=index
                if failed:break
                self.workers[w]['status']=('waiting' if index==len(moves) or time>=moves[index]['gate_at_s'] else 'travelling')
            if failed:continue
            if all(job['index'][w]==len(job['moves'][w]) for w in job['crew']):
                job['work_start']=time;record.update(status='working',work_started_at_s=time,arrived_at_s=time)
                record['scheduled_completion_at_s']=time+self.profile['work_times_s'][record['work_interface_id']]
                for w in job['crew']:self.workers[w]['status']='working'

    def process(self,time_s,blocked_locations):
        require(time_s>=self.last_time,'Workforce clock cannot move backward');self.last_time=time_s
        self._advance_crews(time_s,blocked_locations)
        while self.index<len(self.requests) and self.requests[self.index]['frame']['as_of_s']<=time_s:
            submission=self.requests[self.index];self.submit(submission['frame'],submission['task']);self.index+=1
        self._start_queued(time_s);self._advance_crews(time_s,blocked_locations)

    def next_event(self,time_s):
        events=[self.requests[self.index]['frame']['as_of_s']] if self.index<len(self.requests) else []
        for record in self.pending:
            events.extend(self.profile['shifts'][r['worker_id']][0] for r in record['crew'])
            events.append(record['deadline_s'])
        for job in self.jobs.values():
            if job['work_start'] is not None:events.append(job['record']['scheduled_completion_at_s'])
            else:
                for w,moves in job['moves'].items():
                    i=job['index'][w]
                    if i<len(moves):events.extend([moves[i]['gate_at_s'],moves[i]['arrives_at_s']])
        return min((x for x in events if x>time_s),default=math.inf)

    def occupation_rates(self):
        result=super().occupation_rates()
        waiting={w for w,state in self.workers.items() if state['status']=='waiting'}
        onsite_waiting=len(waiting)
        waiting.update(r['worker_id'] for task in self.pending for r in task['crew']
                       if self.workers[r['worker_id']]['status']=='idle'
                       and self.profile['shifts'][r['worker_id']][0]<=self.last_time<self.profile['shifts'][r['worker_id']][1])
        checking=sum(job['work_start'] is None and job['index'][w]<len(job['moves'][w])
            and self.last_time>=job['moves'][w][job['index'][w]]['gate_at_s']
            for job in self.jobs.values() for w in job['crew'])
        result.update(worker_wait_person_s=len(waiting),access_check_person_s=checking,
            rendezvous_wait_person_s=onsite_waiting-checking,queue_wait_person_s=len(waiting)-onsite_waiting,
            tool_work_tool_s=sum(len(j['tools']) for j in self.jobs.values() if j['work_start'] is not None))
        return result

    def snapshot(self):
        result=dict(workers=deepcopy(self.workers),tools=deepcopy(self.tools),
                    active_requests=sorted(self.jobs),queued_requests=[r['id'] for r in self.pending])
        for job in self.jobs.values():
            for w,moves in job['moves'].items():
                i=job['index'][w]
                if i<len(moves):
                    row=result['workers'][w];row['last_location_id']=row['location_id'];row['location_id']=None
                    row['travel']=deepcopy(moves[i]);row['stage']='gate_check' if self.last_time>=moves[i]['gate_at_s'] else 'walking'
            for t in job['tools']:
                carrier=self.tools[t]['carried_by']
                if carrier and result['workers'][carrier]['location_id'] is None:
                    result['tools'][t]['last_location_id']=result['tools'][t]['location_id'];result['tools'][t]['location_id']=None
        return result

    def public_feedback(self,as_of_s):
        """Only declared arrived task-local reports; private job records stay private."""
        return deepcopy([row for row in self.feedback if row['arrived_at_s']<=as_of_s])
