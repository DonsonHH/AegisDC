"""Stage 2 review views. Exact unrounded values and original row pointers live in claims.json."""
from claims_sources import NAMES
from stage1_report import VisibleTables

ROLE={"B":"强透明 B","P":"既有保护 P","PERIODIC":"周期巡检","ALARM":"报警响应","B_COST":"B_COST（补充）",
      "POSTHOC_MIN_P_PERIODIC_ALARM":"事后逐行最优"}


def _table(head,rows):
    return tuple(map(str,head)),[tuple(map(str,row)) for row in rows]


def _md(t):
    a,b=t
    row=lambda xs:"| "+" | ".join(xs)+" |"
    return "\n".join([row(a),row(["---"]*len(a)),*(row(r) for r in b)])


def make(data):
    c1,c2,c3,c4=data["claims"];n={v["id"]:v["value"] for c in data["claims"] for v in c["numbers"]}
    def val(id,signed=False):
        v=n[id];return (f"{v:+.2f}" if signed and v else f"{v:.2f}").replace("-","−")
    def dirs(cell):
        return "/".join(str(n[cell["directions"][k]]) for k in ("better","equal","worse"))
    tables={}
    tables["status"]=_table(("主张","状态","本阶段记录"),[
        ("C1","部分成立","T4b 全板的 B 主比较成立；荷兰式的逐行服务差，以及冷却与通行族对巡检的退化，限制了适用范围。"),
        ("C2",c2["status"],"伦敦式、荷兰式机制与完整设施研究单列；作用取决于可见证据、许可、窗口与真实执行。"),
        ("C3",c3["status"],"固定普通改进的开发结果与新面板确认分列，不把人工参照或有利开发成绩记成新板优势。"),
        ("C4",c4["status"],"statement 为空。只登记两块面板的数值依据，等用户裁决。")])
    scores=[];staff=[];joint=[]
    for panel,tab in c1["panel_tables"].items():
        for scope,t in tab.items():
            sc="全板" if scope=="ALL" else NAMES[scope]
            for role,c in t.items():
                if scope=="ALL":
                    scores.append((panel,ROLE[role],n[c["denominator"]],val(c["estimate"],True) if c["estimate"] else "无该臂",
                                   dirs(c) if c["estimate"] else "—", "主对照" if role=="B" else "描述性"))
            per=t["PERIODIC"];al=t["ALARM"];p=per["personnel"];ap=al["personnel"]
            staff.append((panel,sc,n[per["denominator"]],val(p["V"]),val(p["control"]),val(p["delta"],True),
                          val(ap["control"]),val(ap["delta"],True)))
            joint.append((panel,sc,val(per["estimate"],True),dirs(per),val(al["estimate"],True),dirs(al),
                          "三项均满足" if c1["joint_service_and_staff"][panel][scope]["all_three"] else "部分成立"))
    tables["board"]=_table(("面板","对照","原分母","V_COST−对照（秒）","优／平／劣","用途"),scores)
    tables["joint"]=_table(("面板","范围","对巡检 L 差","优／平／劣","对报警 L 差","优／平／劣","联合条件"),joint)
    tables["staff"]=_table(("面板","范围","分母","V_COST 人秒","巡检人秒","相对巡检差","报警人秒","相对报警差"),staff)
    for panel,tab in c1["panel_tables"].items():
        rows=[]
        for f in NAMES:
            for role,c in tab[f].items():
                rows.append((NAMES[f],ROLE[role],n[c["denominator"]],val(c["estimate"],True) if c["estimate"] else "无该臂",
                             dirs(c) if c["estimate"] else "—"))
        tables[panel]=_table(("族","对照","分母","L 均差（秒）","优／平／劣"),rows)
    ce=[]
    for e in c1["counterexamples"]:
        ce.append((e["panel"],NAMES[e["family"]],e["key"],e["candidate"],ROLE.get(e["comparator"],e["comparator"]),
                   val(e["metrics"][0]),val(e["metrics"][1]),val(e["delta"],True)))
    tables["exceptions"]=_table(("面板","族","条件","候选","对照","候选 L","对照 L","多出的缺额（秒）"),ce)
    incident=[]
    for f in ("LONDON","NETHERLANDS"):
        k="C2.T3."+f
        incident.append((NAMES[f]+" T3","开发","P／巡检／报警／合法全知的平均 L（秒）",
                         "／".join(val(k+".mean_"+role) for role in ("P","PERIODIC","ALARM","ORACLE"))))
        k="C2.T4b."+f
        incident.append((NAMES[f]+" T4b","确认面板，分族描述","V_COST−B 平均 L 及原分族区间（秒）",
                         val(k+".mean",True)+" ["+val(k+".lo",True)+", "+val(k+".hi",True)+"]"))
    for key,desc in (("dev19","R6 公开开发"),("ext35","R6 同账号有限扩展")):
        pre="C2.R6."+key+"."
        incident.append((desc,"开发","合规／计划；I 对 D 的优／平／劣",
                         f"{n[pre+'valid']}/{n[pre+'all']}；"+"/".join(str(n[pre+"D_"+i]) for i in ("better","equal","worse"))))
    incident.extend([("V6 首片","公开设计的有限研究","V 对 D 服务持平／可判配对",f"{n['C2.V6.first.equal']}/{n['C2.V6.first.pairs']}"),
        ("V6 冷态 A04","公开设计的有限研究","J−B 服务缺额（秒）",f"{n['C2.V6.cold.A04_delta']:+g}".replace("-","−")),
        ("V6 冷态 B08","公开设计的有限研究","J−B 服务缺额（秒）",f"{n['C2.V6.cold.B08_delta']:+g}".replace("-","−"))])
    tables["incidents"]=_table(("材料","层级","核实事项","结果"),incident)
    stages=c3["evidence_by_stage"]
    k3=lambda k:val("C3."+k,True)
    pts={"v1":"相对 V** "+k3("v1.V_COST.mean")+" 秒。","v2":"U−R "+k3("v2.R.mean")+" 秒。",
         "v3a":f"回收率 {100*n['C3.v3a.k6.recovery']:.2f}% 到 {100*n['C3.v3a.k24.recovery']:.2f}%。",
         "v3b":"重组差 "+k3("v3b.delta.mean")+" 秒，单侧上界 "+k3("v3b.delta.hi")+" 秒。",
         "v3c_dev":"S−整板 "+k3("v3c_dev.delta.mean")+" 秒，单侧上界 "+k3("v3c_dev.delta.hi")+" 秒。",
         "v3c_new":"S−W "+k3("v3c_new.delta.mean")+" 秒，双侧区间 ["+k3("v3c_new.delta.lo")+", "+k3("v3c_new.delta.hi")+"] 秒。"}
    tables["improvement"]=_table(("工作包","层级","数值与读法"),[(k,v["level"],pts[k]+v["finding"]) for k,v in stages.items()])
    fixed=c4["pools"]["fixed54"]
    tables["rsi"]=_table(("证据量","封存读回","解释"),[
        ("旧板固定排名第一",val(fixed["fixed_first_gap"])+" 秒","MAIN-R-3；同一套策略覆盖全板。"),
        ("旧板固定排名第二",val(fixed["fixed_second_gap"])+" 秒","Q22；54 项、58 项两套名册均相同。"),
        ("旧板逐行最低的平均剩余",val(fixed["retrospective_gap"])+" 秒","事后信息，非可部署策略。"),
        ("旧板相对最佳固定的条件化余量",val(fixed["conditional_room"])+" 秒","衡量换向量可能释放的空间，不是已取得的收益。"),
        ("旧板 MAIN-R-3 贴界",f"{n['C4.old.attained']}/{n['C4.old.n']}","其余："+ "、".join(e["key"] for e in c4["counterexamples"])+"。"),
        ("新板 W 贴界",f"{n['C4.new.attained']}/{n['C4.new.n']}","已认证下界与 W 的实际 L 逐行相等。"),
        ("新板相对 W 的条件化余量",val("C4.new.room")+" 秒","仅指同一批条件、同一服务端点和合法动作范围。")])
    return tables


def documents(data):
    tab=make(data);c1,c2,c3,c4=data["claims"]
    intro="阶段 2 只交主张台账。C1 主对照仍是强透明规则 B；事故证据、普通改进和 RSI 分开记录。C4 保留空 statement。"
    word=["# T6 阶段 2：主张台账交审","",intro,"",_md(tab["status"]),"",
          "## C1　主比较及成立条件","",c1["statement"],"",
          "T4b 的全板 V_COST−B 为 −343.90 秒，封存双侧 95% 区间为 [−445.94, −244.22] 秒。"
          "荷兰式族 24 条中有 10 条比 B 差；台账将这些行挂在主对照的“部分成立”条件下。"
          "v3c 新板没有 B 臂，不能用 B_COST 替代；本表的新板结果是相对于各现状的描述性比较。",
          "",_md(tab["board"]),"","### 按族同时核对服务和人时","",
          "先分别比较每族 V_COST 对巡检、报警的平均 L，再比较 V_COST 与巡检的平均人员秒。"
          "T4b 冷却与通行族虽比巡检省工，但平均多 37.29 秒服务缺额（1 优、20 平、3 劣）。"
          "新板同族对巡检和报警均持平，不能称为服务优于二者。其他族均值通过不代表其每个条件都改善。",
          "",_md(tab["joint"]),"",_md(tab["staff"]),"","### 所有分族对照","",
          "T4b 留出确认面板：","",_md(tab["T4b"]),"","v3c 新面板：","",_md(tab["v3c"]),
          "","### 反例逐条件索引","","表中每行对应 claims.json 的 C1.counterexamples 一项。多个对照可以共享一条原条件。"
          "整板与分族表按同一个反例 ID 引用；T4d 是 B−P 的开发反例，单列候选列。事后逐行最优取 P、巡检、报警的最小 L。",
          "",_md(tab["exceptions"]),"","## C2　伦敦式与荷兰式有限机制","",c2["statement"],"",_md(tab["incidents"]),
          "","C2 的数值、失效条件及定位见机器台账的 C2.numbers、failure_conditions 与 counterexamples。"
          "原生首片的 V−D 和冷态的 J−B 分开；A04 和 B08 两个方向均来自冷态，不能移到首片或历史事故。",
          "","## C3　普通改进","",c3["statement"]+" 该命题在新板未成立。","",_md(tab["improvement"]),
          "","## C4　证据就位，措辞待决","","状态为“未建立”，statement 为空。","",_md(tab["rsi"]),
          "","## 如何逐项复核","","[主张台账](claims.json)的每个 numbers 条目含数值 ID、未舍入有理数、单位、提交、仓库路径、字段及运算。"
          "rows 与字段内 {i} 展开为确切源行；比较差均为候选减对照。counterexamples 通过 ID 回指这些数值。"
          "运行 python docs/mainline/t6-paper-consolidation/claims_check.py --check，只用标准库及 git show 读取封存文件。",
          "","与阶段 2 任务书及补充口径的数值差异：无。在旧板，把逐行事后择优和全板固定策略分别列账，不能互换。",
          "","[完整核验输出](claims-verification.txt) · [交付清单](claims-delivery.json) · [HTML 审阅页](claims-review.html)。"
          "本轮设施、Slurm、H2 均为零。待用户审查，不编写论文正文。"]
    # The public HTML uses the short view; its numerical tables are checked cell for cell.
    html=["---","title: T6 阶段 2：主张和反例","file: t6-claims-stage2","template: doc","theme: paper","lang: zh","---",
          "## A 当前可交审的主张","",intro,"",_md(tab["status"]),"",
          "## B C1 全板与反例","","T4b 对 B 的 14 条劣行中，10 条来自荷兰式族。新板没有 B 臂。","",_md(tab["board"]),
          "","## C 服务与用工分别判断","","均差为候选减对照。联合条件要求两项服务缺额均降低，且比巡检少用人时。","",
          _md(tab["joint"]),"",_md(tab["staff"]),"","## D 每项反例可回查","",
          "下表保留每个面板、对照和条件。事后逐行最优不属于可部署方案。","",_md(tab["exceptions"]),
          "","## E 事故与普通改进","",c2["statement"],"",_md(tab["incidents"]),"",
          "首片的 V 与 D 在所有合规行服务持平。冷态 A04 改善、B08 退化；它们属于另一面板。","",_md(tab["improvement"]),
          "","## F RSI 只列依据","","C4 状态：未建立。statement 暂不填写。","",_md(tab["rsi"]),
          "","## G 核验入口","","[按路径与提交逐项核对](claims.json) · [报告与分族全表](claims-stage2.md) · [完整核验输出](claims-verification.txt)。"
          "每个数值带 JSON 字段或原文行，未改封存数据。本阶段交回后等审。"]
    return "\n".join(word)+"\n","\n".join(html)+"\n"


def check_html(path,data):
    t=make(data);p=VisibleTables();p.feed(path.read_text(encoding="utf8"));p.close()
    keys=("status","board","joint","staff","exceptions","incidents","improvement","rsi")
    expected=[[t[k][0],*t[k][1]] for k in keys]
    if p.tables!=expected:
        for key,a,b in zip(keys,p.tables,expected):
            if a!=b:
                raise ValueError(f"HTML {key}: first differing cells {next(((x,y) for x,y in zip(a,b) if x!=y),(len(a),len(b)))}")
        raise ValueError("HTML stage-2 table inventory")
