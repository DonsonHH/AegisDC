# AegisDC

**算力设施风险评估与按需巡检研究。**

研究问题：在固定测点稀疏、信息不完整的设施中，怎样结合工程依赖、历史记录、人工报告和现场核查，选择值得检查的风险问题，并衡量检查及后续处置的价值？

## 当前主线

**[会后研究报告：设施架构、风险与180次注册仿真](paper/mainline-report-20261108/report.md)** · **[离线HTML（8图与内嵌数据）](paper/mainline-report-20261108/AegisDC-会后研究报告.html)**。以简短正文和对照表展示导师要求、实际结果及未测范围。

2026年11月9日已同步到[Lab第三项目页面](https://lab.donson.top/liquid-cooling/)：12张图、8张表与6份数据，保留旧报告、Datapath、ISA和HTTPS。暂存/源站/公网资源及跳转核验通过；浏览器预览连接超时，本次只完成静态响应式检查。用户总体审阅已收到，当前先完成[39a跨阶段复核及39b–39d前置补全](docs/reviews/20261109-user-review/response.md)，然后冻结39新协议；新增研究试验仍为0。见[实际发布记录](docs/mainline/evidence/lab-publication-20261109.json)。

截至2026年11月8日，01–35已按会后要求完成实质审计与必要修正，原定180次注册运行及第37项报告已接受。主要确认平均服务改善0.03515625秒，未达到0.25秒门槛，结论保持 **NO_PRACTICAL_GAIN**；四组稳健性没有显示稳定优势。本次在[38后的阅读检查点](docs/mainline/checkpoint38.md)收束：结构化AI选单具备独立比较条件，效果尚未测；原否决已按独立审查撤回并保留。39–42未完成，总目标不标完成。误报/漏报、提前预防、正式比较的验证关闭和现场标定仍待研究。

- [保留的35项阅读快照（15图、8组公式、参数筛选）](paper/mentor-review-20261108/report.md)。
- **[第36项：四组稳健性结果与新数据图](evidence/mainline/research/36-robustness/README.md)**，含全部16原件、配对CSV、失败/图形修订和复算工具。
- **[01–35会后要求审计与修正闭环](docs/mainline/audits/20261108-pre36/audit-report.md)**，区分符合、有限覆盖及尚未测量。
- **[第35项阶段报告：原目标、架构、数据与结论](docs/mainline/checkpoint35.md)** · **[离线HTML（9张图、4份CSV）](evidence/mainline/research/checkpoint35/AegisDC-35-阶段研究成果.html)**。HTML需下载后用浏览器打开，支持手机、大屏、图表放大和打印。
- [独立确认结果、三张数据图与原件](evidence/mainline/research/34-paired-analysis/README.md)：16个工况、六种方法，包含全部正值、反向值、零差异与无人工参照。
- [机制消融、两张数据图与原件](evidence/mainline/research/35-ablation/README.md)：8个独立工况、四个规划视图，分别报告线索、依赖后果和团队选项的服务作用及代价。
- [第31项开发结果、两张数据图与原始账](evidence/mainline/research/31-development/README.md)：六个工况、六种方法，主配对平均改善−0.0417秒；开发与确认分开统计。
- [完整设施闭环数据和八域架构图](evidence/mainline/engineering/27-root-acceptance/README.md)：服务恢复、人员处置完成和证据核验关闭分别记录。
- [第32项独立确认冻结及失败记录](docs/mainline/32-confirmation-freeze.md)：16个独立工况、96份输入，方法、指标、成本门槛和执行源固定。

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

- [v11会前报告](paper/supervisor-briefing.html)及[阅读索引](paper/README.md)：七章、31图、27表和图表说明；[v11历史HTML下载](https://lab.donson.top/liquid-cooling/history/20261103/report.bin)。Lab项目主地址现展示会后180次研究报告。
- [独立补充基准](evidence/supplement-study/README.md)：3个CVAE-U-Net、6个PPO、1080测试回合；同流温度误差改善与学习调度未超过名义FIFO的结果一并保留。
- [事件验证](evidence/event-validation/final/README.md)、[九规则负结果](evidence/response-defer/README.md)、[反馈研究](evidence/feedback-study/README.md)：协议、原失败及未成立的增益分别保留。
- [全部证据索引](evidence/README.md)：大体积逐帧原件按SHA索引保存在项目私有服务器；Git包含原件索引、明细、权重与实际执行源码等交付。[2026年11月9日空间清理记录](docs/maintenance/20261109-storage/README.md)说明远端完整性验证和本地保留范围。

旧Tour、实时观测及返回/重访假设属于会前问题定义。旧结果作为比较与复现材料保留，新问题的效果需另行验证。

## 新研究原型入口

完整设施主线现有[八域工程运行基线](docs/mainline/healthy-run-model.md)：电力/后备、两级水热与参考相变、IT服务、局部控制、访问和异质人员作业在同一场景中运行。[工程轨迹与图](evidence/mainline/engineering/03-root-demonstration/README.md)保存正常工况、外电中断/自动接管及专业作业时序。该早期工程基线及其M2数值资格属于历史验收范围；最新进度为1–38有限范围接受、39a跨阶段复核，见[progress](docs/mainline/progress.json)。

**M0–M4 已按各自有限工程范围接受**。[M1 原工程基线](evidence/mainline/engineering/M1-root-acceptance/README.md)、[M2 数值见证](evidence/mainline/engineering/M2-root-acceptance/README.md)、[M3 证据、风险与价值](evidence/mainline/engineering/20-root-acceptance/README.md)及[M4 正常与负例](evidence/mainline/engineering/28-root-acceptance/README.md)保留各自执行身份、原始失败和验收范围。[第29项联合工况](docs/mainline/29-root-acceptance.md)限定本轮模型工作域；[第30项注册协议](docs/mainline/30-registered-comparison.md)随后固定方法、独立单位和180次总预算。数值研究显式使用 `--model configs/full-facility-mainline-reserve-v6.json --step .01` 和新输出目录；兼容默认保持原样。

以下示例均在现有服务器执行：依赖下载、隔离环境准备和轻量状态读取按登录节点规则进行，仿真、风险计算、工程评价和重型验证通过Slurm作业。桌面仅做编辑、SSH、完整性核对、小文件同步和结果查看。远端不可用时停止并记录原因，不能自动改在本机计算。详见[远端计算与存储规则](docs/agents/compute-storage.md)。每次输出使用新目录。

```bash
python -m aegis_dc scenario
python -m aegis_dc simulate --model configs/full-facility-mainline-reserve-v6.json --step .01 --output runs/full-site-engineering-new
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

这些入口没有训练或LLM调用，也不控制真实设备；其中设施仿真和风险算例仍进行数值计算，按上述远端规则执行。算例参数和结果标为synthetic，不是FEMA官方设备分数或实测收益。

## 兼容执行与检查

以下为远端兼容入口：Python3.11+，依赖安装及工程校验在服务器按调度规则执行。现有包名和历史CLI保留兼容：

```bash
python -m patrol_rsi status
python -m patrol_rsi verify --output runs/verification-new
```

`status`读取会前状态，`verify`执行工程/证据校验；没有自动训练或LLM调用，计算校验仍须远端执行。`demo/explain/respond/study`等历史命令的用法保留在[归档README](https://github.com/DonsonHH/AegisDC/blob/pre-meeting-20261103/README.md)。不要将兼容CLI的默认Tour理解为新主线。

1–38已按各自有限范围接受，研究结论以冻结协议和保存原件为准。2026年11月9日收到用户总体审阅，当前39a先复核跨阶段覆盖，随后补全多系统问题/动态任务、业务端点和人员设备时间尺度，再冻结39的新比较。38已接受窄结构化AI因素的可检验性，AI／RSI效果仍未测，现场标定仍待完成。[审阅采纳与执行顺序](docs/reviews/20261109-user-review/response.md) · [主线进度](docs/mainline/progress.json)
