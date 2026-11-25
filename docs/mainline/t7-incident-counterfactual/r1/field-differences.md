# r1 与原登记的逐字段差异

以原登记提交 `51ddd578` 为准，按 JSON 路径比较。数组作一个有序字段。表中“—”表示原登记没有该字段。未列字段逐值相同。

## 样本量及相应数字

| 字段 | 原值 | r1 值 |
|---|---|---|
| `/inference/raw_p` | 对总体配额均差等于零，p=2*t.sf(abs(delta/SE),g-1)。这是合成块均值的名义推断；仅有四块每族，偏态和重复条件可影响校准。 | 对总体配额均差等于零，p=2*t.sf(abs(delta/SE),g-1)。这是合成块均值的名义推断；仅有五块每族，偏态和重复条件可影响校准。 |
| `/inference/resampling` | 逐族对四个完整配额块有放回抽取四块。保留块内全部行及配对臂，两个族的抽取独立。取该分层配对 bootstrap 分布的精确方差，无随机次数或分析种子。可枚举每族所有等概率有序抽法，或用等价的闭式计算。 | 逐族对五个完整配额块有放回抽取五块。保留块内全部行及配对臂，两个族的抽取独立。取该分层配对 bootstrap 分布的精确方差，无随机次数或分析种子。可枚举每族所有等概率有序抽法，或用等价的闭式计算。 |
| `/inference/standard_error` | 令 g=4，m_fb 为族 f、块 b 内的配对差均值，s_f^2 为该族 g 个块均值的无偏样本方差。bootstrap 方差乘 g/(g-1) 去除有限经验分布的缩放。SE^2=(s_LONDON^2+s_NETHERLANDS^2)/(4g)。HC 同法处理行内指示变量差。 | 令 g=5，m_fb 为族 f、块 b 内的配对差均值，s_f^2 为该族 g 个块均值的无偏样本方差。bootstrap 方差乘 g/(g-1) 去除有限经验分布的缩放。SE^2=(s_LONDON^2+s_NETHERLANDS^2)/(4g)。HC 同法处理行内指示变量差。 |
| `/panel/blocks_per_family` | 4 | 5 |
| `/panel/conditions_per_family` | 48 | 60 |
| `/panel/order` | 阶段 2 获准后，将种子的原始字节转为无符号大端整数。按 draw=0..47，每个 draw 先 LONDON 再 NETHERLANDS，传入既有 condition(seed, family_index, draw, templates)。沿用原始插槽、配额和块号 draw//12；不改种子流标签。 | 阶段 2 获准后，将种子的原始字节转为无符号大端整数。按 draw=0..59，每个 draw 先 LONDON 再 NETHERLANDS，传入既有 condition(seed, family_index, draw, templates)。沿用原始插槽、配额和块号 draw//12；不改种子流标签。 |
| `/panel/total_conditions` | 96 | 120 |
| `/panel/total_planned_positions` | 480 | 600 |
| `/power/effect_multiplier` | — | 0.75 |
| `/power/reported_effect_multipliers` | — | [1, 0.75, 0.5] |
| `/power/selection` | 按 12 行配额块逐级检查。每族至少两块才可估计块间方差。各族按 max(行配对差方差,12×块均值方差) 规划行尺度方差；用第一步 Bonferroni 双侧临界值、每族块数减一的自由度及非中心 t 的负向尾功效。三项边际功效的并集界达到目标的首个规模入选。 | 规划效应为各族各端点历史配对均值的 0.75 倍，历史方差取值沿用原登记。按 12 行配额块逐级检查。每族至少两块才可估计块间方差。各族按 max(行配对差方差,12×块均值方差) 规划行尺度方差；用第一步 Bonferroni 双侧临界值、每族块数减一的自由度及非中心 t 的负向尾功效。三项边际功效的并集界达到目标的首个规模入选。 |

## 重合敏感性

| 字段 | 原值 | r1 值 |
|---|---|---|
| `/overlap_sensitivity/denominators` | — | 逐族逐块列计划行数、命中两来源的行数及交集、去重后剔除数、保留数和每端点有效配对数。报告原始分母 60/族、120 合计。两套参考清单均完整且无命中时写“无需敏感性”。匹配证据缺失时标“重合未建立”，不把未核对记为零。 |
| `/overlap_sensitivity/development_reference/archive` | — | docs/mainline/t4c-action-cost-v3/dev-inputs.jsonl.gz |
| `/overlap_sensitivity/development_reference/archive_sha256` | — | 882d4c17b91eb2067ff49885d95b535649a78f5e89ec8422f097fe448b0abf2e |
| `/overlap_sensitivity/development_reference/manifest` | — | docs/mainline/t4c-action-cost-v3/dev-manifest.json |
| `/overlap_sensitivity/development_reference/manifest_sha256` | — | 1408fa54fe27ee616954e8d9b4016e151a4171f724f7531fb817e8da5301b47d |
| `/overlap_sensitivity/development_reference/match` | — | 对 T4c 已披露开发清单的全部 72 条验明整行身份，再按同一投影匹配，六族均在参考集中。 |
| `/overlap_sensitivity/development_reference/operative_map_format` | — | 对全部 72 条建立 {原条件编号: operative 摘要}，以同一 compact 规则序列化，无换行，计算 SHA-256。 |
| `/overlap_sensitivity/development_reference/operative_map_sha256` | — | d74b27c4decec5d7819bf7c9fab83a126d572b3e8154b5589e87d992dcec6cc5 |
| `/overlap_sensitivity/development_reference/revision` | — | 3487276af9e9759357771d16eb45feceaa3c948a |
| `/overlap_sensitivity/estimate` | — | 保留行数可因块而异。对 HA、HB、HC 分别用原配对差，族内每条保留行等权，两个族均值各占一半。HC 加列两方向不一致配对。原块号保留；不补抽条件、不重配对、不把剩余行拼成新的十二行块。 |
| `/overlap_sensitivity/exclusion` | — | 在读取留出评分前固定筛选账。两参考集任一命中即删除该条件整行的全部臂。多次命中只删除一次，列出全部来源与原编号。仅板内重复、同编号或相同工况名不触发此筛选；板内单独重复仍在主重合账中报告。 |
| `/overlap_sensitivity/historical_reference/match` | — | 逐族匹配 T4b 同族 24 条的 operative_sha256。 |
| `/overlap_sensitivity/historical_reference/path` | — | docs/mainline/t4b-holdout-confirmation-v2/condition-summary.json |
| `/overlap_sensitivity/historical_reference/revision` | — | 3487276af9e9759357771d16eb45feceaa3c948a |
| `/overlap_sensitivity/historical_reference/sha256` | — | 745b99b439bd8267817768010d04e0eec157fd235515f911c7623038990e1504 |
| `/overlap_sensitivity/identity` | — | 沿用 T4b author.py::operative，对完整 native、attachment、maintenance 三项按 context_t4b.compact 序列化（键排序、紧凑分隔、ASCII、禁用 NaN），以 SHA-256 标识。 |
| `/overlap_sensitivity/interval` | — | 对每族 f 的 k_f 个非空原块，记 n_b 为块内保留行数、S_b 为配对差之和。有放回抽 k_f 块，每次统计量为所抽 S_b 总和除以所抽 n_b 总和。取全部等概率有序抽法的精确方差 V_f，按 k_f/(k_f−1) 校正。SE²=[k_L/(k_L−1)·V_L+k_N/(k_N−1)·V_N]/4。描述性双侧 95% 区间为点估计 ± t_(0.975,min(k_L,k_N)−1)·SE。完整等长块时退化为原登记公式。 |
| `/overlap_sensitivity/sparse_or_invalid` | — | 任一族保留行数为零，合并点估计和区间均未建立。两族均有行但任一族不足两个非空块，或两族方差同时为零，给出可计算点估计，区间未建立。对所需臂缺失、非合规或数值未决的保留行，沿用原端点失效规则，不以可用行替代该端点的完整子集。其他端点依各自配对报告。 |
| `/overlap_sensitivity/use` | — | 仅描述。三项主分析使用全部 120 个原始条件及原判据，MET 只由主分析给出。筛除结果不参加 Holm 判定，不反馈给策略。 |

## 阶段 1 开发来源

| 字段 | 原值 | r1 值 |
|---|---|---|
| `/stage1_development/direct_compatibility` | — | T3 原件只有 native、attachment、evaluation，公开工单值为 OPEN。T4c native_v3.native_run 直接索引 case['maintenance']，完整 v3 运行器无法原样载入 T3 行。T3 的默认 choose 没有 V_COST 决策逻辑。T4c 的同名行来自不同开发输入，不能填入 T3 的实测栏。 |
| `/stage1_development/exact_input_route` | — | 后续获准后优先保留 T3 原始输入和 T3 原生设施/评分，按 T4a run_panel.py::unit 已用过的公开决策接法绑定 t4c_v3 的独立 V_COST 工人（公开静态目录握手、每次仅到时 view、计划为空）。T3 的 OPEN 保留原值，冻结 permit.exposure 对缺少 MAINT 标签返回 0；工人继续执行自己的 180 秒写入间隔。T3 设施沿用自己的执行规则。该组合目前只有静态接口依据。需核对输入/策略哈希、实际 IPC、派工及有身份的读数到达回执，方能登记为原 T3 输入上的开发观察。 |
| `/stage1_development/fallback` | — | 若在任何设施调用前已确认原样接法不兼容，记录原因，原 T3 的 V_COST 读数仍为“未建立”。可交阶段 1 授权的替代是对原始 T3 行的副本应用冻结的 inputs_v3.attach(copy, 0)，赋予 0 秒暴露、0.5 容量和 180 秒恢复，并把公开工单标为 OPEN/MAINT-0。用独立输入身份、t4c_v3 的 V_COST 与 native_v3 记账。该副本有不同的动作准入与工单，只能报告为派生开发条件；不得填回 T3 原行。发生调用后的失败留原件，不能自动换接法重跑。 |
| `/stage1_development/policy/bundle` | — | t4c_v3 |
| `/stage1_development/policy/bundle_sha256` | — | 28811a22be4e30a34526448c8379a004a96fd951363c9eeb2eceecad947074cd |
| `/stage1_development/policy/freeze` | — | docs/mainline/t4c-action-cost-v3/v-double-star-freeze.json |
| `/stage1_development/policy/freeze_sha256` | — | 17e5e4c98b46b7859621608efa3ea3378baf5f5be6209c28a91dee998f55c462 |
| `/stage1_development/policy/public_rules` | — | src/aegis_action_cost/rules.json |
| `/stage1_development/policy/public_rules_sha256` | — | ef5e73cfd6489e99b94b8a5a5697903dc257cec17060337d117d6f69635dcc97 |
| `/stage1_development/policy/reference_revision` | — | 3487276af9e9759357771d16eb45feceaa3c948a |
| `/stage1_development/policy/role` | — | V_COST |
| `/stage1_development/restriction` | — | 阶段 1 的任何输出只属于开发，不回改本登记的样本量、判据或确认清单。 |
| `/stage1_development/status` | — | 仅登记来源和将来可交审的接法。开发级，不入确认。阶段 1 的实测和兼容性验证尚未执行，须取得单独授权。 |
| `/stage1_development/t3/archive` | — | development-inputs.jsonl.gz |
| `/stage1_development/t3/archive_sha256` | — | 6a0836ded5b28056a5c50ab711940405a9747a6d94c9fd4bed26344dff34df6a |
| `/stage1_development/t3/candidate_roster` | — | 从已封存开发清单按原序选两族各 12 条：5-01..5-12、6-01..6-12。5-01 和 6-02 各是其中一行。阶段 1 的授权决定实际执行范围。使用原始行字节及 T3 原评分口径。 |
| `/stage1_development/t3/directory` | — | docs/mainline/t3-prior-information-v2 |
| `/stage1_development/t3/freeze_sha256` | — | f8cc8891c0e747ef900c647079990af622601e045f158c8df77aaf120860511d |
| `/stage1_development/t3/generator` | — | generator_v2.py::dev_case → incident_case → complete；以 execute.py 生成并封存的逐条输入为准。 |
| `/stage1_development/t3/generator_sha256` | — | cdd386f585a05c401a0153802028a7e9cc2f895f682c4b8bf4bed00f8d66c630 |
| `/stage1_development/t3/manifest` | — | development-inputs.json |
| `/stage1_development/t3/manifest_sha256` | — | 21520e8ec4339a2f9b0d9dfc6afa904c601c6a8bab05379a4321621dc392869e |
| `/stage1_development/t3/parameters` | — | settings.json |
| `/stage1_development/t3/parameters_sha256` | — | 0511ab6b8ee679c753580ab312f88522b82cca607729d3d5611466ac40bd5936 |
| `/stage1_development/t3/public_development_seed` | — | 2026112143 |
| `/stage1_development/t3/representative_input_sha256/5-01` | — | 40742a119ad8eae95daebf239927482b983eac2d968ce183ace532407636cba3 |
| `/stage1_development/t3/representative_input_sha256/6-02` | — | 87dd1031e7d77c980840b915e91b20e2364e7cbe2f6dfd58eebb064358b070e2 |
| `/stage1_development/t3/revision` | — | 85af7e48b60e61dc453456b5b7bc73ab832900b5 |

## 版本登记

| 字段 | 原值 | r1 值 |
|---|---|---|
| `/revision/file_scope` | — | companion_sha256 指向原登记提交的六件附件。r1 的 power.script、power.ledger 均相对于本目录；本次交付件的哈希在 delivery.json，其哈希同登记哈希写入提交说明。 |
| `/revision/id` | — | r1 |
| `/revision/parent_commit` | — | 51ddd5784ceeaff1b26d3cec28920f6e86e08453 |
| `/revision/parent_path` | — | docs/mainline/t7-incident-counterfactual/registration.json |
| `/revision/parent_review` | — | 有条件接受 |
| `/revision/parent_sha256` | — | cc1d69e07769df3783965883036b4d7f431a5ddcda0703fc356899166d04d787 |
| `/revision/reason` | — | 两族及主对照都在 T4b 结果已知后选定。用未收缩的历史均差规划，每族 48 条对效应衰减的余量有限。本修订在 H3 原文交接、条件生成和结果访问之前登记。 |

三项修订以外的研究字段差异为 **0**。版本登记单列。
