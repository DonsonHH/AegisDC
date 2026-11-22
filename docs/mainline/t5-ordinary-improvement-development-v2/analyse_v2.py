"""Read the registered saved positions and estimate the prespecified development contrasts."""
from collections import Counter
import gzip
import importlib.util
import json
import os
from pathlib import Path
import sys

import numpy as np

from context_v2 import (ACT, LOCK, METRICS, PK, ROOT, T4B, case_at, config, digest, job, need,
                        operative, panel, put, put_gz, read, sha, verify_sources)
from positions import binding, dev_labels
from aegis_improvement_v2.search import identifiers


def t4b_analysis():
    location=T4B/"readback.py"
    need(sha(location)==read(LOCK)["files"][location.relative_to(ROOT).as_posix()],"frozen analysis source")
    spec=importlib.util.spec_from_file_location("accepted_t4b_analysis",location)
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


def duplicate_audit(design, manifest):
    precedent={}
    for file,count in zip(design["filters"]["public_identity_corpora"],(144,84),strict=True):
        path=ROOT/file
        committed=read(path)
        need(sha(path)==manifest["public_exclusion_registers"][file] and len(committed["conditions"])==count,"previous complete public identities")
        precedent[file]=(count,{x["sha256"] for x in committed["conditions"].values()},
                                {x["operative_sha256"] for x in committed["conditions"].values()})
    seen={}
    checks={}
    for split,keys in manifest["order"].items():
        full=set();effective=set()
        for key in keys:
            case=case_at(key,manifest)
            info=manifest["cases"][key]
            full.add(info["sha256"])
            actual=operative(case)
            need(actual==info["operative_sha256"],"actual condition digest")
            effective.add(actual)
        need(len(full)==len(effective)==len(keys),"no repeated condition within a panel")
        seen[split]=(full,effective)
        checks[split]=[dict(previous=file,previous_conditions=n,full=len(full&f),operative=len(effective&op))
                       for file,(n,f,op) in precedent.items()]
    cross=dict(full=len(seen["FIT"][0]&seen["DEV"][0]),operative=len(seen["FIT"][1]&seen["DEV"][1]))
    need(not any(c[k] for v in checks.values() for c in v for k in ("full","operative")) and not any(cross.values()),"exact disjoint identities")
    return dict(previous=checks,FIT_DEV=cross,rejected=len(manifest["rejected"]))


def load_position(path, entry, manifest, case, registry, read_metadata):
    info=manifest["cases"][entry["key"]]
    label,key=entry["label"],entry["key"]
    need(path==ACT/"positions"/label/key and entry["source"]==sha(LOCK)
         and entry["input"]==info["sha256"] and entry["input_manifest"]==os.environ["T5V2_INPUTS"]
         and entry["pid"]!=entry["worker_pid"] and entry["charged"] is True,"actual position identity")
    declared=registry[entry["group"]]
    need(entry["job"]==declared["job"] and [label,key] in declared["positions"],"registered paid position")
    score_file=path/"score.json"
    if not score_file.is_file():
        return None,None,dict(entry,status="NO_SCORE")
    saved=read(score_file)
    raw=path/"native.jsonl.gz"
    vector,_=binding(label)
    need(saved["entry"]==entry and sha(raw)==saved["raw_sha256"] and saved["clocks"]==61
         and entry["descriptor"]==(digest(vector) if vector else None),"original bytes and served descriptor")
    record=dict(entry,status="SCORED",score_sha256=sha(score_file),actual_sha256=saved["raw_sha256"])
    with gzip.open(raw,"rt",encoding="utf8") as stream:
        data=json.loads(next(stream))["metadata"]
    native=case["native"]
    need(data["source_config"]==native["scenario"] and data["inputs"]["dispatch_program"]==native["dispatch_program"]
         and data["inputs"]["boundary_events"]==sorted(native["boundary_events"],key=lambda q:q["time_s"])
         and data["t3_received_attachment_sha256"]==digest(case["attachment"])
         and data["v3_received_maintenance"]==case["maintenance"],"verified physical and evidence arguments")
    props=data["v3_proposals"]
    frames=data["policy_public_decisions"]
    need([p["view"]["time"] for p in frames]==list(range(0,3601,60))
         and all(digest(p["view"])==q["view"] for p,q in zip(frames,props,strict=True))
         and digest([[d["at"],d["view"],d["proposal"]] for d in props])==saved["public_transcript"],
         "61 witnessed decisions in original")
    record["actions_sha256"]=digest([f["decision"]["request"] for f in frames])
    return saved,data if read_metadata else None,record


def panel_rows(manifest):
    registry={r["name"]:r for r in (read(f) for f in (ACT/"registrations").glob("*.json"))}
    lookup={(label,key):job for job in registry.values() for label,key in job["positions"]}
    need(len(lookup)==sum(len(job["positions"]) for job in registry.values()),"no replay in scientific groups")
    saved={}
    metadata={}
    inventory=[]
    cases={key:case_at(key,manifest) for key in manifest["cases"]}
    for (label,key),owner in sorted(lookup.items()):
        path=ACT/"positions"/label/key
        if (path/"entry.json").is_file():
            result,meta,record=load_position(path,read(path/"entry.json"),manifest,cases[key],registry,key.startswith("dev-"))
            if result is not None:
                saved[label,key]=result
                if meta is not None:
                    metadata[label,key]=meta
            inventory.append(record)
        else:
            inventory.append(dict(label=label,key=key,job=owner["job"],group=owner["name"],charged=False,status="NO_FACILITY_ENTRY"))
    return saved,metadata,inventory,cases


def read_replays(u):
    stages=[]
    for epoch in range(1,u["rounds"]+1):
        proposed=read(ACT/"search"/f"proposals-{epoch}.json")
        receipts=read(ACT/"search"/f"state-{epoch}.json")["receipts"]
        rows={}
        for arm in identifiers():
            evidence=proposed["replay"].get(arm)
            if not evidence:
                rows[arm]=dict(discarded=0,drawn=0,distinct=0,paid_slots=0,paid=0,unallocated=0,status="PEER_OR_SEARCH_TERMINAL")
                continue
            if arm in receipts:
                paid=receipts[arm]["charged_new"]
                need(sha(ACT/"paid-feedback"/receipts[arm]["file"])==receipts[arm]["sha256"],"paid feedback unchanged")
            else:
                paid=0
            need(paid<=evidence["paid_slots"]*12,"bounded per-seed commitments")
            rows[arm]=dict(discarded=evidence["discarded"],drawn=len(evidence["draws"]),
                distinct=evidence["proposed"],paid_slots=evidence["paid_slots"],paid=paid,
                unallocated=evidence["unallocated_unique"],status="EXHAUSTED" if evidence["dedup_exhausted"] else "COMPLETE")
        stages.append(dict(epoch=epoch,rows=rows,source_sha256=sha(ACT/"search"/f"proposals-{epoch}.json"),
                           computed_vectors=proposed["computed_vectors"]))
    return stages


def comparisons(rows,design,aux):
    setting=design["bootstrap"]
    ids=aux.samples(rows,setting["seed_prefix"],"overall",setting["repetitions"])
    values={label:np.array([arm["arms"][label]["L"] for arm in rows]) for label in dev_labels()
            if all(label in r["arms"] for r in rows)}
    boot={label:v[ids].mean(axis=1) for label,v in values.items()}
    means={label:float(v.mean()) for label,v in values.items()}
    result={}
    for track in ("MAIN","HOT"):
        per={method:[f"{track}-{method}-{seed}" for seed in (1,2,3)] for method in ("U","R")}
        refs=("B_COST","V_COST","M" if track=="MAIN" else "M_HOT")
        by_search={}
        for method,labels in per.items():
            score=[means.get(label) for label in labels]
            by_search[method]=dict(means=score,n_seeds=len(score),range=None)
            if all(v is not None for v in score):
                by_search[method].update(median=float(np.median(score)),range=[min(score),max(score)])
        estimate={}
        for method,labels in per.items():
            targets = (*refs,"R") if method=="U" else refs
            block={}
            complete=all(x in boot for x in labels)
            for reference in targets:
                target=per["R"] if reference=="R" else [reference]
                if not complete or not all(x in boot for x in target):
                    block[reference]=None
                    continue
                against=np.median(np.stack([boot[t] for t in target]),axis=0)
                central=float(np.median([means[x] for x in labels])-np.median([means[t] for t in target]))
                distribution=np.median(np.stack([boot[x] for x in labels]),axis=0)-against
                lo,hi=np.percentile(distribution,setting["interval_percentiles"],method=setting["quantile_interpolation"])
                block[reference]=dict(mean=central,lo=float(lo),hi=float(hi),conditions=len(rows))
            estimate[method]=block
        seed_ranges={}
        for method,labels in per.items():
            seed_ranges[method]={}
            for reference in (*refs,"R") if method=="U" else refs:
                controls=per["R"] if reference=="R" else [reference]*3
                diff=[means[a]-means[b] if a in means and b in means else None for a,b in zip(labels,controls,strict=True)]
                seed_ranges[method][reference]=dict(seeds=diff,range=[min(diff),max(diff)] if None not in diff else None)
        result[track]=dict(search=by_search,estimates=estimate,seed_effects=seed_ranges)
    return result,means


def main():
    verify_sources()
    need(np.__version__=="2.2.6","pinned NumPy")
    design,_,u=config()
    manifest=panel()
    overlap=duplicate_audit(design,manifest)
    locked=read(ACT/"locked.json")
    need(locked["inputs"]==os.environ["T5V2_INPUTS"] and locked["source"]==sha(LOCK)
         and locked["final_round"]==u["rounds"] and set(locked["arms"])==set(identifiers()),"all identical locks before scoring")
    saved,meta,positions,cases=panel_rows(manifest)
    aux=t4b_analysis()
    failures={}
    rows=[]
    for key in manifest["order"]["DEV"]:
        row={label:saved[label,key] for label in dev_labels() if (label,key) in saved}
        for label in ["V_COST",*(a for a in identifiers() if a.startswith("HOT-"))]:
            control=label+"-NP" if label!="V_COST" else "V_COST_NOPROBE"
            pair={k:v for k,v in (("V_COST",row.get(label)),("B",row.get("B")),("V_COST_NOPROBE",row.get(control))) if v is not None}
            counts=aux.failure_counts(cases[key],pair,meta.get((label,key)))
            failures.setdefault(label,{})[key]=counts
        rows.append(dict(key=key,family=manifest["cases"][key]["family"],arms={a:{k:b[k] for k in METRICS} for a,b in row.items()}))
    summary,means=comparisons(rows,design,aux)
    selected=summary["MAIN"]["estimates"]["U"]
    replay=read_replays(u)
    paired_budget={}
    for track in ("MAIN","HOT"):
        for seed in (1,2,3):
            labels=[f"{track}-{method}-{seed}" for method in ("U","R")]
            totals=[sum(stage["rows"][a]["paid"] for stage in replay) for a in labels]
            paired_budget[f"{track}-{seed}"]=dict(U=totals[0],R=totals[1],equal=totals[0]==totals[1])
    required_fit=all(lock["status"]!="INVALID_FIT_FEEDBACK" for lock in locked["arms"].values())
    balanced=all(v["equal"] for v in paired_budget.values())
    gate=None if not required_fit or not balanced or not selected["R"] or not selected["B_COST"] else (
        selected["R"]["hi"]<design["main_gate"]["upper_vs_R_strictly_below"] and
        selected["B_COST"]["hi"]<design["main_gate"]["upper_vs_B_COST_strictly_below"])
    kinds=("missed_preventive_window","measurement_vs_action_need","measurement_delayed_necessary_action")
    residual={}
    for label,values in failures.items():
        residual[label]={k:dict(count=sum(v[k] is True for v in values.values()),
                                denominator=sum(type(v[k]) is bool for v in values.values()),
                                unresolved=sum(v[k] is None for v in values.values())) for k in kinds}
    full=dict(schema="T5-v2-development-scientific-readback",job=job(),locked_sha256=sha(ACT/"locked.json"),
              input_sha256=sha(ACT/"inputs.json"),development_gate=gate,comparisons=summary,DEV_means=means,residual=residual,
              replay=replay,fit_call_budget=paired_budget,overlap=overlap,position_status=dict(Counter(x["status"] for x in positions)),
              H2_accessed=False,H2_derived=0,final_comparisons=0,references="M and M_HOT are manual evaluation arms")
    put_gz(ACT/"results.json.gz",dict(full,rows=rows,positions=positions,failure_evidence=failures))
    put(ACT/"headline.json",full)
    print("DEV gate",gate,"position status",full["position_status"],"paired FIT budget",paired_budget,flush=True)


if __name__=="__main__":
    main()
