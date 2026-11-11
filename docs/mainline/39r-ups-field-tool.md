# UPS 现场记录模板与条件比较

从[空模板](39r-ups-field-record.template.json)另存 `field-record.json`；[JSON Schema](39r-ups-field-record.schema.json)说明字段形状，CLI 还检查分数范围、时序与资格。未知标量填 `null` 或省略该键。该工具比较一个负载的声明后果，输入中的许可状态和数据来源须由填表者核实。

| 填写项 | 口径 |
|---|---|
| 负载、来源与可比域 | `asset_id` 指同一个负载；`basis` 为 `FIELD_RECORD` 或 `DECLARED_FIXTURE`，现场记录填写 `evidence_refs`。`leaf_gap_s` 是同窗未投入与投入叶子的断供秒数之差，须为正；`fixed_over_prior` 确认合法集和条件量在所算先验域内固定。 |
| 动作集与门 | `legal_actions` 声明哪些候选合法：`defer`、`escalate`、`direct`、`inspect`。再填写独立的直接授权、查后恢复授权及各策略资源可行性；`true` 是已核对的输入，不是工具授予的权限。查后用工可行性按各分支上限填。 |
| 时戳 | 填 `decision_at`、`deadline_at`；直接恢复填 `direct_completion_at`，查后恢复填 `report_available_at` 和 `conditional_completion_at`。都用带时区的时戳；这里是比较所依据的完成时刻，非工具验证的实际完工。完成须早于截止，等于截止也不算及时。 |
| 条件量 | `a,b` 分别是在未投入／已投入时报告“未投入”的概率，已含未解决分支；`q_I` 是及时、已授权的查后尝试在未投入时的条件成功率，`q_R` 是可比直接恢复的及时成功率。若纳入升级，填其有效恢复概率 `r_E` 和扰动 `d_E`。 |
| 扰动与代价 | `d_R,d_FP,d_E,k` 以同一负载的 `leaf_gap_s` 归一化。数值可用 `0.9` 或 `"9/10"`。工时和工具占用用于资源门，不直接填入同口径断供代价 `k`。 |

```sh
python -B scripts/verify_theorem.py field --input field-record.json
```

结果先列各动作资格，再对可比动作给端点 `alpha,beta`、严格胜区和平手；`best_no_inspection` 是各合法不查参照胜区的交集。不可行标为 `NOT_COMPARABLE`，资料不足标为 `INSUFFICIENT_INPUT`。未知的合法候选未排除前，不给“胜全部”的结论。条件量随先验变动或叶子差非正时返回 `OUTSIDE_MODEL`，须先限定可比区段或重建损失。

`direct_dominance` 说明无扰动直接恢复的充分条件是否满足。满足时的结论限于**声明辅助断供指标下，检查没有严格胜过直接恢复的先验点**。报告既不是授权，也不替代要求先核验的规程。

缺项附在相应资格或端点。只缺一个数值且其余参数、资格和损失口径固定时，`single_missing_boundary` 给出相对该不查动作的边界。`no_strict_win_parameter_range` 是**缺失参数的取值范围**：参数取其中任一值，整个先验区间 `p∈[0,1]` 都没有严格胜点。`could_flip_nonempty_strict_win` 回答的是胜区是否可能由空变为非空。

例如核验包的无扰动样例只缺 `q_R`，上述范围是 `[47/80,1]`；`q_R=47/80` 时 `p=1` 平手。该例中 `q_R<47/80` 只说明某处存在严格胜点。要判断一次具体观测后的选择，仍需知道当时的 `p`、核对可比资格，并检查它是否落在相对所有合法不查动作的交集中。`47/80` 只适用于这组固定合成条件。多项未知时先补记录，工具不会假定哪一项可单独翻转。

跨域复用见[风险子问题模板](39r-risk-problem-template.md)。

[本地 CLI 核验结果](../../evidence/mainline/engineering/39r-ups-field-cli-v1/result.json)保留原四个 `pair` 边界和六个声明的现场格式样例。负分数用 `--s=-1/10` 送入旧解析器，仍被范围校验拒绝。未使用真实场站数据。

```sh
python -B scripts/check_theorem_cli.py --check evidence/mainline/engineering/39r-ups-field-cli-v1/result.json
```
