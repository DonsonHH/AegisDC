"""Independent, saved-data-only H12 endpoints. Nothing in this module dispatches work."""
from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
from math import fsum, isfinite
from cold3_identity import public_keys
from audit_v6_joint import certificate_from_records, digest, physiology, work_receipt_statistics

CATEGORIES=('BETTER','SAME','WORSE','NUMERIC_UNRESOLVED','NONCOMPLIANT','NO_PAIR')
TYPES={'NO_ACTION_CURRENT':'NA','POST_ACTION_VERIFIED_CURRENT':'PV'}
H=12
TOL=1e-8


def service_account(run):
    balance=[Fraction(0),Fraction(0)];rate=[Fraction(0),Fraction(0)];curve=[];previous=0
    for left,b,right in zip(run['trace'],run['balances'],run['trace'][1:],strict=False):
        a,z=b['start_s'],b['end_s']
        if a!=previous or z<=a or left['time_s']!=a or right['time_s']!=z:
            raise ValueError('Noncontiguous service interval')
        it=left['domains']['it_service'];d,y=it['demand'],it['delivered']
        if not 0<=y<=d:raise ValueError('Invalid delivered service')
        dt=Fraction(z)-Fraction(a);lost=Fraction(d)-Fraction(y)
        balance[0]+=Fraction(b['service_deficit_time_s'])
        balance[1]+=Fraction(b['demand_service_unit_s'])-Fraction(b['delivered_service_unit_s'])
        rate[0]+=dt*lost/Fraction(d) if d else 0;rate[1]+=dt*lost
        if curve and curve[-1][2:]==[d,y]:curve[-1][1]=z
        else:curve.append([a,z,d,y])
        previous=z
    if previous!=H or len(run['trace'])!=len(run['balances'])+1:raise ValueError('Incomplete H12 integral')
    return dict(balance=list(map(str,balance)),rate=list(map(str,rate)),curve=curve)


def service_direction(left,right):
    for s in (left,right):
        if any(abs(Fraction(a)-Fraction(b))>Fraction('1e-8') for a,b in zip(s['balance'],s['rate'],strict=True)):
            return 'NUMERIC_UNRESOLVED'
    if left['curve']==right['curve']:return 'SAME'
    delta=[Fraction(b)-Fraction(a) for k in ('balance','rate') for a,b in zip(left[k],right[k],strict=True)]
    if all(x==0 for x in delta):return 'SAME'
    if all(x>0 for x in delta):return 'BETTER'
    if all(x<0 for x in delta):return 'WORSE'
    return 'NUMERIC_UNRESOLVED'


def resource_direction(left,right):
    delta=[Fraction(b)-Fraction(a) for a,b in zip(left,right,strict=True)]
    if all(x==0 for x in delta):return 'SAME'
    if min(delta)>=0:return 'BETTER'
    if max(delta)<=0:return 'WORSE'
    return 'MIXED'


def occupations(run):
    jobs={r['id']:r for r in run['work_records']}
    usage={k:dict(travel=0.,work=0.,wait=0.,tool=0.) for k in jobs}
    shifts=run['inputs']['dispatch_program']['workforce_profile']['shifts']
    for b,snapshot in zip(run['balances'],run['trace']):
        dt=b['end_s']-b['start_s'];p=snapshot['domains']['people_tools_work'];active=set()
        for w,rec in p['workers'].items():
            status={'travelling':'travel','working':'work','waiting':'wait'}.get(rec['status'])
            if status:
                usage[rec['request_id']][status]+=dt;active.add(w)
        for name in p.get('queued_requests',[]):
            for role in jobs[name]['crew']:
                w=role['worker_id']
                if w not in active and shifts[w][0]<=b['start_s']<shifts[w][1]:
                    usage[name]['wait']+=dt;active.add(w)
        for rec in p['tools'].values():
            if rec['reserved_by'] is not None:usage[rec['reserved_by']]['tool']+=dt
    return usage


def native_effects(run):
    known={'clean_filter':('C','filter_resistance_multiplier'),'restore_network_capacity':('N','network_service_capacity')}
    effects=[];unknown=[];writes=[]
    for row in run['intervention_private_audit']['events']:
        if row['outcome']=='NO_EFFECT':continue
        if row['outcome']!='APPLIED' or row['operation_id'] not in known:
            unknown.append(row);continue
        kind,param=known[row['operation_id']]
        if row['parameter_id']!=param or row['task_id'].split('/')[0]!=kind:
            unknown.append(row);continue
        event=[row['applied_at_s'],kind,row['old_value'],row['new_value']]
        writes.append(event)
        if event[2]!=event[3]:effects.append(event)
    return sorted(effects),unknown,sorted(writes)


def receipt_view(run,cfg,clock):
    out={}
    for t in clock:
        work=[(r['task_id'],r['status'],r['observed_at_s'],r['arrived_at_s'],r['origin_id']) for r in run['workforce_public_feedback'] if r['arrived_at_s']<=t]
        writes=[(r['task_id'],r['outcome'],r['observed_at_s'],r['arrived_at_s'],r['origin_id']) for r in run['intervention_public_feedback'] if r['arrived_at_s']<=t]
        paid=[r for r in run['inspection_public_feedback'] if r['arrived']<=t]
        out[t]=(work,writes,paid)
    return out


def score_arm(item,run):
    cfg=item['dispatch_program']['policy_program'];prog=item['dispatch_program'];issues=[]
    def check(ok,label):
        if not ok and label not in issues:issues.append(label)
    req=run['inputs']
    check(digest(run['source_config'])==digest(item['scenario']) and digest(req['dispatch_program'])==digest(prog),'INPUT_IDENTITY')
    check(run['summary']['duration_s']==H==item['duration_s'] and req['maximum_step_s']==item['step_s'] and req.get('private_physical_audit') is True,'WINDOW_OR_AUDIT')
    check(req['boundary_events']==item['boundary_events']==[] and not req.get('action_commands') and not req.get('work_requests') and
          item.get('business_program') is None and 'business_evaluation' not in run,'COLD_BOUNDARY')
    numerical=physiology(run);check(numerical['continuous'] and numerical['conserved'],'CONSERVATION')
    account=service_account(run)
    numeric=all(abs(Fraction(a)-Fraction(b))<=Fraction('1e-8') for a,b in zip(account['balance'],account['rate']))
    usage=occupations(run);summary=run['summary']
    for k,native in [('travel','worker_travel_person_s'),('work','worker_work_person_s'),('wait','worker_wait_person_s'),('tool','tool_occupation_tool_s')]:
        check(abs(fsum(row[k] for row in usage.values())-summary[native])<=TOL,'RESOURCE_'+k.upper())
    work=run['work_records'];acks=run['workforce_public_feedback'];op_reports=run['intervention_public_feedback']
    waits=work_receipt_statistics(work,acks,cfg,H)
    check(waits['rejected']==0 and not waits['conflicts'],'RECEIPT_IDENTITY')
    stages=[[r['id'].split('/')[0]+'.'+r['id'].split('/')[-1],r['issued_at_s'],r.get('finished_at_s'),waits['terminal_arrivals'][r['id']]] for r in work]
    reads=run['inspection_public_feedback'];snap={s['time_s']:s['domains'] for s in run['trace']}
    faces=run['private_physical_audit'];epochs=faces['epochs']
    check(faces['visibility']=='PRIVATE_EVALUATOR_ONLY' and [e['t'] for e in epochs]==list(snap),'PRIVATE_EPOCH_IDENTITY')
    phys_by_t={e['t']:e for e in epochs};balances=run['balances'];params={r['id']:r['value'] for r in item['scenario']['parameters']}
    def interval(b):
        return [b['end_s']-b['start_s'],params['energy_absolute_tolerance']+params['balance_relative_tolerance']*(abs(b['boundary_input_J'])+abs(b['boundary_output_J']))]
    effects,unknown,all_writes=native_effects(run)
    applied=[r for r in run['events'] if r.get('kind')=='completed_research_intervention']
    check(len(applied)==len(all_writes) and sorted((r['task_id'],r['applied_at_s'],r['old_value'],r['new_value']) for r in applied)==
        sorted((r['task_id'],r['applied_at_s'],r['old_value'],r['new_value']) for r in run['intervention_private_audit']['events'] if r['outcome']=='APPLIED'),'PRIVATE_OPERATION_BINDING')
    known_params=[params['filter_resistance_multiplier'],params['network_service_capacity']]
    for i,e in enumerate(epochs):
        t=e['t'];before=e['before'];right=e['right'];left=e['left'];s=snap[t]
        incoming=balances[max(0,i-1)];outgoing=balances[min(i,len(balances)-1)]
        e['incoming']=interval(incoming);e['outgoing']=interval(outgoing)
        original=incoming['storage_after_J'] if i else outgoing['storage_before_J']
        check(all(abs(left['stocks'][k]-v)<=e['incoming'][1] for k,v in original.items()),'TRUE_LEFT_INVENTORIES')
        check(left['params']==before['params']==known_params,'PRE_MANUAL_PARAMETER_HISTORY')
        for _,kind,old,new in (w for w in all_writes if w[0]==t):
            j=0 if kind=='C' else 1
            check(known_params[j]==old,'PHYSICAL_OLD_VALUE');known_params[j]=new
        check(right['params']==known_params and right['service'][1]==s['it_service']['delivered'] and
              right['flow'][0]==s['facility_cooling']['lake_pump']['volume_flow_m3_s'] and right['heat']==s['facility_cooling']['plate_hx_heat_W'],
              'RIGHT_NATIVE_READBACK')
    for r in reads:
        j=next((j for j in work if j['id']==r['task']),None)
        kind=r['task'].split('/')[0];typ=cfg['types'][kind]
        check(j is not None and j['status']=='completed' and j.get('finished_at_s')==r['at'] and
              r['arrived']==r['at']+cfg['latency'] and r['until']==r['at']+cfg['paid_ttl'],'PAID_TIME')
        if j is None:continue
        window=typ['read'].get(r['field'])
        authorized=window is not None and window[0]<=j['issued_at_s']<=r['at']<window[1]
        field=r['field'];state=snap[r['at']]
        val=(phys_by_t[r['at']]['right']['params'][1] if field=='g' else state['it_service']['capacities']['network'] if field=='e'
             else state['facility_cooling']['lake_pump']['volume_flow_m3_s'])
        check(r['interval']==([val,val] if authorized else None) and r['bundle']==f"{r['task']}@{r['at']:g}",'PAID_SCOPE')
    dec=run['policy_public_decisions'];clock=cfg['clock'];exposed=receipt_view(run,cfg,clock)
    check([d['view']['time'] for d in dec]==clock,'PUBLIC_CLOCK')
    opened={};states={};first={};history=[];issued=[];charged=[0,0,0];resource_log=[]
    for d in dec:
        view,choice=d['view'],d['decision'];t=view['time']
        check(set(view)=={'time','orders','issued','work','writes','paid','fixed'},'PUBLIC_FIELDS')
        work_seen,writes_seen,paid_seen=exposed[t]
        check(view['orders']==[r for r in prog['order_channel'] if r['arrived']<=t] and view['paid']==paid_seen,'PUBLIC_ARRIVAL')
        check([(r['task'],r['status'],r['at'],r['arrived'],r['origin']) for r in view['work']]==work_seen,'WORK_ARRIVAL')
        check([(r['task'],r['outcome'],r['at'],r['arrived'],r['origin']) for r in view['writes']]==writes_seen,'WRITE_ARRIVAL')
        expected_fixed=[]
        for ep in cfg['fixed_epochs']:
            if ep+cfg['latency']>t:continue
            raw=snap[ep];values={'lake':raw['facility_cooling']['lake_mass_flow_kg_s'],'network':raw['it_service']['capacities']['network'],'service':raw['it_service']['delivered']}
            for f in cfg['fixed_on']:expected_fixed.append(dict(at=ep,arrived=ep+cfg['latency'],until=ep+cfg['fixed_ttl'],field=f,interval=[values[f]]*2,origin=f'fixed:{f}@{ep:g}',source='fixed-'+f))
        check(view['fixed']==expected_fixed,'FIXED_ARRIVAL')
        for r in view['orders']:
            for kind,typ in cfg['types'].items():
                if ((r['desk'],r['target'],r['observable'],r['value'])==(typ['desk'],typ['target'],'problem_reported',True)
                        and r['copied_from'] is None and r['arrived']<=t<r['until'] and (r['revoked_at'] is None or t<r['revoked_at'])):
                    opened.setdefault(kind+'/'+r['origin'],t)
        state={k:certificate_from_records(cfg,view,k,at) for k,at in opened.items()};states[f'{t:g}']=state
        check(state==choice['certificates'],'NAMED_CLOSURE')
        for name,s in state.items():
            if s in TYPES:first.setdefault(name,{}).setdefault(TYPES[s],t)
        check([x['task'] for x in view['issued']]==[x['task'] for x in issued] and choice['prefix']['debit']==charged,'PAID_PREFIX')
        row=choice['request'];decision=row['task'] if row else None
        bare_view=dict(view,issued=[{k:v for k,v in x.items() if k!='contingent'} for x in view['issued']])
        history.append(dict(time=t,public=digest(view),signature=public_keys(cfg,view),evidence=digest(bare_view),task=decision,
            selected=[choice['selected']['sequence'],choice['selected']['score']] if choice['selected'] else None,
            menu=[[x['sequence'],x['admitted'],x.get('excluded_by_order_rule',False)] for x in choice['alternatives']],
            support=choice['prefix']['support'],debit=list(charged)))
        resource_log.append(dict(time=t,spent=list(charged),review_reserved=choice['prefix']['reserved_review'],
            obligations=choice['prefix']['obligations'],contingent=choice['prefix']['contingent'],locked=choice['prefix']['locked'],pose=choice['prefix']['pose']))
        if row:
            instance,phase=decision.rsplit('/',1);typ=cfg['types'][instance[0]]
            check(instance in opened and row['at']==t and decision not in [v['task'] for v in issued],'LEGAL_ISSUE')
            check(not (cfg['method']=='J_OPEN' and phase!='R' and opened[instance]!=min(opened.values())) and
                  not (cfg['method']=='J_NO_PROBE' and phase=='I'),'MECHANISM_BOUNDARY')
            check(bool(choice['selected'] and choice['selected']['admitted'] and not choice['selected'].get('excluded_by_order_rule')),'ADMISSION')
            release=opened[instance]
            if phase=='R':
                parent=instance+'/A'
                received=next((m for m in view['writes'] if m['task']==parent and m['outcome']=='APPLIED'),None)
                check(received is not None and any(m['task']==parent and m['status']=='completed' for m in view['work']),'OWN_REVIEW')
                if received:release=received['arrived']
            check(row['release']==release,'NATIVE_RELEASE')
            if phase=='A':
                check(typ['write'][0]<=t and row['planned_end']<typ['write'][1],'WRITE_WINDOW')
                if typ['require_probe']:
                    proof={r['field']:r for r in view['paid'] if r['task']==instance+'/I' and r['until']>t and r['interval'] is not None}
                    check('g' in proof and 'e' in proof and proof['g']['bundle']==proof['e']['bundle'] and
                          proof['g']['interval'][1]<1 and proof['e']['interval'][1]<=proof['g']['interval'][0] and
                          any(m['task']==instance+'/I' and m['status']=='completed' and m['at']==proof['g']['at'] for m in view['work']),'POSITIVE_GRANT')
            charged=[charged[0]+cfg['deadline']-release,charged[1]+cfg['deadline']-release,charged[2]+cfg['fee']]
            check(all(a<=b for a,b in zip(charged,cfg['caps'])),'BUDGET')
            issued.append(row)
    check([(r['task'],r['at']) for r in issued]==[(r['id'],r['issued_at_s']) for r in work],'REAL_WORK_MATCHES_ISSUES')
    check(len(opened)==len(prog['order_channel']),'ALL_REGISTERED_INSTANCES')
    # Seal per-task/per-instance costs; task wait and administrative delays are not actual occupation.
    for row in issued:usage[row['task']]['fee']=cfg['fee']
    physical=digest([item['scenario'],item['boundary_events'],H,item['step_s'],item['action_commands'],item['work_requests']])
    public=deepcopy(prog);del public['policy_program']['method']
    return dict(status='NONCOMPLIANT' if issues else 'OK' if numeric else 'NUMERIC_UNRESOLVED',violations=issues,
        physical_id=physical,public_id=digest(public),runtime=run['code_identity']['source_tree_sha256'],horizon=H,
        audit=epochs,effects=effects,all_writes=all_writes,unknown_effects=unknown,service=account,
        resources=[*numerical['physical_work'],charged[2]],admission=charged,task_resources=usage,resource_history=resource_log,
        waits=waits,stages=stages,work_outcomes=[(r['id'],r['status'],r.get('reason')) for r in work],
        opened=opened,states=states,first=first,decisions=history,private_inputs_digest=digest(item))

def _different(a,b,tolerance=0):
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()!=b.keys() or any(_different(a[k],b[k],tolerance) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)!=len(b) or any(_different(x,y,tolerance) for x,y in zip(a,b))
    if type(a) is bool or type(b) is bool:return type(a)!=type(b) or a!=b
    return not (isfinite(a) and isfinite(b) and abs(a-b)<=tolerance)


def _prefix(left,right):
    a,b=left['effects'],right['effects']
    changes=sorted({r[0] for r in a+b})
    first=changes[0] if changes else None
    delta=next((t for t in changes if sorted(r[1:] for r in a if r[0]==t)!=sorted(r[1:] for r in b if r[0]==t)),None)
    stop=left['horizon'] if delta is None else delta
    result=dict(t_star=first,t_delta=delta,through=stop,common_effect_epochs=[t for t in changes if delta is None or t<delta])
    def invalid(reason,**detail):
        return dict(result,category='NUMERIC_UNRESOLVED',reason=reason,**detail)
    if left['unknown_effects'] or right['unknown_effects']:return invalid('PENDING_TRANSFER_EFFECT')
    if delta is not None:
        aa=[r[1:] for r in a if r[0]==delta];bb=[r[1:] for r in b if r[0]==delta]
        if any(x in bb for x in aa):return invalid('PENDING_TRANSFER_SIMULTANEOUS_BATCH')
    one=[e for e in left['audit'] if e['t']<=stop];two=[e for e in right['audit'] if e['t']<=stop]
    knots=[e['t'] for e in one];other=[e['t'] for e in two]
    if knots!=other or not knots or knots[0]!=0 or knots[-1]!=stop or knots!=sorted(set(knots)):
        return invalid('PENDING_TRANSFER_GRID',left_only=sorted(set(knots)-set(other)),right_only=sorted(set(other)-set(knots)))
    checked=0
    for p,q in zip(one,two):
        t=p['t']
        for face in ('left','before','right'):
            if face=='right' and delta is not None and t==delta:continue
            if face not in p or face not in q:return invalid('MISSING_FACE',time=t,face=face)
            x,y=p[face],q[face];which='incoming' if face=='left' else 'outgoing'
            da,ta=p[which] if which in p else (p['dt'],p['tol'])
            db,tb=q[which] if which in q else (q['dt'],q['tol'])
            required={'params','protection','flow','service','stocks','heat'}
            if set(x)!=required or set(y)!=required:return invalid('MISSING_FACE',time=t,face=face)
            for k in ('params','protection','flow','service','stocks','heat'):
                tol=0 if k in ('params','protection') else TOL if k in ('flow','service') else (ta+tb if k=='stocks' else (ta+tb)/min(da,db))
                if _different(x[k],y[k],tol):
                    return invalid('PREFIX_STATE',time=t,face=face,field=k,left=x[k],right=y[k],tolerance=tol)
            checked+=1
    return dict(result,points=len(knots),faces=checked,grid_sha256=digest(knots),common_effects_checked=result['common_effect_epochs'])


def compare_pair(left,right):
    if not left or not right:return dict(category='NO_PAIR',reason='MISSING_RETURN')
    if (left['status']=='NONCOMPLIANT' or right['status']=='NONCOMPLIANT' or left['violations'] or right['violations']
        or any(left[k]!=right[k] for k in ('physical_id','public_id','runtime','horizon','opened'))):
        return dict(category='NONCOMPLIANT',reason='ARM_OR_BINDING')
    if left['status']!='OK' or right['status']!='OK':
        return dict(category='NUMERIC_UNRESOLVED',reason='ARM_NUMERICS')
    outcome=_prefix(left,right)
    change=None;first_menu=None;fair=True;same_public=[]
    if len(left['decisions'])!=len(right['decisions']):
        return dict(outcome,category='NONCOMPLIANT',reason='DECISION_COVERAGE')
    for a,b in zip(left['decisions'],right['decisions']):
        if a['time']!=b['time']:fair=False;break
        if change is None:
            if a['evidence']!=b['evidence']:fair=False;break
            same_public.append(a['time'])
            if first_menu is None and a['menu']!=b['menu']:first_menu=a['time']
            if a['task']!=b['task']:
                change=dict(time=a['time'],candidate=a['task'],comparator=b['task'],candidate_choices=a['menu'],
                            comparator_choices=b['menu'],support=[a['support'],b['support']],paid=[a['debit'],b['debit']])
    if not fair:return dict(outcome,category='NONCOMPLIANT',reason='UNEXPLAINED_PUBLIC_DIFFERENCE')
    loss=[];gained=[];switches=[]
    for lhs,rhs,lost in [(left,right,loss),(right,left,gained)]:
        for name in rhs['opened']:
            for typ,epoch in rhs['first'].get(name,{}).items():
                if typ not in lhs['first'].get(name,{}):lost.append([name,'ever',typ])
                if TYPES.get(lhs['states'][f'{epoch:g}'].get(name))!=typ:lost.append([name,'first-at',typ,epoch])
            for t in ('5','7.5','12'):
                y=TYPES.get(rhs['states'][t].get(name));x=TYPES.get(lhs['states'][t].get(name))
                if y is not None and x!=y:lost.append([name,t,y])
                if lost is loss and x and y and x!=y:switches.append([name,t,y,x])
    if 'category' not in outcome:outcome['category']=service_direction(left['service'],right['service'])
    delta={k:[str(Fraction(b)-Fraction(a)) for a,b in zip(left['service'][k],right['service'][k])] for k in ('rate','balance')}
    return dict(outcome,resources=resource_direction(left['resources'],right['resources']),
        resource_delta=[str(Fraction(b)-Fraction(a)) for a,b in zip(left['resources'],right['resources'])],
        service_delta=delta,closures_preserved=not loss,lost=loss,gained=gained,type_changes=switches,
        first_menu_difference=first_menu,first_issue_difference=change,matched_public_roots=len(same_public))


def panel(rows,pair_results,positions):
    """Aggregate against the manifest, including absent, failed, and withheld slots."""
    counts={};comparisons=[];slots={}
    for row in rows:
        rid=row['id']
        for method in row['arms']:
            key=rid+'-'+method
            slots[key]=positions.get(key,'UNEXECUTED')
            if method=='J':continue
            typ='J/B' if method=='B' else method
            bucket=counts.setdefault(typ,dict.fromkeys(CATEGORIES,0))
            names=[rid+'-J',key]
            pair=pair_results.get(key)
            if not pair or any(positions.get(k)!='RETURNED' for k in names):
                pair=dict(category='NO_PAIR',reason='MISSING_OR_FAILED_POSITION',pair=names)
            cat=pair['category']
            if cat not in CATEGORIES:raise ValueError('Unknown paired outcome')
            bucket[cat]+=1;comparisons.append(dict(row=rid,control=method,**pair))
    primary=[p for p in comparisons if p['control']=='B']
    valid={'BETTER','WORSE','SAME'}
    all_valid=bool(primary) and all(p['category'] in valid for p in primary)
    dominates=all_valid and all(p['category']!='WORSE' for p in primary) and any(p['category']=='BETTER' for p in primary)
    resource_claim=(all_valid and all(p['category']=='SAME' and p.get('closures_preserved') and
                      p.get('resources') in ('BETTER','SAME') for p in primary) and any(p.get('resources')=='BETTER' for p in primary))
    return dict(counts=counts,denominators={k:sum(v.values()) for k,v in counts.items()},planned=len(slots),
        position_states=slots,positions_by_state=dict(Counter(slots.values())),comparisons=comparisons,
        service_dominance=bool(dominates),service_with_closure=bool(dominates and all(p.get('closures_preserved') for p in primary)),
        equal_service_resource_with_closure=bool(resource_claim))
