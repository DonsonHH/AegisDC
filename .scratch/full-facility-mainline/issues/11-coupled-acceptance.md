# 11: 验收同一全设施模型的跨系统行为

**What to build:** 研究者可用受控事件展示八域均会通过明确路径影响服务或作业，且全场边界账成立。

**Blocked by:** 04, 05, 06, 07, 08, 09, 10

**Status:** claimed

**Milestone:** M1

- [ ] 每域至少一个行为反例证明其不是目录占位；共享瓶颈与冗余容量实际改变结果。
- [ ] 人员域用03的资格/工具/占用反例和07的访问变化验收；21负责后续调度扩展，不作为本票未声明的前置。
- [ ] 模块接口无重复热/质量/服务记账，数值越界明确失败。
- [ ] 八域完整范围保持，阶段报告区分已实现、数值验证和现场未标定。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner: `/root/mainline_11_coupled`, branch `donson/mainline-11-coupled`,
worktree `.work/worktrees/full-site-11`; confirmed no duplicate live owner and
started from integration `cb249b611a9fee3d87a974524786ce2c014bbb55`.

Public seams: `load_scenario`/validation, `simulate_scenario`/describe/save,
and the actual CLI, as authorized by the specification. Acceptance will keep
one V6 identity across all eight domains; engineering fixtures are not
registered effect studies. Implementation and acceptance in progress.

Source/test/tool freeze is prepared in `docs/mainline/11-coupled-acceptance.md`
and `docs/mainline/11-coupled-runbook.json`: 17 same-V6 engineering cases,
129 independent literal conditions, three explicit refusals and 17 public-seam
tests. Draft public tests and saved-port conservation checks pass; retained
preparation failures distinguish a missing runbook, an author drainage
arithmetic error and a verifier's external-versus-internal floor-energy field
classification. None changed the accepted runtime or V1-V6 snapshots.

Formal immutable capture, one full suite and fresh-checkout delivery are still
pending. M1 and the complete research goal remain in progress.
