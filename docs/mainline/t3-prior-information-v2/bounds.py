"""Independent finite upper-envelope calculations; never imported by an online baseline."""
from itertools import product
from common import H,CLOCK,next_tick
from public_work import duration,entries,key

EPS=1e-7


def starts(pub,sub):
    lo,hi=sub['write_window'];a,b=pub['workforce']['shifts'][sub['worker']]
    dt=duration(pub,sub,sub['start'])
    return [t for t in CLOCK if max(a,lo)<=t and t+dt<hi and
            (r:=next_tick(t+dt+15)) is not None and r+35+15<=min(H,b)]


def original(x):
    pub=x['native']['dispatch_program']['public'];data=x['evaluation']['original'];g=data['group'];f=data['family']
    target=data['target']+'/'+data['target'].lower()+'0';s=entries(pub)[target]
    ps={p['id']:p['value'] for p in x['native']['scenario']['parameters']}
    d=duration(pub,s,s['start']);times=starts(pub,s);tau=anytau=None;plan={}
    if g=='reference':value=0;why='nonnegative L, hold achieves zero'
    elif g=='mask':
        if f in ('WATER_HEAT','COOLING_ACCESS'):value=H;why='storage zero throughout'
        elif f=='NETWORK_POWER':
            b=data['latent']['demand_start'];value=(H-b)*(1-min(1,ps['rectifier_capacity']*ps['rectifier_efficiency']/2200000))
            why='shared rectifier caps delivered service'
        else:value=None;why='all permitted physical writes are identity; compare two independent native hold trajectories'
    else:
        if f in ('WATER_HEAT','COOLING_ACCESS'):
            times=[t for t in times if t+d>=data['latent']['onset']];tau=max(times);value=0
            why='zero loss by last first trip compatible with a completed filter write'
        elif f=='NETWORK_POWER':
            tau=max(t for t in times if t+d<=data['latent']['demand_start'])
            value=0;why='unit load onset and network limit; zero at last legal start'
        else:
            tau=min(times);value=(1-ps['network_service_capacity'])*(tau+d)+data['latent']['return']-data['latent']['onset']
            why='earliest legal effective network restoration plus unavoidable transfer outage'
        anytau=max(times);plan[tau]=key(target,'A')
    return dict(lower=value,plan=plan,latest_best=tau,latest_possible_gain=anytau,proof=why,enumerated=len(times))


def london_loss(c,op=None):
    if c['fault_at'] is None or c['b_voltage'] and (c['b_connected'] or op=='restore_path' and c['released']):return 0
    gap=c['restore_at']-c['fault_at']
    if c['permit'] and c['hardware_ready'] and c['transfer_ok']:
        if op=='prestart':gap=0
        elif c['logic']=='SHARED_CONTACT' or not c['b_voltage'] or op=='revise_shared':gap=min(gap,c['gen_delay'])
    endurance=c['ups_J']/c['group_W']
    return min(H-c['fault_at']-endurance,gap-endurance+c['boot_s']) if gap>endurance else 0


def netherlands_loss(c,worked):
    tf=c['fault_at']
    if tf is None:return 0
    tr=c['restore_at']
    relocated=c['group_relocated'] or ('NR' in worked and c['spare_kW']>=c['other_kW'] and worked['NR']<tf)
    load=c['critical_kW']+(0 if relocated else c['other_kW'])
    elec=tr-tf if load>c['transfer_kW'] else 0
    continuous=not c['construction'] or c['handover'] and 'NC' in worked and worked['NC']<tf
    if continuous:return elec
    restored=tr if c['auto_restart'] else worked.get('NP',H+1) if c['restart_capable'] else H+1
    expires=tf+c['thermal_hold_s']
    thermal=max(0,min(H,restored+c['cool_reset_s'])-expires) if restored>expires else 0
    # The registered power row restores in 120 s; hold-up is 300 s. The two deficits are disjoint.
    return elec+thermal


def incident(x):
    c=x['attachment'];pub=x['native']['dispatch_program']['public'];subs=entries(pub)
    if c['kind']=='LONDON':
        base=london_loss(c);opts=[(base,(),{})]
        for sid,s in subs.items():
            for t in starts(pub,s):
                if c['fault_at'] is None or t+duration(pub,s,s['start'])>=c['fault_at']:continue
                loss=london_loss(c,s['operation']);opts.append((loss,(t,),{t:key(sid,'A')}))
        proof='two feeders + accepted startup/availability; finite battery integral and reboot. All PRE grants end before the external challenge. Combining redundant supplies cannot improve on the earliest single source.'
    else:
        base=netherlands_loss(c,{});opts=[(base,(),{})];tf=c['fault_at']
        if tf is not None:
            for hydraulic in (None,'NP','NC'):
                for electric in (False,True):
                    subset=(['NR'] if electric else [])+([hydraulic] if hydraulic else [])
                    if not subset:continue
                    menus=[]
                    for sid in subset:
                        s=subs[sid];ts=starts(pub,s)
                        if sid=='NP':ts=[t for t in ts if t>=c['restore_at']+15]
                        if sid=='NC':ts=[t for t in ts if c['handover'] and t>=90]
                        menus.append(ts)
                    for start in product(*menus):
                        if len(set(start))!=len(start):continue
                        completions={sid:t+duration(pub,subs[sid],subs[sid]['start']) for sid,t in zip(subset,start)}
                        cost=netherlands_loss(c,completions)
                        opts.append((cost,tuple(sorted(start)),{t:key(sid,'A') for sid,t in zip(subset,start)}))
        proof='integer capacity/group trip + finite thermal hold-up, return latch and independent handover/restart; disjoint electrical and hydraulic loss. Separate grants/crews; one hydraulic restoration suffices.'
    best=min(o[0] for o in opts)
    if abs(best-base)<=EPS:chosen=opts[0];tau=gain=None
    else:
        winners=[o for o in opts if o[1] and abs(o[0]-best)<=EPS]
        # Never let nuisance work advance the apparent deadline.
        tau=max(o[1][0] for o in winners)
        chosen=min((o for o in winners if o[1][0]==tau),key=lambda o:(len(o[2]),sorted(o[2].items())))
        gain=max(o[1][0] for o in opts if o[1] and o[0]<base-EPS)
    return dict(lower=best,protected_only=base,plan=chosen[2],latest_best=tau,latest_possible_gain=gain,
                enumerated=len(opts),proof=proof)


def certificate_for(x):return incident(x) if x['attachment'] else original(x)


def information(x,score,tau):
    """Availability at a public decision starting from the common untreated prefix; each paid alternative is a separate possible purchase."""
    pub=x['native']['dispatch_program']['public'];rows=x['native']['dispatch_program']['channel']
    def first(kind):
        eligible=[]
        for r in rows:
            if r['kind']!=kind or r['copied_from'] is not None:continue
            tick=next_tick(r['arrived']+(.00001 if kind=='alarm' else 0))
            if tick is not None and tick<r['until']:eligible.append((r['arrived'],tick,r['origin']))
        return min(eligible,default=None)
    alarm=first('alarm');prior=first('prior');query=[]
    for s in pub['subjects']:
        if not s['primary'] or not s['allow_initial']:continue
        lo,hi=s['read_window'];shift=pub['workforce']['shifts'][s['worker']];d=duration(pub,s,s['start'])
        for t in CLOCK:
            if t<max(shift[0],lo) or t+d>=hi or t+d>shift[1] or d>min(pub['resources'][:2]) or pub['resources'][2]<1:continue
            arrival=t+d+pub['latency'];tick=next_tick(arrival)
            if tick is not None and tick<t+d+pub['paid_ttl']:
                query.append((arrival,tick,s['id'],t,t+d));break
    paid=min(query,default=None)
    def timely(item):return bool(item and tau is not None and item[0]<tau and item[1]<=tau)
    # An alarm is not a prior. In c2 the eligible availability must precede the registered alarm as well as the deadline.
    def prior_timely(item):return timely(item) and (not alarm or item[0]<alarm[0])
    return dict(alarm=alarm,prior=prior,paid=paid,paid_is_counterfactual_opportunity=True,all_paid=query,
        c1=timely(alarm),c2=bool(prior_timely(prior) or prior_timely(paid)),
        from_record=prior_timely(prior),from_paid=prior_timely(paid))
