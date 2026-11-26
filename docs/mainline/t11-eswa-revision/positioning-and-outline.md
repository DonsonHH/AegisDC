# 投稿定位与页数预算

**建议主标题：Cost-aware value-of-information scheduling of inspections and interventions in maintenance-degraded computing facilities**

中文工作题为“面向维护降级计算设施的成本感知信息价值调度”。它把方法、两类可控行动和使用条件放在标题中，避免把全篇缩成“是否等一份读数”。

另两项可供 PI 选择：

- **Evidence-driven scheduling under maintenance constraints in coupled computing facilities: A preregistered paired simulation study**。强调既有主比较的研究设计；摘要需另标后补对照的证据等级。
- **Belief-based dispatch of field inspections and corrective work for coupled computing services**。强调可获得证据、现场作业和服务交付，适合把方法可解释性作为第一贡献。

## 论文回答的问题

一个受维护约束的计算设施同时有多个可能的服务瓶颈。调度器在仅见到时证据时，怎样选择**查什么、是否等、何时直接干预、如何复核**，使全窗服务缺额和作业成本在可行范围内更低？贡献放在“有限世界信念 → 有准入约束的下一份具名作业 → 独立的整窗服务评价”。这延续 11 月 20 日的完整设施主线，事故族用于检验机制能否表达并影响服务。单次核查是否有价值属于该方法的一个条件问题。[主线交接](https://github.com/DonsonHH/AegisDC/blob/abc8ff50c751543a15f993f695939357c8257918/docs/mainline/full-facility-method-handoff.md) · [导师目标与 FEMA 定义](https://github.com/DonsonHH/AegisDC/blob/abc8ff50c751543a15f993f695939357c8257918/docs/meetings/2026-11-03-research-reset.md)

## 英文正文目录（计划 16 页，含参考文献）

| 拟设小节 | 页数 | 读者应能在正文中回答的问题 |
|---|---:|---|
| 摘要与关键词 | 0.50 | 运行对象、可见信息、决策和端点是什么？摘要明确区分预注册与事后证据。 |
| 1. Decision support during maintenance | 1.50 | 为什么耦合设施的供电／热／IT 服务和人员许可要一起考虑？相关工作按方法问题组织。 |
| 2. Partially observed facility and work constraints | 2.00 | 什么属于实际设施、公共材料、合法动作和假设世界？给状态、时钟、观察与服务积分。 |
| 3. Cost-aware inspection and intervention scheduling | 2.50 | 给后验、报告分组、UNKNOWN、资源可行域、同一报告共用续排、伪代码与复杂度。 |
| 4. Design, comparators and endpoints | 1.50 | 主比较的六族 144 条与后补的开发 72 条如何区分？对照得到什么信息、能做什么工作？ |
| 5. Service and cost under the main comparisons | 2.00 | 依序报告 H1–H3 的原点估计、区间和分母。后补的两种算法若另获授权并完成，放独立面板；当前保留待测。 |
| 6. When does a paid reading change the decision? | 1.25 | 以 0／600／1,200 秒维护分层为中心，列正反见证、人秒和单因素结果的状态。分层是描述性证据。 |
| 7. Mechanism checks in two synthetic incident families | 1.25 | HA/HB 的服务严重度与 HC 零方差分别意味着什么？现场复盘对机制能约束到哪一层？ |
| 8. Limits of feedback-based improvement | 0.75 | 合并 C3 的迁移反例和 C4 的零增量，保留工时越界；后继 RSI 研究另立。 |
| 9. Operational meaning, conditional risk and limitations | 1.25 | 每个维护窗的服务、人员、工具与费用是多少？什么是频率情景、什么还需要现场材料和决策耗时？ |
| References | 1.50 | 从候选地图择直接论证所需的工作。若最终参考文献排版超额，优先扩页，并保留方法和负结果。 |
| **合计** | **16.00** | 英文单栏排版预算。附录另计。 |

建议补充材料 A（2 页）放参数、资格与运行时计量，B（2 页）放全部配对、场景权重及未决项，C（1 页）放版本、保管程序、签名归属和复核范围。此处是版面规划，T10 的 10 页原文保持原样。

## 从内部编号转为读者可懂的表述

| 原术语 | 正文首次出现 | 后续用法 |
|---|---|---|
| V_COST / V\*\* | 成本感知检查—处置调度器 | 本文方法，实施标识放附录 |
| B / B_cost / NOPROBE | 透明直接处置规则／成本感知直接规则／同策略禁用初检 | 表内用简写并与对照定义并排 |
| I/A/R/X | 付费初检、直接处置、本人处置后的复核及续核 | 算法框保留四种动作，正文用作业名称 |
| L/U、NA/PV | 归一化服务缺额秒／未服务量；未处置情况下的有效检查关闭／本人处置后的验证关闭 | 图表脚注写清有效时点和分母，关闭与服务分别计量 |
| FIT/DEV、R/O | 选优面板／另设资格面板；可改写搜索／普通搜索 | 首次解释，避免把选优结果写成 DEV 资格 |
| H1–H3、HA–HC | 预注册比较的标识 | 与同名的保管种子分开。正文表中按对照、端点和单位阅读。 |

正文将输入如何受限、方法如何选择、原始比较数值和负结果直接放在表／算法框内。仓库链接只承担追溯，不替代定义。保管问题在正文只留一句：“历史选优面板采用同账号的程序性查重，保管与归属的核验范围见补充材料。” 补充保留 PASS 回执、代签的个人授权归属有异议且未独立证实、共用账号及其对独立性解释的限制。[已接受的原局限](https://github.com/DonsonHH/AegisDC/blob/361574a049f0cfbf816f62af92ff5fd398d77ae8/docs/mainline/t9-submission-r1/manuscript.md#L161-L167)
