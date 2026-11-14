"""Expand v2's literal tables into complete qualification inputs; no model import.

Run on an allocated remote node BEFORE running any candidate model. Expected
mechanical values below are transcribed literals, never evaluated from a model.
"""
from copy import deepcopy
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path


BASE = dict(vA=0, vB=1, cA=1, cB=0, sA=1, sB=1, profile='PATH_REF',
            permit=1, accept_enabled=1, ready=1, connected=1, supports=1,
            exec_fault=0, completion='AT')
W0 = dict(BASE, vA=1, profile='LINE_ONLY', completion='BEFORE')
CONTEXT = dict(role='AUDITOR', access_slot='AVAILABLE')
REQUEST = dict(action='READ_B_POSITION', request_id='rq-1', target='feeder-B')
FIELDS = ['ordinary', 'line_present', 'request', 'accepted', 'takeover', 'effective_support']
CASES, PAIRS = [], []


def op(label, name, expected=None, select=None, **args):
    row = dict(label=label, op=name, args=args)
    if expected is not None:
        row['expected'] = deepcopy(expected)
    if select:
        row['select'] = select
    return row


def add(identifier, refs, kind, world, steps, context=None, mode='DEFINITE'):
    CASES.append(dict(id=identifier, source_refs=refs, kind=kind,
                      input=dict(world=deepcopy(world), context=deepcopy(context or CONTEXT), mode=mode),
                      steps=deepcopy(steps)))


def record(value=0, action='READ_B_POSITION', status='KNOWN'):
    quantity, group = (('breaker_position', 'g-pos-B') if action == 'READ_B_POSITION'
                       else ('upstream_voltage', 'g-voltage-B'))
    return dict(record_id='obs-1', target='feeder-B', quantity=quantity, value=value,
                status=status, physical_provenance_group=group, observed_at='e2',
                available_at='e3', expires_at='e4', receiver='AUDITOR',
                request_id='rq-1', action=action)


def view(event, observation, context=None, admission='ADMITTED', copies=()):
    """Literal public encoding of the specification's five-event view table."""
    context = context or CONTEXT
    states = {'e0': (None, 'NONE', False), 'e1': ('PENDING', 'RESERVED', False),
              'e2': ('PENDING', 'RELEASED', True),
              'e3': ('RESULT_AVAILABLE', 'RELEASED', True), 'e4': ('EXPIRED', 'RELEASED', True)}
    status, occupancy, completed = states[event]
    denied = admission != 'ADMITTED' and event != 'e0'
    if denied:
        status, occupancy, completed = 'REJECTED', 'NONE', False
    published = event in ('e3', 'e4') and not denied
    return dict(event=event, context=deepcopy(context), target='feeder-B',
                supported_actions=['READ_B_POSITION', 'READ_B_VOLTAGE'],
                request_status=status, admission=None if event == 'e0' else admission,
                occupancy=occupancy, completed=completed,
                current_observations=[deepcopy(observation)] if published and event == 'e3' else [],
                history=[deepcopy(observation), *deepcopy(list(copies))] if published else [])


def lifecycle(observation, context=None, request=None, admission='ADMITTED', through='e4'):
    context, request = context or CONTEXT, request or REQUEST
    steps = [op('e0_view', 'view', view('e0', observation, context, admission))]
    for event in ['e1', 'e2', 'e3', 'e4']:
        steps.append(op(event + '_advance', 'advance', event=event))
        if event == 'e1':
            steps.append(op('request', 'request', admission, payload=request))
        steps.append(op(event + '_view', 'view', view(event, observation, context, admission)))
        if event == through:
            break
    return steps


def world_audit(world, admissions=1, acquisitions=1, groups=('g-pos-B',)):
    return op('private_integrity', 'audit', dict(state=world, admissions=admissions,
              acquisitions=acquisitions, provenance_groups=list(groups)),
              ['state', 'admissions', 'acquisitions', 'provenance_groups'])


def public_pair(left, right, labels, refs):
    PAIRS.append(dict(id=f'{left}--{right}', left=left, right=right, labels=labels,
                      expected='IDENTICAL_PUBLIC_OUTPUT', source_refs=refs))


def build():
    # P: full local truth table, applied to each ordinary path.
    p_rows = [(0,0,0,0),(0,0,1,0),(0,1,0,0),(0,1,1,0),
              (1,0,0,0),(1,0,1,0),(1,1,0,0),(1,1,1,1)]
    for path in ('A', 'B'):
        for index, (v,c,s,answer) in enumerate(p_rows):
            w = dict(BASE, vA=0, vB=0)
            w.update({f'v{path}':v, f'c{path}':c, f's{path}':s})
            add(f'P-{path}-{index}', ['P', 'Q01', 'Q02'], 'physical', w,
                [op('path', 'mechanics', {f'path{path}':answer}, [f'path{path}'])])
    for a,b,answer in [(0,0,0),(0,1,1),(1,0,1),(1,1,1)]:
        add(f'AGG-{a}{b}', ['AGG', 'Q01'], 'physical', dict(BASE,vA=1,vB=1,cA=a,cB=b),
            [op('aggregate','mechanics',dict(pathA=a,pathB=b,ordinary=answer),['pathA','pathB','ordinary'])])
    for label,patch,line,ordinary,line_request,path_request in [
        ('00',dict(vB=0),0,0,1,1),('10',{},1,0,0,1),('11',dict(vA=1),1,1,0,0)]:
        for profile,answer in [('LINE_ONLY',line_request),('PATH_REF',path_request)]:
            add(f'K-{label}-{profile}', ['K','Q03'], 'physical',dict(BASE,**patch,profile=profile),
                [op('control','mechanics',dict(line_present=line,ordinary=ordinary,request=answer),
                    ['line_present','ordinary','request'])])
    m_rows = [({},[0,1,1,1,1,1]),({'profile':'LINE_ONLY'},[0,1,0,0,0,0]),
        ({'permit':0},[0,1,1,0,0,0]),({'accept_enabled':0},[0,1,1,0,0,0]),
        ({'ready':0},[0,1,1,1,0,0]),({'connected':0},[0,1,1,1,0,0]),
        ({'supports':0},[0,1,1,1,0,0]),({'exec_fault':1},[0,1,1,1,0,0]),
        ({'completion':'BEFORE'},[0,1,1,1,0,0]),({'vA':1},[1,1,0,0,0,1]),
        ({'cB':1},[1,1,0,0,0,1]),({'vB':0},[0,0,1,1,1,1]),
        ({'vB':0,'profile':'LINE_ONLY'},[0,0,1,1,1,1]),
        ({'cB':1,'sB':0},[0,1,1,1,1,1]),({'vA':1,'profile':'LINE_ONLY'},[1,1,0,0,0,1])]
    for index,(patch,expected) in enumerate(m_rows,1):
        add(f'M{index:02}',[f'M{index:02}','Q04','Q05'], 'physical',dict(BASE,**patch),
            [op('mechanics','mechanics',dict(zip(FIELDS,expected)),FIELDS)])
    # Full PRE lifecycles: values are specified explicitly, not read from world fields.
    specifications = [
        ('I-P-W0',W0,REQUEST,record(0),['I01','I02','I03','I04','I05','I06']),
        ('I-P-W1',dict(W0,cB=1),REQUEST,record(1),['I01','I02','I03','I04','I05']),
        ('I-P-W2',dict(W0,ready=0),REQUEST,record(0),['I06']),
        ('I-V-W0',W0,dict(REQUEST,action='READ_B_VOLTAGE'),record(1,'READ_B_VOLTAGE'),['I07','I13','I14','I15','I16','I17']),
        ('I-V-W1',dict(W0,cB=1),dict(REQUEST,action='READ_B_VOLTAGE'),record(1,'READ_B_VOLTAGE'),['I07']),
        ('I-V-W3',dict(W0,vB=0),dict(REQUEST,action='READ_B_VOLTAGE'),record(0,'READ_B_VOLTAGE'),['I13','I14','I15','I16','I17'])]
    for name,w,request,obs,refs in specifications:
        add(name,refs+['Q08'], 'pre',w,lifecycle(obs,request=request)+[
            world_audit(w,groups=(obs['physical_provenance_group'],))])
    for identifier,mode in [('I08','INCONCLUSIVE'),('I09','CHANNEL_FAILED')]:
        add(identifier,[identifier,'B05','Q06','Q11-defined'], 'pre',W0,
            lifecycle(record('UNKNOWN',status='NO_RESULT'))+[world_audit(W0)],mode=mode)
    for identifier,ctx,denial in [('I10',dict(CONTEXT,role='GUEST'),'ACCESS_DENIED'),
        ('I11',dict(CONTEXT,access_slot='EXHAUSTED'),'RESOURCE_UNAVAILABLE'),
        ('I12',dict(role='GUEST',access_slot='EXHAUSTED'),'ACCESS_DENIED')]:
        add(identifier,[identifier,'B05','Q09','Q11-defined'], 'pre',W0,
            lifecycle(record(),ctx,admission=denial)+[world_audit(W0,0,0,())],ctx)
    labels=['e0_view','e1_view','e2_view','e3_view','e4_view']
    public_pair('I-P-W0','I-P-W1',labels[:3],['I01','I02','I03','Q08'])
    public_pair('I-P-W0','I-P-W2',labels,['I06','Q08'])
    public_pair('I-V-W0','I-V-W1',labels,['I07','Q08'])
    public_pair('I-V-W0','I-V-W3',labels[:3],['I13','I14','I15','Q08'])
    public_pair('I08','I09',labels,['I08','I09','Q09'])
    # Material audit cannot modify the authoritative publication ledger or physics.
    obs=record()
    add('B01',['B01','Q07'],'pre',W0,lifecycle(obs,through='e3')+[
        op('duplicate','material','ACCEPTED',payload={'records':[obs,obs]}),
        op('duplicate_again','material','ACCEPTED',payload={'records':[obs]}),
        op('after','view',view('e3',obs)),world_audit(W0)])
    for event in ('e3','e4'):
        copied=dict(obs,record_id='obs-copy',copy_of='obs-1',copy_received_at=event)
        add('B02-'+event,['B02','Q07'],'pre',W0,lifecycle(obs,through=event)+[
            op('copy','material','ACCEPTED',payload={'records':[obs,copied]}),
            op('repeat_copy','material','ACCEPTED',payload={'records':[obs,copied]}),
            op('after','view',view(event,obs,copies=[copied])),world_audit(W0)])
    add('B03',['B03','Q07'],'physical',dict(BASE,profile='LINE_ONLY'),[
        op('plc','mechanics',dict(plc_requests=[0,0],plc_source_groups=[['g-voltage-A','g-voltage-B']]*2),
           ['plc_requests','plc_source_groups'])])
    copied=dict(obs,record_id='obs-copy',copy_of='obs-1',copy_received_at='e3')
    for identifier,event,records,answer,copies in [
        ('B04a','e0',[obs],'INVALID_MATERIAL',[]),('B04b','e3',[],'INVALID_MATERIAL',[]),
        ('B04c','e3',[record(1)],'INVALID_MATERIAL',[]),
        ('B04d-reversed','e3',[copied,obs],'ACCEPTED',[copied]),
        ('B04d-original','e3',[obs,copied],'ACCEPTED',[copied])]:
        before=lifecycle(obs,through=event) if event!='e0' else [op('e0_view','view',view('e0',obs))]
        add(identifier,['B04',identifier.split('-')[0],'Q10'],'pre',W0,before+[
            op('material','material',answer,payload={'records':records}),
            op('after','view',view(event,obs,copies=copies)),
            world_audit(W0,0 if event=='e0' else 1,0 if event=='e0' else 1,() if event=='e0' else ('g-pos-B',))])
    for origin in ('M01','M02','I-P-W0','I-P-W1'):
        case=deepcopy(next(c for c in CASES if c['id']==origin))
        case.update(id='B06-'+origin,source_refs=['B06','Q12'])
        CASES.append(case)
        public_pair(origin,case['id'],[s['label'] for s in case['steps'] if 'expected' in s],['B06','Q12'])
    # Explicit domain refusals, no derived answer computations.
    for identifier,patch,drop in [('X01-missing',{},'cB'),('X01-unknown',{'ready':'UNKNOWN'},None),
        ('X01-profile',{'profile':'UNKNOWN'},None),('X02-ordinary',{'ordinary':1},None),
        ('X02-takeover',{'takeover':1},None),('X05-path',{'third_path':{}},None),
        ('X05-seconds',{'seconds':300},None),('X05-Netherlands',{'site':'Netherlands'},None),
        ('X05-RESP',{'phase':'RESP'},None)]:
        w=dict(W0,**patch)
        if drop:del w[drop]
        add(identifier,[identifier.split('-')[0],'Q12'],'invalid_world',w,[])
        CASES[-1]['expected_constructor_error']='ValueError'
    for identifier,request in [
        ('X03-ready',dict(REQUEST,ready=1)),('X03-world',dict(REQUEST,world_id='W0')),
        ('X03-role',dict(REQUEST,role='AUDITOR')),('X03-slot',dict(REQUEST,access_slot='AVAILABLE')),
        ('X03-action',dict(REQUEST,action='REPAIR')),('X05-asset',dict(REQUEST,target='feeder-C'))]:
        add(identifier,[identifier.split('-')[0],'Q09','Q12'],'pre',W0,
            lifecycle(obs,request=request,admission='INVALID_REQUEST')+[world_audit(W0,0,0,())])
    for identifier,event in [('X03-repeat','e1'),('X03-late','e2')]:
        steps=lifecycle(obs,through=event)
        steps += [op('invalid_request','request','INVALID_REQUEST',payload=REQUEST),
                  op('unchanged','view',view(event,obs)),world_audit(W0,1,0 if event=='e1' else 1,())]
        add(identifier,['X03','Q09','Q12'],'pre',W0,steps)
    add('X03-late-without-prior',['X03','Q09','Q12'],'pre',W0,[
        op('e1','advance',event='e1'),op('e2','advance',event='e2'),
        op('late','request','INVALID_REQUEST',payload=REQUEST),
        op('after','view',view('e2',obs,admission='INVALID_REQUEST')),world_audit(W0,0,0,())])
    for event in ('e0','e1','e2','e3','e4'):
        for forbidden in ('future_challenge','private_configuration'):
            records=[obs] if event in ('e3','e4') else []
            before=lifecycle(obs,through=event) if event!='e0' else [op('e0_view','view',view('e0',obs))]
            add(f'X04-{forbidden}-{event}',['X04','Q10'],'pre',W0,before+[
                op('material','material','INVALID_MATERIAL',payload={'records':records,forbidden:'forbidden'}),
                op('after','view',view(event,obs))])
    for event in ('e1','e2'):
        add('X04-unarrived-'+event,['X04','Q10'],'pre',W0,lifecycle(obs,through=event)+[
            op('material','material','INVALID_MATERIAL',payload={'records':[obs]}),
            op('after','view',view(event,obs))])
    next(c for c in CASES if c['id']=='B04a')['source_refs'].append('X04')
    # Q03: one live instance per route, full expected states at all events.
    for route,profile,before_tuple,at_tuple in [
        ('T-LON','LINE_ONLY',[0,1,0,0,0,0],[0,1,0,0,0,0]),
        ('T-REF','PATH_REF',[0,1,1,1,0,0],[0,1,1,1,1,1])]:
        w=dict(W0,profile=profile);after=dict(w,vA=0);at=dict(after,completion='AT')
        frozen=dict(state=w,public_view=view('e4',obs),challenge={'vA':0,'completion':'AT'})
        steps=lifecycle(obs)
        for event,state,values in [('f',w,[1,1,0,0,0,1]),('u',after,before_tuple),
                                   ('j_before',after,before_tuple),('j_at',at,at_tuple)]:
            steps.append(op(event+'_advance','advance',event=event))
            steps.append(op(event+'_audit','audit',dict(state=state,frozen=frozen,
                outcome=dict(zip(FIELDS,values))),['state','frozen','outcome']))
            if event!='f':
                steps[-1]['same_as']={'path':'state_identity','label':'f_audit','reference_path':'state_identity'}
            steps.append(op(event+'_public','view',view('e4',obs)))
        add(route,[route,'Q03','Q10','Q12'],'challenge',w,steps)
    return dict(schema='aegisdc-london-pre-qualification-inputs-v1',specification_revision='747f1678880881b7bebc4dfa26e5557f4750cc89',
        unit_definition='One complete constructor input plus sequential public/evaluator operations. Lifecycle observations are assertions within that unit.',
        cases=CASES,pair_assertions=PAIRS,
        deferred=[dict(item=x,status='DEFERRED_UNCOVERED',executed=False,waived=False) for x in
                  ['Q11 escalation workflow','Q11 revision implementation','Q11 reverification']],
        expected_provenance='Literal P/K/aggregation and M/T rows, literal observation templates and v2 lifecycle rules; no candidate-model outputs or imports.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise SystemExit('Remote Slurm allocation required')
    packet=build()
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(packet,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(units=len(CASES),pair_assertions=len(PAIRS),sha256=sha256(args.output.read_bytes()).hexdigest(),model_calls=0)))
