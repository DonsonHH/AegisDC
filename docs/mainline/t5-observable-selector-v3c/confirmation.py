"""Fit and publish before generating; run each new policy on its own native plant."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import gzip
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import resource
from statistics import mean
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

from analysis import FAMILIES,ROLES,fit,interval,need,winner
from control_v3c import BATCHES,OUT,ROLES as ARMS,targets,await_publication
from development import ACT,PK,previous
from landscape import digest,job,packed,read,sha,write

OLD=previous.old
from public_ipc import Process
from bridge import PublicProcess
from context_v2 import references
from native_v3 import native_run
from score_positions import oracle_plan,witness
from score_saved import score
from run_panel import retain
from analyse_landscape import minimum
import public_ipc
import public_work


def source(name):
    import numpy as np
    reg=read(OUT/"registrations"/(name+".json"));rel=read(OUT/"release.json")
    need(job()==reg["job"] and reg["source"]==rel["commit"] and int(os.environ["SLURM_CPUS_PER_TASK"])==reg["cpus"],"original reservation")
    for f,h in rel["files"].items():need(sha(PK/f)==h,"confirmation source "+f)
    for f,h in read(PK/"predecessors.json")["files"].items():need(sha(PK.parents[2]/f)==h,"unchanged predecessor "+f)
    os.environ["V3A_PANEL"]=previous.PIN["panel-and-strategies.json"];os.environ["V3A_SOURCE"]=previous.PIN["source-freeze.json"]
    core=OLD.check_source();bundles=OLD.verify_workers()
    need(np.__version__=="2.2.6" and core and bundles["V_COST"]==references()["V_COST"][0],"native and policy identity")
    return reg,core


def fitting():
    result=read(PK/"development.json");m,rows,_=previous.data()
    need(result["gate0"]==result["gate1"]=="PASS" and sha(PK/"development.json")==sha(ACT/"development.json"),"fitting gate")
    keys=m["order"];cells={k:"|".join(result["checks"][k]["cell"]) for k in keys}
    losses={k:{l:rows[k]["arms"][l]["L"] for l in ROLES} for k in keys}
    fitted=fit(keys,cells,losses)
    # Historical number diagnostics, not used by the selector or in any gate.
    group_order=list(rows[keys[0]]["arms"])
    orders={"frozen58":ROLES,"Q48":ROLES[:48],"alphabetical58":tuple(sorted(ROLES)),
            "references_first":ROLES[48:]+ROLES[:48],
            "stored_arm_order":tuple(l for l in group_order if l in ROLES)}
    checks={}
    for tag,labels in orders.items():
        values=[]
        for k in keys:
            f=rows[k]["family"];other=[j for j in keys if rows[j]["half"]!=rows[k]["half"] and rows[j]["family"]==f]
            chosen=winner(other,losses,labels);values.append(losses[k][chosen]-rows[k]["minimum"]["certified_min"])
        checks[tag]=mean(values)
    obj=dict(schema="T5-v3c-locked-selector-and-W",source=read(OUT/"release.json")["commit"],protocol_sha256=sha(PK/"confirmation-protocol.md"),
             development_sha256=sha(PK/"development.json"),old_panel=previous.PIN["panel-and-strategies.json"],fit=fitted,
             public_policy_sha256=sha(PK/"selector.py"),dispatch_sha256=sha(PK/"selector_worker.py"),roster=list(ROLES),
             historic_reference_diagnostics=checks,job=job(),new_conditions_generated=0,new_facility_starts=0)
    write(OUT/"locked-selector.json",obj)
    return obj


def panel_lock(lock):
    from inputs_v3 import condition,templates
    token=await_publication("lock",OUT/"locked-selector.json")
    seed=hashlib.sha256(("AegisDC/T5-v3c/new-panel/v1|"+token["commit"]).encode("ascii")).digest()
    oldm=OLD.manifest();previous_sets=OLD.old_identities(OLD.config())
    previous_sets["v3a"]=({v["sha256"] for v in oldm["conditions"].values()},{v["operative_sha256"] for v in oldm["conditions"].values()})
    full={v for a,_ in previous_sets.values() for v in a};op={v for _,b in previous_sets.values() for v in b}
    panel={};order=[];reject=[];templates_=templates();folder=OUT/"inputs";folder.mkdir()
    for n in range(6):
        for i,f in enumerate(FAMILIES):
            k=f"new-{i+1}-{n+1:02}"
            for retry in range(128):
                salt=f+"|"+("block0" if not retry else f"slot{n}|retry{retry}")
                v=condition(int.from_bytes(hashlib.sha256(seed+b"|"+salt.encode()).digest(),"big"),i,n,templates_)
                raw=hashlib.sha256(packed(v)+b"\n").hexdigest();oper=OLD.operative(v)
                if raw not in full and oper not in op:break
                reject.append(dict(key=k,retry=retry,full=raw,operative=oper))
            else:raise ValueError("disjoint panel exhausted at "+k)
            write(folder/(k+".json"),v);need(sha(folder/(k+".json"))==raw,"registered input bytes")
            full.add(raw);op.add(oper);order.append(k);panel[k]=dict(family=f,slot=n,retry=retry,sha256=raw,operative_sha256=oper)
    complete={r["sha256"] for r in panel.values()};operative={r["operative_sha256"] for r in panel.values()}
    overlap={k:dict(full=len(complete&a),operative=len(operative&b)) for k,(a,b) in previous_sets.items()}
    need(len(complete)==len(operative)==len(order)==36 and all(not any(pair.values()) for pair in overlap.values()),"disjoint identities")
    obj=dict(schema="T5-v3c-new-panel",order=order,cases=panel,old_counts=[144,84,36,36],overlap=overlap,internal_duplicates=0,
             rejected=reject,seed_sha256=hashlib.sha256(seed).hexdigest(),lock_publication=token,locked_W=lock["fit"]["winner"],job=job(),native_entries=0)
    write(OUT/"panel.json",obj);return obj


def worker(label,dest,m):
    if label in ("P","PERIODIC","ALARM"):
        refs=references()
        with patch.object(public_ipc,"references",lambda:{**refs,label:refs["V_COST"]}):
            return Process(label,dest)
    desc,manual=OLD.binding(label,m)
    return Process(label,dest,desc,manual)


class Router(PublicProcess):
    def __init__(self,folder,lock,m):
        self.shelf={};self.triggers=[];self.events=[];self.selected=None;self.at=None;self.cell=None
        self.folder=folder;self.lock={k:lock["fit"][k] for k in ("winner","cells")};self.m=m
        public_root=OUT/"selector-public"
        need({p.name for p in public_root.iterdir()}=={"selector.py","selector_worker.py"} and
             all(sha(public_root/n)==sha(PK/n) for n in ("selector.py","selector_worker.py")),"public selector bundle")
        self.stderr=(folder/"router.stderr").open("x")
        self.child=subprocess.Popen([sys.executable,"-I","-S","-B",str(public_root/"selector_worker.py")],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,cwd=public_root,env={"LANG":"C.UTF-8","OPENBLAS_NUM_THREADS":"1"})
    def start(self,pub):
        need(self.message({"subjects":[{"id":s["id"],"key":s["key"]} for s in pub["subjects"]],"lock":self.lock})=={"ready":True},"selector startup")
        self.pub=digest(pub);self.pids={}
    def request(self,label,pub,view):
        if label not in self.shelf:
            w=worker(label,self.folder/(label+".stderr"),self.m)
            self.shelf[label]=w;self.pids[label]=w.child.pid;w.start(pub)
        return self.shelf[label].choose(pub,view,label,{})
    def choose(self,pub,view,label,plan):
        need(label=="S" and not plan and digest(pub)==self.pub,"router receives public input only")
        if self.selected is not None:
            reply=self.request(self.selected,pub,view)
        else:
            queries={};first=None
            for role in ROLES:
                q=self.request(role,pub,view);queries[role]=q
                if q["request"] is not None:first=role;break
            answer=self.message({"view":view,"any_nonempty":first is not None})
            self.triggers.append(dict(t=view["time"],public=digest(view),first_nonempty=first,
                                      probes=[(r,digest(v)) for r,v in queries.items()],answer=answer))
            self.selected=answer["selected"]
            if first is not None:
                self.at=view["time"];self.cell=answer["cell"];need(self.selected in ROLES,"locked vector")
                reply=queries[self.selected] if self.selected in queries else self.request(self.selected,pub,view)
            else:
                need(self.selected is None and len(queries)==58,"all policies deferred");reply=queries[ROLES[0]]
        self.events.append([view["time"],digest(view),digest(reply)])
        return reply
    def close(self,failed=False):
        try:
            for w in self.shelf.values():w.close(failed=failed)
        finally:super().close(failed=failed)


def cpu_used():
    return sum(q.ru_utime+q.ru_stime for q in (resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)))


def unit(key,arm,core):
    folder=OUT/"positions"/key/arm;folder.mkdir(parents=True,exist_ok=False)
    wall=time.monotonic();cpu=cpu_used()
    try:
        panel=read(OUT/"panel.json");lock=read(OUT/"locked-selector.json");published=read(OUT/"published-panel.json")
        need(sha(OUT/"panel.json")==published["sha256"] and sha(OUT/"locked-selector.json")==panel["lock_publication"]["sha256"],"execution publications")
        pin=panel["cases"][key];path=OUT/"inputs"/(key+".json");case=read(path)
        need(sha(path)==pin["sha256"] and OLD.operative(case)==pin["operative_sha256"],"complete and operative input")
        actual=lock["fit"]["winner"] if arm=="W" else arm
        if arm=="MIRROR":
            parent=read(OUT/"positions"/key/"S"/"row.json");need(parent["status"]=="SCORED" and parent["selection"]["selected"] in ROLES,"actual selected identity")
            actual=parent["selection"]["selected"]
        cert=oracle_plan(case) if arm=="ORACLE" else None
        m=OLD.manifest();w=None if cert is not None else Router(folder,lock,m) if arm=="S" else worker(actual,folder/"worker.stderr",m)
        pub=case["native"]["dispatch_program"]["public"];done=False
        try:
            if w:w.start(pub)
            entry=dict(job=job(),key=key,arm=arm,actual=actual,source=read(OUT/"release.json")["commit"],lock=sha(OUT/"locked-selector.json"),
                       panel=published["sha256"],input=pin["sha256"],operative=pin["operative_sha256"],tree=core,pid=os.getpid(),
                       public_sha256=digest(pub),worker_pid=w.child.pid if w else None,worker_bundle=(sha(PK/"selector_worker.py") if arm=="S" else w.identity) if w else None)
            write(folder/"entry.json",entry)
            run,end=native_run(case,actual,cert["plan"] if cert else {},(),decider=w.choose if w else public_work.choose)
            done=True
        finally:
            if w:w.close(failed=not done)
        raw=folder/"original.jsonl.gz";retain(raw,run,end);val=score(case,run,end,actual)
        need(val["clocks"]==61 and val["runtime"]==core and run["v3_received_maintenance"]==case["maintenance"] and not run["t3_unpurchased_evaluator_only"],"native contract")
        proposed=[[p["at"],p["view"],p["proposal"]] for p in run["v3_proposals"]]
        if w:need(w.child.pid!=os.getpid() and w.events==proposed,"original independently hosted decisions")
        issued=[d["decision"]["request"] for d in run["policy_public_decisions"] if d["decision"]["request"] is not None]
        need(val["requests"]==[[p["at"],p["task"]] for p in issued],"complete physical issuance ledger")
        sel=None
        if arm=="S":
            sel=dict(selected=w.selected,at=w.at,cell=w.cell,probe_log=w.triggers,pids=w.pids)
            write(folder/"selector.json",sel)
        result=dict(status="SCORED",entry=entry,raw=sha(raw),entry_sha256=sha(folder/"entry.json"),issued=issued,
                    proposal_index=digest(proposed),selection=({k:sel[k] for k in ("selected","at","cell")} if sel else None),
                    selector_log=sha(folder/"selector.json") if sel else None,oracle=witness(cert,val,run["policy_public_decisions"]) if cert else None,
                    **{k:val[k] for k in ("L","U","integral_balances","person","tool","fee","curve","requests","writes","paid","clocks")})
    except Exception as e:
        (folder/"failure.log").write_text(traceback.format_exc(),encoding="utf8")
        result=dict(status="FAILED",error=f"{type(e).__name__}: {e}")
    result.update(arm=arm,key=key,job=job(),entered=(folder/"entry.json").exists(),cpu_s=cpu_used()-cpu,wall_s=time.monotonic()-wall)
    write(folder/"row.json",result);print(key,arm,result["status"],flush=True)
    return result["status"]


def evaluate(core):
    panel=read(OUT/"panel.json");lock=read(OUT/"locked-selector.json");keys=panel["order"];cases=[];errors=[];mirrors=[]
    oldm=OLD.manifest();ex=OLD.old_identities(OLD.config());ex["v3a"]=({q["sha256"] for q in oldm["conditions"].values()},{q["operative_sha256"] for q in oldm["conditions"].values()})
    full=set();ops=set()
    for key in keys:
        info=panel["cases"][key];inp=OUT/"inputs"/(key+".json");case=read(inp);top={}
        need(sha(inp)==info["sha256"] and info["family"]==case["evaluation"]["family"] and OLD.operative(case)==info["operative_sha256"],"readback original condition")
        full.add(sha(inp));ops.add(OLD.operative(case))
        for role in [*ARMS,*(["MIRROR"] if key in keys[:3] else [])]:
            folder=OUT/"positions"/key/role;path=folder/"row.json"
            try:
                q=read(path);need(q["status"]=="SCORED",q.get("error","not scored"));e=read(folder/"entry.json");raw=folder/"original.jsonl.gz"
                need(e==q["entry"] and e["key"]==key and e["arm"]==role and e["job"]==q["job"] and e["input"]==sha(inp) and e["operative"]==info["operative_sha256"]
                     and e["source"]==read(OUT/"release.json")["commit"] and e["lock"]==sha(OUT/"locked-selector.json") and e["panel"]==sha(OUT/"panel.json")
                     and e["tree"]==core and e["public_sha256"]==digest(case["native"]["dispatch_program"]["public"]) and
                     sha(raw)==q["raw"] and sha(folder/"entry.json")==q["entry_sha256"],"sealed position binding")
                with gzip.open(raw,"rt") as fd:meta=json.loads(next(fd))["metadata"]
                m=meta["summary"];ix=(m["service_deficit_time_s"],m["demand_service_unit_s"]-m["delivered_service_unit_s"])
                need(max(abs(a-b) for a,b in zip(ix,[q["L"],q["U"]]))<1e-7 and meta["inputs"]["dispatch_program"]==case["native"]["dispatch_program"]
                     and [d["decision"]["request"] for d in meta["policy_public_decisions"] if d["decision"]["request"] is not None]==q["issued"]
                     and q["proposal_index"]==digest([[p["at"],p["view"],p["proposal"]] for p in meta["v3_proposals"]]),"raw accounting, public and issued history")
                if role=="S":
                    sel=q["selection"];need(sha(folder/"selector.json")==q["selector_log"] and sel["selected"]==lock["fit"]["cells"].get("|".join(sel["cell"]),lock["fit"]["winner"]),"actual S cell")
                if role=="W":need(e["actual"]==lock["fit"]["winner"],"W identity")
                q["row_sha256"]=sha(path);top[role]=q
            except Exception as err:errors.append(dict(key=key,role=role,error=f"{type(err).__name__}: {err}",entered=(folder/"entry.json").exists()))
        lower=minimum(case,top)
        if "MIRROR" in top and "S" in top:
            a,b=top["S"],top["MIRROR"]
            mirrors.append(dict(key=key,selected=a["selection"]["selected"],standalone=b["entry"]["actual"],
                    L=[a["L"],b["L"]],issued=[digest(a["issued"]),digest(b["issued"])],
                    passed=a["L"]==b["L"] and a["issued"]==b["issued"] and a["selection"]["selected"]==b["entry"]["actual"],
                    original_sha256=[a["raw"],b["raw"]]))
        cols={}
        for role,q in top.items():
            cols[role]={k:q[k] for k in ("L","U","person","tool","fee","raw","entry_sha256","row_sha256","selector_log","selection","clocks","job","cpu_s","wall_s")}
            cols[role].update(issued_digest=digest(q["issued"]),issued_count=len(q["issued"]),entry=q["entry"])
        cases.append(dict(key=key,family=info["family"],lower=lower,arms=cols))
    overlaps={n:dict(full=len(full&a),operative=len(ops&b)) for n,(a,b) in ex.items()}
    need(len(full)==len(ops)==36 and overlaps==panel["overlap"] and not any(any(r.values()) for r in overlaps.values()),"post-run double overlap audit")
    contrasts={};all_means={};by_family={};by_cell={}
    for r in ("W","V_COST","M_HOT","P","PERIODIC","ALARM","B_COST"):
        ds=[dict(family=k["family"],delta=k["arms"]["S"]["L"]-k["arms"][r]["L"]) for k in cases if {"S",r}<=k["arms"].keys()]
        ci=interval(ds,"delta",2,"stage1") if len(ds)==36 else None
        contrasts[r]=dict(pairs=len(ds),planned=36,ci=ci)
    def summary(sub):
        res={}
        for r in ARMS:
            valid=[t for t in sub if r in t["arms"]];paired=[t for t in valid if t["lower"]["certified_min"] is not None]
            res[r]=dict(planned=len(sub),scored=len(valid),mean_L=mean(t["arms"][r]["L"] for t in valid) if len(valid)==len(sub) else None,
                bound_pairs=len(paired),gap=mean(t["arms"][r]["L"]-t["lower"]["certified_min"] for t in paired) if len(paired)==len(sub) else None)
        return res
    all_means=summary(cases)
    for f in FAMILIES:by_family[f]=summary([t for t in cases if t["family"]==f])
    for t in cases:
        if "S" in t["arms"]:
            sel=t["arms"]["S"]["selection"];cell="|".join(sel["cell"])
            by_cell.setdefault(cell,dict(n=0,selected=sel["selected"],fallback=cell not in lock["fit"]["cells"],keys=[]))
            by_cell[cell]["n"]+=1;by_cell[cell]["keys"].append(t["key"])
    ok=len(mirrors)==3 and all(m["passed"] for m in mirrors) and contrasts["W"]["pairs"]==36
    verdict=("PASS" if contrasts["W"]["ci"]["upper"]<0 else "FAIL") if ok else "UNRESOLVED"
    return dict(schema="T5-v3c-new-panel-readback",primary_verdict=verdict,source=read(OUT/"release.json")["commit"],pub_lock=read(OUT/"published-lock.json"),
                pub_panel=read(OUT/"published-panel.json"),positions_planned=327,scored=sum(len(x["arms"]) for x in cases),errors=errors,
                comparisons=contrasts,roles=all_means,families=by_family,cells=by_cell,conditions=cases,mirrors=mirrors,overlap=overlaps,internal_duplicates=0,
                H2_generated=0,H2_accessed=0,H2_derived=0,job=job())


def lane(args):
    jobs,core=args
    return [unit(k,r,core) for k,r in jobs]


def main(name):
    reg,core=source(name);folder=OUT/"jobs"/name;folder.mkdir(parents=True,exist_ok=False)
    write(folder/"entry.json",dict(job=job(),name=name))
    if name=="pilot":
        lock=fitting();print("READY FOR LOCK PUBLICATION",flush=True)
        panel=panel_lock(lock);print("READY FOR PANEL PUBLICATION",flush=True)
    else:panel=read(OUT/"panel.json")
    await_publication("panel",OUT/"panel.json")
    pilots,groups=targets(panel["order"]);cpus=reg["cpus"]
    with ProcessPoolExecutor(cpus,mp_context=mp.get_context("fork")) as pool:
        if name=="pilot":
            primary=pilots[:-3];mirrors=pilots[-3:]
            states=list(pool.map(lane,[(primary[i::3],core) for i in range(3)]))
            states+=list(pool.map(lane,[([x],core) for x in mirrors]))
        else:
            budget=read(OUT/"budget.json");ls=budget["plan"][name]["lanes"]
            need(budget["proceed"] and set(tuple(x) for l in ls for x in l)==set(groups[name]),"no position reallocation")
            states=list(pool.map(lane,[(l,core) for l in ls]))
    from collections import Counter
    write(folder/"terminal.json",dict(name=name,job=job(),states=dict(Counter(x for l in states for x in l))))
    if name==BATCHES[-1]:write(OUT/"confirmation-result.json",evaluate(core))


if __name__=="__main__":main(sys.argv[1])
