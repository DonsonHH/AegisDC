# 13: 重放外生作业、故障与维护场景

**What to build:** 同一配置和外生事件可确定性重放，策略行动造成的内部状态差异仍被保留。

**Blocked by:** 11

**Status:** claimed

**Milestone:** M2

- [ ] 外生需求/天气/扰动与行动引起的状态变化分开。
- [ ] 输出含源哈希、种子/事件、时间步与失败状态；已有输出停止覆盖。
- [ ] 工程夹具与注册研究尝试区分，失败和重试规则可追溯。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner: `/root/mainline_13_replay`, branch `donson/mainline-13-replay`, worktree
`.work/worktrees/full-site-13`; integration base `77660da5` confirmed against
live agent/worktree inventory on 2026-11-05. Public scenario/run/save/replay and
actual CLI seams follow the accepted specification. Implementation and
acceptance evidence pending; this claim is not M2 or research completion.
