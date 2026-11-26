"""Render the public FIT tables from aggregate readback. No study imports."""

import argparse
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FAMILIES = ("LONDON", "NETHERLANDS")
NAMES = {"LONDON": "伦敦", "NETHERLANDS": "荷兰", "ALL": "两族合计"}


def number(x):
    return "未建立" if x is None else f"{x:.6f}".rstrip("0").rstrip(".")


def as_table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|",
            *["| " + " | ".join(str(v) for v in row) + " |" for row in rows], ""]


def render(d):
    lines = ["# 阶段 1c 统计表", "",
             "差值一律为候选减共享父。L 的单位为秒，人员实耗的单位为人秒。下表显示到六位小数。"
             "整数微秒的原轮账保存在上一阶段，条件配对差取自封存评分原文。", "",
             "## 逐臂、逐轮的实际付费分布", "",
             "每格按（平均 L，平均人秒）×槽数列出。每槽独立完成 48 行。", ""]
    rows = []
    for r in d["rounds"]:
        scores = "、".join(f"({number(v['L_s'])}, {number(v['person_s'])}) × {v['slots']}"
                          for v in r["distribution"])
        rows.append([r["arm"], r["round"], scores, r["selected"] or "保留父", len(r["new_paid_slots"])])
    lines += as_table(["臂", "轮", "四个提案的评分分布", "获选槽", "由前轮改写新增的付费槽"], rows)
    lines += ["## 16 个实际评分的单点编辑", "",
              "同一编辑有 O、R 两张独立付费回执。等级 1、2、3 对应登记的 30、60、120 秒参数。", ""]
    rows = []
    for c in d["candidates"]:
        rows.append([c["edit"], " / ".join(c["slots"]), *(number(v) for v in c["means"]),
                     " / ".join(map(number, c["delta"])),
                     *[" / ".join(map(number, c["family_deltas"][f])) for f in FAMILIES],
                     d["saturation"]["ALL"]["L_min_hits_by_edit"][c["edit"]]])
    lines += as_table(["编辑", "付费槽", "平均 L", "平均人秒", "总差 L / 人秒", "伦敦差 L / 人秒",
                       "荷兰差 L / 人秒", "达到逐行最低 L 的条件数（含并列）"], rows)
    lines += ["## 输入结构", "",
              "r1 的十二行块签名有五项计数，依次为有外部扰动、扰动在 1,500 秒、扰动前有可完成的启动时点、"
              "这种时点只有 1–3 个，以及全窗无合法启动时点。逐行五个 0/1 标记的列和恰好构成块签名。"
              "这些是评价端的事后分组。", ""]
    rows = []
    for f in FAMILIES:
        st = d["structure"][f]
        for p in st["block_patterns"]:
            indices = [i for i, k in enumerate(st["blocks_in_order"], 1) if k == p["signature"]]
            rows.append([NAMES[f], "、".join(map(str, indices)), " ".join(map(str, p["signature"])),
                         p["blocks"], p["conditions"]])
    lines += as_table(["族", "FIT 块序号", "登记的五整数签名", "块数", "条件数"], rows)
    flags = {f: {tuple(s["flags"]): s["conditions"] for s in d["structure"][f]["row_patterns"]} for f in FAMILIES}
    rows = []
    for k in sorted(set().union(*flags.values())):
        values = [flags[f].get(k, 0) for f in FAMILIES]
        rows.append([" ".join(map(str, k)), *values, sum(values)])
    lines += as_table(["逐行标记", "伦敦条件数", "荷兰条件数", "合计"], rows)
    lines += ["## 逐行取优的空间", "",
              "每个条件的比较菜单包含全部 16 个已付编辑。若某行有并列，所有并列者都计为该行的最优者。"
              "这里的逐行最优使用评价端的完整结果。", ""]
    measures = (("缺额最优集合的公共编辑数", "L_optimum_intersection"),
                ("先缺额后工时的最优集合公共编辑数", "lex_optimum_intersection"),
                ("最低平均缺额，最佳固定编辑", "best_fixed_mean_L_s"),
                ("逐行最低缺额的平均", "row_min_mean_L_s"),
                ("保持逐行最低缺额的最少平均人秒", "least_person_at_row_min_L_s"),
                ("相对锁定策略可节省的平均人秒", "staff_gap_lock_vs_row_lex_s"),
                ("所有编辑在该行缺额相同", "all_edits_tie_on_L"),
                ("有多个并列缺额最优编辑", "multiple_L_winners"),
                ("有编辑比父降低缺额", "any_edit_lowers_parent_L"),
                ("锁定编辑比父降低缺额", "lock_lowers_parent_L"),
                ("锁定编辑未降缺额、另有编辑能降", "other_edit_helps_where_lock_does_not"),
                ("有编辑比锁定编辑缺额更低", "lock_above_row_min_L"),
                ("有编辑在锁定编辑的缺额下节省人秒", "another_edit_saves_staff_at_lock_loss"),
                ("有编辑比父降缺额且工时不增", "any_loss_gain_no_extra_staff"))
    rows = []
    for label, key in measures:
        values = []
        for f in (*FAMILIES, "ALL"):
            s = d["saturation"][f]
            v = s.get(key, s["row_counts"].get(key))
            values.append(len(v) if isinstance(v, list) else number(v))
        rows.append([label, *values])
    lines += as_table(["已评分编辑的比较", "伦敦（24 行）", "荷兰（24 行）", "整板（48 行）"], rows)
    lines += ["## Q1–Q3 条件外推", "",
              "每行含 24 个 FIT 条件，两个完整十二行块。方差为两块均差的无偏样本方差。"
              "FIT 上界按 g=2、df=1 计算。情景上界将相同的均差和方差代入 g=38、df=37。"
              "判定使用未舍入的单侧 95% 上界。", ""]
    rows = []
    for e in d["endpoints"]:
        threshold = ("< " if e["operator"] == "<" else "≤ +") + str(e["threshold"])
        rows.append([e["question"], NAMES[e["family"]], e["metric"], " / ".join(map(number, e["block_means"])),
                     number(e["mean"]), number(e["block_sample_variance"]), number(e["fit_upper_g2"]),
                     number(e["conditional_upper_g38"]), threshold, e["conditional_status"]])
    lines += as_table(["端点", "族", "量", "块 1 / 块 2", "均差", "块方差", "FIT 上界", "38 块情景上界",
                       "门槛", "情景预测"], rows)
    lines += ["每族两个块恰好属于两个结构簇，r1 描述性簇上界的自由度为 1。"
              "当前 FIT 的簇上界与两块主上界重合。实际 DEV 的簇数、变异及硬约束记录均未观测。", ""]
    rows = [[e["question"], *e["improved_equal_worse"], number(e["worst_row_delta"]),
             e["fit_cluster_k"], e["fit_cluster_df"], number(e["fit_cluster_upper"])] for e in d["endpoints"]]
    lines += as_table(["端点", "改善行", "相同行", "较差行", "最坏行差", "结构簇数", "簇自由度",
                       "FIT 描述性簇上界"], rows)
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = render(json.loads((HERE / "statistics.json").read_bytes())).encode("utf-8")
    target = HERE / "tables.md"
    if args.check:
        if target.read_bytes() != raw:
            raise SystemExit("table contents do not match the aggregate record")
        print("PASS all published tables reproduce the aggregate record")
    else:
        with target.open("xb") as stream:
            stream.write(raw)
