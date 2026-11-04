# 08: 让计算、网络和存储决定服务缺额

**What to build:** 服务账根据需求、实际可供计算/网络/存储能力及降载状态产生可解释结果。

**Blocked by:** 03

**Status:** resolved

**Milestone:** M1

- [x] 同一服务的重叠故障不重复计损失，组件可用不等于整项服务可用。
- [x] 外生作业需求与实际执行负载分开，调整/推迟任务不删除应计服务需求。
- [x] 容量/速率和FLOP/s口径明确，不从MW反推算力。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner: `donson/mainline-08-service` in `.work/worktrees/full-site-08`, based on
integration `454408e33bc39a45a87ac2799c8dfd8ceff0a4ae` (2026-11-04).

The accepted scenario/run and CLI seams are used. The existing joint-service
minimum and independent requested/delivered accounts are retained; timed changes
to the three already declared normalized component capacities are the missing
engineering input behavior. Work remains in the complete eight-domain scene;
no queue, scheduler, policy comparison, FLOP/s calibration or research trial is
introduced.

Implementation: `2c328cab`; assembled with accepted integration `588cec81` at
`60f21f25dc55765124398215b065c2c29bac0dfb` before the saved runs/full regression.

- Production change: the three existing `compute_service_capacity`,
  `network_service_capacity` and `storage_service_capacity` parameters are now
  permitted as source-tagged timed engineering inputs. Existing ranges, event
  validation/splitting, joint-service minimum and independent integrals are
  retained. No physical, runtime-contract or scenario change belongs to 08.
- `docs/mainline/service-accounting.md`: dimensionless normalized service-rate
  factors, explicit assumed W per reference execution factor, independent
  requested/delivered integrals and interval-normalized deficit seconds.
  Absolute workload/throughput is uncalibrated; no FLOP/s is derived from MW.
- `tests/test_mainline_service.py`: eight public run/CLI tests, all executed,
  no errors/failures/skips. Independent literal hand cases cover fractional-time
  component capacities, overlapping network/storage loss counted once, any
  required component stopping joint delivery, zero/positive and changing demand,
  execution throttle/pause without deleting offered demand, event rejection,
  and CLI save/source parity. They pass again after integrating ticket 05.
- `evidence/mainline/engineering/08-service/red-green.md` and
  `red-timed-capacity-01/` retain the actual unsupported-input red result and
  each behavior slice. Existing account behavior passed on first observation;
  no artificial failing source change was introduced.
- `hand-cases-v1.json` freezes eleven same-facility engineering cases with
  literal independent interval-sum expectations before capture. The public-only
  `capture_engineering.py` writes new directories and verifies saved bytes/counts.
  `runs-60f21f25-01/receipt.json` records eleven full eight-domain trajectories,
  including one CLI run, six expected input refusals and 59 fresh-read hashes.
  Interval energy residual max is `3.4851254895329475e-6 J`, whole-run
  `2.5853514671325684e-6 J`, mass `2.2737367544323206e-13 kg`.
- `acceptance-60f21f25-01/summary.json`: engineering/evidence/overall PASS,
  225 discovered /223 executed, no failures/errors, exactly two pre-existing
  optional Torch skips in the primary interpreter path, no unexpected skips;
  twenty original-file hashes pass. Full regression ran once after the source
  merge. Root owns independent review and enabled-Torch integration acceptance.
  Compilation and staged whitespace checks pass with captured CRLF bytes kept.

Paths after the explicit documentation/test pointers are under
`evidence/mainline/engineering/08-service/`. A pause/throttle is an execution
request change, not a hardware-failure diagnosis; a capacity event is a separate
declared ceiling change. Restoration does not erase prior unserved demand.
No queue, catch-up/deadline optimizer or policy mechanism is added.

This resolves the finite ticket-08 accounting slice, not M1 or the complete
research objective. State remains PRIVATE_PLANT_EVALUATOR_ONLY, research/model/
training calls are zero, gain NOT_ESTABLISHED and field calibration PENDING.
Global progress was not edited by this ticket.
