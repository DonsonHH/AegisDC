# 03: 跑通八域正常工况竖切片

**What to build:** 同一个全设施场景可运行正常负荷，返回物理、控制、服务、空间和人员的时间演化及独立边界账。

**Blocked by:** 02

**Status:** claimed

**Milestone:** M1

- [ ] 实际执行功率进入热账，外生未服务需求保留；各域不是固定占位返回值。
- [ ] M1已实现最低人员/工具/资格/占用与工程作业请求可行性规则：资格不符、工具占用或位置/访问不可达会拒绝请求，不能只有人员字段。预定请求仅为工程夹具，默认无工作项时不自动巡回。
- [ ] 电功率、质量、内能、库存、服务和人员可行性满足声明边界，正常初值与代数约束一致。
- [ ] 可重放结果标工程夹具/合成研究设定，含源配置/代码身份，默认无固定巡回和科研模型调用。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

This ticket includes the minimum observable personnel behavior needed by the M1 acceptance. Ticket 21 later extends it into evidence-driven heterogeneous parallel dispatch; it is not a hidden prerequisite for M1.

## Evidence

Implementation claimed on `donson/mainline-03-healthy`, worktree `full-site-03`,
based on integration commit `0e2e2a8e5faf98f6ee9870dc4adf0c94d077db15`.
Public verification boundaries are the scenario loader, facility run interface,
replaceable thermodynamic property interface, and CLI, as authorized by the
mainline specification. Acceptance evidence remains pending.
