"""One pair of reader-facing tables, checked against both Markdown documents and visible HTML."""
from html.parser import HTMLParser
import re
from counterexamples import FAMILIES, need

OPEN="<!-- V-P-COUNTEREXAMPLES:BEGIN -->"
CLOSE="<!-- V-P-COUNTEREXAMPLES:END -->"
FIELDS=("面板 / 条件","条件族","V_COST 的 L（秒）","P 的 L（秒）","V_COST−P（秒）","V_COST 首个实际签发（模拟秒）","记录所示原因")
GROUPS=("T4b 条件族","条件数","V_COST−P 均差（秒）","优","平","劣")


def n(x):
    return f"{x:g}".replace("-","−")


def sign(x,d=2):
    return (f"{x:+.{d}f}" if x else f"{x:.{d}f}").replace("-","−")


def explain(z):
    if z["reason"]=="same_outage_then_no_effect_restart":
        a,b,_,_=z["service_segment"]
        return (f"两臂同在 {n(a)}–{n(b)} 秒失供；供给恢复后，V_COST 才申请重启泵。回执为 NO_EFFECT，两臂缺额相同。")
    if z["panel"]=="v3c":
        a,b,demand,delivery=z["service_segment"]
        action="网络恢复" if z["write_operation"]=="restore_network" else "清滤"
        return (f"后台记录该次{action}无维修指征；写入生效后的 {n(a)}–{n(b)} 秒仅供应需求的 {n(100*delivery/demand)}%，P 全窗足额。")
    end=z["maintenance_until_s"];start=z["write_completed_s"]
    action="网络恢复" if z["write_operation"]=="restore_network" else "核查后清滤"
    return (f"{action}写入被执行，但后台无维修指征；{n(start)}–{n(end)} 秒的维护限容计入 {n(z['lost_L_at_cap'])} 秒缺额，P 全窗足额。")


def matrices(s):
    new=s["v3c"];t4=s["t4b"]
    rows=[]
    for z in [*new["rows_including_named_ties"],*sorted(t4["worse_rows"],key=lambda r:r["key"])]:
        tag=z["panel"]+" / "+z["key"]
        if z["classification"]=="TIED_WITH_P":tag+="（持平）"
        rows.append((tag,FAMILIES[z["family"]],n(z["V_L"]),n(z["P_L"]),sign(z["delta_s"]),
                     f"{z['first_issued_action']} @ {n(z['first_issued_s'])} s",explain(z)))
    family=[]
    for f,name in FAMILIES.items():
        z=t4["families"][f];family.append((name,str(z["n"]),sign(z["mean_delta_s"]),
                                            str(z["better"]),str(z["equal"]),str(z["worse"])))
    return ((FIELDS,rows),(GROUPS,family))


def narrative(s):
    q=s["v3c"];b=s["t4b"];alt=s["cooling_comparator_check"]
    cool=b["families"]["COOLING_ACCESS"]
    registered=set(q["keys_named_in_brief"])
    detail={r["key"]:r for r in q["rows_including_named_ties"]}
    ties=[k for k in q["keys_named_in_brief"] if detail[k]["delta_s"]==0]
    need(registered==set(q["above_certified_lower_keys"]) and len(ties)==2 and all(
        detail[k]["V_L"]==detail[k]["P_L"] for k in ties),"named ties and oracle comparison")
    first=(f"固定对照为仅有既有保护的 P，V_COST 表示 V**。正差是 V_COST 多出的整窗服务缺额。新板 {q['n']} 条："
           f"{q['counts']['better']} 优、{q['counts']['equal']} 平、{q['counts']['worse']} 劣。任务书点名的四条恰是 V_COST "
           f"高于已认证全知下界的四条；其中 {'、'.join(ties)} 的 V_COST 和 P 都为 {n(detail[ties[0]]['V_L'])} 秒，"
           "所以列为持平对照，不纳入严格劣行。下表同时列全两块面板的严格反例。")
    second=(f"T4b 的 {b['n']} 个原配对全部保留：{b['counts']['better']} 优、{b['counts']['equal']} 平、{b['counts']['worse']} 劣。"
            f"冷却与通行族以固定 P 为对照时是 {sign(cool['mean_delta_s'])} 秒（{cool['n']} 条）；"
            "另一个口径逐条取 P、周期巡检、报警响应中的最小缺额。"
            f"同族差值合计 {n(alt['best_of_status_quo']['sum_delta_s'])} 秒，除以 {alt['best_of_status_quo']['n']} "
            f"得到 {sign(alt['best_of_status_quo']['mean_delta_s'])} 秒。此前的约 +112 秒来自这个事后对照。")
    return first,second


def block(s):
    (h1,r1),(h2,r2)=matrices(s);intro,context=narrative(s)
    def table(head,rows):
        line=lambda cells:"| "+" | ".join(cells)+" |"
        return "\n".join([line(head),line(["---"]*len(head)),*(line(r) for r in rows)])
    return "\n\n".join([OPEN,intro.replace("表示 V**。","表示 V\\*\\*。"),table(h1,r1),context,table(h2,r2),
        "I 为签发初检，A 为签发处置。首动作列是签发时钟，原因列使用实际写入回执、服务曲线或维护降容账。"
        "各数值的提交号、原文件路径和字段索引见证据台账中的 v_cost_vs_p_counterexamples。",CLOSE])


class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden=0;self.text=[];self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","template"):self.hidden+=1
        if self.hidden:return
        if tag=="table":self.table=[]
        if self.table is None:return
        if tag=="tr":self.row=[]
        if tag in ("th","td"):self.cell=[]
    def handle_endtag(self,tag):
        if tag in ("script","style","template"):
            self.hidden-=1;return
        if self.hidden or self.table is None:return
        if tag in ("th","td") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()));self.cell=None
        if tag=="tr" and self.row is not None:self.table.append(tuple(self.row));self.row=None
        if tag=="table":self.tables.append(self.table);self.table=None
    def handle_data(self,text):
        if self.hidden:return
        self.text.append(text)
        if self.cell is not None:self.cell.append(text)


def check_surfaces(out,s):
    expected=block(s)
    for filename in ("README.md","review-draft.md"):
        txt=(out/filename).read_text(encoding="utf8")
        need(txt.count(OPEN)==txt.count(CLOSE)==1 and expected in txt,filename+": every r2 number and first action on the main page")
    reader=Visible();reader.feed((out/"review.html").read_text(encoding="utf8"));reader.close()
    for head,rows in matrices(s):
        found=[t for t in reader.tables if t and t[0]==head]
        need(len(found)==1 and found[0][1:]==rows,"visible HTML: "+head[0])
    text=" ".join("".join(reader.text).split())
    need(all(part in text for part in narrative(s)),"visible HTML: counts and both comparator explanations")
