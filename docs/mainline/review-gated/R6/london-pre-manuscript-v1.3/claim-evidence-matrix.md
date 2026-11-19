# 附录 B　主张与证据矩阵

**R6 阶段研究工作稿 v1.3**

编号沿用 v1.2.2 配套矩阵。源表示发布方记载，实表示原运行结果或明确注明的存档核对，推表示有前提的书面推导，假表示尚未识别的命题。数字与否决均保留原面板归属。新增的作业计划证据标为源3、实20、推8和假3，后继目录的有限否决与范围反例标为推7。

## B.1　来源事实

| 编号／正文 | 来源支持的陈述与范围 | 直接证据 |
|---|---|---|
| 源1　§1、3.1 | 伦敦公开复盘记载维护隔离、共享电压信息与未发启动信号。现场核查者当时可见哪些资料未知。 | [官方报告的版本与定位](../../R1/sources.md) |
| 源2　§3.1 | 事件表的 23:00 与部分产品段的 22:53 尚未消歧，约五分钟的 UPS 描述不能换算为核查者的实际窗口。 | [同一报告的两处时间口径](../../R1/sources.md) |
| 源3　§8.4 | 同类控制改造有预计停用影响的送审计划和建筑持续运营的实例。六项公开来源没有同时给出伦敦本次动作、适用版本、申请前合法接收和查阅代价。 | [六项来源与逐项缺口](../work-impact-source-decision.md) |

## B.2　执行观察与存档核对

本节的原行缺额、人员与工具实耗、关闭、违规及各实购候选，以同一版本的[开发逐臂原件](../../R5/ordinary-v2-development/records/dev19-rows.json)和[扩展逐臂原件](../../R5/ordinary-v2-development/records/ext35-rows.json)为共同数值依据。下表另列时间、阶段、票据或输入的针对性记录。

| 编号／正文 | 已记录的观察与限定 | 直接证据 |
|---|---|---|
| 实1　图 1 | dev19 为 19 行、18 行合规。I 对 D 缺额较低／相同／较高为 0／10／8，对 P 为 0／17／1。各合规行 I 的人员与工具实耗均高于 P。 | [开发配对记录](../../R4/public-development-v1/paired-results.md) |
| 实2　图 1 | ext35 为 35 行、34 行合规。I 对 D 为 1／28／5，唯一较低行 B01。I 对 P 为 1／32／1，较低行 G06、较高行 B02。35 项指定阶段到达包括失败阶段。 | [扩展比较](../../R4/finite-extension-study-v1/paired-results.md) |
| 实3　§4.2 | A01、A02 的合法否定分别在 4、8 秒到达，I 对 D 每种资源分别节省 5、3 秒。dev19.C02、C03 各有相同的工时差。 | [到时记录](../../R4/finite-extension-study-v1/actual-stage-coverage.md) · [开发成本](../../R4/public-development-v1/paired-results.md) · [扩展成本](../../R4/finite-extension-study-v1/paired-results.md) |
| 实4　图 2 | B01 的 I 在 4 秒看到否定后停止。D 的隔离与重启使服务在 [2,9) 缺失，L(I,D,P)＝0／7／0。早期工程 X02 与 B01 的完整输入只差外部预约。 | [扩展原臂](../../R4/finite-extension-study-v1/paired-results.json) · [X02](../../R4/confirmation-entry-v1/README.md) |
| 实5　图 3 | G05 中 I 的名义提交被 12 秒截止阻止，L＝5／0／5。G06 中 I 于 12 秒实际提交、未复核，L＝0／0／4。两行的读取链和申请时刻相同。 | [阶段与分段](../../R4/finite-extension-study-v1/actual-stage-coverage.md) |
| 实6　表 3 | H03／H04 的预算门与 J03／J04 的窗口门改变动作能否完成。K02 中 I 排队后仍被截止。在 C07b，I 对 D 少用两种工时各 3 秒，却多 5 秒缺额。 | [扩展输入](../../R4/finite-extension-v1/conditions.json) · [实际阶段](../../R4/finite-extension-study-v1/actual-stage-coverage.md) · [开发原表](../../R4/public-development-v1/paired-results.md) |
| 实7　§5.1 | D01 的 I 在 16 秒收到绑定复核通过，D 因许可不足未发请求。E01–E05 分别保留审批拒绝、提交失败、联锁阻断、复核失败与无结论。 | [实际阶段](../../R4/finite-extension-study-v1/actual-stage-coverage.md) |
| 实8　§5.1 | 原扩展的 33 次复核请求与 33 条发布可绑定本组执行。在 22 个适用行，I／P 的服务机制分段相同。754 个策略包及 450 次重复同包属于技术核对。 | [冻结命题及核对](../../R4/finite-extension-study-v1/propositions.json) |
| 实9　§4.2 | C09b 与 B03 均退出超出预留。I／D／P 的原缺额分别为 13／19／0 和 11／18／0，保留在全分母，不能登记正向数值收益。 | [完整结果附录](appendix.md) |
| 实10　图 4 | F01、F02 中 I／D 后备接管失败。三臂依靠 A 与 UPS 维持至窗口末，H＝20 时转为 OFF。窗内 L／U 为零，恢复右删失的下界为零。 | [恢复记录](../../R4/finite-extension-study-v1/costs-and-recovery.md) · [供给与端点](../../R4/finite-extension-study-v1/paired-results.json) |
| 实11　§5.2 | L01 的外生故障区间为空，PRE 仍截止。L02 窗内未恢复 A，I／P 各有 5 秒缺额，D 为零。 | [实际阶段](../../R4/finite-extension-study-v1/actual-stage-coverage.md) |
| 实12　表 5 | U0 依次购 C全续、C早续、C早止。强搜索依预定次序购 C全续、C早止、V早续。六张票在全列齐备后释放。 | [逐票回执](../../R5/ordinary-v2-development/records/tickets.json) |
| 实13　§7.1 | 两组的唯一终局均为 C早止，强搜索第二票取得，U0 第三票取得。四个实购候选各以自己的完整列晋级，另外三项未购。 | [前沿与锁定](../../R5/ordinary-v2-development/decisions.md) |
| 实14　表 6 | C早止 对 I，dev19 为 0／18／0，ext35 为 1／33／0。只在 K02 将 L 从 4 降至 0、每种实耗从 8 降至 7。该行没有申请 VERIFY，仍未合法关闭。 | [扩展逐行归档](../../R5/ordinary-v2-development/records/ext35-rows.json) |
| 实15　§7.2 | D01 的 I 与 C早止 均以 EVIDENCE 申请、绑定复核关闭，每种实耗 9 秒。D 直接许可不足，缺额为零且未关闭。 | [D01 原记录](../../R5/ordinary-v2-development/records/ext35-rows.json) |
| 实16　表 7 | 相对 I，C早止 在 dev19 两行、ext35 六行省工。配置否定各省 1 秒，未知停止各省 2 秒，四个两读后修订行各省 1 秒。 | [开发原行](../../R5/ordinary-v2-development/dev19.md) · [扩展原行](../../R5/ordinary-v2-development/ext35.md) |
| 实17　表 6 | C早止 对 D 的合规缺额方向为 0／10／8、1／29／4，对 P 为 0／17／1、2／31／1，对人工 C全续 为 0／18／0、1／33／0。两个锁定者逐行持平。 | [全部对照](../../R5/ordinary-v2-development/records/comparisons.json) |
| 实18　§7.3 | 四个实购新候选在 C09b 的 L／人员／工具为 13／16／16，在 B03 为 11／14／14。两行同 I，原非合规状态保留。 | [完整终态](../../R5/ordinary-v2-development/records/terminal.json) |
| 实19　§7.3 | 存档对账：27 项事前预测与实际记录吻合，涵盖票序、时序和工时。预测来自已见材料，匹配数量不增加样本。 | [预测对照](../../R5/ordinary-v2-development/records/prediction-check.json) |
| 实20　§8.4 | 存档对账：同一面板内仅改变作业方式的完整输入，dev19 没有，ext35 有 A01／B01 和 A03／B02 两对。前一对的两行 I 均省工，后一对 D 均省工。没有查阅说明的已执行处理。 | [配对核查与来源](../work-impact-source-decision.md) |

## B.3　条件式静态推导

| 编号／正文 | 在何种前提下可以推出什么 | 直接证据 |
|---|---|---|
| 推1　§3.1 | 历史信息、权限与耗时未取得，合成条件无法识别真实事故可避免性。 | [R1 可识别性边界](../../R1/README.md) |
| 推2　§3.2、8.1 | 决策只能使用当前合法公开帧。作业方式及未来故障可以在决策时不可区分，不能按评价端真值选组。 | [运行器接口](../../R3/runner-v1/README.md) |
| 推3　§6.2 | 在原 v1 目录中，D 和四种 H 均无法在 D01 保留 I 已有的合法关闭。H 在这行的行为来自规则。 | [v1 目录判定](../../R5/v1-static-disposition.md) |
| 推4　§6.3 | 在 A02 正常配方下，I／D 各资源为 3／6 秒（实测），H1／H2 为 7／8 秒（推导）。工时约束独立否决五项。 | [原配方与推导](../../R5/v1-static-disposition.md) |
| 推5　§6.4 | 在原 v1 目录、原偏好和正常完整选择下，空前沿只能回退 I，U1 的采纳条件无法满足。没有 U1 执行事件。 | [晋级及空前沿规则](../../R5/bounded-improvement-v1/improvement.md) |
| 推6　§8.3 | 原普通 v2 目录与已见 54 行限定了终局归因上限。强搜索的预定查询包含 C早止，U0 同时严格超过人工候选和强搜索的额外服务收益已被结构排除。 | [执行前的规则论证](../../R5/ordinary-improvement-v2/README.md) |
| 推7　§8.5 | 后继目录在六块可构造、完整且关键行合规时，两次验证按拟议偏好同选固定子，两个策略选择块均回退 I。初态直申／回退 I 的形态不在该目录，只有必要条件和反例分析。 | [限定否决](../../R5/service-priority-bounded-candidate/reviewed-scope.md) · [遗漏形态](../london-pre-closure-decision/README.md) |
| 推8　§8.4 | 在原逐行偏好下，若查阅方与基线的其他实际占用相同，多出的净查阅实耗即可否决本行。实际配对没有给出付费信息净收益见证，暂停限于所核来源和选择。 | [来源与决策判断](../work-impact-source-decision.md) |

## B.4　尚未识别的主张

| 编号／正文 | 开放问题 | 缺少的证据 |
|---|---|---|
| 假1　§8.3 | 未见任务是否也有可迁移的策略改善，有限实例能否代表真实现场。 | 其他有依据的任务、决策时材料及相应评价。现有同账号结果只覆盖已见条件。[原适用域](../../R5/ordinary-v2-development/acceptance-20261119.json) |
| 假2　§8.3、8.5 | 改变后续产生或筛选改进的程序，能否在强透明规则、固定改进器与同预算强搜索之外带来额外后果改善。 | 可区分的真实程序变化、同预算对照和独立评价。本阶段未测量 RSI。[主线主张](../../plan.md) |
| 假3　§8.4 | 同次拟议修订的费用、版本、到达及对决策的影响能否支撑付费净信息价值。 | 对应设备的有效作业计划，以及首次决定前合法取得且足以改变行动的有成本证据；当前支线结束。[有限来源判定](../work-impact-source-decision.md) |
