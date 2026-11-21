"""Three fixed status-quo baselines. Imports only public admission and arrived messages."""
from aegis_dc.joint_evidence import certificate, instances, observation
from aegis_dc.joint_messages import own_ack
from public_gate import admit, live_sources


def controller(mode, public, evaluator_schedule=None):
    if mode not in ('P','PERIODIC','ALARM','ORACLE'):
        raise ValueError('Unknown registered role')
    if (mode=='ORACLE') != (evaluator_schedule is not None):
        raise ValueError('Only the evaluation witness receives planned operation times')

    def decide(cfg,view):
        now=view['time']
        issued={r['task']:r for r in view['issued']}
        opens=instances(cfg,view)
        possible=[];reasons=[]
        # A real APPLIED receipt and own terminal work are required in admit.
        if mode!='P':
            for task in sorted(issued):
                if task.endswith('/A') and task[:-1]+'R' not in issued:
                    possible.append((task[:-1]+'R',None))
        if mode=='ALARM':
            live=live_sources(view,'alarm')
            for row in sorted(live,key=lambda r:(0 if r['desk']=='cooling-service-desk' else 1,r['arrived'],r['origin'])):
                kind='C' if row['desk']=='cooling-service-desk' else 'N'
                instance=kind+'/'+row['origin']
                if now>row['arrived'] and instance in opens and instance+'/A' not in issued:
                    possible.append((instance+'/A',None))
        elif mode=='PERIODIC':
            for task in public['paid_opportunities']:
                state,_=observation(cfg,view,task)
                if state in ('LOW_FLOW','CONFIG_LIMIT_CURRENT','MIXED_LIMIT_CURRENT') and task[:-1]+'A' not in issued:
                    possible.append((task[:-1]+'A',None))
            vertices={r['patrol_slot']:r for r in issued.values() if 'patrol_slot' in r}
            for opening,slot in public['duty_route']:
                if opening>now:break
                if slot in vertices:
                    # Finish the earlier stop before visiting the next, including other specialties.
                    if not own_ack(cfg,view,vertices[slot]['task']):break
                    continue
                k=slot[0];named=public['own_instance'][k]+'/I'
                task=named if named in public['paid_opportunities'] and named not in issued else slot
                possible.append((task,slot))
                break
        elif mode=='ORACLE' and now in evaluator_schedule:
            possible.append((evaluator_schedule[now],None))
        req=None
        for task,slot in possible:
            is_duty=slot is not None and task==slot
            req,reason=admit(cfg,view,task,duty=is_duty)
            reasons.append([task,reason])
            if req:
                if slot is not None:req['patrol_slot']=slot
                break
        return dict(request=req,admissions=reasons,certificates={k:certificate(cfg,view,k,t) for k,t in opens.items()})
    return decide
