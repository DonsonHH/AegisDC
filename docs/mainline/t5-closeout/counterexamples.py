"""Paired V_COST minus P, plus hash-bound issued actions. No runtime or random imports."""
from fractions import Fraction
import gzip
import hashlib
import json

V3 = "87cdd7183970a7787616c666246b38b9fce8320b"
T4 = "3487276af9e9759357771d16eb45feceaa3c948a"
VROOT = "docs/mainline/t5-observable-selector-v3c"
TROOT = "docs/mainline/t4b-holdout-confirmation-v2"
BUNDLE = "counterexample-action-witnesses.json"
NAMED = ("new-3-05", "new-4-04", "new-6-03", "new-6-04")
FAMILIES = {"WATER_HEAT":"水侧与热","NETWORK_POWER":"网络与供电","RESERVE_TRANSFER":"有限备用",
            "COOLING_ACCESS":"冷却与通行","LONDON":"伦敦式","NETHERLANDS":"荷兰式"}
F = Fraction


def need(ok, why):
    if not ok:
        raise ValueError("counterexample readback: "+why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def packed(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",",":"), allow_nan=False).encode("ascii")


def sources_for(git):
    inventory, content = {}, {}
    for label, revision, path in (("new",V3,VROOT+"/confirmation-result.json"),
                                  ("index",V3,VROOT+"/confirmation-artifacts.sha256"),
                                  ("t4b",T4,TROOT+"/results.json.gz"),
                                  ("t4b_receipt",T4,TROOT+"/receipt.json")):
        obj=revision+":"+path
        raw=git("show",obj)
        inventory[label]=dict(commit=revision,path=path,git_blob=git("rev-parse",obj).decode().strip(),sha256=sha(raw))
        content[label]=(json.loads(gzip.decompress(raw)) if path.endswith(".gz") else
                        json.loads(raw) if path.endswith(".json") else raw.decode())
    need(content["t4b_receipt"]["transferred_artifacts_sha256"]["results.json.gz"]==inventory["t4b"]["sha256"],"original T4b gzip")
    return inventory,content


def counts(ds):
    return dict(better=sum(d<0 for d in ds),equal=sum(d==0 for d in ds),worse=sum(d>0 for d in ds))


def totals(ds):
    n=len(ds);s=sum(ds,F());avg=s/n
    return dict(n=n,**counts(ds),sum_delta_s=float(s),mean_delta_s=float(avg),exact_mean_fraction=str(avg))


def comparison_fields(row, base):
    return dict(key=row["key"],family=row["family"],V_L=row["arms"]["V_COST"]["L"],P_L=row["arms"]["P"]["L"],
                delta_s=float(F(row["arms"]["V_COST"]["L"])-F(row["arms"]["P"]["L"])),
                fields={"key":base+"/key","family":base+"/family","V_L":base+"/arms/V_COST/L","P_L":base+"/arms/P/L",
                        "delta_s":{"op":"subtract","fields":[base+"/arms/V_COST/L",base+"/arms/P/L"]}})


def trace_loss(curve):
    need(bool(curve),"empty original curve")
    previous=0; loss=F()
    for start,end,demand,delivered in curve:
        need(start==previous and end>start and demand>0 and 0<=delivered<=demand,"complete, normalized curve")
        loss+=(F(end)-F(start))*(F(demand)-F(delivered))/F(demand)
        previous=end
    need(previous==3600,"original full facility window")
    return loss


def verify_action_sources(out, materials, cases):
    bundle=json.loads((out/BUNDLE).read_bytes());idx={name:h for h,name in (s.split("  ",1) for s in materials["index"].splitlines())}
    need(bundle["artifact_index_commit"]==V3 and set(bundle["rows"])=={k+"/"+r for k in cases for r in ("V_COST","P")},"entire witness set")
    locators,actual={},{}
    for k,(i,cond) in cases.items():
        actual[k]={}
        for role in ("V_COST","P"):
            code=k+"/"+role;name="positions/"+code+"/row.json";x=bundle["rows"][code]
            base=f"/conditions/{i}/arms/{role}";summary=cond["arms"][role]
            need(sha(packed(x)+b"\n")==idx[name]==summary["row_sha256"],"canonical row bytes "+name)
            need((x["status"],x["key"],x["arm"],x["entry"])==("SCORED",k,role,summary["entry"]) and x["entered"] and
                 x["entry"]["actual"]==role and x["L"]==summary["L"] and x["U"]==summary["U"] and
                 x["raw"]==summary["raw"] and x["entry_sha256"]==summary["entry_sha256"],"role, physical input, and release "+name)
            need(sha(packed(x["issued"]))==summary["issued_digest"] and len(x["issued"])==summary["issued_count"] and
                 x["requests"]==[[e["at"],e["task"]] for e in x["issued"]] and [e["at"] for e in x["issued"]]==sorted(e["at"] for e in x["issued"]),
                 "issued objects, count, timestamps and order "+name)
            need(trace_loss(x["curve"])==F(x["L"]) and (role!="P" or not x["issued"]),"original witnessed L "+name)
            token="score:"+code
            locators[token]=dict(commit=V3,path=bundle["private_root"]+"/"+name,match_sha256=summary["row_sha256"],
                                 issued_sha256=summary["issued_digest"],index_file="index",index_key=name,
                                 public_digest_field="new#"+base+"/row_sha256",public_issued_digest_field="new#"+base+"/issued_digest",
                                 local_verified_object=BUNDLE+"#/rows/"+code.replace("/","~1"))
            actual[k][role]=x
    need(set(bundle["native_headers"])==set(cases),"native header roster")
    for k,h in bundle["native_headers"].items():
        i,cond=cases[k];row=actual[k]["V_COST"]
        name=f"positions/{k}/V_COST/original.jsonl.gz"
        need(h["native_sha256"]==idx[name]==row["raw"]==cond["arms"]["V_COST"]["raw"] and
             h["first_issued"]=={f:row["issued"][0][f] for f in ("task","at")},"sealed raw identity and first actual action: "+k)
        locators["raw:"+k]=dict(commit=V3,path=bundle["private_root"]+"/"+name,match_sha256=idx[name],index_file="index",
            index_key=name,public_digest_field=f"new#/conditions/{i}/arms/V_COST/raw",
            local_excerpt=BUNDLE+"#/native_headers/"+k,
            fields={"maintenance":"/metadata/v3_maintenance_events","received_maintenance":"/metadata/v3_received_maintenance",
                    "first_issued":"first non-null /metadata/policy_public_decisions/*/decision/request"})
    return locators, actual, bundle["native_headers"]


def make_supplement(out,git):
    sources,m=sources_for(git);new=m["new"];t4=m["t4b"];rows=new["conditions"];historic=t4["rows"]
    need(len(rows)==len({r["key"] for r in rows})==36 and len(historic)==len({r["key"] for r in historic})==144,"complete denominators")
    cases={r["key"]:(i,r) for i,r in enumerate(rows) if r["key"] in NAMED or r["arms"]["V_COST"]["L"]>r["arms"]["P"]["L"]}
    sources_extra,witness,headers=verify_action_sources(out,m,cases)
    sources.update(sources_extra)
    origin_new=[comparison_fields(r,f"new#/conditions/{i}") for i,r in enumerate(rows)]
    new_bad=[r["key"] for r in origin_new if r["delta_s"]>0]
    above_bound=[r["key"] for r in rows if F(r["arms"]["V_COST"]["L"])>F(r["lower"]["certified_min"])]
    need(all(r["lower"]["status"]=="ATTAINED" for r in rows),"oracle claim")
    examples=[]
    for k in sorted(cases):
        i,r=cases[k];z=origin_new[i].copy();z["fields"]=dict(z["fields"])
        v,p=witness[k]["V_COST"],witness[k]["P"];a=v["issued"][0];writes=v["writes"];curve=v["curve"]
        need(a["task"]==a["subject"]+"::"+a["phase"] and len(writes)==1 and len(curve)==3,"first actual action and service interval")
        wire=writes[0]; action=next((u for u in v["issued"] if u["task"]==wire["task"]),None)
        need(action is not None and action["at"]<=wire["at"],"corresponding actual write")
        prefix="score:"+k+"/V_COST#";pp="score:"+k+"/P#"
        row_kind="WORSE_THAN_P" if z["delta_s"]>0 else "TIED_WITH_P" if z["delta_s"]==0 else "BETTER_THAN_P"
        interval=curve[1];vm=wire["operation"];start,end,demand,supply=interval;h=headers[k];raw="raw:"+k+"#/metadata/"
        if row_kind=="WORSE_THAN_P":
            need(wire["outcome"]=="APPLIED" and start==wire["at"] and len(p["curve"])==1 and p["L"]==0 and
                 p["curve"][0][2:]==[1,1] and curve[0][2:]==curve[2][2:]==[1,1] and [demand,supply]==[1,.5] and
                 (end-start)*(1-supply/demand)==z["delta_s"] and vm in ("restore_network","clean_filter"),"observed service penalty")
            need(h["maintenance"]==[dict(task=wire["task"],at=start,until=end,indicated=False)] and
                 h["received_maintenance"]["exposure_s"]==end-start and h["received_maintenance"]["capacity"]==supply,
                 "native maintenance interval and capacity vs applied write and actual service")
            reason="unindicated_write_and_matching_maintenance_cap"
        else:
            need(row_kind=="TIED_WITH_P" and curve==p["curve"] and [demand,supply]==[1,0] and a["at"]>=end and
                 wire["outcome"]=="NO_EFFECT" and vm=="restart_pump","equal original curves and late no-effect action")
            need(not h["maintenance"],"no accepted maintenance change on tied path")
            reason="same_outage_then_no_effect_restart"
        z.update(panel="v3c",classification=row_kind,oracle_L=r["lower"]["certified_min"],first_issued_action=a["task"],first_issued_s=a["at"],
                 write_issued_s=action["at"],write_completed_s=wire["at"],write_operation=vm,write_outcome=wire["outcome"],
                 service_segment=interval,P_curve=p["curve"],native_maintenance=h["maintenance"],reason=reason)
        j=v["issued"].index(action)
        z["fields"].update(oracle_L=f"new#/conditions/{i}/lower/certified_min",
            first_issued_action=prefix+"/issued/0/task",first_issued_s=prefix+"/issued/0/at",
            write_issued_s=prefix+f"/issued/{j}/at",write_completed_s=prefix+"/writes/0/at",write_operation=prefix+"/writes/0/operation",
            write_outcome=prefix+"/writes/0/outcome",service_segment=prefix+"/curve/1",P_curve=pp+"/curve",
            native_maintenance=raw+"v3_maintenance_events",
            reason=[prefix+"/issued",prefix+"/writes",prefix+"/curve",pp+"/curve",raw+"v3_maintenance_events",raw+"v3_received_maintenance"])
        if row_kind=="WORSE_THAN_P":
            z["supply_pct"]=float(100*F(supply)/F(demand))
            z["fields"]["supply_pct"]={"op":"100 * delivered / demand","fields":[prefix+"/curve/1/3",prefix+"/curve/1/2"]}
        examples.append(z)

    # Use the full T4b panel: no complete-case selection, no estimates from the report prose.
    input_rows=[];groups={};bad=[]
    for i,r in enumerate(historic):
        base=f"t4b#/rows/{i}";v=r["arms"]["V_COST"];p=r["arms"]["P"]
        z=comparison_fields(r,base);input_rows.append(z)
        need(r["family"] in FAMILIES and not p["requests"],"historical P and family")
        groups.setdefault(r["family"],[]).append(i)
        if z["delta_s"]<=0:continue
        events=v["maintenance"];writes=v["writes"];req=v["requests"];stamp,task=req[0]
        need(req==sorted(req,key=lambda a:a[0]) and len(events)==len(writes)==1,"historical action order")
        e=events[0];w=writes[0];j=next(j for j,rq in enumerate(req) if rq[1]==w["task"])
        need(w["task"]==e["task"] and w["outcome"]=="APPLIED" and w["at"]==e["at"] and
             not e["indicated"] and e["lost_L_at_cap"]==z["delta_s"] and p["L"]==0,"retained maintenance explanation")
        badrow={**z,"fields":dict(z["fields"]), "panel":"T4b","classification":"WORSE_THAN_P","first_issued_action":task,"first_issued_s":stamp,
                "write_issued_s":req[j][0],"write_completed_s":w["at"],"write_operation":w["operation"],"write_outcome":w["outcome"],
                "maintenance_until_s":e["until"],"indicated":e["indicated"],"lost_L_at_cap":e["lost_L_at_cap"],"reason":"unindicated_write_bound_by_maintenance"}
        pr=base+"/arms/V_COST"
        badrow["fields"].update(first_issued_action=pr+"/requests/0/1",first_issued_s=pr+"/requests/0/0",
            write_issued_s=pr+f"/requests/{j}/0",write_completed_s=pr+"/writes/0/at",write_operation=pr+"/writes/0/operation",
            write_outcome=pr+"/writes/0/outcome",maintenance_until_s=pr+"/maintenance/0/until",indicated=pr+"/maintenance/0/indicated",
            lost_L_at_cap=pr+"/maintenance/0/lost_L_at_cap",reason=[pr+"/requests",pr+"/writes",pr+"/maintenance",base+"/arms/P/L"])
        bad.append(badrow)
    by_family={}
    for fam in FAMILIES:
        ids=groups[fam];ds=[F(input_rows[i]["delta_s"]) for i in ids];summary=totals(ds)
        scope=t4["scopes"]["family/"+fam]
        need(scope["n"]==len(ids) and abs(scope["by_role"]["V_COST"]["averages"]["L"]-scope["by_role"]["P"]["averages"]["L"]-summary["mean_delta_s"])<1e-9,
             "scope means and complete family denominator: "+fam)
        pointers=[input_rows[i]["fields"]["delta_s"]["fields"] for i in ids]
        by_family[fam]={**summary,"keys":[historic[i]["key"] for i in ids],
                        "fields":{"family_selector":[f"t4b#/rows/{i}/family" for i in ids],"paired_L":pointers,
                                  "n":"count(paired_L)","sum_delta_s":"sum(V_COST.L-P.L)","mean_delta_s":"sum_delta_s/n",
                                  "exact_mean_fraction":"same mean in rational seconds","better":"count(delta<0)","equal":"count(delta=0)","worse":"count(delta>0)"}}
    cids=groups["COOLING_ACCESS"];rowwise=[]
    for i in cids:
        r=historic[i];base=f"t4b#/rows/{i}";v=F(r["arms"]["V_COST"]["L"])
        fixed=("P","PERIODIC","ALARM"); levels={a:r["arms"][a]["L"] for a in fixed}
        best=min(F(vv) for vv in levels.values())
        rowwise.append({"key":r["key"],"V_L":float(v),"baselines":levels,"best_L":float(best),"V_minus_best":float(v-best),
                        "sources":{a:base+f"/arms/{a}/L" for a in ("V_COST",*fixed)}})
    cf="new#/conditions/*"
    return dict(definition="Absolute complete-window L, in seconds. Delta=V_COST.L-P.L. Strict sign on stored row values; no random sampling.",
        sources=sources,
        v3c=dict(n=len(rows),counts=counts([r["delta_s"] for r in origin_new]),worse_keys=new_bad,keys_named_in_brief=list(NAMED),
                 above_certified_lower_keys=above_bound,all_rows=origin_new,rows_including_named_ties=examples,
                 fields={"n":cf+"/key","counts":[cf+"/arms/V_COST/L",cf+"/arms/P/L"],
                         "worse_keys":"all_rows[delta_s>0].key","above_certified_lower_keys":[cf+"/arms/V_COST/L",cf+"/lower/certified_min",cf+"/key"]}),
        t4b=dict(n=len(historic),counts=counts([r["delta_s"] for r in input_rows]),families=by_family,worse_rows=bad,
                 fields={"n":"t4b#/rows/*/key","counts":"all six families' paired_L; signs on each pair",
                         "worse_rows":"t4b#/rows/* where arms/V_COST/L > arms/P/L"}),
        cooling_comparator_check=dict(fixed_P=by_family["COOLING_ACCESS"]["mean_delta_s"],fixed_P_fields="t4b.families.COOLING_ACCESS.fields.paired_L",
            best_of_status_quo=totals([F(r["V_minus_best"]) for r in rowwise]),rows=rowwise,
            fields={"n":"count(rows)","baselines":"rows/*/sources/{P,PERIODIC,ALARM}","sum_delta_s":"sum(rows/*/V_minus_best)",
                    "mean_delta_s":"sum_delta_s/n","signs":"count signed rows/*/V_minus_best","brief_rounded_seconds":"round(mean_delta_s)"},
            formula="Per row subtract min(P.L,PERIODIC.L,ALARM.L) from V_COST.L, then average over the same 24 rows. Distinct from fixed P."),
        source_note="No v3c results.json.gz in this revision. New-panel scores: new; new-panel actual actions: compact score objects tied to index. T4b's public results.json.gz directly records actual requests and attributed maintenance penalties.")
