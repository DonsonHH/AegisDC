"""Deterministic full inputs. Only the development and engineering purposes are materialized."""
from copy import deepcopy
import random
from common import H,CLOCK,BIZ,PK,load,digest,materialize
import generator as previous
from facility_inputs import epoch_event

SET=load(PK/'settings.json')
FAMILIES=SET['development_families']
SEED=SET['development_seed']
INCIDENTS=FAMILIES[-2:]
CELLS=('NORMAL','FALSE_NOTICE','SAFE_TRANSFER','TWIN_A','TWIN_B','EARLY_ALARM',
       'SILENT','LATE','LOCKED','SPECIAL_A','SPECIAL_B','PARTIAL')
# Public professional work uses existing V6 interfaces, qualification and station.
DEFS={
 'C':('inspect_facility_cooling','intake_pump','filter','clean_filter','worker_cooling','tool_flow_meter','loc_lake'),
 'N':('inspect_it_service','network','network','restore_network','worker_it','tool_it_diagnostic','loc_it'),
 'LC':('inspect_control_monitoring','local_controller','local_controller','revise_shared','worker_control','tool_control_reader','loc_control'),
 'LB':('inspect_power','main_switchboard','main_switchboard','restore_path','worker_electrical','tool_electrical_meter','loc_electrical'),
 'LG':('inspect_backup','generator','generator','prestart','worker_electrical','tool_electrical_meter','loc_electrical'),
 'NR':('inspect_power','main_switchboard','main_switchboard','relieve_group','worker_electrical','tool_electrical_meter','loc_electrical'),
 'NP':('inspect_facility_cooling','internal_pump','internal_pump','restart_pump','worker_cooling','tool_flow_meter','loc_hx'),
 'NC':('inspect_backup','backup_tower','backup_tower','commission_backup','worker_electrical','tool_electrical_meter','loc_hx')}


def source_rng(seed,*tags):
    return random.Random(digest([str(seed),*tags]))


def msg(typ,subject,source,at,arrival,ttl,value,origin=None,copied=None):
    return dict(kind=typ,subject=subject,source=source,origin=origin or source+'@'+str(at),copied_from=copied,
                sampled=at,arrived=arrival,until=at+ttl,value=value)


def preceding(seed,family,block,token,degraded,context):
    rows=[];exposures=[]
    for j,(typ,src,positive,false_positive,at,delay,ttl) in enumerate(SET['information_law'][family]):
        # Design availability is preassigned. A dated routine notice also occurs under a healthy plant.
        probability=0 if context=='no_channel' else (1 if context=='routine_notice' and j==0 else
                    positive if degraded else false_positive)
        rng=source_rng(seed,'prior',family,block,token,typ)
        published=rng.random()<probability
        exposures.append(dict(type=typ,degraded=degraded,context=context,p=probability,appears=published))
        if not published:continue
        arrival=at+delay+(960 if context=='late_publication' else 0)
        row=msg('prior',None,src,at,arrival,ttl,'REVIEW_DUE',origin=src+'/'+typ+'@'+str(at))
        row['record_type']=typ;rows.append(row)
        if rng.random()<SET['copy_probability']:
            dup=deepcopy(row);dup.update(source='registered-relay',arrived=arrival+SET['copy_delay_s'],copied_from=row['origin'])
            rows.append(dup)
    return rows,exposures


def incident_case(seed,draw,family,forced=None):
    block,slot=divmod(draw,12)
    order=list(CELLS);source_rng(seed,'incident-order',family,block).shuffle(order)
    cell=forced or order[slot]
    twin=cell.startswith('TWIN');token='pair' if twin else cell
    rng=source_rng(seed,'incident-factors',family,block,token)
    tf=rng.choice([1500,1800]);active=cell not in ('NORMAL','FALSE_NOTICE')
    before=cell in ('EARLY_ALARM','SAFE_TRANSFER')
    alarm=360 if before else 990
    context={'FALSE_NOTICE':'routine_notice','SILENT':'no_channel','LATE':'late_publication'}.get(cell,'ordinary')
    if twin:context='routine_notice'
    default=(60,780)
    if family=='LONDON':
        subjects=['LC','LB','LG'];windows={k:list(default) for k in subjects}
        spec=dict(kind=family,fault_at=tf if active else None,restore_at=tf+600,group_W=1000,ups_J=180000,
                  boot_s=120,gen_delay=60,b_voltage=True,b_connected=False,released=False,logic='SHARED_UPSTREAM',
                  permit=True,hardware_ready=True,transfer_ok=True)
        if cell in ('NORMAL','FALSE_NOTICE','SAFE_TRANSFER'):spec.update(logic='SHARED_CONTACT',b_connected=True)
        if cell in ('TWIN_B','SPECIAL_B'):spec.update(hardware_ready=False,released=True)
        if cell=='SPECIAL_A':windows.update(LC=[1,2],LB=[1,2])
        if cell=='SPECIAL_B':windows.update(LC=[1,2],LG=[1,2])
        if cell=='PARTIAL':
            spec.update(gen_delay=360,ups_J=120000);windows.update(LG=[1,2],LB=[1,2])
        if cell=='LOCKED':windows={k:[1,2] for k in subjects}
        first='LC'
    else:
        subjects=['NR','NP','NC']
        windows={'NR':[60,600],'NP':[0,3000],'NC':[720,1140]}
        spec=dict(kind=family,fault_at=tf if active else None,restore_at=tf+120,critical_kW=60,other_kW=40,
                  spare_kW=40,transfer_kW=70,group_relocated=False,auto_restart=False,restart_capable=True,
                  construction=True,handover=False,thermal_hold_s=300,cool_reset_s=60)
        if cell in ('NORMAL','FALSE_NOTICE','SAFE_TRANSFER'):
            spec.update(transfer_kW=120,auto_restart=True,construction=False,handover=True)
        if cell in ('TWIN_A','SPECIAL_A'):spec.update(auto_restart=True)
        if cell=='TWIN_B':spec.update(transfer_kW=120)
        if cell=='SPECIAL_B':
            spec.update(transfer_kW=120,handover=True,restart_capable=False);windows['NP']=[1,2]
        if cell=='PARTIAL':spec.update(transfer_kW=45)
        if cell=='LOCKED':windows={k:[1,2] for k in subjects}
        first='NR'
    inspect=[] if cell in ('SILENT','LATE') else list(subjects)
    phys=dict(filter_resistance_multiplier=1,network_service_capacity=1,storage_service_capacity=1,rectifier_capacity=5000000)
    donor=dict(initial='S12',physical=phys,step=.25,events=[],records=[],grants={'C':[0,H],'N':[0,H]},
               catalog=[['C','c0','IAR'],['N','n0','IAR']],fixed_epochs=list(range(0,H,300)))
    stream=[msg('order',k,'work-desk',0,0,H+1,'OPEN',origin='order/'+k) for k in subjects]
    stream.append(msg('alarm','power-board' if family=='LONDON' else 'cooling-board','alarm-desk',max(0,alarm-30),alarm,660,'ALARM',origin='risk-review'))
    if family=='NETHERLANDS':
        # A work release is a signed business document, and by itself proves no actual transfer/commission.
        stream.append(msg('release','NC','works-office',60,90,3240,'HANDOVER_RELEASED' if spec['handover'] else 'WORK_OPEN'))
    return dict(family=family,draw=draw,cell=cell,token=token,degraded=active and cell!='SAFE_TRANSFER',
                context=context,twin=twin,subjects=subjects,first=first,windows=windows,inspect=inspect,
                donor=donor,stream=stream,incident=spec,old_eval=None)


def base_case(seed,draw,family,src):
    g=previous.sample(seed,draw,family);d=g['design'];target=g['target']+'/'+g['target'].lower()+'0'
    ids=[k+'/'+o for k,o,ph in d['catalog']]
    streams=[msg('order',k,'work-desk',0,0,H+1,'OPEN',origin='order/'+k) for k in ids]
    for row in d['records']:
        if row['observable']=='alarm':
            streams.append(msg('alarm',target,row['desk'],row['at'],row['arrived'],row['until']-row['at'],'ALARM',
                               origin='alarm/'+target,copied=row['copied_from']))
    avail=[target] if draw%4 or g['ambiguous_pair'] else []
    return dict(family=family,draw=draw,cell=g['regime'],token='pair' if g['ambiguous_pair'] else g['regime'],
        degraded=g['group']!='reference',context=('routine_notice' if g['ambiguous_pair'] else 'ordinary'),
        twin=g['ambiguous_pair'],subjects=ids,first=target,windows={s:list(d['grants'][s[0]]) for s in ids},
        inspect=avail,donor=d,stream=streams,incident=None,old_eval={k:v for k,v in g.items() if k!='design'})


def descriptor(subject,case,base):
    k=subject.split('/')[0];iface,read_target,act_target,op,worker,tool,loc=DEFS[k]
    knowledge=base['nominal_knowledge'];registry={w['id']:w for w in knowledge['work_interfaces']}
    nominal={r['id']:r for r in knowledge['entities']}
    primary='/' not in subject or subject.endswith('0')
    start=nominal[worker]['nominal_location_id']; assert start==nominal[tool]['nominal_location_id']
    # All actors start with their own tool. These route times are recomputed from the real public graph at dispatch.
    return dict(id=subject,key=k,interface=iface,worker=worker,tool=tool,location=loc,start=start,
                expertise=registry[iface]['qualification_id'],read_asset=read_target,write_asset=act_target,
                operation=op,write_window=case['windows'][subject] if primary else [1,2],
                read_window=[0,H],renew_window=case.get('renew_window',[1680,H]),
                allow_initial=subject in case['inspect'],review=True,primary=primary)


def complete(case,src,seed):
    base=materialize(src,case['donor']);old=base['dispatch_program']
    prof=old['workforce_profile']
    for kind,start in case['donor'].get('shift_starts',{}).items():
        prof['shifts'][DEFS[kind][4]]=[start,H]
    subjects=[descriptor(q,case,old) for q in case['subjects']]
    prior,opps=preceding(seed,case['family'],case['draw']//12,case['token'],case['degraded'],case['context'])
    stream=deepcopy(case['stream'])+prior
    routes=[q['id'] for q in subjects if q['primary']]
    pub=dict(subjects=subjects,workforce=prof,clock=list(CLOCK),business_ticks=list(BIZ),
             routes=routes,resources=[2400,2400,24],route_graph=old['nominal_knowledge']['graphs']['access'],
             fixed_epochs=list(range(0,H,300)),fixed_ttl=720,paid_ttl=2100,latency=15,renew_at=1680)
    base['dispatch_program']=dict(schema='T3-native-work-session-v2',id='minute-facility',
        policy_program={'schema':'t3-three-status-quo-v2'},public=pub,channel=stream,
        nominal_knowledge=old['nominal_knowledge'],evidence_ledger=old['evidence_ledger'])
    return dict(native=base,attachment=case['incident'],evaluation=dict(family=case['family'],draw=case['draw'],
           cell=case['cell'],pair=case['twin'],degraded=case['degraded'],context=case['context'],
           prior_draw=opps,original=case['old_eval']))


def dev_case(seed,draw,fam,src):
    c=incident_case(seed,draw,fam) if fam in INCIDENTS else base_case(seed,draw,fam,src)
    return complete(c,src,seed)


def qualification(fam,kind,src):
    """Independent fixture background/operations; never inspect development outcomes."""
    if fam in INCIDENTS:
        c=incident_case(SEED,0,fam,'NORMAL' if kind in ('NA','EXPIRE') else 'TWIN_A')
        target='LC' if fam=='LONDON' else 'NR'
        c['windows'][target]=[0,H]
    else:
        c=base_case(SEED,0,fam,src);target='C/c0' if fam in ('WATER_HEAT','COOLING_ACCESS') else 'N/n0'
        c['subjects']=['C/c0','N/n0'];c['windows']={'C/c0':[0,H],'N/n0':[0,H]}
        c['donor'].update(initial='S12',physical={'filter_resistance_multiplier':4 if target=='C/c0' and kind=='PV' else 1,
            'network_service_capacity':.25 if target=='N/n0' and kind=='PV' else 1,'storage_service_capacity':1,'rectifier_capacity':5000000},
            events=[],shift_starts={'C':0,'N':0})
        if fam=='WATER_HEAT':c['donor']['initial']='T03'
        if fam=='RESERVE_TRANSFER':
            c['donor']['physical']['diesel_in_service']=0
            c['donor']['events']=[epoch_event(960,'grid_capacity',0),epoch_event(1080,'grid_capacity',10000000)]
        if fam=='COOLING_ACCESS':
            c['donor']['physical']['backup_cooling_in_service']=int(kind=='NA')
            c['donor']['events']=[epoch_event(60,'backup_cooling_requested',1),epoch_event(120,'backup_cooling_requested',0)]

    c['stream']=[msg('order',k,'engineering-desk',0,0,H+1,'OPEN',origin='order/'+k) for k in c['subjects']]
    c['inspect']=[target];c['renew_window']=[1680,H] if kind!='EXPIRE' else [0,1000]
    item=complete(c,src,SEED)
    return item,{'target':target,'mode':kind,'plan':{0:target+('::A' if kind=='PV' else '::I')}}
