# 05: 在全场传播滤阻、泵阀和板换变化

**What to build:** 滤阻/泵阀变化可改变湖水与内循环供回、换热和服务。

**Blocked by:** 03

**Status:** resolved

**Milestone:** M1

- [x] 不同介质质量分开，板换端口与冷热容积温度不同。
- [x] 泵曲线、压差/表压、效率和热耗散不混用；质量与能量账闭合。
- [x] 流量衰减及污垢后果由方程产生，不直接手写成停机或奖励。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Owner: `donson/mainline-05-water` in `.work/worktrees/full-site-05`, assigned by
the integration owner after ticket 03 acceptance. Base/integration tip checked:
`0ee160cdcdbd195acf35d552abd8040ef7e55b5c`.

- Implementation: `8db1e95a`. Public seams are the scenario loader/validator,
  `valve_loop_operating_point`, `simulate_scenario`, `save_run`, and explicit
  CLI `--model configs/full-facility-mainline-water-v3.json`. Source/model/domain
  limits and independent hand cases are in `docs/mainline/water-verification.md`.
- Existing paid fixed-head/affinity pump, Kq² filter response, finite hot/cold
  volumes and signed epsilon/NTU HX were evaluated and reused. New water-v3 adds
  two identifiable, inspectable aggregate series valves with independent
  Kopen/a² and separate passive resistance, preserving the full-open V2 working
  point. Exact closure invokes a declared local hardwired pump-stop branch;
  sampled thermal/low-flow protection subsequently determines compute service.
- V1/V2 files, frozen property data, scenario schema and both CLI defaults stay
  unchanged. The runtime accepts exactly the old topology and one explicit new
  model/digest. Unsupported graph edits fail. All positions/curves/relay rules
  are synthetic research choices, not real Zhengzhou equipment information.
- Pressure outputs are differential head/losses, not gauge values. Total pump
  electrical heat is allocated once. Since this model exports no pipe heat or
  pressure work, actual positive hydraulic work requires f>=eta for its own
  fluid. This operating-domain check covers V2/V3 and timed enabling; inactive,
  zero-head, unpowered and interlocked pumps are not overconstrained.
- Independent literals: .01 m3/s, 60/40 kPa and 1/2 kW at the first valve hand
  point; .005 m3/s, 15/10 kPa and 125/250 W under a 250 W limit; separated
  399.5 kW HX /400.5 kW lake boundary and 310.0125 K outlet ports. Distinct
  refrigerant/internal-water/lake/floor-water accounts close.
- Numbered checks under `evidence/mainline/engineering/05-water/` retain every
  red/green/failure with exact command and source/input SHA-256. The rejected
  initial control graph/generator and the incorrect co-location work expectation
  are preserved, not silently converted into successful evidence. The final
  water suite executes 18 checks with no failures/errors/skips.
- First committed-source artifact set: `fixtures-e8555f76/` plus the separate
  `cli-e8555f76/`. After merging latest integration `47dda5d7` (power ticket 04),
  source merge `122f73bd7fcd38fb18d3911227a58aaf8aafaafd` has a new nine-run set
  `fixtures-122f73bd/`. Each run has clean implementation attribution and fresh
  file/hash/count/pressure/HX-port/mass/whole-facility-energy checks. Old outputs
  remain unchanged and retain their original source attribution.
- Normal 600 s has 601 states /600 balances, zero temperature drift and zero
  deficit. Internal shutoff/reopen cases retain external demand and each have
  the independently expected 1 s deficit. Under explicit engineering 306/305 K
  protection, lake shutoff/UA degradation first trip at 56/57 s and give 42/43 s
  deficit over 180 s. A qualified internal-valve visit completes at 30 s; it is
  an engineering work record, not diagnosis, evidence creation or repair.
- Final full acceptance: `acceptance-122f73bd/summary.json`, engineering/evidence/
  overall PASS, 206 discovered /204 executed, zero failures/errors, the two
  pre-existing optional isolated-Torch skips, no unexpected skips, 20 original
  evidence files hash-valid. `compileall` and `git diff --check` pass. Root owns
  enabled-Torch verification and independent Standards/Spec/integration review.

All artifact paths above are relative to
`evidence/mainline/engineering/05-water/`. This resolves the finite ticket-05
implementation slice, with root acceptance still pending. M1 remains
in_progress and the complete research goal active; global progress and other
owners' files were not edited. No registered research/AI/training trial ran.
Field calibration PENDING, scientific gain NOT_ESTABLISHED. Detailed real pump/
valve curves, deadhead/leakage/transient hydraulics, arbitrary topology execution,
stagnant conduction, parallel reserve availability and step-convergence
qualification remain outside this bounded engineering result.
