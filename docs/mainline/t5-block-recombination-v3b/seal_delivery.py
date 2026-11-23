"""Format already saved Stage-A records and reconcile their terminal Slurm bill, without facility imports."""
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
import sys

FAMILIES=("WATER_HEAT","NETWORK_POWER","RESERVE_TRANSFER","COOLING_ACCESS","LONDON","NETHERLANDS")
NAMES=("水侧与热","网络与供电","有限备用","冷却与通行","伦敦式","荷兰式")
T4="docs/mainline/t4b-holdout-confirmation-v2"


def digest(p):
    return sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_bytes())


def seconds(s):
    d,_,rest=s.rpartition("-")
    n=0.
    for part in rest.split(":"):
        n=n*60+float(part)
    return n+86400*int(d or 0)


def reconcile(e, published):
    index={r.split("  ",1)[1]:r.split("  ",1)[0] for r in (e/"evidence.sha256").read_text().splitlines() if r}
    for f,h in index.items():
        if f.startswith(("positions/","replay/")):
            continue  # private originals and IPC rows stay on the server; their identities are indexed below.
        if digest(e/f)!=h:
            raise ValueError(f)
    c=read(e/"construction.json"); result=read(e/"result.json"); src=read(e/"release.json")
    assert digest(e/"construction.json")==digest(published/"construction.json")==result["construction_sha256"]
    assert c["release"]==result["release"]==src["commit"]
    assert all(index["replay/"+k+"/row.json"]==v for k,v in c["rows_sha256"].items())
    for k,v in result["rows"].items():
        for n,field in (("original.jsonl.gz","raw_sha256"),("row.json","row_sha256"),("native-entry.json","entry_sha256")):
            assert index["positions/"+k+"/"+n]==v[field]
    expected_jobs={read(p)["job"]:read(p) for p in (e/"registrations").glob("*.json")}
    fields=("id","name","state","exit","elapsed","cpus","limit_min","total_cpu","user_cpu","system_cpu","start","end","node","partition","mem")
    allocations={};with_steps={}
    for line in (e/"sacct.psv").read_text().splitlines():
        if line.strip():
            rec=dict(zip(fields,line.rstrip("|").split("|"),strict=True));allocations[rec["id"]]=rec
    for line in (e/"sacct-with-steps.psv").read_text().splitlines():
        if not line.strip():
            continue
        rec=dict(zip(fields,line.split("|")[:len(fields)],strict=True))
        assert rec["id"] not in with_steps
        with_steps[rec["id"]]=rec
    assert allocations.keys()==expected_jobs.keys() and {j for j in with_steps if "." not in j}==expected_jobs.keys()
    jobs=[]
    for j in sorted(expected_jobs,key=int):
        rec=with_steps[j];batch=with_steps[j+".batch"]
        if j not in expected_jobs:
            raise ValueError("unexpected allocation "+j)
        reg=expected_jobs[j]
        assert all(rec[k]==allocations[j][k] for k in fields if k not in ("total_cpu","user_cpu","system_cpu"))
        assert (rec["total_cpu"],rec["state"],rec["exit"])==(batch["total_cpu"],batch["state"],batch["exit"])
        assert rec["name"]=="b3-"+reg["name"] and int(rec["cpus"])==reg["cpus"] and int(rec["limit_min"])==reg["minutes"]
        assert reg["release"]==src["commit"] and reg["files"]==src["files"] and int(rec["elapsed"])>=0
        terminal=e/"jobs"/reg["name"]/"terminal.json"
        assert terminal.exists() and read(terminal)["job"]==j
        if reg["name"].startswith("native-"):
            assert reg["construction"]==result["construction_sha256"]
        jobs.append(dict(rec,registration=reg["name"],reserved_s=reg["reserved_s"],process_cpu_s=seconds(rec["total_cpu"]),
                         allocated_elapsed_s=int(rec["cpus"])*int(rec["elapsed"]),terminal=read(terminal),
                         terminal_sha256=digest(terminal),stdout_sha256=index["logs/"+j+".out"],stderr_sha256=index["logs/"+j+".err"]))
    assert len(jobs)==len(expected_jobs)==len(set(x["id"] for x in jobs))
    totals=dict(jobs=len(jobs),reserved_s=sum(x["reserved_s"] for x in jobs),process_cpu_s=round(sum(x["process_cpu_s"] for x in jobs),3),
                allocated_elapsed_s=sum(x["allocated_elapsed_s"] for x in jobs),nonzero=[x["id"] for x in jobs if (x["state"],x["exit"])!=("COMPLETED","0:0")])
    return c,result,dict(jobs=jobs,accounting=totals,accounting_source=dict(
        allocation_only_sha256=digest(e/"sacct.psv"),including_steps_sha256=digest(e/"sacct-with-steps.psv"),
        convention="sacct -X binds job identity/exit/allocation; TotalCPU from full sacct, .batch cross-check, count each allocation once."),
        public_inputs=read(published/"predecessor.json"),
        stage_A=src,vector_publication=read(e/"published-construction.json"),vector_sha256=c["construction"].get("theta_sha256"),
        check_before_replay=read(e/"selfcheck.json"),result_sha256=index["result.json"],original_index_sha256=digest(e/"evidence.sha256"),
        durable_files_indexed=len(index),replay_rows_compared=len(c["rows_sha256"]),native_rows_compared=len(result["rows"]),
        failure_positions=result["errors"],replay_errors=c["errors"],old_facility_runs=0,new_facility_entries=result["entries"],
        old_frames=c["frames"],stage_B_started=False,H2_generated=0,H2_accessed=0,H2_derived=0,
        server_root="/share/home/renly/renly-patrol-rsi/mainline/T5-block-recombination-v3b",
        server_layout="replay/<role>/<condition>/row.json; positions/<condition>/{native-entry.json,original.jsonl.gz,row.json}; logs/<job>.{out,err}; jobs/<batch>/{entry,terminal}.json; registrations/<batch>.{intent,json}")


def fmt(x):
    return f"{x:+.2f}" if x else "0.00"


def report(c,r,seal):
    assert r["status"] in ("FAIL_STOP","UNRESOLVED_STOP","PASS")
    a=seal["accounting"]; comparisons=r["contrasts"]
    if comparisons:
        d,u=comparisons[0]["mean"],comparisons[0]["upper95"]
        verdict=("通过" if r["status"]=="PASS" else "未通过")
        headline=(f"**阶段一{verdict}。** 重组减去 58 项全板最优的平均服务缺额差为 **{fmt(d)} 秒**，"
                  f"单侧 95% 区间为 **(−∞, {fmt(u)}] 秒**。重组减去按全板 L 选优的整向量同为 "
                  f"**{fmt(comparisons[1]['mean'])} 秒**，区间 **(−∞, {fmt(comparisons[1]['upper95'])}] 秒**。"
                  f"原协议的两项对照都选出 `{r['control']}`；这两行共享同一组条件差与重抽索引。")
    else:
        headline="**阶段一未决。** 原分母不齐或未得到合法重组向量，两个均差和区间均不可给出。"
    lines=["# T5 v3b · 分块重组开发诊断", "", headline,""]
    if comparisons:
        rows=r["rows"]
        lines.extend([f"原板 36 条条件等权，重组平均 L 为 {mean(x['L'] for x in rows.values()):.2f} 秒，"
                      f"对照为 {mean(x['control_L'] for x in rows.values()):.2f} 秒。"
                      + ("按预注册停止，不启动阶段二，不改分块再试。" if r["status"]=="FAIL_STOP" else "进入阶段二前必须解决注册预算口径。"),""])
    lines+=["## 逐族重组、请求和服务", "",
            "每族 6 条条件、348 条原轨迹。正差表示重组增加缺额。请求数按实际公开提案；同一条件可以关联多个块，L 只按条件计一次。", "",
            "| 族 | 条件 | 族内供体 | 各块提案 | 签发／提案 | 无归属条件／无提案轨迹 | 重组 L | 对照 L | 均差（秒） |",
            "|---|---:|---|---|---:|---:|---:|---:|---:|"]
    chosen=c["construction"]
    for f,n in zip(FAMILIES,NAMES):
        z=c["mapping"][f]; group=[v for v in r["rows"].values() if v["family"]==f]
        blocks="、".join(k+" "+str(v) for k,v in z["block_requests"].items()) or "无"
        metrics=([f"{mean(x[k] for x in group):.2f}" for k in ("L","control_L")]+[fmt(comparisons[0]["by_family"][f])]) if comparisons else ["—"]*3
        lines.append(f"| {n} | {len(group)}/6 | {chosen.get('selected',{}).get(f,'—')} | {blocks} | {z['issued']}/{z['requests']} | "
                     f"{z['no_attribution_conditions']}/6；{z['no_request_trajectories']}/348 | "+" | ".join(metrics)+" |")
    lines+=["","58 个角色、2,088 条历史的回放及完整动作链均按各自的原轨迹进行。每条 61 帧；[构造记录](construction.json)列出每族完整最优集合、每域的票数、并列裁决和每条无请求轨迹。"]
    if chosen["status"]=="LOCKED":
        conflicts=[f"{k}：{v['family']}（{v['source']}，{v['votes'][v['family']]} 票）" for k,v in chosen["domains"].items() if v["conflict"]]
        lines+=["","兼容性搜索"+("找到能同时满足各族的并列最优组合。" if chosen["fully_compatible"] else
                    "未找到能同时满足各族的并列最优组合。按事先决定，冲突块归："+ "；".join(conflicts)+"。"),
                "全局四项均取 B_cost。其余域归属见构造记录。全局 `lookahead=0` 时，v2 MAIN 使用直接动作菜单；移植局部坐标不会移植供体的全局前瞻设置。"
                "该诊断考察这一个固定拼法；请求共同落到一个块并不能证明该块造成了全部损失。"]
    lines+=["","## 条件身份与版本","","阶段一故意复用 v3a 的 36/36 个条件。整包及实际设施输入在板内均无重复，A/B 两半交集为零；"
            "与 T4b 的 144 条、T5 v1 的 84 条、T5 v2 的 36 条逐种身份对照均为零。本轮未生成新的 FIT/DEV 面板。",
            "",f"阶段 A 源码与协议 `{c['release'][:8]}`；评分前公开的唯一向量 `{seal['vector_publication']['commit'][:8]}`；"
            "v3a 原件与原得分封存版本 `29ac5a2e`。H2 的生成、访问、派生均为 0。M_hot 仅回放其历史，没有热启动搜索。",
            "","## 计算与回执","",
            f"Slurm 使用 {a['jobs']} 个作业，预留 {a['reserved_s']:,} CPU 秒；进程 CPU 实耗 {a['process_cpu_s']:,.3f} 秒，"
            f"分配核数×墙时 {a['allocated_elapsed_s']:,} 秒。非正常作业：{a['nonzero'] or '无'}。"
            f"原生入口 {r['entries']}/36，完成评分 {r['scored']}/36；回放成功 {c['replayed']}/2,088，逐帧响应 {c['frames']:,}/127,368。"
            f"回放失败 {len(c['errors'])}，研究位置失败／未执行 {len(r['errors'])}，没有重跑。",
            "",f"完整逐条件 L/U、资源、费用、配对和原件身份见[数值结果](result.json)；"
            "各作业的申请、实耗、日志和终态见[交付回执](receipt.json)，[包含批步骤的终态账](sacct-with-steps.psv)按作业汇总一次，"
            "原件逐文件索引见[evidence.sha256](evidence.sha256)。"
            "大轨迹保留在回执列出的私有目录。区间仅描述这块开发板及其固定供体、对照和映射，不代表独立确认或 RSI 收益。"]
    return "\n".join(lines)+"\n"


if __name__=="__main__":
    evidence,published=map(Path,sys.argv[1:])
    c,r,s=reconcile(evidence,published)
    for src,dst in (("result.json","result.json"),("evidence.sha256","evidence.sha256"),("sacct-with-steps.psv","sacct-with-steps.psv")):
        if (published/dst).exists():
            assert digest(published/dst)==digest(evidence/src)
            continue
        with (published/dst).open("xb") as h:
            h.write((evidence/src).read_bytes())
    with (published/"receipt.json").open("x",encoding="utf8",newline="\n") as h:
        json.dump(s,h,indent=2,ensure_ascii=False);h.write("\n")
    with (published/"README.md").open("x",encoding="utf8",newline="\n") as h:
        h.write(report(c,r,s))
