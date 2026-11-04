# 09: 使本地控制与自动保护实际响应

**What to build:** 本地传感、泵阀命令、保护和失联模式改变物理响应，独立于巡检调度。

**Blocked by:** 04, 05, 06

**Status:** ready-for-agent

**Milestone:** M1

- [ ] 采用有依据或声明的阈值、滞回/延时/饱和；保护不等待人员到达。
- [ ] 控制可见测量和调度可见证据不同，测量偏差可影响实际控制。
- [ ] 失联/传感错误情景有明确自治及恢复模式。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

## Preparation (implementation not started)

Assigned owner/worktree: `donson/mainline-09-control`,
`.work/worktrees/full-site-09`, prepared at integration `e12a2d76`.
See `docs/mainline/09-control-design.md` for the source/assumption review,
07-compatible explicit profile and public run acceptance proposal. Ticket 07's
owner confirmed `local_control_profile` as a later 09 extension; unsupported or
unimplemented values must be rejected until behavior is implemented. This round
changes no runtime source/config and performs no engineering acceptance run.
Status remains ready-for-agent pending the root's implementation follow-up.
