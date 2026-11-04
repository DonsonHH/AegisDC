# 主线任务依赖图

固定目标见[主线入口](../../docs/MAINLINE.md)，详细契约见[spec](spec.md)。票据Status与Evidence是完成依据；只执行阻塞项均已解决的任务。

|ID|阶段|端到端结果|Blocked by|
|---|---|---|---|
|01|M0|[固定总目标、场景身份和验收契约](issues/01-freeze-mainline.md)|None (can start immediately)|
|02|M1|[读取并核验独立全设施场景](issues/02-scenario-contract.md)|01|
|03|M1|[跑通八域正常工况竖切片](issues/03-healthy-site.md)|02|
|04|M1|[在全场传播供电容量和失电](issues/04-power-response.md)|03|
|05|M1|[在全场传播滤阻、泵阀和板换变化](issues/05-water-response.md)|03|
|06|M1|[闭合相变库存、内能和冷凝响应](issues/06-phase-response.md)|03|
|07|M1|[让房间、泄漏与访问条件影响作业](issues/07-environment-access.md)|03|
|08|M1|[让计算、网络和存储决定服务缺额](issues/08-service-accounting.md)|03|
|09|M1|[使本地控制与自动保护实际响应](issues/09-local-control.md)|04, 05, 06|
|10|M1|[让UPS、柴油与维护改变保障能力](issues/10-reserve-response.md)|04, 05|
|11|M1|[验收同一全设施模型的跨系统行为](issues/11-coupled-acceptance.md)|04, 05, 06, 07, 08, 09, 10|
|12|M2|[用独立算例验证数值与步长](issues/12-numerical-verification.md)|11|
|13|M2|[重放外生作业、故障与维护场景](issues/13-event-replay.md)|11|
|14|M3|[接收有到达时间和共同来源的记录](issues/14-evidence-ledger.md)|12, 13|
|15|M3|[验证决策视图不泄漏真实故障](issues/15-truth-isolation.md)|14|
|16|M3|[让稀疏测点、偏差和迟到形成可用信息](issues/16-sensor-channels.md)|14|
|17|M3|[让历史、人工和手持检查提供证据](issues/17-nonfixed-evidence.md)|14|
|18|M3|[建立随证据和时间变化的风险认识](issues/18-belief-updates.md)|15, 16, 17|
|19|M3|[把FEMA情景、后果和能力映射到风险](issues/19-risk-scenarios.md)|18, 08|
|20|M3|[比较检查信息与可执行处置的价值](issues/20-action-value.md)|19|
|21|M4|[执行专业、工具、路径和占用约束](issues/21-heterogeneous-workers.md)|07, 14|
|22|M4|[把检查执行与现场证据接起来](issues/22-inspection-actions.md)|17, 21|
|23|M4|[让处置延时、残余效果与服务响应闭环](issues/23-intervention-actions.md)|20, 21|
|24|M4|[用恢复证据关闭问题](issues/24-verified-closure.md)|22, 23|
|25|M4|[在同一设施运行透明比较策略](issues/25-transparent-baselines.md)|24|
|26|M4|[实现一个可证伪的联合核查处置候选](issues/26-candidate-policy.md)|20, 25|
|27|M4|[重放完整设施的跨系统闭环](issues/27-full-loop-demo.md)|26, 13|
|28|M4|[验证正常、误报和来不及挽救的情景](issues/28-negative-controls.md)|27|
|29|M5|[冻结可行参数域和模型可信度边界](issues/29-uncertainty-domain.md)|12, 28|
|30|M5|[预注册独立比较问题、指标和预算](issues/30-freeze-protocol.md)|29|
|31|M5|[在已见条件开发和诊断方法](issues/31-development-run.md)|30|
|32|M5|[核对执行源码、配置和原件生命周期](issues/32-freeze-execution.md)|31|
|33|M5|[执行封存独立条件](issues/33-confirmation-run.md)|32|
|34|M6|[形成主要结果、成本和约束结论](issues/34-paired-analysis.md)|33|
|35|M6|[隔离信息、依赖知识和协作机制](issues/35-knowledge-ablation.md)|34|
|36|M6|[评价参数域、结构变体与模型误差](issues/36-robustness-study.md)|34|
|37|M6|[形成全设施基线研究结论和复算包](issues/37-baseline-report.md)|35, 36|
|38|M7|[审计智能体与经验改进的进入条件](issues/38-agent-eligibility.md)|37|
|39|M7|[条件式比较智能体的独立增量](issues/39-agent-increment.md)|38|
|40|M7|[条件式比较普通反馈与递归改进](issues/40-rsi-increment.md)|39|
|41|M7|[复核智能体/RSI结果或资格限制](issues/41-increment-conclusion.md)|38, 39, 40|
|42|M7|[逐项复核固定总目标与最终研究结论](issues/42-research-closeout.md)|37, 41|

M1/M2保持完整设施并分层验证；M3/M4完成证据、认识和专业作业闭环；M5/M6独立比较与归因；M7仅按真实资格进入。步骤数量不构成进度，接受证据才构成进度。
