"""Audit-only enumeration of the frozen input law; no policy, score or facility invocation."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
FAMILIES = ("LONDON", "NETHERLANDS")
FEATURES = ("external_fault_count", "fault_time_histogram", "opportunity_histogram", "service_joint", "work_joint")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def compact(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def hash_obj(v):
    return hashlib.sha256(compact(v)).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def file_hash(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write(path, obj):
    with path.open("xb") as f:
        f.write(compact(obj)+b"\n")
        f.flush()
        os.fsync(f.fileno())


def original_modules(base):
    paths = sys.path.copy()
    main = base / "docs/mainline"
    t4c, t3, t2 = (main / k for k in ("t4c-action-cost-v3","t3-prior-information-v2","t2-minute-facility-v1"))
    sys.path.insert(0, str(t4c))
    import inputs_v3
    # The legacy constants also name other shared environments. Use the exported
    # pinned modules only, including the idle public admission arithmetic.
    sys.path[:] = [str(base/"src"), str(t3), str(t2/"production"), str(t2), str(t4c), *paths]
    import public_work
    from aegis_action_cost.permit import Gate
    from aegis_dc import joint_resources
    for name in ("inputs_v3","generator_v2","generator","facility_inputs","public_work","common","common_v3",
                 "aegis_action_cost.permit","aegis_dc.joint_resources"):
        need(Path(sys.modules[name].__file__).resolve().is_relative_to(base), "wrong generator source: "+name)
    return inputs_v3, public_work, Gate


def ordered_profiles(seed, fam, catalog):
    def key(profile):
        return (hash_obj(["AegisDC/T8/r0/profile/v1",seed,fam,profile]),profile)
    return sorted(catalog, key=key)


def schedule(pub, profile, delta, second):
    e0,e1,s0,s1=profile
    shifts=pub["workforce"]["shifts"]
    shifts["worker_electrical"]=[60*e0,60*e1]
    shifts[second]=[60*s0,60*s1]
    for subject in pub["subjects"]:
        lo,hi=subject["write_window"]
        if hi-lo>=180:
            subject["write_window"]=[lo,min(3600,max(lo+60,hi+60*delta))]
    return (*shifts["worker_electrical"],*shifts[second])


def identity(case):
    native=case["native"]
    prog=native["dispatch_program"]
    effective={k:case[k] for k in ("native","attachment","maintenance")}
    channel=[]
    for row in prog["channel"]:
        if row["kind"]=="order":
            need(row["value"]=="OPEN/MAINT-"+str(case["maintenance"]["exposure_s"]), "signed order mismatch")
            channel.append(dict(row,value="OPEN"))
        else:
            channel.append(row)
    common={"native":dict(native,dispatch_program=dict(prog,channel=channel)), "attachment":case["attachment"]}
    return (hashlib.sha256(compact(case)+b"\n").hexdigest(),hash_obj(effective),hash_obj(common))


def structural_features(case,fam,public_work,gate_type):
    cfg=case["attachment"]; prog=case["native"]["dispatch_program"]; pub=prog["public"]
    target="LB" if fam=="LONDON" else "NR"
    subject=next(s for s in pub["subjects"] if s["id"]==target)
    gate=gate_type(case["maintenance"]["recovery"])
    cost=public_work.duration(pub,subject,subject["start"])
    legal=[];pre=[]
    fault=cfg["fault_at"]
    for t in pub["clock"]:
        if not subject["write_window"][0]<=t<subject["write_window"][1]:
            continue
        view={"time":t,"records":[r for r in prog["channel"] if r["arrived"]<=t],
              "work":[],"paid":[],"writes":[],"fixed":[],"issued":[]}
        admitted,_=gate.admit(pub,view,subject,"A")
        if admitted:
            legal.append(t)
            if fault is not None and admitted["planned_end"]<fault:
                pre.append(t)
    fault_key=-1 if fault is None else fault
    window=(len(legal),legal[0] if legal else -1,legal[-1] if legal else -1)
    timely=(len(pre),pre[-1] if pre else -1) if fault is not None else (-1,-1)
    npriors=len({r["origin"] for r in prog["channel"] if r["kind"]=="prior" and
                 r["copied_from"] is None and fault is not None and r["arrived"]<fault})
    return {
        "external_fault_count": int(fault is not None), "fault_time_histogram":(fault_key,),
        "opportunity_histogram":timely,
        "service_joint":(fault_key,-1 if fault is None else cfg["restore_at"]-fault,case["maintenance"]["exposure_s"],*timely,npriors),
        "work_joint":(*window,cost if cost is not None else -1),
    }


def histogram(values):
    return [[k,count] for k,count in sorted(Counter(values).items())]


def structural_signature(histograms):
    fault = histograms["fault_time_histogram"]
    timely = histograms["opportunity_histogram"]
    work = histograms["work_joint"]
    return (sum(n for (t,),n in fault if t>=0), sum(n for (t,),n in fault if t==1500),
            sum(n for (count,_),n in timely if count>0), sum(n for (count,_),n in timely if 1<=count<=3),
            sum(n for (count,_,_,_),n in work if count==0))


def signature_stats(counts):
    n=sum(counts.values()); squares=sum(v*v for v in counts.values())
    return {"blocks":n,"unique":len(counts),"max_multiplicity":max(counts.values()),"max_share":max(counts.values())/n,
            "matching_pairs":(squares-n)//2,"all_pairs":n*(n-1)//2,
            "pair_collision_probability":(squares-n)/(n*(n-1)) if n>1 else None,
            "inverse_simpson":n*n/squares}


def family_run(args):
    family, lane, base, r0, output, spec=args
    os.sched_setaffinity(0,{lane})
    gen,work,Gate=original_modules(base); templates=gen.templates()
    law=read(r0/"panel-law.json"); rnd=read(r0/"seed-registration.json")
    reg=read(r0/"registration.json")["randomization"]
    variation=law["operative_variations"]; groups=spec["schedule_groups"]
    new_seed=hashlib.sha256(spec["audit_seed_tag"].encode()+b"\0"+bytes.fromhex(rnd["fresh_public_development_root_hex"])).hexdigest()
    need(new_seed!=rnd["fit_seed_hex"], "audit namespace collision")
    start=range(variation["start_ticks_inclusive"][0],variation["start_ticks_inclusive"][1]+1)
    end=range(variation["end_ticks_inclusive"][0],variation["end_ticks_inclusive"][1]+1)
    catalog=list(itertools.product(start,end,start,end))
    reserved=set(ordered_profiles(rnd["fit_seed_hex"],family,catalog)[:len(groups)*reg["fit_blocks_per_family"]])
    ordered=ordered_profiles(new_seed,family,(x for x in catalog if x not in reserved))
    nblocks=len(ordered)//len(groups); idx=4+FAMILIES.index(family)
    seen=[set(),set(),set()]; profile_blocks={}; excluded_blocks=set()
    block_rows=[]; chain=hashlib.sha256(); expected_cells=set(gen.incident_case.__globals__["CELLS"])
    with gzip.open(output/(family+"-row-identities.jsonl.gz"),"xb",compresslevel=3) as raw:
        for block in range(nblocks):
            profiles=dict(zip(groups,ordered[block*len(groups):(block+1)*len(groups)],strict=True))
            byfeature={f:[] for f in FEATURES}
            maintenance=Counter(); cells=set(); seen_tuples=Counter()
            for slot in range(12):
                draw=12*block+slot
                case=gen.condition(int(new_seed,16),idx,draw,templates); ev=case["evaluation"]
                need((ev["family"],ev["draw"],case["attachment"]["kind"])==(family,draw,family), "original draw")
                cell=ev["cell"];token="TWIN_PAIR" if cell in ("TWIN_A","TWIN_B") else cell
                profile=profiles[token]
                delta=min(variation["permit_end_offsets_ticks"],key=lambda j:(hash_obj(["AegisDC/T8/r0/window/v1",new_seed,family,[profile,j]]),j))
                pub=case["native"]["dispatch_program"]["public"]
                observed=schedule(pub,profile,delta,variation["second_worker"][family])
                need(observed==tuple(60*x for x in profile), "operative shift identity")
                need(profile_blocks.setdefault(observed,block)==block,"profile reused across blocks")
                seen_tuples[observed]+=1;maintenance[case["maintenance"]["exposure_s"]]+=1;cells.add(cell)
                ids=identity(case)
                if any(v in bucket for v,bucket in zip(ids,seen)):
                    excluded_blocks.add(block)
                for v,bucket in zip(ids,seen):bucket.add(v)
                row=compact([block,slot,profile,ids])+b"\n"
                raw.write(row);chain.update(row)
                features=structural_features(case,family,work,Gate)
                for f,v in features.items():byfeature[f].append(v)
            need(cells==expected_cells and maintenance=={0:4,600:4,1200:4} and
                 sorted(seen_tuples.values())==[1]*10+[2], "frozen cell/maintenance/profile quota")
            sig={f:histogram(vals) for f,vals in byfeature.items()}
            block_rows.append({"block":block,"cluster_signature":structural_signature(sig),"histograms":sig})
    # No block can match a different block on any identity: all projections retain the two shifts.
    need(len(profile_blocks)==nblocks*11,"injective block workforce profiles")
    public_gz=output/(family+"-audit-blocks.json.gz")
    with public_gz.open("xb") as f:
        f.write(gzip.compress(compact(block_rows)+b"\n",compresslevel=6,mtime=0))
    historic=sum(sum(e["counts"]) for e in law["historical_catalogue"]["entries"])
    usable=nblocks-len(excluded_blocks)
    def diversity(rows):
        summary={f:signature_stats(Counter(hash_obj(x["histograms"][f]) for x in rows)) for f in FEATURES}
        summary["primary_cluster"]=signature_stats(Counter(x["cluster_signature"] for x in rows))
        return summary
    return {"family":family,"catalog_profiles":len(catalog),"fit_profiles_reserved":len(reserved),
            "unused_profile_tail":len(ordered)%11,"audit_blocks":nblocks,"audit_rows":12*nblocks,
            "distinct_identities":dict(zip(("full","operative","common_core"),map(len,seen))),
            "blocks_with_internal_identity_repeats":sorted(excluded_blocks),"profile_block_invariant":True,
            "historical_gross_debit":historic,"capacity_upper_blocks":usable,"guaranteed_blocks":max(0,usable-historic),
            "guaranteed_rows":12*max(0,usable-historic),"rows_upper":12*usable,
            "all":diversity(block_rows),"first_registered_size":diversity(block_rows[:reg["dev_blocks_per_family"]]),
            "ordered_audit_identity_chain_sha256":chain.hexdigest(),"block_file_sha256":file_hash(public_gz),
            "private_row_file_sha256":file_hash(output/(family+"-row-identities.jsonl.gz"))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();bundle=a.bundle.resolve();output=a.output.resolve()
    need(os.environ.get("SLURM_JOB_ID") and int(os.environ["SLURM_CPUS_PER_TASK"])==2, "two allocated audit lanes")
    lock=read(bundle/"r1/audit-sources.json")
    need(file_hash(bundle/"r1/audit-sources.json")==os.environ["T8_AUDIT_SHA"],"registered source manifest")
    for path,h in lock["files_sha256"].items():need(file_hash(bundle/path)==h,"pinned audit source: "+path)
    r0=bundle/"r0";spec=read(bundle/"r1/audit-plan.json")
    need(file_hash(r0/"registration.json")==spec["registration_sha256"],"r0 identity")
    output.mkdir();job=os.environ["SLURM_JOB_ID"]
    write(output/"entry.json",{"job":job,"source":os.environ["T8_AUDIT_SHA"],"purpose":"AUDIT_ONLY","facility_calls":0})
    lanes=sorted(os.sched_getaffinity(0))[:2];need(len(lanes)==2,"two CPU affinity lanes")
    with ProcessPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(family_run,[(f,c,bundle/"base",r0,output,spec) for f,c in zip(FAMILIES,lanes)]))
    result={"job":job,"source_sha256":os.environ["T8_AUDIT_SHA"],"families":results,"facility_calls":0,
            "policy_decisions":0,"scores":0,"FIT_conditions":0,"DEV_conditions":0,"H2_access":0,"H3_access":0,
            "official_overlap_queries":0,"audit_condition_calls":sum(r["audit_rows"] for r in results)}
    write(output/"capacity.json",result)
    print("AUDIT COMPLETE",job,[(s["family"],s["audit_rows"],s["guaranteed_rows"]) for s in results],flush=True)


if __name__=="__main__":
    main()
