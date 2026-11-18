# 复现与证据身份附录

本附录区分三件事：按已有记录重建论文中的表图；复核历史执行身份；重新运行研究。当前写作包只做前两者中的仓库材料阅读、静态整理与工件核对，不重新运行设施、策略或评分器。正文、图表与本附录以 `cf666ec5c3f390ecb3b07818365cf4be2c475cde` 为既有证据基线。原始协议、结果、失败、非合规行和已消费授权保持原件；新的图表是对已有结果的表达。[既有主张矩阵][matrix]

## 1. 两个面板始终分开

| 字段 | dev19：公开开发 | ext35：有限机制扩展 |
|---|---|---|
| 分析单位 | 一个完整条件下独立 I／D／P 三元组 | 同左 |
| 完整条件／处理 | 19／57 | 35／105 |
| 有效比较条件 | 18 | 34 |
| 保留但不计有效获益 | C09b，I／D 退出预留超额 | B03，I／D 退出预留超额 |
| I 对 D：缺额较小／相同／较大 | 0／10／8 | 1／28／5 |
| I 对 P：缺额较小／相同／较大 | 0／17／1 | 1／32／1 |
| 数据身份 | 已披露开发设计；6 个完整配置与运行器工程见证重合 | 执行前冻结、同账号、非独立保管的有限扩展 |
| 原始结果发布 | [`519da3d4`][dev-commit] | [`535de4f5`][ext-commit] |

条件键始终使用 `(panel, condition_id)`，例如 `dev19.C01` 与 `ext35.C01`，不能按裸行名连接。实际处理、工程见证、断言、时间步、保存核对与私有原件数量是不同计数，不可互换。两面板不能合并估计现场胜率或总体效应；原独立确认义务仍未建立、未豁免。[开发报告][dev-readme] · [扩展报告][ext-readme] · [固定扩展协议][ext-protocol]

## 2. 版本与冻结输入

| 身份 | dev19 | ext35 |
|---|---|---|
| 共同核心 | `1c0b0c47a5742321a3524a5b16843775cc224e3e` | 同左 |
| 开发输入编制 | `395018e1920f68ed3435f618cfeafc40771d50fd` | 不适用 |
| 输入发布／准备审阅 | `34201ef76f4b5d16286ae7008a814c6c02c566c4` | `01ac5084ff15f584d0b6e08dcf45d600accdeab2` |
| 入口身份 | `75981d124d3c33348c1d4bc3a6528bc0884abc7d` | 实测入口 `cea3317e25587b843d04a48fd577c56bff3e0c63` |
| manifest 提交／实际源码包 | manifest 提交 `bf1096e65cf55ad792c3b1ce4b868968977dacaf` | 实际源码包 `24cc268d783973bb7350d1682c12cc4274cee3d4` |
| 保存核对身份 | 原包 `verification.json` 与作业 134205 | 工具 `65f3d288b248580c7d1dd8f266b3347ac0d4570d`，作业 134537 |

完整输入及 manifest 的 SHA-256 如下；这些值引自冻结身份记录，不是论文重新定义的输入。[开发回执][dev-result] · [开发 manifest][dev-manifest] · [扩展 manifest][ext-manifest] · [扩展身份索引][ext-index]

| 对象 | 仓库路径（相对根目录） | SHA-256 |
|---|---|---|
| dev19 完整输入 | `docs/mainline/review-gated/R3/formal-protocol-v1/development-inputs.json` | `661ed1da1611dde316d6920e3a4e9cc6546ec73e214727e8335bd5a47c663880` |
| dev19 manifest | `docs/mainline/review-gated/R4/public-development-v1/launch-manifest.json` | `8cbb680d29522cb29af5165b2bb2f3f4a1aaa51f41fecc101dbfab84379c5aa0` |
| ext35 完整输入 | `docs/mainline/review-gated/R4/finite-extension-v1/conditions.json` | `4b025bbb29e3652ff70a0a0ccd53556aaa131177bb3b6b9830c6c4e0053aa7d9` |
| ext35 manifest | `docs/mainline/review-gated/R4/finite-extension-v1/execution-manifest.json` | `fa5478798a47d9b37c05e25775337e59f4ac0e2425d495e393852f9dd28164d0` |

两次研究承接的四个核心文件在扩展 manifest 中固定为以下 SHA-256。入口代码与核心逻辑分别绑定，不能将最终文档发布提交当作当时的模型执行版本。[扩展 manifest][ext-manifest]

| 核心文件 | SHA-256 |
|---|---|
| `src/aegis_dc/__init__.py` | `32c7ae44be5f74a3d9d1c44cbe6df95e58637bfe74564ef41c463e1269cd013d` |
| `src/aegis_dc/london_e14.py` | `1d9f8421882faf9e021badf3138505332f9a0513bea90539e6cac04bfc6d2a42` |
| `src/aegis_dc/london_treatments.py` | `4bce4df739e8fbb9ae5b64f1ddb5434670a9334b44941777d7d9db25b466ece2` |
| `src/aegis_dc/london_treatment_score.py` | `707306ffa163a90b8a6a607197eec8364da3208f6fc71cf8a3d2a0e72f85904f` |

## 3. 如何从保存材料重建论文表图

主要数据入口为 dev19 的 [`terminal.json`][dev-terminal]（`rows` 为逐条件摘要，`records` 为私有原件身份索引）和 ext35 的 [`paired-results.json`][ext-data]（逐条件逐臂结果）。两批的完整 Markdown 配对表便于逐行阅读；ext35 的 [`actual-stage-coverage.md`][ext-stages]、[`costs-and-recovery.md`][ext-costs] 与 [`propositions.json`][ext-propositions] 分别给出实际阶段、恢复／成本和冻结命题判定。不能用条件名称或输入中的计划结果替代实际到达事件。[开发全表][dev-table] · [扩展全表][ext-table]

本写作包将图表需要的已有字段集中到 [figure-data.json](data/figure-data.json)，每一项的来源映射见 [figure-map.md](figure-map.md)，生成程序为 [build_figures.py](tools/build_figures.py)。它们的用途是静态整理和出版制图；不生成新条件，不执行策略，也不重算设施未来状态。生成工具、实际出版命令及工件哈希以本包交付回执为准。

重建顺序如下：

1. 固定到本附录所列原始结果提交或证据基线，读取完整输入、结果表与身份记录，先核对行键、处理顺序和全分母。
2. 每行分别保留原始 L/U、资源实耗、完整性、合规状态及实际流程阶段。有效符号的筛选只按原协议；C09b、B03 仍保留原始数值和非合规标记。
3. 对服务差值统一使用 `L_D−L_I`；对 P 的背景关系另给 `L_I−L_P`。人员秒与工具秒分列，不在图中改作单一费用。原精确数值用于比较，显示格式不改变相等或严格不等。
4. 时间图中的实际提交、回执到达、退出、复核、供给和服务恢复取实际记录。若标示名义提交位置，必须单独标为名义事件；`NOT_ATTEMPTED` 不能画成失败的实际提交。
5. `ext35.F01/F02` 的图同时保留 `[0,20)` 完整服务、H20 能量为零、端点设备 OFF、G 的 FAILED／IDLE 状态，以及恢复右删失。窗内零积分不能替换端点状态。
6. R5 的 H1／H2 资源值只在静态证明表中标为推导，不能混入已执行 I/D/P 数据或新策略结果图。

若只阅读仓库配对材料，可以复核论文的报告数字、差值方向、病例解释和静态论证；完整复算所有原始调用与逐段积分需要私有归档中的逐条件原件。本轮未重新登录私有服务器、未重新执行历史 134205／134537 核对，也不把那些历史核对回执说成本次新获得的独立原件复验。

## 4. 评分、关闭与失败的复核规则

评价窗口始终为 `[0,20)`。L 是冻结需求归一化的服务缺额秒，U 是服务单位·秒；两批需求恒为 1，所以二者数值相同而单位不同。恢复右删失只限制恢复时长的识别，不删除窗内损失。轨迹缺失时评分为 null，不以零值替代。人员／工具积分包含真实安全退出；预留不是实耗，审批与排队等待不是人员工时。[设施关系][relations] · [运行器契约][runner]

合法关闭的判断需要本组实际绑定执行身份与目标版本的复核通过，或停止时仍有效的合法否定证据。成功提交但尚未核验可以改善物理后果，却不能改标为已核验关闭。审批拒绝、提交未尝试、提交失败、复核失败、无结论、未恢复及非合规各保留原类型。H20 恰好停机的恢复下界为 0，不表示即时恢复。[R5 晋级定义][r5-rule] · [扩展阶段][ext-stages]

历史资格用预先冻结的独立字面预期约束所列接口。通过的单位、配对、断言及保存核对次数不能解释为研究样本量或全参数空间证明。本文使用已接受的有限结果，不扩大完整 Q11、完整 R2/R3 或现场可靠性主张。[扩展结果回执][ext-result]

## 5. 历史执行与原件边界

下表是历史回执中的实际研究调用，不是本写作包的新调用。[开发回执][dev-result] · [扩展结果回执][ext-result]

| 历史活动 | 研究作业 | runner／构造／设施入口／策略／评分调用 | 保存核对 |
|---|---|---|---|
| dev19 | 134204，一批 19 条件，重试 0 | 19／57／986／362／57 | 134205；历史记录为零新增模型、策略和评分调用 |
| ext35 | 134500–134534，35 个串行单条件作业，重试 0 | 35／105／1890／754／105 | 134537；历史记录为零新增 runner、设施、策略和评分调用 |

dev19 作业限额为 1 CPU、1 GiB、300 秒；历史记录的实际 elapsed 为 3 秒、TotalCPU 为 1.862 秒。ext35 每作业 1 CPU、1 GiB、60 秒，累计 2,100 预留 CPU 秒；这不是实耗 CPU，也不是现场决策运行时。历史解释器为 Python 3.13.9，二进制 SHA-256 为 `5b2187174e57eb543b1800d101a5f115afc24e52c1519b6f09e4759ca4d6abe6`。文稿生成环境应另行记录，不能冒用该研究解释器身份。[开发计算记录][dev-result] · [扩展 manifest][ext-manifest]

详细历史原件保存在以下已登记路径；路径用于定位，不表示本轮已验证其当前可读性：

- dev19：`/share/home/renly/renly-patrol-rsi/mainline/R4-public-development-20261116/attempt-01/result/`；原件 SHA 在 `terminal.json:records`。
- ext35：`/share/home/renly/renly-patrol-rsi/mainline/R4-finite-extension-20261118/study-v1/`；逐文件身份与作业索引见 `identity-index.json`。

重新运行原研究需要重新确认执行目的、授权和唯一输出目录，不能复用已消费的一次授权。本附录不提供自动重跑入口，也不将保存核对变成第二批独立研究。

## 6. R5 静态结论怎样复核

先读取 `e060acfe` 的候选目录、逐行晋级、固定掩码及 U1 采纳规则，再读取 `cf666ec5` 的追加判定。两项否决相互独立：

- `ext35.D01`：已执行 I 经 EVIDENCE 提交并合法复核；D 没有 DIRECT 许可。四种 H 的书面前缀没有否定证据，且只能走 DIRECT，故不能保留 I 的合法关闭。
- `ext35.A02`：已执行 I 的人员与工具各用 3 秒，D 各用 6 秒。按书面正常链，H1 为一次读取加 DIRECT／复核链，各 7 秒；H2 为两次读取加同一链，各 8 秒。H 的数值是规则推导，未运行。

在原目录和原偏好不变、选择正常完整的前提下，全部非 I 项被排除，严格晋级集合为空，锁定结果必为 I；U1 所需的 `p_new ≻ π0` 也不成立。技术中断须记未完成，不用该命题替它补造选择结果。结论不要求也不授权计算四种 H 的其他条件后果；不能从“保留 I”推出 I 在各行各指标都支配其他策略。[R5 原目录][r5-policy] · [晋级与 U1][r5-rule] · [完整静态判定][r5-static]

原 216 个开发回合和至多 105 个最终评估回合保持未执行、不可转拨的历史提案，21 个最终评估槽位未构造成输入。没有发生 U1 的真实提案、采纳或拒绝事件，本文没有 RSI 效应估计。[R5 原预算][r5-budget] · [静态处置][r5-static]

## 7. 本写作包能支持到哪里

本文能够呈现两个具名清单的完整有限结果、机制反例及一个有明确前提的静态不可晋级命题。它不能据此识别真实伦敦事故的可避免性、总体发生率、现场工时价值、普遍最优策略或普通自改进／RSI 的一般效果。来源事实、合成定义、既有运行与未运行推导在正文和图注中分别标识。同账号预冻结提供版本与分析约束，不能代替开发者不可访问结果的独立确认。[R6 主张—证据矩阵][matrix]

[matrix]: https://github.com/DonsonHH/AegisDC/blob/cf666ec5c3f390ecb3b07818365cf4be2c475cde/docs/mainline/review-gated/R6/london-pre-synthesis-v1/README.md
[dev-commit]: https://github.com/DonsonHH/AegisDC/commit/519da3d477676314970a3b44feb8973eafddb5f8
[ext-commit]: https://github.com/DonsonHH/AegisDC/commit/535de4f50bd1618ec4b82d86a1561300cba8d10b
[dev-readme]: https://github.com/DonsonHH/AegisDC/blob/519da3d477676314970a3b44feb8973eafddb5f8/docs/mainline/review-gated/R4/public-development-v1/README.md
[dev-result]: https://github.com/DonsonHH/AegisDC/blob/519da3d477676314970a3b44feb8973eafddb5f8/docs/mainline/review-gated/R4/public-development-v1/result.json
[dev-manifest]: https://github.com/DonsonHH/AegisDC/blob/bf1096e65cf55ad792c3b1ce4b868968977dacaf/docs/mainline/review-gated/R4/public-development-v1/launch-manifest.json
[dev-terminal]: https://github.com/DonsonHH/AegisDC/blob/519da3d477676314970a3b44feb8973eafddb5f8/docs/mainline/review-gated/R4/public-development-v1/terminal.json
[dev-table]: https://github.com/DonsonHH/AegisDC/blob/519da3d477676314970a3b44feb8973eafddb5f8/docs/mainline/review-gated/R4/public-development-v1/paired-results.md
[ext-readme]: https://github.com/DonsonHH/AegisDC/blob/535de4f50bd1618ec4b82d86a1561300cba8d10b/docs/mainline/review-gated/R4/finite-extension-study-v1/README.md
[ext-protocol]: https://github.com/DonsonHH/AegisDC/blob/01ac5084ff15f584d0b6e08dcf45d600accdeab2/docs/mainline/review-gated/R4/finite-extension-v1/protocol.md
[ext-manifest]: https://github.com/DonsonHH/AegisDC/blob/01ac5084ff15f584d0b6e08dcf45d600accdeab2/docs/mainline/review-gated/R4/finite-extension-v1/execution-manifest.json
[ext-result]: https://github.com/DonsonHH/AegisDC/blob/535de4f50bd1618ec4b82d86a1561300cba8d10b/docs/mainline/review-gated/R4/finite-extension-study-v1/result.json
[ext-index]: https://github.com/DonsonHH/AegisDC/blob/535de4f50bd1618ec4b82d86a1561300cba8d10b/docs/mainline/review-gated/R4/finite-extension-study-v1/identity-index.json
[ext-data]: https://github.com/DonsonHH/AegisDC/blob/535de4f50bd1618ec4b82d86a1561300cba8d10b/docs/mainline/review-gated/R4/finite-extension-study-v1/paired-results.json
[ext-table]: https://github.com/DonsonHH/AegisDC/blob/535de4f50bd1618ec4b82d86a1561300cba8d10b/docs/mainline/review-gated/R4/finite-extension-study-v1/paired-results.md
[ext-stages]: https://github.com/DonsonHH/AegisDC/blob/535de4f50bd1618ec4b82d86a1561300cba8d10b/docs/mainline/review-gated/R4/finite-extension-study-v1/actual-stage-coverage.md
[ext-costs]: https://github.com/DonsonHH/AegisDC/blob/535de4f50bd1618ec4b82d86a1561300cba8d10b/docs/mainline/review-gated/R4/finite-extension-study-v1/costs-and-recovery.md
[ext-propositions]: https://github.com/DonsonHH/AegisDC/blob/535de4f50bd1618ec4b82d86a1561300cba8d10b/docs/mainline/review-gated/R4/finite-extension-study-v1/propositions.json
[relations]: https://github.com/DonsonHH/AegisDC/blob/cf666ec5c3f390ecb3b07818365cf4be2c475cde/docs/mainline/review-gated/R2/extensions/e1-e4-v2/relations.md
[runner]: https://github.com/DonsonHH/AegisDC/blob/cf666ec5c3f390ecb3b07818365cf4be2c475cde/docs/mainline/review-gated/R3/runner-v1/contract.md
[r5-rule]: https://github.com/DonsonHH/AegisDC/blob/e060acfe32a0e8da4997b5d932782d05f926cac6/docs/mainline/review-gated/R5/bounded-improvement-v1/improvement.md
[r5-policy]: https://github.com/DonsonHH/AegisDC/blob/e060acfe32a0e8da4997b5d932782d05f926cac6/docs/mainline/review-gated/R5/bounded-improvement-v1/policy.md
[r5-budget]: https://github.com/DonsonHH/AegisDC/blob/e060acfe32a0e8da4997b5d932782d05f926cac6/docs/mainline/review-gated/R5/bounded-improvement-v1/evaluation.md
[r5-static]: https://github.com/DonsonHH/AegisDC/blob/cf666ec5c3f390ecb3b07818365cf4be2c475cde/docs/mainline/review-gated/R5/v1-static-disposition.md
