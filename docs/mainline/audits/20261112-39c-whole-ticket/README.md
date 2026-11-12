# 39c 整票独立复核

第 58 项经用户核验通过。**整票未验收，五个验收框保持开放。** 本轮只读核对代码和既有回执，没有新增设施进入、项目测试、注册研究或 CI。复核冻结在 `8a366e9b7d7bc76d1dbe7e53e29c8284682f7ab3`，从 39c 首个冻结切片的父提交 `42252bf8a9242f9141212fa4922318ca82ed310c` 起比较。复核使用 `git diff 42252bf8...8a366e9b` 和 `git log 42252bf8..8a366e9b --oneline`（165 个提交）；审查对象是其中的 39c 变更。独立 Spec 与 Standards 分开评阅，以下证据已与留存回执交叉核对。

## Spec

对照[票面五项](../../../../.scratch/full-facility-mainline/issues/39c-business-endpoints-and-closure.md)、[主线规约](../../../../.scratch/full-facility-mainline/spec.md)和[会后 R6](../20261109-integrated/meeting-gaps.md)。表中每一行区分预定契约、已执行验证与能支持的结论。

| 验收框 | 契约／协议 | 可核对的已执行验证 | 证据边界与本轮判定 |
|---|---|---|---|
| 1. 误判、漏报与机会分母 | [公开判定和私有事件契约 03](../../39c-state-diagnostic-contract-03.md)；[主动暂缓契约 13](../../39c-deliberate-defer-contract-13.md) | 切片 04 的[正常原件](../../../../evidence/mainline/engineering/39c-development/slice-04/07-state-diagnostic-qualification/normal--business-result.json)和[错误需求模型原件](../../../../evidence/mainline/engineering/39c-development/slice-04/07-state-diagnostic-qualification/wrong-demand-model--business-result.json)给出误判 **0/1、1/1**；[07 正常模式](../../../../evidence/mainline/engineering/39c-development/slice-07/README.md)核对了 44 件保存输出。按时确认例为漏确认 0/1；[13 暂缓例](../../../../evidence/mainline/engineering/39c-development/slice-13/16-deliberate-defer-green/business-result.json)截止 2 秒、确认 2.25 秒，漏确认 **1/1**。[10–14](../../../../evidence/mainline/engineering/39c-development/reference-window-checkpoint/README.md)保留参考未建模、不可用、来不及的事件；这些工况适用分母 0，率为 null。 | **可数实例已成立，事件去重仍有缺口（SPEC-01）。** 分母是声明的初始状态事件与合成参考机会；虚假工单、读数发现和系统确认各有口径。原 04 整批仍为 FAILED，已保存的结果和事后只读复核分开记录。这些比例不能作为现场准确率或根因准确率。 |
| 2. 提前量、删失及预防 | [时序契约 37](../../39c-temporal-endpoints-contract-37.md)、[38 输入修订](../../39c-temporal-input-correction-contract-38.md)和[41 资格](../../39c-temporal-remaining-qualification-contract-41.md) | [38 实际输出](../../../../evidence/mainline/engineering/39c-development/slice-38/business-result.json)中确认在 1.75 秒可用；故障和服务首样本均在 1 秒，提前量分别 **−0.75、−0.75 秒**，转换区间均为 `(−1.75, −0.75]` 秒；3.5 秒计划处置截止的余量 **+1.75 秒**。[39](../../../../evidence/mainline/engineering/39c-development/slice-39/qualification.json)四种边界覆盖左／右删失、未确认和未建模；[41](../../../../evidence/mainline/engineering/39c-development/slice-41/qualification.json)覆盖有确认而 2 秒仍未采到服务损失的情形，已观察提前量为 null，若损失以后出现才有 0.25 秒条件下界。 | **有限时序证据成立；预防效应未识别。** 无冻结、实际执行的匹配预防反事实，输出明确为 `NOT_IDENTIFIED_NO_PAIRED_COUNTERFACTUAL`。满足票面的“或明确未识别”分支。首样本不是精确物理起点，计划余量不等于可挽救，服务损失也没有自动归因。原 37 失败保留。 |
| 3. 复检及验证关闭 | [实例自身关闭契约 16](../../39c-instance-closure-contract-16.md)、[私有管理端点 51](../../39c-instance-management-endpoint-contract-51.md)、[52 分支资格](../../39c-instance-management-qualification-contract-52.md) | [18 两个实际案例](../../../../evidence/mainline/engineering/39c-development/slice-18/README.md)在 3.25 秒完成行动、5 秒完成自身复检，5.5 秒复检结果到达。服务合格例 5.5 秒验证关闭，服务受阻例仍为症状退去待核验。[52](../../../../evidence/mainline/engineering/39c-development/slice-52/README.md)的四个实际窗口区分风险接受后过期、仅历史有效、升级优先和基于证据审查误报；新实例的管理处置没有产生物理关闭。 | **有限行为证据成立。** 仅在已到达证据和离散评价时刻核验适用实例，不能保证连续恢复或跨实例复用。风险接受、升级、症状退去和物理恢复分别记录；共用词表仍需对齐（STD-02）。 |
| 4. 成本与完整分母 | [实际成本 42](../../39c-actual-cost-contract-42.md)、[任务归属 44](../../39c-task-cost-attribution-contract-44.md)、[45 工况资格](../../39c-cost-qualification-contract-45.md) | [44 中止原件](../../../../evidence/mainline/engineering/39c-development/slice-44/green/result.json)在 0.75 秒中止后仍计 0.5 人秒作业、0.25 人秒等待、0.75 工具秒与费用 1；[45 五工况](../../../../evidence/mainline/engineering/39c-development/slice-45/qualification.json)保留完成、中止、拒绝、窗内未完成和共享排队。共享队列的 0.5 人秒只计一次。计算审计将选择／判定调用与纳秒计时分开，无人、未测和失败保留。 | **部分覆盖（SPEC-02）。** 人时、工具时、等待、作业、合成发出费用、已插桩计算和失败归属可核对；已有移动人时，米制路程仍未测。内部嵌套调用、货币和计算能耗也保持未测，不能当成零。工况表是有限工程分母，不是完整现场成本分布。 |
| 5. 私有真值、到时证据及冻结执行 | [公开／私有契约 03](../../39c-state-diagnostic-contract-03.md)、[联合契约 53](../../39c-composite-endpoint-contract-53.md)、[录制契约 57](../../39c-business-record-replay-contract-57.md) | [33 公开选择](../../../../evidence/mainline/engineering/39c-development/slice-33/result.json)核验 24 条授权、来源、到时及实例边界；[53 公共接口测试](../../../../tests/test_composite_business_endpoint.py#L129)对应 8 次公开决策不含私有业务标识，私有评价在执行结束后进行。[57-R1](../../../../evidence/mainline/engineering/39c-development/slice-57/result.json)在两次 6 秒窗口精确重放；[58](../../../../evidence/mainline/engineering/39c-development/slice-58/result.json)通过 24 条负向用例、零设施进入。 | **权限隔离与有界重放有证据，整票交付仍开放。** 原 180 次未测端点不重标，注册数据未改。文件式 CLI 成功记录的原始提交内容绑定还有缺口（STD-01）。此处不作任意声明、任意场景的隔离或重放保证。 |

1. **SPEC-01，机会身份仍有缺口。** 契约 03 要求“重复判断/同源记录不能增加事件数”。[诊断验证器](../../../../src/aegis_dc/diagnostic_endpoints.py#L79)按条件、开启时刻、截止三元组去重，[既有负例](../../../../tests/test_diagnostic_reference_refusal.py#L27)只覆盖同截止别名。同一物理事件的不同截止视图尚可被当作两个事件纳入分母。建议固定物理机会身份，或把不同截止窗口明示为分开的敏感性视图，禁止合并计数。这个缺口来自静态复核；没有证据表明已经封存的单事件样本被重复计数。
2. **SPEC-02，路程只有未测字段。** [联合 53 成本](../../../../evidence/mainline/engineering/39c-development/slice-53/green/joint/business-result.json#L1460)中实际移动 2 人秒，`distance_m` 仍为 `NOT_RECORDED`；[成本实现](../../../../src/aegis_dc/cost_endpoints.py#L107)没有米制路程账。如果接受口径限于移动人时，应明确限定；如果要求米制路程，需要有依据的边长和实际路径，不能由耗时倒推。

## Standards

- **STD-01，文件式录制的证据绑定缺口。** [录制器](../../../../src/aegis_dc/replay.py#L207)保留 CLI 提交的原始字节和解析副本。[读取器](../../../../src/aegis_dc/replay.py#L364)核对文件哈希，并在 v3 下绑定解析副本与冻结输入，尚未核对完成记录的 `submitted-*.json` 与相应解析副本内容、请求角色的一致性。契约 57 要求绑定提交／冻结／实际输入。第 58 项的两个 CLI 负例只验证拒绝及留存，不能替代成功文件记录的来源绑定。此为静态发现，未执行新设施。
- **STD-02，术语需对齐。** [词表](../../../../GLOSSARY.md#L52)把风险接受纳入“验证关闭”，而票面、[实例端点](../../../../src/aegis_dc/business_endpoints.py#L105)和 52 实际分支明确分开。按[共用术语规则](../../../agents/domain.md)，应将管理接受和物理核验分列。
- **STD-03，前置状态需对齐。** [39r](../../../../.scratch/full-facility-mainline/issues/39r-risk-baseline-review.md)和[39t](../../../../.scratch/full-facility-mainline/issues/39t-time-foundation.md)仍为 `claimed`；[跟踪规程](../../../agents/issue-tracker.md)以票面状态为准。57、58 有用户单步授权。整票关闭前需要记录适用的有限前置处置或限定授权，不将 39t 数字资格升级。
- **已留档的执行偏差。** 契约 57 原定红测一次，实际两次、均零设施进入；[原回执](../../../../evidence/mainline/engineering/39c-development/slice-57/result.json)保留两次红测和首绿失败。[轻量规程](../../../agents/lightweight-engineering.md)已经要求先读终态和实际计数再启动新目录。保留原预算和结果。
- **非阻塞维护建议。** [业务端点的校验与求值](../../../../src/aegis_dc/business_endpoints.py#L184)分别按同一版本族分发，后续如有行为需求可减少重复分支。此处是维护判断，不构成本轮验收缺口。

静态核对了第 57 项五份冻结输入、第 58 项 52 个运行时文件及测试字节。原 180 次研究目录、原注册脚本和正式确认回执在复核区间无变化；已记录的失败未重标。

## 原件与交付门槛

- [目录清单哈希](origins-inventory.json)是第 58 项的只读补充回执。57-R1 原件、重放及 v1/v2 对照分别有 11、14、11、11 个文件；以相对路径和原始 SHA-256 组成清单，四份都与冻结基线逐文件相同。57-R1 依据原终态工件表及终态字节；旧版依据 Git 冻结成员。证明各核对时点的字节相等。58 原回执、测试及 57 的 3/3 预算保持原样。
- 下一步先处置上述缺口，再固定整票根回归。[当前常规 CI](../../../../.github/workflows/acceptance.yml)只安装最小环境，[根检查器](../../../../scripts/acceptance.py)允许两项可选 Torch 跳过，不能把现有检查点绿灯用作零跳过证明。验收应记录发现数＝执行数，且跳过、失败、错误均为 0。第 58 项私有原件验证脚本不在根测试自动发现路径，应单列其执行回执。
- 根回归之后，另从 GitHub 新检出按固定交付清单验证。进度登记中的本地导师 DOCX 和生成脚本未跟踪，本轮审查没有将它们计入 39c 验收证据；若后续交付要纳入，应在清单定版前明确列入或排除。

Spec 留有两项证据边界（事件身份、米制路程）。Standards 留有三项当前发现（文件来源绑定、术语、前置状态），另有一项已留档的历史偏差和一项非阻塞维护建议。整票仍为 `claimed`。
