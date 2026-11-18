# 35个槽位的静态前提与资格承接

时刻单位为秒。下表给出每行入组前可核对的条件。实际到达阶段留给获授权后的归档轨迹。既有工程依据的完整路径和单位 ID 见 [static-transfer.json](static-transfer.json)。

| 槽位 | 同背景组 | 静态前提与实际取证依据 | 对应有限见证 |
|---|---|---|---|
| A01 | A01/B01 | pos-B 在 4 到达，至 15 前有效。D 正常复核在 9 发布。 | E03-short-circuit, X01, X02 |
| A02 | A02 | cfg-local 在 8 到达，至 19 前有效。D 正常复核在 9 发布。 | I11-revised, A07, E03-short-circuit |
| A03 | A03/B02/B03 | I／D 名义作业开工 9/2，名义退出 14/7。记录实际隔离和退出。 | E01-no-fault-full-chain, E11-harmful-isolation, X07 |
| B01 | A01/B01 | pos-B 在 4 到达，至 15 前有效。D 正常复核在 9 发布。 | E03-short-circuit, X01, X02 |
| B02 | A03/B02/B03 | I／D 名义作业开工 9/2，名义退出 14/7。记录实际隔离和退出。 | E01-no-fault-full-chain, E11-harmful-isolation, X07 |
| B03 | A03/B02/B03 | I／D 名义作业开工 9/2，名义退出 14/7。记录实际隔离和退出。 | E12-incomplete-exit, S08, X08 |
| C01 | C01 | POS 无结论路径仍有 VOLT／CONFIG 在 6/8 的合法资料机会。 | I03a, I03b, E04-information-insufficient |
| D01 | D01 | D 缺 direct 许可，I 资料合法且名义修订申请可在 8 提出。 | E08-direct-permission, F10-c4-budget-equal-B1 |
| E01 | E01/E02/E03/E04/E05 | approval=DENY，I／D 正常前序到计划检查点 9/1。按回执及实际阶段核对。 | E05-approval-denied |
| E02 | E01/E02/E03/E04/E05 | commit=FAIL，I／D 正常前序到计划检查点 12/5。按回执及实际阶段核对。 | E06-commit-failure-reached, A03-commit |
| E03 | E01/E02/E03/E04/E05 | guard=BLOCK，I／D 正常前序到计划检查点 12/5。按回执及实际阶段核对。 | X03, A03-guard |
| E04 | E01/E02/E03/E04/E05 | verification=FAIL，I／D 正常前序到计划检查点 16/9。按回执及实际阶段核对。 | E07-verification-failure-reached |
| E05 | E01/E02/E03/E04/E05 | verification=INCONCLUSIVE，I／D 正常前序到计划检查点 16/9。按回执及实际阶段核对。 | X04, A06c |
| F01 | F01/F02 | 两条核验链在 16/9 可达，挑战 17。以 g_state 与实际供给段识别后备父条件。 | E16-backup-unavailable, C05-ready, X05 |
| F02 | F01/F02 | 两条核验链在 16/9 可达，挑战 17。以 g_state 与实际供给段识别后备父条件。 | C05-permit, X05, X06 |
| G01 | G01/G02/G03 | 名义提交 5，截断 4，严格比较完成时点，安全退出照常计费。 | T01, T02, T03, E02-c0-cutoff, E14-private-half-second-cutoff |
| G02 | G01/G02/G03 | 名义提交 5，截断 5，严格比较完成时点，安全退出照常计费。 | T01, T02, T03, E02-c0-cutoff, E14-private-half-second-cutoff |
| G03 | G01/G02/G03 | 名义提交 5，截断 6，严格比较完成时点，安全退出照常计费。 | T01, T02, T03, E02-c0-cutoff, E14-private-half-second-cutoff |
| G04 | G04/G05/G06 | 名义提交 12，截断 11，严格比较完成时点，安全退出照常计费。 | T01, T02, T03, E02-c0-cutoff, E14-private-half-second-cutoff |
| G05 | G04/G05/G06 | 名义提交 12，截断 12，严格比较完成时点，安全退出照常计费。 | T01, T02, T03, E02-c0-cutoff, E14-private-half-second-cutoff |
| G06 | G04/G05/G06 | 名义提交 12，截断 13，严格比较完成时点，安全退出照常计费。 | T01, T02, T03, E02-c0-cutoff, E14-private-half-second-cutoff |
| H01 | H01/H02 | 已消耗加所需预留的阈值 5，两种资源各 4。以实际请求及准入区别读取与完整修订。 | T10, E10-budget-insufficient |
| H02 | H01/H02 | 已消耗加所需预留的阈值 5，两种资源各 5。以实际请求及准入区别读取与完整修订。 | T10, E10-budget-insufficient |
| H03 | H03/H04 | 已消耗加所需预留的阈值 8，两种资源各 7。以实际请求及准入区别读取与完整修订。 | T10, F09-c4-budget-short-B1, F10-c4-budget-equal-B1 |
| H04 | H03/H04 | 已消耗加所需预留的阈值 8，两种资源各 8。以实际请求及准入区别读取与完整修订。 | T10, F09-c4-budget-short-B1, F10-c4-budget-equal-B1 |
| H05 | H05/H06 | 已消耗加所需预留的阈值 11，两种资源各 10。以实际请求及准入区别读取与完整修订。 | T10, F09-c4-budget-short-B1, F10-c4-budget-equal-B1 |
| H06 | H05/H06 | 已消耗加所需预留的阈值 11，两种资源各 11。以实际请求及准入区别读取与完整修订。 | T10, F09-c4-budget-short-B1, F10-c4-budget-equal-B1 |
| J01 | J01/J02 | 发布 10 必须小于窗口末，预留末 11 可等于窗口末 10。 | F05-c4-window-short-B1, F06-c4-window-equal-B1, F02-c7-long-verify-B1, X07 |
| J02 | J01/J02 | 发布 10 必须小于窗口末，预留末 11 可等于窗口末 11。 | F05-c4-window-short-B1, F06-c4-window-equal-B1, F02-c7-long-verify-B1, X07 |
| J03 | J03/J04 | 发布 17 必须小于窗口末，预留末 18 可等于窗口末 17。 | F05-c4-window-short-B1, F06-c4-window-equal-B1, F02-c7-long-verify-B1, X07 |
| J04 | J03/J04 | 发布 17 必须小于窗口末，预留末 18 可等于窗口末 18。 | F05-c4-window-short-B1, F06-c4-window-equal-B1, F02-c7-long-verify-B1, X07 |
| K01 | K01/K02 | 首读排至 3，I／D 名义提交 13/6。依据实际队列、截断与回执核对。 | E09-queue-full-chain, E15-queue-cutoff-before-approval, F07-c4-queue-B1, X07 |
| K02 | K01/K02 | 首读排至 3，I／D 名义提交 13/6。依据实际队列、截断与回执核对。 | E09-queue-full-chain, E15-queue-cutoff-before-approval, F07-c4-queue-B1, X07 |
| L01 | L01/L02 | tF=12，恢复端为 12。分开核对PRE关闭、A源右状态、全窗服务及恢复删失。 | T09, S13 |
| L02 | L01/L02 | tF=12，恢复端为 NEVER。分开核对PRE关闭、A源右状态、全窗服务及恢复删失。 | S02, X05, X06 |

全部槽位共同继承已经接受的组间隔离、冻结需求评分和失败留存见证 E13、G01–G04。各行对整秒配方作解析迁移，正式运行前由用户审阅。

三份旧配置含权限或授权撤销。首次静态审计对这些旧配置给出了过宽的行动机会。追加审计用原规则顺序重新核对全部组，校正撤销、无结论与权限守卫的来源定位。原始清单和首次审计均可追溯。
