"""C1: paired service and personnel comparisons with first-class counterexamples."""
from fractions import Fraction as F
from claims_sources import BASE, FAMS, NAMES, T4B, T4D, NEW, P4B, P4D, PNEW, P1, require

POST="POSTHOC_MIN_P_PERIODIC_ALARM"
PANELS=(("T4b",T4B,P4B,"/rows",("B","P","PERIODIC","ALARM",POST)),
        ("v3c",NEW,PNEW,"/conditions",("B","P","PERIODIC","ALARM","B_COST")))
SIGNS=("better","equal","worse")


def build(book):
    ledger=dict(id="C1",statement="在 T4b 合成留出面板上，V** 相对预注册强透明规则 B 的平均服务缺额较低。相对巡检和报警的平均缺额及相对巡检的人时须分族判断；逐条件优势未在所有比较中成立。",
        level=["确认","开发"],comparator="主对照 B；P、PERIODIC、ALARM 为并列描述性对照；新板 B_COST 另列。逐行最优使用事后信息。",
        denominator={},numbers=[],failure_conditions=[],counterexamples=[],status="部分成立",
        definitions=dict(loss="V_COST.L 减该对照 L；优/平/劣严格按逐条件未舍入差的负/零/正计，不以工时抵消损失。",
            staff="person 为实际人员占用秒；人力较少的规定对照为周期巡检。另列所有可执行固定对照的人时。",
            simultaneous="按族均值判断：V_COST−PERIODIC 与 V_COST−ALARM 的 L 均严格小于零，且相对 PERIODIC 的平均人员秒严格较少。相等不算优于。",
            evidence="T4b 的 B 检验是原顺序确认；v3c 新面板正式主比较为 S−W。此处的新板 V_COST 比较为描述性。T4d BASE 是独立的公开开发边界。",
            denominator_rule="先按面板及对照列出劣例；同一条件对多个对照变差分别保留。同一面板／对照的整板和分族单元共享反例 ID，不重复计作样本。"),
        panel_tables={},joint_service_and_staff={},subclaims=[],signed_losses_by_panel={})
    nums=ledger["numbers"];bad=ledger["counterexamples"]
    def add(*args,**kw):
        m=book.num(*args,**kw);nums.append(m);return m["id"],m["value"]
    st=book.get(BASE,P1)
    cache={}
    for panel,rev,path,group,roles in PANELS:
        rows=book.get(rev,path)[group[1:]];indices=list(range(len(rows)))
        scopes={"ALL":indices,**{k:[i for i in indices if rows[i]["family"]==k] for k in FAMS}}
        pre=st["C1"][panel]["scopes"];require(set(pre)==set(scopes),"C1 stage-1 family coverage")
        table={};joint={};losses={}
        panel_level="确认" if panel=="T4b" else "确认面板中的描述性读回"
        for scope,ii in scopes.items():
            table[scope]={};losses[scope]={}
            prefix="C1."+panel+"."+scope
            n,_=add(prefix+".n","条件分母","条",rev,path,[group+"/{i}/key"],"count",ii)
            if scope=="ALL":ledger["denominator"][panel]=n
            for role in roles:
                name=prefix+"."+role;entry=pre[scope][role];tot=len(ii)
                require(entry["planned"]==tot,"C1 paired denominator")
                if role=="B" and panel=="v3c":
                    require(all("B" not in rows[i]["arms"] for i in ii) and entry["state"]=="ARM_NOT_PRESENT","no substitution for B")
                    table[scope][role]=dict(state="无该臂",level=panel_level,denominator=n,estimate=None,personnel=None,counterexample_ids=[],
                        absence_source=dict(commit=rev,path=path,fields=[group+f"/{i}/arms" for i in ii]))
                    continue
                controls=("P","PERIODIC","ALARM") if role==POST else (role,)
                fields=[group+"/{i}/arms/"+r+"/L" for r in ("V_COST",*controls)]
                scale="确认主比较" if (panel,role)==("T4b","B") else "事后描述性参照，非可部署" if role==POST else "描述性"
                est,v=add(name+".loss_mean","配对平均服务缺额差","秒",rev,path,fields,"mean_delta",ii)
                require(F(nums[-1]["exact"])==F(entry["mean"]["fraction"]),"C1 original vs accepted stage-1 mean "+name)
                sign_ids={}
                for op in SIGNS:
                    sign_ids[op],nc=add(name+"."+op,"逐条件"+{"better":"优","equal":"平","worse":"劣"}[op],"条",rev,path,fields,op,ii)
                    require(nc==entry[op],"C1 original vs stage-1 signs "+name)
                worse=[]
                for i in ii:
                    r=rows[i];arms=r["arms"];least=min(F(arms[q]["L"]) for q in controls);vL=F(arms["V_COST"]["L"])
                    if vL<=least:continue
                    chosen=[q for q in controls if F(arms[q]["L"])==least]
                    rid=f"C1.{panel}.{role}.{r['key']}";worse.append(rid)
                    if scope!="ALL":continue
                    base=group+f"/{i}";cand_field=base+"/arms/V_COST/L";cmp_field=base+"/arms/"+chosen[0]+"/L"
                    x,_=add(rid+".V_L","V_COST 实际 L","秒",rev,path,[cand_field])
                    y,_=add(rid+".comparator_L","对照实际 L","秒",rev,path,[cmp_field])
                    z,_=add(rid+".delta","严格劣行的 V_COST−对照","秒",rev,path,[cand_field,cmp_field],"subtract")
                    rec=dict(id=rid,panel=panel,level=panel_level,family=r["family"],key=r["key"],candidate="V_COST",comparator=role,
                        definition=scale,V_L=x,comparator_L=y,delta=z,metrics=[x,y,z],source=book.ref(rev,path,base),scopes=["ALL",r["family"]])
                    if role==POST:
                        rec.update(posthoc=True,minimum_roles=chosen,alternative_fields=[book.ref(rev,path,base+"/arms/"+q+"/L") for q in controls])
                    bad.append(rec)
                require([x.rsplit(".",1)[-1] for x in worse]==entry["worse_keys"],"every strict loss agrees with accepted stage-1 roster")
                people=None;pd=None
                if role!=POST:
                    pf=[p[:-1]+"person" for p in fields]
                    pv,av=add(name+".staff_V","V_COST 平均实际人员占用","人秒",rev,path,[pf[0]],"mean",ii)
                    pb,ab=add(name+".staff_control","对照平均实际人员占用","人秒",rev,path,[pf[1]],"mean",ii)
                    ident,pd=add(name+".staff_delta","平均实际人员占用差","人秒",rev,path,pf,"mean_delta",ii)
                    people=dict(V=pv,control=pb,delta=ident)
                table[scope][role]=dict(state="已取得",comparison_role=scale,level=panel_level,denominator=n,estimate=est,
                    directions=sign_ids,personnel=people,counterexample_ids=worse)
                cache[panel,scope,role]=(v,pd)
                losses[scope][role]=len(worse)
            p,sp=cache[panel,scope,"PERIODIC"];a,_=cache[panel,scope,"ALARM"]
            joint[scope]=dict(service_better_than_periodic=p<0,service_better_than_alarm=a<0,less_staff_than_periodic=sp<0,
                all_three=p<0 and a<0 and sp<0,level=panel_level,denominator=n,
                metrics=[table[scope]["PERIODIC"]["estimate"],table[scope]["ALARM"]["estimate"],table[scope]["PERIODIC"]["personnel"]["delta"]],
                reading=("两项服务均差均为负，且平均工时少于周期巡检。" if p<0 and a<0 and sp<0 else
                         "工时须与服务分别判断；本族未同时取得两项严格服务改善和规定的工时减少。"))
        ledger["panel_tables"][panel]=table;ledger["joint_service_and_staff"][panel]=joint
        ledger["signed_losses_by_panel"][panel]=losses["ALL"]
    # Retain the original T4b sequential tests and their frozen intervals, not new confidence intervals.
    htests=book.get(T4B,P4B)["hypotheses"];ledger["T4b_sequential_confirmations"]=[]
    for i,h in enumerate(htests):
        base=f"/hypotheses/{i}";pre="C1.T4b."+h["id"];ids={}
        for a in ("mean","lo","hi"):
            ids[a],_=add(pre+"."+a,"封存的 L 配对 "+a,"秒",T4B,P4B,[base+"/comparison/metrics/L/"+a])
        ids["pairs"],_=add(pre+".n","有效配对","条",T4B,P4B,[base+"/comparison/available"])
        ledger["T4b_sequential_confirmations"].append(dict(test=h["id"],comparator=h["comparator"],level="确认",metrics=ids,original_decision=h["decision"],
            decision_source=book.ref(T4B,P4B,base+"/decision"),interval="原面板已封存的双侧 95% 区间；未重抽"))
    # B-P in T4d is about the comparator, not a V_COST outcome; its denominator stays separate.
    t4=book.get(T4D,P4D)["panels"]["BASE"];ii=list(range(len(t4)));bf="/panels/BASE/{i}/arms/"
    n,_=add("C1.T4d.BASE.n","原开发面板 B−P 分母","条",T4D,P4D,["/panels/BASE/{i}/key"],"count",ii)
    cnt,val=add("C1.T4d.BASE.worse","B 比 P 差的条件数","条",T4D,P4D,[bf+"B/L",bf+"P/L"],"worse",ii)
    require(val==st["T4d"]["worse"],"T4d BASE checked against stage 1")
    ledger["denominator"]["T4d.BASE"]=n;ledger["T4d_B_vs_P"]=dict(level="开发",comparator="B−P；原 BASE，不与敏感性或 V_COST 合并",denominator=n,worse=cnt)
    for i,r in enumerate(t4):
        if r["arms"]["B"]["L"]<=r["arms"]["P"]["L"]:continue
        base=f"/panels/BASE/{i}";rid="C1.T4d.B_vs_P."+r["key"]
        metrics=[]
        a=base+"/arms/B/L";b=base+"/arms/P/L"
        for suffix,fl,op in (("B_L",[a],"value"),("P_L",[b],"value"),("delta",[a,b],"subtract")):
            ident,_=add(rid+"."+suffix,suffix,"秒",T4D,P4D,fl,op);metrics.append(ident)
        bad.append(dict(id=rid,panel="T4d.BASE",level="开发",family=r["family"],key=r["key"],candidate="B",comparator="P",
                        metrics=metrics,delta=metrics[-1],source=book.ref(T4D,P4D,base)))
    tab=ledger["panel_tables"];cool=tab["T4b"]["COOLING_ACCESS"]["PERIODIC"];dutch=tab["T4b"]["NETHERLANDS"]["B"]
    def subset(id,stmt,comp,den,metric_ids,examples,fail,scope,status):
        return dict(id=id,statement=stmt,level="确认",scope=scope,comparator=comp,denominator=den,numbers=metric_ids,
                    failure_conditions=fail,counterexamples=examples,status=status)
    main=tab["T4b"]["ALL"]["B"]
    ledger["subclaims"].append(subset("C1.B","T4b 全板平均 L 低于强透明 B；该方向不能逐条件成立。","V_COST−B",
        main["denominator"],[main["estimate"],*main["directions"].values(),dutch["directions"]["worse"],"C1.T4b.H1.lo","C1.T4b.H1.hi"],
        main["counterexample_ids"],[dict(condition="荷兰式族有 10 条 V_COST 缺额大于 B；全板严格劣行共 14 条。",
            metrics=[dutch["directions"]["worse"],main["directions"]["worse"]],counterexamples=dutch["counterexample_ids"])],"T4b","部分成立"))
    joint_fail=[]
    for panel in ("T4b","v3c"):
        by=ledger["joint_service_and_staff"][panel]
        for f in FAMS:
            if by[f]["all_three"]:continue
            row=tab[panel][f]["PERIODIC"];clause=("T4b 冷却与通行族对巡检平均多 37.29 秒（1优/20平/3劣）；平均人员占用较少，不能抵消服务缺额。" if panel=="T4b" and f=="COOLING_ACCESS" else
                        "新板冷却与通行族对巡检、报警均全族持平；人时较少仍不满足服务严格改善。" if panel=="v3c" and f=="COOLING_ACCESS" else "本族不满足全部三个均值条件。")
            joint_fail.append(dict(panel=panel,family=f,condition=clause,metrics=[*by[f]["metrics"],*row["directions"].values()],counterexamples=row["counterexample_ids"]))
    conds=[e["id"] for e in bad if e["panel"] in ("T4b","v3c") and e["comparator"] in ("PERIODIC","ALARM")]
    ledger["subclaims"].append(subset("C1.现状联合","全板平均同时优于巡检、报警且比巡检省工；逐族并非全部成立。","V_COST 对 PERIODIC 与 ALARM 的服务差；V_COST 对 PERIODIC 的人时差",
        {p:tab[p]["ALL"]["PERIODIC"]["denominator"] for p in tab},
        [s for p in tab for s in ledger["joint_service_and_staff"][p]["ALL"]["metrics"]],conds,joint_fail,"T4b 留出与新板描述性比较，分别判断","部分成立"))
    ledger["failure_conditions"]=[
        dict(condition="荷兰式族的主对照 B 比较有严格劣行，强规则的全板均差不保证每个条件获益。",metrics=[main["directions"]["worse"],dutch["directions"]["worse"]],applies_to="C1.B"),
        dict(condition="冷却与通行族是“优于巡检且更省工”的边界；不能把服务和工时折为一个胜负。",metrics=[cool["estimate"],*cool["directions"].values(),cool["personnel"]["delta"]],applies_to="C1.现状联合"),
        dict(condition="新板没有 B 臂，不能检验 V_COST 相对强透明 B；B_COST 和事后最优现状均不是 B。",source=book.ref(BASE,P1,"/C1/v3c/scopes/ALL/B/state"))]
    return ledger
