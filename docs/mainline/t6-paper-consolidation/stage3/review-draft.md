---
title: 维护降级时，何时值得先核查？耦合算力设施中的服务、证据与行动
file: t6-manuscript
template: doc
theme: paper
lang: zh
---

## A 摘要

算力设施收到异常记录时，等待现场核查可以避免不必要的处置，也可能错过切换或修复的窗口。本文把供电、冷却、服务和现场作业放在同一套合成设施中。记录何时到达、人员何时可进场、处置何时生效，都与服务损失在同一时钟上核对。

强透明规则 B 可在许可下直接处置；风险驱动方法 V\*\* 还可选择先核查。在合成留出面板上，V\*\* 相对 B 的平均服务缺额差为 −343.90 秒。个别条件的缺额反而增加。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

伦敦式与荷兰式验证区分了两个问题：观测能否区分原因，取得观测后还能否及时行动。普通改进的公开选择器在开发板减少了缺额，在新板却高于冻结的固定策略。现有比较尚不能分离递归自改进给后续决策带来的增量。 [完整设施的方法和公开证据边界](https://github.com/DonsonHH/AegisDC/blob/0ca350d1cb54ecc20fd99db5d69167d886cdef34/docs/mainline/full-facility-method-handoff.md#L11) [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)

**关键词：** 算力设施；按需核查；受约束处置；服务缺额；条件化余量

## B 研究问题与计量

供电或冷却链上的异常会沿服务依赖影响计算、存储或通信，现场人员却未必能沿可通行路线及时抵达设备。研究的问题是：这时应先测量、直接申请处置，还是等待？设备真值留在设施与评价端。决策者可查公开作业目录，只接收已经到达的观测和工作回执。现场读数有时只能排除一种解释。

V\*\* 依据公开材料比较仍有支持的风险解释，估计核查会怎样改变后续行动，再在可行分支中派工。策略提出请求后，设施仍要核验许可、人员、工具和通行条件。完成处置后，还要等本次执行的复测和服务证据，才能把工单记为合法关闭。所有对照均保留设备内原有的自动保护。 [完整设施的方法和公开证据边界](https://github.com/DonsonHH/AegisDC/blob/0ca350d1cb54ecc20fd99db5d69167d886cdef34/docs/mainline/full-facility-method-handoff.md#L11)

主端点 L 是全窗归一化服务缺额：需求存在时，把每一时段未交付的服务比例乘以该时段长度，再相加。数值越小，表示同一需求下少损失了服务。同一条件的各策略独立运行。人员、工具和费用另行入账；省工不能冲抵服务损失。

下文以候选 L 减对照 L。负差表示候选少损失服务。合法全知排程遵守相同动作和资源约束，用于核实每个条件能达到的下界，其私有信息不进入实际策略。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md) [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

## C C1 按需核查降低了整板平均缺额，但不能逐条件替代直接处置

### 结论

在 T4b 合成留出面板上，风险驱动的 V\*\* 相对强透明规则 B 降低了平均 L。这就是预注册 H1 检验的命题，范围只到全板等权均值。B 在公开条件允许时可直接处置；P 只使用既有保护，周期巡检按排程检查，报警响应由已发布的报警触发。用它们作对照可以说明方法介于哪些现状做法之间，却不能替换 B 的主检验。 [T4b 预注册检验及对照](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4d-cost-baseline-v1/confirmation-protocol-v2.md#L7-L17)

### 数字

T4b 的 144 条条件全部成对。V\*\*−B 为 −343.90 秒，封存双侧区间为 [−445.94, −244.22] 秒，上界低于零。

与关闭自选初检的同一方法相比，差为 −55.83 秒；与成本感知透明规则 B_cost 相比为 −390.48 秒。原协议依次检验全板均值。分族结果只用来描述差异。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

| 描述性参照 | T4b 留出：V\*\*−参照（秒） | v3c 新板：V\*\*−参照（秒） |
|---|---:|---:|
| 仅既有保护 P | −711.96 | −551.78 |
| 周期巡检 | −447.89 | −302.97 |
| 报警响应 | −489.91 | −344.90 |

同样按全板均值，V\*\* 的人员占用相对巡检在留出板少 498.47 人秒，在新板少 492.08 人秒。新板没有 B 臂；V\*\* 相对 B_cost 的服务差为 −269.65 秒，只是补充比较。新板的预注册主问题是选择器 S 与冻结赢家 W 的差，并非在另一块板上重检 H1。 [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)

### 失效条件与反例

若把全板命题改为“每个条件都优于 B”，封存记录并不支持。在 T4b 中，V\*\* 对 B 为 54 优、76 平、14 劣。荷兰式族有 10 条劣行，均与错过预防性重分组窗口的记录对应。申请泵操作不能补回此前已损失的供电时间。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

冷却与通行族则说明省工与少失服务可以指向不同的策略。留出板上，V\*\* 相对巡检少用 256.04 人秒，平均 L 却增加 37.29 秒（1 优、20 平、3 劣）。新板同族相对巡检、报警均持平。

固定对照也并非处处占优：T4d 原开发条件中 B 有 18/72 条比 P 差；V\*\* 自身对 P 在留出板有 4 条、新板有 2 条更差。这些反例限定了适用条件，保留在比较的原分母内。 [成本基线的原开发板](https://github.com/DonsonHH/AegisDC/blob/036ccfdf2d6e5d4b39ba11da480fa2a3d69c1f9f/docs/mainline/t4d-cost-baseline-v1/README.md) [实际处置与严格劣行](https://github.com/DonsonHH/AegisDC/blob/ce3ee6303a81f99341d40796d499185e997238da/docs/mainline/t5-closeout/README.md#L9)

## D C2 事故机制在什么条件下会改变服务损失

### 结论

核查改变服务后果，需要证据到达后仍有可执行的处置。伦敦式工况中，移交后才能恢复隔离的备用路径。若控制器把上游有电误判为备用路径可供电，可申请修正共享判断或预启动机组。

荷兰式工况中，转供前减轻过载可减少供电损失，来电后恢复泵送可减少冷却损失。两类行动各有许可和窗口。Google 事后报告给出了故障链。现场能否提前识别并避免损失，仍未建立。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [伦敦事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L18-L32)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L43)

### 数字

T3 公开开发条件的平均服务缺额如下，单位为秒。全知排程仅供评价端确定同等许可下能达到的最低缺额。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

| 事故族 | 开发条件 | 仅既有保护 P | 周期巡检 | 报警响应 | 合法全知排程 |
|---|---:|---:|---:|---:|---:|
| 伦敦式 | 12 | 410 | 165 | 365 | 75 |
| 荷兰式 | 12 | 1045 | 865 | 1035 | 170 |

在另行留出的 T4b 条件上，下表给出风险策略 `V**` 减去透明直接规则 B 的服务缺额。负差表示少损失服务。分族结果是描述性比较，预注册主检验针对整板均值。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

| 事故族 | 配对条件 | 平均差（秒） | 原封存双侧区间（秒） | 较少／持平／较多 |
|---|---:|---:|---|---|
| 伦敦式 | 24 | −47.50 | [−150.00, +42.50] | 3／20／1 |
| 荷兰式 | 24 | −128.85 | [−269.06, −5.00] | 7／7／10 |

伦敦事前就绪性研究（PRE，R6 v1.3）另行比较固定先核查 I 与合法直接修订 D。公开开发共 19 条，其中 18 条合规，I 的缺额较少／持平／较多为 0／10／8 条。同账号合成扩展共 35 条，其中 34 条合规，相应为 1／28／5 条。开发条件 C09b 与扩展条件 B03 中，I 与 D 退出时均超过预留工时，原面板各自保留该条件。 [伦敦维护降级 PRE 的有限证据](https://github.com/DonsonHH/AegisDC/blob/84eaa73d8e1365abd1ff1b8f6c0b83d01470bd69/docs/mainline/review-gated/R6/london-pre-manuscript-v1.3/claim-evidence-matrix.md)

V6 完整设施的取水清滤首片中，策略 V 与直接规则 D 的 17 个主配对全窗服务均持平。V 节省人员、工具和费用的 3 条均失去了 D 曾取得的合法关闭。 [完整设施的原生首片比较](https://github.com/DonsonHH/AegisDC/blob/ec1e37475360dd5025d8571f04fa75253c67f33e/docs/mainline/v6-native-method-study-v1/README.md)

在公开设计的冷却与网络联合工单冷态面板中，策略 J 对 B 的 24 个主配对有 1 条改善、22 条持平、1 条退化。A04 的冷却正常，网络配置限制服务。J 核查网络、修正配置并通过复核，B 清滤时写回原值，J−B 服务缺额为 −6.375 秒。 [完整设施的联合冷态比较](https://github.com/DonsonHH/AegisDC/blob/b867628f1d0cd1a8355b9d5e4394bce9b12bd992/docs/mainline/v6-stage-three-cold-study-v2/README.md)

### 失效条件与反例

伦敦式开发条件 5-04 与 5-10 在仅既有保护时全窗公开记录相同，合法全知排程却分别恢复路径和修正共享判断。付费核查路径的移交状态与连接位置可以区分它们。独立工程见证还保留了三类限制：路径未移交、连接位置不对、发电机硬件未就绪。在这些工况下，即使执行控制修正，终端仍会失电。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

伦敦式留出条件 5-08 中，风险策略比 B 多损失 540 秒。荷兰式留出中有 10 条错过预防性重分组窗口。B 已在转供前完成重分组；稍后重启泵，无法追回停电期间的服务。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

冷态 B08 中，B 有权直接安排冷却和网络处置，网络在 2.00 秒恢复。J 先查后改，到 3.50 秒才恢复网络，服务缺额差为 +1.50 秒。J 虽少用人员和工具，却失去了 B 对冷却工单取得的处置后复核关闭。A04 与 B08 均属于完整设施冷态比较，观察到的服务变化不能用于估算真实事故的损失。 [完整设施的联合冷态比较](https://github.com/DonsonHH/AegisDC/blob/b867628f1d0cd1a8355b9d5e4394bce9b12bd992/docs/mainline/v6-stage-three-cold-study-v2/README.md)

## E C3 普通改进的开发收益能否迁移

### 结论

固定改进器用付费开发反馈提出或挑选调度策略。任一候选首次提出请求，公开选择器 S 就要选定整套策略。它读取设施类型，以及首个已到达风险信号所属的域与类别。若尚无风险信号，就按“无信号”分组。选定后不再换策略。

对照 W 在开发条件上选取平均整窗服务缺额最低的策略，对所有新条件沿用。选择器在旧板的跨半评价中减少了缺额。在同一发生器上评价新条件，S 平均缺额高于 W。预注册迁移命题未成立。 [公开选择器的旧板开发](https://github.com/DonsonHH/AegisDC/blob/25f86d8c7de5cad37e6b47d01a4991f161db0539/docs/mainline/t5-observable-selector-v3c/development-report.md)  [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)

### 数字

v1 的主轨在 48 个开发条件上相对 V\*\* 的平均缺额差为 −49.64 秒。主轨和热启动轨锁定的向量都来自首批手写方案，付费评价选中了它们，向量的构造不能归因于反馈。 [人工锚点的归因更正](https://github.com/DonsonHH/AegisDC/blob/0e89b678c7da4b3060d364d3625bd66952ff113f/docs/mainline/t5-ordinary-improvement-development-v2/manual-references.json)

v2 去掉手写锚点，付费反馈会更新变异算子的得分。每次变异仍从根向量出发，没有沿当前胜者继续爬山。

每个搜索种子先在共同开发条件上计平均缺额，再取各算法的种子中位数。改进器 U 相对等预算随机搜索 R 的差为 +379.58 秒。相对成本感知规则 B_cost 的双侧区间上端为 0.00 秒。两项都未过开发门槛。 [无锚点开发结果](https://github.com/DonsonHH/AegisDC/blob/0e89b678c7da4b3060d364d3625bd66952ff113f/docs/mainline/t5-ordinary-improvement-development-v2/README.md)

v3a 在半板选优、对侧计分，再调换方向。回收率以成本感知规则到认证全知下界的距离为分母。候选数从 6 扩至 24 时，双向回收率由 63.63% 降至 56.89%，预注册判读为“不确定”。 [候选空间的开发诊断](https://github.com/DonsonHH/AegisDC/blob/29ac5a2eac2e6527cbfd04145b0caa2c9206c09e/docs/mainline/t5-landscape-diagnostic-v3a/README.md)

v3b 拼接各族优胜者的动作域参数。与最佳完整向量相比，开发板的平均缺额差为 +352.96 秒，单侧上界为 +493.42 秒。分块重组未通过开发门槛，后续搜索未启动。 [分块重组的开发门槛](https://github.com/DonsonHH/AegisDC/blob/9360a3c8f9c06f4b85f4706ef529c2fc4ef811a3/docs/mainline/t5-block-recombination-v3b/README.md)

v3c 旧板跨半评价中，S 相对各训练半赢家的均差为 −141.13 秒，单侧上界为 −40.00 秒，通过开发门槛。

在整块旧板重新拟合并冻结后，新板 36 个配对的 S−W 均差为 +80.49 秒，预注册双侧区间为 [+41.31, +123.48] 秒。选择器在 0 个条件上更优、26 个持平、10 个更差。 [公开选择器的旧板开发](https://github.com/DonsonHH/AegisDC/blob/25f86d8c7de5cad37e6b47d01a4991f161db0539/docs/mainline/t5-observable-selector-v3c/development-report.md)  [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)

### 失效条件与反例

旧板 A-2-01 已出现反例，选择器比该训练半赢家多损失 180.00 秒。新板有限备用族的 6 个条件平均多损失 310.00 秒。在 new-3-02，首次提案时尚无风险信号。选择器采用 MAIN-U-3，整窗缺额为 600.00 秒，同条件的整板赢家 MAIN-R-3 为 0.00 秒。

这项确认只检验冻结选择规则相对整板赢家的迁移。更换候选空间或反馈规则后的表现仍需另行比较。 [公开选择器的旧板开发](https://github.com/DonsonHH/AegisDC/blob/25f86d8c7de5cad37e6b47d01a4991f161db0539/docs/mainline/t5-observable-selector-v3c/development-report.md)  [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)

## F C4 递归自我改进的增量能否辨识

### 结论

在该合成发生器范围内，依据现有对照，递归自我改进（RSI）相对固定改进器的增量不可辨识。普通改进用既定程序提出和筛选调度策略。RSI 要求开发经验能改变后续提案程序。问题是：在相同预算下，新程序选出的策略能否再减少服务缺额？

封存研究已经比较固定策略，并为每个条件认证了服务缺额下界。尚未执行同预算的 RSI 与固定改进器对照，因而无法从这些成绩估计改变提案程序带来了多少收益。 [固定向量和逐条件最小值的复算](https://github.com/DonsonHH/AegisDC/blob/383c00c3137958dd146d784a6e6251dbe9e603e7/docs/mainline/t6-paper-consolidation/README.md)

### 数字

整窗服务缺额与该条件认证全知下界之差称为剩余缺额。评价器用满足既定行动权限的设施轨迹核实下界确实可达。剩余缺额不超过 0.01 秒记为贴界，实际服务仍可能有不可挽回的损失。旧开发板按条件等权计分。

固定策略必须在全板沿用同一向量。MAIN-R-3 在固定向量名册和完整回放名册中均居首位，Q22 均居次位。若允许读完各候选的实际成绩再逐条件择优，便可算出相对固定首位还能减少多少缺额。这个选择使用**事后信息，非可部署策略**。 [固定向量和逐条件最小值的复算](https://github.com/DonsonHH/AegisDC/blob/383c00c3137958dd146d784a6e6251dbe9e603e7/docs/mainline/t6-paper-consolidation/README.md)

| 旧板候选名册 | 固定首位的平均剩余（秒） | 固定次位的平均剩余（秒） | 逐条件事后最低的平均剩余（秒） | 相对固定首位的条件化改善上限（秒） |
| --- | ---: | ---: | ---: | ---: |
| 固定向量，54 项 | 82.03 | 86.67 | 0.00 | 82.03 |
| 完整回放，58 项 | 82.03 | 86.67 | 0.00 | 82.03 |

### 失效条件与反例

旧板上的 MAIN-R-3 只有 32/36 个条件贴界，仍有 4 个条件可以指出具体的改善空间。下表把固定首位的剩余与该行实际达界的向量对照。向量身份来自评价结束后的计分。若要将这部分余量转化为可部署收益，还须说明决策者凭当时已到达的公开记录如何选中相应向量。 [固定向量和逐条件最小值的复算](https://github.com/DonsonHH/AegisDC/blob/383c00c3137958dd146d784a6e6251dbe9e603e7/docs/mainline/t6-paper-consolidation/README.md)

| 未贴界的旧板条件 | 固定首位的剩余缺额（秒） | 事后达界向量 |
| --- | ---: | --- |
| A-3-02 | 30.00 | Q03 |
| A-6-03 | 1235.00 | Q01 |
| B-1-01 | 1643.00 | Q03 |
| B-3-03 | 45.00 | Q09 |

确认新板实际使用的 W 为 MAIN-R-3，36/36 个条件贴界，平均剩余为 0.00 秒。固定参照已逐条件达到认证下界。在这块新板上，保持服务端点和行动权限不变，无法再降低缺额。这项界限只约束该面板的比较，其他任务和现场设施上 RSI 的收益仍未建立。 [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)  [固定向量和逐条件最小值的复算](https://github.com/DonsonHH/AegisDC/blob/383c00c3137958dd146d784a6e6251dbe9e603e7/docs/mainline/t6-paper-consolidation/README.md)

## G 导师五问

### 伦敦

**识别了什么。** 待核查的是维护期间备用供电能否接管。Google 事后查明，备用馈线断路器已断开，控制器却共用上游电压判断。运行馈线失电时，发电机没有收到启动信号。 [伦敦事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L18-L32)

**凭什么当时知道。** 合成开发条件 5-01 的路径维护复查提示在 60 秒到达。从起点付费查路径，读数可在 50 秒到达，仅购买方可取得。提示本身不能诊断故障。现场人员当时可见的材料未建立，缺工单版本、收件人和到达记录。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [伦敦事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L18-L32)

**能采取什么行动。** 合成设施可在获准后恢复已移交的路径、预启动机组或修正共享判断。接管还要求接线正确、硬件就绪。现场有事后切至备用市电的记录，事前操作权未建立，缺当班授权单。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [伦敦事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L18-L32)

**是否来得及。** 5-01 要挽回全部可避免损失，最迟须在 720 秒开始恢复获准路径，报警在 990 秒才到。现场余量未建立。同版报告的事件表把失电与影响起点记在电池耗尽时，产品说明却将部分不可用记在馈线故障时。时刻尚未对齐，也缺实际剩余电量。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [伦敦事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L18-L32)

**额外收益从何而来。** 伦敦 PRE 同账号扩展条件 B01 中，否定读数使核查方停手，避开了直接修订带来的隔离和重启。先核查、直接修订、仅既有保护的缺额依次为 0、7、0 秒。现场增益未建立，缺同工况的合法替代处置结果。 [伦敦维护降级 PRE 的有限证据](https://github.com/DonsonHH/AegisDC/blob/84eaa73d8e1365abd1ff1b8f6c0b83d01470bd69/docs/mainline/review-gated/R6/london-pre-manuscript-v1.3/claim-evidence-matrix.md)

### 荷兰

**识别了什么。** Google 事后记载，转供触发过载保护，部分负载失电。控制器离线后泵未随来电重启，施工又使备用冷却无法接替。需要核查的风险因此从电力转供延伸到复电后的冷却。 [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L43)  [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

**凭什么当时知道。** 合成开发条件 6-02 的复电测试提示在 120 秒到达，付费读数最早可在 50 秒到达。未派工的策略看不到读数。现场能否提前判断转供余量和泵的状态未建立，缺当时收到的负荷测量和控制器记录。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L43)

**能采取什么行动。** 合成设施在另路有余量且许可有效时可提前重分组，来电后可依权限重启泵，备用冷却须在施工移交后复役。现场事前操作权未建立，缺授权记录。人工切泵发生在恢复期，临时不间断电源是事后部署。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L43)

**是否来得及。** 6-02 要挽回全部可避免损失，最迟须在 540 秒启动重分组，正式报警在 990 秒到达。现场能否在跳闸前完成重分组、在热缓冲耗尽前恢复泵送，未建立，缺作业时长和库存记录。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L43)

**额外收益从何而来。** 合成工程见证中，仅既有保护的缺额为 1920 秒。只重分组仍有冷却损失 1800 秒，只重启泵仍有供电损失 120 秒，及时重分组并重启泵的缺额为 0 秒。现场减损幅度未建立，缺可比的替代处置记录。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L43)
