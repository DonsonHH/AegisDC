# 07: 让房间、泄漏与访问条件影响作业

**What to build:** 房间空气、排水/泄漏与门禁状态能改变热边界及人员可达/作业可行性。

**Blocked by:** 03

**Status:** claimed

**Milestone:** M1

- [ ] 空气热与液冷热分别记账，凝露/泄漏判据及数据边界显式。
- [ ] 访问变化不能由电缆/管网图自动推导，路径与权限来自独立关系。
- [ ] 受限区不可直接进入或继续不满足条件的作业。
- [ ] 用03已实现的最低人员/工程作业接口演示访问状态实际改变请求可行性，M1无需等待21的完整证据驱动调度。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner: `donson/mainline-07-environment`, `.work/worktrees/full-site-07`, assigned
after root acceptance/integration of 03/04/05/06. Live worktree state checked;
base/integration tip `02423809d20fcd4541e8a16177f0e10371fb6f09`. Checks pending.
