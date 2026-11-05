# 23: 让处置延时、残余效果与服务响应闭环

**What to build:** 切换、清理/维修、调整负荷等研究动作在授权、工时和物理约束下改变设施。

**Blocked by:** 20, 21

**Status:** claimed

**Milestone:** M4

- [ ] 动作完成延时和中断可能导致不同结果，不瞬间无成本修复。
- [ ] 外生需求保留，服务降级与实际发热同步。
- [ ] 修复/切换效果及残余风险可核对，失败动作不会记成功收益。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

Apply `docs/mainline/information-boundary.md` to proposal validation and execution acknowledgments. Backend safety checks may use actual state; information returned to dispatch needs a declared channel, timing and resource accounting, including failed attempts. Repeated zero-cost rejection queries cannot become an undeclared inspection mechanism.

## Evidence

Pending implementation and acceptance.

Assigned independent ready slice: `/root/m4_23_intervention`, branch `donson/mainline-23-intervention`, managedworktree `C:/Users/Donson/.codex/worktrees/mainline23-intervention/Renly`. Blockers20/21 accepted; primary22 unchanged. Physical effects require separate Root acceptance.
