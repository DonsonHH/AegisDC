# 正文数字溯源

各行对照[正文](manuscript.md)与发布提交 [72d10c07](https://github.com/DonsonHH/AegisDC/commit/72d10c07250cd43395cff7ad07e3c1d325c8e3e7)。下列短文件名均相对于 `docs/mainline/t7-incident-counterfactual/`，另行列出的 T6 正文除外。文件链接固定到该提交的原始行号。

| 正文位置 | 数字、单位及读法 | 封存文件及行号 |
|---|---|---|
| <a id="panel"></a>设计 · 面板与五臂 | T7 的 H3 一次确认。两族各 60 个条件，每族权重 0.5。同一条件内五臂独立运行。P 为既有保护，V\*\* 为 `V_COST`。 | [r1/registration.json:26–27][holdout]、[r1/registration.json:46–63][panel-size]、[r1/registration.json:117][average]、[README.md:3][arms]、[stage2/README.md:31][once-used] |
| <a id="overlap"></a>设计 · 历史重合 | 原主分析 120 个条件。16 个条件的运行输入与旧面板重合，按登记只从描述性子集剔除。 | [stage2/README.md:29][overlap] |
| <a id="endpoint"></a>设计 · 整窗端点 | L 为归一化服务缺额秒。对每臂每条件，未舍入的 L > 0 记一次事件，L = 0 记无事件。 | [r1/registration.json:66–75][endpoint]、[T6 正文 manuscript.md:19][loss-definition] |
| <a id="oracle"></a>设计 · 全知参照 | ORACLE 为 T3 原开发条件的评价端描述性参照。H3 未安排 ORACLE，无该臂留出读数。 | [stage1/README.md:7][dev-oracle]、[stage2/tables.md:32][held-oracle] |
| <a id="inference"></a>主结果 · 区间与校正 | HA、HB、HC 三项。各区间为边际双侧 95% 区间，对三项原始双侧 p 统一作 Holm 校正。 | [stage2/tables.md:3–7][table-header]、[r1/registration.json:117–125][inference] |
| <a id="ha"></a>主结果 · HA | V\*\* 减 P 的平均 L 差为 −580.00 秒，对应正文所说的平均少约 580 秒。区间 [−595.52, −564.48] 秒。封存表原始 p 为 5.174524e-08，Holm p 为 1.552357e-07，按引用卡显示为 1.55×10⁻⁷。判定 MET。 | [stage2/tables.md:9][ha] |
| <a id="hb"></a>主结果 · HB | V\*\* 减报警响应的平均 L 差为 −582.08 秒，区间 [−612.65, −551.51] 秒。封存表原始 p 为 7.66355e-07，Holm p 为 1.53271e-06，按引用卡显示为 1.53×10⁻⁶。判定 MET。 | [stage2/tables.md:10][hb] |
| <a id="hc"></a>主结果 · HC | V\*\* 减 P 的事件率点估计为 −37.50 个百分点。区间和原始 p 均未建立。Holm 列的 1 为占位，保留三项校正分母。判定 INDETERMINATE。 | [stage2/tables.md:11–13][hc]、[r1/registration.json:125][degenerate] |
| <a id="service-counts"></a>主结果 · 逐条件方向 | 对 P 的 120 个同条件配对中，V\*\* 的 L 较小、相同、较大分别有 70、50、0 行。分别来自伦敦的 40、20、0 与荷兰的 30、30、0，按列相加。 | [stage2/tables.md:59][london-passive]、[stage2/tables.md:63][netherlands-passive] |
| <a id="events"></a>事故是否避免 · 配对计数 | P 有缺额的 90 行中，V\*\* 归零 45 行（伦敦 35、荷兰 10），仍有缺额 45 行（伦敦 10、荷兰 35）。P 无缺额的 30 行（伦敦、荷兰各 15）中，新增事件为 0。 | [stage2/tables.md:36–39][pairs]、[stage2/README.md:13][event-totals] |
| <a id="periodic"></a>人力取舍 · 周期巡检 | 所有 120 行均省人秒（两族各 60 行）。伦敦每条件少用 446.83 人秒、少 175.00 秒缺额。荷兰每条件少用 1371.42 人秒、少 660.00 秒缺额。节省量取封存配对均差的相反数。 | [stage2/tables.md:55–57][diff-labels]、[stage2/tables.md:61][london-periodic]、[stage2/tables.md:65][netherlands-periodic] |
| <a id="losses"></a>人力取舍 · 十个劣例 | 荷兰 10 行的整窗缺额均为 V\*\* 120 秒、周期巡检 0 秒。下列 H3 条件依次对应原表第 101 至 110 行，分别是 `6-06`、`6-07`、`6-22`、`6-23`、`6-27`、`6-28`、`6-40`、`6-47`、`6-52`、`6-54`。 | [stage2/tables.md:95–110][losses] |
| <a id="wait"></a>失败型 · 等待与见证 | 荷兰 60 个可判条件中有 30 个满足等待失败定义。其中 25 个也有 B 及时完成重分组、避开转供跳闸并减少转供段缺额的同条件见证。 | [stage2/protocol.md:11][wait-rule]、[stage2/tables.md:114][wait] |
| <a id="example"></a>失败型 · H3 实例 | H3 的 `6-06`。B 在 95 秒完成有效重分组，V\*\* 在最后合法重分组帧 540 秒选择 WAIT。1800 至 1920 秒的转供段缺额为 V\*\* 120 秒、B 0 秒。后续泵操作回执为 NO_EFFECT。 | [stage2/tables.md:116–117][witness-header]、[stage2/tables.md:121][example]、[stage2/README.md:25][example-text] |
| <a id="next"></a>失败型 · 后续研究问题 | T8 是后续研究编号。本文由等待失败提出及时处置问题。五臂只能比较固定策略整体，最后合法开工时点来自事后评价，决策仅可使用届时公开的合法信息。 | [README.md:53][later-gate]、[r1/registration.json:63][available]、[stage2/protocol.md:11][wait-rule]、[stage2/README.md:23][scope] |
| <a id="blocks"></a>事故是否避免、局限 · 块间方差 | 两个合成族各五个块，每块十二（12）行。伦敦各块 P、V\*\* 的事件数分别为 9、2，荷兰分别为 9、7。因此伦敦各块配对差均值均为 −7/12，荷兰均为 −2/12，两族块间方差均为零。 | [stage2/README.md:3][block-means]、[stage2/README.md:11][block-counts]、[r1/registration.json:125][degenerate] |
| <a id="field"></a>局限 · 外推 | 两起历史事故的复盘先于合成族和策略设计。HA、HB 的区间来自冻结配额块下的估计，现场缺少暴露分母、当班记录、授权和设施状态，外推误差尚无现场量化依据。 | [r1/registration.json:117–125][inference]、[contamination.md:3][prior-knowledge]、[contamination.md:13][field]、[r1/registration.json:144–146][field-data] |

[holdout]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/r1/registration.json#L26-L27
[panel-size]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/r1/registration.json#L46-L63
[average]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/r1/registration.json#L117
[arms]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/README.md#L3
[once-used]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L31
[overlap]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L29
[endpoint]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/r1/registration.json#L66-L75
[loss-definition]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t6-paper-consolidation/r3/manuscript.md#L19
[dev-oracle]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage1/README.md#L7
[held-oracle]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L32
[table-header]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L3-L7
[inference]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/r1/registration.json#L117-L125
[ha]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L9
[hb]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L10
[hc]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L11-L13
[degenerate]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/r1/registration.json#L125
[london-passive]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L59
[netherlands-passive]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L63
[pairs]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L36-L39
[event-totals]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L13
[diff-labels]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L55-L57
[london-periodic]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L61
[netherlands-periodic]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L65
[losses]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L95-L110
[wait-rule]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/protocol.md#L11
[wait]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L114
[witness-header]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L116-L117
[example]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L121
[example-text]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L25
[later-gate]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/README.md#L53
[available]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/r1/registration.json#L63
[scope]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L23
[block-means]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L3
[block-counts]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L11
[prior-knowledge]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/contamination.md#L3
[field]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/contamination.md#L13
[field-data]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/r1/registration.json#L144-L146
