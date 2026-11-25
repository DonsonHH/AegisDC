"""C2 evidence from the incident families, the London PRE study and the V6 panels."""


def archive(revision, directory, name):
    return revision, f"docs/mainline/{directory}/{name}"


T3 = "t3-prior-information-v2"
T3_DEV = archive("85af7e48", T3, "development-result.json.gz")
T3_ENG = archive("85af7e48", T3, "engineering-results.json.gz")
T3_REPORT = archive("85af7e48", T3, "README.md")
INCIDENT_SOURCES = archive("85af7e48", "review-gated/R1", "sources.md")
T4B = archive("3487276a", "t4b-holdout-confirmation-v2", "results.json.gz")
R6_RECORDS = "review-gated/R5/ordinary-v2-development/records"
R6_DEV = archive("84eaa73d", R6_RECORDS, "dev19-rows.json")
R6_EXT = archive("84eaa73d", R6_RECORDS, "ext35-rows.json")
R6_COMPARISONS = archive("84eaa73d", R6_RECORDS, "comparisons.json")
R6_MATRIX = archive("84eaa73d", "review-gated/R6/london-pre-manuscript-v1.3", "claim-evidence-matrix.md")
FIRST = archive("ec1e3747", "v6-native-method-study-v1", "result.json")
COLD = archive("b867628f", "v6-stage-three-cold-study-v2", "result.json")
COLD_MECHANISMS = archive("b867628f", "v6-stage-three-cold-study-v2", "mechanisms.json")


def index_of(rows, name, key="key"):
    matches = [i for i, row in enumerate(rows) if row[key] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {key}={name}, found {len(matches)}")
    return matches[0]


class Case:
    def __init__(self, book, key, title, level, source, finding):
        self.book = book
        self.source = source
        self.id = "C2." + key
        self.title = title
        self.level = level
        self.finding = finding
        self.numbers = []
        self.denominators = {}
        self.sources = []
        self.counterexamples = []
        self.observations = []

    def ref(self, field, source=None):
        return self.book.ref(*(source or self.source), field)

    def num(self, name, label, unit, *fields, op="value", rows=None, source=None):
        metric_id = f"{self.id}.{name}"
        self.numbers.append(self.book.num(metric_id, label, unit, *(source or self.source),
                                          list(fields), op=op, rows=rows))
        return metric_id

    def example(self, condition, observation, metrics, refs=(), *, counterexample=True):
        group = self.counterexamples if counterexample else self.observations
        group.append(dict(case=self.id, level=self.level, condition=condition,
                          statement=observation, metric_ids=metrics, sources=list(refs)))

    def record(self):
        return dict(id=self.id, panel=self.title, level=self.level, finding=self.finding,
                    denominator=self.denominators, metric_ids=[n["id"] for n in self.numbers],
                    sources=self.sources, observations=self.observations)


def t3_engineering(book, family, name, specifications):
    case = Case(book, f"T3.{family}.qualification", f"T3 {name}式原生工程见证", "开发", T3_ENG,
                "各见证单独检验指定动作、物理条件与服务积分，只作接口资格。")
    rows = book.get(*T3_ENG)["C"]["rows"]
    indices = [index_of(rows, key) for key, _ in specifications]
    case.denominators["工程见证"] = case.num("n", f"{name}式接口工程见证", "见证", "/C/rows/{i}/key",
                                         op="count", rows=indices)
    losses = {}
    for i, (key, label) in zip(indices, specifications, strict=True):
        losses[key] = case.num(key, label + "的实际 L", "秒", f"/C/rows/{i}/L")
    case.sources.append(case.ref("L39-L52", T3_REPORT))
    if family == "LONDON":
        failed = ["C-L-refused", "C-L-connection", "C-L-hardware"]
        case.example("、".join(failed), "路径恢复未生效、连接位置受限、发电机硬件受限时，"
                     "共享控制修正已执行，终端仍失电。", [losses[key] for key in failed],
                     [case.ref(f"/C/rows/{index_of(rows, key)}/writes") for key in failed])
    else:
        failed = ["C-N-late", "C-N-insufficient"]
        case.example("、".join(failed), "重启泵晚于库存耗尽，或重分组后另路容量不足，均留下缺额。",
                     [losses[key] for key in failed],
                     [case.ref(f"/C/rows/{index_of(rows, key)}/attachment") for key in failed])
    return case


def t3_family(book, family, name, partial, locked, twins):
    case = Case(book, f"T3.{family}", f"T3 {name}式公开开发条件", "开发", T3_DEV,
                "比较仅既有保护 P、周期巡检、报警响应与评价端合法全知排程。"
                "报警、事前记录与可购买检查能否赶上截止按各行实际条件核对。")
    data = book.get(*T3_DEV)
    rows = data["rows"]
    indices = [i for i, row in enumerate(rows) if row["family"] == family]
    case.denominators["公开条件"] = case.num("n", f"{name}式开发条件", "条件",
                                      "/rows/{i}/family", op="count", rows=indices)
    for key, label in (("a", "P 有缺额"), ("b", "P 高于合法最小 L"),
                       ("c1", "正式报警可在截止前使用"), ("c2", "事前记录或合法付费结果可在截止前使用")):
        case.num(key, label, "条件", "/rows/{i}/" + key, op="count_true", rows=indices)
    for role, label in (("P", "仅既有保护"), ("PERIODIC", "周期巡检"),
                        ("ALARM", "报警响应"), ("ORACLE", "评价端合法全知排程")):
        case.num("mean_" + role, f"{label}的条件等权平均 L", "秒", "/rows/{i}/arms/" + role + "/L",
                 op="mean", rows=indices)
    timely = "5-01" if family == "LONDON" else "6-02"
    row = f"/rows/{index_of(rows, timely)}"
    metrics = [case.num(timely + "_" + key, f"{timely} {label}", "秒", row + field)
               for key, label, field in (("prior", "事前记录到达", "/info/prior/0"),
                                         ("paid", "付费读数可到达", "/info/paid/0"),
                                         ("alarm", "正式报警到达", "/info/alarm/0"),
                                         ("latest", "挽回全部可避免缺额的最晚必要启动", "/latest"),
                                         ("P_L", "P 的实际 L", "/arms/P/L"),
                                         ("periodic_L", "周期巡检的实际 L", "/arms/PERIODIC/L"),
                                         ("oracle_L", "合法全知排程的实际 L", "/arms/ORACLE/L"))]
    action = "恢复获准路径" if family == "LONDON" else "预防性重分组"
    case.example(timely, f"事前记录和可购买的现场读数均能早于最晚启动，正式报警迟到。实际达界计划为{action}。"
                 "可购买读数属于评价端核实的机会，未付费的策略当时看不到它。", metrics,
                 [case.ref(row + "/certified_plan"), case.ref(row + "/info/paid_is_counterfactual_opportunity")],
                 counterexample=False)
    partial_row = f"/rows/{index_of(rows, partial)}"
    locked_row = f"/rows/{index_of(rows, locked)}"
    losses = [case.num(partial + "_" + arm, f"{partial} {arm} 的 L", "秒", f"{partial_row}/arms/{arm}/L")
              for arm in ("P", "PERIODIC", "ALARM", "ORACLE")]
    case.example(partial, "周期巡检已达合法最小缺额。" if family == "LONDON" else
                 "重启泵能减少冷却损失，合法最优仍留有转供期间的服务缺额。",
                 losses, [case.ref(partial_row + "/certified_plan"), case.ref(partial_row + "/partial")])
    losses = [case.num(locked + "_" + arm, f"{locked} {arm} 的 L", "秒", f"{locked_row}/arms/{arm}/L")
              for arm in ("P", "ORACLE")]
    case.example(locked, "虽有事前材料，现有许可和物理条件下的最小 L 已等于 P。",
                 losses, [case.ref(locked_row + "/cell"), case.ref(locked_row + "/incident_single_action_bounds")])
    i = index_of(data["paired_worlds"], family, "family")
    twin = f"/paired_worlds/{i}"
    if data["paired_worlds"][i]["keys"] != twins:
        raise ValueError("unexpected T3 paired-world identities")
    refs = [case.ref(twin + "/" + key) for key in ("keys", "whole_P_public_history_identical", "legal_schedules")]
    if family == "LONDON":
        metrics = [case.num("twin_L_" + key, f"{key} 的 P 缺额", "秒", f"{twin}/P_losses/{j}")
                   for j, key in enumerate(twins)]
        note = "全窗 P 公开记录相同。合法全知解分别恢复隔离路径、修正共享判断，付费路径核查可区分。"
    else:
        metrics = [case.num("twin_first_difference", "成对 P 公开记录首次分歧时刻", "秒",
                            twin + "/first_different_public_tick")]
        note = "两行早期 P 公开历史相同，随后才分歧。合法全知排程分别重启泵和预防性重分组。"
    case.example("／".join(twins), note, metrics, refs + [case.ref("L75-L85", T3_REPORT)])
    case.sources.extend([case.ref("L75-L85", T3_REPORT), case.ref("L87-L122", T3_REPORT)])
    return case


def t4_family(book, family, name):
    case = Case(book, f"T4b.{family}", f"T4b {name}式留出条件", "确认", T4B,
                "V** 与透明直接规则 B 逐行配对。区间为原封存的分族区间，正式主检验使用全板。")
    base = f"/scopes/family~1{family}/test_effects/H1"
    case.denominators["可用配对"] = case.num("n", f"{name}式 V** 与 B 的可用配对", "条件", base + "/available")
    for key, label in (("mean", "平均差"), ("lo", "封存区间下端"), ("hi", "封存区间上端")):
        case.num(key, f"{name}式 V**−B 的 L {label}", "秒", f"{base}/metrics/L/{key}")
    for j, key in enumerate(("better", "equal", "worse")):
        case.num(key, f"V** 相对 B 的 L {('较少', '相同', '较多')[j]}", "条件", f"{base}/directions/{j}")
    rows = book.get(*T4B)["rows"]
    if family == "LONDON":
        i = index_of(rows, "5-08")
        m = case.num("5-08_delta", "留出 5-08 的 V**−B 缺额", "秒",
                     f"/rows/{i}/arms/V_COST/L", f"/rows/{i}/arms/B/L", op="subtract")
        case.example("5-08", "留出条件中 V** 的缺额超过 B，分族平均差的封存区间跨零。",
                     [m, case.id + ".lo", case.id + ".hi"], [case.ref(f"/rows/{i}/key")])
    else:
        failure = "/failure_counts/missed_preventive_window"
        keys = book.get(*T4B)["failure_counts"]["missed_preventive_window"]["keys"]
        worse = [r["key"] for r in rows if r["family"] == family and r["arms"]["V_COST"]["L"] > r["arms"]["B"]["L"]]
        if keys != worse:
            raise ValueError("Dutch preventive-window cases differ from V** losses against B")
        assessed = case.num("window_assessed", "预防性重分组失窗可判定的荷兰式条件", "条件", failure + "/assessed")
        count = case.num("window_missed", "未在合法窗口完成预防性重分组", "条件", failure + "/count")
        metrics = [count, assessed]
        refs = [case.ref(failure + "/keys")]
        for key in keys:
            prefix = f"/rows/{index_of(rows, key)}"
            metrics.append(case.num(key + "_delta", f"留出 {key} 的 V**−B 缺额", "秒",
                                    prefix + "/arms/V_COST/L", prefix + "/arms/B/L", op="subtract"))
            refs.append(case.ref(prefix + "/failures/missed_preventive_evidence"))
        case.example("、".join(keys), "B 在转供前完成预防性重分组。V** 失窗后的泵操作无法补回此前的电力损失。",
                     metrics, refs)
    return case


def london_pre(book, panel, source, noncompliant):
    case = Case(book, f"R6.{panel}", f"R6 v1.3 伦敦 PRE {panel}", "开发", source,
                "固定先核查 I 与合法直接修订 D、仅保护 P 的合规行分别计分。"
                "两块面板均为已见合成条件，扩展由同一账户执行。")
    rows = book.get(*source)["rows"]
    eligible = [i for i, row in enumerate(rows) if row["in_mask"]]
    case.denominators["全体条件"] = case.num("all", f"{panel} 原始条件", "条件", "/rows", op="length")
    case.denominators["合规配对"] = case.num("valid", f"{panel} 合规配对", "条件",
                                       "/rows/{i}/in_mask", op="count_true", rows=range(len(rows)))
    for role in ("D", "P"):
        for op, label in (("better", "较少"), ("equal", "相同"), ("worse", "较多")):
            case.num(role + "_" + op, f"合规行 I 的 L 相对 {role} {label}", "条件",
                     "/rows/{i}/baseline/I/z/0", "/rows/{i}/baseline/" + role + "/z/0", op=op, rows=eligible)

    def row(key):
        return f"/rows/{index_of(rows, panel + '.' + key)}"

    def loss(key, role):
        return case.num(f"{key}_{role}_L", f"{panel}.{key} 的 {role} 实际 L", "秒", f"{row(key)}/baseline/{role}/z/0")

    case.example(noncompliant, "I 与 D 退出时超过预留。这条记录留在全分母，原缺额只作非合规观测。",
                 [loss(noncompliant, role) for role in ("I", "D", "P")],
                 [case.ref(row(noncompliant) + tail) for tail in ("/in_mask", "/baseline/I/violations", "/baseline/D/violations")])
    case.sources.extend([case.ref("L17-L30", R6_MATRIX), case.ref("L46-L47", R6_MATRIX)])
    if panel == "dev19":
        return case
    case.sources.extend([case.ref("L32-L35", R6_MATRIX), case.ref("L51-L61", R6_MATRIX)])
    for key, readout in (("B01", "及时的否定读数使 I 停止，避开 D 修改带来的隔离与重启。"),
                         ("B02", "I 与 D 都完成修订和复核，缺额相同，均高于本行仅既有保护 P。"),
                         ("G05", "I 完成读取后，其名义提交被截止阻断。"),
                         ("G06", "相同读取和申请时刻下，I 实际完成提交，尚未复核。")):
        metrics = [loss(key, role) for role in ("I", "D", "P")]
        case.example(key, readout, metrics, [case.ref(row(key) + "/baseline/I/stage")],
                     counterexample=key in ("B02", "G05"))
    d01 = row("D01") + "/baseline"
    verified = case.num("D01_verified", "D01 的 I 收到绑定复核通过时刻", "秒", d01 + "/I/closure_evidence/at")
    case.example("D01", "直接修订缺少许可，D 未发行。I 以取得的证据申请并在本人复核后合法关闭。",
                 [verified], [case.ref(d01 + "/I/closure_evidence/kind"), case.ref(d01 + "/D/stop"),
                              case.ref("L35", R6_MATRIX)], counterexample=False)
    failed = {"E01": ("审批拒绝", "APPROVAL_DENIED"), "E02": ("提交失败", "COMMIT_FAILED"),
              "E03": ("联锁阻断", "NOT_IMPLEMENTED"), "E04": ("复核失败", "VERIFICATION_FAILED"),
              "E05": ("复核无结论", "VERIFY_INCONCLUSIVE")}
    for key, (_, expected) in failed.items():
        if rows[index_of(rows, panel + "." + key)]["baseline"]["I"]["stage"] != expected:
            raise ValueError("unexpected London PRE stage: " + key)
    metrics = [case.num("failed_stages", "有指定审批、执行或复核失败／无结论的见证", "条件",
                        *(row(key) + "/baseline/I/stage" for key in failed), op="count")]
    case.example("、".join(failed), "，".join(f"{key} {label}" for key, (label, _) in failed.items()),
                 metrics, [case.ref(row(key) + "/baseline/I/stage") for key in failed] + [case.ref("L27", R6_MATRIX)])
    case.example("F01／F02", "I 与 D 后备接管失败。窗口末设备关停，窗内零缺额与右删失恢复同时保留。",
                 [loss(key, role) for key in ("F01", "F02") for role in ("I", "D", "P")],
                 [case.ref(row(key) + f"/baseline/{role}/{field}") for key in ("F01", "F02")
                  for role in ("I", "D") for field in ("final_backup", "recoveries")])
    k02 = row("K02")
    i_arm, locked = k02 + "/baseline/I", k02 + "/paid_candidates/C早止"
    k_metrics = []
    for label, prefix in (("I", i_arm), ("C早止", locked)):
        for j, key, unit in ((0, "L", "秒"), (2, "人员", "人秒"), (3, "工具", "工具秒")):
            k_metrics.append(case.num(f"K02_{label}_{key}", f"K02 {label} 的{key}", unit, f"{prefix}/z/{j}"))
    k_metrics += [case.num("K02_commit", "K02 C早止 实际提交时刻", "秒", locked + "/execution_receipts/0/committed_at"),
                  case.num("K02_cutoff", "K02 I 名义提交被截止阻断的时刻", "秒", i_arm + "/stop/time"),
                  case.num("locked_improved", "扩展板锁定策略相对 I 缺额较低的合规条件", "条件",
                           "/U0/I/panels/ext35/on_original_mask_lower_same_higher/L/0", source=R6_COMPARISONS)]
    case.example("K02", "锁定的 C早止 提前提交，I 的名义提交遭截止，两者均未获复核关闭。"
                 "固定改进器与同预算强搜索都选中 C早止，这项局部服务改善不能归为改进器独有。",
                 k_metrics, [case.ref(i_arm + "/execution_receipts/0"), case.ref(locked + "/closed"),
                             case.ref(i_arm + "/closed"), case.ref("L32-L34", R6_MATRIX)], counterexample=False)
    return case


def first_slice(book):
    case = Case(book, "V6.first", "V6 取水流量／清滤首片", "开发", FIRST,
                "披露的单模板正式有限面板。价值策略 V 与强透明直接规则 D 的主比较全窗同服务。")
    case.denominators["合规 V−D 配对"] = case.num("pairs", "合规 V−D 主配对", "条件",
                                             "/official_panel/claims/D/compliant_pairs")
    case.num("equal", "V 与 D 实际服务相同", "条件", "/comparisons/D/same_service", op="length")
    for key, label in (("BETTER", "较少"), ("EQUAL", "相同"), ("WORSE", "较多")):
        case.num("resource_" + key, f"V 相对 D 的人员、工具及发行费{label}", "条件",
                 "/comparisons/D/resources/" + key, op="length")
    saved = case.num("saved_with_closure", "同服务、省资源且保有 D 关闭", "条件",
                     "/comparisons/D/saved_resources_with_closure", op="length")
    case.example("C02、C06、C07", "V 少用人员、工具和发行费，均失去 D 已取得的合法关闭。",
                 [case.id + ".resource_BETTER", saved], [case.ref("/comparisons/D/lost_closure")])
    case.sources.append(case.ref("/official_panel/claims/D"))
    return case


def cold_panel(book):
    case = Case(book, "V6.cold", "V6 第三阶段冷态的冷却与网络联合工单", "开发", COLD,
                "同账户执行的有限正式面板，比较 J 与强透明 B。J−B 的 L 为负表示 J 少损失服务。"
                "主配对和机制配对共用部分原臂，各自保留分母。")
    counts = "/official_panel/counts/J~1B"
    case.denominators["J−B 主配对"] = case.num("pairs", "冷态 J 与 B 的主配对", "条件",
                                         "/official_panel/denominators/J~1B")
    case.num("all_pairs", "包括机制对照在内的全部预定配对", "配对", "/comparisons", op="length")
    for key, label in (("BETTER", "较少"), ("SAME", "相同"), ("WORSE", "较多")):
        case.num(key, f"主配对中 J 相对 B 的服务缺额{label}", "条件", counts + "/" + key)
    data = book.get(*COLD)
    for key, note in (
        ("A04", "冷却正常，网络配置限制服务。J 付费核查网络、修订并复核。B 清滤产生等值写入。"
                "J 降低缺额，少用人员和工具，但多付发行费。"),
        ("B08", "冷却正常，网络初容量为零。B 有权先发冷却与网络处置，较早恢复网络。J 先核查再修订，"
                "少用人员、工具及费用，服务缺额增加，并失去 B 的冷却工单处置后复核关闭。")):
        index = index_of(data["rows"], key, "row")
        row = f"/rows/{index}"
        j, b = [row + f"/positions/{key}-{role}/actual" for role in ("J", "B")]
        metrics = [case.num(key + "_network", f"{key} 初始网络配置倍率", "倍率", row + "/specification/network")]
        for endpoint, col, unit, delta_id in (("L", 0, "秒", "delta"), ("U", 1, "服务单位·秒", "delta_U")):
            column = f"/service/rate/{col}"
            for role, prefix in (("J", j), ("B", b)):
                metrics.append(case.num(f"{key}_{role}_{endpoint}", f"{key} {role} 的实际 {endpoint}", unit,
                                        prefix + column, op="rational_value"))
            metrics.append(case.num(f"{key}_{delta_id}", f"{key} 的 J−B 实际 {endpoint} 差", unit,
                                    j + column, b + column, op="rational_subtract"))
        for k, label, unit in ((0, "person", "人秒"), (1, "tool", "工具秒"), (2, "fee", "发行费单位")):
            metrics.append(case.num(f"{key}_{label}", f"{key} 的 J−B 资源差", unit,
                                    f"{j}/resources/{k}", f"{b}/resources/{k}", op="subtract"))
        refs = [case.ref(base + "/" + field) for base in (j, b) for field in ("stages", "all_writes", "states")]
        if key == "B08":
            for role in ("J", "B"):
                metrics.append(case.num(f"{key}_{role}_restore", f"B08 {role} 网络恢复时刻", "秒",
                                        f"/B08/observed/{role}/network_restored_at", source=COLD_MECHANISMS))
        case.example(key, note, metrics, refs, counterexample=key == "B08")
    loss = case.num("closure_loss_n", "J 相对 B 有具名类型或时点关闭损失的行", "条件",
                    "/groups/J~1B/lost_closure_rows", op="length", source=COLD_MECHANISMS)
    case.example("A03、B07、B08", "J 未保有 B 的全部具名关闭。整板服务支配、服务支配且保有关闭、"
                 "等服务省资源且保有关闭均未成立。", [loss, case.id + ".WORSE"],
                 [case.ref("/groups/J~1B/lost_closure_rows", COLD_MECHANISMS)])
    case.sources.extend([case.ref("/official_panel/" + key)
                         for key in ("service_dominance", "service_with_closure", "equal_service_resource_with_closure")])
    return case


def build(book):
    london = (("C-L-base", "仅保护"), ("C-L-read-fix", "读取并修正共享判断"), ("C-L-prestart", "获准预启动"),
              ("C-L-path", "获准恢复路径"), ("C-L-refused", "路径操作未生效"), ("C-L-connection", "连接位置受限"),
              ("C-L-hardware", "备用硬件受限"))
    dutch = (("C-N-base", "仅保护"), ("C-N-group", "单独重分组"), ("C-N-restart", "单独重启泵"),
             ("C-N-both", "重分组并重启泵"), ("C-N-handover", "交接后备冷复役"),
             ("C-N-late", "迟重启泵"), ("C-N-insufficient", "分组后容量仍不足"))
    sections = [
        t3_engineering(book, "LONDON", "伦敦", london), t3_engineering(book, "NETHERLANDS", "荷兰", dutch),
        t3_family(book, "LONDON", "伦敦", "5-07", "5-03", ["5-04", "5-10"]),
        t3_family(book, "NETHERLANDS", "荷兰", "6-10", "6-05", ["6-04", "6-09"]),
        t4_family(book, "LONDON", "伦敦"), t4_family(book, "NETHERLANDS", "荷兰"),
        london_pre(book, "dev19", R6_DEV, "C09b"), london_pre(book, "ext35", R6_EXT, "B03"),
        first_slice(book), cold_panel(book),
    ]
    return {
        "id": "C2",
        "statement": "伦敦式和荷兰式有限合成条件中的核查与处置可以少损失服务。收益取决于证据能否及时区分原因、"
                     "权限和作业耗时能否容许相应处置。相同研究也观测到失窗、增加缺额和丢失合法关闭。",
        "level": ["开发", "确认"],
        "comparator": "T3 用 P、周期巡检、报警响应及评价端合法全知界。T4b 用 V** 对透明 B。"
                      "R6 的固定先核查 I 对直接修订 D 和仅保护 P，C早止 另对 I。V6 首片用 V 对 D，冷态用 J 对 B。"
                      "这些 V6 工单配对单独计数，两站的事故族统计取自 T3 和 T4b。",
        "denominator": {case.id: case.denominators for case in sections},
        "numbers": [n for case in sections for n in case.numbers],
        "case_sections": [case.record() for case in sections],
        "failure_conditions": [
            {"statement": "伦敦式合成条件中，单改共享控制判断无法打通未获移交的路径、错误连接或未就绪的备用硬件。",
             "sources": [book.ref(*T3_REPORT, "L39-L45")]},
            {"statement": "荷兰式中重分组须有供电余量且能赶上转供。来电后泵仍需合法重启，备冷复役需完成施工交接。",
             "sources": [book.ref(*T3_REPORT, "L89-L93"), book.ref(*T4B, "/failure_counts/missed_preventive_window/keys")]},
            {"statement": "等待证据可耗尽写入窗口，修订也会引入隔离和重启。审批、联锁、执行与本人复核都可能失败。",
             "sources": [book.ref(*R6_MATRIX, "L23-L30")]},
            {"statement": "公开同轨和付费结果不到时限制可辨识性。服务恢复、行动回执及工单合法关闭须分别判断。",
             "sources": [book.ref(*T3_REPORT, "L75-L85"), book.ref(*R6_MATRIX, "L25-L30")]},
            {"statement": "两起真实事故缺少足以重建当时可见材料、现场权限和作业时长的数据。"
             "事故可避免性、未见现场泛化及 RSI 增量均未建立。",
             "sources": [book.ref(*T3_REPORT, "L89-L93"), book.ref(*R6_MATRIX, "L46-L47"),
                         book.ref(*R6_MATRIX, "L57-L61")]},
        ],
        "counterexamples": [example for case in sections for example in case.counterexamples],
        "historical_evidence": [
            {"site": "伦敦", "record": "Google 事后记载维护隔离、控制器共用上游电压输入和未发启动信号。"
             "报告对不可用起点的叙述尚待消歧，当时核查人员可见的材料、申请权和剩余处置时间未识别。",
             "sources": [book.ref(*INCIDENT_SOURCES, lines) for lines in ("L18-L32", "L50-L51")]},
            {"site": "荷兰", "record": "Google 事后记载转供过载保护、控制器离线后泵未重启和施工期间备用冷却不可用。"
             "人工切泵发生在恢复期，临时 UPS 在事后部署。现场事前可实施的负荷重分组或泵操作窗口未识别。",
             "sources": [book.ref(*INCIDENT_SOURCES, "L34-L43"), book.ref(*T3_REPORT, "L89-L93")]},
        ],
        "text_sources": [book.ref(*INCIDENT_SOURCES, lines) for lines in ("L19-L32", "L34-L43", "L48-L54")]
                        + [book.ref(*R6_MATRIX, "L46-L47"), book.ref(*R6_MATRIX, "L59-L61")],
        "status": "部分成立",
    }
