"""Run on Slurm: collect common public prefixes first, then join the sealed scores."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import multiprocessing as mp
import os
from pathlib import Path
import sys
import traceback
from unittest.mock import patch

from analysis import ROLES,FAMILIES,development,fit,interval,need,winner
from selector import catalogue,features,signals

PK=Path(__file__).resolve().parent
B=PK.parent/"t5-block-recombination-v3b"
sys.path.insert(0,str(B))
import execute as previous
from landscape import digest,read,sha,write
import public_ipc

ACT=previous.old.SHARE/"T5-observable-selector-v3c"
CLOCK=previous.CLOCK


@lru_cache(None)
def seals():
    p=read(B/"receipt.json")
    need(sha(B/"construction.json")==p["vector_publication"]["sha256"],"previous public replay roster")
    return read(B/"construction.json")["rows_sha256"]


def guard(label):
    import numpy as np
    rel=read(ACT/"release.json");reg=read(ACT/"registrations"/(label+".json"))
    need(os.environ["SLURM_JOB_ID"]==reg["job"] and reg["name"]==label and rel["commit"]==reg["source"] and
         reg["cpus"]==int(os.environ["SLURM_CPUS_PER_TASK"]),"held registration")
    for name,h in rel["files"].items():
        need(sha(PK/name)==h,"stage A frozen "+name)
    for name,h in rel["previous"].items():
        need(sha(PK.parents[2]/name)==h,"inherited evidence "+name)
    os.environ["V3A_PANEL"]=previous.PIN["panel-and-strategies.json"]
    os.environ["V3A_SOURCE"]=previous.PIN["source-freeze.json"]
    previous.old.check_source();previous.old.verify_workers()
    need(np.__version__=="2.2.6" and ROLES==previous.ROLES and FAMILIES==previous.FAMILIES,"old order and runtime")
    return reg


def difference(hashes):
    groups={}
    for label,h in hashes:
        groups.setdefault(h,[]).append(label)
    return groups if len(groups)>1 else None


def selfcheck():
    pub={"subjects":[{"id":"aliasN","key":"C"},{"id":"service-desk","key":"N"}]}
    r=dict(sampled=0,arrived=10,until=70,kind="alarm",subject="aliasN",copied_from=None)
    def frame(t,rows):return dict(time=t,records=rows,fixed=[])
    def cell(rows):return features(catalogue(pub),[signals(v) for v in rows])
    need(cell([frame(0,[r])])==("MAIN","NONE","NONE"),"future signal")
    need(cell([frame(60,[dict(r,copied_from="same"),dict(r,kind="order")])])==("MAIN","NONE","NONE"),"copy/order")
    need(cell([frame(60,[r]),frame(120,[r])])==("MAIN","C","alarm"),"legal first signal retained")
    decorated=dict(pub,family="invented",private_state="unavailable")
    early=frame(60,[dict(r,kind="prior",record_type="trend",subject=None)])
    need(features(catalogue(decorated),[signals(dict(early,evaluation="discard"))])==("MAIN","UNSCOPED","prior:trend"),"projection")
    need(difference([("a","x"),("b","x")]) is None and difference([("a","x"),("b","y")])=={"x":["a"],"y":["b"]},"mismatching decision frame")
    loss={"0":{"q":1,"p":0},"1":{"q":1,"p":0},"2":{"q":0,"p":4}}
    rule=fit(list(loss),{"0":"AA","1":"AA","2":"BB"},loss,("q","p"))
    need(rule["cells"]=={"AA":"p"} and rule["winner"]=="q" and winner(["0","1"],{k:{"q":1,"p":1} for k in loss},("q","p"))=="q","trained only/one/unseen/tie")
    z=[dict(family=f,d=-(i+1)) for i,f in enumerate(FAMILIES) for _ in range(6)]
    ci=interval(z,"d",1,"stage0");need(ci["mean"]==ci["upper"]==-3.5,"pair/stratum")
    need(interval([dict(r,d=0) for r in z],"d",1,"stage0")["upper"]==0,"strict boundary")
    return dict(status="PASS",checks=["cutoff","copy/order","first signal","projection","hash mismatch","fallback","tie","six strata","zero boundary"],new_facility=0)


def old_row(key,label):
    p=previous.ACT/"replay"/label/key/"row.json"
    need(sha(p)==seals()[label+"/"+key],"v3b saved replay "+label+"/"+key)
    row=read(p)
    need((row["label"],row["key"],row["status"])==(label,key,"REPLAYED"),"old replay identity")
    return row


def probe(arg):
    key,label,cutoff=arg
    out=ACT/"prefix"/key/label;out.mkdir(parents=True,exist_ok=False)
    try:
        saved=old_row(key,label); api=public_ipc.Process
        prefix=[]; projected=[]; static=None;static_hash=None
        class Tap(api):
            def start(self,pub):
                nonlocal static,static_hash
                static=catalogue(pub);static_hash=digest(pub)
                return super().start(pub)
            def choose(self,pub,view,role,plan):
                reply=super().choose(pub,view,role,plan)
                if view["time"]<=cutoff:
                    prefix.append(digest(view))
                    if label==ROLES[0]:
                        projected.append(signals(view))
                return reply
        with patch.object(public_ipc,"Process",Tap):
            fresh=previous.replay_one(label,key,out)
        for field in fresh:
            if field!="job":
                need(fresh[field]==saved[field],"old replay cross-check: "+field)
        need(static is not None and len(prefix)==cutoff//60+1,"inclusive common history")
        row=dict(key=key,label=label,status="OK",previous_native=fresh["raw_sha256"],previous_score=fresh["score_sha256"],
                 old_replay=seals()[label+"/"+key],ipc=fresh["worker_ipc"],full_index=fresh["frame_index_sha256"],
                 frames=61,static=static_hash,hashes=prefix,first=fresh["events"][0]["at"] if fresh["events"] else None,
                 cell=features(static,projected) if label==ROLES[0] else None)
    except Exception as e:
        (out/"failure.log").write_text(traceback.format_exc(),encoding="utf8")
        row=dict(key=key,label=label,status="INVALID",error=f"{type(e).__name__}: {e}")
    write(out/"record.json",row)
    return row,sha(out/"record.json")


def inspect_condition(key,pool):
    firsts=[q["events"][0]["at"] for label in ROLES if (q:=old_row(key,label))["events"]]
    first=min(firsts,default=None);cutoff=3600 if first is None else first
    replies=list(pool.map(probe,[(key,l,cutoff) for l in ROLES],chunksize=1))
    rows={r["label"]:r for r,_ in replies}
    result=dict(key=key,first_s=first,frame=None if first is None else int(first//60),roster=len(rows),rows={r["label"]:h for r,h in replies})
    errors=[r for r in rows.values() if r["status"]!="OK"]
    if errors:return dict(result,status="UNRESOLVED",errors=errors)
    need(list(rows)==list(ROLES) and first==min((r["first"] for r in rows.values() if r["first"] is not None),default=None),"original/replayed first nonempty proposal")
    diff=difference([(l,rows[l]["static"]) for l in ROLES])
    if diff:return dict(result,status="MISMATCH_STOP",at_s=0,frame_index=0,field="static",hash_groups=diff)
    representative=rows[ROLES[0]]
    for i,_ in enumerate(representative["hashes"]):
        diff=difference([(l,rows[l]["hashes"][i]) for l in ROLES])
        if diff:return dict(result,status="MISMATCH_STOP",at_s=CLOCK[i],frame_index=i,field="view",hash_groups=diff)
    return dict(result,status="PASS",static=representative["static"],prefix_hashes=representative["hashes"],
                frames_compared=len(representative["hashes"]),cell=representative["cell"] if first is not None else None)


def main(name):
    reg=guard(name);m,rows,_=previous.data()
    if name=="pilot":
        checked=selfcheck();write(ACT/"selfcheck.json",dict(checked,job=reg["job"]))
        start,end=0,12
    else:
        need(name=="remaining" and read(ACT/"selfcheck.json")["status"]=="PASS" and read(ACT/"pilot.json")["status"]=="PASS"
             and read(ACT/"budget.json")["proceed"],"pilot and measured budget")
        start,end=12,36
    keys=m["order"];folder=ACT/"checks";folder.mkdir(exist_ok=True)
    fail=None
    with ProcessPoolExecutor(reg["cpus"],mp_context=mp.get_context("fork")) as pool:
        for key in keys[start:end]:
            try:
                obs=inspect_condition(key,pool)
            except Exception as err:
                obs=dict(key=key,status="UNRESOLVED",error=f"{type(err).__name__}: {err}")
                (ACT/("failure-"+key+".log")).write_text(traceback.format_exc(),encoding="utf8")
            write(folder/(key+".json"),obs)
            print(key,obs["status"],obs.get("frame"),flush=True)
            if obs["status"]!="PASS":
                fail=key;break
    checks={k:read(folder/(k+".json")) for k in keys if (folder/(k+".json")).is_file()}
    term=dict(name=name,job=reg["job"],status="PASS" if fail is None else "STOP",failed_key=fail,inspected_keys=list(checks),facilities=0)
    if name=="remaining" or fail is not None:
        g0=all(k in checks and checks[k]["status"]=="PASS" for k in keys)
        output=dict(stage="development",source=reg["source"],panel=previous.PIN["panel-and-strategies.json"],old_results=previous.PIN["results.json.gz"],
                    gate0="PASS" if g0 else checks[fail]["status"],gate1="NOT_EVALUATED",checks=checks,
                    unexecuted=[k for k in keys if k not in checks],original_denominator=[36,58],new_facility=0)
        if g0 and all(q["first_s"] is not None for q in checks.values()):
            output.update(development(keys,rows,{k:q["cell"] for k,q in checks.items()}))
        output["overlap"]=previous.audit_panel(m) if g0 else None
        write(ACT/"development.json",output)
    write(ACT/(name+".json"),term)


if __name__=="__main__":
    main(sys.argv[1])
