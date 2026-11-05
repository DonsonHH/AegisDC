# 15: 验证决策视图不泄漏真实故障

**What to build:** 相同可用证据下，调度输入与动作不因后台不同隐藏状态直接变化。

**Blocked by:** 14

**Status:** claimed

**Milestone:** M3

- [ ] 调度API只收到允许的静态知识与证据，无后台对象/未来标签引用。
- [ ] 隐藏故障本身不自动生成已知问题；必须经过声明的观测通道。
- [ ] 保护使用本地测量的例外不扩展为调度全覆盖权限。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

Include the candidate/action masks, feasibility queries and operational feedback from `docs/mainline/information-boundary.md` in the paired-hidden-state audit. Equal available records must produce equal pre-observation dispatch inputs and choices; later differences require declared, timed evidence. Private safety interlocks remain active.

## Evidence

Pending implementation and acceptance.
