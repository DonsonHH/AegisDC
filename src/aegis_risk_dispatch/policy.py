"""Online entry: static public recipes plus a detached decision-time view are the only arguments."""
from .belief import posterior
from .planning import choose_first

PUB_FIELDS={'subjects','workforce','clock','business_ticks','routes','resources','route_graph','fixed_epochs',
            'fixed_ttl','paid_ttl','latency','renew_at'}
VIEW_FIELDS={'time','records','work','paid','writes','fixed','issued'}


FIELDS={
 'records':set('arrived copied_from kind origin record_type sampled source subject until value'.split()),
 'work':set('arrived_at_s basis coverage location_id observed_at_s origin_id reason source_id status task_id'.split()),
 'paid':set('arrived execution fields issued origin parent parent_epoch phase physical_epoch sampled source subject task tool until worker'.split()),
 'writes':set('arrived at epoch execution operation origin outcome source subject task'.split()),
 'fixed':set('arrived field ok origin sampled source until'.split()),
 'issued':set('at execution instance parent parent_epoch patrol_slot phase planned_end subject task tool worker'.split())}
SUBJECT_FIELDS=set('id key interface worker tool location start expertise read_asset write_asset operation write_window read_window renew_window allow_initial review primary'.split())
PAID_FIELDS=set('q g e versions source_group contact upstream released request permitted ready actual_takeover group_kW transfer_kW alternate_kW running latched controller_on automatic_restart power_returned under_construction handover commissioned'.split())
PROFILE_FIELDS=set('access_check_s basis facility_id feedback_latency_s id nominal_knowledge_id schema shifts source_note time_unit walk_times_s work_times_s'.split())


def validate(pub,view):
    if set(pub)!=PUB_FIELDS or set(view)!=VIEW_FIELDS or view['time'] not in pub['clock']:
        raise ValueError('Invalid public envelope')
    if any(set(s)!=SUBJECT_FIELDS for s in pub['subjects']) or set(pub['workforce'])!=PROFILE_FIELDS:
        raise ValueError('Unexpected public declaration fields')
    if any(set(r)-set('id kind from to bidirectional requires_qualification_ids'.split()) for r in pub['route_graph']):
        raise ValueError('Unexpected public route')
    for channel,fields in FIELDS.items():
        if any(set(row)-fields for row in view[channel]):raise ValueError('Unexpected message fields: '+channel)
    if any(r['fields'] is not None and set(r['fields'])-PAID_FIELDS for r in view['paid']):
        raise ValueError('Unregistered observation')
    now=view['time']
    if any(r['arrived']>now or r['sampled']>r['arrived'] for ch in ('records','fixed','paid') for r in view[ch]):
        raise ValueError('Prospective evidence')
    if any(w['arrived']>now or w['at']>w['arrived'] for w in view['writes']):
        raise ValueError('Prospective write')
    if any(w['arrived_at_s']>now or w['observed_at_s']>w['arrived_at_s'] for w in view['work']):
        raise ValueError('Prospective work')
    if any(w['at']>now for w in view['issued']):raise ValueError('Prospective issue')


def priorities(pub,view,gate):
    now=view['time'];done={q['task'] for q in view['issued']}
    subs=gate.entries(pub)
    mandatory=sorted((s for s in pub['routes'] if s+'::A' in done and s+'::R' not in done),
                     key=lambda sid:(subs[sid]['read_window'][1],sid))
    renew=sorted((sid for sid in pub['routes'] if now>=pub['renew_at'] and sid+'::X' not in done),
                 key=lambda sid:(subs[sid]['renew_window'][1],sid))
    return [(s,'R',None) for s in mandatory],[(s,'X',None) for s in renew]


def alarm_and_work(pub,view,gate):
    now=view['time'];done={r['task'] for r in view['issued']}
    alarms=[]
    for note in gate.live(view,'alarm'):
        if now<=note['arrived']:continue
        route=pub['routes'] if note['subject'] in ('power-board','cooling-board') else [note['subject']]
        alarms.extend((s,'A',None) for s in route if s in pub['routes'] and s+'::A' not in done)
    evidence=[]
    for s in pub['subjects']:
        sid=s['id']
        if not s['primary'] or sid+'::A' in done:continue
        if any(r['until']>now and r['phase']=='I' and gate.actionable(s['key'],r['fields'])
               for r in gate.each_read(view,sid)):evidence.append((sid,'A',None))
    return alarms,evidence


def patrol(pub,view,gate):
    now=view['time'];visits={q['patrol_slot']:q for q in view['issued'] if q['patrol_slot']}
    done={q['task'] for q in view['issued']};subs=gate.entries(pub)
    for cycle in range(4):
        if cycle*900>now:break
        for sid in pub['routes']:
            slot=f'{cycle}/{sid}'
            if slot in visits:
                if gate.ack(view,visits[slot]['task']) is None:return []
            else:
                phase='I' if subs[sid]['allow_initial'] and sid+'::I' not in done else 'V'+str(cycle)
                return [(sid,phase,slot)]
    return []


def first_legal(options,pub,view,gate):
    subs=gate.entries(pub);seen=set();reject=[]
    for sid,phase,slot in options:
        if (sid,phase) in seen:continue
        seen.add((sid,phase))
        req,why=gate.admit(pub,view,subs[sid],phase,slot)
        if req:return req,reject
        reject.append([sid,phase,why])
    return None,reject


def decide(role,pub,view,settings,gate):
    validate(pub,view)
    subs=gate.entries(pub);statuses={sid:gate.certificate(s,view) for sid,s in subs.items()}
    required,renew=priorities(pub,view,gate)
    if role in ('PA','B'):
        alarms,paid=alarm_and_work(pub,view,gate)
        if role=='PA':
            candidates=required+alarms+paid+renew+patrol(pub,view,gate)
        else:
            opened={r['subject'] for r in gate.live(view,'order')}
            done={r['task'] for r in view['issued']}
            # Direct on the open signed order itself, with additional urgency from an arrived alarm or read.
            direct=[(s,'A',None) for s in pub['routes'] if s in opened and s+'::A' not in done and statuses[s]!='NA']
            candidates=required+renew+alarms+paid+direct
        req,declined=first_legal(candidates,pub,view,gate)
        return dict(request=req,refusals=declined,certificates=statuses,
                    rationale=dict(version=role,priority=candidates,chosen=req['task'] if req else 'WAIT'))
    price=settings['versions'][role];weights,belief=posterior(pub,view,settings)
    req,reject=first_legal(required+renew,pub,view,gate)
    why='MANDATORY_OWN_WORK' if req else 'VALUE'
    branches=[];first=None
    if not req:
        waiting=False
        for r in view['issued']:
            if r['phase']!='I':continue
            terminal=gate.ack(view,r['task'])
            absent=not any(z['task']==r['task'] for z in view['paid'])
            if terminal is None and view['time']<=r['planned_end']+pub['latency']:
                waiting=True
            if terminal and terminal['status']=='completed' and absent and view['time']<terminal['observed_at_s']+pub['latency']:
                waiting=True
        if not weights:why='UNSUPPORTED_PUBLIC_EVIDENCE'
        elif waiting:why='AWAIT_OWN_PAID_RESULT'
        else:
            req,diagnostics,branches,first=choose_first(pub,view,weights,price,settings,gate)
            reject+=diagnostics
            if not branches:why='NO_COMPLETE_ADMITTED_BRANCH'
    return dict(request=req,refusals=reject,certificates=statuses,rationale=dict(version=role,price=price,
        reason=why,posterior=belief,continuation_table=branches,winning_first=first,chosen=req['task'] if req else 'WAIT'))
