# 22: 把检查执行与现场证据接起来

**What to build:** 被分配者到场、用时检查并返回有限覆盖/带误差的结果，期间全场继续运行。

**Blocked by:** 17, 21

**Status:** resolved

**Milestone:** M4

- [x] 到访、观察、专业确认是不同事实，失败/未确认均保留。
- [x] 真正完成时才产生记录，不在派单时泄漏结果。
- [x] 检查时间/可靠度依专业工具与工况声明，不能只靠随机成功标志替代测量。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

Assigned independent ready slice: `/root/m4_22_inspection`, branch `donson/mainline-22-inspection`, managed worktree `C:/Users/Donson/.codex/worktrees/mainline22-inspection/Renly`. Predecessors17/21 accepted; primary remains20. Real completion/measurement integration requires its own acceptance.

Implementation candidate: `docs/mainline/evidence/22.json`; actual source5486/data6812,1formal3srun, saved-only fresh proof and visual readback. Independent reviews and Root full/acceptance remain pending; ticket remainsclaimed.

Root acceptance: `docs/mainline/evidence/22-root.json`; actual source`e33ff63a4a110a00cbce640fa267dff7c2da48bf`, 490 executed checks with0skips and1427independentassertions. Author candidate and pendingreceipt remain their historical snapshots; Root authority resolves this ticket.
