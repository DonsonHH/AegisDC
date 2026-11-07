# 29: 冻结可行参数域和模型可信度边界

**What to build:** 研究者明确哪些结论来自概念/数值验证、合成比较或现场数据，并定义物理可行的参数域。

**Blocked by:** 12, 28

**Status:** resolved

**Milestone:** M5

- [x] 参数联动满足几何/守恒/容量/物性约束，不任意独立抽样。
- [x] 公开数据只在适用模块和年代边界使用，不自动校准郑州。
- [x] 未知现场参数保持缺口，合成范围与敏感性选择可追溯。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Accepted at the declared finite synthetic engineering scope.

Owner `/root`, branch `donson/mainline-29-uncertainty-domain`, isolated worktree `C:/Users/Donson/.codex/worktrees/mainline29-uncertainty-domain/Renly`, base accepted M4 `3f918a94`. Progress/refs/worktrees/agents/processes checked; no conflicting owner.

[Joint-domain contract](../../../docs/mainline/29-uncertainty-domain-contract.md) separates scalar, joint, finite numerical and field evidence. [Reproducible V6 provenance inventory](../../../evidence/mainline/engineering/29-uncertainty-domain/reference/v6-parameter-inventory-v1.json) accounts for all 113 parameters (106 assumptions and 7 synthetic reference derivations), all eight domains and four relation types, and four site gaps kept null. The pinned author/verifier used accepted M2/M4 and tickets12/28; stdlib-only verification passed, zero project/physical/research calls. Joint generator/negative boundaries and scientific qualification remain pending.


Root acceptance at c6197fc857b8032109328f6e68aa75b03c717268: eight complete trajectories (33.0 s), no reruns, with 576/576 integrated tests, 20 historical originals, and two independent saved-data reviews. [Report and figures](../../../evidence/mainline/engineering/29-uncertainty-domain/README.md), [root authority](../../../docs/mainline/evidence/29-root.json), [fresh Git proof](../../../docs/mainline/evidence/29-root-delivery.json). Four unresolved site values remain null. Next dependency frontier is 30, before any registered effect trial.
