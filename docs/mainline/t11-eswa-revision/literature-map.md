# ESWA 修订候选文献地图

50 篇具有唯一 DOI 的候选作品中，43 篇的登记出版年在 2022–2026 年，8 篇发表于 *Expert Systems with Applications*。截至 2026-11-27，逐篇取得 Crossref 的题名、作者、出版物和出版日期，并从 DOI Handle 独立取得有效出版去向。年份取登记的 `published`，保留卷期年与在线年可能不同的原记录。每篇只归入一个主题，表中“与本文的关系”是选用理由。此表用于遴选，不能据 50 条登记声称已系统综述全部工作。[逐条核验回执](doi-verification.json)

原稿 [2]、[3]、[4] 的方法比较另据作者或出版社摘要及原文核对。POMCP 的首篇会议论文通过会议官方原文单列；未向其补写未经验证的 DOI，也不计入这 50 篇。事故报告、维护手册、FEMA 文件及既有仿真报告规范保留各自的资料性质。[原始 POMCP 论文](https://papers.neurips.cc/paper_files/paper/2010/file/edfbe1afcf9246bb0d40eb4d8027d90f-Paper.pdf) · [形式化草稿](method-formalization.md)

## 检查、维护与信息价值（13 篇）

| 编号 | 年份 | 作者、题名与出版物 | 与本文的关系 | DOI |
|---|---:|---|---|---|
| V01 | 1966 | Ronald Howard．Information Value Theory．*IEEE Transactions on Systems Science and Cybernetics* | 定义观测价值应随决策及其后果改变，给同策略禁购消融提供解释框架。 | [10.1109/tssc.1966.300074](https://doi.org/10.1109/tssc.1966.300074) |
| V02 | 2016 | Milad Memarzadeh、Matteo Pozzi．Value of information in sequential decision making: Component inspection, permanent monitoring and system-level scheduling．*Reliability Engineering & System Safety* | 把部件检查、持续监测与系统排程放入序贯决策，可直接对照“先获得信息再安排作业”的结构。 | [10.1016/j.ress.2016.05.014](https://doi.org/10.1016/j.ress.2016.05.014) |
| V03 | 2020 | William Fauriat、Enrico Zio．Optimization of an aperiodic sequential inspection and condition-based maintenance policy driven by value of information．*Reliability Engineering & System Safety* | 按信息价值选择下一次检查或更换的时机，适合区分推迟检查与等候一份在途报告。 | [10.1016/j.ress.2020.107133](https://doi.org/10.1016/j.ress.2020.107133) |
| V04 | 2022 | Guang Zou、Athanasios Kolios．Quantifying the value of negative inspection outcomes in fatigue maintenance planning: Cost reduction, risk mitigation and reliability growth．*Reliability Engineering & System Safety* | 研究疲劳维护中阴性检查结果的价值，对应本文“读数支持免去一次写入”的正例。 | [10.1016/j.ress.2022.108668](https://doi.org/10.1016/j.ress.2022.108668) |
| V05 | 2022 | P.G. Morato 等．Optimal inspection and maintenance planning for deteriorating structural components through dynamic Bayesian networks and Markov decision processes．*Structural Safety* | 把动态贝叶斯网络与马尔可夫决策过程用于退化部件，提供比较状态估计和维护选择的参照。 | [10.1016/j.strusafe.2021.102140](https://doi.org/10.1016/j.strusafe.2021.102140) |
| V06 | 2022 | Nandar Hlaing 等．Inspection and maintenance planning for offshore wind structural components: integrating fatigue failure criteria with Bayesian networks and Markov decision processes．*Structure and Infrastructure Engineering* | 海上风机的疲劳失效判据连接观测与维护，可用来说明物理阈值和决策阈值需分别论证。 | [10.1080/15732479.2022.2037667](https://doi.org/10.1080/15732479.2022.2037667) |
| V07 | 2024 | Mayank Chadha 等．A value-of-information-based optimal sensor placement design framework for cost-effective structural health monitoring (with application to miter gate monitoring)．*Structural Health Monitoring* | 按信息价值选择结构监测传感器的位置，给固定测点与按需付费测量的区别提供参照。 | [10.1177/14759217241275643](https://doi.org/10.1177/14759217241275643) |
| V08 | 2023 | Wei-Heng Zhang 等．Quantification of the value of condition monitoring system with time-varying monitoring performance in the context of risk-based inspection．*Reliability Engineering & System Safety* | 研究监测性能随时间变化时的条件监测价值，适合定位本文对观测到达、失效和匹配参数的处理。 | [10.1016/j.ress.2022.108993](https://doi.org/10.1016/j.ress.2022.108993) |
| V09 | 2025 | Vladimir Ulansky、Ahmed Raza．A historical survey of condition-based maintenance models with imperfect inspections: Cases of constant and non-constant probabilities of inspection outcomes．*Reliability Engineering & System Safety* | 综述检查结果概率恒定与变化时的维护模型，帮助定位本研究冻结的观测误差假设。 | [10.1016/j.ress.2024.110544](https://doi.org/10.1016/j.ress.2024.110544) |
| V10 | 2022 | Nan Zhang 等．A condition-based maintenance policy considering failure dependence and imperfect inspection for a two-component system．*Reliability Engineering & System Safety* | 联合考虑双部件失效依赖和不完美检查，可用来说明共享来源的读数为何不能被当成独立观测。 | [10.1016/j.ress.2021.108069](https://doi.org/10.1016/j.ress.2021.108069) |
| V11 | 2023 | Jiantai Wang 等．An inspection-based replacement planning in consideration of state-driven imperfect inspections．*Reliability Engineering & System Safety* | 以状态驱动的不完美检查安排更换，提供对照来解释为何检查结果与后续行动应联合评价。 | [10.1016/j.ress.2022.109064](https://doi.org/10.1016/j.ress.2022.109064) |
| V12 | 2025 | Salih Tekin 等．Maintenance policies for protection systems with imperfect inspection and imperfect repair．*Reliability Engineering & System Safety* | 同时考虑保护系统的不完美检查和维修，适合区分“能观察”与“干预能成功”。 | [10.1016/j.ress.2025.110798](https://doi.org/10.1016/j.ress.2025.110798) |
| V13 | 2022 | Chaochao Lin 等．Optimal inspection of binary systems via Value of Information analysis．*Reliability Engineering & System Safety* | 以二元系统的信息价值选择检查，是本文短视后验决策对照的应用近邻。 | [10.1016/j.ress.2021.107944](https://doi.org/10.1016/j.ress.2021.107944) |

## 部分可观测维护与在线规划（14 篇）

| 编号 | 年份 | 作者、题名与出版物 | 与本文的关系 | DOI |
|---|---:|---|---|---|
| P01 | 1998 | Leslie Pack Kaelbling 等．Planning and acting in partially observable stochastic domains．*Artificial Intelligence* | 给出部分可观测决策和信念状态的经典表述，用于区分设施真值、信念与外部评价。 | [10.1016/s0004-3702(98)00023-x](https://doi.org/10.1016/s0004-3702\(98\)00023-x) |
| P02 | 2021 | C.P. Andriotis、K.G. Papakonstantinou．Deep reinforcement learning driven inspection and maintenance planning under incomplete information and constraints．*Reliability Engineering & System Safety* | 在信息不完整和资源约束下用深度强化学习安排检查维护，是原稿 [3] 及方法差异的直接参照。 | [10.1016/j.ress.2021.107551](https://doi.org/10.1016/j.ress.2021.107551) |
| P03 | 2006 | Levente Kocsis、Csaba Szepesvári．Bandit Based Monte-Carlo Planning．*Lecture Notes in Computer Science* | 给出树内访问与探索的 bandit 选择依据，冻结的有限预算树基线据此明确探索常数。 | [10.1007/11871842_29](https://doi.org/10.1007/11871842_29) |
| P04 | 2022 | Chunhui Guo、Zhenglin Liang．A predictive Markov decision process for optimizing inspection and maintenance strategies of partially observable multi-state systems．*Reliability Engineering & System Safety* | 部分可观测多状态系统的检查维护决策提供同一类问题在预测式 MDP 下的建模参照。 | [10.1016/j.ress.2022.108683](https://doi.org/10.1016/j.ress.2022.108683) |
| P05 | 2023 | Akash Deep 等．Partially observable Markov decision process-based optimal maintenance planning with time-dependent observations．*European Journal of Operational Research* | 研究有时间依赖观测的 POMDP 维护规划，与本研究分开记录采样时刻和报告到达直接相关。 | [10.1016/j.ejor.2023.05.022](https://doi.org/10.1016/j.ejor.2023.05.022) |
| P06 | 2023 | Ezra Wari 等．A Corrosion Maintenance Model Using Continuous State Partially Observable Markov Decision Process for Oil and Gas Pipelines．*Algorithms* | 连续腐蚀状态的管道维护 POMDP 提供状态表示参照，便于解释有限设计世界离散化的代价。 | [10.3390/a16070345](https://doi.org/10.3390/a16070345) |
| P07 | 2025 | Nozomu Ogura 等．Joint Optimal Policy for Maintenance, Spare Unit Selection and Inventory Control Under a Partially Observable Markov Decision Process．*Mathematics* | 把维护、备件选择和库存纳入一个部分可观测决策，说明资源状态可以进入可行行动集。 | [10.3390/math13030406](https://doi.org/10.3390/math13030406) |
| P08 | 2022 | Reza Mohammadi、Qing He．A deep reinforcement learning approach for rail renewal and maintenance planning．*Reliability Engineering & System Safety* | 铁路更新与维护规划的强化学习应用可用于讨论跨期维护选择与短许可窗的任务差异。 | [10.1016/j.ress.2022.108615](https://doi.org/10.1016/j.ress.2022.108615) |
| P09 | 2023 | Zhenggeng Ye 等．Joint optimization of maintenance and quality inspection for manufacturing networks based on deep reinforcement learning．*Reliability Engineering & System Safety* | 把制造网络的质量检查和维护联合优化，适合定位付费观察与执行行动联合派工的研究问题。 | [10.1016/j.ress.2023.109290](https://doi.org/10.1016/j.ress.2023.109290) |
| P10 | 2024 | Hengchang Liu 等．Maintenance optimization of multi-unit balanced systems using deep reinforcement learning．*Reliability Engineering & System Safety* | 多单元平衡系统的维护优化提供耦合约束参照，解释本文为何按共同服务计量多故障后果。 | [10.1016/j.ress.2023.109921](https://doi.org/10.1016/j.ress.2023.109921) |
| P11 | 2023 | Seyedvahid Najafi、Chi-Guhn Lee．A deep reinforcement learning approach for repair-based maintenance of multi-unit systems using proportional hazards model．*Reliability Engineering & System Safety* | 以比例风险模型研究多单元维修策略，可用来区分从寿命数据学习风险与情景后果仿真。 | [10.1016/j.ress.2023.109179](https://doi.org/10.1016/j.ress.2023.109179) |
| P12 | 2023 | Giulio Mazzi 等．Risk-aware shielding of Partially Observable Monte Carlo Planning policies．*Artificial Intelligence* | 在部分可观测蒙特卡洛规划中处理风险约束，说明树节点的合法行动筛选值得作为单独的资格要求。 | [10.1016/j.artint.2023.103987](https://doi.org/10.1016/j.artint.2023.103987) |
| P13 | 2025 | Yang You 等．Partially Observable Monte-Carlo Graph Search．*Proceedings of the International Conference on Automated Planning and Scheduling* | 研究部分可观测蒙特卡洛图搜索，为后续解释历史树重用或不重用节点的计算成本提供参照。 | [10.1609/icaps.v35i1.36129](https://doi.org/10.1609/icaps.v35i1.36129) |
| P14 | 2024 | Maddalena Zuccotto 等．Online model adaptation in Monte Carlo tree search planning．*Optimization and Engineering* | 研究蒙特卡洛树搜索中的在线模型适配，帮助界定本协议固定预测模型、只改变搜索方法的比较。 | [10.1007/s11081-024-09896-2](https://doi.org/10.1007/s11081-024-09896-2) |

## 数据中心、HPC 与设施数字孪生（10 篇）

| 编号 | 年份 | 作者、题名与出版物 | 与本文的关系 | DOI |
|---|---:|---|---|---|
| F01 | 2020 | Walid Mokhtar Bennaceur、Leïla Kloul．Formal models for safety and performance analysis of a data center system．*Reliability Engineering & System Safety* | 形式化分析供电、热和网络子系统依赖，限定本文可归于证据到达和作业执行的新增部分。 | [10.1016/j.ress.2019.106643](https://doi.org/10.1016/j.ress.2019.106643) |
| F02 | 2024 | Jian Sun 等．Energy dataset of Frontier supercomputer for waste heat recovery．*Scientific Data* | Frontier 的现场能量数据给出功率、温度及流量量级，可用于设施量纲检查。 | [10.1038/s41597-024-03913-w](https://doi.org/10.1038/s41597-024-03913-w) |
| F03 | 2024 | Wesley Brewer 等．A Digital Twin Framework for Liquid-cooled Supercomputers as Demonstrated at Exascale．*SC24: International Conference for High Performance Computing, Networking, Storage and Analysis* | ExaDigiT 提供液冷超算数字孪生与实机遥测的比较，提示现场验证还需要相应层级的数据。 | [10.1109/sc41406.2024.00029](https://doi.org/10.1109/sc41406.2024.00029) |
| F04 | 2026 | Ningbo Wang 等．Surrogate-assisted synergistic optimization of data center air-liquid hybrid cooling servers considering cooling power consumption and thermal reliability．*International Communications in Heat and Mass Transfer* | 数据中心气液混合冷却同时考虑功耗和热可靠性，可用于解释冷却侧服务与能耗目标的区别。 | [10.1016/j.icheatmasstransfer.2026.111683](https://doi.org/10.1016/j.icheatmasstransfer.2026.111683) |
| F05 | 2024 | Yihong Wang 等．Subsystem Reliability Analysis of Data Center Network BCube．*IEEE Transactions on Reliability* | BCube 网络的子系统可靠性分析是网络拓扑层参照，补足将网络一概视为单一容量的局限讨论。 | [10.1109/tr.2024.3381160](https://doi.org/10.1109/tr.2024.3381160) |
| F06 | 2022 | Abdullahi Sanusi、Ibrahim Yusuf．Reliability assessment and profit analysis of distributed data center network topology．*Life Cycle Reliability and Safety Engineering* | 以分布式数据中心拓扑评估可靠性与收益，提示服务缺额换算为经济量还依赖另外的收益模型。 | [10.1007/s41872-022-00186-3](https://doi.org/10.1007/s41872-022-00186-3) |
| F07 | 2024 | Haitao Zhu、Botao Lin．Digital twin-driven energy consumption management of integrated heat pipe cooling system for a data center．*Applied Energy* | 热管冷却系统的数字孪生能耗管理提供子系统运行参照，可与本文的跨系统工单比较应用范围。 | [10.1016/j.apenergy.2024.123840](https://doi.org/10.1016/j.apenergy.2024.123840) |
| F08 | 2024 | Yongping Huang 等．Experimental study on the immersion liquid cooling performance of high-power data center servers．*Energy* | 高功率服务器浸没冷却的实验属于设备级验证，适合说明哪些热响应假设最终应由仪器数据约束。 | [10.1016/j.energy.2024.131195](https://doi.org/10.1016/j.energy.2024.131195) |
| F09 | 2025 | Sikai Zou 等．Performance of a multi-cooling sources cooling system with photovoltaics and waste heat recovery in data center．*Energy Conversion and Management* | 多冷源数据中心的性能研究可作为运行组合参照，提醒设施可用能力受运行方式影响。 | [10.1016/j.enconman.2024.119319](https://doi.org/10.1016/j.enconman.2024.119319) |
| F10 | 2023 | Ranran Mi 等．Energy performance evaluation in a data center with water-side free cooling．*Energy and Buildings* | 水侧自然冷却的能效评估提供水冷设施运行背景，不能单独给出本文到场作业的频率。 | [10.1016/j.enbuild.2023.113278](https://doi.org/10.1016/j.enbuild.2023.113278) |

## 持续巡检、路线与资源调度（5 篇）

| 编号 | 年份 | 作者、题名与出版物 | 与本文的关系 | DOI |
|---|---:|---|---|---|
| I01 | 2026 | Alessandro Bucci 等．Cooperative multi-robot routing for AUV–UAV inspection with inter-vehicle synchronization．*Ocean Engineering* | 异类机器人协同巡检的同步要求可与本文人员／工具同时可用的约束相比较。 | [10.1016/j.oceaneng.2026.127392](https://doi.org/10.1016/j.oceaneng.2026.127392) |
| I02 | 2025 | Kaleb Ben Naveed 等．Adaptive ergodic search with energy-aware scheduling for persistent multi-robot missions．*Autonomous Robots* | 持续多机器人任务中的能量约束搜索提供巡检时序的近邻，评价目标可与服务缺额作维度区分。 | [10.1007/s10514-025-10215-6](https://doi.org/10.1007/s10514-025-10215-6) |
| I03 | 2025 | Mela Coffey、Alyssa Pierson．Persistent multi-resource coverage with heterogeneous multi-robot teams．*Autonomous Robots* | 异构多资源团队的持续覆盖适合解释访问能力与不同工种、工具可用性之间的关系。 | [10.1007/s10514-025-10207-6](https://doi.org/10.1007/s10514-025-10207-6) |
| I04 | 2022 | Jurgen Scherer 等．Min-Max Vertex Cycle Covers With Connectivity Constraints for Multi-Robot Patrolling．*IEEE Robotics and Automation Letters* | 连通约束下的最小最大巡检环覆盖，提供以访问周期为目标的清晰基准问题。 | [10.1109/lra.2022.3193242](https://doi.org/10.1109/lra.2022.3193242) |
| I05 | 2023 | Xiang Li、Yuxuan Ma．Analysis of Multi-Robot Patrolling Algorithms．*Journal of Physics: Conference Series* | 多机器人巡检算法的比较有助于交代回访策略谱系，并指出本文另需验证报告是否改变处置。 | [10.1088/1742-6596/2419/1/012100](https://doi.org/10.1088/1742-6596/2419/1/012100) |

## ESWA 上的直接应用近邻（8 篇）

| 编号 | 年份 | 作者、题名与出版物 | 与本文的关系 | DOI |
|---|---:|---|---|---|
| E01 | 2025 | Samuel Yanes Luis 等．Variational model-based Deep Reinforcement Learning for Non-Homogeneous Patrolling aquatic environments with multiple unmanned surface vehicles．*Expert Systems with Applications* | 原稿已引的水域持续巡检研究把未知重要度与主动重访联系起来，可在 ESWA 读者熟悉的问题上引出服务后果。 | [10.1016/j.eswa.2025.126483](https://doi.org/10.1016/j.eswa.2025.126483) |
| E02 | 2025 | De Zhang 等．A bi-level hybrid algorithm for solving multi-target inspection path planning problem of mobile robot in complex radioactive indoor environment．*Expert Systems with Applications* | 室内多目标机器人巡检路径的双层优化适合比较到达多个核查点的空间代价。 | [10.1016/j.eswa.2024.126095](https://doi.org/10.1016/j.eswa.2024.126095) |
| E03 | 2026 | Ruying Cai 等．Vision-based multi-site safety inspection path planning using multi-agent system in large-scale work environment．*Expert Systems with Applications* | 多场点视觉安全检查规划展示应用中的取证与路径联合决策，可对照本研究受权限约束的具名工单。 | [10.1016/j.eswa.2025.130663](https://doi.org/10.1016/j.eswa.2025.130663) |
| E04 | 2022 | Jianyu Su 等．Deep multi-agent reinforcement learning for multi-level preventive maintenance in manufacturing systems．*Expert Systems with Applications* | 多层预防性维护的多智能体强化学习提供跨维护层级决策的期刊内参照。 | [10.1016/j.eswa.2021.116323](https://doi.org/10.1016/j.eswa.2021.116323) |
| E05 | 2024 | Phuc Do 等．Multi-agent deep reinforcement learning-based maintenance optimization for multi-dependent component systems．*Expert Systems with Applications* | 多重依赖部件的维护优化是耦合设施决策的直接应用近邻，便于交代结构依赖和推理方法两方面的差异。 | [10.1016/j.eswa.2024.123144](https://doi.org/10.1016/j.eswa.2024.123144) |
| E06 | 2025 | Yanping Zhang 等．A system-centred predictive maintenance re-optimization method based on multi-agent deep reinforcement learning．*Expert Systems with Applications* | 系统层预测维护的再优化研究可对照系统目标与局部维护动作的关系。 | [10.1016/j.eswa.2025.127034](https://doi.org/10.1016/j.eswa.2025.127034) |
| E07 | 2025 | Aleksandr Dekhovich 等．Sequential wafer map inspection via feedback loop with reinforcement learning．*Expert Systems with Applications* | 用反馈循环安排逐步晶圆图检查，适合解释本研究为何评价下一份证据改变后续决策的能力。 | [10.1016/j.eswa.2025.126996](https://doi.org/10.1016/j.eswa.2025.126996) |
| E08 | 2024 | Haojun Teng 等．CMRS: A digital twin enabled workers recruitment and task scheduling scheme for future crowdsourcing networks under precedence constraints．*Expert Systems with Applications* | 带先后依赖的人员招募与任务调度作为人力可行性的应用参照，补充只讨论设备状态的文献。 | [10.1016/j.eswa.2023.122914](https://doi.org/10.1016/j.eswa.2023.122914) |
