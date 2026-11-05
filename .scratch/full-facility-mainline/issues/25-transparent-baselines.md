# 25: 在同一设施运行透明比较策略

**What to build:** 无人工、固定周期对照、FIFO及风险优先可通过同一动作和证据接口运行。

**Blocked by:** 24

**Status:** claimed

**Milestone:** M4

- [ ] 默认运行不生成固定全场Tour；周期策略仅为声明的对照。
- [ ] 人员、工具、保护规则和可获得信息一致，策略可选择不同使用方法。
- [ ] 每次选择/暂缓理由与不可行候选可追踪。
- [ ] 结合相关工作选择至少一个可公平实现的贴近问题基线，或具体说明其不适用约束；不只依靠弱对照支持先进性。记录模型知识、信息与计算代价差异。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

Owner `/root`, branch `donson/mainline-25-baselines`; accepted24source2b8d/512checks and publicationd487. Public current evidence/action/CLI seams remain the implementation boundary. No policy effect experiments before30.

Development milestone only: `c54b24aab132948737bd444ba0cc6aa2eed960e4` on the assigned branch adds a public no-human/FIFO selector, arrived-feedback resource book and expired-intention audit; 3 focused methods pass. See `docs/mainline/25-policy-execution.md` and `docs/research/20261105/baseline-selection.md`. Same-facility dynamic execution, periodic/risk/literature policies, authority/inspection/closure binding, frozen evidence and independent/root gates remain required. No formal25capture/full run or effect trial has run.

Development continuation `d683c0a5`: no-human/FIFO now share one advancing facility and actual crew/resources, predeclared inspection/intervention bindings and arrived-only actual inspection records.7policy methods and45targeted compatibility methods pass. Primary25stillclaimed; periodic/risk/literature policies, fixed-source/cost integration, CLI, independent frozen evidence and rootacceptance remain.
