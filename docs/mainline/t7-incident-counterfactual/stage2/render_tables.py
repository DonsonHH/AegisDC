"""Render the saved confirmatory and descriptive results for review."""

import json
from study import HERE, FAMILIES, ROLES


def n(value, digits=2):
    return "未建立" if value is None else f"{value:.{digits}f}"


def probability(p):
    return "未建立" if p is None else f"{p:.7g}"


def holm_label(record):
    return probability(record["holm_p"]) + ("（占位）" if record["raw_p"] is None else "")


def interval(value, scale=1):
    return "未建立" if value is None else "[" + ", ".join(n(x*scale) for x in value) + "]"


def endpoint_cells(name, record):
    scale = 100 if name == "HC" else 1
    point = None if record["estimate"] is None else record["estimate"]*scale
    return [n(point), interval(record["interval_95"],scale)]


def key_text(keys):
    return "、".join(keys) if keys else "无"


def render(a, m):
    lines=["# H3 留出面板的完整结果", "", "## 三项预注册主结果", "",
           "方向为 V_COST 减指定对照。区间为边际双侧 95% 区间，显著性判定使用三项原始双侧 p 的 Holm 校正值。", "",
           "| 假设 | 配对量 | 有效/计划 | 估计 | 95% 区间 | 原始 p | Holm p | 判定 |",
           "|---|---|---:|---:|---|---:|---:|---|"]
    for name,label in (("HA","相对 P 的 L 差（秒）"),("HB","相对报警的 L 差（秒）"),("HC","相对 P 的事件率差（百分点）")):
        e=a["primary"][name]
        point, ci=endpoint_cells(name,e)
        lines.append(f"| {name} | {label} | {e['valid']}/{e['planned']} | {point} | {ci} | "
                     f"{probability(e['raw_p'])} | {holm_label(e)} | {e['status']} |")
    if a["primary"]["HC"]["status"]=="INDETERMINATE" and a["primary"]["HC"]["se"]==0:
        lines+=["","HC 的两族块间方差同时为零。按登记保留事件率差点估计，原始 p 和区间未建立；Holm 列的 1 用于保留三项校正分母。"]
    lines += ["", "## 两族原臂评分", "", "事件为原始 L 严格大于零。均值的分母为有效评分数，另列原计划分母。", "",
              "| 族 | 臂 | 有效/计划 | 平均 L（秒） | 平均实耗（人秒） | 有缺额行数 | 事件率 |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for family in FAMILIES:
        for role in ROLES:
            r=a["families"][family]["arms"][role]
            rate="未建立" if r["event_rate"] is None else n(100*r["event_rate"])+"%"
            lines.append(f"| {family} | {role} | {r['scored']}/{r['planned']} | {n(r['mean_L'])} | "
                         f"{n(r['mean_person'])} | {r['events']} | {rate} |")
    lines += ["", "ORACLE 在 H3 面板没有计划位置，实测均值和事件率均未建立。", "",
              "## HC 的逐族配对", "", "| 族 | 均无事件 | P 有而 V 无 | P 无而 V 有 | 均有事件 | 配对缺失 |",
              "|---|---:|---:|---:|---:|---:|"]
    for family in FAMILIES:
        c=a["families"][family]["event_pairs"]
        lines.append("| "+family+" | "+" | ".join(str(len(c[k])) for k in ("P0_V0","P1_V0","P0_V1","P1_V1","missing"))+" |")
    for family in FAMILIES:
        c=a["families"][family]["event_pairs"]
        lines.extend(["",f"**{family}**", "", "P 有、V_COST 无的原条件为 "+key_text(c["P1_V0"])+"。",
                      "", "P 无、V_COST 有的原条件为 "+key_text(c["P0_V1"])+"。"])
    lines += ["", "## 配对描述", "", "每格方向均为 V_COST 减比较臂。优、平、劣表示数值较低、相同、较高。", "",
              "| 族 | 比较臂 | 配对/计划 | L 均差（秒） | L 优/平/劣 | 人员均差（人秒） | 人员工时优/平/劣 |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for family in FAMILIES:
        for role in ("P","ALARM","PERIODIC","B"):
            r=a["descriptive_pairs"][family][role];lo=r["L"];pe=r["person"]
            lines.append(f"| {family} | {role} | {r['valid']}/{r['planned']} | {n(lo['mean_difference'])} | "
                         +"/".join(map(str,lo["better_equal_worse"]))+f" | {n(pe['mean_difference'])} | "
                         +"/".join(map(str,pe["better_equal_worse"]))+" |")
    extra=a["sensitivity"]
    lines += ["", "## 重合与缺失分母", "",
              f"描述性筛选去重后剔除 {extra['excluded']} 行，保留 {extra['retained']}/120。原主分析包含所有行。", "",
              "| 族 | 原块号 | 五臂有效位置/60 | 原主配对 HA/HB/HC（各 12） | 外部命中 T4b/T4c/交集 | 实剔/保留 | 子集有效配对 HA/HB/HC | 各臂缺失数 P/巡检/报警/B/V |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    missing=[]
    for b in a["blocks"]:
        miss=[len(b["missing_by_role"][r]) for r in ROLES]
        valid=b["positions_planned"]-sum(miss)
        main="/".join(str(b["primary_pairs"][name]) for name in ("HA","HB","HC"))
        s="/".join(str(b["retained_pairs"][name]) for name in ("HA","HB","HC"))
        lines.append(f"| {b['family']} | {b['block']} | {valid}/{b['positions_planned']} | {main} | "
                     f"{b['t4b']}/{b['t4c']}/{b['both']} | {b['excluded']}/{b['retained']} | {s} | "
                     +"/".join(map(str,miss))+" |")
        for role in ROLES:
            missing.extend(k+"/"+role for k in b["missing_by_role"][role])
    lines+=["", "未取得有效评分的位置："+key_text(missing)+"。","", "## 剔除重合后的描述性结果", ""]
    if "endpoints" in extra:
        lines+=["| 配对量 | 有效/保留 | 估计 | 描述性 95% 区间 | 自由度 |","|---|---:|---:|---|---:|"]
        for name in ("HA","HB","HC"):
            e=extra["endpoints"][name]
            point,ci=endpoint_cells(name,e)
            lines.append(f"| {name}（{'百分点' if name=='HC' else '秒'}） | {e['valid']}/{e['planned']} | {point} | {ci} | {e['df']} |")
    else:
        lines.append("无需敏感性。")
    worse=a["worse_than_periodic"]
    lines+=["","## V_COST 缺额高于周期巡检的所有行","",f"共 {len(worse)} 行，按原族和条件编号列出。","",
            "| H3 条件 | V_COST L | 周期 L | 多出的缺额秒 | V_COST 人秒 | 周期人秒 |","|---|---:|---:|---:|---:|---:|"]
    for r in worse:
        lines.append(f"| {r['key']} | {n(r['V_L'])} | {n(r['PERIODIC_L'])} | {n(r['V_L']-r['PERIODIC_L'])} | "
                     f"{n(r['V_person'])} | {n(r['PERIODIC_person'])} |")
    if not worse:lines.append("| 无 | | | | | |")
    faulted=sum(r.get("fault") is not None for r in m["rows"])
    feasible=sum(r.get("last_legal") is not None for r in m["rows"])
    lines+=["", "## 荷兰错过预防窗的等待", "",
            f"按评分前写定的轨迹口径，{m['assessable']}/{m['planned']} 行可判。可判记录中 {faulted} 行有外生故障，"
            f"{feasible} 行有可在故障前完成的合法 NR 开工机会，{m['wait_failure']} 行满足等待失败。"
            f"有强规则 B 避开转供跳闸且转供损失较小的配对见证 {m['paired_B_witness']}/{m['B_assessable']} 行，"
            f"其中与等待失败相交 {m['wait_with_B_witness']} 行。等待失败中，同时无故障前有效初检且后来泵操作为 NO_EFFECT 的有 "
            f"{m['exact_late_no_effect_without_initial']} 行。", "",
            "| H3 条件 | 最后合法 NR 帧（秒） | 实际选择 | 转供窗（秒） | V / B 转供缺额（秒） | B 有效 NR（秒） | 后续泵动作 |",
            "|---|---:|---|---|---:|---:|---|"]
    for r in m["rows"]:
        if not r["wait_failure"]: continue
        last=r["last_legal"]
        pump="、".join(str(w["at"])+" "+w["outcome"] for w in r["later_pump"]) or "无"
        bt="无" if r["B_NR_effect"] is None else n(r["B_NR_effect"],0)
        lines.append(f"| {r['key']} | {last['time']} | {last['actual']} | {r['fault']}–{r['restored']} | "
                     f"{n(r['V_transfer_L'])} / {n(r['B_transfer_L'])} | {bt} | {pump} |")
    if not m["wait_failure"]:lines.append("| 无 | | | | | | |")
    return ("\n".join(lines)+"\n").encode()


if __name__=="__main__":
    import sys
    sys.stdout.buffer.write(render(json.loads((HERE/"analysis.json").read_bytes()),json.loads((HERE/"mechanisms.json").read_bytes())))
