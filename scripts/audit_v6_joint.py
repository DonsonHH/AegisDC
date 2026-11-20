"""Independent saved-output checks. This module never imports the joint plant, planner or evidence implementation."""
from fractions import Fraction
import hashlib
import json
import math


def digest(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def equal(a,b):
    if isinstance(a,bool) or isinstance(b,bool):return type(a) is type(b) and a==b
    if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    if a==b:return True
    try:return math.isclose(float(Fraction(str(a))),float(Fraction(str(b))),rel_tol=0,abs_tol=1e-8)
    except (ValueError,TypeError,ZeroDivisionError):return False


class Checks:
    def __init__(self):
        self.rows=[]
    def compare(self,label,actual,expected):
        self.rows.append(dict(check=label,ok=equal(actual,expected),actual=actual,expected=expected))
    def condition(self,label,actual):
        self.compare(label,bool(actual),True)
    def report(self,details):
        failures=[r for r in self.rows if not r['ok']]
        return dict(passed=not failures,assertions=len(self.rows),failures=failures,details=details,checks=self.rows)


def label(task):
    kind,origin,phase=task.split('/')
    return kind+'.'+phase


def native_check_label(task,multiple):
    kind,origin,phase=task.split('/')
    return (kind+'#'+origin[1:] if multiple and kind=='C' else kind)+'.'+phase


def public_case(key,item,actual,expected):
    c=Checks()
    if key.startswith('G'):
        c.compare(item['op'],actual,expected)
        return c.report(dict(interface=item['op'],actual=actual))
    c.compare('actual public decision',actual['choice'],expected['first'])
    alts=actual['alternatives']
    for i,kind in enumerate(('W','C.A','N.A')):
        if 'loss_hold_C_N' not in expected:break
        chosen=next((r for r in alts if (not r['sequence'] and kind=='W') or
                    (len(r['sequence'])==1 and label(r['sequence'][0])==kind)),None)
        c.compare(kind+' projected deficit',chosen['score'][0] if chosen and chosen['score'] else None,expected['loss_hold_C_N'][i])
    if 'loss_both' in expected:
        viable=[r for r in alts if len(r['sequence'])==2 and r['admitted']]
        c.compare('both legal orders',len(viable),2)
        for row in viable:c.compare('joint loss '+' '.join(row['sequence']),row['score'][0],expected['loss_both'])
    for name,cost in expected.get('best_probe_work',{}).items():
        row=next((r for r in alts if len(r['sequence'])==1 and label(r['sequence'][0])==name and 'branches' in r),None)
        c.compare('conditional paid work '+name,row['score'][1] if row else None,cost)
    return c.report(dict(choice=actual['choice'],support=actual['prefix']['support'],candidates=len(alts),
        score=actual['selected']['score'] if actual['selected'] else None,semantic_decision=digest(actual)))


def certificate_from_records(cfg,view,instance,opening):
    issued={r['task']:r for r in view['issued']}
    ack={};writes={}
    for task,issue in issued.items():
        typ=cfg['types'][task.split('/')[0]]
        terminal=[r for r in view['work'] if r['task']==task and r['origin']=='workforce:'+task
                  and r['status'] in ('completed','rejected','aborted')
                  and (r['worker'],r['tool'])==(typ['worker'],typ['tool'])
                  and r['location']==(typ['location'] if r['status']=='completed' else None)
                  and all(type(r[k]) in (int,float) and math.isfinite(r[k]) for k in ('at','arrived'))
                  and issue['at']<=r['at']<=r['arrived']<=view['time']]
        if len({(r['status'],r['at']) for r in terminal})!=1 or terminal[0]['status']!='completed':continue
        ack[task]=min(terminal,key=lambda r:r['arrived'])
        if not task.endswith('/A'):continue
        effects=[r for r in view['writes'] if r['task']==task and r['origin']=='intervention:'+task
                 and r['operation']==typ['operation'] and r['outcome'] in ('APPLIED','NO_EFFECT')
                 and all(type(r[k]) in (int,float) and math.isfinite(r[k]) for k in ('at','arrived'))
                 and r['at']==ack[task]['at'] and r['at']<=r['arrived']<=view['time']]
        if effects and {r['outcome'] for r in effects}=={'APPLIED'}:
            writes[task]=min(effects,key=lambda r:r['arrived'])
    kind=instance[:1];acted=instance+'/A' in issued;target=instance+('/R' if acted else '/I')
    if acted:
        action=instance+'/A'
        if target not in issued or action not in ack or action not in writes:return 'OPEN'
        if issued[target]['at']<max(ack[action]['arrived'],writes[action]['arrived']):return 'OPEN'
        start=writes[action]['at']
    else:start=opening
    paid=[r for r in view['paid'] if r['task']==target and r['instance']==instance and r['phase']==target[-1]]
    if paid and all(r['until']<=view['time'] for r in paid):return 'OPEN_EXPIRED'
    if target not in ack:return 'OPEN'
    fields={r['field']:r['interval'] for r in paid if view['time']<r['until'] and r['at']==ack[target]['at']
        and r['bundle']==f"{target}@{r['at']:g}" and r['source']=='onsite-'+kind and r['interval'] is not None}
    if kind=='C':normal='q' in fields and .099<=fields['q'][0]<=fields['q'][1]<=.101
    else:normal=all(f in fields and fields[f][0]>=1 for f in ('g','e'))
    if not normal:return 'OPEN'
    needed=['lake' if kind=='C' else 'network']+(['service'] if acted else [])
    for f in needed:
        samples=[r for r in view['fixed'] if r['field']==f and r['source']=='fixed-'+f and r['at']>=start]
        def good(r):
            lo,hi=r['interval']
            return 99.7<=lo<=hi<=99.9 if f=='lake' else lo>=1
        times=[r['at'] for r in samples if r['until']>view['time'] and good(r)]
        last_bad=max([r['at'] for r in samples if not good(r)]+[-1])
        usable=[t for t in times if t>last_bad]
        if not usable or max(usable)-min(usable)<1:return 'OPEN'
    return 'POST_ACTION_VERIFIED_CURRENT' if acted else 'NO_ACTION_CURRENT'


def physiology(run):
    trace=run['trace'];balances=run['balances'];p={x['id']:x['value'] for x in run['source_config']['parameters']}
    losses=[];unserved=[];workers=[];tools=[];consistent=True;conserved=True
    for b,left,right in zip(balances,trace,trace[1:]):
        dt=b['end_s']-b['start_s'];state=left['domains'];it=state['it_service']
        consistent &= dt>0 and left['time_s']==b['start_s'] and right['time_s']==b['end_s']
        losses.append(dt*(it['demand']-it['delivered'])/it['demand'] if it['demand'] else 0)
        unserved.append(dt*(it['demand']-it['delivered']))
        workforce=state['people_tools_work'];busy={w for w,r in workforce['workers'].items()
                                                   if r['status'] in ('travelling','working','waiting')}
        for task in workforce.get('queued_requests',[]):
            record=next(x for x in run['work_records'] if x['id']==task)
            busy.update(w['worker_id'] for w in record['crew'] if workforce['workers'][w['worker_id']]['status']=='idle')
        workers.append(dt*len(busy))
        tools.append(dt*sum(x['reserved_by'] is not None for x in workforce['tools'].values()))
        energy_tol=p['energy_absolute_tolerance']+p['balance_relative_tolerance']*(abs(b['boundary_input_J'])+abs(b['boundary_output_J']))
        conserved &= all(abs(v)<=energy_tol for v in b['energy_residuals_J'].values()) and abs(b['electrical_residual_W'])*dt<=energy_tol
        conserved &= all(abs(math.fsum([x['before_kg'],x['in_kg'],-x['out_kg'],-x['after_kg']]))<=p['mass_absolute_tolerance'] for x in b['mass_accounts_kg'].values())
        before,after,rates=b['storage_before_J'],b['storage_after_J'],b['component_energy_rates_W']
        conserved &= before.keys()==after.keys()==rates.keys()
        conserved &= all(abs((after[k]-before[k])-rates[k]*dt)<=energy_tol for k in rates)
        inventory_change=math.fsum(after.values())-math.fsum(before.values())
        conserved &= abs(inventory_change-(b['boundary_input_J']-b['boundary_output_J']))<=energy_tol
    s=run['summary'];whole=(s['final_stored_energy_J']-s['initial_stored_energy_J'])-(s['boundary_input_J']-s['boundary_output_J'])
    conserved &= abs(whole)<=p['energy_absolute_tolerance']+p['balance_relative_tolerance']*(abs(s['boundary_input_J'])+abs(s['boundary_output_J']))
    return dict(rate=[math.fsum(losses),math.fsum(unserved)],balance=[math.fsum(b['service_deficit_time_s'] for b in balances),
            math.fsum(b['demand_service_unit_s']-b['delivered_service_unit_s'] for b in balances)],
        physical_work=[math.fsum(workers),math.fsum(tools)],native_work=[sum(s[k] for k in ('worker_travel_person_s','worker_work_person_s','worker_wait_person_s')),s['tool_occupation_tool_s']],
        continuous=bool(consistent and len(trace)==len(balances)+1 and trace[0]['time_s']==0 and trace[-1]['time_s']==s['duration_s']),
        conserved=bool(conserved))


def work_receipt_statistics(jobs, messages, cfg, as_of):
    """Independent retrospective task waits and work-message latencies.

    Only compare a public terminal with saved physical completion after resolving
    its public identity. Missing or conflicting tasks remain in the denominator.
    """
    def finite_clock(x):
        return type(x) in (int, float) and math.isfinite(x)
    if not finite_clock(as_of):
        raise ValueError('Expected a finite reporting cutoff')
    issued = {j['id']: j for j in jobs if j['issued_at_s'] <= as_of}
    if len(issued) != sum(j['issued_at_s'] <= as_of for j in jobs):
        raise ValueError('Duplicate actual issued task')
    arrivals = {}
    raw_lags = []
    rejected = 0
    for msg in messages:
        at, arrived = msg.get('observed_at_s'), msg.get('arrived_at_s')
        if finite_clock(arrived) and arrived > as_of:
            continue
        task = msg.get('task_id')
        job = issued.get(task)
        kind = task.split('/')[0] if isinstance(task, str) else None
        typ = cfg['types'].get(kind)
        status = msg.get('status')
        valid = (job is not None and typ is not None and finite_clock(at) and finite_clock(arrived)
                 and job['issued_at_s'] <= at <= arrived <= as_of
                 and msg.get('source_id') == 'workforce-execution-report' and msg.get('origin_id') == 'workforce:'+task
                 and msg.get('coverage') == 'THIS_ISSUED_TASK_ONLY'
                 and job['work_interface_id'] == typ['interface'] and job['tool_carrier_id'] == typ['worker']
                 and job['crew'] == [dict(worker_id=typ['worker'],qualification_id=typ['qualification'])]
                 and job['target_id'] == (typ['asset'] if task.endswith('/A') else typ['target'])
                 and status in ('completed','aborted','rejected','safety_stop_observed') and 'location_id' in msg
                 and msg['location_id'] == (typ['location'] if status == 'completed' else None))
        if not valid:
            rejected += 1
            continue
        identity = (task, msg['origin_id'], status, at, msg['location_id'])
        raw_lags.append(arrived-at)
        arrivals.setdefault(identity, []).append(arrived)
    by_task = {key: [] for key in issued}
    logical = []
    for (task, origin, status, at, location), times in sorted(arrivals.items()):
        earliest = min(times)
        logical.append(dict(task=task, origin=origin, status=status, at=at, location=location,
                            arrived=earliest, lag_s=earliest-at, deliveries=len(times)))
        if status != 'safety_stop_observed':
            by_task[task].append((status,at,earliest))
    waits, held, conflicts = {}, {}, []
    for task, terminals in by_task.items():
        job = issued[task]
        waits[task] = held[task] = None
        if not terminals:
            continue
        if (len(terminals) != 1 or terminals[0][0] != job['status']
                or terminals[0][1] != job.get('finished_at_s')):
            conflicts.append(task)
            continue
        _, observed, arrived = terminals[0]
        waits[task] = arrived - observed
        held[task] = arrived - job['issued_at_s']
    known = [v for v in waits.values() if v is not None]
    processes = sum(r['status']=='safety_stop_observed' for r in logical)
    return dict(issued_tasks=len(issued), task_waits=waits, held_s=held, known_tasks=len(known),
                unresolved=sorted(k for k,v in waits.items() if v is None), conflicts=sorted(conflicts),
                total_wait_s=math.fsum(known) if len(known)==len(issued) else None, known_wait_sum_s=math.fsum(known),
                raw_count=len(raw_lags), unique_count=len(logical), process_count=processes,
                terminal_count=len(logical)-processes, duplicate_deliveries=len(raw_lags)-len(logical),
                logical_delay_s=math.fsum(r['lag_s'] for r in logical), raw_delay_s=math.fsum(raw_lags),
                rejected=rejected, messages=logical)


def native_case(key,item,run,oracle):
    c=Checks();expected=oracle['units'][key]
    cfg=item['dispatch_program']['policy_program']
    c.compare('empty scripted native commands',run['inputs'].get('action_commands',[]),item.get('action_commands',[]))
    c.compare('empty direct work requests',run['inputs'].get('work_requests',[]),item.get('work_requests',[]))
    c.compare('private native evaluator identity',digest(run['inputs'].get('business_program')),digest(item.get('business_program')))
    c.compare('frozen source config',digest(run['source_config']),digest(item['scenario']))
    c.compare('frozen public program',digest(run['inputs']['dispatch_program']),digest(item['dispatch_program']))
    c.compare('exogenous and horizon',[run['inputs']['boundary_events'],run['summary']['duration_s'],run['inputs']['maximum_step_s']],
              [item['boundary_events'],item['duration_s'],item['step_s']])
    if key.startswith('L'):
        from aegis_dc.native_compare_score import score_arm
        scored=score_arm(run,run['trace'],run['balances'])
        c.compare('unchanged original semantic digest',scored['semantic_sha256'],expected['expected_semantic_sha256'])
        c.compare('old constraints',scored['violations'],[]);c.compare('old clock',scored['internal_policy_calls'],20)
        return c.report(dict(semantic=scored['semantic_sha256'],decisions=20,service=scored['service'],work=scored['resources']['balance']))
    account=physiology(run);c.condition('complete time intervals',account['continuous']);c.condition('native and independent conservation',account['conserved'])
    c.compare('independent integral vs saved balances',account['rate'],account['balance'])
    c.compare('physical occupation vs native work',account['physical_work'],account['native_work'])
    decisions=run['policy_public_decisions'];by_time={x['view']['time']:x for x in decisions}
    c.compare('actual public clock',list(by_time),cfg['clock'])
    c.condition('private sidecar excluded from plant dispatch','business_evaluation' not in run)
    trace={r['time_s']:r['domains'] for r in run['trace']}
    final_reads=run['inspection_public_feedback'];work=run['work_records'];native_acks=run['workforce_public_feedback']
    writes=run['intervention_public_feedback'];audit_writes=run['intervention_private_audit']['events']
    selected=[r['decision']['request'] for r in decisions if r['decision']['request']]
    c.compare('real work equals issued requests',[(r['id'],r['issued_at_s']) for r in work],[(r['task'],r['at']) for r in selected])
    c.compare('unique real issues',len({r['id'] for r in work}),len(work))
    for r in final_reads:
        _task=next(x for x in work if x['id']==r['task'])
        c.condition('own sample '+r['task']+'/'+r['field'],_task['status']=='completed' and r['at']==_task['completed_at_s'] and
                    r['arrived']==r['at']+cfg['latency'] and r['until']==r['at']+cfg['paid_ttl'])
    first={};actual_certs={};views={};openings={}
    for d in decisions:
        v=d['view'];t=v['time'];choice=d['decision'];pub=choice['certificates']
        c.compare(f'public interface {t}',sorted(v),sorted(['time','orders','issued','work','writes','paid','fixed']))
        c.compare(f'paid arrival {t}',v['paid'],[r for r in final_reads if r['arrived']<=t])
        c.compare(f'work arrival {t}',[(x['task'],x['status'],x['at']) for x in v['work']],
                  [(x['task_id'],x['status'],x['observed_at_s']) for x in native_acks if x['arrived_at_s']<=t])
        c.compare(f'write arrival {t}',[(x['task'],x['outcome'],x['at']) for x in v['writes']],
                  [(x['task_id'],x['outcome'],x['observed_at_s']) for x in writes if x['arrived_at_s']<=t])
        actual_fixed=[]
        for epoch in cfg['fixed_epochs']:
            if epoch+cfg['latency']>t:continue
            state=trace[epoch]
            real={'lake':state['facility_cooling']['lake_mass_flow_kg_s'],'network':state['it_service']['capacities']['network'],'service':state['it_service']['delivered']}
            actual_fixed.extend((f,epoch,real[f]) for f in cfg['fixed_on'])
        c.compare(f'fixed acquisition and release {t}',[(x['field'],x['at'],x['interval'][0]) for x in v['fixed']],actual_fixed)
        for o in v['orders']:
            for k,typ in cfg['types'].items():
                if (o['desk'],o['target'],o['observable'],o['value'])==(typ['desk'],typ['target'],'problem_reported',True) and o['copied_from'] is None and o['arrived']<=t<o['until'] and (o['revoked_at'] is None or t<o['revoked_at']):
                    openings.setdefault(k+'/'+o['origin'],t)
        own={i:certificate_from_records(cfg,v,i,at) for i,at in openings.items()}
        c.compare(f'independent instance states {t}',pub,own)
        for i,value in own.items():
            if value in ('NO_ACTION_CURRENT','POST_ACTION_VERIFIED_CURRENT'):
                first.setdefault(i,dict(time=t,state=value))
        if t in (5,7.5,9,10,12,2700,3600):actual_certs[f'{t:g}']=own
        views[f'{t:g}']=digest(dict(view=v,decision=choice))
    receipt_stats=work_receipt_statistics(work,native_acks,cfg,item['duration_s'])
    ack_wait=receipt_stats['total_wait_s']
    work_summary=account['physical_work']+[len(work)]
    c.compare('every issued task has one known terminal',receipt_stats['known_tasks'],len(work))
    c.compare('task terminal delay is separate from message latency and physical work',ack_wait,len(work)*cfg['latency'])
    cap=[sum(cfg['deadline']-x['release'] for x in selected)]*2+[len(work)*cfg['fee']]
    c.condition('actual nonrefunded cap',all(x<=y for x,y in zip(cap,cfg['caps'])))
    details=dict(decisions=len(decisions),physical_integrals=account['rate'],work=work_summary,debit=cap,
                 wait_for_public_receipts_s=ack_wait,work_receipt_statistics=receipt_stats,first=first,current=actual_certs,open_instances=list(openings),prefix_sha256=views)
    if key.startswith('S'):
        e=expected['expected'];chain=oracle['chains'][e['chain']];multi=key=='S17'
        entries=[]
        for x in work:
            ack=next(a for a in native_acks if a['task_id']==x['id'])
            entries.append([native_check_label(x['id'],multi),x['issued_at_s'],x['finished_at_s'],ack['arrived_at_s']])
        want=[[name,number(a),number(str(b).split(' ')[0]),number(str(end).split(' ')[0])] for name,a,b,end in chain]
        c.compare('actual chronological stages',entries,want)
        c.compare('literal L and U',account['rate'],[e['L'],e['U']])
        c.compare('actual work, fees and envelope',work_summary+cap[:2],oracle['costs'][e['chain']])
        def tags(certs):
            labels=[]
            for i,s in certs.items():
                if s not in ('NO_ACTION_CURRENT','POST_ACTION_VERIFIED_CURRENT'):continue
                k,org=i.split('/')
                labels.append((k+'#'+org[1:] if multi else k)+('.NA' if s=='NO_ACTION_CURRENT' else '.PV'))
            return sorted(labels)
        c.compare('complete positive ever',tags({i:v['state'] for i,v in first.items()}),sorted(e['first_and_current_at_7_5']))
        c.condition('first positive times',all(v['time']==7.5 for v in first.values()))
        c.compare('current 7.5',tags(actual_certs['7.5']),sorted(e['first_and_current_at_7_5']))
        c.compare('current H12',tags(actual_certs['12']),sorted(e['current_at_H']))
        got={}
        for w in audit_writes:
            got[native_check_label(w['task_id'],multi)]=[w['old_value'],w['new_value']] if w['outcome']=='APPLIED' else w['outcome']
        for task in {r['task'] for r in final_reads}:
            fields={r['field']:r['interval'][0] if r['interval'] is not None else None for r in final_reads if r['task']==task}
            got[native_check_label(task,multi)]=fields.get('q') if task.startswith('C/') else [fields.get('g'),fields.get('e')]
        c.compare('independent expected read and actual write values',got,oracle['physical_expected'][key])
        for trow,extra in zip(oracle['temporal'].get(key,[]),oracle['temporal_remaining'].get(key,[])):
            t,worlds,confirmed,pending,owed,success,fail=trow
            choice=by_time[t]['decision'];p=choice['prefix']
            c.compare(f'original worlds and confirmed prefix {t}',[p['support'],p['confirmed'],p['pending'],p['obligations']],
                      [sorted(worlds),sorted(confirmed),sorted(pending),sorted(owed)])
            c.compare(f'shared paid prefix and remaining first operation {t}',[choice['choice'],p['debit'][0],p['reserved_review']],extra)
            if success is not None:
                c.compare(f'W conditional benefit is not an actual write {t}',[p['W_conditional'][','.join(sorted(pending))],p['W_conditional']['']],[success,fail])
        details.update(stages=entries,observations_and_writes=got)
    else:
        lim=oracle['thermal_limits'];series=run['trace']
        trips=[s['time_s'] for s in series if s['domains']['control_monitoring']['protection_latched']]
        highest=max(s['domains']['equipment_environment']['refrigerant']['temperature_K'] for s in series)
        masked=key in lim['mask'];direct=item['dispatch_program']['policy_program']['method']=='C_DIRECT'
        c.compare('warm paid native work',work_summary,[4.5,4.5,2] if direct else [0,0,0])
        if direct:
            c.compare('actual warm write',[w['old_value'] for w in audit_writes]+[w['new_value'] for w in audit_writes],[100,1])
            c.compare('actual early action chronology',[(x['issued_at_s'],x['finished_at_s']) for x in work],[(0,3.25),(3.75,5)])
        if masked:c.compare('network zero mask',account['rate'],lim['zero_mask_L_U'])
        elif direct:
            c.compare('full warm delivery',account['rate'],[0,0]);c.condition('clean protection permits load',not trips and highest<325)
        else:c.condition('trip and service interruption within predicted bound',bool(trips) and trips[0]<=2700 and min(account['rate'])>0)
        c.compare('local/service certificate at 7.5',bool(first),direct and not masked)
        c.condition('sparse fixed evidence expired',all(v not in ('POST_ACTION_VERIFIED_CURRENT','NO_ACTION_CURRENT') for t in (9,10,2700,3600) for v in by_time[t]['decision']['certificates'].values()))
        flow=lambda s:s['facility_cooling']['lake_pump']['volume_flow_m3_s']
        c.condition('dirty flow',.0111<flow(trace[0])<.0113)
        if direct:c.condition('clean observed flow',.0999<flow(trace[3.25])<.1001)
        energy_by_t={b['start_s']:b for b in run['balances'] if b['start_s']<3.25}
        details.update(first_trip=trips[0] if trips else None,max_Tsat_K=highest,
            warm_prefix={f"{s['time_s']:g}":dict(heat=s['domains']['facility_cooling']['plate_hx_heat_W'],
                stored_J={k:energy_by_t[s['time_s']]['storage_before_J'][k] for k in ('coolant','hot','cold','solid')},
                dt=energy_by_t[s['time_s']]['end_s']-s['time_s'],
                boundary_abs_J=abs(energy_by_t[s['time_s']]['boundary_input_J'])+abs(energy_by_t[s['time_s']]['boundary_output_J']),
                q=flow(s['domains']),service=s['domains']['it_service']['delivered'],latched=s['domains']['control_monitoring']['protection_latched'],
                Tsat=s['domains']['equipment_environment']['refrigerant']['temperature_K'],
                hot=s['domains']['facility_cooling']['hot_temperature_K'],cold=s['domains']['facility_cooling']['cold_temperature_K'],
                solid=s['domains']['equipment_environment']['solid_temperature_K'])
                for s in series if s['time_s']<3.25},
            q_at_3_25=flow(trace[3.25]),heat_at_3_25=trace[3.25]['facility_cooling']['plate_hx_heat_W'])
    return c.report(details)


def number(value):
    return float(Fraction(str(value)))
