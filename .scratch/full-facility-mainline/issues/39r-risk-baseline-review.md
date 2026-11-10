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

A2原生UPS只读／恢复接口在同一测试红100d1fb2、绿d4432d5b一次通过，单一结果evidence/mainline/engineering/39r-ups-a2/result.json；8进入／4完成窗口24秒、0策略／模型／注册研究，授权拒绝及risk_closed=false保持，父风险仍UNMODELED，待审后按单步指导。
