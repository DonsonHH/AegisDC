# 39r · 真实设施数据：公开候选与现场配对缺口

核验日期：2026-11-11。优先选 **ORNL Frontier** 校验设施电热量级和热量平衡，再选 **CINECA Marconi100** 检查同站多源证据及人工摘除标记。以下均为各自设施的数据；保留独立的站点、时间、设备和来源身份。当前现场标定仍为 `PENDING`。

后续完成：[Frontier 实测小样与全年时钟审计](20261111-frontier-field-pilot/README.md)。已从 v4 原件核对列和时间，保留实际缺行与时标偏离的区别。这里的表保存初次查源时的访问记录。

| 优先级 / 实际设施 | 入口与核验状态 | 字段及可支持的用途 | 证据边界 |
|---|---|---|---|
| **1. ORNL Frontier（2023）** | [原论文及测点表](https://doi.org/10.1038/s41597-024-03913-w)；[Figshare v4](https://doi.org/10.6084/m9.figshare.24391240.v4)；[官方文件](https://ndownloader.figshare.com/files/47812750) 匿名范围 GET 返回 206／8 字节，[ZIP 入口](https://ndownloader.figshare.com/articles/24391240/versions/4)也通过了首字节探针。[原仓 v4 元数据](https://api.figshare.com/v2/articles/24391240/versions/4)为 CC BY 4.0，`Frontier HPC & Facility Data.xlsx` 20,164,974 B，登记 MD5 `f1832f7215e529f12f38d4087620d6e2`；尚未取整件复验。 | `Frontier2023` 有时标、三个二次冷却支路的供回液温度和体积流量、超算和附属系统功率；`Readme` 是列说明。余热和 PUE 是计算列。适合独立约束设施电力、流量、温差与带走热量的量级。 | 论文记录 2023 全年、发布间隔 10 分钟、约 440 小时缺失；同文称 Metasys historian 存储间隔 15 分钟，取数后应核对工作簿时间轴和重采样，缺失不能当停机零值。表覆盖三个运行支路，未含第四备用支路的动态验证。[另发的 Frontier 作业遥测](https://doi.ccs.ornl.gov/dataset/2cfa2292-3f9d-549c-b2d2-c9aff1557218) 为 2024–25 年选定日期，不能与 2023 设施表拼成同次事件。 |
| **2. CINECA Marconi100（2020-03 至 2022-09）** | [原论文表 1 与引用 14–25](https://doi.org/10.1038/s41597-023-02174-3) 列出 12 批按月原包；[2022-07 原包](https://zenodo.org/records/7590565) 31.4 GB，[原仓元数据](https://zenodo.org/api/records/7590565) 显示开放、CC BY 4.0。只核验目录与字典；[7541722](https://zenodo.org/records/7541722) 是 15 分钟聚合的节点 IPMI/Nagios 子集，设施点位应查原包。 | Parquet 按月 / 插件 / 测点分区，多数表为 `timestamp`,`value` 加设备标识。[Schneider](https://gitlab.com/ecs-lab/exadata/-/blob/main/documentation/plugins/schneider.md)：后门换热回路 `Portata_1`、`T_mandata_hmi`、`T_ritorno_hmi`、泵运行与阈值告警，字典标称 20 秒。[Logics](https://gitlab.com/ecs-lab/exadata/-/blob/main/documentation/plugins/logics.md)：配电盘/设备标识、三相电压电流、有功功率及通信状态。[Vertiv](https://gitlab.com/ecs-lab/exadata/-/blob/main/documentation/plugins/vertiv.md)：空调供回风温湿度、设定值与状态。[Nagios](https://gitlab.com/ecs-lab/exadata/-/blob/main/documentation/plugins/nagios.md) 状态与 [Slurm 作业表](https://gitlab.com/ecs-lab/exadata/-/blob/main/documentation/plugins/job_table.md) 可约束同站热、电、负荷、告警之间的时序。 | `nagiosdrained` 表示该告警关联节点被操作员手动摘除，是后续可核查的动作代理；告警采集/更新时标不等于实际摘除时刻。没有检查结论、授权、人工耗时或恢复核验。测点在各月的覆盖不同；同一 PLC 经两块 HMI 导出的镜像或派生值应保留共同来源。字典的配电/节点电源字段不能证明 UPS 转供或电池荷电状态。 |
| **3. NLR（原 NREL）ESIF HPC 电力与 PUE** | [NLR 数据目录](https://doi.org/10.7799/3015212) / [OEDI 8616](https://data.openei.org/submissions/8616)，公开 CC BY 4.0，Parquet / ZIP CSV。OEDI 页面与字段可读；文件旧域名未解析，新域名 Parquet 探针返回 503，本次未取到文件。 | 电表 `ts`,`it_power_kw`,`cooling_kw`,`hvac_kw`,`pump_kw`,`plug_and_light_kw`,`pue`,`energy_reuse`，另有气象 `ts`,`outside_air_temp`（°F）、`outside_air_humidity`（%RH）。适合分项用电与天气的对照；文档明确塔过滤泵约 2.67 kW 计入 `cooling_kw`，不能再计入 `pump_kw`。 | 泵耗电不是流量，照明插座项内的备用发电机曲轴箱加热功率也不表示发电机启动。目录未列供回液温度、UPS、人工操作或关键服务结果；采样和覆盖待取得文件后核验。 |
| **4. NREL ESIF HPC 冷却余热（2016-09 至 2017-08）** | [数据发布者 GitHub](https://github.com/M-D-Murphy/Data-Centre-Waste-Heat) 提供每月 CSV，可匿名获取，未见明确数据许可；核到 [2017-03 CSV 表头和前几行](https://github.com/M-D-Murphy/Data-Centre-Waste-Heat/blob/main/NREL_HPCDC_201703.csv)。 | `Time`，空气/液冷两组 `T_supply`,`T_return`（°C）、`Q_flow`（kW）。可做设施热功率和供回温分布的旁证。 | README 写 1 分钟，2017-03 文件开头实际隔 5 分钟；需逐月核验。`Q_flow` 为热功率，不能当体积流量。与同站 PUE 数据分别发布，未证实同期或测点可配对。 |
| **5. ORNL Summit（2020–2022 选定月份）** | [Constellation DOI](https://doi.org/10.13139/OLCF/1861393)、[公开赛说明](https://smc-datachallenge.ornl.gov/2022ch7hpc-power/) 和 [字段字典](https://github.com/at-aaims/summit_power_and_thermal_data)。[官方指南](https://smc-datachallenge.ornl.gov/wp-content/uploads/2022/05/Constellation_Downloading_Guide_v02.pdf) 要求 Globus 登录/端点和 Constellation 注册；未下载，公开登记未列明确数据许可。 | `timestamp`,`hostname`,`ps0_input_power`,`ps1_input_power`、CPU/GPU 功率、芯温与显存温度，发布 10 秒 / 1 分钟均值；适合节点功热响应对照。 | 本包的 PSU 是节点电源，赛题冷却水流量为模型假设。[SC21 作者附录](https://github.com/at-aaims/sc21_summit_power_analysis_artifacts#dataset-12) 另述冷站 `mtwst`,`mtwrt` 与主开关板电表；本次没有核到这些独立文件的可下载入口。 |

**使用边界。** 现场测量可约束相应物理域和观测过程。采样时标、决策可见时标与实际动作时标须分别记录；温度回落或告警清除不能单独证明人员检查、授权、复原作业或服务恢复。保留郑州参照的合成设施身份；不同设施及非同期发布只分别用于校准或外部对照。

## 运维事件与配对线索

| 来源 | 真实记录与可用字段 | 现在可做的判断 |
|---|---|---|
| [NERSC OMNI 运营团队论文，§4.4 与图 7](https://www.nersc.gov/assets/OTG-files/EE-HPC-SOP-2019.Bautista.final.pdf) | 一个同设施案例：2018-12-31 电气事故触发保护停机，人员在安全许可后检查，监控与 BMS 记录解释温升；报警复位和恢复空调涉及分别具备权限的人员。正文与图公开。 | 这给出了电气、冷却、空间和授权的同一事件链。公开论文没有可逐条对齐的工单与原始轨迹，不用来估成功率、检查耗时或净收益。 |
| [Rabobank BPI Challenge 2014](https://data.4tu.nl/collections/_/5065469/1) · [主办方字段说明](https://ais.win.tue.nl/bpi/2014/quick_reference_bpi_challenge_2014.pdf) | 来自同一 ICT 运维系统的来报、事件、事件活动和变更。`Incident ID`、`Interaction ID`、`Change ID` 与配置项可建立部分关联；活动有组别和开始时戳，变更有计划及实际开完工时间、`CAB-approval needed`。目录可访问，[变更记录登记](https://api.datacite.org/dois/10.4121/uuid:d5ccb355-ca67-480f-8739-289b9b593aaf)为 4TU 通用使用条款。 | 可检验事件去重、工单链和计划／实际时钟。`CAB-approval needed` 只是需审批标志，不是实际许可；没有同设施流量、电力、独立故障真值和物理复检。 |
| [UCI ServiceNow 运维事件](https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log) | 匿名真实日志，141,712 条事件、24,918 个事件实例，36 字段，CC BY 4.0；ZIP 入口 HTTP 200。含报障、创建／更新／解决／关闭时戳，受影响配置项、派工组、重开与变更请求；有缺项和重复行。 | 可检验工单到达、转派、重开与关闭的记录方式；结束时间不当作恢复验证，也不当作人员占用时长。没有对应设施遥测。 |
| [LANL HPC 故障目录](https://usrc.lanl.gov/data/failure-data.php) · [USENIX CFDR 说明](https://www.usenix.org/cfdr-data) | 实际 HPC 节点停机起止、匿名系统与节点及原因类目，包括电力、空调、网络。官方列出公开研究使用及致谢要求；本次直连文件入口未验证。 | 可作 HPC 故障／中断时间的历史对照；只有需管理员处理的中断，不能当作全部检查机会、现代站点的 UPS 退出先验或到场时间。 |

UPS 还有两个真实数据线索：[腾讯 VRLA 电池研究](https://hub.hku.hk/handle/10722/365512)使用生产站点电池监测，[Schneider UPS 维护研究](https://ieeexplore.ieee.org/document/11148246)使用 CRM 与服务完工报告。两者本次仅核到论文，未确认可取得原始记录。电池健康或维修分类本身也不等于“检修后是否恢复投入”。

## 建议的首个交付：一套实测曲线，一张配对缺项表

1. **先用 Frontier v4 做实测对照。** 云端获取单个 XLSX，核对字节数与原仓校验值；按 `Readme` 核对时间基准、相邻间隔、缺口和测点单位，再切出原文图 7 使用的 2023-01-08 作为可复核示例。交付同轴电力、分支流量与供回温差图及缺测统计。按发布口径复算 `ρ c_p Q ΔT` 只检查计算列与单位；与独立电表对照也只报告同窗量级及差异，不能把余热曲线当成第二个独立热量测点。示例日用于复核数据管线，不代表全年故障表现。
2. **同站点闭环优先查 Marconi100。** 先用字典和分区清单定一个共同月份，限制到水侧流量／温度、对应配电、告警及作业所需字段；核对站点、资产映射和时标。公开包如无可查的现场许可／复检表，就将 `nagiosdrained` 保留为动作代理。Rabobank 或 UCI 只用于另测工单关联规则；不能给 Marconi100 或 Frontier 补工单。
3. **若要进入现场决策验证，目标是一种工况的一份可关联摘录。** 同一匿名设施、资产或服务组、事件实例和时间基准下，保留检查前的独立状态及外生需求、检查机会与实际到达报告（包括未报告）、授权和资源占用、动作发起与完成或中止、截止前的独立复检与后果。正常机会也要纳入；未观测到结果留缺项或删失。先报告逐字段可用率和实际可配对数，再判断哪些参数可辨识。历史处置可能按严重性选择，只有观测到两种动作还不能给净收益；比较须另声明识别条件或冻结独立对照。

本轮仅核查公开目录、字段说明和小范围访问，没有取得配对原件，也没有填入 UPS／IT 参数。**B 可从公开实测开始；同站点检查、授权和复检的完整样本仍待确认。**

## Marconi100：约束耦合的下一道门

用 [Schneider](https://gitlab.com/ecs-lab/exadata/-/raw/main/documentation/plugins/schneider.md) 的面板／测点、[Logics](https://gitlab.com/ecs-lab/exadata/-/raw/main/documentation/plugins/logics.md) 的设备与电表键、[Nagios](https://gitlab.com/ecs-lab/exadata/-/raw/main/documentation/plugins/nagios.md) 的节点与告警标签、[作业表](https://gitlab.com/ecs-lab/exadata/-/raw/main/documentation/plugins/job_table.md) 的节点及作业状态寻找同窗机会。先核时区、实际重叠时间、回路和供电设备到节点的连接，以及记录何时对调度可见。作业表的开始／结束可能是预计值，须与作业状态核实；两块 HMI 的同源读数和事后写入的动作标记均不能充当新的到时证据。不同设备的曲线在同一时刻变化，只能作为候选线索。

要判断两项任务的可行顺序，至少还要有同事件的匿名资源标识、技能和工具、各自释放时间、通路／占用与持续时间、授权和截止。[两域约束的判法](../mainline/39r-six-domain-structure.md#两域联合先判可行顺序)可以在这些量有据时直接使用。公开字典没有核到班组、工作许可或运维截止字段；`nagiosdrained` 只给人工摘除标记，不能据此恢复派工顺序或证明冷却和电气人员是同一班组。下一步可先核分区的小样可取性，若班组记录仍缺，交付只能分为“同站实测锚定的机会”和“声明约束下的排程演示”。截至本次核对，还未下载 Marconi100 原包或确认一个可配对事件。
