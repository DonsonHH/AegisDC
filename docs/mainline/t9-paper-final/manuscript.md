# 维护降级时，何时值得先核查？耦合算力设施中的服务、证据与行动

## 摘要

算力设施收到异常记录时，等待现场核查可以避免不必要的处置，也可能错过切换或修复的窗口。本文把供电、冷却、服务和现场作业放在同一套合成设施中。记录何时到达、人员何时可进场、处置何时生效，都与服务损失在同一时钟上核对。

强透明规则 B 可在许可下直接处置。风险驱动方法 V\*\* 还可选择先核查。在 T4b 合成留出面板上，以 V\*\* 的 L 减去 B 的 L，整板均差为 [−343.90](numeric-sources.md#n001) 秒，双侧 [95](numeric-sources.md#n136)% 区间 [[−445.94](numeric-sources.md#n137), [−244.22](numeric-sources.md#n138)] 秒。预注册 H1 确认检验的封存判定为 MET，个别条件的缺额仍会增加。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

在伦敦式和荷兰式合成事故的预注册确认中，V\*\* 相对仅保留既有保护的 P 和相对报警响应的平均缺额差分别为 −580.00 和 −582.08 秒。合成事件率差的块间方差为零，该端点不可判。普通搜索在维护窗口开发面板上以增加工时换得减损。允许改写提案程序的一臂未触发可影响后续候选的改写，与普通搜索锁定同一子策略。 [事故族确认量](numeric-sources.md#inc-ha) · [报警对照](numeric-sources.md#inc-hb) · [频率端点](numeric-sources.md#inc-hc) · [改写与锁定记录](numeric-sources.md#fit-mechanism)

**关键词**　算力设施、按需核查、受约束处置、服务缺额、递归自我改进

## 研究问题与计量

供电或冷却链上的异常会沿服务依赖影响计算、存储或通信，现场人员却未必能沿可通行路线及时抵达设备。这时应先测量、直接申请处置，还是等待？设备真值留在设施与评价端。决策者可查公开作业目录，只接收已经到达的观测和工作回执。现场读数有时只能排除一种解释。

V\*\* 依据公开材料比较仍有支持的风险解释，估计核查会怎样改变后续行动，再在可行分支中派工。策略提出请求后，设施仍要核验许可、人员、工具和通行条件。完成处置后，还要等本次执行的复测和服务证据，才能把工单记为合法关闭。所有对照均保留设备内原有的自动保护。 [完整设施的方法和公开证据边界](https://github.com/DonsonHH/AegisDC/blob/0ca350d1cb54ecc20fd99db5d69167d886cdef34/docs/mainline/full-facility-method-handoff.md#L11)

主端点 L 是全窗归一化服务缺额，以秒计。需求存在时，把每一时段未交付的服务比例乘以该时段长度，再相加。数值越小，表示同一需求下少损失了服务。同一条件的各策略独立运行。人员、工具和费用另行入账。省工不能冲抵服务损失。

下文以候选 L 减对照 L。负差表示候选少损失服务。合法全知排程遵守相同动作和资源约束，用于核实每个条件能达到的下界，其私有信息不进入实际策略。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md) [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

## C1 允许先核查的决策规则降低了整板平均缺额

### 结论

在 T4b 合成留出面板上，风险驱动的 V\*\* 相对强透明规则 B 降低了平均 L。这就是预注册 H1 检验的命题，范围只到全板等权均值。B 在公开条件允许时可直接处置。P 只使用既有保护，周期巡检按排程检查，报警响应由已发布的报警触发。用它们作对照可以说明方法介于哪些现状做法之间，却不能替换 B 的主检验。 [T4b 预注册检验及对照](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4d-cost-baseline-v1/confirmation-protocol-v2.md#L7-L17)

### 数字

T4b 的 [144](numeric-sources.md#n002) 条条件全部成对。V\*\*−B 为 [−343.90](numeric-sources.md#n003) 秒，封存双侧区间为 [[−445.94](numeric-sources.md#n004), [−244.22](numeric-sources.md#n005)] 秒，上界低于零，预注册 H1 确认为 MET。

预注册 H2 确认为 MET。V\*\* 比同一方法关闭自选初检时的平均服务缺额少，配对差为 [−55.83](numeric-sources.md#n006) 秒，双侧 [95](numeric-sources.md#n139)% 区间 [[−110.00](numeric-sources.md#n140), [−11.61](numeric-sources.md#n141)] 秒。这一对照直接比较能否自选初检。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

预注册 H3 确认为 MET。V\*\* 相对成本感知透明规则 B_cost 的配对差为 [−390.48](numeric-sources.md#n007) 秒，双侧 [95](numeric-sources.md#n142)% 区间 [[−488.63](numeric-sources.md#n143), [−292.83](numeric-sources.md#n144)] 秒。V\*\* 对 B 的总差还包含派工排序、暂缓和直接处置的不同选择，不能全部归因于核查。 [自选初检与整套决策规则的比较口径](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4c-action-cost-v3/README.md#L19-L37)

原协议依次检验全板均值。分族结果只用来描述差异。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

| 描述性参照 | T4b 留出板 V\*\*−参照（秒） | v3c 新板 V\*\*−参照（秒） |
|---|---:|---:|
| 仅既有保护 P | [−711.96](numeric-sources.md#n008) | [−551.78](numeric-sources.md#n009) |
| 周期巡检 | [−447.89](numeric-sources.md#n010) | [−302.97](numeric-sources.md#n011) |
| 报警响应 | [−489.91](numeric-sources.md#n012) | [−344.90](numeric-sources.md#n013) |

同样按全板均值，V\*\* 的人员占用相对巡检在留出板少 [498.47](numeric-sources.md#n014) 人秒，在新板少 [492.08](numeric-sources.md#n015) 人秒。新板没有 B 臂。V\*\* 相对 B_cost 的服务差为 [−269.65](numeric-sources.md#n016) 秒，只是补充比较。新板的预注册主问题是选择器 S 与冻结赢家 W 的差，并非在另一块板上重检 H1。 [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)

### 失效条件与反例

若把全板命题改为“每个条件都优于 B”，封存记录并不支持。在 T4b 中，V\*\* 对 B 为 [54](numeric-sources.md#n017) 优、[76](numeric-sources.md#n018) 平、[14](numeric-sources.md#n019) 劣。荷兰式族有 [10](numeric-sources.md#n020) 条劣行，均与错过预防性重分组窗口的记录对应。申请泵操作不能补回此前已损失的供电时间。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

冷却与通行族则说明省工与少失服务可以指向不同的策略。留出板上，V\*\* 相对巡检少用 [256.04](numeric-sources.md#n021) 人秒，平均 L 却增加 [37.29](numeric-sources.md#n022) 秒（[1](numeric-sources.md#n023) 优、[20](numeric-sources.md#n024) 平、[3](numeric-sources.md#n025) 劣）。新板同族相对巡检、报警均持平。

T4d 原开发条件也有固定对照退化的记录，B 有 [18](numeric-sources.md#n026)/[72](numeric-sources.md#n027) 条比 P 差。V\*\* 自身对 P 在留出板有 [4](numeric-sources.md#n028) 条、新板有 [2](numeric-sources.md#n029) 条更差。这些反例限定了适用条件，保留在比较的原分母内。 [成本基线的原开发板](https://github.com/DonsonHH/AegisDC/blob/036ccfdf2d6e5d4b39ba11da480fa2a3d69c1f9f/docs/mainline/t4d-cost-baseline-v1/README.md) [实际处置与严格劣行](https://github.com/DonsonHH/AegisDC/blob/ce3ee6303a81f99341d40796d499185e997238da/docs/mainline/t5-closeout/README.md#L9)

## C2 事故机制在什么条件下会改变服务损失

### 结论

核查改变服务后果，需要证据到达后仍有可执行的处置。伦敦式工况中，移交后才能恢复隔离的备用路径。若控制器把上游有电误判为备用路径可供电，可申请修正共享判断或预启动机组。

荷兰式工况中，转供前减轻过载可减少供电损失，来电后恢复泵送可减少冷却损失。两类行动各有许可和窗口。Google 事后报告给出了故障链。现场能否提前识别并避免损失，仍未建立。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [伦敦事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L18-L32)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L44)

### 两个合成事故族的预注册确认

T7 分别选取 60 个伦敦式和 60 个荷兰式条件。在同一设施输入、故障和维护安排下，既有保护 P、周期巡检、报警响应、强透明规则 B 与冻结策略 V\*\* 各自独立运行。先计算条件内配对差，再取两族均差的等权平均。主分析保留全部 120 个条件，其中 16 个运行输入与旧面板重合。 [设计、配对分母与重合口径](numeric-sources.md#inc-design)

服务端点使用全窗 L，频率端点把每臂未舍入的 L > 0 记为该条件发生一次合成事件。下表列边际双侧 95% 区间，预注册判定对三项双侧 p 值统一作 Holm 校正。 [区间与校正](numeric-sources.md#inc-design) · [事件定义](numeric-sources.md#inc-hc)

| 主检验 | 同一条件内的比较 | 点估计 | 双侧 95% 区间 | 判定 |
|---|---|---:|---|---|
| HA | V\*\* 减既有保护 P 的服务缺额 | −580.00 秒 | [−595.52, −564.48] 秒 | MET（确认） |
| HB | V\*\* 减报警响应的服务缺额 | −582.08 秒 | [−612.65, −551.51] 秒 | MET（确认） |
| HC | V\*\* 减 P 的合成事件率 | −37.50 个百分点 | 未建立 | INDETERMINATE |

P 有服务缺额的 90 行中，V\*\* 使 45 行归零，另 45 行仍有缺额。P 无缺额的 30 行中，新增事件为 0。两族的事件率配对差在各自的块间均无变异，HC 依原登记规则保留 INDETERMINATE。现场事件频率端仍未建立。 [HA 原表](numeric-sources.md#inc-ha) · [HB 原表](numeric-sources.md#inc-hb) · [HC 判据](numeric-sources.md#inc-hc) · [事件配对计数](numeric-sources.md#inc-events)

### 开发参照与较早的机制比较

T3 公开开发条件的平均服务缺额如下，单位为秒。全知排程仅供评价端确定同等许可下能达到的最低缺额。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

| 事故族 | 开发条件 | 仅既有保护 P | 周期巡检 | 报警响应 | 合法全知排程 |
|---|---:|---:|---:|---:|---:|
| 伦敦式 | [12](numeric-sources.md#n030) | [410](numeric-sources.md#n031) | [165](numeric-sources.md#n032) | [365](numeric-sources.md#n033) | [75](numeric-sources.md#n034) |
| 荷兰式 | [12](numeric-sources.md#n035) | [1045](numeric-sources.md#n036) | [865](numeric-sources.md#n037) | [1035](numeric-sources.md#n038) | [170](numeric-sources.md#n039) |

在另行留出的 T4b 条件上，下表给出风险策略 `V**` 减去透明直接规则 B 的服务缺额。负差表示少损失服务。分族结果是描述性比较，预注册主检验针对整板均值。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

| 事故族 | 配对条件 | 平均差（秒） | 原封存双侧区间（秒） | 较少／持平／较多 |
|---|---:|---:|---|---|
| 伦敦式 | [24](numeric-sources.md#n040) | [−47.50](numeric-sources.md#n041) | [[−150.00](numeric-sources.md#n042), [+42.50](numeric-sources.md#n043)] | [3](numeric-sources.md#n044)／[20](numeric-sources.md#n045)／[1](numeric-sources.md#n046) |
| 荷兰式 | [24](numeric-sources.md#n047) | [−128.85](numeric-sources.md#n048) | [[−269.06](numeric-sources.md#n049), [−5.00](numeric-sources.md#n050)] | [7](numeric-sources.md#n051)／[7](numeric-sources.md#n052)／[10](numeric-sources.md#n053) |

伦敦事前就绪性研究（PRE，R6 v1.3）另行比较固定先核查 I 与合法直接修订 D。公开开发共 [19](numeric-sources.md#n054) 条，其中 [18](numeric-sources.md#n055) 条合规，I 的缺额较少／持平／较多为 [0](numeric-sources.md#n056)／[10](numeric-sources.md#n057)／[8](numeric-sources.md#n058) 条。同账号合成扩展共 [35](numeric-sources.md#n059) 条，其中 [34](numeric-sources.md#n060) 条合规，相应为 [1](numeric-sources.md#n061)／[28](numeric-sources.md#n062)／[5](numeric-sources.md#n063) 条。开发条件 C09b 与扩展条件 B03 中，I 与 D 退出时均超过预留工时，原面板各自保留该条件。 [伦敦维护降级 PRE 的有限证据](https://github.com/DonsonHH/AegisDC/blob/84eaa73d8e1365abd1ff1b8f6c0b83d01470bd69/docs/mainline/review-gated/R6/london-pre-manuscript-v1.3/claim-evidence-matrix.md)

V6 完整设施的取水清滤首片中，策略 V 与直接规则 D 的 [17](numeric-sources.md#n064) 个主配对全窗服务均持平。V 节省人员、工具和费用的 [3](numeric-sources.md#n065) 条均失去了 D 曾取得的合法关闭。 [完整设施的原生首片比较](https://github.com/DonsonHH/AegisDC/blob/ec1e37475360dd5025d8571f04fa75253c67f33e/docs/mainline/v6-native-method-study-v1/README.md)

在公开设计的冷却与网络联合工单冷态面板中，策略 J 对 B 的 [24](numeric-sources.md#n066) 个主配对有 [1](numeric-sources.md#n067) 条改善、[22](numeric-sources.md#n068) 条持平、[1](numeric-sources.md#n069) 条退化。A04 的冷却正常，网络配置限制服务。J 核查网络、修正配置并通过复核，B 清滤时写回原值，J−B 服务缺额为 [−6.375](numeric-sources.md#n070) 秒。 [完整设施的联合冷态比较](https://github.com/DonsonHH/AegisDC/blob/b867628f1d0cd1a8355b9d5e4394bce9b12bd992/docs/mainline/v6-stage-three-cold-study-v2/README.md)

### 失效条件与反例

荷兰式确认条件中，60 行有 30 行在最后合法开工时点仍选择等待，未能在故障前完成预防性重分组。其中 25 行有 B 及时重分组、避免转供跳闸并减少转供段缺额的配对见证。最后合法时点由评价端事后确定，策略当时只能利用已到达的证据。 [等待失败及强透明对照](numeric-sources.md#inc-wait)

伦敦式开发条件 5-04 与 5-10 在仅既有保护时全窗公开记录相同，合法全知排程却分别恢复路径和修正共享判断。付费核查路径的移交状态与连接位置可以区分它们。独立工程见证还覆盖了路径尚未移交、连接位置不对和发电机硬件未就绪三种工况。在这些工况下，即使执行控制修正，终端仍会失电。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

伦敦式留出条件 5-08 中，风险策略比 B 多损失 [540](numeric-sources.md#n071) 秒。荷兰式留出中有 [10](numeric-sources.md#n072) 条错过预防性重分组窗口。B 已在转供前完成重分组。稍后重启泵，无法追回停电期间的服务。 [T4b 留出结果](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md)

冷态 B08 中，B 有权直接安排冷却和网络处置，网络在 [2.00](numeric-sources.md#n073) 秒恢复。J 先查后改，到 [3.50](numeric-sources.md#n074) 秒才恢复网络，服务缺额差为 [+1.50](numeric-sources.md#n075) 秒。J 虽少用人员和工具，却失去了 B 对冷却工单取得的处置后复核关闭。A04 与 B08 均属于完整设施冷态比较，观察到的服务变化不能用于估算真实事故的损失。 [完整设施的联合冷态比较](https://github.com/DonsonHH/AegisDC/blob/b867628f1d0cd1a8355b9d5e4394bce9b12bd992/docs/mainline/v6-stage-three-cold-study-v2/README.md)

## C3 普通改进的开发收益能否迁移

### 结论

固定改进器用付费开发反馈提出或挑选调度策略。任一候选首次提出请求，公开选择器 S 就要选定整套策略。它读取设施类型，以及首个已到达风险信号所属的域与类别。若尚无风险信号，就按“无信号”分组。选定后不再换策略。

对照 W 在开发条件上选取平均整窗服务缺额最低的策略，对所有新条件沿用。选择器在旧板的跨半评价中减少了缺额。在同一发生器上评价新条件，S 平均缺额高于 W。预注册迁移命题未成立。 [公开选择器的旧板开发](https://github.com/DonsonHH/AegisDC/blob/25f86d8c7de5cad37e6b47d01a4991f161db0539/docs/mainline/t5-observable-selector-v3c/development-report.md)  [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)

### 数字

v1 的主轨在 [48](numeric-sources.md#n076) 个开发条件上相对 V\*\* 的平均缺额差为 [−49.64](numeric-sources.md#n077) 秒。主轨和热启动轨锁定的向量都来自首批手写方案，付费评价选中了它们，向量的构造不能归因于反馈。 [普通改进首版开发成绩](https://github.com/DonsonHH/AegisDC/blob/4ade92174994e378d4bdb97961d51d8aa58e9803/docs/mainline/t5-ordinary-improvement-development-v1/results.json.gz)  [人工锚点的归因更正](https://github.com/DonsonHH/AegisDC/blob/0e89b678c7da4b3060d364d3625bd66952ff113f/docs/mainline/t5-ordinary-improvement-development-v2/manual-references.json)

v2 去掉手写锚点，付费反馈会更新变异算子的得分。每次变异仍从根向量出发，没有沿当前胜者继续爬山。

每个搜索种子先在共同开发条件上计平均缺额，再取各算法的种子中位数。改进器 U 相对等预算随机搜索 R 的差为 [+379.58](numeric-sources.md#n078) 秒。相对成本感知规则 B_cost 的双侧区间上端为 [0.00](numeric-sources.md#n079) 秒。两项都未过开发门槛。 [无锚点开发结果](https://github.com/DonsonHH/AegisDC/blob/0e89b678c7da4b3060d364d3625bd66952ff113f/docs/mainline/t5-ordinary-improvement-development-v2/README.md)

v3a 在半板选优、对侧计分，再调换方向。回收率以成本感知规则到认证全知下界的距离为分母。候选数从 [6](numeric-sources.md#n080) 扩至 [24](numeric-sources.md#n081) 时，双向回收率由 [63.63%](numeric-sources.md#n082) 降至 [56.89%](numeric-sources.md#n083)，预注册判读为“不确定”。 [候选空间的开发诊断](https://github.com/DonsonHH/AegisDC/blob/29ac5a2eac2e6527cbfd04145b0caa2c9206c09e/docs/mainline/t5-landscape-diagnostic-v3a/README.md)

v3b 拼接各族优胜者的动作域参数。与最佳完整向量相比，开发板的平均缺额差为 [+352.96](numeric-sources.md#n084) 秒，单侧上界为 [+493.42](numeric-sources.md#n085) 秒。分块重组未通过开发门槛，后续搜索未启动。 [分块重组的开发门槛](https://github.com/DonsonHH/AegisDC/blob/9360a3c8f9c06f4b85f4706ef529c2fc4ef811a3/docs/mainline/t5-block-recombination-v3b/README.md)

v3c 旧板跨半评价中，S 相对各训练半赢家的均差为 [−141.13](numeric-sources.md#n086) 秒，单侧上界为 [−40.00](numeric-sources.md#n087) 秒，通过开发门槛。

在整块旧板重新拟合并冻结后，新板 [36](numeric-sources.md#n088) 个配对的 S−W 均差为 [+80.49](numeric-sources.md#n089) 秒，预注册双侧区间为 [[+41.31](numeric-sources.md#n090), [+123.48](numeric-sources.md#n091)] 秒。选择器在 [0](numeric-sources.md#n092) 个条件上更优、[26](numeric-sources.md#n093) 个持平、[10](numeric-sources.md#n094) 个更差。 [公开选择器的旧板开发](https://github.com/DonsonHH/AegisDC/blob/25f86d8c7de5cad37e6b47d01a4991f161db0539/docs/mainline/t5-observable-selector-v3c/development-report.md)  [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)

### 固定预算搜索的收益与代价

T8 以同一组 48 个条件评价候选策略，称为 FIT 面板。普通改进器 O 用固定程序提出候选，每轮独立评价 4 个候选，共 4 轮。候选须严格降低总缺额才能替换当前策略，工时只用于候选缺额并列时的排序。共享父平均缺额 135 秒、平均工时 98.645833 人秒。第四轮选中的 `ORDER_FAR=3` 将两项均值分别变为 120 秒和 117.604167 人秒。固定预算搜索平均少损失 15 秒服务，多用 18.96 人秒。这是选择候选所用面板上的实测收益与代价。 [独立付费分母](numeric-sources.md#fit-budget) · [锁定策略和共享父的均值](numeric-sources.md#fit-trade)

登记的 Q3 工时容许量按族比较，要求单侧上界各不超过 +5 人秒。若未来每族 38 个独立块复现 FIT 的块均差和块方差，荷兰工时均差为 +36.458 人秒，单侧 95% 上界为 +38.152 人秒，足以使联合资格不能通过。这是对另行登记的开发资格面板（DEV）的分族情景预测。T8 的实测范围止于 FIT。 [分族门槛、估计与外推](numeric-sources.md#fit-gate)

### 失效条件与反例

旧板 A-2-01 已出现反例，选择器比该训练半赢家多损失 [180.00](numeric-sources.md#n095) 秒。新板有限备用族的 [6](numeric-sources.md#n096) 个条件平均多损失 [310.00](numeric-sources.md#n097) 秒。在 new-3-02，首次提案时尚无风险信号。选择器采用 MAIN-U-3，整窗缺额为 [600.00](numeric-sources.md#n098) 秒，同条件的整板赢家 MAIN-R-3 为 [0.00](numeric-sources.md#n099) 秒。

这项确认只检验冻结选择规则相对整板赢家的迁移。更换候选空间或反馈规则后的表现仍需另行比较。 [公开选择器的旧板开发](https://github.com/DonsonHH/AegisDC/blob/25f86d8c7de5cad37e6b47d01a4991f161db0539/docs/mainline/t5-observable-selector-v3c/development-report.md)  [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)

## C4 递归自我改进的增量能否辨识

### 结论

普通改进用固定程序提出和筛选策略。递归自我改进（RSI）的可检验差异，在于付费反馈能否改变提案程序，使后续真正接受评价的候选发生变化，并让这种变化传递到锁定策略。T8 给 O 和允许改写的 R 相同的父策略、信息、候选空间与预算。此次比较中，**递归改写的独立服务增量未建立**。 [两臂的四轮设计](numeric-sources.md#fit-budget) · [付费候选与父链](numeric-sources.md#fit-mechanism)

前三轮两臂每轮均未找到严格降低父策略平均缺额的候选，R 的改写条件始终没有触发。第四轮首次出现减损候选，两臂均选第 3 槽的 `ORDER_FAR=3` 并结束搜索。由改写新增且进入付费批次的候选为 0 个。R−O 的平均服务缺额差与工时差均为 0，同一锁定策略产生了这个零差。两种搜索程序在其他反馈条件下是否等价，仍未经检验。 [每轮改写、实际付费与终态](numeric-sources.md#fit-mechanism)

另一项限制来自已测单点编辑的服务表现。16 个已评分编辑中，`ORDER_FAR=3` 是唯一在全部 48 行都达到最低缺额的编辑。42 行所有编辑并列，其余 6 行全在荷兰。四个十二行块的登记签名各不相同，面板结构同构的解释与数据不符。整板同时降低缺额与工时的编辑为 0 个。还有 `ALARM_NEAR=3` 和 `ORDER_NEAR=3` 两个单点编辑未评分。服务饱和的结论限于本面板已评分的单点编辑。 [编辑菜单与未测项](numeric-sources.md#fit-menu) · [并列与分族行数](numeric-sources.md#fit-ties) · [块签名](numeric-sources.md#fit-blocks)

### 较早面板上的固定策略与事后余量

整窗服务缺额与该条件认证全知下界之差称为剩余缺额。评价器用满足既定行动权限的设施轨迹核实下界确实可达。剩余缺额不超过 [0.01](numeric-sources.md#n100) 秒记为贴界，实际服务仍可能有不可挽回的损失。旧开发板按条件等权计分。

固定策略必须在全板沿用同一向量。MAIN-R-3 在固定向量名册和完整回放名册中均居首位，Q22 均居次位。若允许读完各候选的实际成绩再逐条件择优，便可算出相对固定首位还能减少多少缺额。这个选择使用**事后信息，非可部署策略**。 [固定向量和逐条件最小值的复算](https://github.com/DonsonHH/AegisDC/blob/383c00c3137958dd146d784a6e6251dbe9e603e7/docs/mainline/t6-paper-consolidation/README.md)

| 旧板候选名册 | 固定首位的平均剩余（秒） | 固定次位的平均剩余（秒） | 逐条件事后最低的平均剩余（秒） | 相对固定首位的条件化改善上限（秒） |
| --- | ---: | ---: | ---: | ---: |
| 固定向量，[54](numeric-sources.md#n101) 项 | [82.03](numeric-sources.md#n102) | [86.67](numeric-sources.md#n103) | [0.00](numeric-sources.md#n104) | [82.03](numeric-sources.md#n105) |
| 完整回放，[58](numeric-sources.md#n106) 项 | [82.03](numeric-sources.md#n107) | [86.67](numeric-sources.md#n108) | [0.00](numeric-sources.md#n109) | [82.03](numeric-sources.md#n110) |

### 失效条件与反例

旧板上的 MAIN-R-3 只有 [32](numeric-sources.md#n111)/[36](numeric-sources.md#n112) 个条件贴界，仍有 [4](numeric-sources.md#n113) 个条件可以指出具体的改善空间。下表把固定首位的剩余与该行实际达界的向量对照。向量身份来自评价结束后的计分。若要将这部分余量转化为可部署收益，还须说明决策者凭当时已到达的公开记录如何选中相应向量。 [固定向量和逐条件最小值的复算](https://github.com/DonsonHH/AegisDC/blob/383c00c3137958dd146d784a6e6251dbe9e603e7/docs/mainline/t6-paper-consolidation/README.md)

| 未贴界的旧板条件 | 固定首位的剩余缺额（秒） | 事后达界向量 |
| --- | ---: | --- |
| A-3-02 | [30.00](numeric-sources.md#n114) | Q03 |
| A-6-03 | [1235.00](numeric-sources.md#n115) | Q01 |
| B-1-01 | [1643.00](numeric-sources.md#n116) | Q03 |
| B-3-03 | [45.00](numeric-sources.md#n117) | Q09 |

下面是确认面板的描述性读回。该面板的正式检验是 S−W。新板实际使用的 W 为 MAIN-R-3，[36](numeric-sources.md#n118)/[36](numeric-sources.md#n119) 个条件贴界，平均剩余为 [0.00](numeric-sources.md#n120) 秒。

固定参照已逐条件达到认证下界。在这块新板上，保持服务端点和行动权限不变，无法再降低缺额。这项界限只约束该面板的比较，其他任务和现场设施上 RSI 的收益仍未建立。 [公开选择器的新板确认](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md)  [固定向量和逐条件最小值的复算](https://github.com/DonsonHH/AegisDC/blob/383c00c3137958dd146d784a6e6251dbe9e603e7/docs/mainline/t6-paper-consolidation/README.md)

## 局限

伦敦式和荷兰式条件内的块结构限制了区间的解释，HA、HB 的区间反映既定结构下的平均缺额波动，HC 则因两族块间方差为零而不可判。 [块间结构与区间](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/manuscript.md#L49-L51)

生成器按配额安排工况，两族等权的条件均值只适用于这一抽取设计，现场的暴露时长与故障分母仍缺。 [配额与现场分母](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/numeric-sources.md#L22-L23)

T8 采用同账号程序性查重，留有 PASS 回执，代签的个人授权归属为“有异议、未独立证实”。 [查重回执与归属记录](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/HANDOFF.md#L36-L38)

两起公开事故的复盘早于合成族和策略设计，研究者已知故障链，现场的历史反事实仍缺当班观测、授权和执行记录。 [公开事故的先验知识](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-incident-counterfactual/contamination.md#L3) · [现场证据边界](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-incident-counterfactual/contamination.md#L13)

## 结论

当一项到达及时的读数能区分会导致不同处置的原因，而且人员仍来得及完成授权作业时，先核查有可解释的服务价值。T4b 的自选初检对照支持这一有限主张，T7 确认了两类合成事故中的平均减损。普通搜索可以用更多工时换取较低缺额，开发收益迁移到新条件仍取决于当时可见的信息。在本次等预算搜索中，改写机制没有产生能够归因于它的不同子策略。

## 未来工作

**相同工时约束下，递归改写能否比普通搜索更早找到公开信息足以辨认的低成本编辑？** 已测编辑中有 4 行可在保持该行最低缺额时减少工时，逐行事后取优在全板平均可省 5.83 人秒。另一个已经付费的 `ALARM_FAR=3` 使荷兰平均缺额少 5 秒，两族工时各增加 4.375 人秒，普通搜索也找到了它。检验这个问题需要新材料和新的查重门，并在相同信息、工时约束与搜索预算下记录程序改写、后继候选实际付费、入选候选进入锁定父链，以及相对 O 的收益。这四行能否在派工时被识别，仍是待检验的条件。 [同缺额下的工时余量](numeric-sources.md#fit-headroom) · [已付编辑的分族取舍](numeric-sources.md#fit-alarm)

## 附录　两起事故的证据、权限与时限（导师五问）

### 伦敦

**识别了什么。** 维护期间，备用供电还能否接管？Google 记载备用馈线已断开，两路控制器仍用上游电压判断，故障时未发启动信号。合成开发板要付费查路径才可能区分两种解释，现场事前识别未建立，缺当班记录。 [伦敦事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L18-L32)

**凭什么当时知道。** 合成开发条件 5-01 中，首条登记类事前材料是路径维护复查提示，在 [60](numeric-sources.md#n121) 秒到达。评价端核实的 [50](numeric-sources.md#n122) 秒是路径目标 LB 的**反事实可买机会**，前提是在 [0](numeric-sources.md#n145) 秒派工。当时只有常规开工授权，没有公开风险触发。这项机会本身不构成任何策略收到读数的证据。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

最晚必要启动为 [720](numeric-sources.md#n146) 秒。实际回执显示，周期巡检在 [50](numeric-sources.md#n147) 秒先收到控制判断目标 LC 的初检读数，在 [110](numeric-sources.md#n148) 秒收到 LB 的初检读数，均早于截止。仅既有保护 P 和报警响应均未在截止前取得付费读数。原 T3 对照没有 V\*\* 臂。T7 在同一输入上补跑冻结策略，V\*\* 在最晚启动时直接恢复 LB，其首份付费读数于 830 秒到达，属于处置后的本人复核。截止前没有实际取得目标初检读数。现场人员当时持有什么材料也未建立，缺工单版本、收件人和到达记录。 [T3 开发原始计分与实际回执](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/development-result.json.gz)  [伦敦事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L18-L32) [同一开发输入的实际回执](numeric-sources.md#inc-london)

**能采取什么行动。** 合成设施可在获准后恢复已移交的路径、预启动机组或修正共享判断。接管还要求接线正确、硬件就绪。现场有事后切至备用市电的记录，事前操作权未建立，缺当班授权单。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [伦敦事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L18-L32)

**是否来得及。** 5-01 要挽回全部可避免损失，最迟须在 [720](numeric-sources.md#n123) 秒开始恢复获准路径，报警在 [990](numeric-sources.md#n124) 秒才到。现场余量未建立。同版报告的事件表把失电与影响起点记在电池耗尽时，产品说明却将部分不可用记在馈线故障时。时刻尚未对齐，也缺实际剩余电量。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [伦敦同版报告的时标冲突](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L50-L51)

**额外收益从何而来。** 伦敦 PRE 同账号扩展条件 B01 中，否定读数使核查方停手，避开了直接修订带来的隔离和重启。先核查、直接修订、仅既有保护的缺额依次为 [0](numeric-sources.md#n125)、[7](numeric-sources.md#n126)、[0](numeric-sources.md#n127) 秒。现场增益未建立，缺同工况的合法替代处置结果。 [伦敦维护降级 PRE 的有限证据](https://github.com/DonsonHH/AegisDC/blob/84eaa73d8e1365abd1ff1b8f6c0b83d01470bd69/docs/mainline/review-gated/R6/london-pre-manuscript-v1.3/claim-evidence-matrix.md)

### 荷兰

**识别了什么。** 事后复盘记载，转供过载使部分负载失电。复电后泵未重启，备用冷却仍在施工。合成开发板须分别查转供余量和泵状态，早期公开记录不足以唯一选定行动。现场事前识别未建立，缺当班观测和方法输出。 [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L44)  [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

**凭什么当时知道。** 合成开发条件 6-02 中，首条登记类事前材料是复电测试提示，在 [120](numeric-sources.md#n128) 秒到达。施工未移交的业务记录在 [90](numeric-sources.md#n149) 秒已到达，不是这条测试提示。评价端核实的 [50](numeric-sources.md#n129) 秒是泵目标 NP 的**反事实可买机会**，前提是在 [0](numeric-sources.md#n150) 秒派工。当时只有常规开工授权，没有公开风险触发。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)

最晚必要启动为 [540](numeric-sources.md#n151) 秒。实际回执显示，周期巡检在 [50](numeric-sources.md#n152) 秒先收到转供目标 NR 的初检读数，在 [230](numeric-sources.md#n153) 秒收到 NP 的初检读数，均早于截止。P 和报警响应均未在截止前取得付费读数。原 T3 对照没有 V\*\* 臂。T7 对相同输入的补臂显示，V\*\* 在最晚启动时仍选择等待，2040 秒才尝试重启 NP，全窗未取得付费读数。现场能否提前判断转供余量和泵的状态未建立，缺当班负荷测量与控制器记录。 [T3 开发原始计分与实际回执](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/development-result.json.gz)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L44) [同一开发输入的实际回执](numeric-sources.md#inc-nl)

**能采取什么行动。** 合成设施在另路有余量且许可有效时可提前重分组，来电后可依权限重启泵，备用冷却须在施工移交后复役。现场事前操作权未建立，缺授权记录。人工切泵发生在恢复期，临时不间断电源是事后部署。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L44)

**是否来得及。** 6-02 要挽回全部可避免损失，最迟须在 [540](numeric-sources.md#n130) 秒启动重分组，正式报警在 [990](numeric-sources.md#n131) 秒到达。现场能否在跳闸前完成重分组、在热缓冲耗尽前恢复泵送，未建立，缺作业时长和库存记录。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L44)

**额外收益从何而来。** 合成工程见证中，仅既有保护的缺额为 [1920](numeric-sources.md#n132) 秒。只重分组仍有冷却损失 [1800](numeric-sources.md#n133) 秒，只重启泵仍有供电损失 [120](numeric-sources.md#n134) 秒，及时重分组并重启泵的缺额为 [0](numeric-sources.md#n135) 秒。现场减损幅度未建立，缺可比的替代处置记录。 [事故族与事前证据的开发记录](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/t3-prior-information-v2/README.md)  [荷兰事故官方复盘定位](https://github.com/DonsonHH/AegisDC/blob/85af7e48b60e61dc453456b5b7bc73ab832900b5/docs/mainline/review-gated/R1/sources.md#L34-L44)
