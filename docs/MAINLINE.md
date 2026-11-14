# 当前研究主线：事故机制、方法有效性与自改进

**用户已接受有限 R2 资格和334e537b的R3候选方向；当前E1–E4扩展资格规格包待review。** R3数值协议未冻结。旧97单位、9组配对、406次断言只覆盖已声明的定性机械／信息接口及离线挑战，不能赋予新增能力资格。本轮集中编写契约、关系、预期和覆盖，未实现或执行。旧01–42／39c队列保持冻结。

本轮审阅：[E1–E4契约与参数](mainline/review-gated/R2/extensions/e1-e4-v1/README.md) · [关系和决定表](mainline/review-gated/R2/extensions/e1-e4-v1/relations.md) · [独立预期与覆盖](mainline/review-gated/R2/extensions/e1-e4-v1/expectations.md)。已接受候选方向：[R3原提案](mainline/review-gated/R3/method-protocol-proposal.md)。既有验收：[有限R2接受记录](mainline/review-gated/R2/execution/acceptance-20261114.json)；原[R2结果](mainline/review-gated/R2/execution/README.md)、[关系v2](mainline/review-gated/R2/relations-v2.md)、[覆盖v2](mainline/review-gated/R2/coverage-v2.md)、[狭义契约](mainline/review-gated/R2/qualification-contract.md)及[R1资料](mainline/review-gated/R1/README.md)保留。详细范围：[R0–R6计划](mainline/review-gated/plan.md)；唯一状态：[progress.json](mainline/progress.json)；决定沿革：[meeting](meetings/2026-11-12-research-mainline-reset.md)。

## 拟研究的问题

在维护降级、相关失效和不完备信息下，基于可用证据的设施核查与受约束处置，能否在声明条件内避免事故升级或减少服务损失？在相同外生资料、合法信息获取机会、反馈规则、权限和预定预算下，普通自改进以及递归增量分别能带来什么？各组主动核查及候选评价产生的实际反馈随本组行动决定并计成本，详见提案的比较公平性规则。

两起 Google 事故作为机制来源和开发案例。先把外部故障、保障失效、保护动作及服务后果分开，建立可核对的模型和合法动作，再做条件反事实比较。事故报告本身不证明“真实事故本来不会发生”；方法效果也不自动证明 RSI 效果。[来源及可验证性研究](research/20261112-incident-counterfactual-method.md)

## 按 review 推进

| 关卡 | 核心交付 | 当前权限 |
|---|---|---|
| R0 | 研究方向与底线；具体模型／协议／数值标准保留后继审查 | 方向已接受 |
| R1 | 来源、决策信息、动作约束、最小因果接口与可识别性 | 修正版资料基线已接受 |
| R2 | 伦敦 PRE 受限合成模型资格 | 已接受旧有限范围；E1–E4扩展规格待review，新增资格与Q11延期义务未解决 |
| R3 | 固定方法、强基线与协议 | 334e537b候选方向已接受；数值试验协议未冻结、方法未实现 |
| R4 | 方法效果、反事实适用域及消融 | 未授权 |
| R5 | 普通自改进与 RSI 的独立增量 | 未授权 |
| R6 | 主张—证据矩阵与论文论证 | 未授权 |

每关先交付，再由用户 review；接受当前关卡不自动授权下一关。新试验、模型调用及研究性数值资格须等具体关卡授权。源事实、假设、未知、事后根因、决策者当时可用信息分别记录；权限、既有保护与封存评价器保持约束。

## 历史和本轮工程状态

PR #3 已再次复核并合入 `donson/mainline-39c-endpoints`，合并提交 `4a9dfdbe`；运行内容与通过远端维护验证的版本一致。这仅是维护合并，未接受旧 39c 整票。

重整前的 [MAINLINE／progress／current-research 原始快照](mainline/history/20261112-before-reset/README.md)逐字节保留。旧票、协议、原件、失败和原 180 次结果均在原位置。原八域合成设施是待按新问题审查的复用资产；既有通过数量不成为新主线已完成数量。[旧比较范围](mainline/preset-study-scope.json)

本地仅编辑、SSH、必要传输和完整性核对；计算与依赖安装遵循[远端规则](agents/compute-storage.md)。本轮只交付E1–E4书面规格；拟定证据域内M0/B1动作等价，不预设方法增益，也不自动改R3主比较。既有结果不重跑；扩展实现、资格执行和研究实验须另行授权。
