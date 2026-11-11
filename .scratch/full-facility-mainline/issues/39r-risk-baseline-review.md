# 39r: 风险目录、价值基线与结论范围纠正

**What to build:** 按用户2026-11-10评阅，交付可审查的八域FEMA适配目录、真实风险／检查价值覆盖及时间错位，修正原180次研究名称与三限定。

**Blocked by:** 39a

**Status:** claimed

**Milestone:** M7 preparation

当前仅执行本次纠正包；长期目标暂停，完成后等待用户审查。目录允许六个主域情景UNMODELED；实际检查价值只覆盖cooling，其他七项不填0。新接口不得据此自动派工。旧1–38有限接受、原180结果和失败不改。

验收：一个公共baseline测试、一个合并result.json及本票证据行；八域身份／资产／服务／线索／能力／后果／未知齐全；当前叙述限定、时间基础39t和执行顺序正确。此验收不等于全场风险已量化。

## Evidence

纠正包已发布到donson/mainline-39c-endpoints并设为默认分支，现等待用户审查；57草稿保留未执行，本票不自动解决或恢复后续开发。

公共risk-baseline接口一个测试远端red/green通过：8主域、2有限风险/6UNMODELED、1价值/7UNMODELED、时间错位与禁派工明确；0新设施/AI/研究，合并result见docs/reviews/20261110-direction-correction/result.json；待用户审查。

用户2026-11-11复核后推荐A，当前仅定义backup-support下UPS检修后未恢复投入问题，四类输入／接口缺口及参数化计算契约见docs/mainline/39r-backup-support-question.md，一手依据见docs/research/20261111-backup-support-sources.md；0新试验、未改原覆盖／风险律，待用户下一步指导。

A2原生UPS接口冻结v1红100d1fb2／绿d4432d5b一次通过，单一结果evidence/mainline/engineering/39r-ups-a2/result.json；8进入／4窗口24秒、0策略／模型／注册研究；v2仅修留存顺序，342e493f的CI42869801491为652／650通过、2既有可选跳过，旧CI42869253754取消保留；授权拒绝／risk_closed=false／父风险UNMODELED保持，待用户审查。

B1独立辅助后果契约docs/mainline/39r-backup-support-consequence.md，匹配探针d06fcb3f见evidence/mainline/engineering/39r-ups-b1/result.json；2进入／2窗口60秒、服务缺额28／28秒、三辅助负载各断供0.2／28秒、交流恢复右删失，零策略／模型／注册研究；A2获用户有限接受并分列v1／v2，A1与57未启动，父风险UNMODELED，待审。

A1第一段只核对合成树能产生非零差；原始算术记录evidence/mainline/engineering/39r-ups-a1-aux-tree/result.json原样保留，点值不作为证据或对外材料；一次算术、零设施或注册研究，父风险UNMODELED。

A1盈亏边界v1锁定0345d2d9；docs/mainline/39r-ups-a1-stage2-breakeven.md与evidence/mainline/engineering/39r-ups-a1-stage2-breakeven-v1/result.json保存四动作逐负载赢输区、83组×101先验点的精确核算；零设施或注册研究；三案例论文骨架paper/conditional-inspection-value-structure-20261111.md，主线冻结范围见进度账，待用户审阅。

Stage 3 证明与现场证据清单docs/mainline/39r-ups-a1-stage3-theorem.md：两方案可行时胜R的非空充要条件max(d_R−d_I,r_I−q_R)>k，全部合法不查动作取交集；同形叶子与观测组合明确，论文重定标题及180次证据范围；仅文档，v1原件、冻结范围与父风险UNMODELED保持，待审。

用户报告 Stage 3 定理独立核对通过。精确算术入口 `scripts/verify_theorem.py` 复核原83组×101先验点、精确分界和三个解析例，合并结果见 `evidence/mainline/engineering/39r-ups-a1-stage3-verification-v1/result.json`。论文附录和现场判决表已补；零新增设施、策略、模型和注册研究，父问题仍未建模，交付后待用户指导。

公开 CLI 边界与 `field` 模板见 `docs/mainline/39r-ups-field-tool.md`；合并结果 `evidence/mainline/engineering/39r-ups-field-cli-v1/result.json` 留存实现前4项通过／6项缺入口及实现后10项通过。单缺项给精确翻转条件，资格未知不排名；旧核验器及原件保留，零设施、模型、注册研究与全CI，父风险UNMODELED，待审。

用户报告冻结核验、10 个 CLI 用例及 `47/80` 边界均通过；已澄清缺失参数范围与观测先验判决的区别。六步模板 `docs/mainline/39r-risk-problem-template.md` 首次用于 `docs/mainline/39r-it-dependence-network-capacity.md`，其[后果复核](../../../evidence/mainline/engineering/39r-it-dependence-reuse-v1/result.json)复用已有 6 秒配对，核对 0／4.5 秒缺额。新增设施、模型和注册研究均为零，`it-dependence` 仍未建模，交审后等待单步指导。
