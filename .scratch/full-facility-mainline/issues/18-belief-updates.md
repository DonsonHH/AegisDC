# 18: 建立随证据和时间变化的风险认识

**What to build:** 公开认知接口能对合理候选原因/参数状态更新，不直接读取当前真实世界。

**Blocked by:** 15, 16, 17

**Status:** resolved

**Milestone:** M3

- [x] 先验、状态演化和观测似然有来源或假设，相关/陈旧证据有适配模型。
- [x] 记录后验/区间与未识别项，可用合成已知生成过程检查校准。
- [x] 信息更新与物理维修分别记账；无证据不是0风险。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Implementation candidate: `docs/mainline/evidence/18.json`; source-frozen author capture and fresh Git delivery proof are documented in `evidence/mainline/engineering/18-beliefs/README.md`. The preserved author candidate originally awaited Root integrated full regression and independent review; the separate Root acceptance below now supplies both.

Root acceptance: `docs/mainline/evidence/18-root.json`; unified execution `49a40b760e6bab1a89c884e3ef466a45337a5e26` passed 434 checks with zero skips. Figures and review evidence: `evidence/mainline/engineering/18-root-acceptance/README.md`. Original author candidate remains pending by design; Root authority resolves this ticket.
