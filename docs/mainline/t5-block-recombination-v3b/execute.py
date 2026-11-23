"""Replay archived public messages; score only the one published Stage-A vector."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from functools import lru_cache
import gzip
import json
import os
from pathlib import Path
import socket
import sys
import time
import traceback

from stage_a import DOMAINS, FAMILIES, GLOBAL, ROLES, choice_set, columns, construct, estimates, gate, mapped, require, selfcheck

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/"t5-landscape-diagnostic-v3a"
sys.path.insert(0,str(OLD))
import landscape as old
from landscape import digest, read, sha, write, write_gz

ACT=old.SHARE/"T5-block-recombination-v3b"
LABEL="V3B_RECOMBINED"
CLOCK=tuple(range(0,3601,60))
PIN=read(HERE/"predecessor.json")["v3a"]


@lru_cache(None)
def data():
    with gzip.open(OLD/"results.json.gz","rt") as fd:
        earlier=json.load(fd)
    receipt=read(OLD/"receipt.json")
    require(receipt["durable_position_index"]==earlier["positions"],"two sealed position indices")
    pos={(p["label"],p["key"]):p for p in earlier["positions"]}
    rows={r["key"]:r for r in earlier["conditions"]}
    m=old.manifest()
    require(earlier["panel"]==PIN["panel-and-strategies.json"] and earlier["source"]==PIN["source-freeze.json"] and
            tuple(old.role_list(old.config())[:-1])==ROLES and len(pos)==len(earlier["positions"]) and
            set(rows)==set(m["order"]) and len(rows)==36,"registered scores and roster")
    return m,rows,pos


def guard(name):
    import numpy as np
    reg=read(ACT/"registrations"/(name+".json"))
    require(reg["job"]==old.job() and reg["release"]==os.environ["STAGE_A_RELEASE"] and
            reg["name"]==name and reg["cpus"]==int(os.environ["SLURM_CPUS_PER_TASK"]),"allocation authorization")
    for path,h in reg["files"].items():
        require(sha(HERE/path)==h,"published runner "+path)
    require(reg["files"]==read(ACT/"release.json")["files"],"identical staged runner")
    for path,h in PIN.items():
        require(sha(OLD/path)==h, "sealed v3a "+path)
    os.environ["V3A_SOURCE"]=PIN["source-freeze.json"]
    os.environ["V3A_PANEL"]=PIN["panel-and-strategies.json"]
    tree=old.check_source()
    require(np.__version__=="2.2.6","statistics runtime")
    workers=old.verify_workers()
    if name!="selfcheck":
        require(read(ACT/"selfcheck.json")["status"]=="PASS","public self-check")
    return reg,tree,workers


def self_test(tree,workers):
    from aegis_improvement_v2.space import root,validate
    m,rows,pos=data()
    space=read(old.V2/"space.json")
    base=root(space,"MAIN")
    names=set(GLOBAL)|{k for b in DOMAINS for k in columns(b)}
    require(names==base.keys() and len(names)==92 and list(DOMAINS)==space["action_types"],"exact nine blocks")
    represent={}
    for label in ROLES:
        descriptor,manual=old.binding(label,m)
        if label=="B_COST" or (descriptor and not manual):
            v=base if descriptor is None else descriptor["theta"]
            validate(space,"MAIN",v)
            represent[label]=digest(v)
        require(all(pos[label,k]["status"]=="SCORED" and label in rows[k]["arms"] for k in m["order"]),"complete inherited roster")
    require(len(represent)==55 and set(ROLES)-set(represent)=={"M","M_HOT","V_COST"},"original descriptor classes")
    require(len(m["order"])==36 and all(sum(rows[k]["family"]==f for k in rows)==6 for f in FAMILIES),"balanced board")
    return dict(status="PASS",rules=selfcheck(),facility_calls=0,replay_positions=0,worker_bundles=workers,
                main_donor_vectors=represent,source=os.environ["STAGE_A_RELEASE"],tree=tree,job=old.job())


def replay_one(label,key,folder):
    from public_ipc import Process
    m,rows,idx=data()
    case=old.case_at(key,m)
    identity=idx[label,key]
    parent=old.ACT/"positions"/label/key
    orig=parent/"original.jsonl.gz"; oldscore=parent/"score.json"; mark=parent/"native-entry.json"
    require(identity["status"]=="SCORED" and all(sha(p)==identity[key_] for p,key_ in
            ((orig,"raw_sha256"),(oldscore,"score_sha256"),(mark,"entry_sha256"))),"sealed private input: "+label+"/"+key)
    saved=read(oldscore); entry=read(mark)
    require(saved["entry"]==entry and (entry["label"],entry["key"],entry["input"])==(label,key,m["conditions"][key]["sha256"])
            and saved["L"]==rows[key]["arms"][label]["L"],"position binding")
    with gzip.open(orig,"rt") as fp:
        meta=json.loads(next(fp))["metadata"]
    static=case["native"]["dispatch_program"]["public"]
    require(meta["inputs"]["dispatch_program"]==case["native"]["dispatch_program"],"static and original channel")
    decisions,proposals=meta["policy_public_decisions"],meta["v3_proposals"]
    require([d["view"]["time"] for d in decisions]==list(CLOCK) and len(proposals)==61,"complete original history")
    descriptor,manual=old.binding(label,m)
    worker=Process(label,folder/"worker.stderr",descriptor,manual)
    ok=False; issued=[]; events=[]; records=[]
    try:
        worker.start(static)
        require(worker.identity==entry["worker_bundle"] and (digest(descriptor) if descriptor else None)==entry["vector_sha256"],"exact worker")
        for tick,d,p in zip(CLOCK,decisions,proposals,strict=True):
            view=d["view"]
            require(set(view)=={"time","records","work","paid","writes","fixed","issued"} and
                    all(r["arrived"]<=tick for ch in ("records","paid","writes","fixed") for r in view[ch]) and
                    all(w["arrived_at_s"]<=tick for w in view["work"]),"public prefix")
            reply=worker.choose(static,view,label,{})
            require(p["at"]==tick and p["view"]==digest(view) and p["proposal"]==digest(reply)
                    and p["requested"]==reply["request"],"frame response disagrees with v3a")
            original=d["decision"]["request"]
            request=reply["request"]; refusal=p["external_refusal"]
            require(original==(None if refusal else request) and (not refusal or request is not None),"actual admission bridge")
            block=mapped(static,request)
            if request:
                events.append(dict(at=tick,block=block,phase=request["phase"],task=request["task"],issued=original is not None,refusal=refusal))
            if original:
                issued.append([tick,original["task"]])
            records.append([tick,p["view"],p["proposal"],block])
        require(issued==saved["requests"]==rows[key]["arms"][label]["requests"] and digest(worker.ipc)==saved["worker_ipc"] and
                digest(worker.events)==saved["proposal"]==identity["transcript"],"entire IPC and issued native work")
        ok=True
    finally:
        worker.close(failed=not ok)
    return dict(label=label,key=key,status="REPLAYED",frames=len(records),frame_index_sha256=digest(records),events=events,
                raw_sha256=identity["raw_sha256"],score_sha256=identity["score_sha256"],entry_sha256=identity["entry_sha256"],
                source_job=identity["job"],worker_bundle=entry["worker_bundle"],worker_ipc=saved["worker_ipc"],job=old.job())


def audit_panel(m):
    oldsets=old.old_identities(old.config())
    full=set(); ops=set(); halves={"A":set(),"B":set()}
    for k in m["order"]:
        case=old.case_at(k,m);info=m["conditions"][k];op=old.operative(case)
        require(op==info["operative_sha256"] and case["evaluation"]["family"]==info["family"],"original condition")
        full.add(info["sha256"]);ops.add(op);halves[info["half"]].add(op)
    require(len(full)==len(ops)==36,"unique original cases")
    overlaps={n:dict(full=len(full&x),operative=len(ops&y)) for n,(x,y) in oldsets.items()}
    require(all(not r["full"] and not r["operative"] for r in overlaps.values()) and not halves["A"]&halves["B"],"stage-A identity accounting")
    return dict(v3a_reused=36,excluded=overlaps,within_duplicates=0,halves_overlap=0,new_inputs=0,H2_accesses=0)


def select_donor():
    from aegis_improvement_v2.space import root,validate
    m,rows,_=data()
    audit=audit_panel(m)
    reports={};ties={};votes={};errors=[];members={}
    replay_count=frames=0
    for f in FAMILIES:
        keys=[k for k in m["order"] if m["conditions"][k]["family"]==f]
        sums=Counter(); signs=Counter();phases=Counter();per_key={};empty_units=0;valid=0
        for key in keys:
            united=set(); votes_here=Counter(); labels_no_requests=[];valid_key=0
            for label in ROLES:
                p=ACT/"replay"/label/key/"row.json"
                q=read(p) if p.exists() else {"status":"NO_ROW"}
                if q["status"]!="REPLAYED":
                    errors.append(dict(key=key,label=label,status=q["status"],error=q.get("error")));continue
                require((q["key"],q["label"])==(key,label) and q["frames"]==61,"row identity")
                members[label+"/"+key]=sha(p);valid_key+=1;valid+=1;frames+=q["frames"];replay_count+=1
                if not q["events"]:
                    labels_no_requests.append(label);empty_units+=1
                for e in q["events"]:
                    b=e["block"];united.add(b);votes_here[b]+=1;sums[b]+=1;signs[b]+=int(e["issued"]);phases[(b,e["phase"])]+=1
            per_key[key]=dict(blocks=sorted(united),request_counts=dict(votes_here),trajectories=valid_key,
                              no_request_labels=labels_no_requests)
        ties[f]=choice_set(ROLES,{l:[rows[k]["arms"][l]["L"] for k in keys] for l in ROLES})
        votes[f]=dict(sums)
        reports[f]=dict(trajectories=valid,requests=sum(sums.values()),issued=sum(signs.values()),refused=sum(sums.values())-sum(signs.values()),
                        block_requests=dict(sums),block_issues=dict(signs),by_phase={b:dict((p,v) for (bb,p),v in phases.items() if b==bb) for b in sums},
                        no_attribution_conditions=sum(not r["blocks"] and r["trajectories"]==58 for r in per_key.values()),
                        no_request_trajectories=empty_units,conditions=per_key,co_minima=ties[f])
    controls=choice_set(ROLES,{l:[rows[k]["arms"][l]["L"] for k in m["order"]] for l in ROLES})
    space=read(old.V2/"space.json");base=root(space,"MAIN")
    v={"B_COST":base}
    for label in ROLES:
        desc,manual=old.binding(label,m)
        if desc and not manual:
            v[label]=desc["theta"]
    if errors:
        chosen=dict(status="INCOMPLETE_REPLAY")
    else:
        chosen=construct(FAMILIES,DOMAINS,votes,ties,v,base)
        if chosen["status"]=="LOCKED":
            validate(space,"MAIN",chosen["theta"])
            chosen["theta_sha256"]=digest(chosen["theta"])
    return dict(schema="T5-v3b-stage-A-construction",release=os.environ["STAGE_A_RELEASE"],job=old.job(),panel=PIN["panel-and-strategies.json"],
                earlier_results=PIN["results.json.gz"],rows_sha256=members,mapping=reports,replayed=replay_count,frames=frames,
                planned_replays=2088,planned_frames=127368,errors=errors,comparator_co_minima=controls,control=controls[0],
                overlap=audit,facility_calls=0,construction=chosen)


def native_one(key,folder,tree):
    from native_v3 import native_run
    from public_ipc import Process
    from score_saved import score
    from run_panel import retain
    m,_,_=data();case=old.case_at(key,m)
    p=ACT/"construction.json"; reg=read(ACT/"registrations"/(os.environ["STAGE_A_JOB"]+".json"))
    require(sha(p)==reg["construction"]==sha(HERE/"construction.json"),"published construction")
    chosen=read(p)["construction"]
    require(chosen["status"]=="LOCKED" and chosen["theta_sha256"]==digest(chosen["theta"]),"sole frozen vector")
    descriptor=dict(track="MAIN",theta=chosen["theta"],no_probe=False)
    worker=Process(LABEL,folder/"worker.stderr",descriptor);ok=False
    raw=folder/"original.jsonl.gz"
    try:
        worker.start(case["native"]["dispatch_program"]["public"])
        entry=dict(key=key,label=LABEL,input=m["conditions"][key]["sha256"],operative=old.operative(case),release=os.environ["STAGE_A_RELEASE"],
                   construction=reg["construction"],theta=digest(chosen["theta"]),worker=worker.identity,
                   server_pid=os.getpid(),worker_pid=worker.child.pid,job=old.job(),core_tree=tree)
        write(folder/"native-entry.json",entry)
        run,terminal=native_run(case,LABEL,{},(),decider=worker.choose);ok=True
    finally:
        worker.close(failed=not ok)
    retain(raw,run,terminal)
    metrics=score(case,run,terminal,LABEL)
    require(metrics["runtime"]==tree and len(run["v3_proposals"])==metrics["clocks"]==61 and
            run["v3_received_maintenance"]==case["maintenance"] and not run["t3_unpurchased_evaluator_only"] and
            worker.child.pid!=os.getpid() and worker.events==[[q["at"],q["view"],q["proposal"]] for q in run["v3_proposals"]],"native decision identity")
    return dict(key=key,status="SCORED",entry=entry,raw_sha256=sha(raw),entry_sha256=sha(folder/"native-entry.json"),
                ipc=digest(worker.ipc),proposal=digest(worker.events),
                **{k:metrics[k] for k in ("L","U","person","tool","fee","integral_balances","requests","clocks")})


def unit(args):
    kind,label,key,tree=args
    folder=(ACT/"replay"/label/key) if kind=="map" else ACT/"positions"/key
    folder.mkdir(parents=True,exist_ok=False); start=time.monotonic()
    try:
        row=replay_one(label,key,folder) if kind=="map" else native_one(key,folder,tree)
    except Exception as error:
        (folder/"failure.log").write_text(traceback.format_exc(),encoding="utf8")
        row=dict(key=key,label=label,status="FAILED",error=f"{type(error).__name__}: {error}",job=old.job())
    row["wall_s"]=time.monotonic()-start
    row["entered"]=(folder/"native-entry.json").is_file()
    write(folder/"row.json",row)
    return row["status"]


def batch(name,cpus,tree):
    m,_,_=data()
    parts=name.split("-");kind=parts[0]; f=FAMILIES[int(parts[-1])-1]
    keys=[k for k in m["order"] if m["conditions"][k]["family"]==f and
          (kind=="native" or m["conditions"][k]["half"]==parts[1])]
    items=[(kind,label,k,tree) for k in keys for label in (ROLES if kind=="map" else (LABEL,))]
    require(len(items)==(174 if kind=="map" else 6),"exact batch slots")
    import multiprocessing as mp
    with ProcessPoolExecutor(max_workers=cpus,mp_context=mp.get_context("fork")) as pool:
        counts=Counter(pool.map(unit,items,chunksize=1))
    return dict(name=name,planned=len(items),states=dict(counts),job=old.job())


def summarize():
    m,rows,_=data(); p=read(ACT/"construction.json"); result={}; errors=[]
    ctrl=p["control"]; keys=m["order"]
    for k in keys:
        folder=ACT/"positions"/k; path=folder/"row.json"
        q=read(path) if path.exists() else {"status":"UNEXECUTED"}
        try:
            if q["status"]!="SCORED":
                raise ValueError(q.get("error",q["status"]))
            e=read(folder/"native-entry.json");reg=read(ACT/"registrations"/("native-"+str(FAMILIES.index(rows[k]["family"])+1)+".json"))
            require(e==q["entry"] and e["job"]==reg["job"] and e["construction"]==reg["construction"]==sha(ACT/"construction.json")
                    and e["release"]==p["release"] and e["theta"]==p["construction"]["theta_sha256"] and e["key"]==k and e["label"]==LABEL
                    and e["input"]==m["conditions"][k]["sha256"] and e["operative"]==m["conditions"][k]["operative_sha256"] and
                    e["server_pid"]!=e["worker_pid"] and e["worker"]==read(ACT/"selfcheck.json")["worker_bundles"]["learned"] and
                    sha(folder/"native-entry.json")==q["entry_sha256"] and sha(folder/"original.jsonl.gz")==q["raw_sha256"],"saved identities")
            with gzip.open(folder/"original.jsonl.gz","rt") as fp:
                meta=json.loads(next(fp))["metadata"]
            raw=meta["summary"]; expected=(raw["service_deficit_time_s"],raw["demand_service_unit_s"]-raw["delivered_service_unit_s"])
            require(all(abs(a-b)<=old.EPS and abs(a-c)<=old.EPS for a,b,c in zip((q["L"],q["U"]),expected,q["integral_balances"],strict=True)) and
                    q["clocks"]==len(meta["v3_proposals"])==61 and
                    digest([[z["at"],z["view"],z["proposal"]] for z in meta["v3_proposals"]])==q["proposal"],"saved integral or proposals")
            result[k]={**{x:q[x] for x in ("L","U","person","tool","fee","clocks","raw_sha256","entry_sha256","ipc","proposal")},
                       "row_sha256":sha(path),"job":e["job"],"family":rows[k]["family"],"control_L":rows[k]["arms"][ctrl]["L"]}
        except (ValueError,OSError,KeyError,TypeError,EOFError,StopIteration) as error:
            errors.append(dict(key=k,state=q["status"],entered=(folder/"native-entry.json").exists(),reason=str(error)))
    comparisons=None;verdict="UNRESOLVED_STOP"
    if not errors and p["construction"]["status"]=="LOCKED":
        tx={k:result[k]["L"] for k in keys}; control={k:result[k]["control_L"] for k in keys}
        fam={k:rows[k]["family"] for k in keys}
        comparisons=estimates(keys,fam,tx,[control,control])
        require(comparisons[0]==comparisons[1],"the two specified controls are identical")
        verdict="PASS" if gate(comparisons) else "FAIL_STOP"
    return dict(schema="T5-v3b-stage-A-result",status=verdict,construction_sha256=sha(ACT/"construction.json"),
                release=p["release"],job=old.job(),planned=36,scored=len(result),entries=sum((ACT/"positions"/k/"native-entry.json").exists() for k in keys),
                control=ctrl,contrasts=comparisons,rows=result,errors=errors,H2_generated=0,H2_read=0,H2_derived=0,
                hot_searches=0,old_policy_facility_runs=0)


def main(name):
    reg,tree,workers=guard(name)
    log=ACT/"jobs"/name;log.mkdir(parents=True,exist_ok=False)
    write(log/"entry.json",dict(job=old.job(),name=name,host=socket.gethostname(),release=reg["release"]))
    if name=="selfcheck":
        output=self_test(tree,workers);write(ACT/"selfcheck.json",output)
    elif name=="construct":
        output=select_donor();write(ACT/"construction.json",output)
    elif name=="report":
        output=summarize();write(ACT/"result.json",output)
    else:
        output=batch(name,reg["cpus"],tree)
    write(log/"terminal.json",{k:v for k,v in output.items() if k in ("job","name","status","states","planned","scored","entries","replayed","frames")})
    print(name,read(log/"terminal.json"),flush=True)


if __name__=="__main__":
    main(sys.argv[1])
