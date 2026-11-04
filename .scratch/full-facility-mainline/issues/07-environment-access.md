# 07: 让房间、泄漏与访问条件影响作业

**What to build:** 房间空气、排水/泄漏与门禁状态能改变热边界及人员可达/作业可行性。

**Blocked by:** 03

**Status:** resolved

**Milestone:** M1

- [x] 空气热与液冷热分别记账，凝露/泄漏判据及数据边界显式。
- [x] 访问变化不能由电缆/管网图自动推导，路径与权限来自独立关系。
- [x] 受限区不可直接进入或继续不满足条件的作业。
- [x] 用03已实现的最低人员/工程作业接口演示访问状态实际改变请求可行性，M1无需等待21的完整证据驱动调度。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner: `donson/mainline-07-environment`, `.work/worktrees/full-site-07`, assigned
after root acceptance/integration of 03/04/05/06. Live worktree state checked;
base/integration tip `02423809d20fcd4541e8a16177f0e10371fb6f09`.

- Implementation `ab6094bf`; merged accepted service ticket 08 from integration
  `5da91789`, with committed run source `5ca3c3a03d05802458cef1bdd10e66928d75bc1b`.
  Public seams are `load_scenario`/`validate_scenario`, `floor_water_step`,
  `condensation_risk`, `simulate_scenario`, `save_run` and the explicit model CLI.
- New independent profile `configs/full-facility-mainline-environment-v4.json`
  retains eight domains, paid water/valve behavior and the healthy working point.
  V1/V2/water-V3 snapshots, frozen property reference, schema and CLI defaults are
  unchanged. The model explicitly registers its one supported topology; unknown
  graphs or unimplemented control-profile declarations fail rather than silently
  run ideal behavior. Source choices, equations, applicability and interfaces are
  in `docs/mainline/environment-verification.md`.
- Actual hot-water leakage debits dynamic hot mass and matching cp*T sensible
  energy, and moves each into the separate floor pool once. Cold/refrigerant/lake
  identities are not debited. The pool mixes analytically and drains at its actual
  evolving temperature. Original `floor_water_inflow` remains separately declared
  external ambient nuisance water, never cooling leakage or makeup.
- The minimum remaining hot inventory explicitly bounds the constant hydraulic
  approximation. Crossing below it fails without clipping or an invented pump/
  suction/low-inventory model. Condensation uses verified primary-source liquid-
  water saturation coefficients and a labeled cold-buffer bulk surface proxy;
  its bounded criterion creates no condensate, latent heat or dispatch alarm.
- `it_access_gate`/binary permission, floor threshold and declared room work-
  temperature threshold independently constrain personnel access. The latter is
  a research rule, not a site/occupational limit. Rising/falling crossings split
  steps; equality uses actual post-control heat direction, with stationary initial
  equality closed. Room sensible and liquid heat remain separately accounted.
- Existing 03 qualification/tool/shift/path interfaces execute the work. Closed
  permission rejects new entry, aborts active work with spent time/actual locations
  retained, and checks a closed destination before entry at its declared gate.
  No continuous geometry, instantaneous evacuation or teleportation is claimed.
- Independent examples: 1000→996 kg at unchanged 320 K with 4 kg/5.12 MJ moved to
  the floor; variable-mass 315 K /12.4 MJ drain; constant-mass 312.64241117657116 K
  analytic tank; actual leak access crossing at 100/19 s; 1.5 s air-heat work cutoff
  and .49019607843137253 s cooling recovery before a midstep request.
- Real numerical failures are preserved: the root's initial 49 refusals in 108
  valid zero-drain probes, the local reproduced red, and lost small positive
  exports. Known zero boundaries and a stable expm1 drain integral fix these
  without arbitrary heat clipping. Root's full 108-input green and local 49-case
  replay are retained with honest source/dirty-state labels. A mixed tiny drain
  matches a separate 70-digit Decimal analytic reference. The stale pre-control
  threshold-direction failure is also retained before its actual-heat fix.
- Numbered command/source/input-SHA checks are under
  `evidence/mainline/engineering/07-environment/`. All 22 environment tests pass.
  `fixtures-5ca3c3a0/` has nine clean-source successful runs plus an explicitly
  expected domain failure, frozen engineering runbook and attempt ledger; each
  actual file is freshly re-read for SHA/count and independent physical accounts.
  A distinct CLI case/fresh read retains .95 kg actual hot loss and no nuisance
  mass input. Normal 600 s is stable with zero deficit.
- Full acceptance `acceptance-5ca3c3a0/summary.json`: engineering/evidence/overall
  PASS; 247 discovered /245 executed; zero failures/errors; exactly two existing
  optional isolated-Torch skips; no unexpected skips; 20 original evidence files
  hash-valid. Compile and scoped whitespace checks pass. Root owns enabled-Torch
  verification, independent dual-axis review and integration acceptance.

This resolves the finite ticket-07 implementation slice, with root acceptance
pending. M1 remains in_progress and the complete research goal active. No global
progress, earlier raw artifact or another owner's implementation was overwritten;
research/AI/training trials remain zero, field calibration PENDING and scientific
gain NOT_ESTABLISHED. Moisture/latent balance, physical leak-pressure laws, site
geometry/limits, coolant makeup, low-inventory pump behavior, emergency egress,
step convergence and evidence-driven intervention remain separate work.
