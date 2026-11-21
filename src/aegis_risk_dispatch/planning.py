"""Public deterministic schedule and one-observation adaptive tree; no native simulator imports."""
from itertools import permutations
from collections import defaultdict
import math
from . import knowledge as model
from .belief import effects

H=3600


def sequences(items):
    return [seq for size in range(len(items)+1) for seq in permutations(items,size)]


def future_permit(sub,records,t):
    for kind,subject,value in [('NC','NC','HANDOVER_RELEASED'),('NP',None,'POWER_RETURNED')]:
        if sub['key']==kind:
            return any(r['kind']==('release' if kind=='NC' else 'status') and
                       (subject is None or r['subject']==subject) and r['value']==value and
                       r['copied_from'] is None and r['arrived']<=t<r['until'] for r in records)
    return True


class PublicCalendar:
    def __init__(self,pub,view,gate):
        self.pub=pub;self.v=view;self.gate=gate
        self.subjects={s['id']:s for s in pub['subjects']}
        self.clock=pub['clock'];self.t=view['time'];self.occupied={};self.pose={};self.unknown=set()
        self.done={i['task'] for i in view['issued']}
        self.debit=sum(q['planned_end']-q['at'] for q in view['issued'])
        self.reviews={};self.renewals={};self.times={}
        self.fees=len(view['issued'])
        for r in view['issued']:
            s=self.subjects[r['subject']]
            ack=gate.ack(view,r['task'])
            end=ack['arrived_at_s'] if ack else max(self.t+1,r['planned_end']+pub['latency'])
            for k in (s['worker'],s['tool']):
                self.occupied[k]=end
                self.pose[k]=s['location'] if not ack else ack['location_id']
                if ack and ack['status']!='completed':self.unknown.add(k)
            write=next((w for w in view['writes'] if w['task']==r['task']),None)
            if r['phase']=='A' and r['subject']+'::R' not in self.done and (not write or write['outcome']=='APPLIED'):
                self.reviews[r['subject']]=max(end,write['arrived'] if write else end)
        for s in self.subjects.values():
            k=s['id']
            if k+'::X' in self.done:continue
            a=k+'::A' in self.done
            if any(r['phase']==('R' if a else 'I') and gate.adequate(s['key'],r['fields'],a)
                   for r in gate.each_read(view,k)):
                self.renewals[k]=pub['renew_at']
        self.known_effects=effects(pub,view,project=True)
        self.opened={r['subject']:r for r in gate.live(view,'order')}

    def duration(self,s,loc):
        ident=s['id'],loc
        if ident not in self.times:self.times[ident]=self.gate.duration(self.pub,s,loc)
        return self.times[ident]

    def run(self,first,sequence,renew_initial=True):
        """Single clock; apply mandatory own review first, real shifts/locks, complete branch costs."""
        poses=dict(self.pose);busy=dict(self.occupied);reviews=dict(self.reviews);renewals=dict(self.renewals)
        pending=list(sequence);effects_=dict(self.known_effects);steps=[];fees=self.fees;used=self.debit
        closed=set(self.done);until=self.t+(60 if first is None else 0)
        if first is not None:pending.insert(0,first)
        for tick in self.clock:
            if tick<self.t:continue
            if not pending and not reviews and not renewals:break
            # As in the online rule, ready mandatory work precedes elective work.
            options=[(sid,'R') for sid,at in sorted(reviews.items()) if at<=tick]
            options.extend((sid,'X') for sid,at in sorted(renewals.items()) if at<=tick)
            if pending and tick>=until:options.append(pending[0])
            for sid,phase in options:
                s=self.subjects[sid];name=sid+'::'+phase
                if name in closed:return None
                opening=self.opened.get(sid)
                if not opening or tick>=opening['until']:continue
                if any(k in self.unknown or busy.get(k,0)>tick for k in (s['worker'],s['tool'])):continue
                location=poses.get(s['worker'],s['start'])
                d=self.duration(s,location)
                if d is None:continue
                end=tick+d;ack=end+self.pub['latency']
                shift=self.pub['workforce']['shifts'][s['worker']]
                window=s['write_window'] if phase=='A' else s['renew_window'] if phase=='X' else s['read_window']
                if not (shift[0]<=tick<=end<=shift[1] and window[0]<=tick<=end<window[1] and ack<=H):continue
                if phase=='A' and (not s['primary'] or not future_permit(s,self.v['records'],tick)):continue
                if phase=='I' and not s['allow_initial']:continue
                if phase=='X' and not (s['read_window'][0]<=tick<=end<s['read_window'][1]):continue
                if tick==self.t and first is not None and (sid,phase)!=first:return None
                if tick==self.t and first is None:return None
                used+=d;fees+=1
                if used>min(self.pub['resources'][:2]) or fees>self.pub['resources'][2]:return None
                for k in (s['worker'],s['tool']):busy[k]=ack;poses[k]=s['location']
                closed.add(name);steps.append((sid,s['key'],phase,tick,end,ack))
                if phase=='R':
                    del reviews[sid]
                    if sid+'::X' not in closed:renewals[sid]=max(ack,self.pub['renew_at'])
                elif phase=='X':del renewals[sid]
                else:
                    pending.pop(0)
                    if phase=='A':
                        effects_[s['key']]=end;reviews[sid]=ack;renewals.pop(sid,None)
                    else:
                        until=ack
                        if renew_initial and sid+'::X' not in closed:renewals[sid]=max(ack,self.pub['renew_at'])
                break
        # Renewal is a paid conditional obligation only while it can be authorized; an expired
        # renewal grant leaves an open/expired certificate. A corrective branch must fit its own R.
        if pending or reviews:return None
        if first is not None and (not steps or steps[0][0]!=first[0] or steps[0][2]!=first[1] or steps[0][3]!=self.t):return None
        return steps,tuple(sorted(effects_.items()))


def expected(plan,distribution,price,fee_equiv,initial_cost):
    steps,effects_=plan
    loss=person=fees=0.
    for w,mass in distribution:
        actuations=dict(effects_)
        for _,kind,phase,issue,end,ack in steps:
            if phase=='A' and not model.write_success(w,kind,end):actuations.pop(kind,None)
        # This is a conservative prospective price: admitted branch reserves and prices its
        # successful R/renewal path. Native actual costs, including refusals, are independent.
        loss+=mass*model.loss(w,tuple(sorted(actuations.items())))
    person=initial_cost[0]+sum(s[4]-s[3] for s in steps)
    fees=initial_cost[1]+len(steps)
    return loss,person,fees,loss+price*(person+fee_equiv*fees)


def choose_first(pub,view,weights,price,settings,gate):
    cal=PublicCalendar(pub,view,gate);subjects=cal.subjects
    candidates=[];denied=[];done=cal.done;primary=[s for s in pub['subjects'] if s['primary'] and s['id'] in cal.opened]
    actions=[s['id'] for s in primary if s['id']+'::A' not in done and s['write_window'][1]>view['time']]
    fee_equiv=settings['fee_in_person_seconds'];sunk=(cal.debit,cal.fees)
    root_allowed={}
    for s in primary:
        for phase in ('A','I'):
            if phase=='I' and s['id']+'::A' in done:continue
            req,reason=gate.admit(pub,view,s,phase)
            if req:root_allowed[(s['id'],phase)]=req
            else:denied.append([s['id'],phase,reason])
    firsts=[None,*sorted(root_allowed)]
    for first in firsts:
        remaining=[(s,'A') for s in actions if first!=(s,'A')]
        paths=[]
        for seq in sequences(remaining):
            path=cal.run(first,seq,renew_initial=False)
            if path is not None:paths.append((seq,path))
        if not paths:continue
        def select(dist,conditional_paths):
            best=None
            for seq,path in conditional_paths:
                val=expected(path,dist,price,fee_equiv,sunk)
                rank=(round(val[3],9),round(val[1],9),round(val[2],9),len(seq),seq)
                if best is None or rank<best[0]:best=(rank,seq,val,path)
            return best
        table={};raw_vectors=[]
        if first is not None and first[1]=='I':
            sid=first[0];kind=subjects[sid]['key']
            sample_time=paths[0][1][0][0][4];observed=defaultdict(list)
            for w,m in weights:
                observed[model.sample(w,kind,sample_time,cal.known_effects)].append((w,m))
            # One uniform continuation per report group, never one optimum per hidden world.
            unknown=settings['unknown_report_probability']
            for signature,group in sorted(observed.items()):
                gm=sum(m for _,m in group)
                # Only a measured adequate initial reading opens a possible NA renewal.
                adequate=signature in ('OK','CONTACT','CLOSED','READY','COMMISSIONED') or signature.startswith('AUTO/RUN')
                choices=paths
                if adequate:
                    choices=[(seq,z) for seq,_ in paths if (z:=cal.run(first,seq,renew_initial=True)) is not None]
                if not choices:break
                _,seq,val,_=select([(w,m/gm) for w,m in group],choices)
                prob=(1-unknown)*gm
                table[signature]=dict(probability=prob,continue_with=[s for s,_ in seq],cost=list(val))
                raw_vectors.append((prob,val))
            else:
                only=[(seq,z) for seq,z in paths if not seq]
                if not only:continue
                _,_,val,_=select(weights,only)
                table['UNKNOWN']=dict(probability=unknown,continue_with=[],cost=list(val))
                raw_vectors.append((unknown,val))
            if not raw_vectors or abs(sum(m for m,_ in raw_vectors)-1)>1e-8:continue
        else:
            _,seq,val,_=select(weights,paths)
            table['CURRENT']=dict(probability=1,continue_with=[s for s,_ in seq],cost=list(val))
            raw_vectors=[(1,val)]
        vector=[sum(m*v[i] for m,v in raw_vectors) for i in range(4)]
        candidates.append(dict(first=None if first is None else list(first),vector=vector,table=table,
                               admitted_continuation_plans=len(paths)))
    if not candidates:return None,denied,[],None
    selected=min(candidates,key=lambda c:(round(c['vector'][3],9),round(c['vector'][1],9),round(c['vector'][2],9),
                                          c['first'] is not None,tuple(c['first'] or [])))
    return root_allowed.get(tuple(selected['first'] or [])),denied,candidates,selected['first']
