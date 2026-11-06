# 27: 重放完整设施的跨系统闭环

**What to build:** 同一场景展示负荷上升、滤阻变化、维护下线和迟到证据如何经过保护、检查、处置与恢复。

**Blocked by:** 26, 13

**Status:** claimed

**Milestone:** M4

- [ ] 完整八域贯穿，不替换为单机柜或只画流程图。
- [ ] 观测依据决定认知，后台故障不直接决定派单。
- [ ] 输出是工程闭环证明，不把一次演示记作统计增益。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

Owner `/root/m4_27_loop`, branch `donson/mainline-27-full-loop`, worktree `C:/Users/Donson/.codex/worktrees/mainline27-full-loop/Renly`, initial accepted26 base8c1fd54b. Live root confirmed27unassigned; this branch owns its lifecycle until reviewed integration. First work is a full same-facility timeline contract and one public behavior slice, not a formal run or accepted ticket.

First contract: `docs/mainline/27-cross-system-loop-contract.md` fixes a proposed same V6 ten-second timeline and separates automatic service restoration, actual filter intervention and later multi-sample verification. `reference/independent-literals-v1.json` under27-full-loop contains pure Fraction flow/service/value expectations. The4second PLC/thermal recovery is explicitly conditional and remains to be independently checked. Two genuine interface gaps are identified: sampled actual delivered-service channel and versioned recorded online-dispatch transport/replay. No selector/plant/full/effect run has been called; contract review precedes the first public RED/GREEN slice.
