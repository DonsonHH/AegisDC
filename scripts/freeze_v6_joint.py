"""Materialize the finite joint engineering inputs without querying the candidate implementation."""
import argparse
from copy import deepcopy
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path

from aegis_dc.native_compare_inputs import Conditions, file_hash
from patrol_rsi.contracts import digest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'docs/mainline/v6-joint-cooling-network-v1/engineering.json'
NORMAL = ROOT / 'evidence/mainline/engineering/11-coupled/fixtures-b135ecff-01/normal-600s/private-state.jsonl'
BASE = '08eed614a77382672ef94c0fb4d9f2f2ce874890'
STATIONS = {
    'C': ('cooling-service-desk', 'intake_pump', 'filter', 'worker_cooling', 'tool_flow_meter',
          'qualified_cooling_inspection', 'inspect_facility_cooling', 'clean_filter', 'loc_lake'),
    'N': ('network-service-desk', 'network', 'network', 'worker_it', 'tool_it_diagnostic',
          'qualified_it_inspection', 'inspect_it_service', 'restore_network_capacity', 'loc_it'),
}


def number(value):
    value = Fraction(str(value))
    return value.numerator if value.denominator == 1 else float(value)


def order(kind, origin, at=0, arrived=None, until=12):
    desk, target = STATIONS[kind][:2]
    return dict(id='desk/' + origin, origin=origin, desk=desk, target=target,
                observable='problem_reported', value=True, at=at, arrived=at if arrived is None else arrived,
                until=until, copied_from=None, revoked_at=None)


def event_view(orders, time=0):
    return dict(time=time, orders=[deepcopy(row) for row in orders if row['arrived'] <= time],
                issued=[], work=[], writes=[], paid=[], fixed=[])


def issue(task, at, release, end):
    return dict(task=task, at=at, release=release, planned_end=end, planned_ack=end + .5)


def work(task, at, arrival=None, status='completed'):
    station=STATIONS[task.split('/')[0]]
    return dict(task=task, at=at, arrived=at+.5 if arrival is None else arrival, status=status,
                location=station[-1] if status=='completed' else None, worker=station[3], tool=station[4],
                origin='workforce:'+task)


def reading(task, field, bounds, at=1.25, arrival=None, ttl=8):
    kind, origin, phase=task.split('/')
    token=f'{task}@{at:g}'
    return dict(task=task, instance=kind+'/'+origin, phase=phase, field=field, target=STATIONS[kind][1],
                unit='m3/s' if field=='q' else '1', interval=bounds, at=at, arrived=at+.5 if arrival is None else arrival,
                until=at+ttl, bundle=token, origin='paid:'+token, source='onsite-'+kind,
                disposition='MEASURED' if bounds is not None else 'FIELD_UNAVAILABLE')


def fixed(field, at, value):
    return dict(field=field, at=at, arrived=at+.5, until=at+3, interval=[value,value],
                origin=f'fixed:{field}@{at:g}', source='fixed-'+field)


def written(task, at, outcome='APPLIED'):
    return dict(task=task, at=at, arrived=at+.5, outcome=outcome,
                operation=STATIONS[task.split('/')[0]][7], origin='intervention:'+task)


def public_config(base, plan, method='J', law='EX50', fee=3, horizon=12, end=12, override=None):
    override=override or {}
    original=base['dispatch_program']
    native=original['policy_program']['workforce_profile']
    nominal=original['nominal_knowledge']
    types={}
    for kind,(desk,target,asset,worker,tool,qualification,interface,operation,location) in STATIONS.items():
        rights={'q':[0,end]} if kind=='C' else {'e':[0,end], 'g':[0,end] if override.get('N_config_read',True) else None}
        types[kind]=dict(desk=desk, target=target, asset=asset, worker=worker, tool=tool, qualification=qualification,
            interface=interface, operation=operation, setting=1, location=location, max_origins=2 if kind=='C' else 1,
            read=rights, write=[0,number(override.get('N_write_expiry_s',end)) if kind=='N' else end],
            require_probe=bool(kind=='N' and override.get('N_write_requires')), work_s=native['work_times_s'][interface])
    actors={row['id']:row for row in nominal['entities']}
    public_actors={v[k] for v in types.values() for k in ('worker','tool')}
    worlds=[]
    for cooling, g, weight, *rest in plan['public_forecast']['tables'].get(law,[]):
        a,s=(rest+[3000000,1])[:2] if rest else (3000000,1)
        worlds.append(dict(origin=f'{cooling}|{Fraction(g)}|{a}|{Fraction(s)}@0', anchor=0, cooling=cooling,
                           g=str(Fraction(g)), A=a, s=str(Fraction(s)), mass=str(Fraction(weight))))
    short=horizon==12
    return dict(schema='aegisdc-joint-problem-policy-v1',method=method,types=types,worlds=worlds,
        horizon=horizon,deadline=end,clock=[k/4 for k in range(49)] if short else [number(x) for x in plan['thermal_input']['public_ticks']],
        forecast_window=[8,12],caps=[60,60,fee],gate=.25,latency=.5,paid_ttl=8,fixed_ttl=3,fee=1,
        fixed_epochs=list(range(6,13)) if short else [6,7],fixed_on=['lake','network','service'],
        pose={k:actors[k]['nominal_location_id'] for k in sorted(public_actors)},
        qualification={t['worker']:actors[t['worker']]['qualification_ids'] for t in types.values()},
        shift={t['worker']:[0,end] for t in types.values()},
        routes=[dict(a=row['from'],b=row['to'],travel=native['walk_times_s'][row['id']],
                     bidirectional=row['bidirectional'],requires=row['requires_qualification_ids']) for row in nominal['graphs']['access']])


def native_task(cfg, kind, origin, phase):
    item=cfg['types'][kind]
    return dict(id=f'{kind}/{origin}/{phase}', work_interface_id=item['interface'],
        target_id=item['asset'] if phase=='A' else item['target'],
        crew=[dict(worker_id=item['worker'],qualification_id=item['qualification'])],
        tool_carrier_id=item['worker'],deadline_s=cfg['deadline'],source_note='Paid scoped facility work')


def materialize_dispatch(base, cfg, orders):
    old=base['dispatch_program']
    profile=deepcopy(old['policy_program']['workforce_profile'])
    profile['shifts'].update(deepcopy(cfg['shift']))
    ledger=deepcopy(old['evidence_ledger'])
    ledger['records']=[]
    operation=deepcopy(old['intervention_program'])
    operation['bindings']=[]
    op_profile=operation['profile']
    op_profile.update(operations=[],authorizations=[])
    tasks=[]
    probes=[]
    for kind,typ in cfg['types'].items():
        op=typ['operation']
        op_profile['operations'].append(dict(id=op,kind=op,target_id=typ['asset'],unit='1',minimum_work_s=1,
            source_note='Authorized named synthetic facility operation'))
        grant='grant-'+kind
        op_profile['authorizations'].append(dict(id=grant,operation_ids=[op],target_ids=[typ['asset']],
            starts_at_s=typ['write'][0],expires_at_s=typ['write'][1],basis='synthetic_assumption',source_note='Finite write window'))
        for origin in sorted({o['origin'] for o in orders if o['desk']==typ['desk'] and o['target']==typ['target']}):
            for phase in ('I','A','R'):
                task=native_task(cfg,kind,origin,phase)
                tasks.append(task)
                if phase=='A':
                    operation['bindings'].append(dict(task_id=task['id'],operation_id=op,setting=1,authorization_id=grant))
                else:
                    probes.append(dict(task=task['id'],target=typ['target'],interface=typ['interface'],
                        tool=typ['tool'],worker=typ['worker'],qualification=typ['qualification'],minimum_work_s=1,
                        fields=deepcopy(typ['read']),ttl=cfg['paid_ttl'],latency=cfg['latency']))
    return dict(schema='aegisdc-policy-run-program-v6',id='joint-facility-engineering',
        policy_program=cfg,nominal_knowledge=old['nominal_knowledge'],workforce_profile=profile,evidence_ledger=ledger,
        order_channel=orders,task_catalog=tasks,intervention_program=operation,
        inspection_program=dict(schema='aegisdc-joint-inspection-v1',bindings=probes))


def warm_initial(params, scenario):
    with NORMAL.open(encoding='utf-8') as stream:
        domains=json.loads(stream.readline())['domains']
    cooling=domains['facility_cooling']
    equipment=domains['equipment_environment']
    for name,val in [('initial_hot_temperature',cooling['hot_temperature_K']),('initial_cold_temperature',cooling['cold_temperature_K']),
                     ('initial_solid_temperature',equipment['solid_temperature_K'])]:
        params[name]['value']=val+20
    target=equipment['refrigerant']['temperature_K']+20
    table=json.loads((ROOT/scenario['runtime']['property_table']).read_bytes())['rows']
    lo,hi=next((a,b) for a,b in zip(table,table[1:]) if a['T_sat_K'] <= target <= b['T_sat_K'])
    f=(target-lo['T_sat_K'])/(hi['T_sat_K']-lo['T_sat_K'])
    props={k:lo[k]+f*(hi[k]-lo[k]) for k in ('v_l_m3_kg','v_v_m3_kg','u_l_J_kg','u_v_J_kg')}
    mass=2000
    x=(6.647467643830208/mass-props['v_l_m3_kg'])/(props['v_v_m3_kg']-props['v_l_m3_kg'])
    params['coolant_initial_energy']['value']=mass*(props['u_l_J_kg']+x*(props['u_v_J_kg']-props['u_l_J_kg']))
    params['lake_temperature']['value']=313.15


def native(base,plan,row,thermal=False):
    override=row.get('overrides',{})
    h,end,dt=(3600,10,number(row['max_step_s'])) if thermal else (12,12,.01)
    cfg=public_config(base,plan,row['method'],row.get('public_law','ref'),override.get('fee_cap',3),h,end,override)
    slots=['C'] if thermal else row['slots'].split(',')
    orders=[order(k,k.lower()+'0',until=end) for k in slots if k in STATIONS]
    if 'openings' in override:
        original=order('C','c0')
        orders=[original,dict(original,id='copy/c0',arrived=.5,copied_from=original['id']),order('C','c1',.5)]
    scenario=deepcopy(base['scenario']);params={p['id']:p for p in scenario['parameters']}
    m,g,s,cap=[1,row['network_g'],1,'A'] if thermal else row['private_tuple']
    for k,v in [('filter_resistance_multiplier',m),('network_service_capacity',g),('storage_service_capacity',s),
                ('rectifier_capacity',550000 if cap=='P' else 5000000),('rectifier_efficiency',.97 if thermal else 1)]:
        params[k]['value']=number(v)
    if thermal:warm_initial(params,scenario)
    events=[dict(time_s=number(t),parameter_id=k,value=number(v),source_note='Frozen independent exogenous event')
            for t,k,v in ([(0,'filter_resistance_multiplier',100)] if thermal else override.get('boundary_events',[]))]
    return dict(scenario=scenario,duration_s=h,step_s=dt,boundary_events=events,action_commands=[],work_requests=[],
                business_program=None,dispatch_program=materialize_dispatch(base,cfg,orders))

def paid_prefix(v, task='N/n0/I', bounds=(1,1), sample=1.25, ttl=8, ack_time=None):
    v['issued'].append(issue(task,0,0,sample))
    if bounds is not None:
        for field,value in zip(('g','e'),bounds):
            v['paid'].append(reading(task,field,None if value is None else [value,value],sample,ttl=ttl))
    if ack_time is not False:
        v['work'].append(work(task,sample,ack_time))
    return v


def policy_fixtures(base,plan):
    inputs={};oracles={}
    for row in plan['policy_cases']:
        id_=row['id'];one=id_ in ('P07','P12')
        cfg=public_config(base,plan,law=row['law'],fee=row['fee_cap'],override={'N_write_requires':one})
        orders=[order('N','n0')] if one else [order('C','c0'),order('N','n0')]
        if id_=='P08':
            cfg['types']=dict(reversed(list(cfg['types'].items())))
            cfg['worlds'].reverse()
            orders.reverse()
        v=event_view(orders)
        if id_ in ('P09','P10','P11','P12'):
            v['time']=1.5 if id_=='P09' else 1.75
            if id_=='P09':paid_prefix(v,bounds=None,ack_time=False)
            else:paid_prefix(v,bounds={'P10':(1,1),'P11':(.25,.25),'P12':(None,.25)}[id_])
        for method in ('J','B'):
            key=id_+'-'+method;inputs[key]=dict(program=dict(cfg,method=method),view=deepcopy(v))
            expected=row['expected']; result=dict(first=expected[method])
            if 'loss_hold_C_N' in expected:result['loss_hold_C_N']=expected['loss_hold_C_N']
            if id_ in ('P05','P13'):result['loss_both']=0 if id_=='P05' else 4
            if id_ in ('P06','P08'):result['best_probe_work']={'N.I':'19/4','C.I':'23/4'}
            oracles[key]=result
    return inputs,oracles


def guard_fixtures(base,plan):
    cfg=public_config(base,plan,law='BOTH',fee=4)
    all_orders=[order('C','c0'),order('N','n0')]
    n='N/n0';c='C/c0'
    inputs={};expected={}
    def add(i,op,view,oracle,config=cfg,**args):
        key=f'G{i:02d}';inputs[key]=dict(op=op,program=deepcopy(config),view=deepcopy(view),args=args)
        expected[key]=oracle
    for i,values,category in [(1,(.25,.25),'CONFIG_LIMIT_CURRENT'),(2,(1,.25),'SUPPLY_LIMIT_CURRENT'),
                              (3,(.25,11/170),'MIXED_LIMIT_CURRENT'),(4,(1,1),'LOCAL_ADEQUATE'),
                              (5,(1,1),'UNKNOWN'),(6,(.25,.25),'UNKNOWN'),(7,(None,.25),'EFFECTIVE_LOW_CAUSE_UNKNOWN'),
                              (8,(.25,.25),'PENDING'),(9,(.25,.25),'PENDING'),
                              (10,(1,1),'PENDING'),(11,(1,1),'CONFLICT')]:
        v=event_view(all_orders,1.75)
        paid_prefix(v,bounds=values,ttl={8:1.25,9:1}.get(i,8),ack_time=2.25 if i in (8,9) else None)
        if i==5:v['paid'][1]['interval']=[.985,1.005]
        if i==6:v['paid'][0].update(bundle='prior-task@1.25',at=1)
        if i==10:v['work'][0]['task']='N/other/I'
        if i==11:
            other=deepcopy(v['paid'][0]);other.update(interval=[.25,.25],origin='other-calibrated-source')
            v['paid'].append(other)
        times,answers=([1.75,2.25,2.5],[category,'CONFIG_LIMIT_CURRENT','EXPIRED']) if i==8 else ([1.75,2.25],[category,'EXPIRED']) if i==9 else ([1.75],[category])
        add(i,'classify',v,answers,times=times,task=n+'/I')
    for i,caps,admitted in [(12,[42.25,42.25,4],True),(13,[42,60,4],False),(14,[60,42,4],False),(15,[60,60,3],False)]:
        add(i,'schedule',event_view(all_orders),dict(admitted=admitted,required=[42.25,42.25,4],work=[7,7,4]),
            dict(cfg,caps=caps),sequence=[c+'/A',n+'/A'])
    for i,expiry,ttl,admit in [(16,1.25,8,False),(17,12,4.5,False),(18,12,4.75,True)]:
        t=deepcopy(cfg);t['types']['N']['write'][1]=expiry;t['paid_ttl']=ttl
        add(i,'feasibility',event_view(all_orders),admit,t,sequence=[n+'/A'])
    t=deepcopy(cfg);t['pose']['worker_cooling']='loc_control'
    add(19,'route',event_view(all_orders),[4.5,5],t,task=c+'/I')
    v=event_view(all_orders+[order('C','c1',.5)],3.75)
    v['issued']=[issue(c+'/I',0,0,3.25)];v['work']=[work(c+'/I',3.25)]
    add(20,'handoff',v,[False,True,5,5.5],times=[3.5,3.75],task='C/c1/I')
    v=event_view(all_orders,1.5);v['issued']=[issue(n+'/A',0,0,1.25)]
    v['work']=[work(n+'/A',.75,status='aborted')];v['writes']=[written(n+'/A',.75,'NO_EFFECT')]
    v['work'].append(dict(v['work'][0]));v['writes'].append(dict(v['writes'][0]))
    add(21,'aborted',v,dict(debit=[12,12,1],pose=[None,None],obligations=[],work=[.75,.75,1]),
        occupation=[[0,.25,1,1],[.25,.75,1,1],[.75,1.5,0,0]])
    v=paid_prefix(event_view(all_orders,7.5))
    v['fixed']=[fixed(field,a,value) for a in (6,7,10,11) for field,value in [('network',1),('service',.25)]]
    add(22,'certificate',v,['NO_ACTION_CURRENT','OPEN_EXPIRED'],instance=n,times=[7.5,12])
    v=event_view(all_orders,7.5)
    v['issued']=[issue(n+'/A',0,0,1.25)];v['writes']=[written(n+'/A',1.25)];v['work']=[work(n+'/A',1.25),work('N/other/R',3)]
    v['paid']=[reading('N/other/R',f,[1,1],3) for f in ('e','g')]
    v['fixed']=[fixed(f,6,1) for f in ('network','service')]*2
    add(23,'certificate',v,['OPEN'],instance=n,times=[7.5])
    v=paid_prefix(event_view(all_orders,1.75),bounds=(1,.25))
    add(24,'support',v,dict(support=[],elective_allowed=False),public_config(base,plan,law='EX50'))
    valid=order('N','nA',arrived=.5);cool=order('C','cA',1)
    reports=[dict(order('N','a'),observable='service_deficit'),dict(order('N','b'),desk='foreign'),
             dict(order('N','d'),target='intake_pump'),dict(order('C','z'),revoked_at=0),
             valid,dict(valid,id='copy/nA',copied_from=valid['id'],arrived=.75),cool]
    v=event_view([],1);v['orders']=reports
    add(25,'openings',v,[[],[],['N/nA'],['N/nA'],['C/cA','N/nA']],times=[0,.25,.5,.75,1])
    return inputs,expected


def timed_oracles():
    f='F|1|3000000|1@0';q='C0|1/4|3000000|1@0';both='F|0|3000000|1@0'
    return {
      'S12':[
        [1.5,[f,q],[],[],[],None,None],
        [1.75,[f],[],[],[],4,4],
        [5,[f],[],['C/c0/A'],['C/c0/R'],0,4],
        [5.5,[f],['C/c0/A'],[],['C/c0/R'],0,0],
        [7.25,[f],['C/c0/A'],[],[],0,0]],
      'S14':[
        [1.5,[f,q],[],[],[],None,None],
        [1.75,[q],[],[],[],3,3],
        [3,[q],[],['N/n0/A'],['N/n0/R'],0,3],
        [3.5,[q],['N/n0/A'],[],['N/n0/R'],0,0],
        [5.25,[q],['N/n0/A'],[],[],0,0]],
      'S16':[
        [.25,[both],[],['C/c0/A'],['C/c0/R'],4,4],
        [1.5,[both],[],['C/c0/A','N/n0/A'],['C/c0/R','N/n0/R'],0,4],
        [2,[both],['N/n0/A'],['C/c0/A'],['C/c0/R','N/n0/R'],0,4],
        [3.75,[both],['C/c0/A','N/n0/A'],[],['C/c0/R'],0,0],
        [5.5,[both],['C/c0/A','N/n0/A'],[],[],0,0]]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    plan=json.loads(PLAN.read_bytes());books=Conditions(ROOT);base=books.call('C02','V')
    inputs,expected=policy_fixtures(base,plan)
    guards,guard_expected=guard_fixtures(base,plan);inputs.update(guards);expected.update(guard_expected)
    for key in ('native_cases','thermal_cases'):
        for row in plan[key]:
            inputs[row['id']]=native(base,plan,row,key=='thermal_cases')
            expected[row['id']]=deepcopy(row)
    for row in plan['legacy_cases']:
        condition,method=row['original'].split('-')
        inputs[row['id']]=books.call(condition,method);expected[row['id']]=deepcopy(row)
    oracle=dict(units=expected,chains=plan['short_input_grammar']['chains'],costs=plan['short_input_grammar']['cost_by_chain'],
                temporal=timed_oracles(),temporal_columns=['time before choice','original support','confirmed writes',
                'unacknowledged writes','unissued own reviews','W all pending succeed','W all pending no effect'],
                coverage=plan['coverage'],budget=plan['execution_if_separately_authorized'])
    oracle['temporal_remaining']={
        'S12':[['W',12,0],['C.A',12,0],['W',24,6.5],['C.R',24,6.5],['W',30.5,0]],
        'S14':[['W',12,0],['N.A',12,0],['W',24,8.5],['N.R',24,8.5],['W',32.5,0]],
        'S16':[['N.A',12,8.25],['W',24,18.25],['N.R',24,18.25],['C.R',34,8.25],['W',42.25,0]]}
    oracle['temporal_remaining_columns']=['next real first action','nonrefunded person/tool debit before choice',
        'unissued mandatory review envelope if outstanding work succeeds, each resource; distinct from a reserved contingent inspection branch']
    oracle['physical_expected']={
        'S01':{'N.A':[.25,1],'N.R':[1,1]},'S02':{},'S03':{'N.I':[.25,.25],'N.A':[.25,1],'N.R':[1,1]},
        'S04':{'N.I':[1,.25]},'S05':{'N.A':[1,1],'N.R':[1,.25]},'S06':{'N.A':[.25,1],'N.R':[1,1]},
        'S07':{},'S08':{},'S09':{'N.A':'NO_EFFECT'},'S10':{'N.I':[.25,'11/170'],'N.A':[.25,1],'N.R':[1,.25]},
        'S11':{},'S12':{'N.I':[1,1],'C.A':[4,1],'C.R':.1},'S13':{'C.A':[4,1],'C.R':.1},
        'S14':{'N.I':[.25,.25],'N.A':[.25,1],'N.R':[1,1]},'S15':{'C.A':[1,1],'C.R':.1},
        'S16':{'C.A':[4,1],'N.A':[0,1],'N.R':[1,1],'C.R':.1},
        'S17':{'C#0.I':.1,'C#1.I':.1},'S18':{'N.I':[1,1]},'S19':{'N.I':[None,.25]}}
    oracle['thermal_limits']={'positive_hold':['T01','T03'],'positive_early':['T02','T04'],
        'mask':['T05','T06'],'H':3600,'trip_by_s':2700,'clean_Tsat_strictly_below_K':325,
        'first_trip_step_difference_max_s':1,'dirty_q_band':[.0111,.0113],'clean_q_band':[.0999,.1001],
        'first_post_if_positive':7.5,'open_at':[9,10,2700,3600],'zero_mask_L_U':[3600,3600],
        'criterion':'preserve native balance limits, positive paired directions across both integrations, actual causal chronology, no parameter search'}
    def packed(data):
        return (json.dumps(data,separators=(',',':'),sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()
    (out/'inputs.json.gz').write_bytes(gzip.compress(packed(inputs),mtime=0))
    (out/'oracle.json').write_bytes(packed(oracle))
    manifest=dict(schema='aegisdc-joint-engineering-freeze-v1',base=BASE,plan_sha256=file_hash(PLAN),
        purpose='FINITE_PUBLIC_ENGINEERING',units={k:digest(v) for k,v in inputs.items()},
        expanded_sha256=hashlib.sha256(packed(inputs)).hexdigest(),artifacts={f:file_hash(out/f) for f in ('inputs.json.gz','oracle.json')},
        author_sha256=file_hash(__file__),source_scope='old runtime baseline; candidate implementation separately sealed before F1')
    (out/'manifest.json').write_bytes(packed(manifest))
    from aegis_dc.policy_execution import PolicySession
    # A single legacy schema probe. Never start a facility or query either selector here.
    try:
        PolicySession(inputs['S12']['dispatch_program'],12)
    except ValueError as exc:
        reason=str(exc)
        if 'fields' not in reason and 'schema' not in reason:raise
    else:raise AssertionError('Old entry unexpectedly accepted v6')
    (out/'red.json').write_bytes(packed(dict(status='EXPECTED_OLD_VERSION_REJECTION',reason=reason,
        loader_calls=1,facility_calls=0,policy_calls=0,units=len(inputs))))


if __name__=='__main__':
    main()
