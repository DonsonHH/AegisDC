"""Read only saved development positions and apply the preregistered paired analysis."""
from collections import Counter
import gzip
import json
import os
from statistics import mean
import subprocess

from context_t5 import (
    ACT, LOCK, METRICS, PK, T4B, TRACKS, bundle_paths, cases, digest, job, operative, read,
    read_case, require, settings, sha, verify_bundles, verify_sources, write, write_gz,
)
from run_plan import descriptor, state_at


def read_score(label,key,manifest,scored,verify_raw=False):
    path=ACT/"positions"/label/key
    entry_path=path/"native-entry.json"
    score_path=path/"score.json"
    raw=path/"original.jsonl.gz"
    if not score_path.is_file():
        return None,None,dict(label=label,key=key,entered=entry_path.is_file(),status="MISSING")
    value=read(score_path)
    entry=read(entry_path)
    require(value["entry"]==entry and entry["label"]==label and entry["key"]==key and entry["input"]==manifest["conditions"][key]["sha256"]
         and entry["input_manifest"]==os.environ["T5_INPUT_SHA"] and entry["source"]==sha(LOCK)
         and entry["pid"]!=entry["worker_pid"] and value["clocks"]==61,"saved evaluation identity")
    ref=bundle_paths()[0]
    bound=read(ACT/"worker-bundle.json")["bundle"] if label not in ref else ref[label][0]
    theta=descriptor(label)
    require(entry["worker_bundle"]==bound and entry["descriptor"]==(digest(theta) if theta else None),"served policy descriptor")
    require((entry["host"],entry["job"],entry["pid"]) not in scored,"native process reused")
    scored.add((entry["host"],entry["job"],entry["pid"]))
    detail=None
    if verify_raw:
        require(sha(raw)==value["raw_sha256"],"original evaluation bytes")
        with gzip.open(raw,"rt",encoding="utf8") as reader:
            detail=json.loads(next(reader))["metadata"]
        prior=read_case(key,manifest)
        inputs=prior["native"]
        require(detail["source_config"]==inputs["scenario"] and detail["inputs"]["dispatch_program"]==inputs["dispatch_program"]
                and detail["inputs"]["boundary_events"]==sorted(inputs["boundary_events"],key=lambda q:q["time_s"])
                and detail["t3_received_attachment_sha256"]==digest(prior["attachment"])
                and detail["v3_received_maintenance"]==prior["maintenance"],"stored native physical and public arguments")
        decisions=detail["policy_public_decisions"];proposals=detail["v3_proposals"]
        require([q["view"]["time"] for q in decisions]==list(range(0,3601,60))
                and all(digest(q["view"])==r["view"] for q,r in zip(decisions,proposals,strict=True))
                and value["public_transcript"]==digest([[r["at"],r["view"],r["proposal"]] for r in proposals]),
                "public transcript")
        if label=="B_COST":
            from aegis_cost_baseline.rule import operative_view
            require(value["public_ipc"]==digest([[q["view"]["time"],digest(operative_view(q["view"])),
                digest({k:v for k,v in q["decision"].items() if k!="certificates"})] for q in decisions]),"filtered baseline transcript")
    return value,detail,dict(entry,label=label,key=key,status="SCORED",score_sha256=sha(score_path),original_sha256=value["raw_sha256"])


def identity_audit(manifest):
    held=read(T4B/"condition-summary.json")["conditions"]
    require(len(held)==144,"complete public identity reference")
    full_h={v["sha256"] for v in held.values()}
    operative_h={v["operative_sha256"] for v in held.values()}
    own={}
    for mode in ("FIT","DEV"):
        full,ops=set(),set()
        for key in manifest["order"][mode]:
            case=read_case(key,manifest)
            identity=manifest["conditions"][key]
            eff=operative(case)
            require(eff==identity["operative_sha256"],"operative identity")
            full.add(identity["sha256"]);ops.add(eff)
        require(len(full)==len(ops)==len(manifest["order"][mode]),"unique development domains")
        own[mode]=dict(conditions=len(full),full_overlap_T4b=len(full&full_h),operative_overlap_T4b=len(ops&operative_h))
        if mode=="FIT":
            full_fit,op_fit=full,ops
    overlap=dict(full=len(full&full_fit),operative=len(ops&op_fit))
    require(not any(d["full_overlap_T4b"] or d["operative_overlap_T4b"] for d in own.values())
            and not any(overlap.values()),"disjoint development and holdout identities")
    return dict(corpus=len(held),by_domain=own,FIT_DEV_overlap=overlap,sampling_rejections=manifest["collision_rejected"],
                digest_of_public_index=sha(T4B/"condition-summary.json"))


def metrics(rows, design, family="overall"):
    import numpy as np
    from readback import estimates, samples

    cfg=dict(seed_prefix=design["bootstrap"]["prefix"],repetitions=design["bootstrap"]["draws"],
             interval_percentiles=design["bootstrap"]["quantiles"],quantile_interpolation=design["bootstrap"]["interpolation"])
    require(np.__version__=="2.2.6","pinned bootstrap")
    shared=samples(rows,cfg["seed_prefix"],family,cfg["repetitions"])
    arms=("MAIN","HOT","B_COST","V_COST")
    totals={}
    for label in arms:
        these=[r["arms"][label] for r in rows if label in r["arms"]]
        totals[label]=dict(n=len(these),avg={k:(mean(v[k] for v in these) if these else None) for k in METRICS},
                          probes=sum(sum(t.endswith("::I") for _,t in s["requests"]) for s in these),
                          final_closure={q:sum(list(v["checkpoints"]["3600"].values()).count(q) for v in these) for q in ("NA","PV")})
    pairs={candidate:{ref:estimates(rows,candidate,ref,cfg,family,shared)
            for ref in ("B_COST","V_COST")} for candidate in ("MAIN","HOT")}
    return dict(n=len(rows),by_role=totals,pairs=pairs)


def cumulative(lock,fit):
    baseline=mean(s["L"] for s in fit["MAIN-root"].values())
    curves={}
    for track in TRACKS:
        train=lock["tracks"][track]
        points=[dict(round=0,paid_calls=36,delta_L=mean(x["L"] for x in fit[track+"-root"].values())-baseline,
                     label=track+"-root")]
        ledger=[]
        for epoch in train["history"]:
            i=epoch["round"]
            labels=state_at(i)["feedback"][track]["labels"]
            scores={k:{"label":labels[k],**v} for k,v in epoch.get("scores",{}).items()}
            used=sum(len(items) for name,items in fit.items()
                     if name==track+"-root" or name.startswith(track+"-r") and int(name.split("-")[1][1:])<=i)
            if epoch["status"]=="PAID_COMPLETE":
                points.append(dict(round=i,paid_calls=used,delta_L=scores[epoch["incumbent"]]["L"]-baseline,
                                   label=labels[epoch["incumbent"]]))
            ledger.append(dict(round=i,paid_calls=used,selected=epoch["incumbent"],previous=epoch.get("previous"),scores=scores,status=epoch["status"]))
        curves[track]=dict(points=points,rounds=ledger)
    return curves


def main():
    from readback import failure_counts

    verify_sources()
    design,space,u=settings()
    manifest=cases()
    verify_bundles(learned=True)
    audit=identity_audit(manifest)
    locked=read(ACT/"locked.json")
    require(locked["source"]==sha(LOCK) and locked["U"]==sha(PK/"U.json"),"locked parameter and U provenance")
    scored=set();inventory=[];rows=[]
    fit={}
    for path in sorted((ACT/"positions").glob("*")):
        owner=path.name
        if owner.split("-")[0] in TRACKS and "-" in owner:
            fit[owner]={}
            for key in manifest["order"]["FIT"]:
                value,_,r=read_score(owner,key,manifest,scored,verify_raw=True)
                inventory.append(r)
                if value is not None:
                    fit[owner][key]={k:value[k] for k in METRICS}
    for key in manifest["order"]["DEV"]:
        condition=read_case(key,manifest)
        arms={};meta={}
        for label in design["evaluation_roles"]:
            value,raw,r=read_score(label,key,manifest,scored,verify_raw=True)
            inventory.append(r)
            if value is not None:
                arms[label]=value
                meta[label]=raw
        failures={}
        for label,no in (("V_COST","V_COST_NOPROBE"),("HOT","HOT_NOPROBE")):
            view={k:v for k,v in arms.items() if k in ("P","B")}
            if label in arms:view["V_COST"]=arms[label]
            if no in arms:view["V_COST_NOPROBE"]=arms[no]
            failures[label]=failure_counts(condition,view,meta.get(label))
        rows.append(dict(key=key,family=manifest["conditions"][key]["family"],duration=condition["maintenance"]["exposure_s"],
                         arms={label:{k:v[k] for k in (*METRICS,"checkpoints","first","requests")} for label,v in arms.items()},
                         failures=failures))
    require(len(rows)==48 and len(inventory)<=design["paid_arm_budget"],"frozen science denominators")
    overall=metrics(rows,design)
    main=overall["pairs"]["MAIN"]
    b,v=main["B_COST"],main["V_COST"]
    gate=None if b["available"]!=48 or v["available"]!=48 else b["metrics"]["L"]["hi"]<design["gates"]["B_cost_upper_strictly_below_s"] and v["metrics"]["L"]["hi"]<=design["gates"]["V_upper_at_most_s"]
    families={f:metrics([r for r in rows if r["family"]==f],design,"family/"+f) for f in sorted({r["family"] for r in rows})}
    kinds=("missed_preventive_window","measurement_vs_action_need","measurement_delayed_necessary_action")
    failure_matrix={}
    for label in ("V_COST","HOT"):
        failure_matrix[label]={}
        for key in kinds:
            values=[r["failures"][label][key] for r in rows]
            failure_matrix[label][key]=dict(count=values.count(True),denominator=sum(isinstance(v,bool) for v in values),
                                           unresolved=values.count(None),not_applicable=values.count("NOT_APPLICABLE"))
    curves=cumulative(locked,fit)
    final=dict(schema="T5-ordinary-improvement-development-v1",job=job(),overall=overall,families=families,development_gate=gate,
               failure_matrix=failure_matrix,curves=curves,rows=rows,charged_positions=inventory,
               locked={k:v for k,v in locked.items()},identity_audit=audit,paid_arm_count=len(scored),
               H2_accessed=False,source=sha(LOCK),input_manifest=os.environ["T5_INPUT_SHA"])
    write_gz(ACT/"results.json.gz",final)
    write(ACT/"headline.json",{k:v for k,v in final.items() if k not in ("rows","charged_positions","locked")})
    runner="/share/home/renly/miniconda3/envs/flux/bin/python"
    plot=subprocess.run([runner,"-B",str(PK/"plot_learning.py"),str(ACT/"headline.json"),str(ACT)],check=False,
                        env=dict(os.environ,MPLBACKEND="Agg",MPLCONFIGDIR=str(ACT/"mpl")))
    print("DEV gate",gate,"scored",len(scored),"figure code",plot.returncode,flush=True)


if __name__=="__main__":
    main()
