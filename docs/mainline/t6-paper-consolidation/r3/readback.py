"""Read immutable local Git objects: distinguish a purchase opportunity from an issued, delivered read."""
from copy import deepcopy
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
T6=HERE.parent
ROOT=T6.parents[2]
PREFIX=T6.relative_to(ROOT).as_posix()+"/"
BASE="21a4624b43812edcd568c1393d4a031368f3af68"
T3="85af7e48b60e61dc453456b5b7bc73ab832900b5"
T4B="3487276af9e9759357771d16eb45feceaa3c948a"
T4C="cef45c0275ce330eaf2652362bfd5090dffd5aa6"
DIR="docs/mainline/t3-prior-information-v2/"
RESULT=DIR+"development-result.json.gz"
INPUTS=DIR+"development-inputs.jsonl.gz"
MANIFEST=DIR+"development-inputs.json"
RECEIPT=DIR+"receipt.json"
HYP="docs/mainline/t4b-holdout-confirmation-v2/results.json.gz"
V_MANIFEST="docs/mainline/t4c-action-cost-v3/dev-manifest.json"
SITES=(("LONDON","5-01"),("NETHERLANDS","6-02"))
BASELINES=("P","PERIODIC","ALARM")
OWNER="用户授权执行者选择"


def need(test,msg):
    if not test:raise ValueError("r3: "+msg)


def git(commit,path):
    return subprocess.check_output(["git","-C",str(ROOT),"show",commit+":"+path])


def pack(obj):
    return (json.dumps(obj,ensure_ascii=False,allow_nan=False,indent=2)+"\n").encode("utf-8")


def sha(raw):return hashlib.sha256(raw).hexdigest()


def pointer(obj,path):
    for k in path.lstrip("/").split("/"):
        k=k.replace("~1","/").replace("~0","~")
        obj=obj[int(k)] if isinstance(obj,list) else obj[k]
    return obj


def ref(commit,path,*fields):
    return dict(commit=commit,path=path,fields=list(fields))


def t3_sources():
    rc=git(T3,RECEIPT);receipt=json.loads(rc)
    archive={};pinned={};key=lambda path:path.rsplit("/",1)[-1]
    for path in (RESULT,MANIFEST,INPUTS):
        b=git(T3,path)
        need(sha(b)==receipt["files_sha256"][key(path)],"digest in accepted T3 receipt: "+path)
        pinned[path]=dict(commit=T3,sha256=sha(b))
        if path==INPUTS: archive[path]=[json.loads(l) for l in gzip.decompress(b).splitlines()]
        else:archive[path]=json.loads(gzip.decompress(b) if path.endswith(".gz") else b)
    need(archive[MANIFEST]["zipped"]==pinned[INPUTS]["sha256"],"original input pack bytes")
    pinned[RECEIPT]=dict(commit=T3,sha256=sha(rc))
    return archive,pinned


def collect():
    base=git(BASE,PREFIX+"stage3/claims.json");prior=json.loads(base);ledger=deepcopy(prior)
    orig_metrics={m["id"]:m for c in prior["claims"] for m in c["numbers"]}
    need(len(orig_metrics)==960,"original ledger size")
    data,assets=t3_sources();results=data[RESULT];inputs=data[INPUTS];manifest=data[MANIFEST]
    need(set(results["roles"])=={"P","PERIODIC","ALARM","ORACLE"} and results["new_method_runs"]==0,"T3 original roster, no V_COST")
    alt_raw=git(T4C,V_MANIFEST);alt=json.loads(alt_raw)
    assets[V_MANIFEST]=dict(commit=T4C,sha256=sha(alt_raw))
    extra=[];reports={}
    def metric(id,label,unit,path,fields,value,op="value",**kwargs):
        need(id not in orig_metrics and id not in {v["id"] for v in extra},"unique supplemental metric")
        val=Fraction(value)
        extra.append(dict(id=id,label=label,unit=unit,commit=T3,path=path,fields=list(fields),op=op,**kwargs,
                          value=int(val) if val.denominator==1 else float(val),exact=str(val)))
        return id
    for family,k in SITES:
        ix=manifest["definitions"]["order"].index(k)
        case=inputs[ix];r=results["rows"][ix];rb=f"/rows/{ix}";xb=f"/{ix}/value/native/dispatch_program";mid=f"C2.r3.{family}.{k}."
        ih=manifest["files"][k];need(case["key"]==r["key"]==k and family==r["family"] and
            sha((json.dumps(case["value"],ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n").encode())==ih,"complete condition/score identity")
        pg=case["value"]["native"]["dispatch_program"];ch=pg["channel"];clock=pg["public"]["clock"];zero=clock[0]
        need(all(a<b for a,b in zip(clock,clock[1:])) and zero==0 and min(pg["public"]["fixed_epochs"])==0,"decision clock")
        pro=r["info"];deadline=r["latest"];at,usable,target,start,sampled=pro["paid"]
        need(start==zero and pro["paid_is_counterfactual_opportunity"] is True and tuple(pro["paid"])==min(map(tuple,pro["all_paid"])),"counterfactual, independent earliest legal purchase")
        proj=[(j,p) for j,p in enumerate(r["unpaid_native_no_action_projection"]) if p["subject"]==target]
        need(len(proj)==1,"one projection for target");j,v=proj[0];pp=rb+f"/unpaid_native_no_action_projection/{j}"
        need((v["start"],v["sampled"],v["would_arrive"],v["usable"])==(start,sampled,at,usable) and v["fields"],"physical non-purchased observation")
        orders=[j for j,e in enumerate(ch) if e["arrived"]<=zero and e["sampled"]<=zero<e["until"]]
        need(orders and all(ch[j]["kind"]=="order" and ch[j]["value"]=="OPEN" for j in orders),"standing orders only at start of public message channel")
        prior_ids=[j for j,e in enumerate(ch) if e["kind"]=="prior" and e["copied_from"] is None]
        first=min(prior_ids,key=lambda j:ch[j]["arrived"]);registered=ch[first]
        need(registered["arrived"]==pro["prior"][0] and registered["origin"]==pro["prior"][2] and pro["prior"][0]>zero and
             r["prior_records"] and min(e["arrived"] for e in r["prior_records"])==pro["prior"][0],"first registered prior")
        dispatch_id=metric(mid+"opportunity.dispatch","评价端反事实可买初检的派工时刻","秒",RESULT,[rb+"/info/paid/3"],start)
        notice_id=f"C2.T3.{family}.{k}_prior";arrival_id=f"C2.T3.{family}.{k}_paid";tau_id=f"C2.T3.{family}.{k}_latest"
        for id,expected in ((notice_id,registered["arrived"]),(arrival_id,at),(tau_id,deadline)):
            need(orig_metrics[id]["value"]==expected,"accepted evidence "+id)
        report=dict(key=k,family=family,panel="T3 public development, same original input bytes",input_sha256=ih,source_row=ref(T3,RESULT,rb),
            input_identity=ref(T3,MANIFEST,"/files/"+k),reference_clock_source=ref(T3,INPUTS,xb+"/public/clock",xb+"/public/fixed_epochs"),
            standing_orders_at_start=[ref(T3,INPUTS,xb+f"/channel/{j}") for j in orders],risk_trigger_present_at_zero=False,
            start_meaning="Only standing OPEN authorizations, no case-specific risk trigger at t=0. A planned periodic round may start without a risk trigger.",
            no_initial_sensor_publication=ref(T3,DIR+"native.py","L55-L74","L140-L145"),
            registered_pre_risk_prior=dict(metric=notice_id,record=registered,source=ref(T3,INPUTS,xb+f"/channel/{first}"),
                                          scope="earliest registered prior (kind=prior); not earliest public datum of every kind"),
            opportunity=dict(dispatch=dispatch_id,arrival=arrival_id,deadline=tau_id,target=target,
                type="EVALUATOR_COUNTERFACTUAL_NOT_AN_ACTUAL_RECEIPT",source=ref(T3,RESULT,rb+"/info/paid",rb+"/info/paid_is_counterfactual_opportunity",pp)),
            roles={},same_named_later_V_COST_input=dict(commit=T4C,path=V_MANIFEST,field="/files/"+k,sha256=alt["files"][k]))
        need(ih!=alt["files"][k],"later V_COST input must not be substituted just because the keys match")
        early_other=[j for j,e in enumerate(ch) if e["kind"] not in ("order","prior") and e["copied_from"] is None and e["arrived"]<registered["arrived"]]
        report["earlier_public_business_records"]=[]
        for j in early_other:
            e=ch[j];need(e["kind"]=="release" and e["value"]=="WORK_OPEN","unexpected earlier non-prior input")
            m=metric(mid+"works_status.arrived","施工未移交业务记录到达","秒",INPUTS,[xb+f"/channel/{j}/arrived"],e["arrived"])
            report["earlier_public_business_records"].append(dict(metric=m,kind=e["kind"],value=e["value"],source=ref(T3,INPUTS,xb+f"/channel/{j}")))
        for role in BASELINES:
            arm=r["arms"][role];basepath=rb+"/arms/"+role;paid=arm["paid"];requests=arm["requests"]
            need(arm["passed"] and arm["key"]==k and arm["role"]==role and arm["input_sha256"]==ih,"role/input binding")
            timely=[];target_timely=[]
            for j,p in enumerate(paid):
                work=[w for w in arm["work"] if w[0]==p["task"]];ticks=[t for t in clock if t>=p["arrived"]]
                need([p["issued"],p["task"]] in requests and len(work)==1 and work[0][1]=="completed" and
                     work[0][2]==p["issued"] and work[0][3]==p["sampled"] and p["issued"]<=p["sampled"]<=p["arrived"] and
                     p["source"]=="onsite/"+p["subject"] and p["origin"]==p["task"]+"@"+format(p["sampled"],"g"),"actual acquired work/receipt")
                if p["fields"] and ticks and p["arrived"]<deadline and ticks[0]<=deadline and ticks[0]<p["until"]:
                    timely.append(j)
                    if p["phase"]=="I" and p["subject"]==target:target_timely.append(j)
            rs=dict(state="有" if timely else "未取得",paid_array=ref(T3,RESULT,basepath+"/paid",basepath+"/requests",basepath+"/work"),
                    deadline=tau_id,qualifying_indices=timely,requested_target_first_index=(target_timely[0] if target_timely else None))
            if timely:
                j=min(timely,key=lambda j:paid[j]["arrived"]);x=paid[j]
                rs["first_received"]=dict(task=x["task"],subject=x["subject"],phase=x["phase"],
                    arrival=metric(mid+role+".first_arrival","本臂实际首份可用的付费读数到达","秒",RESULT,[basepath+f"/paid/{j}/arrived"],x["arrived"]),
                    source=ref(T3,RESULT,basepath+f"/paid/{j}"))
                need(len(target_timely)==1,"single initial read for the named opportunity target")
                j=target_timely[0];x=paid[j]
                rs["target_received"]=dict(task=x["task"],subject=x["subject"],phase=x["phase"],
                    arrival=metric(mid+role+".target_arrival","与机会同一目标的实际初检读数到达","秒",RESULT,[basepath+f"/paid/{j}/arrived"],x["arrived"]),
                    source=ref(T3,RESULT,basepath+f"/paid/{j}"))
            report["roles"][role]=rs
        report["roles"]["V_COST"]=dict(state="未建立",reason="同输入上没有该臂，不能将缺臂编码为未取得或零；不借用别的面板。",
            source=ref(T3,RESULT,"/roles","/new_method_runs",rb+"/arms"))
        need("V_COST" not in r["arms"] and set(r["arms"])==set(results["roles"]),"do not invent a V_COST observation")
        reports[k]=report
    hraw=git(T4B,HYP);hyps=json.loads(gzip.decompress(hraw))["hypotheses"];checklist={}
    for i,h in enumerate(hyps):
        id=f"H{i+1}";need(h["id"]==id and h["decision"]=="MET" and h["comparison"]["metrics"]["L"]["hi"]<0,"sequential frozen MET")
        fields={}
        for name in ("mean","lo","hi"):
            metric_id=f"C1.T4b.{id}.{name}";n=orig_metrics[metric_id];pt=f"/hypotheses/{i}/comparison/metrics/L/{name}"
            need(n["fields"]==[pt] and n["commit"]==T4B and n["path"]==HYP and
                 Fraction(n["exact"])==Fraction(h["comparison"]["metrics"]["L"][name]),"original signed interval "+metric_id)
            fields[name]=metric_id
        checklist[id]=dict(status=h["decision"],level="确认",comparator=h["comparator"],metrics=fields,
                           source=ref(T4B,HYP,f"/hypotheses/{i}/decision",f"/hypotheses/{i}/comparison/metrics/L"))
    assets[HYP]=dict(commit=T4B,sha256=sha(hraw))
    c4=ledger["claims"][3]
    need(c4["id"]=="C4" and "用户授权执行者" in c4["wording_owner"] and ledger["stage3_decision"]["option"]=="A","delegated option A already recorded")
    c4["wording_owner"]=OWNER
    ledger["r3_supplement"]=dict(schema="aegisdc-t6-prose-r3",baseline=BASE,decision="A",wording_owner=OWNER,
        original_numbers_unchanged=True,numbers=extra,conditions=reports,pre_registered_tests=checklist,sources=assets,
        intended_scope="Supplemental observational IDs for the revision only. Existing four claims' numbers, statuses and every counterexample are unchanged.")
    for old,new in zip(prior["claims"],ledger["claims"],strict=True):
        for field,value in old.items():
            if old["id"]=="C4" and field=="wording_owner":continue
            need(new[field]==value,"immutable prior claim field "+field)
    return ledger
