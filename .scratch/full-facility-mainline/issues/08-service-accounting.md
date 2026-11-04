# 08: 让计算、网络和存储决定服务缺额

**What to build:** 服务账根据需求、实际可供计算/网络/存储能力及降载状态产生可解释结果。

**Blocked by:** 03

**Status:** claimed

**Milestone:** M1

- [ ] 同一服务的重叠故障不重复计损失，组件可用不等于整项服务可用。
- [ ] 外生作业需求与实际执行负载分开，调整/推迟任务不删除应计服务需求。
- [ ] 容量/速率和FLOP/s口径明确，不从MW反推算力。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner: `donson/mainline-08-service` in `.work/worktrees/full-site-08`, based on
integration `454408e33bc39a45a87ac2799c8dfd8ceff0a4ae` (2026-11-04).

The accepted scenario/run and CLI seams are used. The existing joint-service
minimum and independent requested/delivered accounts are retained; timed changes
to the three already declared normalized component capacities are the missing
engineering input behavior. Work remains in the complete eight-domain scene;
no queue, scheduler, policy comparison, FLOP/s calibration or research trial is
introduced.
