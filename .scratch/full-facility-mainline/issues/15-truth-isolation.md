# 15: 验证决策视图不泄漏真实故障

**What to build:** 相同可用证据下，调度输入与动作不因后台不同隐藏状态直接变化。

**Blocked by:** 14

**Status:** resolved

**Milestone:** M3

- [x] 调度API只收到允许的静态知识与证据，无后台对象/未来标签引用。
- [x] 隐藏故障本身不自动生成已知问题；必须经过声明的观测通道。
- [x] 保护使用本地测量的例外不扩展为调度全覆盖权限。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

Include the candidate/action masks, feasibility queries and operational feedback from `docs/mainline/information-boundary.md` in the paired-hidden-state audit. Equal available records must produce equal pre-observation dispatch inputs and choices; later differences require declared, timed evidence. Private safety interlocks remain active.

## Evidence

Owner `/root/mainline_12_method_spec`, branch `donson/mainline-15-truth`,
worktree `.work/worktrees/full-site-15`, base
`6fe8313d5780bbda86c4c9bec51071a570f0fd72`. The pre-created clean tree and
accepted ticket-14 gate were checked before claim. The authorized public seams
are the evidence-only current decision frame, pure candidate/feasibility query
and CLI/tracer; implementation uses one red/green behavior slice at a time.
No extra permission gate is inferred from TDD. Root owns independent review and
acceptance; full M3 and the research goal remain active.

Continuation owner `/root/m3_15_continue` verified the preserved dirty tree and
the root-confirmed absence of the old owner before resuming. The root liveness
record `56bcfe23af09c54f2e5927fe21cf87fdd17e8820` was merged normally before
freezing; no reset, cleanup or other ticket's implementation was changed.
The current source includes nine red/green public-interface slices, the
canonical V6 public input authoring tool, actual paired private-world audit,
capture/data-figure tools and a read-only fresh Git-delivery verifier. The
development green log is not a frozen-source formal capture. Root review and
acceptance remain pending.

Root acceptance: `docs/mainline/evidence/15-root.json`. The integrated execution at `777ee58541a4cb2be2ff200de2ac135c6f13affe` passed all 420 checks. See `evidence/mainline/engineering/15-17-root-acceptance/README.md`.
