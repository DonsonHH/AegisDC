# 13: 重放外生作业、故障与维护场景

**What to build:** 同一配置和外生事件可确定性重放，策略行动造成的内部状态差异仍被保留。

**Blocked by:** 11

**Status:** resolved

**Milestone:** M2

- [x] 外生需求/天气/扰动与行动引起的状态变化分开。
- [x] 输出含源哈希、种子/事件、时间步与失败状态；已有输出停止覆盖。
- [x] 工程夹具与注册研究尝试区分，失败和重试规则可追溯。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Review history: reopened after independent Spec review of `aaa4d8cb`: unsupported terminal /
declaration versions and malformed/incomplete lifecycle origins were not
authoritatively checked. The exact original probes and red observations are
preserved under `evidence/mainline/engineering/13-replay/review-AAA-spec/`.
The prior engineering capture/delivery/full counts below retain their actual
source identity. The correction is separately verified at execution
`cf9b33900d8f349b9a8145c042bbffe03503c858`, delivery
`3e508cbe3ce3c157ef4ad13d0b7d8d4d1f6e802e`; root review remains pending.

Reader-v2 follow-up: `docs/mainline/evidence/13-reader-v2.json` records strict
known terminal/declaration/lifecycle versions and typed authority, bounded v1
legacy compatibility, staged origin refusal and exact original bad bytes.
Eight new copy-only/public reader/replay/actual CLI tests plus the original
thirteen focused cases passed. The frozen v2 runbook generated five explicit
review-origin cases; all new refusals are FAILED requests with no plant
execution, while declaration-only historical state stays UNKNOWN.

`capture-04` has 239 declared artifacts plus receipt, 18 terminal requests
(6 completed / 12 expected failures), unchanged whole-facility exact/causal
checks, and one new-source full check: 345 discovered, 343 executed, zero
failures/errors, only two old optional Torch skips. Source/tool and 299 prior
durable records passed real fresh-checkout/Git-blob verification at
`.work/replay13-v2-fresh-3e508cbe-01`. Its separate receipt is
`evidence/mainline/engineering/13-replay/delivery-v2-3e508cbe-fresh-01.json`;
no physics/full rerun or runtime cache was required for delivery verification.

The attempted `capture-03` stopped before directory creation on the root
attribute-file CRLF/LF identity preflight (0 plant, 0 full). Its stderr/stdout,
original working-tree bytes and diagnostic are preserved under `preflight-03`.
Exact leaf attribute corrections preserve all historical bytes; root attribute
LF is anchored only at `/.gitattributes`. The old `13.json`, capture-01 FAIL,
capture-02 success and its 330/328 full remain unchanged. Shared numerical
source remains 8e; ticket 12 qualification/NO-GO is independent. This remains
an engineering implementation milestone, not M2 or research-goal completion.

Owner: `/root/mainline_13_replay`, branch `donson/mainline-13-replay`, worktree
`.work/worktrees/full-site-13`; integration base `77660da5` confirmed against
live agent/worktree inventory on 2026-11-05. Public scenario/run/save/replay and
actual CLI seams follow the accepted specification.

Implementation resolved with engineering checks and a real fresh-checkout
delivery proof; root's independent review/integration acceptance remains
pending. This resolution is neither numerical qualification of ticket 12 nor
completion of M2 or the complete research objective.

- Execution source `264e8423a8620d3a10bf3a9af863b212e9b37022` includes the
  coordinated `8e57abb9`/`8191244e` time/floor source and retains the distinct
  command origin. The actual root integration `08f2c1bc` is an ancestor.
- Data delivery `3e23431fc5a78b2748b1f72c3ed99a86fd2f8798` contains the
  separately frozen `capture-02` package. Its initial pending receipt is
  unchanged. The original `capture-01` FAIL at `79e2f926`, committed as
  `dcb118dc`, remains intact with all 139 original files and zero full runs.
- `docs/mainline/13-replay-contract.md` and
  `docs/mainline/13-replay-runbook.json` define command authority, exact source
  and interpreter replay, canonical conflict/order rules and private visibility.
- `evidence/mainline/engineering/13-replay/capture-02/receipt.json` records two
  exact full-facility pairs (600 s normal / 240 s combined), 31 inherited
  independent literals and all boundary/resource accounts; the command pair
  retains offered demand 2 each and delivers 2 versus 1 service-unit s through
  real valve/PLC/thermal changes. There are 13 terminal engineering/request
  records: 6 completed, 7 expected failures, one explicit retry. No-overwrite
  and malformed-JSON CLI refusals preserve original bytes.
- The single full check discovered 330 tests, executed 328 with zero failures
  or errors, and reported only the two pre-existing optional Torch skips.
  Twenty historical originals verify. The earlier failed capture ran no full
  check; it was not promoted after the adapter correction.
- Actual fresh checkout `.work/replay13-fresh-3e23431f-01` verified 142 declared
  artifacts plus terminal receipt, all runtime/tool identities, 139 retained
  failed-capture originals and committed Git blobs. The separate proof is
  `evidence/mainline/engineering/13-replay/delivery-3e23431f-fresh-01.json`.
  It reran neither physics nor the full suite and required no runtime caches.
- Reproduce capture with primary Python `-Xutf8
  scripts/capture_replay_engineering.py --output NEW_DIRECTORY`; verify from
  the fresh delivery using `scripts/verify_replay_delivery.py --directory
  evidence/mainline/engineering/13-replay/capture-02 --delivery-commit
  3e23431fc5a78b2748b1f72c3ed99a86fd2f8798 --output NEW_PROOF.json`.

Structured implementation evidence: `docs/mainline/evidence/13.json`.
Registered research/protocol/budget remains unopened; field calibration is
PENDING and effect/AI/training claims remain unestablished. Replay inputs,
future faults and actual trajectories are evaluator-private. Tickets 14-15
must expose only legally arrived evidence; professional inspection/repair and
dispatch remain later tickets. Fresh-read progress still reports current 12,
M2 in progress and the complete research objective active.
