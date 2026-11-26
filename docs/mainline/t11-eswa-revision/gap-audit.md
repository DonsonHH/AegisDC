# ESWA 六项缺口审计

[审查对象为英文候选版 abc8ff50](https://github.com/DonsonHH/AegisDC/tree/abc8ff50c751543a15f993f695939357c8257918/docs/mainline/t10-submission-en)。修改方案在 T11-0 锁定；正文重写须等 PI 另行决定。下表的“无”指可通过写作或直接核对现有实现完成。

| 缺口 | 现状与证据 | 修改方案 | 需要的新证据 |
|---|---|---|---|
| 1　标题与完整设施方法不匹配 | T10 标题集中在等待一次付费核查，实际方法还调度直接处置、本人复核和跨系统资源，原主比较也包含整套策略。 | 以“方法如何选择下一份合法作业”为主线。把“何时值得查”放在主比较之后，用维护时长分层和一正一反见证作答。 | **无**。[原题与正文](https://github.com/DonsonHH/AegisDC/blob/abc8ff50c751543a15f993f695939357c8257918/docs/mainline/t10-submission-en/manuscript.md#L1-L39) |
| 2　缺少对现代决策方法的直接比较 | 已有 B、B_cost、同策略禁购消融、巡检和报警等；它们不能回答有限树规划与单步 VoI 在同一接口下表现如何。 | 增加两个明确、可复现的算法对照。使用同一有限信念、实际作业门、资源与单次发行限制。监督式／深度强化学习维护文献作为方法定位，不给未经训练的网络冠以原文算法名称。 | **新运行**。72 条公开开发行的两种新策略；冻结原方法只读。[补充协议 P2–P3](supplement-protocol.md) |
| 3　形式化不完整 | T10 已有 L、J 和六步算法框。尚缺可见历史的数学边界、带来源的似然、报告分组的共同续决策及逐点复杂度。 | 给出状态、公开过滤、行动可行域、后验、混合匹配因子、UNKNOWN 分支和枚举上界，与真实函数逐一对应。 | **无**。[形式化草稿](method-formalization.md) |
| 4　12 项引用不足以定位方法 | 原稿 10 篇论文与 2 份报告支撑主要术语，但网络可靠性、现代维护规划、树搜索和期刊内应用仍欠比较。 | 50 篇候选按五条研究线组织；在修订稿中优先选能支撑具体方法差异或工程假设的论文。原事故报告与工程手册独立引用。 | **无**需新试验；已补 DOI 核验资料。[文献地图](literature-map.md) |
| 5　正文依赖外链，代号妨碍阅读 | 对价格、许可、数据边界及研究身份的若干解释留在仓库，外部读者还需辨认 V_COST、NA/PV、FIT/DEV。 | 主要定义、预算、算法、基本对照、绝对端点和反例入正文。内部角色与版本对照、详细签名记录及公开复核路径入补充。 | **无**。[章节预算和术语替换](positioning-and-outline.md) |
| 6　参数、实用意义与耗时 | 已有 v3 机制 S0/S1/S2 和原确认的时长分层，尚缺四个决策旋钮的 OAT。已有实际服务和工时、可重加权的逐行公开成绩，以及约 100 秒的整位置墙时。逐决策点延迟尚未建立。 | 服务差同时报告绝对缺额、资源、费用、拒绝与关闭；给假设情景的加权后果。OAT 一参两侧，中心分数只读。逐点延迟先查旧开发日志，再决定是否需要独立的公共工人计时。 | **已有聚合**可支持实用量级与情景算术；**新运行**才可评价八个 OAT 变体；无历史逐点计时时，另列**新计时运行**，不重跑中心设施。[归档敏感性](https://github.com/DonsonHH/AegisDC/blob/036ccfdf2d6e5d4b39ba11da480fa2a3d69c1f9f/docs/mainline/t4d-cost-baseline-v1/README.md) · [P4–P7](supplement-protocol.md) |

## v3 维护暴露的工程依据和参数依据

| 问题 | 可以用什么支持 | 仍取决于什么 |
|---|---|---|
| 维护中“上游有电”能否与负荷侧真实可用相背离？ | Google 伦敦 11 月 4 日复盘的根因段说明，维护隔离、上游电压信号、实际断路器位置和发电机启动判断可以不一致。UPS 曾承担负荷，随后储能耗尽。这支持将可见信号、真实保护和后备可用分开。 | 复盘并未给出本文干预约束的逐时服务曲线。同一报告事件表与分产品影响说明中的 23:00／22:53 不能解释为七分钟可用处置余量。[Google 官方复盘](https://status.cloud.google.com/incidents/Xs2XTHzAVC9YnafnPyzj) |
| 旁路是否可能改变服务保障？ | Eaton《BladeUPS 12 kVA Maintenance Bypass Cabinet Installation and Operation Manual》P-164000130 Rev 1，§4.2 说明维护旁路期间负荷可以继续由市电供电，而 UPS 保护暂时不可用。这给出“仍有交付但保障状态改变”的设备级实例。Uptime Institute 对 Tier III 的并行维护定义也表明计划维护可以在维持运行的条件下完成。 | 旁路本身不能推出立即失电或固定比例的减载。维护影响取决于拓扑、需求及其他限制。本文保留零暴露和正暴露时实际损失仍为零的可能。[Eaton 手册 §4.2](https://www.eaton.com/content/dam/eaton/products/backup-power-ups-surge-it-power-distribution/backup-power-ups/bladeups/eaton-bladeups-maintenance-bypass-cabinet-installation-operation-manual-164000130.pdf) · [Uptime 的设施分级定义](https://uptimeinstitute.com/tier-certification) |
| 为什么检查许可、执行身份与恢复时序？ | 维护作业的授权、能源隔离及确认在公开作业规程中有独立用途。本文用许可窗口和执行绑定的复核表达这些约束。 | 不能从设备手册或规程推出所有设施共享 180 秒排他间隔，或把合成例中的远程写入当作现场操作指引。[公开规程的程序说明](https://www.osha.gov/etools/lockout-tagout/tutorial/energy-control-program) |
| 为什么 v3 引入直接处置的下行代价？ | v2 面板里 B 在 72/72 行已达合法服务下界。研究者看见这一退化情形后才改机制。v3 规则先登记，后产生 v3 开发结果，再做留出确认。原 v2、v3 三档时长及 S0 反例均保留。 | 实际执行发生且按该世界的实现判为不需要时，才触发有限支撑。支撑上限 0.50、0／600／1,200 秒时长、180 秒间隔和等额配额均为**合成设计假设**。公开文献支持机制可能存在，不能校准这些数值或保证其他设施具有同样效应。[最初登记](https://github.com/DonsonHH/AegisDC/blob/93077fb27f60b3205bdd634be942329ab05c5204/docs/mainline/t4c-action-cost-v3/protocol.md) · [实际触发条件](https://github.com/DonsonHH/AegisDC/blob/16b2ca5978d042a4dced9d655cfa181e0832bde2/docs/mainline/t4c-action-cost-v3/plant_cost.py#L18-L47) · [v2 达界与 v3 的结果](https://github.com/DonsonHH/AegisDC/blob/16b2ca5978d042a4dced9d655cfa181e0832bde2/docs/mainline/t4c-action-cost-v3/README.md#L21-L39) |

**剩余的识别边界。** 已有 v3 确认支持预先规定的合成机制和分布。S0 同时改变两个物理条件，不能单独识别旁路时长或许可恢复间隔的效应；本次 OAT 改的是策略设置，也不能代替独立场站验证。如果以后取得带分母的维护日志、实际旁路持续时间、关键负荷和批准时刻，才可校准频率与后果模型。

**实际意义的量纲。** 原确认 H2 的 55.83 缺额秒约占 3,600 秒整窗的 1.55%，同期人员均值约多 21.35 人秒；后一项按已发表、已舍入的 128.92 与 107.57 作差。“整窗占比”针对模拟需求归一化积分，不能换算成现场可用率、年停机时间或经济收益。[原确认量与单位](https://github.com/DonsonHH/AegisDC/blob/361574a049f0cfbf816f62af92ff5fd398d77ae8/docs/mainline/t9-submission-r1/manuscript.md#L77-L98)
