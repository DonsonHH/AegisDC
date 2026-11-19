"""Publish the one study from saved returns. This reader has no project-runtime imports."""
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path
from record_io import MANIFEST, MANIFEST_SHA, APPROVAL_SHA, ARMS, DIMS, RUN_SOURCE
from record_io import digest, evidence_summary, exact, read, save, sha
import json

KINDS=("constructor","plant","policy","request","scorer")
PANELS=("dev19","ext35")
BITS=("提前申请后退化","未知停止后失去关闭","继续补证时服务落后","无结论后仍付费","末项给出否定")


def lines(path):
    if not path.is_file():
        return [],False
    raw=path.read_bytes().splitlines()
    events=[]
    for i,line in enumerate(raw):
        try:
            events.append(json.loads(line))
        except ValueError:
            if i!=len(raw)-1:raise
            return events,True
    return events,False


def timeline(raw):
    result=evidence_summary(raw)
    result["closed"]=raw["closed"]
    result["closed_decision"]=raw["run"]["public_trace"][-1]["decision"] if raw["run"]["public_trace"] else None
    result["diagnostics"]=[dict(action=r["action"],value=r["value"],status=r["status"],observed_at=r["observed_at"],
                                available_at=r["available_at"],expires_at=r["expires_at"],record_id=r["record_id"])
                           for r in raw["final"]["observations"] if r["action"].startswith("READ_")]
    exits=[]
    for seg in raw["final"]["segments"]:
        if seg["work_stage"]!="EXITING":continue
        action=seg["work_action"]
        if exits and exits[-1][1]==seg["start"] and exits[-1][2]==action:
            exits[-1][1]=seg["end"]
        else:
            exits.append([seg["start"],seg["end"],action])
    result["safe_exits"]=exits
    return result


def call_log(path):
    events,torn=lines(path)
    started={e["sequence"]:e for e in events if e["event"]=="intent"}
    returns=[e["call"] for e in events if e["event"]=="return"]
    raised=[e["call"] for e in events if e["event"]=="raised"]
    finished=returns+raised
    counts=dict.fromkeys(KINDS,0)
    for k in set(finished) & started.keys():
        e=started[k];counts[e["kind"]]+=1
        if e["kind"]=="plant" and e["method"]=="request":
            counts["request"]+=1
    return dict(intents=len(started),returned=len(returns),raised=len(raised),known_counts=counts,
                pending=sorted(started.keys()-set(finished)),duplicate_or_orphan=len(set(finished))!=len(finished)
                or bool(set(finished)-started.keys()),torn=torn)


def pareto_witness(candidate, reference, masks):
    """Find why a paid passing item was removed from the recorded frontier."""
    strict={}; violations={}
    for k,b in reference.items():
        a=candidate[k];am,bm=set(a["violations"]),set(b["violations"])
        d=[Fraction(x)-Fraction(y) for x,y in zip(a["z"],b["z"])]
        worse=[DIMS[i] for i,n in enumerate(d) if n>0]+sorted(am-bm)
        if masks[k] and b["closed"] and not a["closed"]:worse.append("lost_closure")
        if worse:violations[k]=worse
        better=[DIMS[i] for i,n in enumerate(d) if n<0 and masks[k]]
        if am<bm:better.append("smaller_violation_set")
        if better:strict[k]=better
    return dict(strict_rows=strict,vetoes=violations,dominates=bool(strict) and not violations)


def comparisons(terminal, panels, checks):
    summary={}
    for group,refs in terminal.get("paired",{}).items():
        summary[group]={}
        for name,comparison in refs.items():
            item=dict(eligible=comparison["eligible"],promotion_flags=comparison["promotion_flags"],panels={})
            for panel,rows in panels.items():
                counts={s:[0,0,0] for s in DIMS}; changed={s:{"lower":[],"higher":[]} for s in DIMS}
                closure={"gained":[],"lost":[]}
                for r in rows:
                    key=r["key"]
                    b=comparison["rows"][key]
                    delta=b["difference"];r.setdefault("locked_differences",{}).setdefault(group,{})[name]=delta
                    locked=terminal["locks"][group]["lock"]
                    def resolve(label):
                        if label in ARMS:return r["baseline"][label]
                        return r["paid_candidates"][label]
                    against=terminal["locks"][name]["lock"] if name in terminal["locks"] else name
                    for expected,label in ((b["candidate"],locked),(b["reference"],against)):
                        a=resolve(label)
                        if any(a[f]!=expected[f] for f in ("z","closed","violations")):
                            checks.append("Terminal pairing mismatch: "+group+"/"+key+"/"+name+"/"+label)
                    if b["in_mask"]!=r["in_mask"]:checks.append("Mask mismatch: "+key)
                    if not r["in_mask"]:continue
                    for i,s in enumerate(DIMS):
                        n=Fraction(delta[i]);j=0 if n<0 else 2 if n>0 else 1
                        counts[s][j]+=1
                        if n:changed[s]["lower" if n<0 else "higher"].append(key)
                    a,y=b["candidate"]["closed"],b["reference"]["closed"]
                    if a!=y:closure["gained" if a else "lost"].append(key)
                item["panels"][panel]=dict(on_original_mask_lower_same_higher=counts,changed_rows=changed,closure=closure)
            summary[group][name]=item
    return summary


def forecast(terminal,rows):
    wanted={"U0":["C全续","C早续","C早止"],"SEARCH":["C全续","C早止","V早续"]}
    actual=terminal.get("paid",{})
    tests=[]
    def obs(name,expected,actual):
        tests.append(dict(item=name,expected=expected,actual=actual,status="UNOBSERVED" if actual is None else
                          "MATCH" if actual==expected else "DIFFERENT"))
    for g in wanted:
        obs(g+" tickets",wanted[g],actual.get(g))
        obs(g+" lock","C早止",terminal.get("locks",{}).get(g,{}).get("lock"))
    for name in ("C早续","C早止","V早续"):
        actual_direct=sorted(k for k,r in rows.items() if name in r["paid_candidates"] and
                            any(x["mode"]=="DIRECT" for x in r["paid_candidates"][name].get("requests",[])))
        if all(name in r["paid_candidates"] and "z" in r["paid_candidates"][name] for r in rows.values()):
            obs(name+" DIRECT rows",["ext35.H06","ext35.J04","ext35.K01","ext35.K02"],actual_direct)
        else:obs(name+" DIRECT rows",["ext35.H06","ext35.J04","ext35.K01","ext35.K02"],None)
    for key,fix,commit,window_exit,publish,work,closed in (
            ("ext35.H06",8,12,14,16,8,True),("ext35.J04",6,10,12,15,9,True),
            ("ext35.K01",7,11,13,16,9,True),("ext35.K02",7,11,13,None,7,False)):
        for name in ("C早续","C早止"):
            row=rows[key]["paid_candidates"].get(name,{})
            values=None
            if "z" in row:
                req=next((x for x in row["requests"] if x["action"]=="FIX_CTRL"),{})
                ex=next(iter(row["execution_receipts"]),{})
                exit_end=next((x[1] for x in row["safe_exits"] if x[2]=="FIX_CTRL"),None)
                vr=next(iter(row["verify_records"]),{})
                values=[req.get("time"),ex.get("committed_at"),exit_end,vr.get("available_at"),row["z"],row["closed"]]
            obs(key+"/"+name,[fix,commit,window_exit,publish,[0,0,work,work],closed],values)
    for key,when,L in (("dev19.C03",4,0),("ext35.A02",6,0)):
        for name in ("C全续","C早续","C早止"):
            a=rows[key]["paid_candidates"].get(name,{})
            obs(key+"/"+name+" CONFIG stop",[[L,L,2,2],True,when],
                [a["z"],a["closed"],a["stop"]["time"]] if "z" in a else None)
    for key,L in (("dev19.C06a",5),("ext35.C01",0)):
        for name,work in (("C全续",3),("C早续",3),("C早止",1)):
            a=rows[key]["paid_candidates"].get(name,{})
            obs(key+"/"+name+" inconclusive POS",[[L,L,work,work],False],
                [a["z"],a["closed"]] if "z" in a else None)
    return dict(source="c32f00e7/before-execution.md",field_order_for_early_rows=[
        "FIX_request","committed_at","FIX_exit_end","VERIFY_publication","z","closed"],
        classification="Pre-execution claims compared with saved observations only",items=tests,
        totals=dict(Counter(x["status"] for x in tests)))


def export(source,stage,exit_code):
    m=read(source/MANIFEST); root=Path(m["output_root"]); dest=stage/"release"
    dest.mkdir(exist_ok=False)
    preflight=read(stage/"preflight.json") if (stage/"preflight.json").exists() else {}
    terminal=read(root/"terminal.json") if (root/"terminal.json").is_file() else {}
    failure=read(root/"failure.json") if (root/"failure.json").is_file() else {}
    journal=root/"queries/ledger.jsonl";events,torn=lines(journal)
    checks=[]
    if torn:checks.append("Torn trailing query event; retain full original")
    tickets=[]; active=None
    for e in events:
        event=e["event"]
        if event=="ticket":
            active=dict(group=e["group"],ticket=e["ticket"],descriptor=e["descriptor"],prior=e["prior"],
                        ticket_event=e["sequence"],started=[],hits=[],returns=[],batch=None,unlocked=False,stop=None)
            tickets.append(active)
        elif active:
            if event=="physical_intent":active["started"].append(e["key"])
            elif event=="cache_hit":active["hits"].append(e["key"])
            elif event=="returned":active["returns"].append({"key":e["key"],"counts":e["counts"]})
            elif event in ("batch_complete","batch_stop"):active["batch"]=e
            elif event=="unlocked":active["unlocked"]=True;active["release_event"]=e["sequence"]
            elif event=="query_stopped":active["stop"]=e
    purchased=list(dict.fromkeys(t["descriptor"] for t in tickets))
    # Identify private directories by exact binding. No call to the studied implementation.
    identity=dict(purpose="ORDINARY_V2_RESEARCH",protocol=m["protocol_revision"],core=m["core_revision"],
                  runtime=m["interpreter_sha256"],source=RUN_SOURCE,input_revision=digest(m["files"]),
                  clock_horizon="H20-public-integers-v2",scoring=m["files"]["src/aegis_dc/london_treatment_score.py"],
                  initial="empty-PRE",observations="public-view-v2",instance=MANIFEST_SHA)
    panels={}; records={}; episode_ids={}; cache_hashes={}; counted=Counter(); states=Counter()
    unknown=[]; pending=[]; technical=[]; identities={}; physical_receipts=[]
    for p in m["panels"]:
        panel=p["name"]; rows=[]
        for c in read(source/p["input"])["conditions"]:
            ident=c["condition_id"];key=panel+"."+ident
            ref=preflight.get("original_rows",{}).get(panel,{}).get(ident,{})
            row=dict(key=key,in_mask=ref.get("in_mask"),baseline=ref.get("arms",{}),paid_candidates={})
            records[key]=row;rows.append(row)
            for name in purchased:
                binding=dict(identity,panel_key=key,condition_digest=digest(c["common"]),descriptor=name)
                uid=digest(binding); folder=root/"episodes"/uid; cached=root/"queries/cache"/(uid+".json")
                episode_ids[name,key]=uid
                value={"status":"NOT_STARTED"};row["paid_candidates"][name]=value
                if not folder.exists():continue
                value.update(status="INTENT_ONLY",episode=uid)
                paths={f.name:dict(sha256=sha(f),bytes=f.stat().st_size) for f in sorted(folder.iterdir()) if f.is_file()}
                identities[uid]=dict(panel_key=key,descriptor=name,files=paths)
                intent=read(folder/"intent.json") if "intent.json" in paths else {}
                if (intent.get("purpose"),intent.get("origin"),intent.get("descriptor"),intent.get("condition"))!=(
                        identity["purpose"],uid,name,c["common"]):checks.append("Episode input binding "+uid)
                calls=call_log(folder/"calls.jsonl")
                counted.update(calls["known_counts"])
                end=read(folder/"terminal.json") if "terminal.json" in paths else {}
                if not end:pending.append(uid)
                if not end or calls["torn"] or calls["pending"] or calls["duplicate_or_orphan"]:unknown.append(uid)
                if end.get("status")=="ERROR":technical.append(dict(episode=uid,key=key,descriptor=name,terminal=end))
                physical_receipts.append(dict(key=key,descriptor=name,episode=uid,terminal=end,ledger=calls))
                if "raw.json" not in paths:
                    value["status"]=end.get("status","UNRESOLVED");continue
                raw=read(folder/"raw.json")
                if end.get("raw")!=digest(raw):checks.append("Raw-to-terminal "+uid)
                if not (raw["origin"]==uid and raw["purpose"]==identity["purpose"] and raw["descriptor"]==name
                        and raw["isolation"]["passed"] and raw["final"]["original_input"]==c["common"]):
                    checks.append("Actual identity/isolation "+uid)
                if end.get("counts")!=calls["known_counts"] or end.get("counts")!=raw["counts"]:
                    checks.append("Call accounting "+uid)
                value.update(timeline(raw),status="COMPLETE" if end.get("status")=="COMPLETE" else "UNPROVED",
                             episode=uid,counts=raw["counts"],raw_sha256=paths["raw.json"]["sha256"])
                states[(panel,name,value["stage"])]+=1
                if cached.is_file():
                    entry=read(cached)
                    ch=digest(entry["row"])
                    cache_hashes[name,key]=ch
                    if entry["identity"]!=binding or entry["sha256"]!=ch:
                        checks.append("Cache identity "+uid)
                    compact=entry["row"]
                    if (any(compact[n]!=value[n] for n in ("z","closed","violations","complete","work_by_action"))
                            or compact["frames"]!=raw["run"]["public_trace"] or compact["requests"]!=raw["run"]["requests"]):
                        checks.append("Cache-to-raw "+uid)
        panels[panel]=rows
    for t in tickets:
        name=t["descriptor"]; target=root/"queries"/t["group"]/str(t["ticket"])
        reportfile=target/"report.json"
        t["report"]=read(reportfile) if reportfile.exists() else None
        if t["report"]:
            report=t["report"]
            if (report["group"],report["ticket"],report["descriptor"])!=(t["group"],t["ticket"],name):
                checks.append("Ticket report binding")
            for key,h in report["row_hashes"].items():
                if cache_hashes.get((name,key))!=h:checks.append("Ticket/cache row hash "+key)
            if t["unlocked"] and (len(report["row_hashes"])!=54 or len(t["hits"])+len(t["started"])!=54):
                checks.append("Incomplete column unlocked")
        for key in t["started"]:
            uid=episode_ids[name,key]; loc=target/"raw"/(uid+".json")
            if loc.is_file():
                copy=read(loc)
                if (copy["episode"]!=uid or digest(copy["row"])!=cache_hashes.get((name,key))
                        or (root/"episodes"/uid/"terminal.json").is_file()
                        and copy["raw_digest"]!=read(root/"episodes"/uid/"terminal.json").get("raw")):
                    checks.append("Physical return/archive "+uid)
            elif t["unlocked"]:checks.append("Missing returned archive "+uid)
        t["suffix_not_started"]=[k for k in records if k not in set(t["started"])|set(t["hits"])]
    normal=terminal.get("status")=="COMPLETE" and exit_code==0
    if normal:
        if len(tickets)!=6 or not all(t["report"] and t["unlocked"] for t in tickets):checks.append("Six complete releases")
        if len(terminal["reports"])!=len(tickets) or any(t["report"]!=u for t,u in zip(tickets,terminal["reports"])):
            checks.append("Terminal reports / ticket originals disagree")
        if len(physical_receipts)!=sum(len(t["started"]) for t in tickets):checks.append("Physical roots / starts disagree")
        if len(physical_receipts)>270 or unknown or pending or technical:checks.append("Physical cap or unresolved return")
        limits=dict(constructor=270,plant=8100,policy=5400,request=1350,scorer=270)
        if any(counted[k]>v for k,v in limits.items()):checks.append("Call caps")
        if any(len(terminal["paid"][g])!=3 or terminal["paid"][g]!=[t["descriptor"] for t in tickets if t["group"]==g]
               for g in ("U0","SEARCH")):checks.append("Terminal payment scope")
    compared=comparisons(terminal,panels,checks) if normal else {}
    frontier_evidence={}
    if normal:
        for t in tickets:
            report=t["report"]; front=report["selection"]["frontier"]; promotions=report["selection"]["flags"]
            k=t["group"]+"."+str(t["ticket"]); masks={i:r["in_mask"] for i,r in records.items()}
            def col(name):
                return {i:(r["baseline"][name] if name in ARMS else r["paid_candidates"][name]) for i,r in records.items()}
            detail={}
            for n in promotions:
                if n in front:continue
                detail[n]={}
                for a in front:
                    why=pareto_witness(col(a),col(n),masks)
                    if why["dominates"]:detail[n][a]=why["strict_rows"]
                if not detail[n]:checks.append("Missing recorded frontier domination: "+k+"/"+n)
            frontier_evidence[k]=detail
    for panel,rows in panels.items():
        save(dest/(panel+"-rows.json"),dict(panel=panel,order=[r["key"] for r in rows],descriptor_order=purchased,
                                            source="Original research raw and charge-bound cached rows",rows=rows))
    forecast_rows=forecast(terminal,records) if normal else {"status":"NOT_EVALUABLE_AFTER_STOP","paid_prefix":[t["descriptor"] for t in tickets]}
    actual_dirs={x.name for x in (root/"episodes").iterdir() if x.is_dir()} if (root/"episodes").is_dir() else set()
    orphan=sorted(actual_dirs-identities.keys())
    if orphan:checks.append("Unbound physical directories")
    bundle=dict(entry_status=terminal.get("status","NO_COMPLETE_TERMINAL"),entry_exit=exit_code,job=__import__("os").environ["SLURM_JOB_ID"],
                manifest_sha256=MANIFEST_SHA,approval_sha256=APPROVAL_SHA,execution_revision=RUN_SOURCE,
                preflight_status=preflight.get("status"),preflight_sha256=sha(stage/"preflight.json") if preflight else None,
                original_masks=preflight.get("masks",{}),paid=terminal.get("paid",{g:[x["descriptor"] for x in tickets if x["group"]==g] for g in ("U0","SEARCH")}),
                locks=terminal.get("locks",{}) if normal else {},queried=purchased,not_queried=[n for n in m["candidates"] if n not in purchased],
                feedback_order=BITS,counts=dict(charged_tickets=len(tickets),charged_logical_rows=54*len(tickets),
                released_tickets=sum(t["unlocked"] for t in tickets),released_logical_rows=sum(54 for t in tickets if t["unlocked"]),
                physical_intents=sum(len(t["started"]) for t in tickets),physical_directories=len(actual_dirs),
                known_completed=sum(x["terminal"].get("status")=="COMPLETE" for x in physical_receipts),
                cache_hits=sum(len(t["hits"]) for t in tickets),known_calls={k:counted[k] for k in KINDS},
                unknown_count_episodes=unknown,unresolved_episodes=pending,orphan_directories=orphan,engineering_cache_hits=0,retries=0),
                source_failure=failure,technical_terminals=technical,readback_findings=checks,
                stage_counts=[dict(panel=k[0],candidate=k[1],stage=k[2],count=v) for k,v in sorted(states.items())],
                scored_after_entry=0,selected_after_entry=0,confirmation_runs=0,RSI_runs=0)
    save(dest/"tickets.json",dict(feedback_order=BITS,events=tickets,frontier_domination_witnesses=frontier_evidence,
                                 ledger_sha256=sha(journal) if journal.exists() else None))
    save(dest/"comparisons.json",compared); save(dest/"prediction-check.json",forecast_rows)
    save(dest/"physical-evidence.json",dict(episodes=physical_receipts,files=identities))
    save(dest/"result.json",bundle)
    return not checks


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path);parser.add_argument("stage",type=Path);parser.add_argument("exit_code",type=int)
    a=parser.parse_args()
    raise SystemExit(0 if export(a.source.resolve(),a.stage.resolve(),a.exit_code) else 2)
