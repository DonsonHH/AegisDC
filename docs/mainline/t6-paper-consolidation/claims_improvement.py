"""C3. Attribute T5 development results and check transfer to the frozen new panel."""

BASE = "docs/mainline/"
D1 = BASE + "t5-ordinary-improvement-development-v1/"
D2 = BASE + "t5-ordinary-improvement-development-v2/"
D3A = BASE + "t5-landscape-diagnostic-v3a/"
D3B = BASE + "t5-block-recombination-v3b/"
D3C = BASE + "t5-observable-selector-v3c/"

V1 = ("4ade9217", D1 + "results.json.gz")
V2 = ("0e89b678", D2 + "results.json.gz")
V3A = ("29ac5a2e", D3A + "results.json.gz")
V3B = ("9360a3c8", D3B + "result.json")
DEV = ("f3027bd7", D3C + "development.json")
NEW = ("87cdd718", D3C + "confirmation-result.json")
LOCK = ("a9398d3f", D3C + "locked-selector.json")
MANUAL = ("0e89b678", D2 + "manual-references.json")
V2_SEARCH = ("93280276", "src/aegis_improvement_v2/search.py")
A_DESIGN = ("de9a56ed", D3A + "design.json")
B_RECEIPT = ("9360a3c8", D3B + "receipt.json")

OLD_PAIR = ["/rows/{i}/S_L", "/rows/{i}/W_L"]
NEW_PAIR = ["/conditions/{i}/arms/S/L", "/conditions/{i}/arms/W/L"]


def build(book):
    numbers = []
    counterexamples = []

    def add(stage, key, label, unit, source, fields, op="value", rows=None):
        identifier = f"C3.{stage}.{key}"
        metric = book.num(identifier, label, unit, *source, fields, op, rows,
                          stage=stage, level="确认" if stage == "v3c_new" else "开发")
        if unit == "比例":
            metric["display"] = format(metric["value"], ".2%")
        elif unit == "比例差":
            metric["display"] = f"{metric['value'] * 100:.2f} 个百分点"
        numbers.append(metric)
        return identifier

    def interval(stage, key, label, source, prefix, endpoints):
        for suffix, name, field in endpoints:
            add(stage, f"{key}.{suffix}", f"{label} {name}", "秒", source, prefix + "/" + field)

    def loss(stage, source, row_key, row_path, first, second, metadata):
        key = "loss." + row_key
        fields = [row_path + "/" + first, row_path + "/" + second]
        outcome_ids = [
            add(stage, key + ".candidate", row_key + " 候选 L", "秒", source, fields[0]),
            add(stage, key + ".control", row_key + " 对照 L", "秒", source, fields[1]),
            add(stage, key + ".delta", row_key + " 候选减对照的 L", "秒", source, fields, "subtract"),
        ]
        counterexamples.append({
            "stage": stage, "level": "确认" if stage == "v3c_new" else "开发",
            "condition": row_key, **metadata, "number_ids": outcome_ids,
            "source": book.ref(*source, row_path),
        })

    def directions(stage, source, pair, rows, label):
        for op, word in (("better", "优"), ("equal", "平"), ("worse", "劣")):
            add(stage, op, label + "逐条件" + word, "条件", source, pair, op, rows)

    both = [("mean", "点估计", "mean"), ("lo", "双侧 95% 下界", "lo"),
            ("hi", "双侧 95% 上界", "hi")]
    v1 = book.get(*V1)
    manual = book.get(*MANUAL)
    locks = book.get("4ade9217", D1 + "locked.json")["tracks"]
    for name, track in (("M", "MAIN"), ("M_HOT", "HOT")):
        record = manual["references"][name]
        if (record["original_label"], record["descriptor_sha256"], record["theta"]) != (
            locks[track]["source_label"], locks[track]["descriptor"], locks[track]["theta"]
        ):
            raise ValueError("v1 manual reference does not match the original lock: " + name)

    add("v1", "n", "人工主轨与 V** 的开发配对", "条件", V1, "/overall/pairs/MAIN/V_COST/available")
    for arm, label in (("V_COST", "V**"), ("B_COST", "B_cost")):
        interval("v1", arm, "主轨锁定策略减 " + label, V1, "/overall/pairs/MAIN/" + arm + "/metrics/L", both)
    for i, row in enumerate(v1["rows"]):
        if row["arms"]["MAIN"]["L"] > row["arms"]["V_COST"]["L"]:
            loss("v1", V1, row["key"], f"/rows/{i}", "arms/MAIN/L", "arms/V_COST/L",
                 {"family": row["family"], "candidate": "MAIN-r01-c03", "comparator": "V**"})

    add("v2", "n", "共同 DEV 条件数", "条件", V2, "/comparisons/MAIN/estimates/U/R/conditions")
    for method in ("U", "R"):
        add("v2", f"{method}.seeds", method + " 的搜索种子数", "种子", V2,
            f"/comparisons/MAIN/search/{method}/n_seeds")
        for seed in range(1, 4):
            add("v2", f"{method}.fit.{seed}", f"主轨 {method} 第 {seed} 个种子的实际付费 FIT 位置",
                "位置", V2, f"/fit_call_budget/MAIN-{seed}/{method}")
    for arm, label in (("R", "等预算随机搜索 R"), ("B_COST", "B_cost")):
        interval("v2", arm, "主轨 U 减" + label, V2, "/comparisons/MAIN/estimates/U/" + arm, both)

    add("v3a", "n", "地形诊断面板", "条件", V3A, "/conditions", "length")
    add("v3a", "pool", "冻结随机策略池", "向量", A_DESIGN, "/roles/random", "length")
    for half in ("A", "B"):
        add("v3a", "n." + half, half + " 半板的条件数", "条件", V3A, f"/halves/{half}/B_COST/scored")
    registered_k = book.get(*A_DESIGN)["analysis"]["k"]
    for k in (6, 24):
        add("v3a", f"k{k}", "选择半抽取的候选数", "向量", A_DESIGN, f"/analysis/k/{registered_k.index(k)}")
        add("v3a", f"k{k}.recovery", f"k={k} 双向合并的平均余量回收率", "比例", V3A,
            f"/landscape/curves/{k}/pooled/recovered/mean")
    add("v3a", "delta", "扩大候选集后的双向平均回收率之差", "比例差", V3A, "/landscape/delta_24_minus_6/mean")
    for direction in ("A_to_B", "B_to_A"):
        add("v3a", "gap." + direction, direction + " 评价半的 B_cost 至全知距离", "秒", V3A,
            f"/landscape/curves/6/{direction}/denominator")
    for field, label, unit in (
        ("easy_at_least", "空间过易所需的小候选集最低回收率", "比例"),
        ("search_strictly_below", "有搜索余量要求小候选集回收率严格低于此值", "比例"),
        ("extra_gain_at_least", "有搜索余量还要求扩大候选集至少增加的回收率", "比例差"),
    ):
        add("v3a", "threshold." + field, label, unit, A_DESIGN, "/analysis/decision/" + field)

    v3b = book.get(*V3B)
    if v3b["contrasts"][0] != v3b["contrasts"][1]:
        raise ValueError("v3b preregistered controls do not share the same paired results")
    add("v3b", "n", "固定分块重组与整向量的已评分开发配对", "条件", V3B, "/scored")
    interval("v3b", "delta", "固定重组减整板最优", V3B, "/contrasts/0",
             [("mean", "配对均差", "mean"), ("hi", "单侧 95% 上界", "upper95")])
    add("v3b", "next_stage_starts", "第二阶段启动数（回执启动标志为真计一次）", "次",
        B_RECEIPT, "/stage_B_started", "count_true")
    loss("v3b", V3B, "A-1-01", "/rows/A-1-01", "L", "control_L",
         {"family": v3b["rows"]["A-1-01"]["family"], "candidate": "固定分块重组", "comparator": v3b["control"]})

    dev = book.get(*DEV)
    old_rows = range(len(dev["rows"]))
    add("v3c_dev", "n", "旧板两个方向合并的评价条件", "条件", DEV, "/rows", "length")
    add("v3c_dev", "pool", "旧板完整向量数", "向量", DEV, "/original_denominator/1")
    for arm in ("S", "W"):
        add("v3c_dev", arm + ".gap", arm + " 的跨半平均剩余缺额 L−L*", "秒", DEV, f"/means/{arm}_gap")
    interval("v3c_dev", "delta", "选择器减选择半整板赢家", DEV, "/primary",
             [("mean", "配对均差", "mean"), ("hi", "单侧 95% 上界", "upper")])
    directions("v3c_dev", DEV, OLD_PAIR, old_rows, "S 相对选择半整板赢家")
    for i, row in enumerate(dev["rows"]):
        if row["S_L"] > row["W_L"]:
            loss("v3c_dev", DEV, row["key"], f"/rows/{i}", "S_L", "W_L",
                 {"family": row["family"], "direction": row["direction"], "cell": row["cell"],
                  "candidate": row["selector"], "comparator": row["whole"]})

    new = book.get(*NEW)
    new_rows = range(len(new["conditions"]))
    add("v3c_new", "n", "新板 S 与冻结 W 的已配对条件", "条件", NEW, "/comparisons/W/pairs")
    interval("v3c_new", "delta", "新板 S 减冻结 W", NEW, "/comparisons/W/ci",
             [("mean", "配对均差", "mean"), ("lo", "双侧 95% 下界", "lower"),
              ("hi", "双侧 95% 上界", "upper")])
    directions("v3c_new", NEW, NEW_PAIR, new_rows, "S 相对冻结 W")
    add("v3c_new", "W.at_bound", "W 的 L 等于已认证全知下界", "条件", NEW,
        ["/conditions/{i}/arms/W/L", "/conditions/{i}/lower/certified_min"], "equal", new_rows)
    for arm in ("S", "W"):
        add("v3c_new", arm + ".gap", arm + " 在新板的平均剩余缺额 L−L*", "秒", NEW, f"/roles/{arm}/gap")
    reserve = [i for i, r in enumerate(new["conditions"]) if r["family"] == "RESERVE_TRANSFER"]
    add("v3c_new", "reserve.n", "有限备用族新板条件", "条件", NEW, ["/conditions/{i}/family"], "count", reserve)
    add("v3c_new", "reserve.delta", "有限备用族 S 减 W 的平均服务缺额", "秒", NEW, NEW_PAIR, "mean_delta", reserve)
    for i, row in enumerate(new["conditions"]):
        s, w = row["arms"]["S"], row["arms"]["W"]
        if s["L"] > w["L"]:
            selection = s["selection"]
            loss("v3c_new", NEW, row["key"], f"/conditions/{i}", "arms/S/L", "arms/W/L",
                 {"family": row["family"], "cell": selection["cell"], "candidate": selection["selected"],
                  "comparator": w["entry"]["actual"]})

    stages = {
        "v1": {
            "level": "开发", "gate": v1["development_gate"],
            "finding": "主轨和热启动轨的锁定向量均来自手写首批候选。两轨原始开发得分保留作人工参照。"
                       "付费评价选中了这些向量，无法把它们的构造或相对基线的降幅归因于反馈提案。",
            "sources": [
                book.ref("4ade9217", "src/aegis_improvement/improver.py", "L14-L19"),
                book.ref("4ade9217", D1 + "U.json", "/U/proposal/first_batch_levels/MAIN/2"),
                book.ref("4ade9217", D1 + "U.json", "/U/proposal/first_batch_levels/HOT/0"),
                book.ref("4ade9217", D1 + "locked.json", "/tracks/MAIN/source_label"),
                book.ref("4ade9217", D1 + "locked.json", "/tracks/HOT/source_label"),
                book.ref(*MANUAL, "/interpretation"), book.ref(*MANUAL, "/references/M"),
                book.ref(*MANUAL, "/references/M_HOT"), book.ref(*V1, "/development_gate"),
            ],
        },
        "v2": {
            "level": "开发", "gate": book.get(*V2)["development_gate"],
            "finding": "去掉人工锚点后，U 用付费 FIT 反馈更新算子得分，也保存接受的现任优胜向量。"
                       "提案代码每次仍把根向量传给突变函数，没有从现任优胜向量连续爬山。"
                       "共同 DEV 上先求各搜索种子的平均 L，再取算法各自的种子中位数作差。U 对 R 更差，"
                       "对 B_cost 的区间上界恰好触界。两项均未通过要求上界严格为负的开发门槛。",
            "sources": [book.ref(*V2_SEARCH, "L60-L65"), book.ref(*V2_SEARCH, "L93-L105"),
                        book.ref("93280276", D2 + "protocol.md", "L23"),
                        book.ref(*V2, "/fit_call_budget"), book.ref(*V2, "/development_gate")],
        },
        "v3a": {
            "level": "开发", "verdict": book.get(*V3A)["landscape"]["decision"],
            "finding": "在一半条件上按 L 选出整向量，再到另一半评分。双向合并以两半 B_cost 到认证全知的缺额差为分母。"
                       "增加候选数后平均回收率下降。较小候选集的回收率落在两条判读线之间，预注册诊断为“不确定”。",
            "sources": [book.ref(*A_DESIGN, "/analysis/decision"), book.ref(*V3A, "/landscape/decision"),
                        book.ref("de9a56ed", D3A + "protocol.md", "L19-L25")],
        },
        "v3b": {
            "level": "开发", "verdict": v3b["status"], "stage_B_started": book.get(*B_RECEIPT)["stage_B_started"],
            "finding": "固定分块重组的平均缺额增加。预定的两个整板对照按相同规则都选中 MAIN-R-3，"
                       "共享配对差与重抽索引。阶段一失败后停止，后续搜索比较未启动。",
            "sources": [book.ref("8fb44c7c", D3B + "protocol.md", "L21-L26"),
                        book.ref(*V3B, "/control"), book.ref(*V3B, "/contrasts/1"),
                        book.ref(*V3B, "/status"), book.ref(*B_RECEIPT, "/stage_B_started")],
        },
        "v3c_dev": {
            "level": "开发", "prefix_gate": dev["gate0"], "development_gate": dev["gate1"],
            "finding": "开发复用 v3a 旧板。S 用首次公开提案时可见的设施类型、信号域和类别选整向量。"
                       "每个方向用一半条件训练，另一半评价。S 的平均剩余缺额低于同方向的整板赢家，"
                       "单侧上界低于零，开发门槛通过。两个方向的对照分别为 MAIN-R-1 和 Q26。",
            "sources": [book.ref(*DEV, "/gate0"), book.ref(*DEV, "/gate1"), book.ref(*DEV, "/overlap/v3a_reused"),
                        book.ref(*DEV, "/directions/A→B/whole"), book.ref(*DEV, "/directions/B→A/whole"),
                        book.ref("ab6a8ad5", D3C + "protocol.md", "L23-L27")],
        },
        "v3c_new": {
            "level": "确认", "verdict": new["primary_verdict"], "winner": book.get(*LOCK)["fit"]["winner"],
            "finding": "在整块旧板重新拟合并冻结 S 与整板赢家 W（MAIN-R-3），再评价同一合成发生器的新条件。"
                       "S 的平均整窗服务缺额高于 W，双侧区间完全在零以上。W 在全板逐条达到认证下界。"
                       "新板未通过预注册主门槛，旧板的开发收益没有迁移。",
            "sources": [book.ref(*LOCK, "/fit/winner"), book.ref(*NEW, "/primary_verdict"),
                        book.ref(*NEW, "/overlap/v3a"), book.ref("f3027bd7", D3C + "confirmation-protocol.md", "L3-L7")],
        },
    }
    for stage, evidence in stages.items():
        evidence["number_ids"] = [n["id"] for n in numbers if n["stage"] == stage]

    return {
        "id": "C3",
        "statement": "固定普通改进的开发收益能迁移到同一合成发生器的新条件，使公开选择器 S 的平均整窗服务缺额 L 低于预注册的冻结整板赢家 W。",
        "level": ["开发", "确认"],
        "comparator": {
            "v1": "主轨锁定人工候选相对 V**、B_cost。",
            "v2": "主轨 U 相对等预算随机搜索 R，以及 B_cost。",
            "v3a": "跨半选优回收的服务缺额占 B_cost 至认证全知下界距离的比例。",
            "v3b": "固定分块重组相对整板最低 L 的完整向量。",
            "v3c_dev": "S 相对各选择半训练出的整板赢家。",
            "v3c_new": "S 相对整块旧板冻结的 W（MAIN-R-3）。",
        },
        "denominator": {
            "v1": ["C3.v1.n"], "v2": ["C3.v2.n", "C3.v2.U.seeds", "C3.v2.R.seeds"],
            "v3a": ["C3.v3a.n", "C3.v3a.n.A", "C3.v3a.n.B", "C3.v3a.pool", "C3.v3a.k6", "C3.v3a.k24",
                    "C3.v3a.gap.A_to_B", "C3.v3a.gap.B_to_A"],
            "v3b": ["C3.v3b.n"], "v3c_dev": ["C3.v3c_dev.n", "C3.v3c_dev.pool"],
            "v3c_new": ["C3.v3c_new.n", "C3.v3c_new.reserve.n"],
        },
        "numbers": numbers, "evidence_by_stage": stages,
        "failure_conditions": [
            "v1 的锁定策略可追溯至手写候选，开发成绩不能识别反馈产生策略的增量。",
            "v2 的严格优势要求 U 相对 R 与 B_cost 的双侧区间上界都低于零。",
            "v3a 的结论取决于预注册回收率条件。v3b 的两个点估计和单侧上界均须严格为负才允许启动后续阶段。",
            "v3c 的确认要求新板 S−W 双侧区间上界严格为负。新板 W 已逐行达界，选择器没有可进一步降低的服务缺额。",
            "结论仅覆盖已评分的固定规则、比较对象与有限合成面板。其他候选集、设施和现场总体的收益仍待建立。",
        ],
        "counterexamples": counterexamples, "status": "不成立",
    }
