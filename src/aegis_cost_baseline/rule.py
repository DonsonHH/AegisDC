"""Cost-aware transparent baseline. The selector receives the signed schedule and its own receipts."""
import public_work as work
from aegis_action_cost.permit import Gate,exposure


def operative_view(view):
    """Certificate reporting uses other channels separately, after the selector returns."""
    issued={r['task'] for r in view['issued']}
    return dict(time=view['time'],records=[r for r in view['records'] if r['kind'] in ('order','alarm','release','status')],
        issued=view['issued'],work=[r for r in view['work'] if r['task_id'] in issued],
        paid=[r for r in view['paid'] if r['task'] in issued and r['phase'] in ('R','X')],
        writes=[r for r in view['writes'] if r['task'] in issued],fixed=[])


def lawful_signals(pub,view,sub):
    now=view['time'];sid=sub['id'];signals=[]
    for alarm in work.live(view,'alarm'):
        if alarm['value']=='ALARM' and (alarm['subject']==sid or
             (alarm['subject']=='power-board' and sub['key'] in ('LC','LB','LG')) or
             (alarm['subject']=='cooling-board' and sub['key'] in ('NR','NP','NC'))):
            signals.append(alarm['origin'])
    own={r['task']:r for r in view['issued'] if r['subject']==sid}
    for r in view['writes']:
        if r['task'] in own and r['outcome']=='NO_EFFECT' and r['source']=='work-execution' and r['origin']=='write/'+r['task']:
            signals.append(r['origin'])
    for r in view['work']:
        if r['task_id'] in own and r['status'] in ('aborted','rejected') and r['source_id']=='workforce-execution-report' and r['origin_id']=='workforce:'+r['task_id']:
            signals.append(r['origin_id'])
    for r in work.each_read(view,sid):
        if r['task'] in own and r['phase'] in ('R','X') and now<r['until'] and work.actionable(sub['key'],r['fields']):
            signals.append(r['origin'])
    return sorted(set(signals))


def legal_times(pub,view,sub,gate):
    """Hold the current public evidence and outstanding resources fixed; let clocks and expiry advance."""
    now=view['time'];high=sub['write_window'][1]
    options=[]
    for t in pub['clock']:
        if now<=t<high:
            frame=dict(view,time=t)
            admitted,_=gate.admit(pub,frame,sub,'A')
            if admitted:options.append(t)
    return options


def can_share(first,second,recovery,latency):
    """Two already-eligible changes can share a window in this order if its second start still fits."""
    request=first['request'];after=request['planned_end']+recovery
    if request['worker']==second['request']['worker'] or request['tool']==second['request']['tool']:
        after=max(after,request['planned_end']+latency)
    return any(t>request['at'] and t>=after for t in second['slots'])


def decide(pub,view,recovery):
    subjects=work.entries(pub);now=view['time'];gate=Gate(recovery);routes=pub['routes']
    index={sid:i for i,sid in enumerate(routes)}
    done={r['task'] for r in view['issued']};denied=[];schedule=[]
    def response(request,reason):
        return dict(request=request,refusals=denied,rationale=dict(reason=reason,maintenance_s=exposure(view),
             permit_gap_s=recovery,considered=schedule,chosen=request['task'] if request else 'WAIT'))
    # Keep the existing actual-parent obligation and its paid lineage.
    for sid in sorted(routes,key=lambda k:(subjects[k]['read_window'][1],index[k])):
        if sid+'::A' in done and sid+'::R' not in done:
            req,reason=gate.admit(pub,view,subjects[sid],'R')
            if req:return response(req,'OWN_REVIEW')
            denied.append([sid,'R',reason])
    ready=[];duration=exposure(view)
    for sid in routes:
        if sid+'::A' in done:continue
        sub=subjects[sid];req,reason=gate.admit(pub,view,sub,'A')
        if not req:
            denied.append([sid,'A',reason]);continue
        slots=legal_times(pub,view,sub,gate)
        if not slots or slots[0]!=now:raise ValueError('Current legal slot disappeared')
        signals=lawful_signals(pub,view,sub)
        why='ZERO_DURATION' if duration==0 else 'FAULT_SIGNAL' if signals else 'LAST_LEGAL_SLOT' if now==slots[-1] else 'DEFER'
        schedule.append(dict(subject=sid,deadline=sub['write_window'][1],latest=slots[-1],basis=why,signals=signals))
        if why!='DEFER':
            ready.append(dict(subject=sid,request=req,slots=slots,deadline=sub['write_window'][1],basis=why))
    if ready:
        leading=min(ready,key=lambda o:(o['deadline'],index[o['subject']]))
        conflict=[o for o in ready if o is not leading and
                  not can_share(leading,o,recovery,pub['latency']) and not can_share(o,leading,recovery,pub['latency'])]
        selected=min([leading,*conflict],key=lambda o:index[o['subject']])
        return response(selected['request'],('ROUTE_CONFLICT/' if conflict else '')+selected['basis'])
    # A renewal consumes the same resources and may narrow a future deferred write.
    if now>=pub['renew_at']:
        for sid in sorted(routes,key=lambda k:(subjects[k]['renew_window'][1],index[k])):
            if sid+'::A' in done and sid+'::X' not in done:
                req,reason=gate.admit(pub,view,subjects[sid],'X')
                if req:return response(req,'OWN_RENEWAL')
                denied.append([sid,'X',reason])
    return response(None,'WAIT')
