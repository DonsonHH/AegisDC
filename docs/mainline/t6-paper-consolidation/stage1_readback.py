"""T6 stage 1. Read only named, sealed Git blobs; no facility, cluster, RNG or seed interface."""
import sys
sys.dont_write_bytecode = True

import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import json
from math import isfinite
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = "ce3ee6303a81f99341d40796d499185e997238da"
STAGE0 = "cc5b43a8ac6d2de9407bcf6ed5355d025cdca55a"
T4B = "3487276af9e9759357771d16eb45feceaa3c948a"
T4D = "036ccfdf2d6e5d4b39ba11da480fa2a3d69c1f9f"
V3A = "29ac5a2eac2e6527cbfd04145b0caa2c9206c09e"
NEW = "87cdd7183970a7787616c666246b38b9fce8320b"
PATH4B = "docs/mainline/t4b-holdout-confirmation-v2/"
PATH4D = "docs/mainline/t4d-cost-baseline-v1/"
PATHA = "docs/mainline/t5-landscape-diagnostic-v3a/"
PATHN = "docs/mainline/t5-observable-selector-v3c/"
MAIN = "MAIN-R-3"
FAMILIES = ("WATER_HEAT","NETWORK_POWER","RESERVE_TRANSFER","COOLING_ACCESS","LONDON","NETHERLANDS")
STATUS_QUO = ("P","PERIODIC","ALARM")
POST = "POSTHOC_MIN_P_PERIODIC_ALARM"
TOL = Fraction(1,100)
F = Fraction


def require(ok, why):
    if not ok:
        raise ValueError("stage 1 readback: "+why)


def blob(revision, path):
    return subprocess.check_output(["git","-C",str(ROOT),"show",revision+":"+path])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def number(v):
    require(type(v) in (int,float) and isfinite(v),"not a finite stored number")
    return F(v)


def mean(values):
    return sum(values,F(0))/len(values)


def exact_seconds(v):
    return {"seconds":float(v),"fraction":str(v)}


def load_seals():
    data={}; catalog={}
    def get(label,rev,path):
        raw=blob(rev,path)
        data[label]=json.loads(gzip.decompress(raw) if path.endswith(".gz") else raw)
        catalog[label]=dict(commit=rev,path=path,sha256=sha(raw))
    for label,rev,path in [
        ("t4b",T4B,PATH4B+"results.json.gz"),("r4b",T4B,PATH4B+"receipt.json"),
        ("t4d",T4D,PATH4D+"development-result.json.gz"),("r4d",T4D,PATH4D+"receipt.json"),
        ("old",V3A,PATHA+"results.json.gz"),("rold",V3A,PATHA+"receipt.json"),
        ("design",V3A,PATHA+"design.json"),("panel",V3A,PATHA+"panel-and-strategies.json"),
        ("new",NEW,PATHN+"confirmation-result.json"),("rnew",NEW,PATHN+"confirmation-receipt.json"),
        ("lock",NEW,PATHN+"locked-selector.json")]:
        get(label,rev,path)
    for label,receipt,path in [
        ("t4b","r4b",["transferred_artifacts_sha256","results.json.gz"]),
        ("t4d","r4d",["remote_return_sha256","development-result.json.gz"]),
        ("old","rold",["remote_return_sha256","results.json.gz"]),
        ("design","rold",["source_and_delivery_files_sha256",PATHA+"design.json"]),
        ("panel","rold",["remote_return_sha256","panel-and-strategies.json"]),
        ("new","rnew",["result_sha256"]),("lock","rnew",["lock","sha256"])]:
        saved=data[receipt]
        for k in path:saved=saved[k]
        require(saved==catalog[label]["sha256"],"published SHA-256: "+label)
        catalog[label]["receipt_hash_field"]=receipt+"#/"+"/".join(k.replace("~","~0").replace("/","~1") for k in path)
    return data,catalog


def check_navigation():
    md="docs/MAINLINE.md";js="docs/mainline/progress.json"
    original,updated=blob(BASE,md),blob(STAGE0,md)
    require(updated.startswith(original),"stage 0 MAINLINE byte prefix")
    a,b=blob(BASE,js),blob(STAGE0,js);first=json.loads(a);now=json.loads(b)
    nav=now.pop("append_20261125_t5_status")
    require(a.endswith(b"}\n") and b.startswith(a[:-2]) and b.endswith(a[-2:]) and first==now,"stage 0 JSON original lines and values")
    require(len(nav["records"])==7 and len({q["commit"] for q in nav["records"]})==7,"seven dated milestones")
    for item in nav["records"]:
        require(item["commit"][:8].encode() in updated[len(original):] and item["reading"].encode() in updated[len(original):],"identical timeline")
    return dict(revision=STAGE0,base=BASE,source_paths=[md,js],records_field="progress#/append_20261125_t5_status/records",milestones=nav["records"],
                added_lines={md:updated.count(b"\n")-original.count(b"\n"),js:b.count(b"\n")-a.count(b"\n")},removed_lines=0)


def check_roster(rows,per_family,name):
    keys=[r["key"] for r in rows]
    require(len(set(keys))==len(keys)==per_family*len(FAMILIES),name+" complete unique condition keys")
    require(Counter(r["family"] for r in rows)=={f:per_family for f in FAMILIES},name+" family denominators")


def summarize(group,rows,role,indices):
    present=[i for i in indices if role==POST or role in rows[i]["arms"]]
    require(not present or present==indices,"partial arm, cannot silently drop conditions: "+role)
    if not present:
        return dict(state="ARM_NOT_PRESENT",planned=len(indices),pairs=0,mean=None,better=None,equal=None,worse=None,
                    field=group+"/*/arms/"+role,within_indices=indices)
    ds=[]
    for i in present:
        arms=rows[i]["arms"]
        ls=[number(arms[r]["L"]) for r in (STATUS_QUO if role==POST else (role,))]
        ds.append(number(arms["V_COST"]["L"])-min(ls))
    keys=[rows[i]["key"] for i in present]
    bad=[k for k,d in zip(keys,ds) if d>0]
    return dict(state="SCORED",planned=len(indices),pairs=len(ds),mean=exact_seconds(mean(ds)),
                better=sum(d<0 for d in ds),equal=sum(d==0 for d in ds),worse=len(bad),worse_keys=bad,
                row_indices=indices,fields=dict(keys=group+"/{i}/key",family=group+"/{i}/family",V=group+"/{i}/arms/V_COST/L",
                    controls=[group+"/{i}/arms/"+r+"/L" for r in (STATUS_QUO if role==POST else (role,))]))


def c1_panel(label,rows,group,roles,per_family,level):
    check_roster(rows,per_family,label)
    lookup={"ALL":list(range(len(rows))),**{f:[i for i,r in enumerate(rows) if r["family"]==f] for f in FAMILIES}}
    result={}
    for scope,indices in lookup.items():
        result[scope]={role:summarize(group,rows,role,indices) for role in roles}
    for role in roles:
        total=result["ALL"][role];parts=[result[f][role] for f in FAMILIES]
        require(sum(p["pairs"] for p in parts)==total["pairs"],"scope denominator")
        if total["pairs"]:
            require(sum(F(p["mean"]["fraction"])*p["pairs"] for p in parts)==F(total["mean"]["fraction"])*total["pairs"]
                    and all(sum(p[k] for p in parts)==total[k] for k in ("better","equal","worse")),"scope arithmetic")
    return dict(level=level,candidate="V_COST",comparators=roles,panel_n=len(rows),source_rows=group,
                row_key_order=[r["key"] for r in rows],scopes=result)


def t4d_count(data):
    rows=data["panels"]["BASE"];check_roster(rows,12,"T4d BASE")
    items=[]
    for i,r in enumerate(rows):
        a,b=(number(r["arms"][l]["L"]) for l in ("B","P"))
        items.append(dict(key=r["key"],family=r["family"],B=float(a),P=float(b),delta_s=float(a-b),row=i))
    return dict(level="public development, original BASE only; S0/S1/S2 sensitivity panels excluded",panel_n=len(items),
                better=sum(t["delta_s"]<0 for t in items),equal=sum(t["delta_s"]==0 for t in items),
                worse=sum(t["delta_s"]>0 for t in items),worse_rows=[t for t in items if t["delta_s"]>0],
                rows=items,fields=["t4d#/panels/BASE/{row}/"+q for q in ("key","family","arms/B/L","arms/P/L")])


def certificate(row,new_panel):
    cert=row["lower" if new_panel else "minimum"]
    require(cert["status"]=="ATTAINED" and cert["actual_chain"] is True,"uncertified bound "+row["key"])
    lb=number(cert["certified_min"])
    require(number(row["arms"]["ORACLE"]["L"])==number(cert["native_L"])==lb,"attainment by original native witness "+row["key"])
    return lb


def c4_evidence(data):
    design=data["design"]["roles"];m=data["panel"];rows=data["old"]["conditions"]
    new=data["new"]["conditions"];check_roster(rows,6,"v3a");check_roster(new,6,"new panel")
    require(m["order"]==[r["key"] for r in rows] and len(set(m["order"]))==36,"v3a source collection order")
    require(set(m["vectors"])==set(design["random"]) and set(m["reference_identities"])==set(design["reference"]),"all frozen policy identities")
    replay=design["random"]+design["reference"]
    subset=design["random"]+[r for r in design["reference"] if r.startswith(("MAIN-U-","MAIN-R-"))]
    extra=[l for l in replay if l not in subset]
    require(len(set(subset))==len(subset)==54 and len(set(replay))==len(replay)==58 and
            set(extra)=={"B_COST","V_COST","M","M_HOT"} and data["lock"]["roster"]==replay,"independent two rosters and stage-0 acceptance order")
    require(data["lock"]["fit"]["winner"]==MAIN and all(r["arms"]["W"]["entry"]["actual"]==MAIN for r in new),"all new W instances are the locked vector")
    definitions={"fixed54":subset,"replay58":replay}
    scores=[];matrix=[]
    for i,r in enumerate(rows):
        lo=certificate(r,False)
        require(set(r["arms"]) in (set(replay)|{"ORACLE"},set(replay)|{"ORACLE","P"}),"no omitted or substituted v3a arm")
        gaps={l:number(r["arms"][l]["L"])-lo for l in replay}
        require(all(v>=0 for v in gaps.values()),"a scored original is below certified bound")
        record=dict(i=i,key=r["key"],family=r["family"],bound_s=float(lo),R3_L_s=r["arms"][MAIN]["L"],R3_gap_s=float(gaps[MAIN]),
                    R3_within_tolerance=gaps[MAIN]<=TOL)
        for name,labels in definitions.items():
            low=min(gaps[l] for l in labels)
            record[name]=dict(row_min_gap_s=float(low),first_attaining=next(l for l in labels if gaps[l]==low),
                              all_attaining=[l for l in labels if gaps[l]==low])
        scores.append(record);matrix.append(gaps)
    means={l:mean([g[l] for g in matrix]) for l in replay}
    pools={}
    for name,labels in definitions.items():
        fixed=min(means[l] for l in labels)
        pools[name]=dict(count=len(labels),members=labels,
            rowwise_best_mean_gap=exact_seconds(mean([min(g[l] for l in labels) for g in matrix])),
            best_single_vector_mean_gap=exact_seconds(fixed),whole_panel_minimizers=[l for l in labels if means[l]==fixed],
            rowwise_zero_gap_rows=sum(min(g[l] for l in labels)==0 for g in matrix),
            fixed_vector_panel_means={l:exact_seconds(means[l]) for l in labels})
    new_scores=[]
    for i,r in enumerate(new):
        lb=certificate(r,True);v=number(r["arms"]["W"]["L"]);require(v>=lb,"new W below certified bound")
        new_scores.append(dict(i=i,key=r["key"],family=r["family"],bound_s=float(lb),W_L_s=float(v),R3_gap_s=float(v-lb),R3_within_tolerance=v-lb<=TOL))
    official=data["old"]["overall"][MAIN]
    require(official["valid_gap_pairs"]==len(rows) and abs(means[MAIN]-number(official["mean_gap"]))<F(1,10**10),"old sealed mean cross-check")
    return dict(old_level="public landscape development",new_level="new synthetic confirmation panel; this W reuse is a descriptive readback",
                tolerance_s=0.01,tolerance_definition="0 <= L - certified_min <= 1/100; strictly greater means residual room",
                sources=dict(old_L="old#/conditions/{i}/arms/{member}/L",old_lower="old#/conditions/{i}/minimum/certified_min",
                    old_attainment=["old#/conditions/{i}/minimum/status","old#/conditions/{i}/minimum/actual_chain",
                                    "old#/conditions/{i}/minimum/native_L","old#/conditions/{i}/arms/ORACLE/L"],
                    old_keys="old#/conditions/{i}/key",old_family="old#/conditions/{i}/family",old_sealed_check="old#/overall/MAIN-R-3/mean_gap",
                    new_L="new#/conditions/{i}/arms/W/L",new_lower="new#/conditions/{i}/lower/certified_min",
                    new_attainment=["new#/conditions/{i}/lower/status","new#/conditions/{i}/lower/actual_chain","new#/conditions/{i}/lower/native_L","new#/conditions/{i}/arms/ORACLE/L"],
                    new_W_binding=["new#/conditions/{i}/arms/W/entry/actual","lock#/fit/winner"],new_keys="new#/conditions/{i}/key",new_family="new#/conditions/{i}/family",
                    roster=["design#/roles/random","design#/roles/reference","panel#/vectors","panel#/reference_identities","lock#/roster"]),
                operations=dict(pointer_best="mean over conditions of min over named members (L - certified_min), retrospective",
                    single_fixed="min over named members of mean over all conditions (L - certified_min), same member for every condition"),
                pools=pools,only_in_54=[],only_in_58=extra,excluded_evaluator="ORACLE and auxiliary P are not members",
                loss_scale=dict(old_mean_certified_lower_s=exact_seconds(mean([number(r["bound_s"]) for r in scores])),
                    rowwise_mean_raw_L_s={n:exact_seconds(mean([number(r["bound_s"])+number(r[n]["row_min_gap_s"]) for r in scores])) for n in definitions},
                    best_single_mean_raw_L_s={n:exact_seconds(F(q["best_single_vector_mean_gap"]["fraction"])+mean([number(r["bound_s"]) for r in scores]))
                                              for n,q in pools.items()}),
                old_R3_mean_gap=exact_seconds(means[MAIN]),old_R3_attained=sum(r["R3_within_tolerance"] for r in scores),
                old_n=len(scores),old_R3_room=[r["key"] for r in scores if not r["R3_within_tolerance"]],
                new_R3_attained=sum(r["R3_within_tolerance"] for r in new_scores),new_n=len(new_scores),
                old_rows=scores,new_rows=new_scores)


def directions(r):
    return [r[k] for k in ("better","equal","worse")]


def compare_pointers(c1,t4d,c4):
    """Pointers from the user's 2026-11-25 brief, applied only after reconstructing results."""
    audited=[]
    def add(panel,item,kind,want,got,evidence,expected_n=None,n=None):
        if kind=="seconds":
            exact=F(got["fraction"])
            ok=abs(exact-F(want))<=TOL if panel=="1b" else round(exact,2)==F(want)
        else:
            ok=want==got
        if expected_n is not None:ok=ok and expected_n==n
        audited.append(dict(stage=panel,item=item,kind=kind,reference=want,observed=got,reference_n=expected_n,
                            observed_n=n,source=evidence,match=ok))
    full=[("T4b","P","-711.96",[73,67,4]),("T4b","PERIODIC","-447.89",[45,89,10]),
          ("T4b","ALARM","-489.91",[67,73,4]),("T4b","B","-343.90",[54,76,14]),
          ("v3c","P","-551.78",[16,18,2]),("v3c","PERIODIC","-302.97",[8,25,3]),
          ("v3c","ALARM","-344.90",[14,22,0])]
    def comparison(panel,scope,arm,expected,counts):
        x=c1[panel]["scopes"][scope][arm];p=f"#/C1/{panel}/scopes/{scope}/{arm}"
        n=144 if panel=="T4b" else 36
        if scope!="ALL":n//=6
        add("1a",f"{panel}/{scope}/{arm} mean","seconds",expected,x["mean"],p+"/mean",n,x["pairs"])
        add("1a",f"{panel}/{scope}/{arm} signs","counts",counts,directions(x),p,n,x["pairs"])
    for panel,arm,s,c in full:comparison(panel,"ALL",arm,s,c)
    for panel,arm,s,c in (("T4b","P","-590.92",[11,10,3]),("T4b","PERIODIC","37.29",[1,20,3]),
                          ("T4b","ALARM","-307.83",[7,14,3]),("v3c","PERIODIC","0.00",[0,6,0]),
                          ("v3c","ALARM","0.00",[0,6,0])):
        comparison(panel,"COOLING_ACCESS",arm,s,c)
    for arm,n in (("PERIODIC",4),("B",10)):
        k="NETHERLANDS";r=c1["T4b"]["scopes"][k][arm]
        add("1a","T4b/NETHERLANDS/"+arm+" losses","count",n,r["worse"],f"#/C1/T4b/scopes/{k}/{arm}/worse",24,r["pairs"])
    r=c1["T4b"]["scopes"]["COOLING_ACCESS"][POST]
    add("1a","T4b/COOLING_ACCESS/post hoc min","seconds","112.29",r["mean"],f"#/C1/T4b/scopes/COOLING_ACCESS/{POST}/mean",24,r["pairs"])
    add("1a","v3c B presence","state","ARM_NOT_PRESENT",c1["v3c"]["scopes"]["ALL"]["B"]["state"],"#/C1/v3c/scopes/ALL/B/state")
    add("1a","T4d BASE B worse than P","count",18,t4d["worse"],"#/T4d/worse",72,t4d["panel_n"])
    add("1b","v3a best of fixed candidate set, rowwise","seconds","0.00",c4["pools"]["fixed54"]["rowwise_best_mean_gap"],
        "#/C4/pools/fixed54/rowwise_best_mean_gap",36,c4["old_n"])
    add("1b","v3a MAIN-R-3 mean gap","seconds","82.03",c4["old_R3_mean_gap"],"#/C4/old_R3_mean_gap",36,c4["old_n"])
    add("1b","v3a MAIN-R-3 at bound","count",32,c4["old_R3_attained"],"#/C4/old_R3_attained",36,c4["old_n"])
    add("1b","v3a MAIN-R-3 above bound tolerance","count",4,len(c4["old_R3_room"]),"#/C4/old_R3_room",36,c4["old_n"])
    add("1b","new W=MAIN-R-3 at bound","count",36,c4["new_R3_attained"],"#/C4/new_R3_attained",36,c4["new_n"])
    diffs=[r for r in audited if not r["match"]];gate="REPRODUCED" if not any(r["stage"]=="1b" for r in diffs) else "MISMATCH_STOP"
    return dict(source="2026-11-25 user-approved T6 brief, stage 1; reference values are not inputs to fitting or filtering",
                seconds_check="1a: compare at displayed precision; 1b: absolute difference <= 0.01 s; counts and denominators exact",
                checked=audited,differences=diffs,C4_numerical_gate=gate,
                interpretation_difference=dict(
                    reference="0.00 is the archived reviewer's per-condition best-of-set diagnostic",
                    fixed_54=c4["pools"]["fixed54"]["best_single_vector_mean_gap"],fixed_58=c4["pools"]["replay58"]["best_single_vector_mean_gap"],
                    rowwise_54=c4["pools"]["fixed54"]["rowwise_best_mean_gap"],rowwise_58=c4["pools"]["replay58"]["rowwise_best_mean_gap"],
                    explanation="If fixed means one policy for the entire board, the 0.00 pointer is not reproduced; swapping min and mean changes the quantity."))


def build():
    data,src=load_seals();nav=check_navigation()
    t=data["t4b"]["rows"];v=data["new"]["conditions"]
    orig=c1_panel("T4b",t,"t4b#/rows",["B",*STATUS_QUO,POST],24,"T4b synthetic holdout: registered B comparison, others descriptive readbacks")
    new=c1_panel("new",v,"new#/conditions",["B",*STATUS_QUO,"B_COST"],6,"new synthetic panel: all V_COST contrasts here are descriptive, not the S-W primary outcome")
    require(new["scopes"]["ALL"]["B"]["state"]=="ARM_NOT_PRESENT","new panel B must not be imputed from B_COST")
    # An independently stored T4b H1 summary also checks direction and order of signs.
    for scope,stats in orig["scopes"].items():
        official=data["t4b"]["scopes"]["overall" if scope=="ALL" else "family/"+scope]["test_effects"]["H1"]
        v0=stats["B"]
        require(official["available"]==v0["pairs"] and directions(v0)==official["directions"]
                and abs(F(v0["mean"]["fraction"])-number(official["metrics"]["L"]["mean"]))<F(1,10**10),"T4b H1 signed mean and counts "+scope)
    c1={"T4b":orig,"v3c":new}
    t4d=t4d_count(data["t4d"]);c4=c4_evidence(data)
    return dict(schema="aegisdc-t6-stage-1-readback-v1",baseline=BASE,sources=src,stage0=nav,
        definitions=dict(L="full-window normalized service deficit, seconds",
            C1="V_COST.L minus the comparator.L on the same row; pair signs strictly <0, =0, >0 with no tolerance. Mean is sum(delta)/n.",
            posthoc_min="one comparator per row chosen retrospectively by min(P.L,PERIODIC.L,ALARM.L); not a deployable baseline",
            missing="absent arm: null statistics, not a tie or zero loss",
            references="source#/path/{i} resolves via sources[source].commit and path; expand row_indices using their frozen source order; no new draws"),
        C1=c1,T4d=t4d,C4=c4,pointer_audit=compare_pointers(c1,t4d,c4),
        execution=dict(facility_calls=0,slurm_jobs=0,H2_generated=0,H2_read=0,H2_derived=0,
                       status="STAGE_1_DELIVERED_AWAITING_REVIEW",stage2_started=False,manuscript_started=False,C4_claim_wording="NOT_DECIDED"))


def encoded(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode("utf8")


def check_output(obj):
    a=obj["C4"];nav=obj["stage0"];diffs=obj["pointer_audit"]["differences"];c1=obj["C1"]
    lines=[f"Stage 0: {len(nav['milestones'])} T5 records; MAINLINE +{nav['added_lines']['docs/MAINLINE.md']}/-0, progress +{nav['added_lines']['docs/mainline/progress.json']}/-0; original lines and JSON values preserved.",
        f"Stage 1a: T4b {c1['T4b']['panel_n']} rows; new panel {c1['v3c']['panel_n']} rows. All six families and whole-panel comparisons verified. New B: absent; B_COST reported separately.",
        f"T4d BASE: B worse than P on {obj['T4d']['worse']}/{obj['T4d']['panel_n']} rows. Reference differences in 1a: {sum(r['stage']=='1a' for r in diffs)}."]
    for n in ("fixed54","replay58"):
        q=a["pools"][n];lines.append(f"v3a {q['count']} roles: rowwise best mean gap {q['rowwise_best_mean_gap']['seconds']:.2f} s; best single fixed vector {q['best_single_vector_mean_gap']['seconds']:.2f} s.")
    lines+= [f"MAIN-R-3: v3a mean gap {a['old_R3_mean_gap']['seconds']:.2f} s, within 0.01 s {a['old_R3_attained']}/{a['old_n']}, room on {len(a['old_R3_room'])}; new panel within 0.01 s {a['new_R3_attained']}/{a['new_n']}.",
             f"Stage 1b (source rowwise definition): {obj['pointer_audit']['C4_numerical_gate']}; 0.00 does not describe a single fixed policy. STOP FOR REVIEW.",
             "Read-only check: evidence, both reports and visible HTML tables agree. Facility=0; Slurm=0; H2=0."]
    return "\n".join(lines)+"\n"


def delivery_manifest():
    files=(".gitattributes","README.md","stage1-evidence.json","stage1_readback.py","stage1_report.py","review-draft.md","review.html","verification.txt")
    return dict(schema="t6-stage1-file-identities-v1",base=BASE,stage0=STAGE0,
                durable_files={name:sha((OUT/name).read_bytes()) for name in files},
                renderer=dict(skill="answer-me-with-html",version="0.6.4",node="24.22.3",
                              cli_sha256="44e4610c22917cfd760e35619c394726b69e57881a3f211c2797cb973e41fa88",
                              input="review-draft.md",output="review.html",delivery_eol="LF"),
                seal_note="This manifest is not self-hashed; the delivery commit pins its own blob.")


def command():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument("--check",action="store_true",help="compare sealed data, report and rendered numbers without writing")
    mode.add_argument("--seal",action="store_true",help="after rendering, save the readback transcript and durable file hashes")
    args=p.parse_args()
    from stage1_report import documents,check_html
    obj=build();report,draft=documents(obj)
    result={"stage1-evidence.json":encoded(obj),"README.md":report.encode("utf8"),"review-draft.md":draft.encode("utf8")}
    if args.check or args.seal:
        for f,b in result.items():require((OUT/f).read_bytes()==b,"delivery differs from reconstructed "+f)
        check_html(OUT/"review.html",obj)
        summary=check_output(obj)
        if args.seal:
            (OUT/"verification.txt").write_bytes(summary.encode("utf8"))
            (OUT/"delivery.json").write_bytes(encoded(delivery_manifest()))
        else:
            require((OUT/"verification.txt").read_bytes()==summary.encode("utf8"),"recorded verification transcript")
            require((OUT/"delivery.json").read_bytes()==encoded(delivery_manifest()),"durable release identities")
        print(summary,end="")
    else:
        for f,b in result.items():(OUT/f).write_bytes(b)


if __name__=="__main__":
    command()
