"""Independent saved-data check. No seed file, generator, policy, or simulator is loaded."""

import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
from itertools import combinations_with_replacement, product
import json
from math import factorial, isclose, isfinite, prod, sqrt
from pathlib import Path
import subprocess

from scipy.special import stdtr, stdtrit

from check_ledger import verify as verify_ledger
from render_tables import render
from study import FAMILIES, HERE, KEYS, LEDGERS, ROLES, need, packed, read, sha

ROOT = HERE.parents[3]
REL = HERE.relative_to(ROOT).as_posix()
PRE = HERE / "pre-score"
ENDPOINTS = (("HA","P",False),("HB","ALARM",False),("HC","P",True))


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)


def close(a,b,label):
    if a is None or b is None:
        need(a is b,label)
    else:
        need(isclose(a,b,rel_tol=1e-10,abs_tol=1e-11),label)


def elapsed(s):
    days,sep,tail=s.partition("-")
    return (86400*int(days) if sep else 0)+sum(float(t)*60**i for i,t in enumerate(reversed((tail if sep else days).split(":"))))


def accounting(path, job):
    lines=[l.split("|") for l in path.read_text("ascii").splitlines() if l.strip()]
    rs=[dict(zip(lines[0],r,strict=True)) for r in lines[1:]]
    a=next(x for x in rs if x["JobID"]==job)
    step=next(x for x in rs if x["JobID"]==job+".batch")
    return {"job":job,"state":a["State"],"exit_code":a["ExitCode"],"cpus":int(a["AllocCPUS"]),
            "reserved_cpu_s":int(a["TimelimitRaw"])*60*int(a["AllocCPUS"]),"actual_cpu_s":elapsed(a["TotalCPU"]),
            "elapsed_s":int(a["ElapsedRaw"]),"req_mem":a["ReqMem"],"max_rss":step["MaxRSS"]}


def exact_stratum(groups):
    """Multinomial weighting of unordered resamples, also valid for unequal block sizes."""
    k=len(groups)
    sums=[sum(g) for g in groups]
    sizes=list(map(len,groups))
    first=Fraction(); second=Fraction(); total=0
    for indices in combinations_with_replacement(range(k),k):
        wt=factorial(k)//prod(factorial(c) for c in Counter(indices).values())
        ratio=sum(sums[i] for i in indices)/sum(sizes[i] for i in indices)
        total+=wt; first+=wt*ratio; second+=wt*ratio*ratio
    need(total==k**k,"complete bootstrap measure")
    return k*(second/total-(first/total)**2)/(k-1)


def check_endpoint(record, keys, items, arms, comparator, binary):
    vals={f:[[] for _ in range(5)] for f in FAMILIES}
    missing=[]
    for k in keys:
        r=arms.get(k,{})
        if not all(role in r and r[role]["status"]=="SCORED" and isfinite(r[role]["L"]) and r[role]["L"]>=0
                   for role in ("V_COST",comparator)):
            missing.append(k)
            continue
        v,c=[row["L"] for row in (r["V_COST"],r[comparator])]
        delta=Fraction(int(v>0)-int(c>0)) if binary else Fraction(str(v))-Fraction(str(c))
        vals[items[k]["family"]][items[k]["block"]].append(delta)
    need(record["planned"]==len(keys) and record["valid"]==len(keys)-len(missing) and record["missing_pairs"]==missing,
         "paired denominators")
    by_family=[[group for group in vals[f] if group] for f in FAMILIES]
    if missing or any(not g for g in by_family):
        need(record["estimate"] is None and record["interval_95"] is None,"missing estimate boundary")
        return None
    means=[sum(map(sum,g))/sum(map(len,g)) for g in by_family]
    point=float(sum(means)/2)
    close(record["estimate"],point,"mean contrast")
    for f,m in zip(FAMILIES,means):close(record["family_estimates"][f],float(m),"family contrast")
    df=min(map(len,by_family))-1
    if df<1:
        need(record["interval_95"] is None,"sparse interval")
        return None
    se=sqrt(float(sum(exact_stratum(g) for g in by_family)/4))
    close(record["se"],se,"exact stratified bootstrap variance")
    need(record["df"]==df,"registered degrees of freedom")
    if not se:
        need(record["interval_95"] is None and record["raw_p"] is None,"degenerate interval and p")
        return None
    bound=float(stdtrit(df,0.975))*se
    for actual,expected in zip(record["interval_95"],(point-bound,point+bound)):close(actual,expected,"interval")
    return float(2*stdtr(df,-abs(point/se)))


def check_analysis(a, items, mask, arms):
    pvals={}
    for name,cmp,binary in ENDPOINTS:
        r=a["primary"][name]
        p=check_endpoint(r,KEYS,items,arms,cmp,binary)
        close(r["raw_p"],p,"two-sided p")
        pvals[name]=p if p is not None else 1.
    order=sorted(pvals,key=lambda x:(pvals[x],list(pvals).index(x)))
    for rank,name in enumerate(order):
        adjusted=min(1.,max((3-i)*pvals[k] for i,k in enumerate(order[:rank+1])))
        e=a["primary"][name]
        close(e["holm_p"],adjusted,"Holm adjusted p")
        status=("INDETERMINATE" if e["raw_p"] is None else
                "MET" if adjusted<=0.05 and e["estimate"]<0 and e["interval_95"][1]<0 else "NOT_MET")
        need(e["status"]==status and e["holm_rank"]==rank+1,"registered gate")
    retained=[k for k in KEYS if not mask["by_condition"][k]["exclude_descriptively"]]
    s=a["sensitivity"]
    need((s["retained"],s["excluded"])==(len(retained),120-len(retained)), "sensitivity counts")
    if len(retained)<120:
        need(s["status"]=="DESCRIPTIVE_ONLY","descriptive gate")
        for name,cmp,binary in ENDPOINTS:
            check_endpoint(s["endpoints"][name],retained,items,arms,cmp,binary)
            need(s["endpoints"][name]["raw_p"] is None,"no sensitivity hypothesis test")
    else:
        need(s["status"]=="无需敏感性","zero-overlap disposition")
    worse=[]
    for family in FAMILIES:
        keys=[k for k in KEYS if items[k]["family"]==family]
        cells={k:[] for k in ("P0_V0","P1_V0","P0_V1","P1_V1","missing")}
        for k in keys:
            r=arms.get(k,{})
            label="missing" if "V_COST" not in r or "P" not in r else "P%d_V%d"%(r["P"]["L"]>0,r["V_COST"]["L"]>0)
            cells[label].append(k)
            if "V_COST" in r and "PERIODIC" in r and r["V_COST"]["L"]>r["PERIODIC"]["L"]:
                worse.append({"key":k,"family":family,"V_L":r["V_COST"]["L"],"PERIODIC_L":r["PERIODIC"]["L"],
                              "V_person":r["V_COST"]["person"],"PERIODIC_person":r["PERIODIC"]["person"]})
        need(a["families"][family]["event_pairs"]==cells,"event discordance and condition IDs")
        for role in ROLES:
            rows=[arms[k][role] for k in keys if role in arms.get(k,{})]
            f=a["families"][family]["arms"][role]
            need(f["planned"]==len(keys) and f["scored"]==len(rows) and f["events"]==sum(r["L"]>0 for r in rows),"arm denominator")
            for m in ("L","person"):close(f["mean_"+m],sum(r[m] for r in rows)/len(rows) if rows else None,"arm mean")
            close(f["event_rate"],f["events"]/len(rows) if rows else None,"event proportion")
        for role,table in a["descriptive_pairs"][family].items():
            pairs=[arms[k] for k in keys if role in arms.get(k,{}) and "V_COST" in arms[k]]
            need(table["valid"]==len(pairs),"secondary paired denominator")
            for m in ("L","person"):
                d=[v["V_COST"][m]-v[role][m] for v in pairs]
                close(table[m]["mean_difference"],sum(d)/len(d) if d else None,"secondary paired mean")
                need(table[m]["better_equal_worse"]==[sum(i<0 for i in d),sum(i==0 for i in d),sum(i>0 for i in d)],
                     "secondary paired directions")
    need(a["worse_than_periodic"]==worse,"every strict loss to periodic")
    need(len(a["blocks"])==len(mask["blocks"])==10,"ten original blocks")
    for x,y in zip(a["blocks"],mask["blocks"],strict=True):
        need(all(x[k]==v for k,v in y.items()),"original exclusion denominators")
        keys=[k for k in KEYS if (items[k]["family"],items[k]["block"])==(x["family"],x["block"])]
        need(x["positions_planned"]==5*len(keys) and
             x["missing_by_role"]=={r:[k for k in keys if r not in arms.get(k,{})] for r in ROLES},"per-block missing positions")
        for n,c,_ in ENDPOINTS:
            valid=[k for k in keys if c in arms.get(k,{}) and "V_COST" in arms[k]]
            need(x["primary_pairs"][n]==len(valid) and x["retained_pairs"][n]==len(set(valid)&set(retained)),"block denominators")


def check_mechanisms(m, scores):
    need(m["planned"]==len(m["rows"])==60,"Dutch mechanism denominator")
    for r in m["rows"]:
        d=scores.get(r["key"],{});v=d.get("V_COST",{}).get("dutch_window");b=d.get("B",{}).get("dutch_window")
        if v is None:
            need(r["wait_failure"] is None,"missing V trajectory")
            continue
        if v["fault"] is None:
            need(r["wait_failure"] is False,"no transfer challenge")
            continue
        last=v["legal_NR_ticks"][-1] if v["legal_NR_ticks"] else None
        failure=last is not None and v["tripped"] and v["transfer_loss"]>1e-7 and (v["effective_NR"] is None or v["effective_NR"]>=v["fault"])
        witnessed=None if b is None else failure and b["effective_NR"] is not None and b["effective_NR"]<v["fault"] and not b["tripped"] and v["transfer_loss"]-b["transfer_loss"]>1e-7
        waited=bool(failure and last["actual"]=="WAIT")
        exact=bool(waited and not v["valid_pre_fault_initial_reads"] and any(w["outcome"]=="NO_EFFECT" and w["at"]>=v["fault"] for w in v["later_pump"]))
        need(r["last_legal"]==last and r["wait_failure"]==waited and r["paired_B_witness"]==witnessed and
             r["exact_late_no_effect_without_initial"]==exact and r["later_pump"]==v["later_pump"],"dated failure evidence: "+r["key"])
    for field in ("wait_failure","paired_B_witness","exact_late_no_effect_without_initial"):
        need(m[field]==sum(r.get(field) is True for r in m["rows"]),"mechanism count: "+field)
    need(m["assessable"]==sum(r["wait_failure"] is not None for r in m["rows"])
         and m["B_assessable"]==sum(r["paired_B_witness"] is not None for r in m["rows"])
         and m["wait_with_B_witness"]==sum(r["wait_failure"] is True and r["paired_B_witness"] is True for r in m["rows"]),
         "mechanism coverage")


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--check",action="store_true",required=True)
    p.add_argument("--checkout-bytes",action="store_true");args=p.parse_args()
    o=verify_ledger(PRE);reg=read(HERE.parent/"r1/registration.json");src=read(HERE/"execution.json")
    hand=read(HERE/"handoff.json");need(hand["original_file_opens"]==1 and hand["raw_bytes"]==32 and
         hand["actual_sha256"]==hand["expected_sha256"]==reg["custody"]["sha256"] and hand["matched"],"H3 commitment")
    lock=read(HERE/"score-release.json");freeze=read(PRE/"input-freeze.json")
    author=read(HERE/"author-entry.json")
    need(author["job"]==freeze["job"] and author["execution_revision"]==freeze["execution_revision"]
         and author["consumption"]==1 and author["commitment"]==hand["actual_sha256"],"original one-time consumption")
    need(lock["input_freeze_sha256"]==sha(PRE/"input-freeze.json") and lock["manifest_sha256"]==o["manifest_sha256"]
         and lock["pilot_job"]==freeze["job"],"score release")
    need(subprocess.run(["git","merge-base","--is-ancestor",freeze["execution_revision"],lock["publication_commit"]],cwd=ROOT).returncode==0,
         "execution precedes input publication")
    for name in (*LEDGERS,"input-freeze.json"):
        need((PRE/name).read_bytes()==git("show",lock["publication_commit"]+":"+REL+"/pre-score/"+name),"published before scoring: "+name)
    for name,pin in src["stage_files"].items():
        need(sha(HERE/name)==pin==hashlib.sha256(git("show",freeze["execution_revision"]+":"+REL+"/"+name)).hexdigest(),"execution file: "+name)
    need((HERE/"execution.json").read_bytes()==git("show",freeze["execution_revision"]+":"+REL+"/execution.json"),"executed lock")
    items=read(PRE/"input-manifest.json")["conditions"];private=read(HERE/"originals.json");d=read(HERE/"delivery.json")
    all_arms={};jobs=[];entries=0;native_decisions=0
    for group,ks in (("pilot",KEYS[:1]),("batch",KEYS[1:])):
        term=read(HERE/(group+"-terminal.json"));raw=gzip.decompress((HERE/(group+"-saved.json.gz")).read_bytes())
        data=json.loads(raw);job=term["job"];jobs.append(accounting(HERE/(group+"-accounting.psv"),job))
        need(term["positions"]==[list(pair) for pair in product(ks,ROLES)],"original position order")
        planned=[k+"-"+role for k,role in term["positions"]]
        need(term["not_launched"]==[x for x in planned if x not in term["exit_codes"]] and
             set(term["entries"])<=set(term["exit_codes"])<=set(planned),"original unexecuted suffix and attempt roster")
        if term["status"]=="COMPLETE":
            need(len(term["entries"])==len(term["result_sha256"])==len(planned) and set(term["exit_codes"].values())=={0}
                 and jobs[-1]["state"]=="COMPLETED" and jobs[-1]["exit_code"]=="0:0","complete group vs scheduler")
        need(len(term["entries"])==len(set(term["entries"])) and set(term["result_sha256"])<=set(term["entries"]),"at most one entry")
        need(private["group_files"][group+"/saved.json"]==hashlib.sha256(raw).hexdigest() and
             private["group_files"][group+"/terminal.json"]==sha(HERE/(group+"-terminal.json")),"unaltered group returns")
        entries+=len(term["entries"])
        found={}
        for k,arms in data.items():
            need(k in ks and k not in all_arms,"condition exclusive to its group")
            all_arms[k]=arms
            for role,s in arms.items():
                ident=k+"-"+role
                need(role in ROLES and (s["key"],s["role"],s["job"],s["group"])==(k,role,job,group)
                     and s["input_sha256"]==items[k]["sha256"] and s["execution_revision"]==freeze["execution_revision"] and
                     s["input_publication"]==lock["publication_commit"] and s["bundle_sha256"]==src["role_bundles"][role] and
                     s["host_pid"]!=s["worker_pid"] and s["status"]=="SCORED" and s["decisions"]==61,"identity: "+ident)
                need(all(isfinite(s[m]) and s[m]>=0 for m in ("L","U","person","tool","fee")),"valid scores")
                found[ident]=hashlib.sha256(packed(s)+b"\n").hexdigest()
                need(private["positions"][ident]["files_sha256"]==s["files_sha256"]|{"result.json":found[ident]},
                     "position originals: "+ident)
                native_decisions+=s["decisions"]
        need(found==term["result_sha256"],"complete digest roster")
    a=read(HERE/"analysis.json");m=read(HERE/"mechanisms.json")
    check_analysis(a,items,read(PRE/"overlap-ledger.json"),all_arms)
    check_mechanisms(m,all_arms)
    need(render(a,m)==(HERE/"tables.md").read_bytes(),"human-readable tables")
    budget=read(HERE/"batch-budget.json")
    need(sha(HERE/"pilot-terminal.json")==budget["pilot_terminal_sha256"] and jobs[0]["actual_cpu_s"]==budget["pilot_TotalCPU_s"]
         and jobs[1]["reserved_cpu_s"]==budget["reserved_cpu_s"]<=2*119*jobs[0]["actual_cpu_s"],"actual pilot and batch resource limit")
    need(d["jobs"]==jobs and d["facility_entries"]==entries and d["scored_decisions"]==native_decisions,"study accounting")
    need(private["group_files"]["author-entry.json"]==sha(HERE/"author-entry.json") and
         private["group_files"]["batch/analysis.json"]==sha(HERE/"analysis.json") and
         private["group_files"]["batch/mechanisms.json"]==sha(HERE/"mechanisms.json"),"original analysis and consumption receipts")
    need(set(private["positions"])=={k+"-"+r for k,r in product(KEYS,ROLES)},"all registered position records")
    need(d["source_archive_sha256"]==private["group_files"]["source.tar"],"executed archive")
    for name,pin in d["files_sha256"].items():need(sha(HERE/name)==pin,"published file: "+name)
    print("PASS H3 commitment, single generation, fixed 120-row order and both ledgers at their pre-score commit")
    print(f"PASS 5 + 595 registered positions; {entries} actual entries; {native_decisions} decisions in scored returns")
    print("PASS private original identities and frozen sources, five arms and per-position scoring provenance")
    print("PASS independent multinomial block variance, two-sided t intervals, p values, Holm decisions and event pairs")
    print(f"PASS original block denominators and descriptive sensitivity; {o['historical_exclusions']} exclusions")
    print("PASS every loss to periodic inspection, Dutch window witnesses and actual Slurm accounting")
    if args.checkout_bytes:
        paths={REL+"/"+name for name in (*d["files_sha256"],"delivery.json")}
        anchor=git("log","-1","--format=%H","HEAD","--",REL+"/delivery.json").decode().strip()
        for rev in (anchor,"HEAD"):
            need(set(git("ls-tree","-r","--name-only",rev,"--",REL).decode().splitlines())==paths,"declared release inventory")
            for path in paths:
                need((ROOT/path).read_bytes()==git("show",rev+":"+path),"clean checkout bytes: "+path)
        trailer=git("show","-s","--format=%B",anchor).decode().splitlines()
        need("Delivery-SHA256: "+sha(HERE/"delivery.json") in trailer,"release hash trailer")
        for sub in ("r1","stage1"):
            base=REL.rsplit("/",1)[0]+"/"+sub
            for path in git("ls-tree","-r","--name-only","41709979","--",base).decode().splitlines():
                need((ROOT/path).read_bytes()==git("show","41709979:"+path),"original package "+path)
        print(f"PASS checkout bytes: {len(paths)} stage-2 files, r1, stage 1 and the delivery hash trailer")
    print("Delivery-SHA256:",sha(HERE/"delivery.json"))


if __name__=="__main__":main()
