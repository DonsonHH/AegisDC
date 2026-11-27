"""Frozen finite-history POMCP adaptation. Only public-model observations reach tree nodes."""
from bisect import bisect_left, bisect_right
import hashlib
import json
import math
import time
from numpy.random import Generator, PCG64

from aegis_action_cost import forecast
from aegis_action_cost.permit import exposure
from aegis_risk_dispatch import belief, knowledge, policy
from baselines import guard, menu_with_refusals

SIMULATIONS = 128
DEPTH = 4


def seed(pub, view):
    raw = json.dumps({"public": pub, "view": view}, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf8")
    return int.from_bytes(hashlib.sha256(b"AegisDC/T11/POMCP/v1|" + raw).digest()[:16], "big")


def report_fields(kind, label):
    """Represent precisely the frozen signature, without exposing within-signature world differences."""
    if label == "UNKNOWN":
        return None
    if kind == "C":
        return {"q": .1 if label == "OK" else .05}
    if kind == "N":
        return {"g": .5 if label == "CONFIG" else 1., "e": 1. if label == "OK" else .25}
    if kind == "LC":
        version = "SHARED_CONTACT" if label == "CONTACT" else "SHARED_UPSTREAM"
        return {"versions": [version, version]}
    if kind == "LB":
        return {"contact": label == "CLOSED", "upstream": label == "CLOSED", "released": label == "RELEASED"}
    if kind == "LG":
        return {"ready": label == "READY", "permitted": label == "READY"}
    if kind == "NR":
        return {"group_kW": 100 if label == "OVER" else 60,
                "transfer_kW": {"TOO_SMALL": 45, "OVER": 70, "OK": 120}[label]}
    if kind == "NC":
        return {"commissioned": label == "COMMISSIONED", "handover": label != "IN_WORKS",
                "under_construction": label == "IN_WORKS"}
    if kind == "NP":
        parts = label.split("/")
        running = "RUN" in parts
        return {"automatic_restart": parts[0] == "AUTO", "running": running, "latched": not running,
                "controller_on": running or "RETURN" in parts, "power_returned": "RETURN" in parts}
    raise ValueError("Unknown public observation type")


class Trajectory:
    """A sampled model trajectory. issue/advance/finish never query the native plant."""
    def __init__(self, pub, view, world, settings, gate, stream):
        self.pub, self.world, self.settings, self.gate, self.stream = pub, world, settings, gate, stream
        # Existing records are immutable. Only the lists receiving model events are copied.
        self.view = {k: (list(v) if isinstance(v, list) else v) for k, v in view.items()}
        self.subjects = gate.entries(pub)
        self.effects = belief.effects(pub, view)
        self.epochs = {sid: 0 for sid in self.subjects}
        for w in view["writes"]:
            self.epochs[w["subject"]] = max(self.epochs[w["subject"]], w["epoch"])
        self.pending = {}
        self.duration = exposure(view)
        self.last_issue = None
        self.person = sum(r["planned_end"]-r["at"] for r in view["issued"])
        self.fees = len(view["issued"])
        writes = {r["task"] for r in view["writes"]}
        paid = {r["task"] for r in view["paid"]}
        for r in view["issued"]:
            ack = gate.ack(view, r["task"])
            if ack is not None and ack["status"] != "completed":
                continue
            end = ack["observed_at_s"] if ack is not None else r["planned_end"]
            arrival = end + pub["latency"]
            # A known missing past receipt stays missing. No retroactive publication.
            if arrival <= view["time"]:
                continue
            result_missing = r["task"] not in (writes if r["phase"] == "A" else paid)
            if result_missing or ack is None:
                self.pending[r["task"]] = dict(req=r, end=end, arrival=arrival, sampled=False,
                                               need_ack=ack is None, need_result=result_missing)

    def issue(self, request):
        t = self.view["time"]
        if self.last_issue == t:
            raise ValueError("Multiple modeled actions at one decision time")
        self.last_issue = t
        if request is None:
            return
        if request["at"] != t or any(r["task"] == request["task"] for r in self.view["issued"]):
            raise ValueError("Invalid predicted issue identity")
        self.view["issued"].append(request)
        self.person += request["planned_end"]-request["at"]
        self.fees += 1
        end = request["planned_end"]
        self.pending[request["task"]] = dict(req=request, end=end, arrival=end+self.pub["latency"],
                                             sampled=False, need_ack=True, need_result=True)

    def _sample(self, event):
        req, end = event["req"], event["end"]
        sid, task, phase = req["subject"], req["task"], req["phase"]
        kind = self.subjects[sid]["key"]
        if phase == "A":
            success = knowledge.write_success(self.world, kind, end)
            if success and event["need_result"]:
                self.effects[kind] = end
                self.epochs[sid] += 1
            event["success"] = success
        elif event["need_result"]:
            event["signature"] = knowledge.sample(self.world, kind, end, self.effects)
        event["epoch"] = self.epochs[sid]
        event["sampled"] = True

    def _deliver(self, event):
        req, end, arrival = event["req"], event["end"], event["arrival"]
        sid, task, phase = req["subject"], req["task"], req["phase"]
        sub = self.subjects[sid]
        visible=[]
        if event["need_ack"]:
            ack=dict(task_id=task,status="completed",observed_at_s=end,arrived_at_s=arrival,
                     source_id="workforce-execution-report",origin_id="workforce:"+task,
                     location_id=sub["location"],reason=None,coverage="complete",basis="public forecast")
            self.view["work"].append(ack)
            visible.append(("work",task,end,arrival,sub["location"],"completed"))
        if not event["need_result"]:
            return visible
        if phase == "A":
            success=event["success"]
            executed=task+"@"+format(end,"g") if success else None
            outcome="APPLIED" if success else "NO_EFFECT"
            self.view["writes"].append(dict(task=task,subject=sid,operation=sub["operation"],at=end,
                arrived=arrival,execution=executed,epoch=event["epoch"],source="work-execution",
                origin="write/"+task,outcome=outcome))
            visible.append(("write",task,end,arrival,outcome,executed,event["epoch"]))
        else:
            label=event["signature"]
            if phase == "I" and self.stream.random() < self.settings["unknown_report_probability"]:
                label="UNKNOWN"
            fields=report_fields(sub["key"],label)
            until=end+self.pub["paid_ttl"]
            origin=f"{task}@{end:g}"
            self.view["paid"].append(dict(task=task,subject=sid,phase=phase,source="onsite/"+sid,origin=origin,
                worker=req["worker"],tool=req["tool"],issued=req["at"],sampled=end,arrived=arrival,until=until,
                parent=req["parent"],execution=req["execution"],parent_epoch=req["parent_epoch"],
                physical_epoch=event["epoch"],fields=fields))
            visible.append(("paid",task,"onsite/"+sid,origin,end,arrival,until,req["parent"],req["execution"],
                            req["parent_epoch"],event["epoch"],label))
        return visible

    def advance(self, tick):
        if tick < self.view["time"]:
            raise ValueError("A public history cannot run backwards")
        for ev in sorted(self.pending.values(), key=lambda e:(e["end"], e["req"]["phase"]!="A", e["req"]["task"])):
            if not ev["sampled"] and ev["end"] <= tick:
                self._sample(ev)
        delivered=[]
        ready=sorted((e for e in self.pending.values() if e["arrival"]<=tick),
                     key=lambda e:(e["arrival"],e["req"]["task"]))
        for ev in ready:
            delivered.extend(self._deliver(ev))
            del self.pending[ev["req"]["task"]]
        self.view["time"]=tick
        # No future external meter, alarm, release or free record is synthesized.
        return tick,tuple(delivered)

    def finish(self):
        """Resolve committed work and legal R/X to H, then score service and expenditures once."""
        clock=self.pub["clock"]; t=self.view["time"]
        while t<=clock[-1]:
            request=None
            if self.last_issue!=t:
                due,renew=policy.priorities(self.pub,self.view,self.gate)
                request,_=policy.first_legal(due+renew,self.pub,self.view,self.gate)
            if request is not None:
                self.issue(request)
            if t==clock[-1]: break
            if self.last_issue==t:
                index=bisect_right(clock,t)
            else:
                # With no new free observations a previously refused mandatory job can
                # become eligible only at an arrival, shift start, or read/renew opening.
                boundaries=[e["arrival"] for e in self.pending.values()]
                boundaries.append(self.pub["renew_at"])
                for sub in self.subjects.values():
                    boundaries.extend((sub["read_window"][0],sub["renew_window"][0],
                                       self.pub["workforce"]["shifts"][sub["worker"]][0]))
                future=[value for value in boundaries if value>t]
                if not future:break
                index=bisect_left(clock,min(future))
            if index>=len(clock):break
            t=clock[index]
            self.advance(t)
        loss=forecast.loss(self.world,tuple(sorted(self.effects.items())),self.duration,self.settings["maintenance_capacity"])
        return loss,self.person,self.fees



class Edge:
    def __init__(self, request):
        self.request=request
        self.visits=0
        self.normalized_cost=0.
        self.children={}

    @property
    def mean(self):
        return self.normalized_cost/self.visits


class Node:
    """Only a public action/observation history determines the menu and the node key."""
    def __init__(self, menu):
        order=sorted(menu,key=lambda a:(a is not None,a or ("","")))
        self.edges={a:Edge(menu[a]) for a in order}
        self.visits=0

    def select(self):
        for action,edge in self.edges.items():
            if not edge.visits:
                return action,edge
        log_visits=math.log(self.visits)
        return max(self.edges.items(),key=lambda p:-p[1].mean+math.sqrt(2*log_visits/p[1].visits))


def node_for(pub, view, gate):
    reason,required,_=guard(pub,view,gate,has_support=True)
    if required is not None:
        return Node({(required["subject"],required["phase"]):required})
    if reason!="VALUE":
        return Node({None:None})
    return Node(menu_with_refusals(pub,view,gate)[0])


def search(pub, view, weights, price, settings, gate):
    begin=time.perf_counter_ns()
    menu,denied=menu_with_refusals(pub,view,gate)
    metrics=dict(tree_ns=0,leaf_ns=0,tree_steps=0,leaf_evaluations=0,simulations=0,nodes=0,max_depth=0)
    if not weights or len(menu)<=1:
        return None,denied,[],None,metrics
    root=Node(menu);metrics["nodes"]=1
    worlds=[];cdf=[];mass=0.
    for world,p in sorted(weights,key=lambda item:tuple(item[0])):
        if p>0:
            mass+=p;worlds.append(world);cdf.append(mass)
    if not cdf:
        raise ValueError("Elective tree root without a supported world")
    rng=Generator(PCG64(seed(pub,view)))
    clock=pub["clock"];root_index=bisect_left(clock,view["time"])
    kappa=settings["fee_in_person_seconds"]
    scale=clock[-1]+price*(pub["resources"][0]+kappa*pub["resources"][2])
    if scale<=0:raise ValueError("Nonpositive public cost normalization")
    for simulation in range(SIMULATIONS):
        # One root draw per simulation. Only delivery of an I can consume an additional draw.
        index=bisect_right(cdf,rng.random()*mass)
        world=worlds[min(index,len(worlds)-1)]
        path=Trajectory(pub,view,world,settings,gate,rng)
        choices=[];node=root;clock_index=root_index
        for step in range(DEPTH):
            if clock_index>=len(clock) or clock[clock_index]>=clock[-1]:
                break
            action,edge=node.select()
            choices.append((node,edge))
            path.issue(edge.request)
            clock_index+=1
            metrics["tree_steps"]+=1
            if clock_index>=len(clock):break
            observed=path.advance(clock[clock_index])
            if step+1<DEPTH and clock[clock_index]<clock[-1]:
                # Parent edge records the action, and the key contains only delivered public events.
                next_node=edge.children.get(observed)
                if next_node is None:
                    next_node=node_for(pub,path.view,gate)
                    edge.children[observed]=next_node
                    metrics["nodes"]+=1
                node=next_node
        metrics["max_depth"]=max(metrics["max_depth"],len(choices))
        leaf_start=time.perf_counter_ns()
        loss,labour,fees=path.finish()
        cost=(loss+price*(labour+kappa*fees))/scale
        metrics["leaf_ns"]+=time.perf_counter_ns()-leaf_start
        metrics["leaf_evaluations"]+=1
        for history,edge in choices:
            history.visits+=1
            edge.visits+=1
            edge.normalized_cost+=cost
        metrics["simulations"]+=1
    if root.visits!=SIMULATIONS or any(not e.visits for e in root.edges.values()):
        raise ValueError("Incomplete registered elective root")
    winner=min(root.edges,key=lambda a:(-root.edges[a].visits,root.edges[a].mean,a is not None,a or ("","")))
    branches=[dict(first=list(a) if a is not None else None,visits=e.visits,mean_normalized_cost=e.mean)
              for a,e in root.edges.items()]
    metrics["tree_ns"]=time.perf_counter_ns()-begin-metrics["leaf_ns"]
    return root.edges[winner].request,denied,branches,list(winner) if winner is not None else None,metrics
