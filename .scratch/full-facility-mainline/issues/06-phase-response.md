# 06: 闭合相变库存、内能和冷凝响应

**What to build:** 设备热量经声明的纯工质参考模型与冷凝接口进入内循环，可追踪相库存和压力/适用域。

**Blocked by:** 03

**Status:** claimed

**Milestone:** M1

- [ ] 采用同一EOS/一致物性表或明确受限变体，具名参考工质不当作郑州已知冷媒。
- [ ] 固定容积M/U与相平衡一致，内部相变不增减总质量或重复添加潜热。
- [ ] 越出两相/物性/压力域时明确切换或失败；不能夹回状态掩盖能量残差。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner: `donson/mainline-06-phase` in `.work/worktrees/full-site-06`, based on
integration `0ee160cdcdbd195acf35d552abd8040ef7e55b5c` (2026-11-04).

Public behavior checks use `SaturationTable.from_file` / `at_pressure` / `flash`
and `simulate_scenario` with the accepted v2 eight-domain scenario. Ticket 03
already implements the fixed-volume equilibrium state update; ticket 06 accepts
or corrects that implementation against conservation and frozen independent-input
EOS examples. No facility milestone or research gain follows from this fixture.
