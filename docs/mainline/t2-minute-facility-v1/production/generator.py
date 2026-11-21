"""Reproducible minute-facility sampling. No policy, evaluator or simulator imports."""
import argparse
from copy import deepcopy
from pathlib import Path
import random
import sys
sys.path.insert(1,str(Path(__file__).resolve().parent.parent))
from facility_inputs import H, PACKAGE, epoch_event, fingerprint, materialize, message, templates, write

SEED=2026112102
FAMILIES=('WATER_HEAT','NETWORK_POWER','RESERVE_TRANSFER','COOLING_ACCESS')
REGIMES=tuple(f'{band}-{j}' for band in ('normal','masked','precursor-early','precursor-late') for j in range(3))


def sample(seed, draw, family):
    """One uniform member of a randomly permuted finite block, sampled without replacement."""
    if family not in FAMILIES or draw<0:raise ValueError('Unknown family/draw')
    if not isinstance(seed,int):raise ValueError('Integer seed required')
    i=FAMILIES.index(family);block,slot=divmod(draw,len(REGIMES))
    shuffled=list(REGIMES);random.Random(f'{seed}/{family}/ordering/{block}').shuffle(shuffled)
    regime=shuffled[slot];rng=random.Random(f'{seed}/{family}/{block}/{regime}')
    q=REGIMES.index(regime);cat=q//3
    # Three members per physical and operating range; labels never go to the policy.
    # Masked, reference, observable-before-deadline and unavoidably-late ranges.
    parameter_group=('reference','mask','early','late')[cat]
    warm=family in ('WATER_HEAT','COOLING_ACCESS')
    if warm:
        target='C';start=rng.choice([60,120,180]);m=rng.choice([72,84,100]);cold=parameter_group=='reference'
        physical={'network_service_capacity':1,'storage_service_capacity':0 if parameter_group=='mask' else 1,
                  'filter_resistance_multiplier':1,'backup_cooling_requested':0,'backup_cooling_in_service':1}
        initial='S12' if cold else 'T03'
        if cold:m=1
        events=[epoch_event(start,'filter_resistance_multiplier',m)]
        if family=='COOLING_ACCESS':
            if parameter_group=='reference':
                events.extend([epoch_event(60,'backup_cooling_requested',1),epoch_event(180,'backup_cooling_requested',0)])
            else:
                events.extend([epoch_event(0,'backup_cooling_in_service',0),epoch_event(60,'backup_cooling_requested',1)])
                # Public maintenance handover controls the access window to the cooling work.
                # The frozen model lacks a separate live blockage for loc_lake.
        latent={'service_floor':'water','restriction':m,'onset':start}
        latest_effect=None
    elif family=='NETWORK_POWER':
        target='N';start=0;initial='S12';net=rng.choice([0.25,0.5])
        physical={'filter_resistance_multiplier':1,'network_service_capacity':net,'storage_service_capacity':1,'rectifier_capacity':5000000}
        if parameter_group=='mask':
            physical.update(network_service_capacity=1,rectifier_capacity=550000)
        if parameter_group=='reference':physical['network_service_capacity']=1
        demand_start=rng.choice([600,900,1200]);physical['service_demand']=0
        events=[epoch_event(demand_start,'service_demand',1)]
        latent={'service_floor':'network','onset':start,'demand_start':demand_start}
        latest_effect=None
    else:
        target='N';initial='S12';start=rng.choice([1200,1500,1800]);end=start+300
        masked=parameter_group=='mask'; ref=parameter_group=='reference'
        # Simultaneous limits can suppress service completely; the reserve still has real native dynamics.
        physical={'filter_resistance_multiplier':1,'network_service_capacity':1 if (masked or ref) else rng.choice([.25,.5]),
                  'storage_service_capacity':1,'diesel_in_service':int(ref),'diesel_transfer_ok':int(ref)}
        if not ref:
            physical['diesel_in_service']=rng.choice([0,1])
            physical['diesel_transfer_ok']=0
        # Actual protected-group energy differs by design autonomy; local dynamics integrate the native demand.
        autonomy=rng.choice([120,180,300]) if masked else rng.choice([600,720,900])
        physical['ups_energy']=(23000/0.92+100)*autonomy
        events=[] if ref else [epoch_event(start,'grid_capacity',0),epoch_event(end,'grid_capacity',10000000)]
        latent={'service_floor':'reserve','onset':start,'return':end,'actual_protected_group':'auxiliaries'}
        latest_effect=None
    # Advance / late proxies vary by the independently drawn notice timestamp and lawful window.
    early=parameter_group=='early'
    alert= rng.choice([20,45,80]) if early else rng.choice([250,310,370]) if parameter_group=='late' else rng.choice([20,80,250])
    opening=0
    # Narrow work authority creates an observable, meaningful start deadline.
    # In the early/late water family both grant and thermal deadline can bind.
    grant_end=(400 if warm else 220) if parameter_group in ('early','late') else 600
    if early and warm and q%3==1:grant_end=455
    if parameter_group=='late' and warm:alert=grant_end+15
    if parameter_group=='late' and not warm:alert=grant_end+15
    norders=2+rng.randrange(3);origins=[('C','c0'),('N','n0')]
    if norders>=3:origins.append(('C','c1'))
    if norders==4:origins.append(('N','n1'))
    records=[message(k,o,'problem_reported',opening,opening,H+1) for k,o in origins]
    alarm_origin='c0' if target=='C' else 'n0'
    records.append(message(target,alarm_origin,'alarm',max(0,alert-20),alert,min(H+1,alert+600)))
    if norders<4 and rng.randrange(2):
        records.append(message(target,alarm_origin,'alarm',max(0,alert-20),alert+12,min(H+1,alert+600),
                               copy='alarm/'+alarm_origin,label='relay/'+alarm_origin))
    others=[k for k in ('C','N') if k!=target]
    grants={'C':[0,0],'N':[0,0]}
    # Write scopes are shared and only include the family's declared corrective primitive.
    # Use a positive-width expired-at-all-dispatches window for non-targets.
    grants[others[0]]=[1,2];grants[target]=[rng.choice([60,120]) if family=='COOLING_ACCESS' else 0,grant_end]
    design=dict(initial=initial,physical=physical,step=.25,events=events,records=records,grants=grants,
        catalog=[[k,o,'IAR' if (k,o) in [('C','c0'),('N','n0')] else 'I'] for k,o in origins],
        fixed_epochs=[600,900],fixed_on=['lake' if warm else 'network','service'],
        shift_starts={'C':rng.choice([0,60]),'N':rng.choice([0,60])})
    # A duty visit always costs occupation. A named diagnostic reading can only be purchased once;
    # its subsequent same-instance verification is a separately counted, outcome-dependent observation.
    ambiguous=family=='NETWORK_POWER' and regime in ('masked-0','precursor-early-0')
    if ambiguous:
        design['physical']['network_service_capacity']=1 if parameter_group=='mask' else .25
        design['events']=[epoch_event(600,'service_demand',1)];latent['demand_start']=600
        design['catalog']=[['C','c0','IAR'],['N','n0','IAR']]
        design['records']=[message('C','c0','problem_reported'),message('N','n0','problem_reported'),
                           message('N','n0','alarm',60,80,680)]
        design['grants']={'C':[1,2],'N':[0,220]}
        design['shift_starts']={'C':0,'N':0};alert=80
    return dict(family=family,draw=draw,seed=seed,regime=regime,group=parameter_group,
                target=target,ambiguous_pair=ambiguous,alert_time=alert,latest_effect=latest_effect,latent=latent,design=design)


def full(item,source):
    """Core call plus separate public opportunities; no private fields in the dispatch envelope."""
    native=materialize(source,item['design'])
    prog=native['dispatch_program']
    cfg=prog['policy_program'];cfg['fixed_on']=list(item['design']['fixed_on'])
    for k,lo in item['design']['shift_starts'].items():
        worker=cfg['types'][k]['worker']
        cfg['shift'][worker]=[lo,H];prog['workforce_profile']['shifts'][worker]=[lo,H]
    parents=[t for t in prog['task_catalog'] if t['id'].endswith('/I')]
    opportunities=[t['id'] for t in parents if t['id'].startswith(item['target']+'/')]
    if item['draw']%4==0 and not item['ambiguous_pair']:opportunities=[]
    route=[]
    # Visits are real separate native work with its own sample/expense at each cycle.
    # These are periodic duties, not additional risk-triggered work orders.
    for cycle in range(4):
        for kind in ('C','N'):
            origin='p'+str(cycle)+kind.lower()
            base=next(t for t in parents if t['id'].startswith(kind+'/'))
            task=deepcopy(base);task['id']=kind+'/'+origin+'/I'
            prog['task_catalog'].append(task)
            old=next(b for b in prog['inspection_program']['bindings'] if b['task']==base['id'])
            binding=deepcopy(old);binding['task']=task['id'];prog['inspection_program']['bindings'].append(binding)
            route.append([cycle*900,task['id']])
    record_rights={b['task']:(b['fields'] if b['task'] in opportunities or b['task'].endswith('/R') else
                        {f:None for f in b['fields']}) for b in prog['inspection_program']['bindings']}
    return dict(native=native,public=dict(read_rights=record_rights,duty_route=route,paid_opportunities=opportunities,
                once_per_named_target=True,post_action_review_required=True,
                work_orders=[k+'/'+o for k,o,_ in item['design']['catalog']],
                own_instance={'C':'C/c0','N':'N/n0'}),
                evaluation={k:v for k,v in item.items() if k!='design'})


def generate(seed,rounds,output):
    source=templates();output.mkdir(parents=True,exist_ok=False)
    indices=[]
    for draw in range(rounds):
        for family in FAMILIES:
            x=full(sample(seed,draw,family),source);key=f'{FAMILIES.index(family)+1}-{draw+1:02d}'
            write(output/(key+'.json'),x)
            indices.append(dict(key=key,family=family,draw=draw,native=fingerprint(x['native']),
                                public=fingerprint(x['public']),full=fingerprint(x)))
    write(output/'index.json',dict(seed=seed,ordered=indices))
    return indices


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--seed',type=int,default=SEED);ap.add_argument('--rounds',type=int,default=12)
    ap.add_argument('--output',type=Path,required=True)
    ns=ap.parse_args();generate(ns.seed,ns.rounds,ns.output)
