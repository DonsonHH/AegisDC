# 30: 预注册独立比较问题、指标和预算

**What to build:** 在运行效果研究前冻结假设、主要结果、成本/约束、方法、种子、场景和失败/重试规则。

**Blocked by:** 29

**Status:** resolved

**Milestone:** M5

- [x] 先定义研究问题和判据，再生成确认结果；不按好看结果改目标。
- [x] 开发/封存确认及不确定性/消融预算清楚，物理世界与外生条件可匹配。
- [x] 分组/独立统计单位预先确定，不把时间帧或重复方法当独立样本。
- [x] 冻结贡献类型与最近方法对照：哪些是既有思想、哪些是场景/接口/机制扩展，以及哪些主张本研究不具备证据；协议不能以改名或更复杂代替比较。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Accepted as a frozen protocol, before any effect execution.


Owner /root; isolated branch donson/mainline-30-protocol based on accepted 29 commit 3feccbb1. Worktree and live agent checks found no other owner. [Comparison design draft](../../../docs/mainline/30-comparison-design.md) fixes the initial interface mapping and evidence boundaries; no protocol or study run has started.


[Protocol](../../../docs/mainline/30-registered-comparison.md), [machine registration](../../../docs/mainline/30-comparison-protocol-v1.json), [source lock](../../../docs/mainline/evidence/30-protocol-lock.json), [root acceptance](../../../docs/mainline/evidence/30-root.json) and [fresh exact proof](../../../docs/mainline/evidence/30-root-delivery.json). Six development conditions and all 36 method inputs were verified without executing the facility or selector. Sealed phase inputs were not materialized. Next: 31 development only.
