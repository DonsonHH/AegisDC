"""T3 native adapter fork with the maintenance service state and shared admission boundary."""
from copy import deepcopy
from math import inf
from unittest.mock import patch
from common import H,CLOCK,CORE,insist,digest
import sys
from plant_cost import Maintenance,indicated
from aegis_action_cost.permit import Gate,exposure
from public_work import choose,key,entries
from incident_facility import London,Netherlands,coupled_class


def native_run(case,role,plan=None,diagnostic_reads=(),*,decider=choose):
    sys.path[:0]=[str(CORE/'src'),str(CORE/'scripts')]
    from aegis_dc import plant,policy_execution,inspection_execution,intervention_execution
    from aegis_dc.decision_view import DecisionGateway
    from aegis_dc.workforce_dispatch import CrewWorkforce
    nat=case['native'];program=nat['dispatch_program'];pub=program['public'];spec=entries(pub)
    limits=case['maintenance'];maintenance=Maintenance(limits['exposure_s'],limits['capacity'])
    gate=Gate(limits['recovery']);proposal_log=[]
    term=None
    if case['attachment']:
        cfg=case['attachment'];term=(London if cfg['kind']=='LONDON' else Netherlands)(cfg)
    attached=term is not None; issued={};epochs=dict.fromkeys(spec,0)
    task_catalog={}
    projected={}
    for arrival,decision,sid,start,sample in diagnostic_reads:
        projected.setdefault(sample,[]).append((sid,start,arrival,decision))
    readonly_samples=[]
    for sid,u in spec.items():
        for ph in ('I','A','R','X','V0','V1','V2','V3'):
            tid=key(sid,ph)
            task_catalog[tid]=dict(id=tid,work_interface_id=u['interface'],target_id=u['write_asset'] if ph=='A' else u['read_asset'],
                crew=[dict(worker_id=u['worker'],qualification_id=u['expertise'])],tool_carrier_id=u['worker'],deadline_s=H,
                source_note='T3 signed synthetic task: '+ph)
    def native_frame(t):
        dispatch=dict(schema='aegisdc-public-preparation-plan-v1',id='minute-v2',basis='synthetic_assumption',time_unit='s',
                      decision_times_s=[t],requests=[])
        return DecisionGateway(program['nominal_knowledge'],program['evidence_ledger'],dispatch).next_frame()

    class Sensors:
        def __init__(self):self.index=0;self.rows=[];self.audit=[];self.status=[]
        def next_event(self):
            return pub['fixed_epochs'][self.index] if self.index<len(pub['fixed_epochs']) else inf
        def process(self,t,snap):
            for sid,start,arrival,decision in projected.get(t,[]):
                typ=spec[sid]['key']
                if typ=='C':fields={'q':snap['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s']}
                elif typ=='N':
                    g=next(v['value'] for v in nat['scenario']['parameters'] if v['id']=='network_service_capacity')
                    for e in sorted(nat['boundary_events'],key=lambda e:e['time_s']):
                        if e['parameter_id']=='network_service_capacity' and e['time_s']<=t:g=e['value']
                    fields={'g':g,'e':snap['domains']['it_service']['capacities']['network']}
                else:fields=term.measure(typ)
                readonly_samples.append(dict(subject=sid,start=start,sampled=t,would_arrive=arrival,usable=decision,fields=fields))
            if attached and isinstance(term,Netherlands) and term.returned and not self.status:
                self.status.append(dict(kind='status',subject='NP',source='controller-work-channel',origin='return-ack',
                    copied_from=None,sampled=t,arrived=t+15,until=H+1,value='POWER_RETURNED'))
            if t<self.next_event():return
            insist(t==self.next_event(),'fixed epoch')
            self.index+=1;dom=snap['domains'];it=dom['it_service']
            values={'service':it['delivered']>=1}
            for sid,z in spec.items():
                k=z['key']
                if k=='C':v=.099<=dom['facility_cooling']['lake_pump']['volume_flow_m3_s']<=.101
                elif k=='N':v=it['capacities']['network']>=1
                elif k=='LC':v=term.source!='NONE'
                elif k=='LB':v=term.b
                elif k=='LG':v=term.ready
                elif k=='NR':v=not term.tripped
                elif k=='NP':v=term.controller and term.pump and not term.latched
                elif k=='NC':v=term.commissioned
                else:raise ValueError(k)
                values[sid]=v
            for field,v in values.items():
                physical_field=spec[field]['key'] if field!='service' else 'service'
                self.rows.append(dict(field=field,ok=v,source='meter/'+field,origin=f'meter/{physical_field}@{t:g}',
                                      sampled=t,arrived=t+15,until=t+pub['fixed_ttl']))
            self.audit.append(t)

    class Inspection:
        def __init__(self,*_):self.rows=[];self.done=set();self.clock=0
        def process(self,t,wf,snapshot):
            self.clock=t
            for w in wf.records:
                tid=w['id']
                if tid in self.done or w['status'] not in ('completed','rejected','aborted'):continue
                self.done.add(tid);r=issued[tid];sid,ph=r['subject'],r['phase'];u=spec[sid]
                if ph=='A':continue
                if w['status']!='completed' or ph.startswith('V'):continue
                insist(w['completed_at_s']==t and w['issued_at_s']==r['at'] and w['tool_carrier_id']==u['worker']
                       and w['target_id']==u['read_asset'] and t-w['work_started_at_s']>=30,'real paid work')
                lo,hi=u['renew_window'] if ph=='X' else u['read_window']
                allowed=lo<=r['at']<=t<hi and (ph!='I' or u['allow_initial'])
                fields=None
                if allowed:
                    if u['key']=='C':fields={'q':snapshot['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s']}
                    elif u['key']=='N':fields={'g':wf.p['network_service_capacity'],'e':snapshot['domains']['it_service']['capacities']['network']}
                    else:fields=term.measure(u['key'])
                self.rows.append(dict(task=tid,subject=sid,phase=ph,source='onsite/'+sid,origin=f'{tid}@{t:g}',
                    worker=u['worker'],tool=u['tool'],issued=r['at'],sampled=t,arrived=t+pub['latency'],until=t+pub['paid_ttl'],
                    parent=r['parent'],execution=r['execution'],parent_epoch=r['parent_epoch'],physical_epoch=epochs[sid],fields=fields))
        def public_feedback(self,t):return [r for r in self.rows if r['arrived']<=t]
        def snapshot(self,t):return dict(as_of_s=t,records=self.public_feedback(t))
        def public_models(self):return dict(issued_only=True,subjects=list(spec),paid_ttl=pub['paid_ttl'])
        def private_audit(self):return dict(events=self.rows)

    class Effects:
        def __init__(self,*_):self.rows=[];self.events=[];self.done=set()
        def record_issue(self,*args):pass
        def process(self,t,wf,params):
            result=[]
            for w in wf.records:
                tid=w['id']
                if not tid.endswith('::A') or tid in self.done or w['status'] not in ('completed','aborted','rejected'):continue
                self.done.add(tid);r=issued[tid];sid=r['subject'];u=spec[sid];op=u['operation'];lo,hi=u['write_window']
                ok=(w['status']=='completed' and w['completed_at_s']==t and r['at']==w['issued_at_s'] and
                    w['target_id']==u['write_asset'] and w['tool_carrier_id']==u['worker'] and lo<=r['at']<=t<hi and t-w['work_started_at_s']>=30)
                if ok:
                    needed=indicated(u['key'],params,term)
                    if op=='clean_filter':params['filter_resistance_multiplier']=1
                    elif op=='restore_network':params['network_service_capacity']=1
                    else:ok=term.apply(op,t)
                if ok:
                    epochs[sid]+=1
                    maintenance.accepted(tid,t,needed)
                row=dict(task=tid,subject=sid,operation=op,at=t,arrived=t+15,execution=tid+'@'+format(t,'g') if ok else None,
                         epoch=epochs[sid],source='work-execution',origin='write/'+tid,outcome='APPLIED' if ok else 'NO_EFFECT')
                self.rows.append(row)
                self.events.append(dict(row,task_id=tid,operation_id=op,applied_at_s=t if ok else None,physical_target=u['write_asset']))
                if ok:result.append(deepcopy(self.events[-1]))
            return result
        def public_feedback(self,t):return [r for r in self.rows if r['arrived']<=t]
        def private_audit(self):return dict(events=self.events)

    class Session:
        def __init__(self,prog,duration):
            insist(prog==program and duration==H,'bound runtime')
            self.program=prog;self.idx=0;self.decisions=[];self.computation_audit=[];self.sensors=Sensors()
            initial=native_frame(0)
            self.work_program=dict(schema='aegisdc-work-program-v2',id='t3-crew',profile=pub['workforce'],initial_frame=initial,submissions=[])
            self.catalog_program=dict(schema='aegisdc-work-program-v1',id='t3-catalog',profile=pub['workforce'],
                                      submissions=[dict(frame=initial,task=z) for z in task_catalog.values()])
            self.inspection_program={'schema':'t3-named-paid-v2'};self.intervention_program={'schema':'t3-named-operations-v2'}
        def next_event(self,t):
            return min(CLOCK[self.idx] if self.idx<len(CLOCK) else inf,self.sensors.next_event())
        def process(self,t,wf,readings,effects):
            if self.idx>=len(CLOCK) or t<CLOCK[self.idx]:return False
            insist(t==CLOCK[self.idx] and isinstance(wf,CrewWorkforce),'public wake')
            view=dict(time=t,records=[r for r in program['channel']+self.sensors.status if r['arrived']<=t],
                work=wf.public_feedback(t),paid=readings.public_feedback(t),writes=effects.public_feedback(t),
                fixed=[r for r in self.sensors.rows if r['arrived']<=t],issued=list(issued.values()))
            # Plain public objects only. Fixed baselines never receive a private plan.
            proposal=decider(pub,deepcopy(view),role,plan if role in ('ORACLE','ENGINEERING') else {})
            decision=deepcopy(proposal)
            request=proposal['request']
            rejection=None
            if request:
                accepted,reason=gate.admit(pub,view,spec[request['subject']],request['phase'],request['patrol_slot'])
                if accepted is None:
                    insist(reason=='MAINTENANCE_CHANGE_BUSY','proposal outside previous public permission')
                    rejection=reason
                    decision['refusals'].append([request['subject'],request['phase'],reason])
                    decision['request']=None
                else:insist(accepted==request,'public request identity')
            proposal_log.append(dict(at=t,view=digest(view),proposal=digest(proposal),requested=request,external_refusal=rejection))
            self.decisions.append(dict(view=deepcopy(view),decision=deepcopy(decision)));self.idx+=1
            self.computation_audit.append(dict(at=t))
            req=decision['request']
            if req is None:return False
            tid=req['task'];insist(tid not in issued,'unique task');issued[tid]=deepcopy(req)
            wf.submit(native_frame(t),task_catalog[tid]);return True

    from contextlib import ExitStack
    with ExitStack() as stack:
        for mod,field,impl in [(policy_execution,'PolicySession',Session),(inspection_execution,'InspectionSession',Inspection),
                               (intervention_execution,'InterventionSession',Effects)]:
            stack.enter_context(patch.object(mod,field,impl))
        base=plant._Plant if term is None else coupled_class(plant._Plant,term)
        stack.enter_context(patch.object(plant,'_Plant',maintenance.attach(base)))
        run=plant.simulate_scenario(**nat)
    run['t3_received_attachment_sha256']=digest(term.cfg if term is not None else None)
    run['t3_unpurchased_evaluator_only']=readonly_samples
    run['v3_maintenance_events']=maintenance.entries
    run['v3_proposals']=proposal_log
    run['v3_received_maintenance']=deepcopy(limits)
    return run,dict(events=term.events,account=term.account()) if term is not None else None
