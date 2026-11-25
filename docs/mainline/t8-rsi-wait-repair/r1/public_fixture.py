"""Hand-authored public frames for the six allowance cells. No original worker is called."""

from copy import deepcopy
from fit_program import CELLS, ZERO, canonical, public_decision, require


class Gate:
    def live(self, view, kind):
        return [r for r in view["records"] if r["kind"]==kind and r["copied_from"] is None and
                r["arrived"]<=view["time"]<r["until"]]

    def each_read(self, view, subject):
        return [r for r in view["paid"] if r["subject"]==subject and r["fields"]]

    def actionable(self, key, fields):
        return fields.get("needs_work") is True

    def admit(self, pub, view, sub, phase):
        if not self.live(view,"order") or view["time"]+60>=sub["write_window"][1]: return None,"CLOSED"
        return {"task":"site::A","subject":"site","planned_end":view["time"]+60},"ALLOW"


def checks():
    gate=Gate()
    pub={"subjects":[{"id":"site","key":"S","worker":"w","write_window":[0,1800]}],
         "workforce":{"shifts":{"w":[0,2400]}},"routes":["site"],"latency":15}
    parent={"request":None,"certificates":{"site":"OPEN"},"refusals":[],
            "rationale":{"reason":"VALUE","chosen":"WAIT","continuation_table":[
                {"first":None,"admitted_continuation_plans":1,"vector":[100,0,0,100]},
                {"first":["site","A"],"admitted_continuation_plans":1,"vector":[90,0,0,130]}]}}
    def record(kind): return {"subject":"site","kind":kind,"copied_from":None,"arrived":15,"until":900,"origin":kind+"/site"}
    def validate(p,v):
        require(set(v)=={"time","paid","fixed","records"},"unexpected stand-in frame key")
        require(all(z["arrived"]<=v["time"] for chan in ("records","paid","fixed") for z in v[chan]),"future frame")
    def call(levels,frame,par=parent):
        return public_decision(levels,pub,frame,lambda p,v:par,gate,validate)
    v={"time":60,"paid":[],"fixed":[],"records":[record("order")]}
    fixed={"field":"site","source":"meter/site","origin":"meter/S@0","sampled":0,"arrived":15,"until":720,"ok":False}
    witnessed=[]
    for pos,name in enumerate(CELLS):
        frame=deepcopy(v)
        frame["records"][0]["until"]=240 if name.endswith("NEAR") else 900
        if name.startswith("DIRECT"):frame["fixed"]=[fixed]
        if name.startswith("ALARM"):frame["records"].append(record("alarm"))
        descriptor=[0]*6;descriptor[pos]=1
        answer=call(descriptor,frame)
        require(answer["rationale"]["t8_cell"]==name and answer["request"]["task"]=="site::A" and
                answer["refusals"]==parent["refusals"] and answer["certificates"]==parent["certificates"],"reachable "+name)
        require(canonical(call(ZERO,frame))==canonical(parent),"zero parent parity")
        witnessed.append(name)
    direct=[0,0,0,1,0,0]
    for rows in [[dict(fixed,source="copy/site")],[dict(fixed,until=60)],[fixed,dict(fixed,ok=True)],
                 [fixed,dict(fixed,sampled=30,arrived=45,until=60,origin="meter/S@30")]]:
        require(call(direct,dict(v,fixed=rows))==parent,"copy, stale, conflict, or expired latest meter")
    paid={"subject":"site","phase":"I","source":"onsite/site","origin":"site::I@0","task":"site::I",
          "sampled":0,"arrived":15,"until":300,"fields":{"needs_work":True}}
    require(call(direct,dict(v,paid=[paid]))["request"] is not None and
            call(direct,dict(v,paid=[dict(paid,origin="copy")]))==parent,"original paid reading")
    alarm=[0,0,0,0,1,0]
    for altered in [dict(record("alarm"),copied_from="old"),dict(record("alarm"),arrived=60)]:
        require(call(alarm,dict(v,records=v["records"]+[altered]))==parent,"alarm copy/arrival guard")
    all_on=(3,)*6
    for reason in ("MANDATORY_OWN_WORK","UNSUPPORTED_PUBLIC_EVIDENCE","AWAIT_OWN_PAID_RESULT"):
        p=deepcopy(parent);p["rationale"]["reason"]=reason
        require(call(all_on,v,p)==p,"parent pass-through "+reason)
    p=dict(parent,request={"task":"site::R"});require(call(all_on,v,p)==p,"mandatory issued pass-through")
    require(call(all_on,dict(v,records=[dict(record("order"),until=60)]))==parent,"expiry prevents action")
    for vector in ([100,0,0,100],[90,0,0,221]):
        p=deepcopy(parent);p["rationale"]["continuation_table"][1]["vector"]=vector
        require(call(all_on,v,p)==p,"gain and cost limit")
    for bad in [dict(v,extra=1),dict(v,records=[dict(record("order"),arrived=61)])]:
        try:call(all_on,bad)
        except ValueError:pass
        else:raise ValueError("invalid public view accepted")
    return {"reachable_cells":witnessed,"zero_and_mandatory_passthrough":True,"arrival_copy_expiry_conflict":True,
            "paid_source_identity":True,"unchanged_gate_and_fees":True,"forbidden_key_and_future_frame":True,
            "scope":"Synthetic public adapter checks. No native worker or plant executed."}
