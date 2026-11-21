# 当前研究主线：完整算力设施中的风险驱动核查、处置与改进

[完整设施方法总路线](mainline/master-roadmap.md)统领原生首片比较、两类风险联合核查处置、方法配对与机制研究、普通改进、可辨识的 RSI 和整篇论文。[设施方法与接口说明](mainline/full-facility-method-handoff.md)保留方法依据；Google 事故是其中的有限验证章节。

用户确认 e060acfe 的 R4 追加验收和 R5 v1 限定的书面分析。公开开发 19 行与同账号扩展 35 行分别报告。v1 的 216 个开发回合、最多 105 个评估回合均作为未执行历史提案保留，无可用或可转拨配额。[R4 有限验收](mainline/review-gated/R4/finite-extension-study-v1/acceptance-20261118.json) · [原 v1](mainline/review-gated/R5/bounded-improvement-v1/README.md)

## 方法问题与首个实现切片

在同一完整设施、外生需求、合法证据获取机会和人员／工具预算下，问题触发的证据选择与受约束行动能否改善服务保障？固定改进器的付费反馈能否改进策略，真正修改后续提案程序能否超过同预算强搜索及固定父、固定子？[11 月 3 日研究定位](meetings/2026-11-03-research-reset.md) · [完整设施 ADR](adr/0003-complete-facility-mainline.md)

原生首片已按一次性授权完成并封存。17 个条件、85 次运行、1,700 个公开决定、131 次人工发行，重试 0。V–D 全部 17 行实际服务持平，V 的资源较少／相同／较多为 3／9／5 行，三项省工均伴随关闭损失。第一阶段已完成并登记[有限验收](mainline/v6-native-method-study-v1/acceptance-20261120.json)。[第二阶段总契约](mainline/v6-joint-cooling-network-v1/README.md)已接受。原工程取得[限定的部分验收](mainline/v6-joint-engineering-v1/acceptance-20261121.json)。[终态接口的有限范围](mainline/v6-joint-terminal-v1/acceptance-20261121.json)已接受。第三阶段[冷态有限工程](mainline/v6-stage-three-cold-v2/acceptance-20261121.json)已接受。[原 V0 的有限验证](mainline/v6-stage-three-cold-launch-v1/v0-acceptance-20261121.json)已接受。[完整替身遍历的有限验收](mainline/v6-stage-three-cold-launch-full-walk-v1/acceptance-20261121.json)已登记。[冷态正式研究](mainline/v6-stage-three-cold-study-v2/README.md)按 be0fe1a9 的一次性授权封存 24 行、66 个位置与 42 个配对。J–B 服务改善 1 行、持平 22 行、较差 1 行，现停在研究结果验收。[第一阶段研究报告](mainline/v6-native-method-study-v1/README.md) · [第一阶段逐臂观测](mainline/v6-native-method-study-v1/per-condition.md) · [本次冷态研究授权](mainline/authorizations/v6-stage-three-cold-study-v2.json)

## 事故验证章节保留的 R0–R6 记录

| 关卡 | 核心交付 | 当前权限 |
|---|---|---|
| R0 | 研究方向与底线；具体模型／协议／数值标准保留后继审查 | 方向已接受 |
| R1 | 来源、决策信息、动作约束、最小因果接口与可识别性 | 修正版资料基线已接受 |
| R2 | 伦敦 PRE 受限合成模型资格 | 已接受旧有限范围；E1–E4声明有限范围已接受；C4/C7有限修复已接受；运行器声明有限工程资格已接受；完整Q11／R2未接受 |
| R3 | 固定方法、强基线与协议 | 方向已调整为核查与合法直接修订的条件价值；公开开发部分已冻结；确认门未就绪，完整R3未完成 |
| R4 | 有限合成机制扩展验证 | 35 条件、105 处理的有限结果已接受。34 行合规，B03 原样保留。原 19 行另计，原独立确认义务未成立、未豁免。 |
| R5 | 普通改进与改进器增量 | 普通 v2 有限开发已完成。已接受服务优先候选在声明前提和目录下的静态否决，暂停该路线。完整 R5 与一般 RSI 仍开放。 |
| R6 | 有限伦敦 PRE 的论文证据 | [v1.3 原版 PDF](mainline/review-gated/R6/london-pre-manuscript-v1.3/manuscript.pdf)与[有限验收](mainline/review-gated/R6/london-pre-manuscript-v1.3/acceptance-20261119.md)作为验证章节材料，原字体显示说明继续适用。 |

每关先交付，再由用户 review；接受当前关卡不自动授权下一关。新试验、模型调用及研究性数值资格须等具体关卡授权。源事实、假设、未知、事后根因、决策者当时可用信息分别记录；权限、既有保护与封存评价器保持约束。

## 历史和本轮工程状态

PR #3 已再次复核并合入 `donson/mainline-39c-endpoints`，合并提交 `4a9dfdbe`；运行内容与通过远端维护验证的版本一致。这仅是维护合并，未接受旧 39c 整票。

[原完整设施主线快照](mainline/history/20261112-before-reset/README.md)和旧工程、失败及研究原件保留。八域设施继续承载主方法。原 180 次比较保留其预设派工及负结果范围，39c 五项尚未整票验收。历史队列与执行额度均不自动恢复。[旧比较范围](mainline/preset-study-scope.json) · [39c 复核](mainline/audits/20261112-39c-whole-ticket/README.md)

本地负责编辑、传输和文件完整性核对。计算与留痕见[远端规则](agents/compute-storage.md)，本活动授权边界见[进度账](mainline/progress.json)。
