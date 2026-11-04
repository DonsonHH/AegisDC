# AegisDC

**算力设施风险评估与按需巡检研究。**

研究问题：在固定测点稀疏、信息不完整的设施中，怎样结合工程依赖、历史记录、人工报告和现场核查，选择值得检查的风险问题，并衡量检查及后续处置的价值？

## 当前主线

用户已确认以完整设施持续推进。[固定总目标与阶段门槛](docs/MAINLINE.md)、[42项依赖任务](.scratch/full-facility-mainline/map.md)和[当前执行状态](docs/mainline/progress.json)共同承载主线：以郑州工程为参照建立可运行合成设施，接入多源证据和异质检查处置，以独立比较形成机制结论，再按资格推进智能体/RSI。

**设施建模 → FEMA框架参照下的情景与风险量化 → 按需检查/处置闭环 → 独立评价 → 智能体与RSI。**

- 不以全场固定路线或统一重访周期作为默认结构；行走路径与服务依赖分别建模。
- 主场景包含稀疏固定传感器，覆盖与可用性有限；允许历史巡检、人工工单与现场手持仪器证据。
- 先扩展配电/HVDC、UPS/电池、应急电源、冷冻/冷却、泵/换热、设备液冷、控制和IT服务等模块，再讨论策略复杂度。
- 风险有明确的情景、时间窗、单位、来源和不确定性；确认、处置和验证关闭分别记录。

依据：[会后决策与纪要差异](docs/meetings/2026-11-03-research-reset.md)、[研究定义与方法](docs/RESEARCH_RESET.md)、[领域术语](GLOSSARY.md)、[当前下一步](docs/NEXT.md)。用户口述与后续澄清优先于自动纪要。

会前整合、更名、会议决策和新原型的[交付复核](docs/reviews/postmeeting-20261104.md)附逐项完成审计、测试范围和远端发布收据。

## 工程与方法来源

三站独立的[拓扑、状态方程与参数资料包](docs/research/20261104/facility-cases/README.md)已整理：8幅原创架构图、103条参数/缺值记录、单文件离线HTML、CSV与可编辑台账。图中区分公开描述、设计、发表模型、厂家声明、研究提议和待补关系；具体来源/年代、初值与闭合缺口逐站列明。

[本轮资料包复核](docs/reviews/facility-cases-20261104.md)记录主来源/方法修正、两轴审阅、浏览器与远端验证；另有[离线ZIP](evidence/facility-case-models-20261104/facility-cases-study.zip)便于直接下载研究。

|参考|已取得什么|仍待核实什么|
|---|---|---|
|[ORNL Frontier / LLNL El Capitan](docs/research/20261103/us-supercomputing-facilities.md)|供配电、机械冷却、换热/CDU、BMS与机柜耦合的官方资料|真实巡检、冗余/切换、参数和故障分布|
|[郑州核心节点 / 曙光8000](docs/research/20261103/china-supercomputing-facilities.md)|央视四集条目、官方机电清单、HVDC与湖水换热设计|竣工拓扑、电池/冷机细节、运行及检查参数|
|[FEMA方法及设施改编](docs/research/20261103/fema-risk-framework.md)|危险源/资产/影响、情景能力与反馈过程；自有风险/检查价值定义|部分PDF完整归档、设施参数标定及真实收益验证|

El Capitan位于LLNL；LANL是协作方。郑州核心节点与纪录片中的曙光8000按同一工程的互补视角处理。工程容量、厂家声明、设计值和实际测量分别登记，不据此宣称复刻现场。

## 会前研究档案

全部会前分支历史已合入main，并固定为[pre-meeting-20261103](https://github.com/DonsonHH/AegisDC/tree/pre-meeting-20261103)。[复核记录](docs/reviews/premeeting-20261103.md)列出原件、预算、修复与范围。

- [v11会前报告](paper/supervisor-briefing.html)及[阅读索引](paper/README.md)：七章、31图、27表和图表说明；[线上快照](https://lab.donson.top/liquid-cooling/)。
- [独立补充基准](evidence/supplement-study/README.md)：3个CVAE-U-Net、6个PPO、1080测试回合；同流温度误差改善与学习调度未超过名义FIFO的结果一并保留。
- [事件验证](evidence/event-validation/final/README.md)、[九规则负结果](evidence/response-defer/README.md)、[反馈研究](evidence/feedback-study/README.md)：协议、原失败及未成立的增益分别保留。
- [全部证据索引](evidence/README.md)：大体积逐帧原件仍在本地runs，以SHA索引定位；Git包含原件索引、明细、权重与实际执行源码等交付。

旧Tour、实时观测及返回/重访假设属于会前问题定义。旧结果作为比较与复现材料保留，新问题的效果需另行验证。

## 新研究原型入口

完整设施主线现有[八域工程运行基线](docs/mainline/healthy-run-model.md)：电力/后备、两级水热与参考相变、IT服务、局部控制、访问和异质人员作业在同一场景中运行。[工程轨迹与图](evidence/mainline/engineering/03-root-demonstration/README.md)保存正常工况、外电中断/自动接管及专业作业时序。当前分阶段资格以新的 M2 根记录为准，风险证据与策略闭环继续按固定主线推进。

**M1 与有限 M2 已由根接受**：[M1 原工程基线](evidence/mainline/engineering/M1-root-acceptance/README.md)和[M2 数值图、正确架构及复核包](evidence/mainline/engineering/M2-root-acceptance/README.md)保留各自执行身份。M2 实际根源 bcac 的359项全执行零跳过、11组有限见证及重放契约已核对；事件侧指标、raw差异和各自参考阶梯分列。当前进入M3，主票14多源证据账待分配；完整研究目标仍active。数值研究显式使用 `--model configs/full-facility-mainline-reserve-v6.json --step .01` 和新输出目录，见复核包；兼容默认保持原样。

```bash
python -m aegis_dc scenario
python -m aegis_dc simulate --output runs/full-site-engineering-new
python -m aegis_dc status
```

第一版[设施结构与风险方法原型](docs/FOUNDATION.md)保留14个功能区、29个资产／服务对象及其代数风险算例，支持无固定测点的对照基线。当前完整 V6 主场景存在稀疏固定测点，并允许历史、人工、工单和手持证据；其 M2 运行资格与早期原型分层记录，现场标定和策略收益仍需后续独立验证。

已执行的[合成算例与复核快照](evidence/foundation-v0.1-20261104/README.md)包含CLI输出、源码/输入SHA和本地验收摘要。

```bash
python -m pip install -e .
python -m aegis_dc status
python -m aegis_dc foundation
python -m aegis_dc risk-demo --output runs/foundation-demo-new
```

这些入口不训练智能体、不调用模型，也不控制真实设备。算例参数和结果标为synthetic，不是FEMA官方设备分数或实测收益。

## 兼容执行与检查

Python3.11+，先`python -m pip install -e .`。现有包名和历史CLI保留兼容：

```bash
python -m patrol_rsi status
python -m patrol_rsi verify --output runs/verification-new
```

这两个命令读取会前状态或执行工程/证据校验，不自动训练或调用科研模型。`demo/explain/respond/study`等历史命令的用法保留在[归档README](https://github.com/DonsonHH/AegisDC/blob/pre-meeting-20261103/README.md)。不要将兼容CLI的默认Tour理解为新主线。

结构／风险原型、M1八域基线与声明有限范围的M2数值／重放门槛已交付。当前M3从主票14多源证据账继续；检查处置、独立比较及条件式AI/RSI仍在后续。详见[主线进度](docs/mainline/progress.json)，现场标定pending。原会议笔记、浏览器缓存、依赖和重复导出不进入公开仓库；本地文件不删除。
