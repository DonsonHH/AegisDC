"""Rank lawful public choices while retaining the original work and evidence interfaces."""
from math import fsum

import public_work as work
from aegis_action_cost import forecast, planning
from aegis_action_cost.permit import Gate, exposure
from aegis_cost_baseline import rule as baseline
from aegis_risk_dispatch import policy as risk
from aegis_risk_dispatch.belief import effects
from common import next_tick

from .space import check, initial


class WithoutInitial(Gate):
    def admit(self, pub, view, subject, phase, slot=None):
        if phase == "I":
            return None, "INITIAL_READ_DISABLED"
        return super().admit(pub,view,subject,phase,slot)


def exact_baseline(pub, view):
    answer = baseline.decide(pub,baseline.operative_view(view),180)
    answer["certificates"] = {s["id"]:work.certificate(s,view) for s in pub["subjects"]}
    return answer


def v3_rank(candidate, correction=0):
    loss, person, fee, total = candidate["vector"]
    return round(total+correction,9),round(person,9),round(fee,9),candidate["first"] is not None,tuple(candidate["first"] or ())


def public_normal(sub, view, level):
    if not level:
        return False
    sid = sub["id"]
    readings = [r for r in work.each_read(view,sid) if r["phase"]=="I" and view["time"]<r["until"]]
    if not readings:
        return False
    reading = max(readings,key=lambda r:r["sampled"])
    if work.adequate(sub["key"],reading["fields"]):
        return True
    if level < 2:
        return False
    meters = [r for r in view["fixed"] if r["field"]==sid and r["source"]=="meter/"+sid
              and reading["sampled"]<=r["sampled"] and view["time"]<r["until"]]
    return bool(meters and max(meters,key=lambda r:r["sampled"])["ok"])


class Selector:
    def __init__(self, space, track, theta, settings, no_probe=False):
        check(space,track,theta)
        self.track=track
        self.theta=theta
        self.original=theta==initial(space,track)
        self.settings=settings
        self.gate=WithoutInitial(180) if no_probe else Gate(180)
        self.no_probe=no_probe
        self.edits=[]
        self.reference=None

    def decide(self, pub, view):
        risk.validate(pub,view)
        self.edits=[]
        if self.track=="MAIN":
            self.reference=exact_baseline(pub,view)
            if self.original:
                return self.reference
        # Each public interpreter is dedicated to a single descriptor.
        risk.choose_first=planning.choose_first if self.original else self.choose_first
        response=risk.decide("V3",pub,view,self.settings,self.gate)
        if not self.original:
            response["rationale"]["improvement_edits"]=self.edits
        if (self.track=="MAIN" and not response["request"]
                and response["rationale"]["reason"] in ("UNSUPPORTED_PUBLIC_EVIDENCE","NO_COMPLETE_ADMITTED_BRANCH")):
            return self.reference
        return response

    def choose_first(self, pub, view, weights, price, settings, gate):
        request, refused, candidates, first = planning.choose_first(pub,view,weights,price,settings,gate)
        if not candidates:
            return request,refused,candidates,first
        subjects=work.entries(pub)
        now=view["time"]
        duration=exposure(view)
        prior=effects(pub,view,project=True)
        writes={}
        probes={}
        for option in candidates:
            if option["first"] is None:
                continue
            sid,phase=option["first"]
            sub=subjects[sid]
            allowed,why=gate.admit(pub,view,sub,phase)
            if not allowed:
                raise ValueError("Frozen candidate not admitted: "+why)
            if phase=="I":
                probes[sid]=allowed,option
            else:
                slots=baseline.legal_times(pub,view,sub,gate)
                if not slots or slots[0]!=now:
                    raise ValueError("Current write slot vanished")
                need=fsum(m for world,m in weights if forecast.locally_needed(world,sub["key"],allowed["planned_end"],prior))
                writes[sid]=dict(request=allowed,option=option,slots=slots,need=need,
                                 veto=duration>0 and public_normal(sub,view,self.theta["subjects"][sub["key"]]["prewrite_evidence"]))
        if self.track=="HOT":
            winner=self.hot_choice(first,candidates,subjects,writes,probes)
        else:
            winner=self.main_choice(pub,view,candidates,subjects,writes,probes,duration)
        chosen=winner["first"]
        if chosen==first:
            return request,refused,candidates,first
        if chosen is None:
            return None,refused,candidates,None
        sid,phase=chosen
        return (writes[sid]["request"] if phase=="A" else probes[sid][0]),refused,candidates,chosen

    def vetoes(self, candidates, writes):
        return [c for c in candidates if c["first"] is None or c["first"][1]!="A" or not writes[c["first"][0]]["veto"]]

    def direct_after_probe(self, option, subjects, writes, probes):
        chosen=option["first"]
        if chosen is None or chosen[1]!="I":
            return None
        sid=chosen[0]
        change=writes.get(sid)
        if not change or change["veto"]:
            return None
        params=self.theta["subjects"][subjects[sid]["key"]]
        probe=probes[sid][0]
        # After the lawful read arrives the same worker cannot have executed a write at this tick.
        slack=change["slots"][-1]-change["request"]["at"]
        if probe["planned_end"]>change["request"]["at"] and slack<=params["no_probe_slack_s"] and change["need"]>=params["no_probe_need"]:
            self.edits.append(["direct_before_probe_delay",sid,change["need"],slack])
            return change["option"]
        return None

    def prevention(self, sid, subjects, writes):
        info=writes[sid]
        theta=self.theta["global"]
        slack=info["slots"][-1]-info["request"]["at"]
        if subjects[sid]["key"]=="NR" and slack<=theta["nr_window_s"] and info["need"]>=theta["nr_need"]:
            return theta["nr_credit_s"]
        return 0

    def hot_choice(self, first, candidates, subjects, writes, probes):
        chosen=next(c for c in candidates if c["first"]==first)
        allowed=self.vetoes(candidates,writes)
        if not allowed:
            return {"first":None}
        if chosen not in allowed:
            self.edits.append(["avoid_unnecessary_write",first[0]])
            chosen=min(allowed,key=v3_rank)
        direct=self.direct_after_probe(chosen,subjects,writes,probes)
        if direct is not None:
            chosen=direct
        best=v3_rank(chosen)
        for sid,info in writes.items():
            credit=self.prevention(sid,subjects,writes)
            if credit and not info["veto"] and v3_rank(info["option"],-credit)<best:
                chosen=info["option"]
                best=v3_rank(chosen,-credit)
                self.edits.append(["prioritize_preventive_window",sid,credit])
        return chosen

    def main_choice(self, pub, view, candidates, subjects, writes, probes, duration):
        theta=self.theta["global"]
        hint=self.reference["request"]
        match=[hint["subject"],hint["phase"]] if hint and hint["phase"] in ("A","I") else None
        eligible=self.vetoes(candidates,writes)
        if not eligible:
            return {"first":None}
        self.edits.extend(["avoid_unnecessary_write",sid] for sid,row in writes.items() if row["veto"])
        def rank(choice):
            first=choice["first"]
            cost=theta["forecast_weight"]*choice["vector"][3]
            if first==match:
                cost-=theta["baseline_credit_s"]
            if first:
                sid,phase=first
                p=self.theta["subjects"][subjects[sid]["key"]]
                if phase=="I":
                    probs=[r["probability"] for r in choice["table"].values()]
                    spread=1-fsum(x*x for x in probs)
                    cost+=p["probe_margin_s"]-p["probe_target_s"]*spread
                else:
                    info=writes[sid]
                    earliest_next=info["request"]["planned_end"]+self.gate.recovery
                    lost=sum(oid!=sid and not other["veto"] and other["slots"][-1]<earliest_next
                             for oid,other in writes.items())
                    slack=info["slots"][-1]-view["time"]
                    cost+=p["exclusive_bid_s"]*lost
                    cost+=p["bypass_risk_weight"]*(1-info["need"])*duration*(1-self.settings["maintenance_capacity"])
                    cost-=p["deadline_credit_s"]*max(0,1-slack/360)
                    cost-=self.prevention(sid,subjects,writes)
            return round(cost,9),v3_rank(choice)
        chosen=min(eligible,key=rank)
        return self.direct_after_probe(chosen,subjects,writes,probes) or chosen
