# 16: 让稀疏测点、偏差和迟到形成可用信息

**What to build:** 固定测点可稀疏、停用、有噪声或延迟；控制和记录按各自时刻更新。

**Blocked by:** 14

**Status:** ready-for-agent

**Milestone:** M3

- [ ] 测点掩码不是全资产数组的隐含真值。
- [ ] 测量误差/偏差和共同来源机制可单独改变；观测与故障过程不硬绑定成必报。
- [ ] 无固定测点输入时，历史/人工/现场证据路径仍可工作。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

The user confirmed that fixed sensors exist but cannot cover every location because of cost and other constraints (ADR 0002, 2026-11-05 clarification). Include sparse fixed measurements in the primary scenario. Missing/disabled/no-fixed-input cases test information availability; they do not redefine the primary facility as sensor-free. Historical/asset records, human reports/work orders and on-site portable measurements remain allowed evidence sources.

## Evidence

Pending implementation and acceptance.
