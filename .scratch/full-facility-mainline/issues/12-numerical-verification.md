# 12: 用独立算例验证数值与步长

**What to build:** 研究者能核对解析/手算守恒、事件顺序、量纲及步长收敛，发现误差边界。

**Blocked by:** 11

**Status:** resolved

**Milestone:** M2

- [x] 预期来自独立手算/解析或外部可信参考，不由被测实现重新计算同一答案。
- [x] 正常、零流、失电、容量紧张及相变域边界均有相应声明。
- [x] 细化步长的关键结果变化可量化，误差大时不进入效果研究。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner `/root/mainline_12_numerical`, branch `donson/mainline-12-numerical`,
worktree `.work/worktrees/full-site-12`, actual integration base `77660da5`.
Active assignment and Git worktree state checked before claim. Public seams are
the already approved loader, full-facility run/save and replaceable property
interfaces; no new permission gate is inferred from TDD. Implementation and
declared finite engineering checks resolved; root full-ticket acceptance remains
pending and no M2/global progress was changed by this implementer.

- Final entry: `evidence/mainline/engineering/12-numerical/final-entry-01/`;
  11 declared full-V6 conditions with explicit candidate/operating/reference
  ladders, 102 lossless original ZIPs / 408 members / 306705 states.
- Source `dac0df3d`, delivery `39d48b67`, exact fresh readback
  `evidence/mainline/engineering/12-numerical/final-entry-fresh-proof-01.json`.
  Original v1/v2 NO-GO and all failed captures remain unchanged.
- Frozen protocols: `docs/mainline/12-numerical-runbook.json`,
  `12-numerical-refinement-v2.json`, `12-numerical-resolution-v3.json`.
  Qualification scope/limitations: `docs/mainline/12-numerical-qualification.md`.
- Genuine red/green: one-ULP event spelling caused an entire PLC period of
  delay; rounded floor crossing delayed a work abort by .5 s; explicit empty
  endpoint needed consistent empty/refill closure. Physical inventories/quality
  are not hard-clipped and conservation tolerances were not relaxed.
- Independent analysis P2 retained and closed using full closed-window amplitude
  checks, old raw/NO-GO kept. Independent original probes and closure reports
  archived as inert exact-byte ZIP members; 28 independent + 16 author targets,
  zero new findings, no physical/full rerun.
- One full acceptance: 317 discovered, 315 executed, 0 failures/errors,
  2 old optional-Torch skips; 20 historical originals verified. Fresh v1/v2/v3
  and final-entry receipts separately prove exact execution/delivery bytes.
- Recommended .01 s is a finite-fixture operational setting. Five original
  .025/.02/.01 ladders do not provide a newly finer .01 reference or a continuous
  parameter-box guarantee. Metric is event-side-anchor/phase-consistent with
  causal raw and actual event-time errors separate, not a raw true-error bound.
- Field calibration pending; registered research / training / LLM calls 0;
  effect, agent and RSI gains not established. Root owns the later acceptance.

## Preserved input for the later qualification

The independent 04–06 review retained a 432-case frozen-row mixture
representation probe, including five mass-scaled nominal pure-vapor inputs
strictly refused after encoded M/U/V reconstructs x=1.0000000000000002.
The exact inputs, hexadecimal values, outcomes, implementation/table identities
and a standalone reproducer are in
`evidence/mainline/engineering/04-06-root-acceptance/endpoint-representation/`.
Quantify this floating-point representation boundary together with the physical
domain; do not silently clip quality, assume every nominal construction is
exactly admissible, or call the finite probe empirical validation. This note
does not start ticket 12 ahead of blocker 11.
