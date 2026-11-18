# 在哪个公开决策点改策略

沿用单一伦敦 PRE、H20、整数秒公共时钟、空初始人工观察、一个控制修订、一个聚合服务。每条轨迹的外生输入与独立实例由评价端持有。策略的完整调用形式为 `act(不可变策略描述符, 脱离引用的当前 v2 视图) → action/mode/reason`。进程内不跨条件学习。改进器只能在轨迹之外更换整个描述符。[既有公共投影](../../../../../src/aegis_dc/london_e14.py#L537) · [固定决策与请求构造](../../../../../src/aegis_dc/london_treatments.py#L37)

## 有限目录

目录版本、顺序和描述符在本协议中公开。下列顺序同时用作确定性并列裁决。I 与 D 是既有策略的精确别名。P 的独立处理始终保留。`a` 允许已完成的读取没有当前确定结论，`k` 要求整个前缀当前均以确定值支持缺陷前件。

| ID | 初态与决定 | 请求上限 | 比较角色 |
|---|---|---:|---|
| I = π0 | 原 `choose('I',v)`。按 POS、VOLT、CONFIG 补证，已否定即停。三项有效证据支持 R 且公共完整链可行时申请 EVIDENCE。 | 5 | 固定起点、普通更新的参照。 |
| D | 原 `choose('D',v)`。空初始观察下，合法便可直接申请。保持已有合法停止、等待和复核处理。 | 2 | 原 I/D 主比较的直接修订强对照，也是目录中的透明选项。 |
| H1a | 先读 POS。有效否定即停。前缀已结算且没有有效否定时，按当时完整公共链申请 DIRECT。 | 3 | **人工先验强候选**，向所有组提供。 |
| H1k | 同样读 POS。只有当前 POS 确定为 0 时才走 DIRECT，无结论时停。 | 3 | 单独辨别无结论后的选择。 |
| H2a | POS 后再读 VOLT，任一有效否定即停。可跳过已结算但当前未知的一项，完成前缀后按合法 DIRECT 处理。 | 4 | 检查第二次核查是否值得它占用的时间和资源。 |
| H2k | 相同的两项前缀，遇到已结算但未获当前支持的项即停。两项均当前确定支持才走 DIRECT。 | 4 | 两项前缀上的保守变体。 |
| P | 原 `choose('P',v)`，无新增人工请求，原自动保护运行到 H。 | 0 | 固定背景，保留 L/U 与实耗；不参加候选晋级。 |

H 的两项开关仅有 2×2 种组合，四种规则都由本稿预先公开。选择其中一项可以记为版本选择，不能归功为改进器发明了规则。H 从来不发 READ_CONFIG 或 EVIDENCE。其 POS=0／VOLT=1 只是部分前件，提出 DIRECT 的依据是公共目录与权限，实际批准还要等待本组审批。仅 I 使用原三项 EVIDENCE 链。每类读取、FIX、VERIFY 各至多一次。I 与 D 各自保留原定义，M0／B1 仍只作为原证据规则的等价标签。

## 到时材料与优先顺序

R 的三个支持值为 `POS=0, VOLT=1, CONFIG=LEGACY_LINE`。单项**否定**是 `POS=1, VOLT=0, CONFIG=REVISED_LOCAL` 中对应的确定值。`e(v,x)` 只查看当前 `records` 中本实例已发布的实际 ACTION_RESULT，问题 q-1、维护版本 m0、接收角色 AUDITOR、动作／对象／来源对应。POS 与 VOLT 指向 feeder-B，来源分别为 pos-B、volt-B。CONFIG 指向 ctrl-1，来源 cfg-local，版本须与当前已知配置版本相符。要求 `observed_at ≤ available_at ≤ time < expires_at` 且 status=KNOWN。先按原始来源与记录身份去重。同一字段的合法确定值唯一才返回“支持”或“否定”；冲突、过期、NO_RESULT、缺记录均为“未知”。复制件不能充作两路独立证据。

`settled(v,x)` 只表示本次读取已发出、当前无 pending，且该动作可在本组已到时的 `records/history` 找到元数据匹配的原始完成记录（包括 NO_RESULT 或现已过期的原始记录）。历史在此只说明该次读取已经结算，历史的旧值不能否定或支持 R。只有 attempted 标记、没有到时完成记录时，以资料不足停止。每次公开 tick 都重新检查整个前缀的当前有效性，包括等待第二项时第一项刚刚过期的情形。

所有 H 共用以下单步伪代码。读取结果“否则”仅发生在有公开完成依据之后。设施对已发请求的公开拒绝直接结束该策略；没有到时结果时不能零成本转入 DIRECT。

```text
H(depth, unknown_rule, v):
    拒绝非法版本、未知描述符或含私有数据的调用（技术错误）
    PRE/窗口已关：由外层记录环境停止，不再调用策略
    if v.terminal_failure: return STOP_UNRESOLVED
    if v.pending: return WAIT_PENDING
    if 当前合法复核通过记录绑定到本组成功执行回执及其目标 epoch:
        return NO_ACTION_CURRENT_SCOPE
    if v.phase == AWAITING_VERIFY:
        if 无本组已到达的成功执行回执，或 VERIFY 已经尝试: return STOP_UNRESOLVED
        if not v.context.acquisition_plans[VERIFY_CTRL].admissible: return INSUFFICIENT_INFORMATION
        return VERIFY_CTRL                 # 请求构造器绑定实际 execution_id、target_config_epoch
    if FIX_CTRL 已在 v.attempted: return STOP_UNRESOLVED
    if 任一 e(v,POS/VOLT/CONFIG) 为否定: return NO_ACTION_CURRENT_SCOPE
    for x in [POS] or [POS,VOLT], in order:
        if e(v,x) 为支持: continue
        if x 尚未尝试:
            if read_parameters_known and acquisition_plans[READ_x].admissible: return READ_x
            return INSUFFICIENT_INFORMATION
        if not settled(v,x) or unknown_rule == k: return INSUFFICIENT_INFORMATION
        # a：保留该字段未知，继续处理下一项
    reason = fix_feasibility(v, DIRECT)
    if reason 存在: return reason
    return PROPOSE_FIX(mode=DIRECT)         # 不携带 evidence_ids
```

完整链检查直接复用 `fix_feasibility`。配方、兼容性或 propose/read/verify/direct 任一所需权限未知时为 INSUFFICIENT_INFORMATION。所需许可被拒、兼容性不允许、余额小于 chain_reserve、chain_finish ≥ window.end 或 chain_resource_end > window.end 时为 INFEASIBLE。允许时只发申请。等待、批准、实施、安全退出、回执到达和 VERIFY 的实际时间仍由原设施产生。公开计划里可见的 earliest_start 或 available_at 是日程投影，不是测量值或未来故障时刻。[准入实现](../../../../../src/aegis_dc/london_treatments.py#L37) · [设施请求](../../../../../src/aegis_dc/london_e14.py#L481)

| 分支 | 当时可用的依据 | 可能改善与可能付出的代价 |
|---|---|---|
| D 的立即申请／H 的先读 | 当前公开权限、余额、窗口、各项已公布计划 | D 可能赶在未知截断前完成；若缺陷本已被正常连接排除，实际作业也可能带来隔离损失。先读有机会停下，同时会占用资源和延迟提交。 |
| 到时合法否定／尚无到时证据 | 当前值、来源、对象、到达、有效期，及 pending | 否定时停止可省一次处置。只排除当前 R，不证明整个设施安全。尚在等待时，策略不能先使用稍后才发布的值。 |
| POS 支持后选 DIRECT／再读 VOLT／按 I 继续 | 单项支持、各自真实读取计划、当前完整链 | 增读可能得到另一项否定；也可能消耗本可用于 FIX 或 VERIFY 的余额和窗口。H 可能在 CONFIG 本会否定时仍合法开工。 |
| 已结算、当前未知 | 已到达 NO_RESULT、失效或冲突状态，公开 DIRECT 许可 | a 可以保留合法处置机会，也可能做一次原可避免的处置。k 可以避免该作业，也可能错过真正有用的修订。两者均完整记录未知。 |
| DIRECT 不可行、拒绝或未完成 | 当前目录和余量、到达的拒绝／失败记录、实际环境停止 | 不借 EVIDENCE 名义绕过 direct 许可，也不重试。只读已付的成本仍入账。已完成的提交可能已经改变保障，即使未来得不到复核。 |
| 有执行回执及 VERIFY | 本组已发布的父身份、当前阶段、实际 VERIFY 专用配方 | 复核可以关闭目标或得到失败／无结论。它占用时间和资源，不能替代后备真实接管。 |

**不可区分的世界。** A01/B01 在 I 的位置短路前具有相同公开材料，work_mode 的差异属于评价端。F01/F02 的 ready／物理 permit 也不在 v2 中，核验配置不能补出它们。相同公共前缀下，未来截断、审批、写入、退出及复核结果都可能不同。任一固定描述符在相同公共视图应给出相同决定。合法读取到达后，只能分开它实际揭示的字段。旧行编号、全配置、原始预约表、私有时钟、动作后果、同组索引或“这个时刻通常是哪一行”的查表均无进入策略的路径。[已见 R4 机制证据](../../R4/finite-extension-study-v1/actual-stage-coverage.md)

还有一个直接影响 H1a 的歧义。A03 与 B02 的共同背景只在作业方式上有差异，POS=0 可以合法取得，两者在申请 FIX 前的材料没有作业方式字段。单凭这个读数既无法辨别实际作业会不会切断负荷，也无法知道再读一次是否来得及。H1a 对这种公共前缀执行同一规则，收益方向只能由后续两条各自完整的轨迹判定。若 direct 被禁，H 仍可能已经花费了前缀工时，随后只能保留公开不可行／资料不足的结果；I 仍可按自己的完整证据和 EVIDENCE 权限继续。

冻结不动的部分包括原实例、E14 权限／保护／准入、事件顺序、需求、评分、窗口、时钟、动作限额和失败规则。仅混合策略的前缀／未知处理以及离线提案优先序是待审可变项。在线策略不接收训练记忆、panel 标识、候选评估器或 improver 状态。
