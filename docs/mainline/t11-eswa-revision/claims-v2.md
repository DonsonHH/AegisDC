# 主张表 v2 与旧表逐行对照

修订改变论文的叙事顺序。四项主张的判定、分母、方向、区间与反例继承 T10 冻结表。本轮增加的两个基线和八个参数变体还没有成绩。[T8 中文原表](https://github.com/DonsonHH/AegisDC/blob/28c5969191bab0c7e3c4d508135cc057f89b809d/docs/mainline/t8-closeout/claims.md) · [T10 冻结原表](https://github.com/DonsonHH/AegisDC/blob/fec03bd390b1bd294afc98975a1afbc9ab7b3566/docs/mainline/t10-submission-en/claims-en.md)

| 主张 | 旧表原判 → v2 判定 | 正文可采用的表述 | 必须同报的边界与反例 | 原提交及原文件 |
|---|---|---|---|---|
| C1　成本感知调度与可选付费初检 | Partially supported → **部分成立** | 在六族 144 个共同条件上，方法相对 B、同策略禁购初检、B_cost 的三项登记均差达到原判据。只有禁购对照隔离了开放这项能力的整板服务差。 | 未购买也保留。两臂分别为 128.92、107.57 人秒。开发见证 3-03 中免去写入，3-02 中等待让缺额从 326.25 升至 371.25 秒。对 B 的整板方向 54 优、76 平、14 差。 | [旧表 C1](https://github.com/DonsonHH/AegisDC/blob/fec03bd390b1bd294afc98975a1afbc9ab7b3566/docs/mainline/t10-submission-en/claims-en.md#L7) · [原确认表](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md#L7-L16) · [资源、分层与两项见证](https://github.com/DonsonHH/AegisDC/blob/361574a049f0cfbf816f62af92ff5fd398d77ae8/docs/mainline/t9-submission-r1/manuscript.md#L85-L98) |
| C2　两类事故机制的合成验证 | Partially supported → **部分成立** | 合成伦敦式及荷兰式族中，相对既有保护和报警响应的服务严重度差通过原确认；事件率单列。 | 原 120 行包括与旧输入重合的 16 行。HC 的族内块差方差为零，事件率区间未建立。原开发条件的最晚可开工时刻不能充当现场已取得读数的证明；历史可避免性与现场频率未识别。 | [旧表 C2](https://github.com/DonsonHH/AegisDC/blob/fec03bd390b1bd294afc98975a1afbc9ab7b3566/docs/mainline/t10-submission-en/claims-en.md#L8) · [T7 原提交](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/manuscript.md) · [T9 计数、区间与代表条件](https://github.com/DonsonHH/AegisDC/blob/361574a049f0cfbf816f62af92ff5fd398d77ae8/docs/mainline/t9-submission-r1/manuscript.md#L104-L120) |
| C3　反馈式普通改进能否迁移 | Registered transfer claim not supported → **登记的迁移优势不成立** | 原开发跨半比较有利，但在 36 个新条件上公开选择器相对冻结赢家多损失 **80.49 秒 [41.31, 123.48]**。 | 0 行更好、26 平、10 差。另一次 48 条 FIT 的普通搜索相对共同父少 15 秒缺额，多用 18.958333 人秒；这是选优面板的服务／工时代价。 | [旧表 C3](https://github.com/DonsonHH/AegisDC/blob/fec03bd390b1bd294afc98975a1afbc9ab7b3566/docs/mainline/t10-submission-en/claims-en.md#L9) · [原迁移比较](https://github.com/DonsonHH/AegisDC/blob/87cdd7183970a7787616c666246b38b9fce8320b/docs/mainline/t5-observable-selector-v3c/README.md#L3-L11) · [FIT 原表](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/tables.md) |
| C4　递归改写的独立增量 | Not established → **未建立** | 两臂锁定相同编辑，改写新增付费候选 0 个，R−O 缺额差、工时差均为 0。与 C3 同节，只交代已测边界。 | 仅限已评分的单点菜单。荷兰 FIT 多用 36.458333 人秒，超过 +5 容许量；即使事后逐行在同缺额中取最省工，仍多 26.25。+38.152 是假设 38 个独立块的情景上界。T8 止于 FIT，正式 DEV 未评分。普遍等价性与后续 RSI 改善仍待另项研究。 | [旧表 C4](https://github.com/DonsonHH/AegisDC/blob/fec03bd390b1bd294afc98975a1afbc9ab7b3566/docs/mainline/t10-submission-en/claims-en.md#L10) · [原 FIT 选择和工时](https://github.com/DonsonHH/AegisDC/blob/a5da1c07123f64de272dbc588feb7e2317ea0d2a/docs/mainline/t8-rsi-wait-repair/stage1b/analysis/tables.md) · [T9 实测与预测](https://github.com/DonsonHH/AegisDC/blob/361574a049f0cfbf816f62af92ff5fd398d77ae8/docs/mainline/t9-submission-r1/manuscript.md#L136-L157) |

## 原主比较与事故端点的读表口径

差取方法减对照；负的缺额差表示减少。下表前五项区间均为双侧 95%。T4b 依 H1→H2→H3 顺序检验；T7 同时报告边际区间，并对三项双侧 p 值作 Holm 校正。HC 的单位是百分点。

| 原端点 | 对照与分母 | 原点估计 | 原区间 | 判定与出处 |
|---|---|---:|---|---|
| H1 | 强透明直接规则 B，144/144 | −343.90 秒 | [−445.94, −244.22] | 整套方法差，MET。[确认原件](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md#L7-L16) |
| H2 | 同方法禁购初检，144/144 | −55.83 秒 | [−110.00, −11.61] | 开放自选初检的整板条件均差，MET。[确认原件](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md#L7-L16) |
| H3 | 成本感知透明规则 B_cost，144/144 | −390.48 秒 | [−488.63, −292.83] | 对另一固定规则，MET。[确认原件](https://github.com/DonsonHH/AegisDC/blob/3487276af9e9759357771d16eb45feceaa3c948a/docs/mainline/t4b-holdout-confirmation-v2/README.md#L7-L16) |
| HA | 既有保护 P，两族各 60 | −580.00 秒 | [−595.52, −564.48] | 严重度，MET。[事故确认原件](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/manuscript.md) |
| HB | 报警响应，同上 120 行 | −582.08 秒 | [−612.65, −551.51] | 严重度，MET。[事故确认原件](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/manuscript.md) |
| HC | 既有保护 P，同上 120 行 | −37.50 个百分点 | 未建立 | INDETERMINATE。[原分析及零方差](https://github.com/DonsonHH/AegisDC/blob/40949cb0c97511b901c180ce6f2334573119bcdb/docs/mainline/t7-closeout/manuscript.md) |

## 何时值得等待读数

用 **H2 对照的原描述性分层**作为这一节的中心。0、600、1,200 秒公开维护时长每档 48 条，方法减禁购的均差与组内区间依次为 **+0.62 [0.00, +1.88]**、**−86.16 [−179.79, −15.99]**、**−81.97 [−197.32, +14.65]** 秒。600 秒档在本面板的组内区间全低于零；这些边际区间没有检验档间交互，也不能给出一个通用的等待阈值。T4d 的开发机制设置 S0 在 36 行上同时去除维护暴露及许可间隔，允许初检的差为 +1.25 [0.00, +3.75] 秒。这是联合改动。新 OAT 参数格不会回填上述任何数。[冻结中文版表 3 及见证](https://github.com/DonsonHH/AegisDC/blob/361574a049f0cfbf816f62af92ff5fd398d77ae8/docs/mainline/t9-submission-r1/manuscript.md#L89-L98)
