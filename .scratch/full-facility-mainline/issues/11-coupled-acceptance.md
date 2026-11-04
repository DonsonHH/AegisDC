# 11: 验收同一全设施模型的跨系统行为

**What to build:** 研究者可用受控事件展示八域均会通过明确路径影响服务或作业，且全场边界账成立。

**Blocked by:** 04, 05, 06, 07, 08, 09, 10

**Status:** resolved

**Milestone:** M1

- [x] 每域至少一个行为反例证明其不是目录占位；共享瓶颈与冗余容量实际改变结果。
- [x] 人员域用03的资格/工具/占用反例和07的访问变化验收；21负责后续调度扩展，不作为本票未声明的前置。
- [x] 模块接口无重复热/质量/服务记账，数值越界明确失败。
- [x] 八域完整范围保持，阶段报告区分已实现、数值验证和现场未标定。

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

Implementation verified; root review and M1 acceptance remain separate gates.

- Execution source/test/tools: `b135ecffb5fe5c3fecaa44859afbf925b8549bb1`,
  after merging the actual integration tip `743898591152da34643c96ede6adced004723464`.
  No runtime or V1-V6 config change was required.
- Formal originals: `evidence/mainline/engineering/11-coupled/fixtures-b135ecff-01/`
  delivered at `1625764dd4c79a408ff13c76e8189ab8a7994769`.
  Same-V6 17 cases, 129 independent literal conditions, three refusals,
  1272 states /1255 intervals, 125 declared durable artifacts plus receipt.
- Exactly one full acceptance: 306 collected /304 executed, zero failures or
  errors; two explicitly allowed existing optional Torch skips on this machine,
  no unexpected skips; 20 old originals passed. No research/model/training calls.
- Fresh checkout at the delivery revision passed source/execution and artifact/
  delivery Git/SHA checks: `delivery-readback-1625764d-fresh-01.json` in the same
  evidence parent, 88 source/tools and 15 prior records, zero caches required.
  The initial pending-delivery receipt remains unchanged; no physics/full rerun.
- Root Spec review identified one architecture visual-semantics error: the old
  author rendered bidirectional V6 access edges as one-way. Historical figures,
  b135 tools and 162 delivery remain immutable. Independent plot source
  `2727adfce8128feb543efd2f489d37eb4a9bbd73` produced `architecture-v2-01/`,
  delivered at `eb5df8e8bdd6448363b6bbcd29db86d439f22644`; five access edges now
  use their actual bidirectional flags, and a4 avoids loc_hx. The separate fresh
  visual readback verifies all 37 selected relations, three author/tools and
  original bytes; see `visual-delivery-readback-eb5df8e8-fresh-01.json`.
- Exact commands, scope, SI hand derivations, original/failure history and
  readable figures are linked by the evidence `README.md` and
  `docs/mainline/evidence/11-candidate.json`. The current architecture entrance
  uses v2 and explicitly marks the old architecture as historical.

This resolves the ticket implementation only. M1 remains `in_progress` in
fresh-read progress; root independent dual-axis review/integration/acceptance
controls its gate. Numerical qualification, exogenous replay, evidence/risk,
diagnosis, repair and recovery verification remain later work. This bounded
synthetic engineering delivery establishes no field calibration, method gain,
AI or RSI result; the complete research objective remains active.
