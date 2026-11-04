# 10: 让UPS、柴油与维护改变保障能力

**What to build:** 受保负载、储能、柴油启动及备用冷源按容量和切换逻辑影响全场。

**Blocked by:** 04, 05

**Status:** resolved

**Milestone:** M1

- [x] 储能能量/效率和接管延迟可核对，不能无限续航或默认全负载受保。
- [x] 维护下线、切换失败和共同电源可降低冗余，不按设备数量推可用率。
- [x] 备用冷源实际连接为研究设定，来源缺口继续保留。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

## Preparation (implementation not started)

Assigned design owner/worktree: `donson/mainline-10-reserve`,
`.work/worktrees/full-site-10`, created at actual integration `81416154`.
See `docs/mainline/10-reserve-design.md` for the primary-source boundary,
finite-energy/transfer proposal, paid effective cooling interface, 07/09
compatibility and independent hand acceptance cases. This round changes no
runtime/config and executes no tests, engineering simulation or effect study.
Status remained ready-for-agent pending the root's implementation follow-up;
the design is not acceptance evidence or M1 completion.

## Implementation started 2026-11-05

Owner/worktree unchanged. Accepted integration `98fd8c4b` and stable, not-yet-root-
accepted 09 interface `4619dbfd` are merged before this implementation.
`docs/mainline/10-reserve-implementation.md` records the revised finite actor-
power boundary resolving the design's unpowered-controller startup deadlock.

## Accepted local implementation and delivery

Components `d609f00e`; integrated reserve-v6 `d3dea988`; same-time source-need
correction `7e9015c0`; final physical/target pin `efb7bbdc`. Root source review
reported Standards0 and one Spec finding closed; two selector directions share
that one causal correction. Runtime source remains that pin through capture.

- Explicit v6 derives control-v5 and preserves environment/water/control groups.
  `reserve.py` holds separate finite-power UPS/generator transitions, sampled
  main-PLC cooling transitions and signed paid sensible exchange. `power.py`
  extends the real budget; original `allocate_power` and v1-v5/default remain.
- UPS internal control receives allocated AC or finite UPS energy independently
  of its disconnected output/main PLC. Generator control/cranking use a separate
  finite start store; its depletion is in facility storage/energy/event accounts.
  Fuel/start/control loss, fan loss and room heat have single declared sinks.
- UPS protection remains the original three auxiliaries. Maintenance, delayed/
  failed transfers and common normal/protected distribution gate actual output.
  Empty starter with full main fuel, disconnected UPS output with ongoing
  internal consumption, and positive stores behind failed distribution all have
  retained negative cases. Main PLC only accepts cooling at a paid local sample.
- Effective standby cooling shares the single paid circulation, has finite
  UA/air-capacity/transport cap, preserves signed heat, adds no water mass, and
  charges actual fan energy once outside. 07 hot/floor mass and energy and 09
  sampling/latches remain active. Unknown real tower/coverage data stay unknown.
- `tests/test_mainline_reserve.py`:26 component/run/CLI targets pass, including
  independent UPS32.6 s and generator5/15 s energy/depletion examples, both
  same-time selector directions at steps1/.25 s, maintenance/failure recovery,
  signed/capacity-limited cooling, real thermal service path and 07/09 combination.
- Clean execution `179094ed28b482fd75c50396c6213472870eed3d` captures twenty
  engineering runs plus six expected refusals under `runbook-v1.json`.
  `fixtures-179094ed-01/receipt.json` declares134 new durable artifacts and36 prior
  durable originals before hashing; runtime caches are excluded by initial type
  policy. There are229 private trace records and209 interval balances.
- The one full `acceptance-179094ed-01` passes engineering/evidence/overall:
  289 discovered /287 executed, zero failure/error, exactly two existing optional
  Torch skips in the primary runtime path, no unexpected skips; twenty historical
  original-file hashes pass. No full regression was repeated.
- Durable data commit `2172dab0f2ba7e7913c926bc196f8a6c0a3f0ea9` was independently
  checked in a new detached worktree by `scripts/verify_reserve_candidate.py`:
  all declared bytes/counts and committed delivery blobs pass, runtime and test/
  tool identities match their execution Git revision, and zero caches are needed.
  `delivery-readback-2172dab0-fresh-01.json` records that actual fresh-checkout PASS.

Paths after the explicit source/test/tool pointers are under
`evidence/mainline/engineering/10-reserve/`; see its README. Maximum interval
energy residual is `4.403875209391117e-6 J`, whole-run
`6.38933852314949e-6 J`, mass `4.547473508864641e-13 kg` in the frozen package.

This resolves only the finite ticket-10 engineering slice. Root metadata/Torch
integration acceptance and the remaining M1/full research gates are separate.
Research/model/training counters are zero, gain NOT_ESTABLISHED, calibration
PENDING, M1 IN_PROGRESS and overall goal ACTIVE. No global progress was edited.
