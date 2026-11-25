"""T6 stage 2: construct or read-only audit the claims ledger, including all loss rows."""
import sys
sys.dont_write_bytecode=True

import argparse
from collections import Counter
from fractions import Fraction as F
import json

from claims_sources import BASE,OUT,ROOT,T4B,T4D,NEW,OLD,P4B,P4D,PNEW,POLD,P1,FAMS,Book,require,packed,sha,revision,roster,git_bytes

SCHEMA="aegisdc-t6-claims-stage2-v1"
FILES=("claims.json","claims-stage2.md","claims-review-draft.md","claims-review.html","claims-verification.txt","claims_check.py",
       "claims_sources.py","claims_comparisons.py","claims_incidents.py","claims_improvement.py","claims_headroom.py","claims_review.py")


def build(book):
    from claims_comparisons import build as one
    from claims_incidents import build as two
    from claims_improvement import build as three
    from claims_headroom import build as four
    claims=[b(book) for b in (one,two,three,four)]
    return dict(schema=SCHEMA,stage="T6.2",accepted_baseline=BASE,
        scope="主张台账待审。完整八域合成设施是方法研究对象；事故族只为有限验证材料。分开列开发、确认及确认面板的描述性读回，不合并分母。",
        how_to_read="每条主张的 numbers 以稳定 ID 标识。commit/path/fields 定位原件，rows 精确列出占位 {i} 的零基源索引。"
            "exact 是未舍入的有理数。表内反例按面板、候选、对照、条件键识别；同一行可以属于不同对照。统计未重新抽样。",
        sources=sorted(book.files.values(),key=lambda x:(x["path"],x["commit"])),claims=claims,
        execution=dict(facility_calls=0,slurm_jobs=0,H2_generated=0,H2_read=0,H2_derived=0,retries=0,
                       stage3_started=False,completion="DELIVERED_AWAITING_REVIEW",next_stage_authorized=False))


def refs_in_text(obj,book):
    """Fail closed on a stale JSON-pointer or line reference, including qualitative annotations."""
    if isinstance(obj,dict):
        if {"commit","path","field"}<=obj.keys():book.ref(obj["commit"],obj["path"],obj["field"])
        for k,v in obj.items():
            if k!="numbers":refs_in_text(v,book)
    elif isinstance(obj,list):
        for v in obj:refs_in_text(v,book)


def audit_c1(book,c,m):
    """A second path: compare raw L row by row; never trust a rendered loss count as its roster."""
    stage=book.get(BASE,P1)
    actual={}
    for e in c["counterexamples"]:
        k=(e["panel"],e["comparator"],e["key"]);require(k not in actual,"duplicate C1 comparator/condition")
        actual[k]=e
    expect=set();counts={};numcells=0;staffcells=0
    for panel,rev,path,group,comps in [
        ("T4b",T4B,P4B,"rows",["B","P","PERIODIC","ALARM","POSTHOC_MIN_P_PERIODIC_ALARM"]),
        ("v3c",NEW,PNEW,"conditions",["B","P","PERIODIC","ALARM","B_COST"])]:
        data=book.get(rev,path)[group];table=c["panel_tables"][panel];counts[panel]=Counter()
        keys={r["key"]:r for r in data};require(len(keys)==len(data),"unique original rows")
        for scope in ("ALL",*FAMS):
            rows=[r for r in data if r["family"]==scope or scope=="ALL"];tab=table[scope]
            for role in comps:
                cell=tab[role];accepted=stage["C1"][panel]["scopes"][scope][role];numcells+=1
                if role=="B" and panel=="v3c":
                    require(all("B" not in r["arms"] for r in rows) and cell["estimate"] is None and
                            cell["personnel"] is None and cell["state"]=="无该臂" and accepted["pairs"]==0,"do not impute B");continue
                require(cell["formal_L_test"]==((panel,scope,role)==("T4b","ALL","B")),"formal test only on prespecified full-panel endpoint")
                vals=[];bad=[];post=role.startswith("POSTHOC_")
                for r in rows:
                    arms=r["arms"];cv=min(F(arms[k]["L"]) for k in ("P","PERIODIC","ALARM")) if post else F(arms[role]["L"])
                    delta=F(arms["V_COST"]["L"])-cv;vals.append(delta)
                    if delta<=0:continue
                    k=(panel,role,r["key"]);expect.add(k);e=actual[k];bad.append(e["id"])
                    require(e["family"]==r["family"] and m[e["delta"]]==delta and m[e["V_L"]]==F(arms["V_COST"]["L"])
                            and m[e["comparator_L"]]==cv,"exhaustive loss row, true role and operands: "+e["id"])
                require(bad==cell["counterexample_ids"] and sorted(accepted["worse_keys"])==sorted(a.rsplit(".",1)[-1] for a in bad),
                        "full and family loss membership")
                require(m[cell["estimate"]]==F(accepted["mean"]["fraction"])==sum(vals,F())/len(rows),"stored stage-1 and independent original exact mean")
                if scope=="ALL":counts[panel][role]=len(bad)
                if not post:
                    people=cell["personnel"];vmean=sum(F(r["arms"]["V_COST"]["person"]) for r in rows)/len(rows)
                    bmean=sum(F(r["arms"][role]["person"]) for r in rows)/len(rows)
                    require(m[people["V"]]==vmean and m[people["control"]]==bmean and m[people["delta"]]==vmean-bmean,"actual staffing per family")
                    staffcells+=1
            pair=c["joint_service_and_staff"][panel][scope]
            require("描述性" in pair["evidence_use"] and "描述性" in tab["PERIODIC"]["personnel"]["evidence_use"],"do not promote status quo and staff readbacks to formal endpoints")
            truth=[m[tab["PERIODIC"]["estimate"]]<0,m[tab["ALARM"]["estimate"]]<0,m[tab["PERIODIC"]["personnel"]["delta"]]<0]
            require(truth==[pair[k] for k in ("service_better_than_periodic","service_better_than_alarm","less_staff_than_periodic")]
                    and pair["all_three"]==all(truth),"strict family joint criterion")
    rows=book.get(T4D,P4D)["panels"]["BASE"];t4d=0
    for r in rows:
        a,b=F(r["arms"]["B"]["L"]),F(r["arms"]["P"]["L"])
        if a<=b:continue
        k=("T4d.BASE","P",r["key"]);expect.add(k);item=actual[k];t4d+=1
        require(item["candidate"]=="B" and item["family"]==r["family"] and m[item["delta"]]==a-b,"development comparator B-P")
    require(set(actual)==expect and t4d==stage["T4d"]["worse"],"missing/extra/duplicated C1 counterexample")
    subs={s["id"]:s for s in c["subclaims"]}
    primary=subs["C1.B"];joint=subs["C1.现状联合"]
    require(primary["status"]==joint["status"]=="部分成立" and c["status"]=="部分成立" and
            primary["level"]=="确认" and joint["level"]=="确认面板中的描述性读回","primary and descriptive joint conditional status")
    dutch=c["panel_tables"]["T4b"]["NETHERLANDS"]["B"]
    require(len(dutch["counterexample_ids"])==10 and any(set(f["counterexamples"])==set(dutch["counterexample_ids"]) for f in primary["failure_conditions"]),
            "Dutch B losses must limit the claim itself")
    cool=c["panel_tables"]["T4b"]["COOLING_ACCESS"]["PERIODIC"]
    require(F(895,24)==m[cool["estimate"]] and [m[cool["directions"][k]] for k in ("better","equal","worse")]==[1,20,3]
            and any(f["panel"]=="T4b" and f["family"]=="COOLING_ACCESS" and cool["estimate"] in f["metrics"] for f in joint["failure_conditions"]),"cooling vs periodic qualifies joint claim")
    return counts,t4d,numcells,staffcells


def audit_c4(book,c,m):
    require(c["statement"]=="" and c["status"]=="未建立" and c["sections"][2]["level"]=="确认面板中的描述性读回","C4 wording reserved; W readback is descriptive")
    require("事后信息，非可部署策略" in c["sections"][1]["reading"] and len(c["sections"])==3,"three mandatory, separate items")
    old=book.get(OLD,POLD)["conditions"];new=book.get(NEW,PNEW)["conditions"];pools=roster(book)
    for (name,pool),members in zip(c["pools"].items(),pools,strict=True):
        require(pool["members"]==members,"exact roster")
        scores=[(sum((F(r["arms"][role]["L"])-F(r["minimum"]["certified_min"]) for r in old),F())/len(old),i,role) for i,role in enumerate(members)]
        scores.sort();first,second=scores[:2]
        retrospective=sum(min(F(r["arms"][l]["L"])-F(r["minimum"]["certified_min"]) for l in members) for r in old)/len(old)
        require((first[2],second[2])==("MAIN-R-3","Q22") and m[pool["fixed_first_gap"]]==first[0] and m[pool["fixed_second_gap"]]==second[0] and
                m[pool["retrospective_gap"]]==retrospective==0 and m[pool["conditional_room"]]==first[0]-retrospective,"both min/mean orders and conditional headroom")
    newg=[F(r["arms"]["W"]["L"])-F(r["lower"]["certified_min"]) for r in new]
    require(len(newg)==36 and all(r["arms"]["W"]["entry"]["actual"]=="MAIN-R-3" for r in new) and all(v==0 for v in newg)
            and m["C4.new.room"]==0 and m["C4.new.attained"]==36,"new W exact attainment, not only tolerance")
    a=book.get(BASE,P1)["C4"];require(set(a["old_R3_room"])=={v["key"] for v in c["counterexamples"]} and
        m["C4.old.attained"]==a["old_R3_attained"] and m["C4.old.above"]==len(a["old_R3_room"]),"old room witnesses")


def audit(book,obj):
    require(obj["schema"]==SCHEMA and obj["accepted_baseline"]==BASE,"claims release identity")
    claims=obj["claims"];require([c["id"] for c in claims]==["C1","C2","C3","C4"],"four claims")
    summary=[];numeric={}
    fields={"id","statement","level","comparator","denominator","numbers","failure_conditions","counterexamples","status"}
    for c in claims:
        require(fields<=c.keys() and c["numbers"] and c["status"] in ("部分成立","成立","不成立","未建立"),"complete schema "+c["id"])
        values={}
        for n in c["numbers"]:
            id=n["id"];require(id.startswith(c["id"]+".") and id not in numeric and n["commit"]==revision(n["commit"])
                                and n["unit"] and n["label"] and n["fields"],"unique, pinned metric "+id)
            exact=book.value(n);require(str(exact)==n["exact"] and n["value"]==(int(exact) if exact.denominator==1 else float(exact)),"reading metric "+id)
            if "display" in n and n["unit"] in ("比例","比例差"):
                expected=format(float(exact),".2%") if n["unit"]=="比例" else f"{float(exact)*100:.2f} 个百分点"
                require(n["display"]==expected,"displayed percentage or percentage-point change "+id)
            numeric[id]=values[id]=exact
        refs_in_text(c,book)
        summary.append((c["id"],len(values),len(c["counterexamples"])))
    require(all(sha(book.raw(s["commit"],s["path"]))==s["sha256"] for s in obj["sources"]),"all source hashes")
    counts,t4d,ncells,staff=audit_c1(book,claims[0],numeric)
    audit_c4(book,claims[3],numeric)
    numeric_sources={(n["commit"],n["path"]) for c in claims for n in c["numbers"]}
    return dict(summary=summary,counts={k:sum(v.values()) for k,v in counts.items()},t4d=t4d,loss_cells=ncells,staff_cells=staff,
                total_metrics=len(numeric),numeric_sources=len(numeric_sources),sources=len(obj["sources"]))


def transcript(report):
    n=report["counts"];first=report["summary"][0]
    lanes="; ".join(f"{id}={m} metrics/{e} counterexamples" for id,m,e in report["summary"])
    return "\n".join([
        "Stage 2 ledger: C1, C2, C3, C4; required claim fields present.",
        f"Numeric readback: {report['total_metrics']} unique metrics, {report['numeric_sources']} numeric Git sources; {report['sources']} sealed sources including protocols, code and context.",
        lanes+".",
        f"C1: {report['loss_cells']} board/family comparison cells including absent B; {report['staff_cells']} fixed-arm staffing cells verified from original person seconds.",
        f"C1 strict-loss coverage: T4b={n['T4b']}, v3c={n['v3c']}, T4d BASE B>P={report['t4d']}; {first[2]} panel/comparator/condition records, no missing or spurious rows.",
        "C1 partial conditions: T4b cooling vs periodic +37.29 s (1/20/3); Netherlands vs B 10 worse; both attached to the corresponding claims.",
        "C4: both 54/58-role rosters rank MAIN-R-3 82.03 s first, Q22 86.67 s second; post-hoc gap 0.00 s is non-deployable; old conditional room 82.03 s.",
        "C4: old MAIN-R-3 at bound 32/36, 4 residual rows; new W=MAIN-R-3 at bound 36/36, conditional room 0.00 s; status=未建立, statement empty.",
        "Gate: stage 2 delivered for review. Manuscript not started. Facility=0; Slurm=0; H2 generated/read/derived=0."])+"\n"


def command():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    m.add_argument("--build",action="store_true",help="write the stage-2 ledger and source drafts")
    m.add_argument("--seal",action="store_true",help="bind checked HTML and stage-2 files after rendering")
    m.add_argument("--check",action="store_true",help="read-only verification; no files or caches are written")
    args=p.parse_args()
    parser_path=OUT/"stage1_report.py";rel=parser_path.relative_to(ROOT).as_posix()
    require(parser_path.read_bytes()==git_bytes(BASE,rel),"accepted stage-1 visible table parser bytes before import")
    from claims_review import documents,check_html
    book=Book();generated=build(book)
    file=OUT/"claims.json"
    if args.build:
        data=generated
    else:
        data=json.loads(file.read_bytes())
        # Audit the recorded numbers themselves before verifying the name/row/section semantics by independent reconstruction.
    checks=audit(book,data)
    require(data==generated,"persisted ledger differs from reconstruction (including statements, scope and exclusions)")
    require(set(book.files)=={(s["commit"],s["path"]) for s in data["sources"]},"complete immutable source inventory")
    report,draft=documents(data)
    products={"claims.json":packed(data),"claims-stage2.md":report.encode(),"claims-review-draft.md":draft.encode()}
    if args.build:
        for name,b in products.items():(OUT/name).write_bytes(b)
        print("Prepared stage 2 ledger and review draft (no research execution).")
        return
    for name,b in products.items():require((OUT/name).read_bytes()==b,"recorded document/ledger bytes: "+name)
    check_html(OUT/"claims-review.html",data)
    out=transcript(checks)
    if args.seal:(OUT/"claims-verification.txt").write_bytes(out.encode("utf8"))
    else:require((OUT/"claims-verification.txt").read_bytes()==out.encode("utf8"),"full saved verification transcript")
    manifest=dict(schema="aegisdc-t6-claims-delivery-v1",accepted_baseline=BASE,files={f:sha((OUT/f).read_bytes()) for f in FILES},
                  inherited_reader=dict(commit=BASE,path=rel,sha256=sha(git_bytes(BASE,rel))),
                  operations="Standard-library readback of immutable git show objects; no new model scores, bootstrap draws or Slurm allocations.",
                  html_renderer="answer-me-with-html 0.6.4 (Node 24.22.3); LF delivery",stopped="AWAITING_STAGE_2_REVIEW")
    if args.seal:(OUT/"claims-delivery.json").write_bytes(packed(manifest))
    else:require((OUT/"claims-delivery.json").read_bytes()==packed(manifest),"stage-2 durable file hashes")
    print(out,end="")


if __name__=="__main__":command()
