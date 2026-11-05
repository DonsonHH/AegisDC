# 24: 用恢复证据关闭问题

**What to build:** 处置完成后，问题根据可用复检和服务恢复记录转为验证关闭或继续开放。

**Blocked by:** 22, 23

**Status:** resolved

**Milestone:** M4

- [x] 处置结束不自动等于恢复和关闭。
- [x] 症状暂退、未确认、误报、升级/接受风险的状态清楚。
- [x] 闭环轨迹包含各事件时刻与所用证据，不补未来信息。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

Owner `/root`, branch `donson/mainline-24-closure`; reuse clean accepted23worktree.22/23 accepted at published41cb9eec. Public decision-frame/ledger and CLI seams remain authorized; closure must cite arrived post-action evidence, never private evaluator truth.

Root acceptance: `docs/mainline/evidence/24-root.json`; source `2b8d224a6d6605b2898117438573d738dae28023`, 512 executed checks/zero skips, Spec1267 and Standards453 saved checks. Both formal captures and all original review failures preserved.
