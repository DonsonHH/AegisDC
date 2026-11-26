# 证据、实现版本与数据可用性

本表给出投稿稿中实际使用的数字与实现定位。原 T9 在 `28c59691` 验收。修订保留其[四条主张状态](../t9-paper-final/claims.md)、[完整数字台账](../t9-paper-final/numeric-sources.md)、[两站的证据、权限和时限](../t9-paper-final/manuscript.md#附录两起事故的证据权限与时限导师五问)。正文中的 H1、H2、H3 是同一六族面板上的三个假设编号。下列源表为已发布材料。

<a id="model"></a>
## 设施、信息和评价侧

八域及四类关系见[工程承接说明第 15–25 行](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/full-facility-method-handoff.md#L15-L25)、[八域覆盖表](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/full-facility-method-handoff.md#L51-L63)。外部工程参照、合成参数和现场未定量分开记录。Frontier 小样的 144 个十分钟时点只对照功率与冷却量级，现场派工和服务结果不在该数据集中。[公开物理数据读回](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/research/20261111-frontier-field-pilot/README.md#L3-L11)。图 1 表示信息和执行接口，不表示各个子域均已现场验证。

<a id="method"></a>
## 算法 1 的执行身份

V** 使用 T4c 冻结策略 `V_COST`。科学源码为 `c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5`，公开方法包 SHA-256 为 `28811a22be4e30a34526448c8379a004a96fd951363c9eeb2eceecad947074cd`。留出清单将注册、策略包与原生核心 `0e5afde1` 绑定。[T4c 冻结记录](https://github.com/DonsonHH/AegisDC/blob/cef45c0275ce330eaf2652362bfd5090dffd5aa6/docs/mainline/t4c-action-cost-v3/v-double-star-freeze.json#L82-L86) · [时钟、价格与原生身份](https://github.com/DonsonHH/AegisDC/blob/cef45c0275ce330eaf2652362bfd5090dffd5aa6/docs/mainline/t4c-action-cost-v3/v-double-star-freeze.json#L108-L114) · [T4b 清单](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/run-manifest.json#L5-L18)

| 算法步骤 | 真正消费的材料与动作 | 可审源码 |
|---|---|---|
| 1、2 | 到时视图、根来源、工单与本人回执，必须复检／续核优先。无支持或等待本人读数时保留原因。 | [公开视图验证](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/policy.py#L21-L43) · [来源与后验](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/belief.py#L21-L55) · [义务优先与等待](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/policy.py#L112-L133) |
| 3 | 暂缓或具名作业，按可行后继排列核查预算、工作窗、许可恢复、排队与本人复核。 | [可行日历](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/planning.py#L52-L117) · [候选首步](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/planning.py#L144-L170) |
| 4、5 | 每种到时报告共用一个续动作。UNKNOWN 单列。按预期评分、工时、费用、暂缓与稳定标识破平。 | [分组与选择](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/planning.py#L171-L209) · [预期费用](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/planning.py#L119-L141) |
| 6、禁购消融 | 只交付一个请求或暂缓，已发请求与实际回执分别记账。禁购版阻止 I，其余准入路径相同。 | [运行入口和真实禁购版](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/worker.py#L17-L36) · [决定的返回字段](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/policy.py#L126-L133) · [实际配对定义](https://github.com/DonsonHH/AegisDC/blob/cef45c0275ce330eaf2652362bfd5090dffd5aa6/docs/mainline/t4c-action-cost-v3/README.md#L33-L37) |

<a id="parameters"></a>
## 表 1 的参数与先验来源

| 标识 | 定义与单位 | 登记或执行出处 |
|---|---|---|
| <a id="p-prior"></a>先验 | 普通架构四族等权。事故架构的十二种组合按质量边际化，先验与本行真值分开。 | [有限目录](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/knowledge.py#L19-L51) · [事前知识与更新](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/t4a-public-risk-v1/protocol.md#L9-L17) |
| <a id="p-evidence"></a>证据 | 匹配参数 0.95，未知报告概率 0.03125。通道配置还含检测、缺报、到达及失效时刻。 | [公开设定](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/settings.json#L3-L22) · [后验筛选](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/belief.py#L64-L116) |
| <a id="p-clock"></a>时钟 | 3,600 秒评价窗、60 秒公开唤醒、0.25 秒物理步长。报告按实际采样、到达和有效期入账。 | [冻结时钟](https://github.com/DonsonHH/AegisDC/blob/cef45c0275ce330eaf2652362bfd5090dffd5aa6/docs/mainline/t4c-action-cost-v3/v-double-star-freeze.json#L108-L114) · [到时验证](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/policy.py#L21-L43) |
| <a id="p-price"></a>费用 | V3 的 λ=1。每发行费用单位折算 30 人秒。工具独立受限。预期评分与原生 L 计分分开。 | [价格与单位](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/t4a-public-risk-v1/protocol.md#L5-L8) · [冻结参数](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_risk_dispatch/settings.json#L3-L11) · [排序表达式](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/planning.py#L119-L141) |
| <a id="p-exposure"></a>维护 | 三档持续时间 0、600、1,200 秒。每十二行各四条。有限支撑上限 0.5，恢复间隔 180 秒。 | [v3 规则](https://github.com/DonsonHH/AegisDC/blob/c5ecb743d4ce0ee6ffaba1ad564bf05d82ff9fc5/src/aegis_action_cost/rules.json#L2-L19) · [实际写入触发](https://github.com/DonsonHH/AegisDC/blob/cef45c0275ce330eaf2652362bfd5090dffd5aa6/docs/mainline/t4c-action-cost-v3/README.md#L23-L29) |

<a id="confirmation"></a>
## 表 2　信息获取与整套策略

同一 144 条件面板、各族 24 条。登记顺序为 H1 对 B、H2 对 V**−probe、H3 对 B_cost。区间为族内配对重抽 10,000 次的双侧 95% 百分位区间，晋级要求上界严格小于零。本文按研究问题先解释 H2。两臂平均人秒 128.92 与 107.57 来自[同一留出报告的角色表](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md#L28-L31)。[冻结顺序、阈值、抽样单位](https://github.com/DonsonHH/AegisDC/blob/35b7bf4213c1cc8c1efb5dcf295f7821a1af15ff/docs/mainline/t4d-cost-baseline-v1/confirmation-protocol-v2.md#L5-L17) · [三个封存估计与区间](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md#L7-L16) · [B_cost 的规则及比较目的](https://github.com/DonsonHH/AegisDC/blob/036ccfdf2d6e5d4b39ba11da480fa2a3d69c1f9f/docs/mainline/t4d-cost-baseline-v1/README.md#L26-L30)

<a id="sensitivity"></a>
## 表 3　维护窗口及工程假设

v2 的 72/72 个 B 对照达界。v3 引入可产生下行代价的有限支撑和额外许可间隔。每档 48 条的 +0.62、−86.16、−81.97 秒取自**对禁购版**列，依次对应时长 0、600、1,200 秒。开发 S0 的 +1.25 [0.00, +3.75] 秒来自另一份 36 条件面板和组合设置。[v2 与 v3](https://github.com/DonsonHH/AegisDC/blob/cef45c0275ce330eaf2652362bfd5090dffd5aa6/docs/mainline/t4c-action-cost-v3/README.md#L23-L29) · [留出分层定义、数据与对照列](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md#L35-L47) · [开发敏感性操作与三种区间](https://github.com/DonsonHH/AegisDC/blob/036ccfdf2d6e5d4b39ba11da480fa2a3d69c1f9f/docs/mainline/t4d-cost-baseline-v1/README.md#L5-L14)

<a id="witness"></a>
## 与反例配对的开发见证

3-03 与 3-02 均比较 V** 与其禁购版，读数在 50 秒到达。前者的 L 为 0 对 600 秒，后者为 371.25 对 326.25 秒。另一个分母 54／76／14 来自留出 V** 对 B 的改善／持平／变差。[开发轨迹见证](https://github.com/DonsonHH/AegisDC/blob/cef45c0275ce330eaf2652362bfd5090dffd5aa6/docs/mainline/t4c-action-cost-v3/README.md#L39-L45) · [确认反例分母](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/t9-paper-final/manuscript.md#L47-L53)

<a id="incidents"></a>
## 表 4 与图 2　两个合成事故族

T7 的 120 行、五臂、每族五个十二行块、16 条旧运行输入重合，以及 HA、HB、HC 的统计口径均见公开收口表。图 2 左侧按缺额的配对方向计数，伦敦为 40／20／0，荷兰为 30／30／0。右侧仅以 P 已有缺额的 90 行为分母，伦敦归零 35、仍有缺额 10，荷兰归零 10、仍有缺额 35。另 30 行新增事件为 0。图中没有从汇总数倒推逐行差值分布。[设计、重合与事件定义](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/manuscript.md#L7-L11) · [HA/HB/HC、校正与事件计数](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/manuscript.md#L19-L31) · [分族作图数据](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/numeric-sources.md#L15-L16) · [块间退化](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/manuscript.md#L47-L51) · [两条原开发条件的实际读数](https://github.com/DonsonHH/AegisDC/blob/41709979b277812c1b7af8af5d7d3128293cb790/docs/mainline/t7-incident-counterfactual/stage1/witnesses.md#L5-L8)

<a id="improvement"></a>
## 早期普通改进与新条件迁移

v1 手写锚点，v2 从根向量变异，v3a 判读不确定，v3b 分块重组未过门槛。v3c 的旧板跨半结果与其新板 S−W 的 +80.49 秒及双侧区间分别定位。[五版普通改进及分母](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/t9-paper-final/manuscript.md#L117-L143) · [新板完整比较](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/t5-observable-selector-v3c/README.md#L3-L11)

<a id="fit"></a>
## 图 3　已付候选与可归因性

每臂四轮，每轮四槽，每槽 48 条。两臂各 768 个位置，加共享父 48 个，合计 1,584 个。图 3 只列 16 个不同编辑。T8 的离线规则按零硬违例、缺额总和、人员总和、描述符排序，并要求缺额严格下降才晋级。它与在线 V** 的 λ、κ 评分在不同时间和数据上运行。轮间改写新增付费项为 0，两臂选择相同的 `ORDER_FAR=3`。[登记的选择和改写规则](https://github.com/DonsonHH/AegisDC/blob/663cadee5c78e496a34d9efc277ec878718feef7/docs/mainline/t8-rsi-wait-repair/r1/fit_program.py#L81-L102) · [实际执行的选择与轮账](https://github.com/DonsonHH/AegisDC/blob/75203c1f59e29b4d6987cfbfdf16572c8da295e8/docs/mainline/t8-rsi-wait-repair/stage1b/scoring/study.py#L229-L256) · [完整候选得分](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/tables.md#L24-L41) · [锁定、未测编辑与逐行交集](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/HANDOFF.md#L7-L19)

<a id="staff"></a>
## 表 5　FIT 实测、效用容许量和情景预测

同一个锁定子策略对父的整板工时差为 +18.958333，人秒差伦敦 +1.458333、荷兰 +36.458333。登记量是**按族**的单侧上界 ≤ +5 人秒，且硬合规记录完整。两族各有两个 FIT 块。38 块情景固定这两个块的均差与样本方差，不重复制造独立块。相同最低服务缺额下事后逐行择优可省全板 5.833333 人秒，荷兰相对父仍多用 26.25 人秒。`ALARM_FAR=3` 的荷兰缺额差 −5 秒，两族工时均多 4.375 人秒。[Q3 原登记](https://github.com/DonsonHH/AegisDC/blob/6b63c4f4db6b8b19d01b2d00b99f740fba68525e/docs/mainline/t8-rsi-wait-repair/r0/registration.json#L89-L105) · [父子均值与替代编辑](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/tables.md#L39-L40) · [两个实际块及外推上界](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/tables.md#L86-L93) · [保持缺额时的工时下界](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/HANDOFF.md#L17-L19) · [已登记硬违规为零](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/HANDOFF.md#L27-L32)

<a id="limits"></a>
## 解释边界

块间结构、配额与现场分母、同账号程序性查重和个人代签授权争议、公开事故先于设计，均沿用经过审阅的表述。[T7 的块与频率端](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/numeric-sources.md#L22-L23) · [T8 查重和归属更正](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/HANDOFF.md#L34-L38) · [公开事故的先验知识](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-incident-counterfactual/contamination.md#L3-L13)

<a id="record"></a>
## 原四项主张与反例

C1、C2 部分成立，C3 登记的迁移优势不成立，C4 的递归独立服务增量未建立。既有 PRE 非合规行、完整设施早期同服务却丢失关闭的反例、T5 序列的负结果和导师五问继续保留在验收版本。[四项原主张](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/t9-paper-final/claims.md#L3-L8) · [PRE 与早期设施的反例](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/t9-paper-final/manuscript.md#L86-L107) · [两站证据与时限](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/t9-paper-final/manuscript.md#L199-L227)

<a id="availability"></a>
## 可复核范围与图件

从研究仓库的本版检出，在目录所在环境执行 `python -B verify.py` 可检查公开表值、执行源码绑定、引用及三个图件。`python -B render.py` 从同一份可编辑正文排印 HTML 和 PDF。无需登录私服，无需读取任何留出原件或运行评分器。算法框定位的公开模块按冻结 SHA-256 核对。公开对账不等于重演私服上的原始设施轨迹。

图 1 为本版可编辑的矢量边界图。图 2、图 3 复用已审矢量 PDF，同时提供由相同绘图源与公开表导出的 SVG 供 Markdown 和 HTML 阅读。已审 PDF 的 SHA-256 分别为 `78f58b7f9b1d9e6d56bd6fedecedb3ff6eca4f64c572c8c0d5c0997baee4ead1`、`1c278f463e4e78463673526cd4cb66c16624b8bc94ebffe01e1d718bd4f6d296`。[图 2 矢量原件](figures/T7-paired-directions.pdf) · [图 3 矢量原件](figures/T8-edit-tradeoffs.pdf) · [图形导出程序](render_figures.py)
