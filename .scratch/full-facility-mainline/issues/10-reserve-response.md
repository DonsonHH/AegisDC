# 10: 让UPS、柴油与维护改变保障能力

**What to build:** 受保负载、储能、柴油启动及备用冷源按容量和切换逻辑影响全场。

**Blocked by:** 04, 05

**Status:** ready-for-agent

**Milestone:** M1

- [ ] 储能能量/效率和接管延迟可核对，不能无限续航或默认全负载受保。
- [ ] 维护下线、切换失败和共同电源可降低冗余，不按设备数量推可用率。
- [ ] 备用冷源实际连接为研究设定，来源缺口继续保留。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

## Preparation (implementation not started)

Assigned design owner/worktree: `donson/mainline-10-reserve`,
`.work/worktrees/full-site-10`, created at actual integration `81416154`.
See `docs/mainline/10-reserve-design.md` for the primary-source boundary,
finite-energy/transfer proposal, paid effective cooling interface, 07/09
compatibility and independent hand acceptance cases. This round changes no
runtime/config and executes no tests, engineering simulation or effect study.
Status remains ready-for-agent pending the root's implementation follow-up;
the design is not acceptance evidence or M1 completion.
