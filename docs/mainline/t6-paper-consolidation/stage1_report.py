"""Render a readback, then compare the visible HTML tables against the same sealed values."""
from html.parser import HTMLParser

CN={"WATER_HEAT":"水侧与热","NETWORK_POWER":"网络与供电","RESERVE_TRANSFER":"有限备用","COOLING_ACCESS":"冷却与通行",
    "LONDON":"伦敦式","NETHERLANDS":"荷兰式"}
ROLE={"B":"强透明 B","P":"仅既有保护 P","PERIODIC":"周期巡检","ALARM":"报警响应","B_COST":"B_COST（补充）",
      "POSTHOC_MIN_P_PERIODIC_ALARM":"事后逐行最优"}
POST="POSTHOC_MIN_P_PERIODIC_ALARM"
BASE_URL="https://github.com/DonsonHH/AegisDC/blob/"


def sec(v,signed=False):
    return (f"{v:+.2f}" if signed and v else f"{v:.2f}").replace("-","−")


def table(head,rows):
    return tuple(str(h) for h in head),[tuple(str(v) for v in row) for row in rows]


def tables(obj):
    out={};c1=obj["C1"];c4=obj["C4"];pools=c4["pools"]
    def stats(v):
        if v["state"]=="ARM_NOT_PRESENT":return ("无该臂","—","—","—")
        return (sec(v["mean"]["seconds"],True),v["better"],v["equal"],v["worse"])
    def c1_rows(panel,scope):
        p=c1[panel]
        return [(cn,ROLE[role],v["planned"],*stats(v))
                for name,cn in scope for role in p["comparators"] for v in [p["scopes"][name][role]]]
    header=("面板","对照","原分母","均差（秒）","优","平","劣")
    out["overall"]=table(header,[*c1_rows("T4b",[("ALL","T4b 留出")]),*c1_rows("v3c",[("ALL","v3c 新板")])])
    for k in c1:out[k]=table(("条件族",*header[1:]),c1_rows(k,CN.items()))
    ratio=lambda a,n:f"{a}/{n}"
    q=pools["fixed54"]
    vals=[("v3a 候选池逐条件取最小后平均","0.00 秒",sec(q["rowwise_best_mean_gap"]["seconds"])+" 秒"),
          ("v3a MAIN-R-3 平均剩余","82.03 秒",sec(c4["old_R3_mean_gap"]["seconds"])+" 秒"),
          ("v3a MAIN-R-3 贴界","32/36",ratio(c4["old_R3_attained"],c4["old_n"])),
          ("v3a MAIN-R-3 尚有余量","4 条",str(len(c4["old_R3_room"]))+" 条"),
          ("新板 W＝MAIN-R-3 贴界","36/36",ratio(c4["new_R3_attained"],c4["new_n"]))]
    gates=[r for r in obj["pointer_audit"]["checked"] if r["stage"]=="1b"]
    out["five"]=table(("C4 待核项","任务书指针","封存逐行复算","数值核对"),
                       [(*r,"相符" if g["match"] else "有差异") for r,g in zip(vals,gates,strict=True)])
    out["pool"]=table(("v3a 候选集","逐行最小后平均（秒）","全板固定一项的最小均值（秒）","全板优胜向量","逐行最低达界"),
        [(q["count"],sec(q["rowwise_best_mean_gap"]["seconds"]),sec(q["best_single_vector_mean_gap"]["seconds"]),
          "、".join(q["whole_panel_minimizers"]),ratio(q["rowwise_zero_gap_rows"],c4["old_n"])) for q in pools.values()])
    names={"B_COST":"成本感知透明规则","V_COST":"V**，原生行动代价规则","M":"v1 人工参照，MAIN","M_HOT":"v1 人工参照，HOT"}
    out["membership"]=table(("仅 58 项集合包含","身份","54 项","58 项"),[(l,names[l],"不含","包含") for l in c4["only_in_58"]])
    out["room"]=table(("v3a 条件","族","MAIN-R-3 的 L","已认证下界","差（秒）","逐行达界见证之一"),
        [(r["key"],CN[r["family"]],sec(r["R3_L_s"]),sec(r["bound_s"]),sec(r["R3_gap_s"]),r["fixed54"]["first_attaining"])
         for r in c4["old_rows"] if not r["R3_within_tolerance"]])
    td=obj["T4d"]
    out["t4d"]=table(("T4d 原设置","分母","B 优于 P","持平","B 劣于 P"),[("BASE",td["panel_n"],td["better"],td["equal"],td["worse"])])
    a=obj["pointer_audit"]
    rows=[("1a 数值","任务书逐项参考","无" if not any(v["stage"]=="1a" for v in a["differences"]) else "见逐项差异",
           "按展示精度核均差；优／平／劣与分母逐项相等。"),
          ("1b 五数","原复算：逐行最小后平均","无" if a["C4_numerical_gate"]=="REPRODUCED" else "见逐项差异",
           "秒值容差 0.01；计数要求完全相同。"),
          ("1b 文字口径","整板只用一个固定向量时是否为 0.00 秒",
           sec(q["best_single_vector_mean_gap"]["seconds"])+" 秒","逐行换向量得到的 0.00 秒不适用于一个整板策略。")]
    for v in a["differences"]:rows.append((v["stage"],v["item"],str(v["observed"]),"任务书："+str(v["reference"])))
    out["differences"]=table(("项目","核对对象","差异／封存值","原因或判定规则"),rows)
    fields={
        "t4b":"/rows/{i}/key, family, arms/{V_COST,B,P,PERIODIC,ALARM}/L",
        "t4d":"/panels/BASE/{i}/key, family, arms/{B,P}/L",
        "new":"/conditions/{i}/key, family, arms/{V_COST,P,PERIODIC,ALARM,B_COST,W}/L; arms/W/entry/actual; lower/{status,certified_min,actual_chain,native_L}; arms/ORACLE/L",
        "old":"/conditions/{i}/key, family, arms/{member}/L; minimum/{status,certified_min,actual_chain,native_L}; arms/ORACLE/L",
        "design":"/roles/random; /roles/reference",
        "panel":"/vectors; /reference_identities",
        "lock":"/roster; /fit/winner"}
    out["source_paths"]=table(("来源标识","仓库内路径","冻结提交","JSON 字段"),[
        (k,obj["sources"][k]["path"],obj["sources"][k]["commit"],p) for k,p in fields.items()])
    return out


def md(t):
    head,rows=t
    line=lambda row:"| "+" | ".join(row)+" |"
    return "\n".join([line(head),line(["---"]*len(head)),*(line(r) for r in rows)])


def documents(obj):
    t=tables(obj);c=obj["C4"];src=obj["sources"];p=c["pools"]["fixed54"]
    def link(k):
        d=src[k];return f"[{k} · {d['commit'][:8]}]({BASE_URL}{d['commit']}/{d['path']})"
    headline=("按原复算的逐条件取最小口径，v3a 的 54 项和 58 项均为 **"
              +sec(p["rowwise_best_mean_gap"]["seconds"])+" 秒**。若全板始终用同一个向量，两套集合的最佳平均剩余均为 **"
              +sec(p["best_single_vector_mean_gap"]["seconds"])+" 秒**，均由 MAIN-R-3 取得。两种计算只交换了取最小和求平均的顺序。")
    scale=c["loss_scale"]
    raw_note=("v3a 的逐行最小原始 L 平均为 "+sec(scale["rowwise_mean_raw_L_s"]["fixed54"]["seconds"])
              +" 秒，与平均认证下界 "+sec(scale["old_mean_certified_lower_s"]["seconds"])+" 秒相等。"
              "全板固定 MAIN-R-3 的平均原始 L 为 "+sec(scale["best_single_mean_raw_L_s"]["fixed54"]["seconds"])+" 秒。")
    desc="同一条件上，以 V_COST（V**）的 L 减去对照的 L。负差表示 V_COST 服务缺额较小；优／平／劣按未舍入差值计数。L 和差值均为整窗归一化服务缺额秒。"
    post="逐行最优一栏先查看 P、周期巡检、报警响应的实际 L，再取三者的最小值。该参照使用事后结果，不能部署。"
    newdesc="新板的正式主比较是 S−W。这里的 V_COST 比较属于描述性读回。新板没有 B 臂，全板和每族均标为无该臂，B_COST 另列。"
    refs=[
        ("C1 · T4b",link("t4b"),"/rows/{i}/key、family、arms/{V_COST,B,P,PERIODIC,ALARM}/L；按同一行配对。"),
        ("C1 · v3c",link("new"),"/conditions/{i}/key、family、arms/{V_COST,P,PERIODIC,ALARM,B_COST}/L；无 B。"),
        ("C1 · T4d",link("t4d"),"/panels/BASE/{i}/key、family、arms/{B,P}/L；逐行计 B−P 严格大于零。"),
        ("C4 · 名册",link("design")+"；"+link("panel")+"；"+link("lock"),"/roles/{random,reference}、/vectors、/reference_identities、/roster；同时核对接受顺序。"),
        ("C4 · v3a",link("old"),"/conditions/{i}/arms/{member}/L、/minimum/{certified_min,status,actual_chain,native_L}、/arms/ORACLE/L。"),
        ("C4 · 新板",link("new")+"；"+link("lock"),"/conditions/{i}/arms/W/{L,entry/actual}、/lower/{certified_min,status,actual_chain,native_L}、/arms/ORACLE/L；/fit/winner。")]
    def local(panel,scope,role):
        v=obj["C1"][panel]["scopes"][scope][role]
        return f"{sec(v['mean']['seconds'],True)} 秒（{v['better']}/{v['equal']}/{v['worse']}）"
    cold="COOLING_ACCESS";nl=obj["C1"]["T4b"]["scopes"]["NETHERLANDS"]
    family_note=(f"冷却与通行族中，对固定 P 为 {local('T4b',cold,'P')}，对周期巡检为 {local('T4b',cold,'PERIODIC')}，"
                 f"对报警为 {local('T4b',cold,'ALARM')}。同一族对事后逐行最优为 {local('T4b',cold,POST)}。"
                 f"荷兰式族相对巡检有 {nl['PERIODIC']['worse']} 条劣行，相对 B 有 {nl['B']['worse']} 条。")
    source_table=md(table(("表／指标","封存版本","JSON 字段与口径"),refs))
    opts=[p["members"][i:i+12] for i in range(0,p["count"],12)]
    r=["# T6 阶段 1：从封存结果复算 C1 与 C4","",headline,"",
       "C1 主对照仍为强透明规则 B。T4b 是合成留出确认；v3c 新板来自冻结的选择器确认设计。两块面板分别计数，不重抽区间。",
       "","## 1a　整板与分族","",desc,"",md(t["overall"]),"",newdesc+" "+post,
       "","### T4b：每族 24 条","",md(t["T4b"]),"",family_note,
       "","### v3c 新板：每族 6 条","",md(t["v3c"]),"",
       "新板冷却与通行族相对巡检为 "+local("v3c",cold,"PERIODIC")+"，相对报警为 "+local("v3c",cold,"ALARM")+"。",
       "","### T4d：单列原开发面板","",md(t["t4d"]),
       "","B 劣于 P 的条件键："+ "、".join(x["key"] for x in obj["T4d"]["worse_rows"])+"。取 BASE 的全部条件；不合并三组参数敏感性面板。",
       "","## 1b　C4 五数与计算顺序","",md(t["five"]),"",md(t["pool"]),"",
       "记 g(i,j)=L(i,j)−L*(i)，L* 是本条件已认证、原生全知角色实际达到的下界。"
       "原复算是 mean_i min_j g(i,j)：候选集合预先固定，达到每行最小值的 j 可以不同。"
       "单向量口径是 min_j mean_i g(i,j)：同一个 j 必须覆盖全部条件。前一种取法使用评价结果，不是策略在运行时拥有的选择权。","",raw_note,
       "","贴界按 0 ≤ g ≤ 0.01 秒计，g > 0.01 秒才计为尚有余量。逐条核验 ORACLE 的实际 L 等于认证下界；新板每个 W 的实际身份均为 MAIN-R-3。",
       "","### 名册与逐行见证","","54 项：48 个开发抽样向量加 6 个锁定的 MAIN 向量。完整成员：","",
       *["、".join(part) for part in opts],"",
       "58 项保留上列全部成员，新增下面四项。ORACLE 和额外的 P 见证均未进入候选集。两套完整有序名单及逐向量整板均值见数字台账。",
       "",md(t["membership"]),"",md(t["room"]),"",
       "上述条件余量合计 "+f"{sum(row['R3_gap_s'] for row in c['old_rows']):,.0f}"+" 秒，除以 36 为 v3a 上 MAIN-R-3 的平均剩余。"
       "新板则从 W 的逐条件实际记录独立复算。每行的全部最低分候选均保存在台账中。",
       "","## 与任务书指针的差异","",md(t["differences"]),"","## 来源与复核","",source_table,"",
       "[数字台账](stage1-evidence.json)记录文件、提交、原件 SHA-256、行索引、字段、统计公式、逐行见证及全部指针对账。"
       "C1 的各格由 scopes 下的 row_indices 和 fields 展开；C4 的数值由 C4.sources、名册和 old_rows / new_rows 展开。","",
       "复核命令：python docs/mainline/t6-paper-consolidation/stage1_readback.py --check。脚本只用标准库和 git show 读取封存记录，不落文件。"
       "阶段 0 的两个导航文件均为纯增行。设施调用、Slurm 作业及 H2 生成／读取／派生均为零。","",
       "阶段 1 已交付，等待审查。主张台账和论文正文没有启动；C4 的论文措辞留待用户裁决。"
       "[HTML 审阅页](review.html) · [完整 --check 输出](verification.txt) · [交付文件哈希](delivery.json)"]
    html=["---","title: T6 阶段 1：两块面板的配对数与 C4 余量","file: t6-stage-1","template: doc","theme: paper","lang: zh","---",
          "## A C1 全板配对","",desc,"",md(t["overall"]),"",newdesc,
          "","## B T4b 六族","","主对照为 B；三种现状为描述性对照。"+post,"",md(t["T4b"]),
          "","## C v3c 新板六族","","每族含 6 条条件。没有 B 的行保留原分母。","",md(t["v3c"]),
          "","## D T4d 原开发面板","","原设置单列；不合并参数敏感性面板。","",md(t["t4d"]),
          "","## E C4 五数","","本表的剩余为 g = L − L*。L* 是本条件有原生见证的认证下界。"
          "0.00 秒表示逐行所选向量达到该下界；该条件的服务缺额 L 仍可以大于零。贴界阈值为 0.01 秒。","",md(t["five"]),
          "","## F 逐行与整板的区别","",headline,"",raw_note,"",md(t["pool"]),"",md(t["membership"]),
          "","逐行选择使用事后成绩。使用单个整板向量时，每一行必须取同一项。","",md(t["room"]),
          "","## G 指针对账","","数值来自封存的逐条件 L；本阶段不拟定 RSI 主张。","",md(t["differences"]),
          "","## H 数字从哪里来","","C1 的 i 为本格所有配对的冻结行号；C4 的 i 为该面板的冻结行号。"
          "下表给出完整提交与字段。每一格的行号、分子、分母和逐个候选见[数字台账](stage1-evidence.json)。","",
          md(t["source_paths"]),"","[查看完整复算报告](README.md) · [查看复核输出](verification.txt)"]
    return "\n".join(r)+"\n","\n".join(html)+"\n"


class VisibleTables(HTMLParser):
    def __init__(self):
        super().__init__();self.hidden=0;self.tables=[];self.table=self.row=self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","template"):self.hidden+=1
        if self.hidden:return
        if tag=="table":self.table=[]
        if self.table is None:return
        if tag=="tr":self.row=[]
        if tag in ("th","td"):self.cell=[]
    def handle_data(self,text):
        if not self.hidden and self.cell is not None:self.cell.append(text)
    def handle_endtag(self,tag):
        if tag in ("script","style","template"):
            self.hidden-=1;return
        if self.hidden or self.table is None:return
        if tag in ("th","td") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()));self.cell=None
        if tag=="tr" and self.row is not None:self.table.append(tuple(self.row));self.row=None
        if tag=="table":self.tables.append(self.table);self.table=None


def check_html(path,obj):
    p=VisibleTables();p.feed(path.read_text(encoding="utf8"));p.close()
    order=("overall","T4b","v3c","t4d","five","pool","membership","room","differences","source_paths")
    t=tables(obj);expected=[[t[k][0],*t[k][1]] for k in order]
    if p.tables!=expected:
        for i,(got,want) in enumerate(zip(p.tables,expected)):
            if got!=want:raise ValueError(f"visible HTML {order[i]}: first unequal row {next(((a,b) for a,b in zip(got,want) if a!=b),(len(got),len(want)))}")
        raise ValueError("visible HTML table count differs")
