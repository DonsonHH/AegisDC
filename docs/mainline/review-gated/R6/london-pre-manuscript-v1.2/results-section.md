<a id="ordinary-v2-results"></a>

## 7　两组付费选择在已见条件上取得同一策略

### 7.1　从 v1 的静态否决到 v2 的实际查询

普通受限改进 v2 改变了可选策略，沿用了第 6 节的逐行晋级规则。v1 的四种 H 都没有配置读取和 EVIDENCE 申请分支。在 D01，它们无法保留 I 已达成的合法关闭。在 A02，按正常作业配方推导的工时又高于 I。v1 的空前沿结论仍然成立。v2 允许调整 POS 首读之后的读取次序，在两项当前证据支持且公开资源与时间余量满足条件时合法提前申请，也允许在读数已结算却仍未知时停止。材料齐全时仍可走 EVIDENCE 并请求绑定实际执行身份的复核。每个描述符对两个面板使用同一规则。[v1 两项独立否决](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/v1-static-disposition.md) · [v2 候选与晋级规则](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-improvement-v2/README.md)

两个选择过程从 I 出发，共享人工换序候选和公开的局部时间账。「C」表示先读 POS，再读 CONFIG、VOLT。「V」将后两项交换。「全」保留完整取证路径。「早」在两项支持、直接许可和当期完整链准入均成立时，检查多等末项的代价。只有再读后名义上仍可负担完整链、但所余时间不足一次安全退出时长，才提前申请。「止」在已结算未知时停止，「续」可继续获取其余材料寻找合法否定。固定改进器 U0 依据自己的已付反馈提出下一项，同预算强搜索依预定次序查询。每张票购买一个候选在 dev19 与 ext35 上的完整配对列，54 行到齐才解锁。即使另一组已经算过同一列，本组也须付票才能取得反馈。[真实入口与费用规则](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-improvement-v2/README.md) · [六票回执](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/records/tickets.json)

**表 5　真实查询顺序、五位反馈与每次解锁后的前沿。** 五位依次表示提前申请后退化、未知停止后丢失关闭、继续补证时服务落后于 D、无结论后仍付费、末项给出否定。每一位的共同前提是在本组完整已付列中至少有一行满足该项定义。物理回合与缓存命中按本次票计。

| 顺序 | 组与票次 | 查询候选 | 五位反馈 | 新物理回合／行级缓存命中 | 解锁后的唯一前沿 |
|---:|---|---|---|---:|---|
| 1 | U0 第 1 票 | C全续 | `00110` | 54／0 | C全续 |
| 2 | 强搜索第 1 票 | C全续 | `00110` | 0／54 | C全续 |
| 3 | U0 第 2 票 | C早续 | `00010` | 54／0 | C早续 |
| 4 | 强搜索第 2 票 | C早止 | `00000` | 54／0 | C早止 |
| 5 | U0 第 3 票 | C早止 | `00000` | 0／54 | C早止 |
| 6 | 强搜索第 3 票 | V早续 | `00011` | 54／0 | C早止 |

U0 的共同首票产生了第三位和第四位反馈。依冻结优先次序，它先改变申请时机，随后依据第二票仍出现的第四位改变未知处理。**强搜索第二票已取得最终策略，U0 第三票才取得。** 四个已付新候选均严格晋级于 I，其中 C全续 只改善工时。两组的最终前沿都只有 C早止，无须用目录顺序裁决并列。六张票合计 324 个逻辑回合，对应 216 个全新单策略回合和 108 次缓存命中。C全止、V全止、V早止 没有被购买，它们的实验结果仍未知。[原始查询事件](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/records/query-ledger.jsonl) · [否决行与支配依据](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/decisions.md)

### 7.2　服务改善集中在 K02，合法关闭由另一条证据链决定

dev19 的 19 行和 ext35 的 35 行全部参与防退化判定。两个固定合规掩码分别包含 18 行和 34 行。相对 I，C早止 在 dev19 的合规行上服务缺额全部持平，在 ext35 中只在 K02 降低了服务缺额，其余 33 行持平。两个面板均保留了 I 在掩码内原已达成的每一次合法关闭。[dev19 逐行结果](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/dev19.md) · [ext35 逐行结果](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/ext35.md)

**表 6　锁定策略 C早止 与各对照的配对比较。** 每格依次为锁定者较少、相同、较多的合规条件数。L 为全窗归一化缺额时间。两面板需求恒为 1，未服务量 U 的方向计数与 L 一致。人员和工具各自计实际占用，两项的方向计数也相同。

| 对照 | dev19 缺额 L | ext35 缺额 L | dev19 每种工时 | ext35 每种工时 |
|---|---:|---:|---:|---:|
| 固定核查 I | 0／18／0 | 1／33／0 | 2／16／0 | 6／28／0 |
| 合法直接修订 D | 0／10／8 | 1／29／4 | 6／0／12 | 11／1／22 |
| 既有保护 P | 0／17／1 | 2／31／1 | 0／0／18 | 0／0／34 |
| 人工候选 C全续 | 0／18／0 | 1／33／0 | 1／17／0 | 5／29／0 |
| 另一组锁定者 | 0／18／0 | 0／34／0 | 0／18／0 | 0／34／0 |

K02 中，C早止 在第 7 秒依据已到的 POS 与 CONFIG 支持和公开余量申请 DIRECT，第 11 秒提交，第 12 秒收到执行回执。第 13 秒故障截断时原安全退出完成，未发 VERIFY 请求。相对 I，L 从 4 秒降至 0 秒，U 从 4 降至 0，两种工时各从 8 秒降至 7 秒。两策略在该行都未合法关闭。D 在同一行原已维持零缺额，并于第 11 秒完成绑定复核。因而 K02 的四秒服务改善成立于对 I 和人工候选的比较。与 D 的服务差为零。[K02 请求、执行回执与复核记录](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/records/ext35-rows.json)

D01 检验的是另一项义务。该行直接申请权限为 DENY，C早止 在第 4、6、8 秒依次收到本组的 POS、CONFIG、VOLT 记录，随后用三项当前支持提交 EVIDENCE 申请。修订在第 12 秒实际提交。第 14 秒请求 VERIFY，第 16 秒收到与本组 `ex-1`、目标版本 1 绑定的 PASS。I 和 C早止 均为零缺额、人员与工具各用 9 秒且合法关闭。D 因直接许可不足而没有发请求，服务也为零，目标仍开。这一行说明 v2 如何保留原 I 的关闭能力。[D01 逐臂证据](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/records/ext35-rows.json)

### 7.3　八个省工条件与适用域

**表 7　相对 I 的全部工时改善。** 工时是人员、工具分别实耗的秒数。末列为 C早止 的终态。这八行的合法关闭状态均与 I 相同。

| 面板与条件 | I → C早止，每种工时 | I → C早止，缺额秒 | 省工来源与终态 |
|---|---:|---:|---|
| dev19.C03 | 3 → 2 | 0 → 0 | 第二读即获配置否定，第 4 秒合法关闭 |
| dev19.C06a | 3 → 1 | 5 → 5 | 位置无结论后停止，目标未关闭 |
| ext35.A02 | 3 → 2 | 0 → 0 | 第二读即获配置否定，第 6 秒合法关闭 |
| ext35.C01 | 3 → 1 | 0 → 0 | 位置无结论后停止，目标未关闭 |
| ext35.H06 | 9 → 8 | 0 → 0 | 两读后申请，第 16 秒复核关闭 |
| ext35.J04 | 10 → 9 | 0 → 0 | 两读后申请，第 15 秒复核关闭 |
| ext35.K01 | 10 → 9 | 0 → 0 | 两读后申请，第 16 秒复核关闭 |
| ext35.K02 | 8 → 7 | 4 → 0 | 两读后提交成功，截断时尚未复核 |

八行中只有 K02 同时减少服务缺额。C06a 和 C01 的节省来自结束一次资料不足的调查，两行都保留未关闭。相对 D，锁定者在 dev19 有 8 个合规行缺额更大，在 ext35 有 4 个更大。相对 P，两个面板的每个合规行都多用人员和工具。比较结论随明确的服务、资源和关闭指标而异。[成本及关闭的全部差值](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/records/comparisons.json)

dev19.C09b 与 ext35.B03 均发生超出预留的退出，未合法关闭。四个已付新候选在 C09b 的 L、人员秒、工具秒为 13、16、16，在 B03 为 11、14、14，均与相应的 I 相同。D 在这两行的缺额分别为 19 秒、18 秒，P 均为零。两行保留在各自完整分母中，对资源违规集合和数值退化有否决权，只从正向数值收益的 18／34 行中排除。[逐行原表与退出记录](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/records/terminal.json)

执行前登记的 27 项对照均与实际记录相符，涵盖票序和锁定、提前申请的触发条件、提交—退出—复核时序以及配置否定和未知停止的工时。作业 134624 的研究选择器读取了真实付费列的反馈。人工换序及局部时间账事前已向两组公开，两个面板均为同账号下已见的有限合成开发材料。结果支持这一范围内的普通策略改善，并记录了两个选择过程如何达到同一终局。其终局服务、工时和关闭相同。未见任务泛化、外部独立确认及改进程序修改带来的增量仍待相应证据。[事前推导](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-qualification/before-execution.md) · [27 项逐项对照](https://github.com/DonsonHH/AegisDC/blob/75f05a477bb16965d882b1c7470d474264a086df/docs/mainline/review-gated/R5/ordinary-v2-development/records/prediction-check.json)
