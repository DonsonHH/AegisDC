"""Exercise the declared public component interfaces; expected answers live in the frozen oracle."""
from aegis_dc.joint_evidence import at_time, certificate, instances, observation
from aegis_dc.joint_forecast import support
from aegis_dc.joint_resources import public_prefix, schedule


def evaluate(item):
    cfg,source,args=item['program'],item['view'],item['args']
    v=at_time(source,source['time'])
    op=item['op']
    if op=='classify':
        return [observation(cfg,at_time(source,t),args['task'])[0] for t in args['times']]
    if op in ('schedule','feasibility','route'):
        seq=args.get('sequence',[args.get('task')])
        plan=schedule(cfg,v,seq)
        if op=='schedule':return {k:plan[k] for k in ('admitted','required','work')}
        if op=='feasibility':return plan['admitted']
        first=plan['steps'][0]
        return [first['planned_end'],first['planned_ack']]
    if op=='handoff':
        rows=[]
        for t in args['times']:
            plan=schedule(cfg,at_time(source,t),[args['task']])
            rows.append(plan['steps'][0])
        return [r['at']==t for r,t in zip(rows,args['times'])]+[rows[-1]['planned_end'],rows[-1]['planned_ack']]
    if op=='aborted':
        root=public_prefix(cfg,v);actual=[sum((b-a)*r[i] for a,b,*r in args['occupation']) for i in (0,1)]
        typ=cfg['types']['N']
        return dict(debit=root['debit'],pose=[root['pose'][typ[k]] for k in ('worker','tool')],
                    obligations=sorted(root['reviews']),work=actual+[root['debit'][2]])
    if op=='certificate':
        states=[]
        for t in args['times']:
            v=at_time(source,t);instance=args['instance']
            states.append(certificate(cfg,v,instance,instances(cfg,v)[instance]))
        return states
    if op=='support':
        original=support(cfg,v,public_prefix(cfg,v))
        return dict(support=sorted(w['origin'] for w in original),elective_allowed=bool(original))
    if op=='openings':
        return [sorted(instances(cfg,at_time(source,t))) for t in args['times']]
    raise ValueError('Unknown frozen component interface')
