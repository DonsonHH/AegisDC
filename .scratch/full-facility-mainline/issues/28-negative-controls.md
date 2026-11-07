# 28: 验证正常、误报和来不及挽救的情景

**What to build:** 系统能合理处理无问题、误报、直接保护和人工无法及时干预的情况。

**Blocked by:** 27

**Status:** claimed

**Milestone:** M4

- [ ] 检查不保证必有收益，资源成本与服务结果都入账。
- [ ] 快速保护不由人员移动替代，失败/未确认不抹除。
- [ ] 异常族和初值不只挑适合候选策略的有利条件。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

Owner `/root`, branch `donson/mainline-28-negative-controls`, isolated worktree `C:/Users/Donson/.codex/worktrees/mainline28-negative-controls/Renly`. Accepted predecessor `96b3c2b7`, refreshed integration tip `7dabde7d`. Progress, worktree, process and live agent checks found no existing implementer.

[Proposed finite contract](../../../docs/mainline/28-negative-controls-contract.md): normal, false report with real paid verification, local protection, and too-late safety abort in the same V6 facility. All targets and budgets remain to be independently reviewed and frozen. No model, selector, plant or registered effect trial called.
