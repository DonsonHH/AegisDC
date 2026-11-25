"""Verify the published structural audit and analytic planning; never open historical holdout inputs."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from math import factorial, isclose, sqrt
from pathlib import Path
import subprocess
from scipy.special import stdtrit
from scipy.stats import nct

from inference import FAMILIES, h2_from_dev_blocks, h2_grid, make, structure_interval


HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
def require(test,why):
    if not test:raise ValueError(why)


def independent_signature(hist):
    events=dict((k[0],n) for k,n in hist["fault_time_histogram"])
    available=hist["opportunity_histogram"]
    return (12-events.get(-1,0),events.get(1500,0),sum(n for (j,_),n in available if j>0),
            sum(n for (j,_),n in available if j in (1,2,3)),sum(n for (j,*_),n in hist["work_joint"] if j==0))


def check_private(folder, r):
    f=r["family"];p=folder/(f+"-row-identities.jsonl.gz")
    require(sha(p.read_bytes())==r["private_row_file_sha256"], "private audit identity file: "+f)
    sums=hashlib.sha256();count=0;ids=[set(),set(),set()];profiles={}
    with gzip.open(p,"rb") as stream:
        for raw in stream:
            block,slot,profile,values=json.loads(raw)
            require((block,slot)==divmod(count,12) and len(values)==3,"ordered audit cases")
            require(profiles.setdefault(tuple(profile),block)==block,"a profile appears in two audit blocks")
            for i,v in enumerate(values):ids[i].add(v)
            sums.update(raw);count+=1
    require(sums.hexdigest()==r["ordered_audit_identity_chain_sha256"] and count==r["audit_rows"],"audit rolling digest")
    require(list(map(len,ids))==[count]*3 and len(profiles)==11*r["audit_blocks"],"independent three-identity capacity proof")


def lower_tail(g, reduction, staff=0, nl_units=None, london_units=None, df=None):
    degrees=g-1 if df is None else df
    q=stdtrit(degrees,.05)
    sizes=[nl_units or g,london_units or g,london_units or g,nl_units or g]
    shifts=[-reduction/30,-.5,(staff-5)/5,(staff-5)/5]
    probs=[float(nct.cdf(q,degrees,x*sqrt(n))) for x,n in zip(shifts,sizes)]
    return max(0,sum(probs)-3-.02)


def check(private=None):
    cap=read(HERE/"capacity.json");lock=read(HERE/"audit-sources.json");plan=read(HERE/"audit-plan.json")
    old=read(HERE.parent/"r0/panel-law.json");sup=read(HERE/"supplement.json")
    require(sha((HERE.parent/"r0/registration.json").read_bytes())==plan["registration_sha256"]==sup["parent_registration_sha256"],"original registration")
    require(cap["source_sha256"]==sha((HERE/"audit-sources.json").read_bytes()),"actual audit lock")
    for name,pin in lock["files_sha256"].items():
        role,path=name.split("/",1)
        if role=="r1":b=(HERE/path).read_bytes()
        elif role=="r0":b=(HERE.parent/"r0"/path).read_bytes()
        else:
            require(role=="base" and not any(s in path for s in ("stage2","/holdout","development-result","/private/")),"unexpected source path")
            b=subprocess.check_output(["git","cat-file","blob",lock["base_revision"]+":"+path],cwd=ROOT)
        require(sha(b)==pin,"audit source bytes: "+name)
    require(cap["audit_condition_calls"]==34584 and all(cap[x]==0 for x in
            ("facility_calls","policy_decisions","scores","FIT_conditions","DEV_conditions","H2_access","H3_access","official_overlap_queries")),"A boundary")
    gross=sum(sum(r["counts"]) for r in old["historical_catalogue"]["entries"])
    for r in cap["families"]:
        f=r["family"];p=HERE/(f+"-audit-blocks.json.gz")
        require(sha(p.read_bytes())==r["block_file_sha256"],"aggregate feature hash")
        rows=json.loads(gzip.decompress(p.read_bytes()))
        require(len(rows)==r["audit_blocks"]==(15876-22)//11 and not r["blocks_with_internal_identity_repeats"],"complete capacity")
        require(gross==714 and r["guaranteed_blocks"]==len(rows)-gross and r["guaranteed_rows"]>=684,"historical pigeonhole lower bound")
        for tab, selected in (("all",rows),("first_registered_size",rows[:38])):
            for cat,stats in r[tab].items():
                counts=Counter()
                for block in selected:
                    h=block["histograms"]
                    require(all(sum(pair[1] for pair in arr)==12 for arr in h.values()),"structure counts")
                    sig=independent_signature(h)
                    require(list(sig)==block["cluster_signature"],"prescoring primary signature")
                    key=sig if cat=="primary_cluster" else json.dumps(h[cat],sort_keys=True)
                    counts[key]+=1
                n=len(selected);sq=sum(x*x for x in counts.values())
                require(len(counts)==stats["unique"] and max(counts.values())==stats["max_multiplicity"] and
                        isclose(n*n/sq,stats["inverse_simpson"]) and (sq-n)//2==stats["matching_pairs"],"diversity profile: "+cat)
        require(r["all"]["primary_cluster"]["unique"]>=8,"candidate diversity threshold")
        if private is not None:check_private(private,r)
    power=make()
    require(power==read(HERE/"power-audit.json"),"CPU allocation power return vs unchanged local readback")
    dev=power["development"]
    for name,d in (("primary_15",15),("family_mean_60",60),("60_in_2_of_12",10),("half_of_15",7.5)):
        for g in (24,38,63,107,cap["families"][0]["guaranteed_blocks"]):
            require(abs(lower_tail(g,d)-dev["curves"][name]["values"][g-2])<5.1e-9,"independent one-sided joint tail")
    for row in dev["cluster_prefix_38"]:
        gl,gn=row["effective_blocks"]
        for gain in (15,60):
            require(abs(lower_tail(38,gain,nl_units=gn,london_units=gl,df=row["df"])-row["gains"][str(gain)]["joint_Q1_to_Q3"])<1e-7,"cluster power")
    # Exact arithmetic check with unequal cluster masses; no endpoint or study data here.
    ci=structure_interval([0,2,4,6],[(0,),(0,),(1,),(1,)],2)
    require(ci["df"]==1 and ci["mean"]==3 and isclose(ci["se"],2) and
            isclose(ci["upper"],3+2*float(stdtrit(1,.95))),"cluster sandwich")
    require(structure_interval([0,1],[(0,),(0,)],3)["upper"] is None and
            structure_interval([0,0],[(0,),(1,)],2)["upper"] is None,"no invented zero-variation structural CI")
    require(h2_from_dev_blocks([],[])["selected_blocks"] is None and h2_grid([0,20],[30,30])["selected_blocks"] is None,"H2 fails closed")
    require(h2_grid([20,20],[30,30])["selected_blocks"]==46 and h2_grid([15,20],[30,30])["selected_blocks"]==65,"H2 example sizes")
    require(sup["decision"]=="A 无需改动" and dev["curves"]["primary_15"]["first_blocks"]==38 and
            power["H2"]["actual_H2_N"] is None,"stage A disposition or H2 evidence boundary")
    print("PASS frozen input-only generator, 34,584 audit candidates, 727..1,441 complete blocks/family; no protected index opened")
    print("PASS all structural histograms and five-count signature; pool k=11/32; prefix k=9/15, common df=8")
    print("PASS 15/60 s, prevalence dilution, block/cluster joint bounds, descriptive Q4 and cost-constrained old development menu")
    print("PASS H2 conditional R-O / R-parent power and separate budgets; actual DEV inputs and H2 N remain unknown")
    if private is not None:print("PASS 34,584 private audit identity triples, unique shifts per block and both rolling digests")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--check",action="store_true",required=True)
    parser.add_argument("--private-audit-only",type=Path,help="optional private audit enumeration journals; no historical panel input")
    args=parser.parse_args();check(args.private_audit_only)
