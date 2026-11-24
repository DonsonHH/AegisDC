"""Verify the returned control archive and render recorded estimates. No fitting or simulation."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
NAMES=dict(WATER_HEAT="水侧与热",NETWORK_POWER="网络与供电",RESERVE_TRANSFER="有限备用",COOLING_ACCESS="冷却与通行",LONDON="伦敦式",NETHERLANDS="荷兰式")


def expect(test,reason):
    if not test:raise ValueError(reason)


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())


def seconds(field):
    d,_,rest=field.rpartition("-");n=0.
    for v in rest.split(":"):n=n*60+float(v)
    return n+(int(d) if d else 0)*86400


def verify(root):
    x=read(root/"development.json");check=read(root/"selfcheck.json");release=read(root/"release.json")
    expect(check["status"]=="PASS" and x["source"]==release["commit"],"development release")
    for fn,h in release["files"].items():
        expect(sha(HERE/fn)==h,"unchanged Stage A source: "+fn)
    listing={n:h for h,n in (s.split("  ",1) for s in (root/"artifacts.sha256").read_text().splitlines())}
    for name,h in listing.items():
        if not name.startswith("prefix/"):
            expect(sha(root/name)==h,"returned "+name)
    sums=0; clocks=0
    for k,obs in x["checks"].items():
        expect(obs==read(root/"checks"/(k+".json")),"same independent condition receipt")
        for l,h in obs.get("rows",{}).items():
            expect(listing["prefix/"+k+"/"+l+"/record.json"]==h,"private audit member")
        if obs["status"]=="PASS":
            expect(obs["roster"]==len(obs["rows"])==58 and len(obs["prefix_hashes"])==obs["frames_compared"] and
                   (obs["first_s"] is None or obs["frames_compared"]==obs["frame"]+1),"all roles and inclusive cutoff")
            sums+=obs["roster"];clocks+=obs["roster"]*obs["frames_compared"]
    roster=read(HERE.parent/"t5-landscape-diagnostic-v3a/panel-and-strategies.json")["order"]
    expect(sorted([*x["checks"],*x["unexecuted"]])==sorted(roster),"all 36 denominators")
    if x["gate0"]=="PASS" and x["gate1"]!="NOT_EVALUATED":
        pi=x["primary"]
        expect(len(x["rows"])==36 and sorted(r["key"] for r in x["rows"])==sorted(roster)
               and (x["gate1"]=="PASS")==bool(pi["upper"]<0),"evaluated roster and gate")
        for key,d in x["directions"].items():
            expect(sum(q["training"] for q in d["cells"].values())==18 and sum(q["evaluation"] for q in d["cells"].values())==18,"opposite halves")
        expect(set(x["families"])==set(NAMES),"family decomposition")
    fields=("id","state","exit","wall","cpus","minutes","total_cpu","user_cpu","sys_cpu","start","end","node")
    table={r[0]:dict(zip(fields,r[:len(fields)],strict=True)) for s in (root/"sacct.psv").read_text().splitlines() if (r:=s.split("|"))}
    jobs=[]
    for f in sorted((root/"registrations").glob("*.json"),key=lambda p:int(read(p)["job"])):
        reg=read(f);j=reg["job"];a=table[j];b=table[j+".batch"]
        expect(a["state"]==b["state"]=="COMPLETED" and a["exit"]==b["exit"]=="0:0" and a["total_cpu"]==b["total_cpu"],"job plus batch "+j)
        expect(int(a["cpus"])==reg["cpus"] and int(a["minutes"])==reg["minutes"] and reg["source"]==x["source"],"allocation identity")
        sec=seconds(a["total_cpu"]);reserve=reg["reserved_s"]
        jobs.append(dict(a,name=reg["name"],process_cpu_s=sec,reserved_cpu_s=reserve,allocated_wall_cpu_s=int(a["cpus"])*int(a["wall"]),
                         actual_ratio=reserve/sec,within_2x=reserve<=2*sec,stderr_sha256=listing["logs/"+j+".err"],stdout_sha256=listing["logs/"+j+".out"]))
    totals=dict(jobs=len(jobs),reserved_cpu_s=sum(j["reserved_cpu_s"] for j in jobs),
                process_cpu_s=round(sum(j["process_cpu_s"] for j in jobs),3),allocated_wall_cpu_s=sum(j["allocated_wall_cpu_s"] for j in jobs),
                individual_within_2x=all(j["within_2x"] for j in jobs),abnormal_job_ids=[j["id"] for j in jobs if j["exit"]!="0:0"])
    return x,dict(schema="T5-v3c-development-readback",release=x["source"],gate0=x["gate0"],gate1=x["gate1"],
                  compared_complete_trajectories=sums,compared_prefix_hashes=clocks,frozen_positions=[36,58],
                  complete_full_frame_replay=sums*61,checked_conditions=len(x["checks"]),unexecuted=x["unexecuted"],jobs=jobs,
                  totals=totals,pilot_projection=read(root/"budget.json") if (root/"budget.json").exists() else None,
                  result_sha256=sha(root/"development.json"),evidence_index_sha256=sha(root/"artifacts.sha256"),
                  stage_A_source_files=release["files"],prior_sources_file_sha256=sha(HERE/"predecessors.json"),
                  remote_root="/share/home/renly/renly-patrol-rsi/mainline/T5-observable-selector-v3c",
                  raw_layout="prefix/<case>/<role>/record.json; checks/<case>.json; registrations/<batch>.{intent,json}; logs/<job>.{out,err}",
                  stage0_new_facility_runs=0,H2=dict(generated=0,accessed=0,derived=0),selfcheck=check)


def signed(x):return f"{x:+.2f}" if x else "0.00"


def markdown(x,s):
    headline=f"门槛 0：{x['gate0']}。"
    if "primary" in x:
        ci=x["primary"];q=x["means"]
        headline+=(f"门槛 1：选择器减整向量的平均剩余缺额差为 **{signed(ci['mean'])} 秒**，单侧 95% 区间 "
                   f"**(−∞, {signed(ci['upper'])}] 秒**，"+("通过。" if x["gate1"]=="PASS" else "未通过。"))
    else:headline+="门槛 1 未评价，没有可报告的差值或区间。"
    ls=["# T5 v3c：可观测选择器开发结果", "",headline,"",
        f"旧面板 36 条、58 个完整策略。已核对 {s['compared_complete_trajectories']:,} 份轨迹，"
        f"逐策略复现 {s['complete_full_frame_replay']:,} 帧；截至决策帧逐一比较的公开帧哈希为 {s['compared_prefix_hashes']:,} 个。",
        "决策帧含在比较内。没有把决策以后的信号用来选策略。"]
    if "primary" in x:
        ls+=["",f"选择器、整板赢家、可见族标签的参照，跨半平均剩余缺额依次为 **{q['S_gap']:.2f}、{q['W_gap']:.2f}、{q['F_gap']:.2f} 秒**。"
             f"用户提供的整板／按族补算为 226.01／120.37 秒；本次核算使用冻结的 58 项和原接受序。","",
             "## 逐格选择","", "格键依次为设施类型、首个信号域、信号类别。NONE 表示首次提案时没有可用的风险信号。训练少于 2 条时使用该方向的整板赢家。",
             "", "| 选择→评价 | 格键 | 训练 | 评价 | 锁定向量 | 回退 |","|---|---|---:|---:|---|---|"]
        for direction,d in x["directions"].items():
            for c,v in d["cells"].items():
                ls.append(f"| {direction} | {c.replace('|',' / ')} | {v['training']} | {v['evaluation']} | {v['chosen']} | {'是' if v['fallback'] else '否'} |")
        ls+=["","| 方向 | 整板赢家 | S 剩余秒 | W 剩余秒 | 按族参照秒 | 回退格／总格 | 评价中回退行／18 |","|---|---|---:|---:|---:|---:|---:|"]
        for direction,d in x["directions"].items():
            g=d["means"];ls.append(f"| {direction} | {d['whole']} | {g['S_gap']:.2f} | {g['W_gap']:.2f} | {g['F_gap']:.2f} | {d['fallback_cells']}/{len(d['cells'])} | {d['fallback_rows']} |")
        ls+=["","## 逐族剩余缺额","", "| 族（各 6 条） | 选择器（秒） | 整板（秒） | 按族参照（秒） | 选择器减整板（秒） |","|---|---:|---:|---:|---:|"]
        for f,n in NAMES.items():
            v=x["families"][f];ls.append(f"| {n} | {v['S_gap']:.2f} | {v['W_gap']:.2f} | {v['F_gap']:.2f} | {signed(v['delta'])} |")
    else:
        ls+=["","## 首次分歧或未决",""]
        for k,o in x["checks"].items():
            if o["status"]!="PASS":ls.append(f"{k}：{o.get('field',o['status'])}，帧 {o.get('frame_index','—')}，时刻 {o.get('at_s','—')} 秒。")
    ls+=["","## 条件身份",""]
    if x.get("overlap"):
        ls+=["开发按设计复用 v3a 的 36/36 条。全包和实际原生输入在面板内均无重复，A/B 交集均为零。"
             "与 T4b（144 条）、T5 v1（84 条）、T5 v2（36 条）两种身份的交集均为零。"]
    else:ls+=["前置核验停止，没有追加身份审计。"]
    ls+=["","## Slurm 与回执","", "| 作业 | 用途 | 预留 CPU 秒 | 进程 CPU 秒 | 预留／实耗 |","|---|---|---:|---:|---:|"]
    for j in s["jobs"]:
        ls.append(f"| {j['id']} | {j['name']} | {j['reserved_cpu_s']} | {j['process_cpu_s']:.3f} | {j['actual_ratio']:.3f} |")
    t=s["totals"];ls+=["",f"合计 {t['jobs']} 个作业，预留 {t['reserved_cpu_s']} CPU 秒，进程实耗 {t['process_cpu_s']:.3f} CPU 秒。"
        f"分配核数乘墙时为 {t['allocated_wall_cpu_s']} 秒。试点计入原分母；设施调用 0；H2 的生成、读取、派生均为 0。",
        "","[冻结协议](protocol.md) · [逐条件与逐格数值](development.json) · [回执](development-receipt.json) · [原件索引](artifacts.sha256)"]
    if x["gate1"]!="PASS":
        ls+=["","开发门槛未通过，未拟合全板 S/W，未创建新面板或启动确认，无新面板效应量。"]
    return "\n".join(ls)+"\n"


if __name__=="__main__":
    evidence=Path(sys.argv[1]); x,s=verify(evidence)
    for name in ("development.json","artifacts.sha256","sacct.psv"):
        with (HERE/name).open("xb") as out:out.write((evidence/name).read_bytes())
    with (HERE/"development-receipt.json").open("x",encoding="utf8",newline="\n") as out:
        json.dump(s,out,indent=2,ensure_ascii=False);out.write("\n")
    with (HERE/"development-report.md").open("x",encoding="utf8",newline="\n") as out:out.write(markdown(x,s))
