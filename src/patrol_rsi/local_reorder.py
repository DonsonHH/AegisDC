"""Round obligations and a separate finite local-permutation safety proof."""
from itertools import permutations
import math

from .facility_observation import eligible


class RoundLedger:
    def __init__(self,tour):
        self.tour=tuple(int(j) for j in tour)
        if not self.tour or len(set(self.tour))!=len(self.tour):raise ValueError('Unique owned tour')
        self.remaining=list(self.tour);self.committed=[];self.inflight=None
        self.round_id=0;self.completed=[]

    def window(self):return self.remaining[:3]

    def commit(self,order):
        order=list(order)
        if self.committed or self.inflight is not None:raise ValueError('Finish committed segment before replanning')
        if len(order)!=len(self.window()) or set(order)!=set(self.window()):raise ValueError('Permutation of current window only')
        self.committed=order

    def dispatch(self,j):
        if self.inflight is not None or not self.committed or self.committed[0]!=j:raise ValueError('Committed head only')
        self.inflight=j

    def complete(self,j):
        if self.inflight!=j or not self.committed or self.committed[0]!=j or j not in self.remaining:
            raise ValueError('Actual obligation can settle only once')
        key=(self.round_id,j)
        if key in self.completed:raise ValueError('Duplicate round settlement')
        self.completed.append(key);self.committed.pop(0);self.remaining.remove(j);self.inflight=None
        if not self.remaining:
            if self.committed:raise ValueError('Round cannot finish with pending segment')
            self.round_id+=1;self.remaining=list(self.tour)
        return key


class LocalPlanChecker:
    def __init__(self,graph,tasks,tour,deadlines,role):
        self.graph,self.tasks,self.tour,self.deadlines,self.role=graph,tasks,tuple(tour),deadlines,role
        if not self.tour or len(set(self.tour))!=len(self.tour):raise ValueError('Owned partition')
        if not all(eligible(role,tasks[j]) for j in self.tour):raise ValueError('Original profession/access contract')
        self.edge={}
        for j in self.tour:
            for k in self.tour:
                distance=graph.path(tasks[j].position_m,tasks[k].position_m)[0]
                self.edge[j,k]=(float(distance),self.duration(distance,tasks[k].service_s))
        self.period=sum(self.edge[a,b][1] for a,b in zip(self.tour[-1:]+self.tour[:-1],self.tour))
        if any(self.period>deadlines[j]+1e-9 for j in self.tour):raise ValueError('Original repeated tour infeasible')

    @staticmethod
    def duration(distance,service):return float(math.ceil((distance+service)/5.-1e-10)*5.)

    def travel_service(self,position,j):
        distance=float(self.graph.path(tuple(position),self.tasks[j].position_m)[0])
        return distance,self.duration(distance,self.tasks[j].service_s)

    def check(self,clock,position,last,remaining,segment,reserved):
        remaining=list(remaining);segment=list(segment)
        if not remaining or len(set(remaining))!=len(remaining) or not set(remaining)<=set(self.tour):raise ValueError('Round remaining contract')
        if not 1<=len(segment)<=3 or len(set(segment))!=len(segment) or set(segment)!=set(remaining[:len(segment)]):
            raise ValueError('Current committed prefix permutation')
        if set(segment)&set(reserved):return {'ok':False,'reason':'task_reservation'}
        restore=[j for j in remaining if j not in segment]+list(self.tour)
        sequence=segment+restore
        virtual={j:max(0.,float(last[j])) for j in self.tour}
        first={};times=[];dues=[];travel=[];t=float(clock);previous=None;slack=float('inf')
        for index,j in enumerate(sequence):
            distance,duration=self.travel_service(position,j) if previous is None else self.edge[previous,j]
            t+=duration;due=virtual[j]+float(self.deadlines[j])
            if t>due+1e-9:
                return {'ok':False,'reason':'delayed_task_deadline','failed_task':j,'finish_s':t,'due_s':due,'sequence_index':index}
            first.setdefault(j,t);virtual[j]=t;times.append(t);dues.append(due);travel.append(distance)
            slack=min(slack,due-t);previous=j;position=self.tasks[j].position_m
        return {'ok':True,'clock_s':float(clock),'segment':segment,'remaining_before':remaining,
            'proof_sequence':sequence,'completion_s':times,'due_s':dues,
            'segment_completion_s':times[:len(segment)],'first_completion_s':first,
            'segment_and_bridge_travel_s':sum(travel[:len(segment)+1]),
            'minimum_slack_s':slack,'restored_period_s':self.period}

    def candidates(self,clock,position,last,remaining,reserved):
        window=list(remaining[:3]);result=[]
        for order in permutations(window):
            certificate=self.check(clock,position,last,remaining,order,reserved)
            result.append({'order':list(order),'original':list(order)==window,'certificate':certificate})
        return result
