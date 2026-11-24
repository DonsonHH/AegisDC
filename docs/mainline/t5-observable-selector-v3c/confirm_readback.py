"""Publish verified summaries and the tables rendered in the HTML handover."""
from pathlib import Path
import json
import sys

from readback import NAMES,expect,sha,read,seconds,signed

HERE=Path(__file__).resolve().parent
NICK={"S":"S（公开选择器）","W":"W（整板赢家）","V_COST":"V**","M_HOT":"M_hot","B_COST":"B_cost","P":"既有保护 P",
      "PERIODIC":"周期巡检","ALARM":"报警响应","ORACLE":"合法全知"}


def verify(base):
    x=read(base/"confirmation-result.json"); release=read(base/"release.json")
    dev=read(HERE/"development-receipt.json"); panel=read(base/"panel.json")
    need=expect; index={n:h for h,n in (q.split("  ",1) for q in (base/"confirmation-artifacts.sha256").read_text().splitlines())}
    for f,h in index.items():
        if not f.startswith(("positions/","inputs/")):need(sha(base/f)==h,"saved "+f)
    need(x["source"]==release["commit"] and sha(base/"locked-selector.json")==sha(HERE/"locked-selector.json")==x["pub_lock"]["sha256"] and
         sha(base/"panel.json")==sha(HERE/"new-panel.json")==x["pub_panel"]["sha256"] and x["pub_lock"]==panel["lock_publication"],"published identity and generation order")
    for f,h in release["files"].items():need(sha(HERE/f)==h,"execution version "+f)
    need([r["key"] for r in x["conditions"]]==panel["order"] and len(x["conditions"])==36,"ordered roster")
    routing=read(base/"routing-readback.json")
    need(set(routing["rows"])==set(panel["order"]) and routing["facilities_called"]==0,"all public histories in extra readback")
    fields=("id","state","exit","wall","cpus","minutes","total_cpu","user_cpu","sys_cpu","start","end","node")
    table={r[0]:dict(zip(fields,r[:len(fields)],strict=True)) for l in (base/"confirm-sacct.psv").read_text().splitlines() if (r:=l.split("|"))}
    jobs=[];regs={};state_counts={}
    for p in sorted((base/"registrations").glob("*.json"),key=lambda p:int(read(p)["job"])):
        reg=read(p);j=reg["job"];regs[j]=reg;a=table[j];batch=table[j+".batch"]
        need(a["state"]==batch["state"] and a["exit"]==batch["exit"] and a["total_cpu"]==batch["total_cpu"] and int(a["cpus"])==reg["cpus"] and
             int(a["minutes"])==reg["minutes"] and reg["source"]==release["commit"],"original allocation "+j)
        sec=seconds(a["total_cpu"]);reserve=reg["reserved_s"]
        terminal=base/"jobs"/reg["name"]/"terminal.json"
        if terminal.exists():
            t=read(terminal);need(t["job"]==j and t["name"]==reg["name"],"batch terminal")
            for state,n in t["states"].items():state_counts[state]=state_counts.get(state,0)+n
        jobs.append(dict(a,name=reg["name"],reserved_cpu_s=reserve,process_cpu_s=sec,allocated_wall_cpu_s=int(a["cpus"])*int(a["wall"]),
                         within_2x=reserve<=2*sec,ratio=reserve/sec if sec else None,stdout_sha256=index["logs/"+j+".out"],
                         stderr_sha256=index["logs/"+j+".err"]))
    budget=read(base/"budget.json")
    p=panel["order"]; pilot=[(p[0],r) for r in NICK]+[(p[i],r) for i,r in ((1,"S"),(2,"S"),(3,"W"),(4,"ORACLE"),(5,"V_COST"))]+[(k,"MIRROR") for k in p[:3]]
    slots={x:"pilot" for x in pilot}
    for name,plan in budget["plan"].items():
        for lane in plan["lanes"]:
            for k,r in lane:
                need((k,r) not in slots,"duplicate charge");slots[k,r]=name
    need(len(slots)==327 and len(regs)==27 and len(jobs)+len(dev["jobs"])<=40,"complete budget roster")
    checked=set(); mirrors={}
    for r in x["conditions"]:
        k=r["key"];need(index["inputs/"+k+".json"]==panel["cases"][k]["sha256"],"raw input")
        for role,v in r["arms"].items():
            e=v["entry"];pref="positions/"+k+"/"+role+"/"
            for fn,f in (("entry.json","entry_sha256"),("row.json","row_sha256"),("original.jsonl.gz","raw")):
                need(index[pref+fn]==v[f],"readback original "+pref+fn)
            need(regs[e["job"]]["name"]==slots[k,role] and e["key"]==k and e["arm"]==role and e["source"]==release["commit"] and
                 e["input"]==panel["cases"][k]["sha256"] and e["operative"]==panel["cases"][k]["operative_sha256"],"slot/release")
            if role=="S":
                z=routing["rows"][k]
                need(index[pref+"selector.json"]==v["selector_log"]==z["selector_sha256"] and z["native_sha256"]==v["raw"] and
                     all(z[f]==v["selection"][f] for f in ("selected","cell","at")) and z["actual_L"]==v["L"] and
                     z["issued_identity"]==v["issued_digest"],"independent readback of native prefix, actual trigger and public feature cell")
            checked.add((k,role))
        if "MIRROR" in r["arms"]:
            a=r["arms"]["S"];b=r["arms"]["MIRROR"]
            mirrors[k]=(a["L"]==b["L"] and a["issued_digest"]==b["issued_digest"] and a["selection"]["selected"]==b["entry"]["actual"])
    need(all(mirrors[q["key"]]==q["passed"] for q in x["mirrors"]) and set(mirrors)==set(p[:3]),"three independent witnesses")
    need(set(slots)-checked=={(q["key"],q["role"]) for q in x["errors"]} and len(checked)==x["scored"]==state_counts.get("SCORED",0),"full denominator")
    totals=dict(jobs=len(jobs),reserved_cpu_s=sum(j["reserved_cpu_s"] for j in jobs),process_cpu_s=round(sum(j["process_cpu_s"] for j in jobs),3),
                allocated_wall_cpu_s=sum(j["allocated_wall_cpu_s"] for j in jobs),over_2x=[j["id"] for j in jobs if not j["within_2x"]],
                nonzero_jobs=[j["id"] for j in jobs if (j["state"],j["exit"])!=("COMPLETED","0:0")])
    combined={k:(round(totals[k]+dev["totals"][k],3)) for k in ("jobs","reserved_cpu_s","process_cpu_s","allocated_wall_cpu_s")}
    admissions=sorted((base/"admissions").glob("*.json"))
    for path in admissions:
        audit=read(path)
        need(all(any(j["id"]==a["job"] and j["reserved_cpu_s"]==a["reserved_s"] and abs(j["process_cpu_s"]-a["actual_cpu_s"])<.001
                     for j in jobs) for a in audit["rows"]),"actual spend per wave")
    return x,dict(schema="T5-v3c-confirmation-receipt",source=x["source"],lock=x["pub_lock"],panel=x["pub_panel"],
        result_sha256=sha(base/"confirmation-result.json"),index_sha256=sha(base/"confirmation-artifacts.sha256"),indexed_files=len(index),
        stage0_receipt_sha256=sha(HERE/"development-receipt.json"),originals_compared=len(checked),native_markers=sum(n.endswith("/entry.json") and n.startswith("positions/") for n in index),
        readback_recovery=dict(first="ca3e877e",repair="86fbeee7",first_source_sha256=index["readback-a1/routing_readback.py"],
            first_error_sha256=index["readback-a1/import.err"],error="ambiguous historical schedule import before any scientific readback",
            repair_source_sha256=sha(HERE/"routing_readback.py"),extra_facility_calls=0,extra_slurm_jobs=0),
        positions_planned=327,failed=x["errors"],retries=[],jobs=jobs,execution_totals=totals,combined=combined,
        mirrored=mirrors,primary_verdict=x["primary_verdict"],overlap=x["overlap"],H2_accessed=0,H2_derived=0,H2_generated=0,
        public_routing_audit=dict(sha256=sha(base/"routing-readback.json"),conditions=len(routing["rows"]),
            triggered=sum(z["state"]=="TRIGGERED" for z in routing["rows"].values()),never_triggered=[k for k,z in routing["rows"].items() if z["state"]=="NEVER_TRIGGERED"]),
        wave_accounting={p.name:sha(p) for p in admissions},combined_budget_ok=combined["jobs"]<=40 and combined["reserved_cpu_s"]<=108000
            and not totals["over_2x"] and dev["totals"]["individual_within_2x"],
        private_root="/share/home/renly/renly-patrol-rsi/mainline/T5-observable-selector-v3c/confirmation",
        private_layout="positions/<case>/<arm>/{entry.json,original.jsonl.gz,row.json}; S/selector.json; inputs/<case>.json; logs/<job>.{out,err}; jobs/<batch>/terminal.json")


def number(v):
    return "未决" if v is None else f"{v:.2f}"


def create(x,s):
    dev=read(HERE/"development.json");d=dev["primary"];main=x["comparisons"]["W"]["ci"];lock=read(HERE/"locked-selector.json")
    observed=[q for q in x["conditions"] if {"S","W"}<=q["arms"].keys()]
    tied=sum(q["arms"]["S"]["L"]==q["arms"]["W"]["L"] for q in observed)
    worse=sum(q["arms"]["S"]["L"]>q["arms"]["W"]["L"] for q in observed)
    attained=sum(q["lower"]["certified_min"] is not None and abs(q["arms"]["W"]["L"]-q["lower"]["certified_min"])<1e-7 for q in observed)
    fallback=[v for v in x["cells"].values() if v["fallback"]]
    primary=("未决" if not main else f"**{signed(main['mean'])} 秒**，双侧 95% 区间 **[{signed(main['lower'])}, {signed(main['upper'])}] 秒**")
    verdict={"PASS":"通过","FAIL":"未通过","UNRESOLVED":"未决"}[x["primary_verdict"]]
    lines=["# T5 v3c：可观测选择器","",
           f"门槛 0 在 36/36 条条件成立。阶段 0 的 S−整板平均剩余缺额为 **{signed(d['mean'])} 秒**，单侧 95% 区间 **(−∞, {signed(d['upper'])}] 秒**，门槛 1 通过。",
           "",f"在新面板 36 条条件上，S−W 的平均服务缺额差为 {primary}；主门槛**{verdict}**。W 是在旧面板全板选定的 {lock['fit']['winner']}。"
           f"W 在 {attained}/36 条达到有原生见证的全知下界；S 与 W 持平 {tied} 条、缺额更大 {worse} 条。"
           f"独立复现按原序取前 3 条，L 和完整签发序列同时一致 {sum(q['passed'] for q in x['mirrors'])}/3。",
           "","## 新面板比较","","正差表示选择器产生更多服务缺额。所有次要比较沿用相同分层和重抽索引，没有独立通过门槛。",
           "","| 对照 | 有效配对／36 | S−对照（秒） | 双侧 95% 区间（秒） |","|---|---:|---:|---|"]
    for r in ("W","V_COST","M_HOT","P","PERIODIC","ALARM","B_COST"):
        a=x["comparisons"][r];ci=a["ci"]
        lines.append(f"| {NICK[r]} | {a['pairs']} | {signed(ci['mean']) if ci else '未决'} | "+(f"[{signed(ci['lower'])}, {signed(ci['upper'])}]" if ci else "未决")+" |")
    lines+=["","## 逐格选择","","训练取旧 36 条，新 36 条只评价。训练格仅 1 条或新格从未见过时，选整板 W。","","| 格键 | 旧板训练 | 新板评价 | 定型选择 | 回退 |","|---|---:|---:|---|---|"]
    for cell in sorted(set(lock["fit"]["training_counts"])|set(x["cells"])):
        n=lock["fit"]["training_counts"].get(cell,0);a=x["cells"].get(cell,{});l=lock["fit"]["cells"].get(cell,lock["fit"]["winner"])
        lines.append(f"| {cell.replace('|',' / ')} | {n} | {a.get('n',0)} | {l} | {'是' if n<2 else '否'} |")
    lines+=["",f"新板实际出现 {len(x['cells'])} 格，{len(fallback)} 格回退，涉及 {sum(v['n'] for v in fallback)}/36 条。"
            "旧板两个方向均有 4/8 格回退，评价中 A→B 有 3/18 条、B→A 有 4/18 条实际使用回退。"
            "参照的历史数值 **120.37 秒**可按文件字母序处理族内并列第一名复现；使用本包冻结接受序得到 **91.77 秒**，整板为 **226.01 秒**。"
            "旧板格键和六族旧板分解见[开发报告](development-report.md)。",
            "","## 各对象到原生全知下界的剩余缺额","","单位为每条件整窗服务缺额秒。全知列为见证的实际剩余；每族 6 条。",
            "","| 对象 | 全板平均 L | 全板剩余 | "+" | ".join(NAMES.values())+" |","|---|"+"---:|"*8]
    for role,nick in NICK.items():
        q=x["roles"][role]
        lines.append("| "+nick+" | "+number(q["mean_L"])+" | "+number(q["gap"])+" | "+" | ".join(number(x["families"][f][role]["gap"]) for f in NAMES)+" |")
    lines+=["","## 原生复现与重合审计","","| 条件 | S 所选 | 独立 L（秒） | 完整签发序列 |","|---|---|---:|---|"]
    for a in x["mirrors"]:lines.append(f"| {a['key']} | {a['selected']} | {number(a['L'][1])} | {'相同' if a['passed'] else '见差异账'} |")
    lines+=["","新的 36 条条件在板内均不重复；和 T4b（144）、v1（84）、v2（36）、v3a（36）分别核对全部条件字节以及实际设施、外挂状态与维护参数，两种身份的重合各为 0。",
        "","## 作业、原件与版本","",f"确认原生入口 {s['native_markers']}/327，有效原件 {x['scored']}/327，原失败 {len(x['errors'])}，重跑 0。"
        f"全包 {s['combined']['jobs']}/40 个 Slurm 作业，预留 {s['combined']['reserved_cpu_s']:,}/108,000 CPU 秒，"
        f"进程 CPU 实耗 {s['combined']['process_cpu_s']:,.3f} 秒。确认作业预留超过实际两倍：{s['execution_totals']['over_2x'] or '无'}。"
        "单作业账取含步骤的 sacct，作业与 .batch 行核对后只计一次。H2 的生成、读取和派生均为 0。"
        "首版额外读回因同名调度模块在导入时退出，修订 86fbeee7 只读保存原件；没有增加设施调用或作业。原错误已索引。",
        "",f"开发协议 ab6a8ad5，确认执行源码 {x['source'][:8]}，S/W 锁表 {x['pub_lock']['commit'][:8]}，新输入清单 {x['pub_panel']['commit'][:8]}。"
        "两端原件身份见[确认回执](confirmation-receipt.json)、[逐条结果](confirmation-result.json)与[证据索引](confirmation-artifacts.sha256)。"
        "原生全知的计划、执行链和逐条件见证保存在同一结果中。开发使用了旧板全部 36 条；新面板来自同一合成发生器，没有现场或总体效应估计。"]
    return "\n".join(lines)+"\n"


if __name__=="__main__":
    base=Path(sys.argv[1]);x,s=verify(base)
    for f in ("confirmation-result.json","confirmation-artifacts.sha256","confirm-sacct.psv","budget.json","routing-readback.json"):
        name="confirmation-budget.json" if f=="budget.json" else f
        with (HERE/name).open("xb") as out:out.write((base/f).read_bytes())
    with (HERE/"confirmation-receipt.json").open("x",encoding="utf8",newline="\n") as out:
        json.dump(s,out,ensure_ascii=False,indent=2);out.write("\n")
    with (HERE/"README.md").open("x",encoding="utf8",newline="\n") as out:out.write(create(x,s))
