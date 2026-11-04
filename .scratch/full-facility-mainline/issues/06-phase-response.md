# 06: 闭合相变库存、内能和冷凝响应

**What to build:** 设备热量经声明的纯工质参考模型与冷凝接口进入内循环，可追踪相库存和压力/适用域。

**Blocked by:** 03

**Status:** resolved

**Milestone:** M1

- [x] 采用同一EOS/一致物性表或明确受限变体，具名参考工质不当作郑州已知冷媒。
- [x] 固定容积M/U与相平衡一致，内部相变不增减总质量或重复添加潜热。
- [x] 越出两相/物性/压力域时明确切换或失败；不能夹回状态掩盖能量残差。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner: `donson/mainline-06-phase` in `.work/worktrees/full-site-06`, based on
integration `0ee160cdcdbd195acf35d552abd8040ef7e55b5c` (2026-11-04).

Public behavior checks use `SaturationTable.from_file` / `at_pressure` / `flash`
and `simulate_scenario` with the accepted v2 eight-domain scenario. Ticket 03
already implements the fixed-volume equilibrium state update; ticket 06 accepts
or corrects that implementation against conservation and frozen independent-input
EOS examples. No facility milestone or research gain follows from this fixture.

Implementation: `1562473b6afe6d49c8a60961cf275e7449c0a1bc`.

- `docs/mainline/phase-domain.md` records source facts, assumptions, private-state
  boundary, shared condenser interface and the pressure/two-phase limits.
- Frozen reference remains CoolProp 8.0.0 / HEOS / R134a / DEF, table SHA
  `9494001ac94e04c6b2474b1c70fdf78ff4b5958b3f5c39f9790581561097329c`;
  the actual Zhengzhou coolant is unknown. No new runtime dependency is added.
- A real endpoint defect was reproduced before correction: four of fourteen
  frozen external-EOS saturation cases were incorrectly refused. The inverse now
  checks already-admissible segment endpoints with an eight-ulp energy condition.
  Dryness and physical pressure are not clipped; finite 0.1 J/kg endpoint-domain
  excursions still fail. All nonendpoint root and uniqueness checks remain.
- `tests/test_mainline_phase.py`: eleven public-interface tests, all executed,
  no skips/failures/errors. Coverage includes nine independent-input EOS M/U/V
  states, fourteen EOS saturation endpoints, four single-phase/pressure-domain
  refusals, invalid/zero/boolean inputs, a nonunique algebraic negative fixture,
  full-facility +/-2 MJ hand cases, reciprocal signed condenser/water energy,
  stopped-flow stored heat, high/low filling and runtime upper-domain exit.
- `evidence/mainline/engineering/06-phase/red-green.md` and
  `red-endpoints-01/` retain the actual failure and each behavior-slice check.
  Existing ticket-03 behavior passed on first observation; no implementation
  was artificially broken to manufacture a red result.
- `eos-reference-01/direct-eos-reference.json` is authored by a separate offline
  program using direct CoolProp PQ and Dmass/Umass calls with frozen numerical
  limits. The author never imports AegisDC; the tests/run consume only JSON.
  These and the earlier 25 flashes /543 off-grid probes are finite numerical
  checks of the same EOS, not independent empirical/site validation.
- `runs-1562473b-01/receipt.json`: eleven fresh complete-facility engineering
  runs plus five expected refusals, 47 saved-artifact hashes freshly checked.
  Same eight-domain scene, fixed M/V and no open coolant flow. The first-step
  +/-2 MJ cases change U exactly once; condenser loss equals the water gain.
  Maximum phase/mass residual is `2.2737367544323206e-13 kg`; maximum interval
  energy residual is `3.87127511203289e-6 J` (whole-run `4.328787326812744e-6 J`).
- `acceptance-1562473b-01/summary.json`: engineering/evidence/overall PASS,
  190 discovered /188 executed, zero failures/errors, exactly two pre-existing
  optional Torch checks skipped because that isolated library is absent from
  this interpreter path; no unexpected skips. All twenty original-file hashes
  pass. Compilation and `git diff --check` pass. Root owns enabled-Torch and
  independent integration review.

All paths after the documentation/test pointers are under
`evidence/mainline/engineering/06-phase/`. The accepted v2 model, table, prior
engineering originals, legacy patrol sources and global progress are unchanged.
This resolves the finite ticket-06 implementation slice, not M1, numerical-domain
qualification, field calibration or the full research objective. Research trials,
training and AI-model calls are zero; gain NOT_ESTABLISHED, calibration PENDING.
