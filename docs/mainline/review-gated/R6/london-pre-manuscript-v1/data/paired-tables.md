# 两个既有面板的完整配对附表

本附表从 [figure-data.json](figure-data.json) 静态导出，保留 dev19 的全部 19 行与 ext35 的全部 35 行，两个面板不合并为统计样本。全部数据来自已执行记录；没有新增设施、策略、评分或研究调用。

提取数据 SHA-256：`989a624f8b21e24a83982cbc544a1b98423893503231fa7f5afccacdadf8d7f3`。逐字段来源和原件身份见 [图表映射](../figure-map.md)。

各三元组统一按 **I／D／P** 排列。L 的单位为服务缺额秒，U 为规范化服务单位乘秒；人员与工具分别为实际占用秒。当前两个面板需求恒为 1，因此 L 与 U 数值相等，但量纲分别保留。

“合规”列直接复制提取数据的 `eligible`：dev19 原字段为 `valid_comparison`，ext35 原字段为 `eligible`。非合规行保留原后果，不计有效获益。阶段列复制原 `stage`；`INSPECTION_STOP` 只表示核查停止，可能源于合法否定，也可能源于信息或预算不足，不能直接当作合法关闭。本提取数据没有完整逐行 `closed` 字段，本附表不从阶段或零缺额推定关闭。

## 附表 A：公开开发面板（19 行，18 行合规）

| 面板与条件 | 合规 | L：I／D／P | U：I／D／P | 人员秒：I／D／P | 工具秒：I／D／P | I 阶段 | D 阶段 | P 阶段 |
|---|---|---:|---:|---:|---:|---|---|---|
| dev19.C01 | 是 | 5／0／5 | 5／0／5 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C02 | 是 | 0／0／0 | 0／0／0 | 1／6／0 | 1／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C03 | 是 | 0／0／0 | 0／0／0 | 3／6／0 | 3／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C04a | 是 | 5／5／5 | 5／5／5 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C04b | 是 | 5／5／5 | 5／5／5 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C05a | 是 | 5／5／5 | 5／5／5 | 3／0／0 | 3／0／0 | `APPROVAL_DENIED` | `APPROVAL_DENIED` | `BACKGROUND_ONLY` |
| dev19.C05b | 是 | 5／5／5 | 5／5／5 | 8／5／0 | 8／5／0 | `NOT_IMPLEMENTED` | `COMMIT_FAILED` | `BACKGROUND_ONLY` |
| dev19.C05c | 是 | 5／5／5 | 5／5／5 | 8／5／0 | 8／5／0 | `NOT_IMPLEMENTED` | `NOT_IMPLEMENTED` | `BACKGROUND_ONLY` |
| dev19.C06a | 是 | 5／0／5 | 5／0／5 | 3／6／0 | 3／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C06b | 是 | 5／0／5 | 5／0／5 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFICATION_FAILED` | `BACKGROUND_ONLY` |
| dev19.C06c | 是 | 5／0／5 | 5／0／5 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFY_INCONCLUSIVE` | `BACKGROUND_ONLY` |
| dev19.C07a | 是 | 5／5／5 | 5／5／5 | 2／0／0 | 2／0／0 | `INSPECTION_STOP` | `NO_ACTION` | `BACKGROUND_ONLY` |
| dev19.C07b | 是 | 5／0／5 | 5／0／5 | 3／6／0 | 3／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C08a | 是 | 5／0／5 | 5／0／5 | 3／6／0 | 3／6／0 | `NOT_IMPLEMENTED` | `VERIFY_ABORTED` | `BACKGROUND_ONLY` |
| dev19.C08b | 是 | 5／0／5 | 5／0／5 | 3／6／0 | 3／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C09a | 是 | 7／7／0 | 7／7／0 | 9／6／0 | 9／6／0 | `VERIFIED` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C09b | **否，原行保留** | 13／19／0 | 13／19／0 | 16／19／0 | 16／19／0 | `EXIT_INCOMPLETE` | `EXIT_INCOMPLETE` | `BACKGROUND_ONLY` |
| dev19.C10a | 是 | 0／0／0 | 0／0／0 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |
| dev19.C10b | 是 | 7／0／7 | 7／0／7 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |

## 附表 B：有限扩展面板（35 行，34 行合规）

| 面板与条件 | 合规 | L：I／D／P | U：I／D／P | 人员秒：I／D／P | 工具秒：I／D／P | I 阶段 | D 阶段 | P 阶段 |
|---|---|---:|---:|---:|---:|---|---|---|
| ext35.A01 | 是 | 0／0／0 | 0／0／0 | 1／6／0 | 1／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.A02 | 是 | 0／0／0 | 0／0／0 | 3／6／0 | 3／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.A03 | 是 | 0／0／0 | 0／0／0 | 9／6／0 | 9／6／0 | `VERIFIED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.B01 | 是 | 0／7／0 | 0／7／0 | 1／6／0 | 1／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.B02 | 是 | 7／7／0 | 7／7／0 | 9／6／0 | 9／6／0 | `VERIFIED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.B03 | **否，原行保留** | 11／18／0 | 11／18／0 | 14／18／0 | 14／18／0 | `EXIT_INCOMPLETE` | `EXIT_INCOMPLETE` | `BACKGROUND_ONLY` |
| ext35.C01 | 是 | 0／0／0 | 0／0／0 | 3／6／0 | 3／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.D01 | 是 | 0／0／0 | 0／0／0 | 9／0／0 | 9／0／0 | `VERIFIED` | `NO_ACTION` | `BACKGROUND_ONLY` |
| ext35.E01 | 是 | 0／0／0 | 0／0／0 | 3／0／0 | 3／0／0 | `APPROVAL_DENIED` | `APPROVAL_DENIED` | `BACKGROUND_ONLY` |
| ext35.E02 | 是 | 0／0／0 | 0／0／0 | 8／5／0 | 8／5／0 | `COMMIT_FAILED` | `COMMIT_FAILED` | `BACKGROUND_ONLY` |
| ext35.E03 | 是 | 0／0／0 | 0／0／0 | 8／5／0 | 8／5／0 | `NOT_IMPLEMENTED` | `NOT_IMPLEMENTED` | `BACKGROUND_ONLY` |
| ext35.E04 | 是 | 0／0／0 | 0／0／0 | 9／6／0 | 9／6／0 | `VERIFICATION_FAILED` | `VERIFICATION_FAILED` | `BACKGROUND_ONLY` |
| ext35.E05 | 是 | 0／0／0 | 0／0／0 | 9／6／0 | 9／6／0 | `VERIFY_INCONCLUSIVE` | `VERIFY_INCONCLUSIVE` | `BACKGROUND_ONLY` |
| ext35.F01 | 是 | 0／0／0 | 0／0／0 | 9／6／0 | 9／6／0 | `VERIFIED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.F02 | 是 | 0／0／0 | 0／0／0 | 9／6／0 | 9／6／0 | `VERIFIED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.G01 | 是 | 13／13／13 | 13／13／13 | 1／4／0 | 1／4／0 | `INSPECTION_STOP` | `NOT_IMPLEMENTED` | `BACKGROUND_ONLY` |
| ext35.G02 | 是 | 12／12／12 | 12／12／12 | 4／5／0 | 4／5／0 | `INSPECTION_STOP` | `NOT_IMPLEMENTED` | `BACKGROUND_ONLY` |
| ext35.G03 | 是 | 11／0／11 | 11／0／11 | 2／5／0 | 2／5／0 | `INSPECTION_STOP` | `EXECUTED_UNVERIFIED` | `BACKGROUND_ONLY` |
| ext35.G04 | 是 | 6／0／6 | 6／0／6 | 7／6／0 | 7／6／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.G05 | 是 | 5／0／5 | 5／0／5 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.G06 | 是 | 0／0／4 | 0／0／4 | 8／6／0 | 8／6／0 | `EXECUTED_UNVERIFIED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.H01 | 是 | 0／0／0 | 0／0／0 | 2／0／0 | 2／0／0 | `INSPECTION_STOP` | `NO_ACTION` | `BACKGROUND_ONLY` |
| ext35.H02 | 是 | 0／0／0 | 0／0／0 | 3／0／0 | 3／0／0 | `INSPECTION_STOP` | `NO_ACTION` | `BACKGROUND_ONLY` |
| ext35.H03 | 是 | 0／0／0 | 0／0／0 | 3／0／0 | 3／0／0 | `INSPECTION_STOP` | `NO_ACTION` | `BACKGROUND_ONLY` |
| ext35.H04 | 是 | 0／0／0 | 0／0／0 | 3／6／0 | 3／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.H05 | 是 | 0／0／0 | 0／0／0 | 3／6／0 | 3／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.H06 | 是 | 0／0／0 | 0／0／0 | 9／6／0 | 9／6／0 | `VERIFIED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.J01 | 是 | 0／0／0 | 0／0／0 | 3／0／0 | 3／0／0 | `INSPECTION_STOP` | `NO_ACTION` | `BACKGROUND_ONLY` |
| ext35.J02 | 是 | 0／0／0 | 0／0／0 | 3／6／0 | 3／6／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.J03 | 是 | 0／0／0 | 0／0／0 | 3／7／0 | 3／7／0 | `INSPECTION_STOP` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.J04 | 是 | 0／0／0 | 0／0／0 | 10／7／0 | 10／7／0 | `VERIFIED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.K01 | 是 | 0／0／0 | 0／0／0 | 10／7／0 | 10／7／0 | `VERIFIED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.K02 | 是 | 4／0／4 | 4／0／4 | 8／7／0 | 8／7／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.L01 | 是 | 0／0／0 | 0／0／0 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |
| ext35.L02 | 是 | 5／0／5 | 5／0／5 | 8／6／0 | 8／6／0 | `NOT_IMPLEMENTED` | `VERIFIED` | `BACKGROUND_ONLY` |

## 阅读边界

同名条件必须带面板前缀阅读，例如 dev19.C01 与 ext35.C01 不代表同一个完整输入。每行的三处理共享该行冻结外生条件，但分别持有自己的状态、预算、材料与回执。不同条件行不是事故总体的随机样本；本附表不计算平均现场收益、概率、置信区间或 p 值。

完整恢复记录、阶段形成的请求与回执、非合规约束细节仍以原结果目录为准。此处没有重新读取私有逐臂日志，也没有把出版数据整理称为独立重新资格。
