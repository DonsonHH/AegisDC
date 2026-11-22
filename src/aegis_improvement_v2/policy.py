"""Rank actually available public decision branches without changing native v3 semantics."""
from bisect import bisect_right
from math import fsum

import public_work as work
from aegis_action_cost import forecast, planning
from aegis_action_cost.permit import Gate, exposure
from aegis_cost_baseline import rule as bc
from aegis_improvement.policy import WithoutInitial, exact_baseline, public_normal, v3_rank
from aegis_risk_dispatch import policy as risk
from aegis_risk_dispatch.belief import effects

from .space import root, validate


class Policy:
    def __init__(self, space, settings, track, vector, no_probe=False):
        validate(space, track, vector)
        self.space = space
        self.settings = settings
        self.track = track
        self.vector = vector
        self.original = root(space, track) == vector
        self.gate = WithoutInitial(180) if no_probe else Gate(180)
        self.baseline = None

    def dispatch(self, pub, view):
        risk.validate(pub, view)
        if self.track == "MAIN":
            self.baseline = exact_baseline(pub, view)
            if self.original:
                return self.baseline
            if self.vector["lookahead"] == 0:
                return self.direct_menu(pub, view)
        risk.choose_first = planning.choose_first if self.original else self.adjusted
        out = risk.decide("V3", pub, view, self.settings, self.gate)
        if self.track == "MAIN" and out["rationale"]["reason"] in ("UNSUPPORTED_PUBLIC_EVIDENCE", "NO_COMPLETE_ADMITTED_BRANCH"):
            return self.baseline
        return out

    def direct_menu(self, pub, view):
        duties, renewals = risk.priorities(pub, view, self.gate)
        mandatory, rejects = risk.first_legal(duties+renewals, pub, view, self.gate)
        if mandatory:
            return self.response(pub, view, mandatory, rejects)
        requests = {None: None}
        scores = {None: 0}
        subjects = work.entries(pub)
        for sid in pub["routes"]:
            sub = subjects[sid]
            for phase in ("I", "A"):
                req, why = self.gate.admit(pub, view, sub, phase)
                if not req:
                    rejects.append([sid, phase, why])
                    continue
                if phase == "I" and any(q["task"] == sid+"::A" for q in view["issued"]):
                    continue
                token = (sid, phase)
                cost = 120-self.value(sub, "probe_credit") if phase == "I" else 80
                if phase == "A":
                    if self.veto(sub, view):
                        continue
                    slack = self.slack(pub, view, sub)
                    cost -= self.deadline(sub, slack)
                    cost += self.value(sub, "bypass_weight") * exposure(view) * 0.5
                requests[token] = req
                scores[token] = cost
        hint = self.baseline["request"]
        hint_id = (hint["subject"], hint["phase"]) if hint else None
        if hint_id in scores:
            scores[hint_id] -= self.space["no_forecast_reference_credit_s"]
        selected = min(scores, key=lambda k:(scores[k], k is not None, k or ()))
        return self.response(pub, view, requests[selected], rejects)

    @staticmethod
    def response(pub, view, req, refused):
        return dict(request=req, refusals=refused, certificates={s["id"]:work.certificate(s,view) for s in pub["subjects"]},
                    rationale={"version":"T5-v2", "mode":"PUBLIC_DEADLINE", "chosen":req["task"] if req else "WAIT"})

    def value(self, sub, parameter):
        return self.vector[sub["key"]+"."+parameter]

    def slack(self, pub, view, sub):
        starts = bc.legal_times(pub, view, sub, self.gate)
        if not starts or starts[0] != view["time"]:
            raise ValueError("Admitted write missing from public schedule")
        return starts[-1]-view["time"]

    def deadline(self, sub, slack):
        band = bisect_right(self.space["slack_band_upper_s"], slack)
        return self.value(sub, "deadline_"+str(band))

    def veto(self, sub, view):
        return exposure(view)>0 and public_normal(sub, view, self.value(sub,"veto"))

    def adjusted(self, pub, view, weights, price, settings, gate):
        original, rejects, choices, old_first = planning.choose_first(pub,view,weights,price,settings,gate)
        if not choices:
            return original,rejects,choices,old_first
        subs = work.entries(pub)
        requests = {}
        writes = {}
        by_action = {}
        prior = effects(pub,view,project=True)
        now = view["time"]
        for row in choices:
            first = row["first"]
            if first is None:
                continue
            sid,phase = first
            sub = subs[sid]
            req, why = gate.admit(pub,view,sub,phase)
            if not req:
                raise ValueError("Frozen candidate failed its public gate: "+why)
            requests[sid,phase] = req
            if phase == "A":
                need = fsum(m for world,m in weights if forecast.locally_needed(world,sub["key"],req["planned_end"],prior))
                writes[sid] = dict(need=need,slack=self.slack(pub,view,sub),veto=self.veto(sub,view))
                by_action[sid] = row
        allowed = [r for r in choices if r["first"] is None or r["first"][1] != "A" or not writes[r["first"][0]]["veto"]]
        if not allowed:
            return None,rejects,choices,None
        hint = self.baseline["request"] if self.track=="MAIN" else None
        baseline_choice = [hint["subject"],hint["phase"]] if hint else None

        def ordering(row):
            first = row["first"]
            cost = 0
            if self.track == "MAIN":
                weight = self.vector["lookahead"]
                cost = (weight-1)*row["vector"][3]
                if first==baseline_choice:
                    cost -= self.space["no_forecast_reference_credit_s"]
            if first is None:
                return v3_rank(row,cost)
            sid, phase = first
            sub = subs[sid]
            if phase=="I" and self.track=="MAIN":
                spread = 1-fsum(q["probability"]**2 for q in row["table"].values())
                cost -= self.value(sub,"probe_credit")*(0.5+spread)
            if phase=="A":
                actual = writes[sid]
                if self.track=="MAIN":
                    end = requests[sid,phase]["planned_end"]+180
                    displaced = sum(k!=sid and not x["veto"] and now+x["slack"]<end for k,x in writes.items())
                    cost += self.value(sub,"displacement")*displaced
                    cost += self.value(sub,"bypass_weight")*(1-actual["need"])*exposure(view)*0.5
                    cost -= self.deadline(sub,actual["slack"])
                if sub["key"]=="NR" and actual["need"]>=self.vector["nr_need"] and actual["slack"]<=self.vector["nr_slack"]:
                    cost -= self.vector["nr_credit"]
            return v3_rank(row,cost)

        winner = min(allowed,key=ordering)
        if winner["first"] is None:
            return None,rejects,choices,None
        sid, phase = winner["first"]
        if phase=="I" and sid in writes:
            available = writes[sid]
            sub = subs[sid]
            if not available["veto"] and available["need"]>=self.value(sub,"fast_need") and available["slack"]<=self.value(sub,"fast_slack"):
                winner = by_action[sid]
        return requests[tuple(winner["first"])],rejects,choices,winner["first"]
