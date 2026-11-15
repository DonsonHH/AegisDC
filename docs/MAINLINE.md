# 当前研究主线：事故机制、方法有效性与自改进

**854379d7的E1–E4声明有限资格已由用户接受。** 当前授权C4/C7公开准入修复、独立回归及有限连续接口验证，并集中编写R3条件价值协议候选。原105／15输入与结果保持；完整参数域／Q11／R2未自动通过，收益实验未授权。

本轮验收：[集中结果](mainline/review-gated/R2/extensions/e1-e4-execution/README.md) · [回执](mainline/review-gated/R2/extensions/e1-e4-execution/result.json)。执行依据：[v2修订](mainline/review-gated/R2/extensions/e1-e4-v2/revision.md)。原[R2接受记录](mainline/review-gated/R2/execution/acceptance-20261114.json)、[v1规格](mainline/review-gated/R2/extensions/e1-e4-v1/README.md)与[R3原提案](mainline/review-gated/R3/method-protocol-proposal.md)按原时点保留。当前范围与权限以[进度账](mainline/progress.json)为准。

## 拟研究的问题

在维护降级、相关失效和不完备信息下，基于可用证据的设施核查与受约束处置，能否在声明条件内避免事故升级或减少服务损失？在相同外生资料、合法信息获取机会、反馈规则、权限和预定预算下，普通自改进以及递归增量分别能带来什么？各组主动核查及候选评价产生的实际反馈随本组行动决定并计成本，详见提案的比较公平性规则。

两起 Google 事故作为机制来源和开发案例。先把外部故障、保障失效、保护动作及服务后果分开，建立可核对的模型和合法动作，再做条件反事实比较。事故报告本身不证明“真实事故本来不会发生”；方法效果也不自动证明 RSI 效果。[来源及可验证性研究](research/20261112-incident-counterfactual-method.md)

## 按 review 推进

| 关卡 | 核心交付 | 当前权限 |
|---|---|---|
| R0 | 研究方向与底线；具体模型／协议／数值标准保留后继审查 | 方向已接受 |
| R1 | 来源、决策信息、动作约束、最小因果接口与可识别性 | 修正版资料基线已接受 |
| R2 | 伦敦 PRE 受限合成模型资格 | 已接受旧有限范围；E1–E4声明有限范围已接受；C4/C7修复进行中；完整Q11／R2未接受 |
| R3 | 固定方法、强基线与协议 | 方向已调整为核查与合法直接修订的条件价值；仅D入口实现，数值研究协议未冻结 |
| R4 | 方法效果、反事实适用域及消融 | 未授权 |
| R5 | 普通自改进与 RSI 的独立增量 | 未授权 |
| R6 | 主张—证据矩阵与论文论证 | 未授权 |

每关先交付，再由用户 review；接受当前关卡不自动授权下一关。新试验、模型调用及研究性数值资格须等具体关卡授权。源事实、假设、未知、事后根因、决策者当时可用信息分别记录；权限、既有保护与封存评价器保持约束。

## 历史和本轮工程状态

PR #3 已再次复核并合入 `donson/mainline-39c-endpoints`，合并提交 `4a9dfdbe`；运行内容与通过远端维护验证的版本一致。这仅是维护合并，未接受旧 39c 整票。

重整前的 [MAINLINE／progress／current-research 原始快照](mainline/history/20261112-before-reset/README.md)逐字节保留。旧票、协议、原件、失败和原 180 次结果均在原位置。原八域合成设施是待按新问题审查的复用资产；既有通过数量不成为新主线已完成数量。[旧比较范围](mainline/preset-study-scope.json)

本地仅编辑、SSH、必要传输和完整性核对；计算与依赖安装遵循[远端规则](agents/compute-storage.md)。E1–E4有限资格已接受；当前仅授权C4/C7修复、新增有限接口验证、受影响回归及R3候选编制。独立输入先冻结，远端执行留痕，集中交付后停止；不预设核查优于直接处置。
