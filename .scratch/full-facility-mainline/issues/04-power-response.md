# 04: 在全场传播供电容量和失电

**What to build:** 改变馈线、整流容量或供电状态，会按真实连接影响IT和辅机及服务。

**Blocked by:** 03

**Status:** claimed

**Milestone:** M1

- [ ] 级次和转换损耗守恒，容量不足不能凭空多供电。
- [ ] 停电后的发热取实际供电功率；需求缺额继续计量。
- [ ] 馈线/负载关系有来源或假设，图可达不等于整站必停。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Assigned implementation: `donson/mainline-04-power`, worktree
`.work/worktrees/full-site-04`, owner `mainline_04_power`. The live assignment and
worktree were checked before claiming on 2026-11-04; starting integration commit
is `0ee160cdcdbd195acf35d552abd8040ef7e55b5c`. Public verification boundaries are
`simulate_scenario`/CLI and the electrical component interfaces used by that run.

Pending implementation and acceptance. Engineering fixtures only; no registered
research trial, training run or AI call.
