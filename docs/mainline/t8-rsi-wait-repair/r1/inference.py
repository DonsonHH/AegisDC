"""Block/cluster calculations over numerical inputs. Does not materialize a study split."""

from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
from statistics import mean, median, stdev
import os
import subprocess

import numpy as np
from scipy.stats import nct, t


HERE=Path(__file__).resolve().parent
FAMILIES=("LONDON","NETHERLANDS")
R0="6b63c4f4db6b8b19d01b2d00b99f740fba68525e"
PRIOR="41709979b277812c1b7af8af5d7d3128293cb790"
ROOT=HERE.parents[3]
NOMINAL=38
HARD_RISK=0.02


def read(path):
    return json.loads(path.read_bytes())


def finite(x):
    return round(float(x),8)


def structure_interval(differences, signatures, k_other, level=.95):
    """Parallel descriptive UCB, same block weighting, arbitrary within-signature dependence."""
    if not differences or len(differences)!=len(signatures) or not all(math.isfinite(v) for v in differences):
        return {"mean":None,"upper":None,"reason":"missing pairs/blocks"}
    delta=mean(differences)
    totals=defaultdict(float)
    for d,s in zip(differences,signatures,strict=True):
        totals[tuple(s)]+=d-delta
    k=len(totals);df=min(k,k_other)-1
    result={"mean":delta,"k":k,"df":df,"se":None,"upper":None}
    if df<1:
        return dict(result,reason="fewer than two distinct structures in at least one family")
    se=math.sqrt(k/(k-1)*math.fsum(x*x for x in totals.values()))/len(differences)
    if se==0:
        return dict(result,se=0,reason="zero cluster score variation")
    return dict(result,se=se,upper=delta+float(t.ppf(level,df))*se,reason="DESCRIPTIVE_ONLY")


def stratum_information(counts, rho):
    g=sum(counts.values())
    return g*g/((1-rho)*g+rho*sum(v*v for v in counts.values()))


def qualification(gain,g_l,g_n,df,extra_person=0,incremental_gain=None):
    if df<1:
        return None
    crit=t.isf(.05,df)
    eff=(gain/30,5/10,(5-extra_person)/5,(5-extra_person)/5)
    size=(g_n,g_l,g_l,g_n)
    probs=[float(nct.sf(crit,df,e*math.sqrt(n))) for e,n in zip(eff,size)]
    lower=1-sum(1-v for v in probs)-HARD_RISK
    r={"marginals_Q1_Q2_staff_L_staff_N":[finite(v) for v in probs],
       "joint_Q1_to_Q3":finite(max(0,lower))}
    if incremental_gain is not None:
        p4=float(nct.sf(crit,df,incremental_gain*math.sqrt(g_n)/30))
        r.update(Q4_descriptive_detection_probability=finite(p4),
                 hypothetical_all_four_labels_lower_bound=finite(max(0,lower-(1-p4))))
    return r


def development(sigs,capacity):
    design=read(HERE.parent/"r0/registration.json")
    caps=min(x["guaranteed_blocks"] for x in capacity["families"])
    pri=design["planning"]
    assert pri["block_sd"]=={"dutch_L":30,"london_L":10,"each_family_person":5}
    assert pri["planning_whole_panel_failure_allowance"]==HARD_RISK
    g=np.arange(2,caps+1);df=g-1;crit=t.isf(.05,df)
    curves={}
    # The 60 s scenario is shown both as a family mean and after dilution by a specified prevalence.
    scenarios=(("primary_15",15,0),("family_mean_60",60,0),("half_of_15",7.5,0),
               ("60_in_2_of_12",60*2/12,0),("historical_825_times_0.75",825*.75,0),
               ("15_with_2.5_extra_person",15,2.5),("15_with_5_extra_person",15,5))
    for name,gain,person_gap in scenarios:
        dutch=nct.sf(crit,df,gain*np.sqrt(g)/30)
        london=nct.sf(crit,df,5*np.sqrt(g)/10)
        staffing=nct.sf(crit,df,(5-person_gap)*np.sqrt(g)/5)
        curve=np.maximum(0,dutch+london+2*staffing-3-HARD_RISK)
        hits=g[curve>=.80]
        curves[name]={"gain_s":gain,"staff_true_gap":person_gap,"first_blocks":int(hits[0]) if len(hits) else None,
                      "at_38":finite(curve[NOMINAL-2]),"at_certified_capacity":finite(curve[-1]),
                      "values":[finite(a) for a in curve]}
    counts=[Counter(x[:NOMINAL]) for x in sigs]
    cluster_df=min(map(len,counts))-1
    cluster=[]
    for rho in (0,.5,1):
        gl,gn=[stratum_information(c,rho) for c in counts]
        row={"working_intra_signature_rho":rho,"effective_blocks":[finite(gl),finite(gn)],"df":cluster_df,
             "gains":{str(d):qualification(d,gl,gn,cluster_df,incremental_gain=7.5) for d in (15,60)}}
        cluster.append(row)
    windows=[]
    for start in range(0,len(sigs[0])-NOMINAL+1,NOMINAL):
        batch=[Counter(f[start:start+NOMINAL]) for f in sigs]
        k=[len(c) for c in batch];df_window=min(k)-1
        row={"offset":start,"k":k,"df":df_window,"df_only_15":qualification(15,NOMINAL,NOMINAL,df_window)["joint_Q1_to_Q3"]}
        gl,gn=[stratum_information(c,1) for c in batch]
        row["rho1_15"]=qualification(15,gl,gn,df_window)["joint_Q1_to_Q3"]
        windows.append(row)
    return {"g_range":[2,caps],"fixed_dev_blocks":NOMINAL,"curves":curves,
            "nominal_15":qualification(15,38,38,37,incremental_gain=7.5),
            "nominal_60":qualification(60,38,38,37,incremental_gain=7.5),
            "cluster_prefix_38":cluster,"disjoint_38_audit_windows":windows,
            "window_coverage":{fam:{"min":min(r["k"][i] for r in windows),"median":median(r["k"][i] for r in windows),
                "max":max(r["k"][i] for r in windows),"below_8":sum(r["k"][i]<8 for r in windows)} for i,fam in enumerate(FAMILIES)}}


def h2_grid(dev_gains,dev_sds):
    if any(x is None or not math.isfinite(x) or x<=0 for x in (*dev_gains,*dev_sds)):
        return {"eligible_precision":False,"selected_blocks":None,"reason":"no complete positive net gain or measurable block variation"}
    g=np.arange(2,77);df=g-1
    gains=[min(15,0.75*x) for x in dev_gains];sds=[max(30,x) for x in dev_sds]
    # Each contrast must clear the most stringent first step. This is a prospective lower bound,
    # not a substitution for the later joint Holm calculation.
    critical=t.isf(.025,df)
    curves=[nct.sf(critical,df,gain*np.sqrt(g)/sd) for gain,sd in zip(gains,sds)]
    bound=np.maximum(0,curves[0]+curves[1]-1-HARD_RISK)
    ix=np.nonzero(bound>=.80)[0]
    first=None if not len(ix) else int(g[ix[0]])
    raw=[nct.sf(critical,df,gain*np.sqrt(g)/sd) for gain,sd in zip(dev_gains,dev_sds)]
    return {"assumed_DEV_net_gains_s":dev_gains,"assumed_DEV_block_sds_s":dev_sds,
            "registered_H2_gains_s":gains,"registered_H2_sds_s":sds,"selected_blocks":first,
            "at_76":{"primary":finite(curves[0][-1]),"secondary":finite(curves[1][-1]),"joint_bound":finite(bound[-1])},
            "unshrunk_DEV_plugin_joint_at_76_descriptive":finite(max(0,raw[0][-1]+raw[1][-1]-1-HARD_RISK)),
            "at_first":None if first is None else {"primary":finite(curves[0][first-2]),
                    "secondary":finite(curves[1][first-2]),"joint_bound":finite(bound[first-2])},
            "joint_by_g2_through_76":[finite(x) for x in bound]}


def h2_from_dev_blocks(r_minus_o, r_minus_parent):
    """Future sufficient statistics only. No DEV seed/file argument and no permission to run H2."""
    if any(len(v)!=NOMINAL or not all(math.isfinite(x) for x in v) for v in (r_minus_o,r_minus_parent)):
        return {"selected_blocks":None,"reason":"incomplete Dutch DEV block pairs"}
    return h2_grid([-mean(v) for v in (r_minus_o,r_minus_parent)], [stdev(v) for v in (r_minus_o,r_minus_parent)])


def h2_budget(g,unit):
    # Two families for safety reporting; only the Dutch pairs enter the two Holm tests.
    positions=2*12*g*3
    return {"blocks_per_family":g,"conditions_per_family":12*g,"positions":positions,
            "jobs_range":[2+math.ceil(g/4),2+math.ceil(g/2)],"expected_cpu_s":[math.floor(.8*unit*positions),math.ceil(1.5*unit*positions+900)],
            "hard_actual_cpu_cap_s":180*positions+900}


def constrained_menu(rows,roles,cap):
    # Retain the lowest loss reachable at each exact personnel expenditure, never a rowwise deployable policy.
    frontier={0:0}
    for r in rows:
        nxt={}
        for previous,loss in frontier.items():
            for role in roles:
                c=previous+r[role]["person"]
                if c<=cap:
                    nxt[c]=min(nxt.get(c,math.inf),loss+r[role]["L"])
        frontier=nxt
    best,cost=min((loss,c) for c,loss in frontier.items())
    return {"minimum_total_L":best,"least_person_at_minimum":cost,"mean_gain_vs_parent":
            (sum(r["V_COST"]["L"] for r in rows)-best)/len(rows)}


def old_development():
    name="docs/mainline/t7-incident-counterfactual/stage1/comparison.json"
    if os.environ.get("SLURM_JOB_ID"):
        raw=(HERE.parent/"public-development/comparison.json").read_bytes()
    else:
        raw=subprocess.check_output(["git","cat-file","blob",PRIOR+":"+name],cwd=ROOT)
    import hashlib
    assert hashlib.sha256(raw).hexdigest()=="0e4c33b5b1a466e02d0e4be7d2d1deac09861d3b899ff00a606cded56ae7be50"
    rows=[r["arms"] for r in json.loads(raw)["rows"] if r["family"]=="NETHERLANDS"]
    cap=sum(x["V_COST"]["person"] for x in rows)+5*len(rows)
    return {"source":PRIOR+":"+name,"n":len(rows),"audit_person_cap":cap,"parent_mean_L":mean(r["V_COST"]["L"] for r in rows),
            "oracle_mean_L":mean(r["ORACLE"]["L"] for r in rows),"parent_total_person":sum(r["V_COST"]["person"] for r in rows),
            "observed_deployable_arm_menu":constrained_menu(rows,("V_COST","P","ALARM","PERIODIC"),cap),
            "including_evaluator_only_oracle":constrained_menu(rows,("V_COST","P","ALARM","PERIODIC","ORACLE"),cap)}


def make():
    capacity=read(HERE/"capacity.json")
    sigs=[]
    for fam in FAMILIES:
        rows=json.loads(gzip.decompress((HERE/(fam+"-audit-blocks.json.gz")).read_bytes()))
        sigs.append([tuple(r["cluster_signature"]) for r in rows])
    old=old_development()
    plan=development(sigs,capacity)
    r0power=read(HERE.parent/"r0/power.json")
    unit=r0power["inputs"]["reference_CPU_s_per_V_position"]
    tests=[([g,20],[30,30]) for g in (5,10,40/3,15,20,60)]
    tests.extend([([20,20],[45,30]),([20,20],[60,60]),([15,15],[30,30])])
    h=[h2_grid(x,y) for x,y in tests]
    for row in h:
        row["budget_at_first"]=h2_budget(row["selected_blocks"],unit) if row.get("selected_blocks") else None
    return {"schema":"T8.stage1a.planning.readback.v1","development":plan,"work_constrained_opportunity":old,
            "H2":{"actual_DEV_input":None,"actual_H2_N":None,"primary":"R-O","secondary":"R-V_COST",
                  "preauthorization_status":"WITHHELD","prospective_scenarios":h,"budget_at_cap":h2_budget(76,unit)},
            "later_FIT_DEV_caps":{"FIT_jobs":10,"FIT_actual_CPU_s":285900,"DEV_jobs":21,"DEV_actual_CPU_s":1150020,
                                 "combined_jobs":31,"combined_actual_CPU_s":1435920}}


if __name__=="__main__":
    import sys
    if sys.argv[1:]!=["--planning"]:raise SystemExit("use --planning for readback of unscored design arithmetic")
    sys.stdout.buffer.write((json.dumps(make(),sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode())
