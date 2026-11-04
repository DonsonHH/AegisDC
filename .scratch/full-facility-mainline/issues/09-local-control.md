# 09: 使本地控制与自动保护实际响应

**What to build:** 本地传感、泵阀命令、保护和失联模式改变物理响应，独立于巡检调度。

**Blocked by:** 04, 05, 06

**Status:** resolved

**Milestone:** M1

- [x] 采用有依据或声明的阈值、滞回/延时/饱和；保护不等待人员到达。
- [x] 控制可见测量和调度可见证据不同，测量偏差可影响实际控制。
- [x] 失联/传感错误情景有明确自治及恢复模式。

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

Implementation started after root acceptance of 07/08 at integration `98fd8c4b`; the public loader/run/CLI and independently varying local-control component are the authorized seams. Signed offsets must not relax physical quantity ranges.


## Implemented engineering evidence

Interface `4619dbfd`, behavior/runbook freeze `90c76618`, actual committed
execution `363c5edf57554c99f80f92030d691d6e1ff4428d`. The earlier preparation
section is historical; implementation was subsequently authorized after root
acceptance of environment-v4 and service ticket 08.

- Independent `control-v5` derives from accepted environment-v4, with identical
  graphs and explicit `local_control_profile`. It requires five SI/source/range
  parameters. Dedicated signed-offset quantities do not relax actual physical
  quantity domains. Static and timed validity/link values are strictly 0/1.
- A public measurement-only local transition module implements biased/invalid
  local channels, actual sampled protection and pump hysteresis, autonomous
  local control under supervisory loss and fresh-valid-sample latch recovery.
  Power cycling cannot erase a held latch. Reports remain LOCAL_PLANT_ONLY;
  no perfect outward evidence or dispatch adapter is created.
- Prior dynamic water/leakage/floor/room-access physics is retained, including
  its post-control equality order. ENVIRONMENT_MODELS and WATER_MODELS remain
  independently extensible for later explicitly validated runtime variants.
- Sixteen focused loader/component/run/CLI tests pass. Real red/green, including
  unknown signed types/profile and a huge-integer OverflowError, is preserved.
  Literal hysteresis/sample-time and service accounts are independently stated.
- Twelve saved same-facility successes, including one actual CLI and combined
  leakage/control interruption, plus six invalid-request refusals are frozen
  and fresh-read checked; 74 artifact hashes/counts/source accounts match.
- Single full author acceptance: 263 discovered /261 executed, no failures/errors,
  exactly two existing optional Torch skips, no unexpected skip, twenty original
  evidence hashes valid. Root owns independent review/combined enabled-Torch
  acceptance; no zero-skip author claim is made.

Entry: `docs/mainline/local-control-verification.md` and
`evidence/mainline/engineering/09-control/README.md`; local receipt
`receipt-363c5edf.json`, full `acceptance-363c5edf/summary.json`, saved artifacts
`fixtures-363c5edf/receipt.json` (last three relative to the evidence directory).
V1-V4, frozen property data, original outputs and CLI defaults retain their bytes.
This resolves a finite ticket implementation slice, not root acceptance or M1.
Research/AI/training trials remain zero, field calibration PENDING, scientific
gain NOT_ESTABLISHED and the overall mainline goal ACTIVE.

Post-integration: accepted tip `de5dbc69` merged at `bcad4042`; the sixteen
control targets and sealed artifact/source/legacy-input reads pass again in
attempts 26/27. Execution remains attributed to `363c5edf`; full regression and
engineering runs were not repeated for a documentation/figure integration.
