# 两类合成事故中的服务缺额与处置时机

[数字溯源表](numeric-sources.md)

## 设计

T7 使用 H3 留出面板进行了一次确认。伦敦式和荷兰式各有 60 个条件。每个条件在相同的设施输入、故障和维护安排下独立运行五臂，即仅保留既有保护的 P、周期巡检、报警响应、强透明规则 B，以及冻结的风险驱动策略 V\*\*（`V_COST`）。[README.md:3][arms] · [r1/registration.json:46–63][panel-size] · [stage2/README.md:31][once-used]

先在同一条件内配对，再取两族各自的平均差，两族等权。主分析保留全部 120 个条件，包括运行输入与旧面板重合的 16 个条件。[r1/registration.json:117][average] · [stage2/README.md:29][overlap]

整窗服务缺额 L 的单位为秒。在有需求的时段，将未交付服务占需求的比例乘以时段长度，再对整个评价窗求和。某臂未舍入的 L > 0，该条件在该臂下就记一次合成事件。[r1/registration.json:66–75][endpoint] · [r3/manuscript.md:19][loss-definition]

T3 开发条件另有只作描述的全知排程参照（ORACLE），H3 未设该臂。[stage1/README.md:7][dev-oracle] · [stage2/tables.md:32][held-oracle]

## 主结果

相对仅保留既有保护的 P，V\*\* 平均每个条件少约 580 秒服务缺额。在 120 个配对中，V\*\* 的缺额较小、相同、较大的条件数分别为 70、50、0。[stage2/tables.md:9][ha] · [stage2/tables.md:59][london-passive] · [stage2/tables.md:63][netherlands-passive]

下表的差值方向为 V\*\* 减去相应对照。三项主检验采用边际双侧区间，双侧 p 值统一按 Holm 法校正。[stage2/tables.md:3–7][table-header]

| 编号 | 配对量 | 点估计 | [95% 区间][table-header] | Holm p | 判定 | 封存行 |
|---|---|---|---|---|---|---|
| HA | 相对既有保护 P 的 L 差 | −580.00 秒 | [−595.52, −564.48] 秒 | 1.55×10⁻⁷ | MET | [stage2/tables.md:9][ha] |
| HB | 相对报警响应的 L 差 | −582.08 秒 | [−612.65, −551.51] 秒 | 1.53×10⁻⁶ | MET | [stage2/tables.md:10][hb] |
| HC | 相对 P 的事件率差 | −37.50 个百分点 | 未建立 | 1（占位） | INDETERMINATE | [stage2/tables.md:11–13][hc] |

HC 的原始 p 值和区间均未建立。Holm 列中的 1 是为保留三项校正分母而设的占位值。[stage2/tables.md:11–13][hc] · [r1/registration.json:125][degenerate]

## 事故是否避免

在 P 有缺额的 90 个条件中，45 个在 V\*\* 下归零，45 个仍有缺额。在 P 无缺额的 30 个条件中，新增事件为 0。两族事件率配对差的块间方差均为零，HC 按预注册规则不可判。[stage2/README.md:13][event-totals] · [stage2/tables.md:36–39][pairs] · [stage2/tables.md:11–13][hc]

## 人力取舍

相对周期巡检，V\*\* 在全部 120 个条件中都少用人力。按每个条件的均值，伦敦族少用 446.83 人秒，整窗服务缺额少 175.00 秒。荷兰族少用 1371.42 人秒，缺额少 660.00 秒。这两组差值均作描述性比较。[stage2/tables.md:61][london-periodic] · [stage2/tables.md:65][netherlands-periodic]

荷兰族有 10 个条件的服务结果较差。这些条件在周期巡检下的整窗缺额均为 0，在 V\*\* 下每个条件都有 120 秒缺额。[stage2/tables.md:95–110][losses]

## 失败型

荷兰族 60 个条件中，V\*\* 在 30 个条件的最后合法开工时点仍选择等待，未能在故障前完成重分组，随后转供跳闸并出现服务缺额。其中 25 个条件有强规则 B 的配对见证。B 及时完成重分组，转供时没有跳闸，转供段的服务缺额也较小。[stage2/protocol.md:11][wait-rule] · [stage2/tables.md:114][wait]

在 H3 条件 `6-06` 中，B 在 95 秒完成有效重分组，V\*\* 在 540 秒的最后合法开工时点仍选择等待。1800 至 1920 秒转供期间，V\*\* 和 B 的服务缺额分别为 120 秒和 0 秒。此后 V\*\* 的泵操作回执为 `NO_EFFECT`。[stage2/tables.md:121][example] · [stage2/README.md:25][example-text]

最后合法开工时点由评价者事后判定。T8 据此追问，仅凭决策时已到达的公开证据、许可和作业时间，能否在值得处置的窗口及时行动，同时维持其他工况的表现？本次五臂比较衡量冻结策略的整体效果，付费采样的独立贡献仍待识别。[README.md:53][later-gate] · [r1/registration.json:63][available] · [stage2/protocol.md:11][wait-rule] · [stage2/README.md:23][scope]

## 局限

本研究在固定生成器和配额下评价两个合成事故族，每族包含五个十二条件块。伦敦每块中，P 和 V\*\* 出现服务缺额的条件数均为 9 和 2，荷兰每块均为 9 和 7。因此，事件率配对差在两个族内的块间方差均为零，HC 按预注册规则不可判。[stage2/README.md:3][block-means] · [stage2/README.md:11][block-counts] · [r1/registration.json:125][degenerate]

HA、HB 的区间刻画的是这一设计内平均缺额差的块间变动。将其推广到故障构成或作业条件分布不同的设施，可能高估估计精度。现有资料尚不能量化这种外推误差。两起事故的复盘先于合成族和策略设计。现场频率端未建立，真实事件的历史反事实仍缺当班记录、授权和现场状态。[r1/registration.json:117–125][inference] · [contamination.md:3][prior-knowledge] · [contamination.md:13][field]

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
[london-periodic]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L61
[netherlands-periodic]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L65
[losses]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L95-L110
[wait-rule]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/protocol.md#L11
[wait]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L114
[example]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/tables.md#L121
[example-text]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L25
[later-gate]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/README.md#L53
[available]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/r1/registration.json#L63
[scope]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L23
[block-means]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L3
[block-counts]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/stage2/README.md#L11
[prior-knowledge]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/contamination.md#L3
[field]: https://github.com/DonsonHH/AegisDC/blob/72d10c07250cd43395cff7ad07e3c1d325c8e3e7/docs/mainline/t7-incident-counterfactual/contamination.md#L13
