"""Render the public FIT report from the independently read-back aggregate results."""

import argparse
import json
from pathlib import Path


def short(value):return value[:12] if value else "—"


def means(score):
    if score is None:return ("—","—")
    return (f"{score['L_mean_s']:.6f}",f"{score['person_mean_s']:.6f}")


def write(r):
    complete=r["status"]=="DUAL_LOCKED_PENDING_REVIEW"
    lines=["# T8 阶段 1b · FIT", "",
           (f"共享父基线和两臂共完成 {r['scored_positions']:,} 个原生位置。O、R 各结束四轮并锁定子策略，交 PI 审阅。"
            if complete else f"FIT 已停止，原生入口 {r['native_starts']} 个，完成 {r['scored_positions']} 个。停止记录为 `{r['stop']}`。"),
           "", "## 基线与终态", "",
           "| 策略 | 策略 ID | FIT 完成分母 | 平均缺额 L（秒） | 平均工时（人秒） |",
           "|---|---|---:|---:|---:|"]
    b=r["baseline"];loss,staff=means(b["score"])
    lines.append(f"| 共享父 V** | `{b['id']}` | {b['completed']}/48 | {loss} | {staff} |")
    for a in ("O","R"):
        arm=r["arms"][a];lock=arm["locked"]
        loss,staff=means(lock["score"] if lock else None)
        ident=f"`{lock['id']}`" if lock else "未锁定"
        lines.append(f"| {a} | {ident} | {arm['completed']}/768（搜索位置） | {loss} | {staff} |")
    lines+=["","终态均值来自该描述符的一份已付 48 行 FIT 评分；搜索位置分母包含全部 16 个提案。"
            "以下均值显示六位小数，原始整数微秒合计、完整策略 ID 和父链见[结果原件](results.json)。",
            "", "## 每轮提案", ""]
    for a in ("O","R"):
        lines+=["### "+a,"","| 轮·槽 | 提案 ID 前 12 位 | 相对当轮父的改动 | 真付费 / 完成数 | 平均 L | 平均人秒 | 新增且付费 | 获选 |",
                "|---|---|---|---:|---:|---:|---|---|"]
        for rd in r["arms"][a]["rounds"]:
            for s in rd["slots"]:
                cells="、".join(s["cells"] or []) or "—"
                loss,staff=means(s["score"])
                paid="是" if s["paid_full"] else s["status"]
                lines.append(f"| {rd['round']}·{s['slot']} | `{short(s['id'])}` | {cells} | {paid}，{s['completed']}/48 | "
                             f"{loss} | {staff} | {'是' if s['membership_changed_and_paid'] else '否'} | {'是' if s['selected'] else '否'} |")
        lines.append("")
    lines+=["## 程序字节、改写与付费谱系","","| 轮 | O 轮前程序 SHA-256 | O 轮后程序 SHA-256 |",
            "|---:|---|---|"]
    for rd in r["arms"]["O"]["rounds"]:
        lines.append(f"| {rd['round']} | `{rd['program_before_sha256'] or '—'}` | `{rd['program_after_sha256'] or '—'}` |")
    lines.append("")
    for rd in r["arms"]["R"]["rounds"]:
        next_=rd["next_roster_change"];c=rd["credit"];idx=rd["round"]
        change="无后继轮" if not next_ else next_["classification"]
        note=f"信用来自本轮槽 {c['slot']} 的 `{c['cell']}`，方向 {c['direction']:+d}，相对轮前父的 48 行缺额合计差 {c['candidate_minus_incumbent_L_sum_us']} 微秒。" if c else ""
        lines.append(f"- 第 {idx} 轮，`{rd['rewrite_reason']}`。{note}后继名册为 `{change}`。")
        if rd["patch"]:
            lines.append("  实际根替换后的程序为 `"+json.dumps(rd["patch"][0]["value"],separators=(",",":"))+"`。")
        if next_ and next_["classification"]=="CHANGED_MEMBERSHIP" and idx<4:
            successor=r["arms"]["R"]["rounds"][idx]
            changed=[s for s in successor["slots"] if s["membership_changed_and_paid"]]
            if changed:
                for s in changed:
                    l,p=means(s["score"])
                    lines.append(f"  后继轮槽 {s['slot']} 的 `{short(s['id'])}` 实际付费，平均 L {l} 秒、人秒 {p}，"
                                 f"{'获选' if s['selected'] else '未获选'}。")
            else:lines.append("  此后继轮没有完成付费的新成员。")
    lineage=r["arms"]["R"]["lineage"]
    trace=" → ".join([short(b["id"]),*(f"R{x['round']}.{x['slot']} {short(x['id'])}" for x in lineage)])
    lines+=["","R 的已选父链为 "+trace+"。"]
    selected=[f"R{x['round']}.{x['slot']}" for x in lineage if x["newly_paid"]]
    if complete:
        lines.append(("其中因程序改写新增、实际付费且进入锁定父链的槽为 "+"、".join(selected)+"。") if selected
                     else "本次锁定父链中，由改写新增且实际付费的槽数为 0。")
    lines+=["","## 作业、预算与留痕","",
            "| Slurm | 阶段 | 终态 / 退出 | 预留 CPU 秒 | 实耗 CPU 秒 |","|---:|---|---|---:|---:|"]
    for j in r["jobs"]:
        lines.append(f"| {j['job']} | {j['stage']} | {j['state']} / {j['exit']} | {j['reserved_cpu_s']:,} | {j['actual_cpu_s']} |")
    lines+=["",f"共 {len(r['jobs'])} 个作业，预留 {r['total_reserved_cpu_s']:,} CPU 秒，Slurm 实耗 {r['total_slurm_cpu_s']} CPU 秒。"
             f"另有本地整批核对进程树实耗 {r['local_intake_comparison_cpu_s']} CPU 秒。上限为 10 个作业和 285,900 CPU 秒。"]
    if "pilot_projection" in r:
        p=r["pilot_projection"]
        lines.append(f"试点 384 个位置实耗 {p['pilot_total_cpu_s']} CPU 秒。余下 1,152 个位置的线性外推为 "
                     f"{p['extrapolated_cpu_s']} CPU 秒，两倍为 {p['twice_extrapolated_cpu_s']} 秒；"
                     f"综合上限 {p['registered_and_measured_ceiling_s']} 秒，六个作业实际预留 {p['planned_reserved_cpu_s']} 秒。")
    lines+=["",f"核对了 {r['rounds_verified']} 份轮账、{r['signed_events_verified']} 条签名事件和 {r['signed_position_role_observations']} "
             f"份原生位置角色审计。原生保留文件共 {r['native_gzip_bytes']:,} 字节；私有索引承诺为 `{r['retained_position_index_sha256']}`。",
             "", "首次作业 135577 在 Python 入口前失败，费用计入上表。恢复使用同一面板和已消费请求的签名回执。"
             "本报告只描述这一次固定 FIT 搜索。DEV 评分为 0，H2 与 H3 原始材料访问为 0。"
             "[原失败记录](../scoring/parent-a1/terminal.json) · [Slurm 原账](sacct.psv) · [FIT 查重](../fit-overlap/README.md)"]
    return "\n".join(lines)+"\n"


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("results",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--check",action="store_true")
    a=p.parse_args();raw=write(json.loads(a.results.read_bytes())).encode("utf-8")
    if a.check:
        if a.output.read_bytes()!=raw:raise SystemExit("FIT report differs from saved aggregates")
        print("PASS all reported table rows, program hashes, lineage and budgets match saved results")
    else:
        with a.output.open("xb") as f:f.write(raw)
