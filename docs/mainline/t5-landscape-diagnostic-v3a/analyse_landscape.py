"""Reconcile saved originals, certify each oracle and estimate the cross-half landscape."""
from collections import Counter
import gzip
import json
import os
from statistics import mean
import subprocess

import numpy as np
from landscape import (
    ACT, EPS, LOCK, PK, ROOT, batches, binding, case_at, check, check_source, config, digest,
    job, manifest, old_identities, operative, read, role_list, seed_bytes, sha, stream_int, verify_workers, write, write_gz,
)
from statistics_v3a import curves, selected_subsets, spearman, verdict
from aegis_cost_baseline.rule import operative_view


def audit_cases(m,cfg):
    previous=old_identities(cfg)
    current={};complete=set();operations=set()
    for key in m["order"]:
        case=case_at(key,m);info=m["conditions"][key];op=operative(case)
        check(op==info["operative_sha256"] and info["family"]==case["evaluation"]["family"],"fresh condition identity")
        complete.add(info["sha256"]);operations.add(op);current[key]=case
    halves={h:[m["conditions"][k] for k in m["order"] if m["conditions"][k]["half"]==h] for h in cfg["halves"]}
    overlap={kind:len({x[kind] for x in halves["A"]}&{x[kind] for x in halves["B"]}) for kind in ("sha256","operative_sha256")}
    audit={name:dict(prior_conditions=cfg["reference_inputs"][name]["n"],full=len(complete&full),operative=len(operations&op))
           for name,(full,op) in previous.items()}
    check(len(complete)==len(operations)==36 and all(len(half)==18 for half in halves.values()) and not any(overlap.values())
          and not any(r["full"] or r["operative"] for r in audit.values()),"published disjoint diagnostic panel")
    return current,dict(previous=audit,A_B=overlap,self_duplicates=0,rejected_inputs=len(m["rejected_input_identities"]))


def audit_score(label,key,case,m,reg,worker_ids):
    folder=ACT/"positions"/label/key
    marker=folder/"native-entry.json";path=folder/"score.json";raw=folder/"original.jsonl.gz"
    base=dict(label=label,key=key,job=reg["job"] if reg else None,group=reg["name"] if reg else None,
              entered=marker.is_file(),status="UNSUBMITTED" if reg is None else "NO_ENTRY")
    if not marker.is_file():
        return None,base
    e=read(marker)
    base.update(status="ENTERED_NO_VALID_SCORE",entry_sha256=sha(marker))
    if not path.is_file():
        if raw.is_file():base["raw_sha256"]=sha(raw)
        return None,base
    try:
        s=read(path)
        check(reg is not None and s["entry"]==e and [label,key] in reg["slots"] and e["job"]==reg["job"]
              and e["input"]==m["conditions"][key]["sha256"] and e["panel"]==os.environ["V3A_PANEL"] and e["source"]==sha(LOCK),"entry binding")
        descriptor,manual=binding(label,m)
        identity=worker_ids["manual" if manual else "learned"] if descriptor is not None else worker_ids.get(label)
        check(e["worker_bundle"]==identity and e["vector_sha256"]==(digest(descriptor) if descriptor else None),"policy and vector")
        check(sha(raw)==s["raw"],"actual raw bytes")
        with gzip.open(raw,"rt",encoding="utf8") as fp:meta=json.loads(next(fp))["metadata"]
        native=case["native"]
        check(meta["source_config"]==native["scenario"] and meta["inputs"]["dispatch_program"]==native["dispatch_program"]
              and meta["inputs"]["boundary_events"]==sorted(native["boundary_events"],key=lambda x:x["time_s"])
              and meta["t3_received_attachment_sha256"]==digest(case["attachment"]) and meta["v3_received_maintenance"]==case["maintenance"]
              and not meta["t3_unpurchased_evaluator_only"],"physical and public input binding")
        dec=meta["policy_public_decisions"];props=meta["v3_proposals"]
        check([d["view"]["time"] for d in dec]==list(range(0,3601,60)) and len(props)==61 and
              all(digest(d["view"])==q["view"] for d,q in zip(dec,props,strict=True)),"public decision clock")
        if label!="ORACLE":
            check(e["worker_pid"]!=e["pid"] and digest([[q["at"],q["view"],q["proposal"]] for q in props])==s["proposal"],"frozen worker IPC")
        if label=="B_COST":
            messages=[]
            for d,prop in zip(dec,props,strict=True):
                check(prop["external_refusal"] is None,"baseline gate")
                reply={k:v for k,v in d["decision"].items() if k!="certificates"}
                messages.append([prop["at"],digest(operative_view(d["view"])),digest(reply)])
            check(digest(messages)==s["worker_ipc"],"filtered baseline")
        check(all(abs(a-b)<=EPS for a,b in zip((s["L"],s["U"]),s["integral_balances"],strict=True)) and s["clocks"]==61,
              "two independent service accounts")
    except (OSError,KeyError,ValueError,TypeError) as error:
        return None,dict(base,status="INVALID_RECORD",error=str(error))
    return s,dict(base,status="SCORED",raw_sha256=s["raw"],score_sha256=sha(path),worker=e["worker_pid"],pid=e["pid"],
                  descriptor=e["vector_sha256"],transcript=s["proposal"])


def minimum(case,scores):
    oracle=scores.get("ORACLE")
    if oracle is None:
        return dict(status="UNRESOLVED",certified_min=None,reason="no valid oracle return")
    cert=dict(oracle["oracle"])
    if cert.get("lower") is None and not cert.get("error") and not cert.get("plan") and "P" in scores:
        native=case["native"];params={r["id"]:r["value"] for r in native["scenario"]["parameters"]}
        targets=("network_service_capacity","filter_resistance_multiplier")
        structural=(case["evaluation"]["family"]=="RESERVE_TRANSFER" and all(params[k]==1 for k in targets)
                    and not any(e["parameter_id"] in targets for e in native["boundary_events"]))
        other=scores["P"]
        if structural and not oracle["requests"] and not other["requests"] and oracle["curve"]==other["curve"]:
            cert.update(status="ATTAINED",certified_min=other["L"],lower=other["L"],identity_proof=True,
                        P_raw_sha256=other["raw"],oracle_raw_sha256=oracle["raw"])
    lower=cert["certified_min"]
    if lower is not None and any(q["L"]<lower-EPS for q in scores.values()):
        cert.update(status="UNRESOLVED",certified_min=None,reason="lawful saved arm contradicts putative lower bound")
    return cert


def average(values):
    return mean(values) if values and all(v is not None for v in values) else None


def gaps(rows,labels):
    output={}
    minima=[r["minimum"]["certified_min"] for r in rows]
    oracle=average(minima)
    for label in labels:
        vals=[r["arms"].get(label,{}).get("L") for r in rows]
        value=average(vals)
        output[label]=dict(planned=len(rows),scored=sum(v is not None for v in vals),mean_L=value,
                           valid_gap_pairs=sum(a is not None and b is not None for a,b in zip(vals,minima,strict=True)),
                           mean_gap=None if value is None or oracle is None else value-oracle)
    return output


def main():
    import numpy
    check_source();m=manifest();cfg=config()
    check(numpy.__version__=="2.2.6","pinned scientific numerical environment")
    worker_ids=verify_workers()
    orig,identity=audit_cases(m,cfg)
    all_groups=batches(m,cfg)
    expected={(label,key):(group) for group,lanes in all_groups.items() for lane in lanes for label,key in lane}
    regs={q["name"]:q for q in (read(path) for path in (ACT/"registrations").glob("*.json"))}
    results=[];units=[]
    roles=role_list(cfg);random=cfg["roles"]["random"]
    for key in m["order"]:
        scores={}
        jobs=roles+(["P"] if key in m["identity_only_keys"] else [])
        for label in jobs:
            value,unit=audit_score(label,key,orig[key],m,regs.get(expected[label,key]),worker_ids)
            units.append(unit)
            if value is not None:scores[label]=value
        cert=minimum(orig[key],scores)
        results.append(dict(key=key,half=m["conditions"][key]["half"],family=m["conditions"][key]["family"],
            minimum=cert,arms={role:{k:score[k] for k in ("L","U","person","tool","fee","requests")} for role,score in scores.items()}))
    check(len(units)==len(expected)==2124+len(m["identity_only_keys"]),"all original positions and witnesses")
    overall=gaps(results,roles)
    families={f:gaps([r for r in results if r["family"]==f],roles) for f in cfg["families"]}
    half={k:[r for r in results if r["half"]==k] for k in cfg["halves"]}
    halves={k:gaps(v,roles) for k,v in half.items()}
    baseline={h:halves[h]["B_COST"]["mean_L"] for h in halves}
    oracle={h:average([r["minimum"]["certified_min"] for r in half[h]]) for h in halves}
    attributes=cfg["analysis"]
    valid_random=all(overall[l]["mean_L"] is not None for l in random)
    profile=dict(curves=None,delta_24_minus_6=None,decision="INDETERMINATE")
    transfer=dict(spearman=None,subsets=None)
    structure=dict(pool=48,distribution=None,strictly_below_M=None,fraction=None)
    if valid_random:
        matrix={h:np.asarray([[r["arms"][label]["L"] for r in rows] for label in random]) for h,rows in half.items()}
        mean_a,mean_b=(matrix[k].mean(axis=1) for k in ("A","B"))
        rng=np.random.Generator(np.random.PCG64(stream_int(seed_bytes("curves"),cfg["seeds"]["curves"],"paired-2000-permutations")))
        profile=curves(mean_a,mean_b,baseline,oracle,attributes,rng)
        transfer=dict(spearman=spearman(mean_a,mean_b),subsets=selected_subsets(matrix["A"],mean_b,[r["family"] for r in half["A"]],
                                                                            attributes["subsets_per_family"]))
        vals=np.asarray([overall[k]["mean_L"] for k in random])
        percentiles=attributes["random_quantiles"]
        structure["distribution"]={str(q):float(y) for q,y in zip(percentiles,np.percentile(vals,percentiles,method="linear"))}
        if overall["M"]["mean_L"] is not None:
            count=int(np.sum(vals<overall["M"]["mean_L"]))
            structure.update(strictly_below_M=count,fraction=count/48)
    summary=dict(schema="T5-v3a-landscape-development",job=job(),source=sha(LOCK),panel=os.environ["V3A_PANEL"],overall=overall,
        oracle={k:dict(certified=sum(r["minimum"]["certified_min"] is not None for r in rows),mean=average([r["minimum"]["certified_min"] for r in rows]))
                for k,rows in {"all":results,**half}.items()},unresolved=[r["key"] for r in results if r["minimum"]["certified_min"] is None],
        families=families,halves=halves,landscape=profile,transfer=transfer,structure=structure,identity=identity,
        status=dict(Counter(q["status"] for q in units)),draw_audit=dict(draws=len(m["draws"]),discarded=m["discarded_draws"],accepted=len(random)),
        H2_generated=0,H2_accessed=0,H2_derived=0,ordinary_improver_runs=0,RSI_runs=0)
    write_gz(ACT/"results.json.gz",dict(summary,conditions=results,positions=units))
    write(ACT/"summary.json",summary)
    if profile["curves"] is not None:
        plotting=read(LOCK)["plot_python"]
        check(sha(plotting["path"])==plotting["sha256"],"pinned plotting interpreter")
        subprocess.run([plotting["path"],"-B",str(PK/"plot_landscape.py"),str(ACT/"summary.json"),str(ACT)],
             env=dict(os.environ,MPLBACKEND="Agg",MPLCONFIGDIR=str(ACT/"mpl")),check=True)
    print("branch",profile["decision"],"certified",summary["oracle"]["all"],"position statuses",summary["status"],flush=True)

if __name__=="__main__":main()
