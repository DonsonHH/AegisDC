# Frontier 与 El Capitan：设施工程主来源及巡检建模边界

调研日期：2026-11-03（Asia/Shanghai）。范围：公开的 ORNL/OLCF、LLNL、DOE 资料，以及 ORNL 作者论文原文和 HPE 技术文档。本文是设施抽象的证据笔记，未运行科研模型、仿真或实验；不是任何实验室的竣工图、运行规程或现场验收记录。

## 1. 首先更正名称和量纲

**El Capitan 位于 Lawrence Livermore National Laboratory（LLNL，劳伦斯利弗莫尔），不是 Los Alamos National Laboratory（LANL，洛斯阿拉莫斯）。** LLNL 官方说明其由 Livermore、Los Alamos、Sandia 三个 NNSA 实验室协作，使用者包括这三个实验室。协作关系不能改写为部署地点。[LLNL ASC：El Capitan，访问于 2026-11-03](https://asc.llnl.gov/exascale/el-capitan)

**Frontier 位于 ORNL 的 Oak Ridge Leadership Computing Facility（OLCF）。** ORNL 为其改造原 Titan 所在机房，并建设配套供电和机械设施。[OLCF：Powering Frontier，2020-09-23](https://www.olcf.ornl.gov/2020/09/23/powering-frontier/)

以下数值仅作为注明年代和边界的工程尺度参照，不能直接作为新环境的设定值：

| 对象与资料日期 | 来源实际描述 | 使用边界 |
|---|---|---|
| Frontier 机房及冷却厂，2021-09-29 | 机房基础设施支持超过 **40 MW 电功率**；冷却厂另有 **8 MW 电力**基础设施。[OLCF](https://www.olcf.ornl.gov/2021/09/29/stunning-specs-whats-inside-the-nations-first-exascale-supercomputer-facility/) | 基础设施能力，不是机器持续实测功耗。 |
| Frontier 机械厂，2021-09-29 | 支持约 **40 MW 计算热负荷**，报道给出可扩展至 **70 MW** 的设计说明。[OLCF](https://www.olcf.ornl.gov/2021/09/29/stunning-specs-whats-inside-the-nations-first-exascale-supercomputer-facility/) | 热移除能力与电力容量分别保留；扩展能力不是已安装运行能力。 |
| LLNL B453，2022 年 ECFM 完成资料 | 电力容量由 **45 MW 增至 85 MW**；液冷能力由 **10,000 refrigeration tons 增至 28,000 refrigeration tons**。[ECFM fact sheet，pp. 1–2](https://asc.llnl.gov/sites/asc/files/2022-09/ECFM-fact-sheet-v6_0.pdf) | B453 支撑多代、可同时容纳两台 exascale-class 系统的设施容量，不能归给 El Capitan 单机。 |
| El Capitan，2021-10-18 的部署预测 | 单机峰值电力需求估计 **30–35 MW**。[LLNL](https://www.llnl.gov/article/48101/powering-llnl-prepares-exascale-massive-energy-water-upgrade) | 历史预测；不是平均负荷、账单电量或当前连续实测值。 |
| El Capitan，未标注发布日期的调试海报，内容已包含 2024-02 里程碑 | 以 **35 MW** 计算热负荷及 **10,000 GPM** 配水能力说明机房下部设施。[LLNL-POST-2004490，p. 1](https://hpc.llnl.gov/sites/default/files/Comp-ERC-poster-deprater.pdf) | 调试工程描述；不由此反推所有工况的流量、温差或机柜功率。 |

MW 是功率；MWh 是能量；refrigeration ton 是制冷能力单位；EFLOPS 是浮点运算速率。它们不能互换。本文不以功率推算算力，也不使用不注明精度和测试口径的算力数值。

## 2. 可以直接支持的设施事实

### 2.1 Frontier：供电、机械设施与机柜连接

- **电力接入。** 2020 年完成约 **2.5 mile、13.8 kV** 的新增馈电线路，接自实验室附近变电站；线路通往 5600–5700–5800 计算设施区。该报道还说明新增机械空间由既有实验室空间改造而来，钢管将机械厂连接至数据中心。[OLCF：Powering Frontier，2020-09-23](https://www.olcf.ornl.gov/2020/09/23/powering-frontier/)
- **配电与承重。** 2021 年后续报道记载建筑内安装 **9 台、每台 4 MW** 的变压器；更新后的架空地板支持超过 **600 lb/ft²**，机柜重约 **8,000 lb**。这些量说明电气、土建与设备布置耦合，不能仅把机柜看作抽象算力节点。[OLCF：Stunning Specs，2021-09-29](https://www.olcf.ornl.gov/2021/09/29/stunning-specs-whats-inside-the-nations-first-exascale-supercomputer-facility/)
- **温水与泵、管。** 同一 2021 年报道记载约 **90°F** 的高温冷却水系统、约 **85,000 gallon** 系统水量、**4 台 350 hp 泵**（每台最高约 **10,000 GPM**），以及机械室至机房约 **500 ft、24 in** 管路。上述是报道的设计/安装参照，不能同时当作实际运行点。[OLCF：Stunning Specs，2021-09-29](https://www.olcf.ornl.gov/2021/09/29/stunning-specs-whats-inside-the-nations-first-exascale-supercomputer-facility/)
- **三段热路径。** ORNL 作者的 ExaDigiT 论文给出简化拓扑：冷却塔回路，经中间换热器连至设施泵回路，再经 CDU 换热器连至机柜回路。论文报告 **25 个 CDU、74 个机柜**；这些设备构成成组依赖，而非每柜独立散热。[Brewer et al.，2024-10-07，§III-C、Fig. 5](https://arxiv.org/html/2410.05133v1#S3.SS3)
- **控制耦合。** 同文描述 CDU 的压差/温度控制及塔、泵、换热器的分级投切；局部 CDU 扰动能够通过阀门和公共回路影响上游控制。其模型部分参数来自控制器，部分经遥测调参，因此“论文模型配置”需要与“全部现场参数”分开。[Brewer et al.，2024-10-07，§III-C5](https://arxiv.org/html/2410.05133v1#S3.SS3)
- **负荷动态。** 2020 年设计报道明确考虑数分钟内 **10 MW 或更大** 的热负荷变化；2026 年 ORNL 官方论文摘要进一步指出，设施冷却主回路响应可按分钟计，而组件热应力按秒计。这支持研究动态耦合，但没有给出可直接用于巡检的具体截止时间。[OLCF，2020-09-23](https://www.olcf.ornl.gov/2020/09/23/powering-frontier/)、[Grant et al.，2026-01-25，官方摘要](https://impact.ornl.gov/en/publications/providing-thermal-stability-for-an-exascale-supercomputer-a-case-/)

### 2.2 El Capitan / LLNL：电气公用设施、两类流体与调试

- **公用设施级电气架构。** 2021 年施工报道列出 **115 kV** 输电接入、新开关场、**2 台 40 MW** 变电站变压器、**13.8 kV** 开关设备、继电保护和馈线，以及计算设施内部的二次变电站。该项目还新增 **6 台、每台 3,000 refrigeration ton** 的冷却塔及配套管路、换热器、泵。[LLNL：Powering up，2021-10-18](https://www.llnl.gov/article/48101/powering-llnl-prepares-exascale-massive-energy-water-upgrade)
- **交付后的分配及监控连接。** ECFM fact sheet 列出空气开关、继电控制间、**13.8 kV 二次馈线**及 B453 内部 **13.8 kV–480 V** 配电；**30 in** 工艺冷却管延伸至 B453，新 ECFM 控制系统接入 B453 楼宇管理系统（BMS）。这是站外公用设施、楼宇设施和机器之间存在接口的直接证据。[LLNL ECFM fact sheet，2022 年版，p. 2](https://asc.llnl.gov/sites/asc/files/2022-09/ECFM-fact-sheet-v6_0.pdf)
- **机房内安装边界。** LLNL 调试海报列出 **4 ft 架空地板、20 in 管道、10,000 GPM**；调试任务包括管路漏水/压力测试、CDU 配水平衡、冷却塔控制远程功能测试，以及公用事业负荷预测。海报说明使用过 **5 MW 负载箱**做局部负荷模拟并外推，不能写成已以完整 35 MW 热负荷完成全部调试。[Chris DePrater，LLNL-POST-2004490，p. 1，发布日期未标明](https://hpc.llnl.gov/sites/default/files/Comp-ERC-poster-deprater.pdf)
- **运行所需冷却组件。** LLNL 2026 年说明明确列出冷却塔、冷水机组、泵、换热器、传感器及超过 **2,000 ft** 管路；使用处理水与 glycol 基冷却液两个回路（未披露具体二醇种类），并以 ECFM 冷却塔蒸发散热为主要排热方式。文章还描述约 **400 kW/机柜** 的密度。[LLNL：How El Capitan keeps its cool，2026-06-03](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool)
- **工作负荷—传感—保护。** 同一官方说明称温度、流量和压力持续监测，以响应工作负荷造成的快速电力变化；保护机制可减载或安全停机。公开报道未给完整控制图、阈值、延时或保护逻辑，不能从这段文字编造某个异常必然导致全机停机。[LLNL，2026-06-03](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool)
- **楼宇空间。** LLNL 官方 Facilities 页面说明 B453 有 **48,000 ft²** 机房面积和机械系统；当前页面同时保留旧 **45 MW** 介绍与上部 ECFM 完成后 **85 MW** 说明。应优先按明确年代的升级段落及 fact sheet 使用，不能把同页所有数字拼成同一时点配置。[LLNL ASC Facilities，访问于 2026-11-03](https://asc.llnl.gov/facilities)

### 2.3 HPE 产品资料可以支持什么

HPE EX QuickSpecs 描述液冷冷板、机柜及 CDU 的接口。CDU 包含换热器、循环泵、控制阀、传感器、控制器和管路，并维持设备回路温度高于房间露点以避免凝露。此处的 primary/secondary 是产品与设施接口命名，不能直接等同于每篇实验室论文的回路序号。[HPE EX QuickSpecs，页面变更表最新版本 22：2026-09-21，CDU 部分](https://www.hpe.com/us/en/collaterals/collateral.a00094635enw.html)

HPE 硬件管理指南还给出产品级启动依赖：先使 CDU 健康，再接通液冷机柜 PDU；环境条件正常且收到管理命令后才启用机箱高压直流。这是可用于抽象“供电与冷却共同许可”的设备规则示例，**不是 Frontier 或 El Capitan 的现场配置确认**。[HPE Cray EX Hardware Management Administration Guide 1.4，S-8015，Power On Compute and IO Cabinets，页面无单独日期，访问于 2026-11-03](https://support.hpe.com/hpesc/public/docDisplay?docId=a00115093en_us&docLocale=en_US&page=Power_On_Compute_and_IO_Cabinets.html)

## 3. 模块、源证据与可建模之处

本表后两列均是**建模建议/待定参数**，不是官方系统设计结论。建议在资产依赖图之外单独建立可行走图；变电站、厂房、机房之间存在工程连接，并不证明巡检员能沿着这些连接通行。

| 模块 | 有直接依据的源证据 | 可用于巡检模型之处（建议） | 仍未知、应参数化或暂不纳入 |
|---|---|---|---|
| 高压接入、开关场、降压 | LLNL 的 115 kV、13.8 kV 开关设备与变压器；[2021 施工报道](https://www.llnl.gov/article/48101/powering-llnl-prepares-exascale-massive-energy-water-upgrade) | 作为上游共享资产；将电气检查点与下游服务组关联。 | 单线图、保护整定、馈线归属、冗余与切换策略；不能由两台变压器推断 2N。 |
| 楼宇二次配电、机柜供电 | B453 的 13.8 kV–480 V；[2022 fact sheet](https://asc.llnl.gov/sites/asc/files/2022-09/ECFM-fact-sheet-v6_0.pdf)；Frontier 的建筑内变压器；[2021 OLCF](https://www.olcf.ornl.gov/2021/09/29/stunning-specs-whats-inside-the-nations-first-exascale-supercomputer-facility/) | 将变压器、配电柜、PDU/整流器视为不同资产类型，允许不同测量方法。 | 额定与实测区分、母联、回路映射、热点阈值、设备间距离。 |
| 冷却塔、环境排热、水处理 | LLNL 增建塔及蒸发散热；[2021](https://www.llnl.gov/article/48101/powering-llnl-prepares-exascale-massive-energy-water-upgrade)、[2026](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool) | 建立共享排热能力与环境边界；水质/散热异常可作为待验证事件类型。 | 当前塔/塔单元状态、补水、湿球温度、污垢、生物风险的实际时序与概率。 |
| 泵、阀与设施换热器 | Frontier 多级回路与受控投切；[ORNL 作者论文 §III-C](https://arxiv.org/html/2410.05133v1#S3.SS3) | 上游压力/流量变化影响多个冷却组；检查对象可为设备或测点。 | 泵曲线、阀特性、换热系数、设定值、故障传播延时。 |
| CDU 与机柜组 | Frontier 的 CDU 分组；[ORNL 作者论文](https://arxiv.org/html/2410.05133v1#S3.SS3)；LLNL 的 CDU 水量平衡调试；[海报](https://hpc.llnl.gov/sites/default/files/Comp-ERC-poster-deprater.pdf) | 把 CDU 与其服务机柜关联，研究检查共享节点能否解释多处告警。 | El Capitan 的 CDU 数量、每组机柜映射、备用泵策略、现场漏水与压力阈值。 |
| 房间环境与凝露边界 | HPE CDU 监测房间条件及露点约束；[产品 QuickSpecs](https://www.hpe.com/us/en/collaterals/collateral.a00094635enw.html) | 增加房间湿度/露点、供液温度两个可观测量，研究测量一致性。 | 两座设施实际湿度控制、传感器布点、露点安全裕度；产品规则不等于已部署参数。 |
| BMS、设备控制与数据采集 | ECFM 控制连接 B453 BMS；[fact sheet](https://asc.llnl.gov/sites/asc/files/2022-09/ECFM-fact-sheet-v6_0.pdf)；El Capitan 的温度/流量/压力监测与保护；[LLNL 2026](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool) | 区分真实设备状态、远程观测和现场确认；设置数据陈旧、传感器矛盾等实验条件。 | 通信拓扑、控制器容错、报警去抖、传感精度、采样和传输延时。 |
| 楼宇、房间和维护通路 | Frontier 旧机房改造；[OLCF 2020](https://www.olcf.ornl.gov/2020/09/23/powering-frontier/)；LLNL 机房下部设施；[调试海报](https://hpc.llnl.gov/sites/default/files/Comp-ERC-poster-deprater.pdf) | 自建示意区块及通路，使行走成本、访问权限与工序时间独立于资产依赖。 | 精确平面图、房号、通路、受限区域、可接近性与真实巡检耗时。 |
| UPS、BESS、柴油发电机等备用能源 | **本次已核验资料未建立“为 Frontier/El Capitan 计算负荷配置了何种 UPS/储能及覆盖范围”的直接证据。** | 初版保持为可选、未实例化模块；如需要研究，可显式标注为合成设施配置。 | 是否部署、仅覆盖控制/存储还是整机、容量、续航、切换、冗余。资料未提及不等于现场没有。 |

## 4. 面向按需巡检的最小抽象建议

以下均为研究设计建议，不是对两座设施运行方式的事实陈述。

1. **先建立三种关系。** 资产供能关系、资产排热关系、巡检员可通行关系分别存储。控制和观测边另加类型，避免把同一房间、同一回路、同一故障域视为同一概念。
2. **回路按语义归一。** 建议内部用“冷却塔侧—设施闭式侧—设备侧”描述功能；每条源证据另存其 primary/secondary/tertiary 原称。保留换热器这一隔离接口，不把不同介质混成单一水网。El Capitan 新闻的“两个回路”与 Frontier 论文的三段模型有不同描述边界，现有资料不足以逐一对应，不能强行补成相同拓扑。
3. **事件从观测量开始。** 可研究供回温异常、流量/压差偏差、设备状态与遥测矛盾、漏液告警、配电测点异常等事件。触发阈值、严重性、持续时间、确认方法和后果均需明确标作合成假设或经数据标定的参数。
4. **自动保护与人工确认分工。** 机器的秒级保护继续存在；巡检任务用于现场确认、定位、排除观测误差或检修前检查。分钟/秒尺度差异已有官方摘要依据，不能把巡检员赶到现场当成快速保护的替代机制。[ORNL 官方论文摘要，2026-01-25](https://impact.ornl.gov/en/publications/providing-thermal-stability-for-an-exascale-supercomputer-a-case-/)
5. **以一个可证伪问题开始。** 例如：“在声明的专业、工时和访问约束下，知道共享冷却依赖，是否能改善按需核查的确认结果与代价？”将依赖图知识作为单独对照因素；不要同时加入更多优先级规则、预测器和模型，把改善来源混在一起。

可作为初版的概念链条（**示意，不是现场竣工连接图**）：

```text
电网/变电站 → 开关及降压 → 楼宇配电 → 机柜供电 → 计算与网络设备
环境排热 ← 冷却塔/泵 ← 设施换热/泵 ← CDU/设备回路 ← 设备发热
                       ↑ 测量与控制反馈 ↑
                    BMS / 局部设备控制

巡检员沿独立通行图到达可访问测点，完成规定的确认动作。
```

## 5. 参数和证据仍待核实之处

- **设备计数不自动升级为完整配置。** ExaDigiT 原文给出 25 CDU、74 机柜，又用每组 3 机柜描述模板；不能简单相乘后宣称 75 个实际机柜。论文简化图、模型实例及实际填充需要分别记录。[2024 原文，§III-C1](https://arxiv.org/html/2410.05133v1#S3.SS3)
- **控制模型不等于控制规程。** ExaDigiT 的具体调参与假设不宜直接当成现场保护参数；其 PUE 计算范围还排除了低功率空气处理等辅助设施，不能无条件与全楼宇 PUE 比较。[2024 原文，§III-C5、§IV-1](https://arxiv.org/html/2410.05133v1#S4)
- **现有主来源未给真实巡检任务。** 公开资料说明资产、观测与调试，未充分公开巡检点表、到访周期、人工确认标准、任务耗时、故障率和告警—维修闭环数据。新环境必须把这些列为合成假设，不能宣传为复刻实验室运行。
- **系统水量不等于储能设施证据。** Frontier 报道的系统存水量不能据此认定配置了专门热储能罐，更不能认定配置了电池储能或 UPS；这些应分别找部署资料。
- **El Capitan 温度单位。** 2026 官方新闻写约“85 degrees”，正文未在该处显式给出温标。本笔记不把它默认为严格的 85°F 工程设定值；如需要温度参数，应进一步找技术规格或测点记录。[LLNL，2026-06-03](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool)
- **原始数据候选。** ORNL 作者的《Energy dataset of Frontier supercomputer for waste heat recovery》及其配套 Frontier HPC & Facility Data 可以作为后续负荷/流量/温度标定入口；本次核验到论文与数据 DOI，但 Nature 正文和 Figshare 直连受访问限制，未下载工作簿核对字段、版本或缺失区间，因此状态为 `pending_verification`，不据此给实验设定值。[论文 DOI，2024](https://doi.org/10.1038/s41597-024-03913-w)、[数据 DOI，v4，2024](https://doi.org/10.6084/m9.figshare.24391240.v4)

## 6. 主要来源登记与本次访问边界

| 来源 | 发布/版本日期 | 主来源身份及核验范围 |
|---|---|---|
| [OLCF — Powering Frontier](https://www.olcf.ornl.gov/2020/09/23/powering-frontier/) | 2020-09-23 | 实验室官方报道；正文已打开核验。 |
| [OLCF — Stunning Specs](https://www.olcf.ornl.gov/2021/09/29/stunning-specs-whats-inside-the-nations-first-exascale-supercomputer-facility/) | 2021-09-29 | 实验室官方报道；检索结果可读取完整相关正文，直接打开返回 403。具体数值是该年代报道，不是当前实测。 |
| [Brewer et al. — A Digital Twin Framework…](https://arxiv.org/html/2410.05133v1) | arXiv v1，2024-10-07；关联 SC24 DOI：10.1109/SC41406.2024.00029 | ORNL 作者原文；HTML 已打开，核验系统、冷却与控制章节。其模拟结果不充作巡检效果证据。 |
| [Grant et al. — Providing Thermal Stability…](https://impact.ornl.gov/en/publications/providing-thermal-stability-for-an-exascale-supercomputer-a-case-/) | 2026-01-25 | ORNL 官方论文登记及摘要，DOI：10.1145/3784828.3785159；仅按摘要使用响应尺度事实，未声称核验全文。 |
| [LLNL — Powering up](https://www.llnl.gov/article/48101/powering-llnl-prepares-exascale-massive-energy-water-upgrade) | 2021-10-18 | 实验室官方施工报道；正文已打开。 |
| [LLNL — ECFM fact sheet](https://asc.llnl.gov/sites/asc/files/2022-09/ECFM-fact-sheet-v6_0.pdf) | 2022 年版；PDF 列 CD-4 为 2022-05-05，URL 归档路径为 2022-09 | LLNL-MI/MISC-834245；两页 PDF 文本已核验。CD-4 里程碑和其他页面的“June 2022 completed”按各自语义保留。 |
| [LLNL — Commissioning Infrastructure for El Capitan](https://hpc.llnl.gov/sites/default/files/Comp-ERC-poster-deprater.pdf) | 原件未标明发布日期；内容包含 2024-02 里程碑 | LLNL-POST-2004490；单页 PDF 文本已核验。未以爬取日期冒充发布日期；图形位置与设备标签不用于还原平面图。 |
| [LLNL — How El Capitan keeps its cool](https://www.llnl.gov/article/54496/meet-machines-matter-how-el-capitan-keeps-its-cool) | 2026-06-03 | 实验室官方运行设施报道；相关正文已核验。 |
| [LLNL ASC — Facilities](https://asc.llnl.gov/facilities) / [El Capitan](https://asc.llnl.gov/exascale/el-capitan) | 页面无独立日期；访问于 2026-11-03 | 实验室官方概览；仅采用明确范围的地点、协作、楼宇与升级信息；页面中旧描述与新描述不合并。 |
| [HPE EX QuickSpecs](https://www.hpe.com/us/en/collaterals/collateral.a00094635enw.html) | v22，2026-09-21 | 厂商产品资料；CDU 与变更表正文已打开。只支持产品接口抽象，不证明两座设施使用当前版本全部配置。 |
| [HPE S-8015 — Power On Compute and IO Cabinets](https://support.hpe.com/hpesc/public/docDisplay?docId=a00115093en_us&docLocale=en_US&page=Power_On_Compute_and_IO_Cabinets.html) | 1.4；子页面无独立日期 | 厂商技术指南；检索结果中对应段落可读，直接页面为脚本式正文。仅作产品级依赖参考，未核对整本 PDF。 |
| [Sun et al. — Energy dataset…](https://doi.org/10.1038/s41597-024-03913-w) / [配套数据 v4](https://doi.org/10.6084/m9.figshare.24391240.v4) | 2024 | 作者原始论文与数据入口已定位；全文/工作簿尚未完成可重复读取，不纳入已标定参数。 |

所有现场配置的确认级别均止于公开资料。未提供的参数继续为 `unknown` 或 `pending_verification`；上述建议若进入配置文件，应明确标识 `synthetic_assumption` 和对应源证据，避免转述为实验室运行事实。
