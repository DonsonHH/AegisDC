# 39r · 风险子问题的三档进度

原来的 `2/8` 风险、`1/8` 检查价值是有限量化模型的计数，不是现场就绪率。[风险目录](../../configs/full-facility-risk-scenarios-v1.json)将 cooling、power 两个主问题标为 `FINITE_CONDITIONAL_LAW`；其余六个为 `UNMODELED`。[审查入口](../../src/aegis_dc/risk_baseline.py)按每域主问题计数，检查价值只找到 cooling 一项。旧模型使用声明的合成条件律，本来就不以取得现场先验为前提。其计数保留，新增进度另按下列三列报告。

| 档位 | 升级条件 | 不代表什么 |
|---|---|---|
| 结构就绪（子问题模型定义完成） | 状态、资产、观察窗和单位明确；四类动作与授权／资源／截止门、未解决及失败分支完整；给出条件损失、端点和可比域。未知参数可为 `null`，此时不输出数值判断。接受的有限合成设定也可满足这一档。 | 不是完整事件概率律，不等于检查有正值，也不等于现场就绪。 |
| 有限工程资格 | 对实际声明的范围有匹配后果或接口见证；输入差分、执行源码、原件哈希、时间与单位可核对。逐项列明已核的后果、状态来源、到时报告或动作效果；不把一个见证扩成整条链通过。 | 旧原件回读不算新试验；后果与信号有据不自动补齐误差、时延、恢复扰动或成功率。 |
| 现场就绪 | 具体资产与工况的证据、合法动作、到时记录、误差／报告性能、后果与有效恢复均有依据；代价口径和资源上限明确，工具需要的输入与模型适用条件已核。若要在某个实际先验点判胜，还需该先验的依据。 | 仅有现场先验不足以就绪；跨所有先验成立的条件结论不强求一个无关的先验点值。工具不代为授予权限。 |

## 当前按子问题报告

“结构就绪／有限工程资格／现场就绪”沿用[词汇表](../../GLOSSARY.md)的名称；配置上限和运行时有效容量是设施量，不是资格档位。

方向审阅确认八域已有定义；UPS 与 IT 有限工程资格保持。新增 [Frontier 功率与冷却实测](../research/20261111-frontier-field-pilot/README.md)是外部物理参照，不给六个新增子问题授予动作资格或现场就绪。

| 主域／子问题 | 结构就绪 | 有限工程资格 | 现场就绪 | 已核证据 |
|---|---|---|---|---|
| 后备／UPS复役 | 条件树和可比域已写明，已有解析边界 | 投入位、合成授权动作与辅助后果有有限见证；现场时钟和实际收益未核 | 未就绪 | [A2](../../evidence/mainline/engineering/39r-ups-a2/result.json)：投入位读取、授权恢复、过期拒绝；[B1](../../evidence/mainline/engineering/39r-ups-b1/result.json)：配对辅助断供各0.2／28秒。 |
| IT／网络有效服务容量 | 四动作、符号端点与观测分母已写明；`a,b,q_I,q_R,d_R` 等留空 | 历史匹配后果与保存点语义已核；到时测量误差和恢复成效未资格 | 未就绪 | [slice-18 后果](../../evidence/mainline/engineering/39r-it-dependence-reuse-v1/result.json)：配对缺额0／4.5秒；[信号回读](../../evidence/mainline/engineering/39r-it-network-signal-readback-v1/result.json)：23号动作后同刻1／1/4，04号固定上限1且无网络恢复动作时读数1→0→1。 |
| 供配电／整流段供能不足 | [结构已审](39r-six-domain-structure.md#1-供配电整流段供能不足) | 新四动作无匹配对照 | 未就绪 | [既有配电见证](power-verification.md)：输入、转换、交付分列；[原有限风险律](../reviews/20261110-direction-correction/risk-baseline.md)保留。 |
| 设施冷却／取水流量不足 | [结构已审](39r-six-domain-structure.md#2-设施冷却同工况下取水流量不足) | 原算例保留；新切分与分支未资格 | 未就绪 | [既有水力见证](water-verification.md)：流量、阀与供能路径；[原冷却价值算例](../reviews/20261110-direction-correction/risk-baseline.md)仍按原窗口解释。 |
| 设备环境／室温作业门 | [结构已审](39r-six-domain-structure.md#3-设备环境室温限制使作业点不可用) | 新子问题无匹配对照 | 未就绪 | [环境工程见证](environment-verification.md#independent-access-permission-and-unsafe-work)：温度门升／降越界和等时规则。 |
| 控制监控／监督链路与指定证据 | [结构已审](39r-six-domain-structure.md#4-控制监控指定证据在监督链路中断时能否到达) | 证据路由与到时后果未资格 | 未就绪 | [本地控制见证](local-control-verification.md)：监督丢失时本地自治；[证据契约](16-observation-contract.md)另定到达时标。 |
| 空间保障／积水阻断路线 | [结构已审](39r-six-domain-structure.md#5-空间保障积水导致通往-it-作业点的路径不可用) | 新四动作无匹配对照 | 未就绪 | [环境工程见证](environment-verification.md#independent-access-permission-and-unsafe-work)：积水、许可与温度门独立，阻断与作业中止有记录。 |
| 人员工具／冷却人员与流量仪预留 | [结构已审](39r-six-domain-structure.md#6-人员工具所需合格人员和流量仪能否同时预留) | 新四动作无匹配对照 | 未就绪 | [既有作业契约](21-workforce-contract.md)：同时预留、逾期和不可双占，旅行／等待／作业人秒分列。 |

结构和工程可以在明确合成假设下推进。若要升级旧的有限量化计数，需对相应主问题实际交付可运行的事件／后果条件律或价值模型，并通过其声明范围的门槛；仅有模板、四动作符号或 `null` 不改 `quantification`。每次交审把三档状态和已核证据分列；仅新增观测设计不提高工程档，原数量口径不被替换。[公开实测来源与同站配对要求](../research/20261111-field-data-candidates.md)另列；候选来源不计现场就绪。
