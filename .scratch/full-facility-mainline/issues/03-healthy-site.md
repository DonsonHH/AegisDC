# 03: 跑通八域正常工况竖切片

**What to build:** 同一个全设施场景可运行正常负荷，返回物理、控制、服务、空间和人员的时间演化及独立边界账。

**Blocked by:** 02

**Status:** resolved

**Milestone:** M1

- [x] 实际执行功率进入热账，外生未服务需求保留；各域不是固定占位返回值。
- [x] M1已实现最低人员/工具/资格/占用与工程作业请求可行性规则：资格不符、工具占用或位置/访问不可达会拒绝请求，不能只有人员字段。预定请求仅为工程夹具，默认无工作项时不自动巡回。
- [x] 电功率、质量、内能、库存、服务和人员可行性满足声明边界，正常初值与代数约束一致。
- [x] 可重放结果标工程夹具/合成研究设定，含源配置/代码身份，默认无固定巡回和科研模型调用。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

This ticket includes the minimum observable personnel behavior needed by the M1 acceptance. Ticket 21 later extends it into evidence-driven heterogeneous parallel dispatch; it is not a hidden prerequisite for M1.

## Evidence

Implementation: `37432b25a994c1c4e37d6747e9e9228a9ea3a44a`,
`donson/mainline-03-healthy` / `full-site-03`, based on integration
`0e2e2a8e5faf98f6ee9870dc4adf0c94d077db15`.

- Public boundaries: `load_scenario`/`validate_scenario`,
  `aegis_dc.plant.simulate_scenario(scenario, duration_s, step_s, work_requests, boundary_events)`,
  replaceable property/HX/pump boundaries, `describe_run`/`save_run`, and
  `python -m aegis_dc simulate [--model PATH] [--duration S] [--step S] [--inputs PATH] [--output NEWDIR]`.
- New initialized model: `configs/full-facility-mainline-v2.json`, eight domains,
  40 shared entities, 79 individually bounded/source-tagged SI parameters, four
  relation views; internal pump, local internal-flow instrument and loss-heat
  interfaces are explicit. V1 and the default `scenario` CLI remain unchanged.
- Physics: actual electrical execution and conversion losses; paid pump flow;
  finite hot/cold-water volumes plus separate plate-HX outlet ports; fixed-volume
  R134a-surrogate M/U flash with all-segment uniqueness/domain checks; solid/room
  storage; finite UPS/fuel and delayed generator; local sampled protection; exogenous
  service demand/joint capacity; separate nuisance-water drainage/access; finite
  qualified personnel/tool travel and work. Heat/enthalpy interfaces enter once.
- Normal initialization/equations/limits: `docs/mainline/healthy-run-model.md`.
  All coefficients and derived initial values are declared research assumptions
  or source-tagged calculations, not real Zhengzhou tuning. The actual coolant
  and other unresolved site data remain unknown.
- Accepted engineering artifacts:
  `evidence/mainline/engineering/03-healthy-site/normal-37432b25/` (600 s, 601 private
  state records /600 balances, demand=delivery=600, deficit=0, stable temperatures),
  `work-37432b25/` (151 s, one exact 120+30 s job and four qualification/tool/worker/
  access refusals), and `receipt-37432b25.json` with fresh-read hash/count/state/
  boundary checks. Both run manifests attribute the clean implementation commit
  and actual source/config/property hashes. No default requests mean no patrol.
- Independent references: 25 external-EOS flashes; .8 MPa reference and table
  endpoints; 1/2 kW hydraulic/electrical pump case; 40 kW HX; 3 K thermal inertia;
  100/95/5 kW conversion; UPS at 32.4 s with 3.24/.36 MJ output/loss; one 4 s joint
  service deficit. Supply/filter/protection/drainage/work counterexamples establish
  behavior beyond domain labels. Invalid/nonfinite/domain/excessive-step inputs
  and existing output directories fail explicitly.
- Red/green observations and exact command context are in the fixture directory's
  `red-green.md` and `README.md`. Final new-interface suite: 21 executed, no skips/
  failures/errors. V1 suite: 13 executed, no failures/errors/skips. `compileall`
  and `git diff --check` passed.
- Full `scripts/acceptance.py:verify` result:
  `evidence/mainline/engineering/03-healthy-site/acceptance-37432b25/summary.json`,
  engineering/evidence/overall PASS; 176 tests discovered /174 executed, zero
  failures/errors, exactly two pre-existing optional neural checks skipped because
  isolated Torch is absent from this interpreter path; no unexpected skips. Twenty
  original-file hashes pass. Root owns enabled-Torch and integration review.

This resolves the ticket's finite normal-run engineering slice, not M1 integration
acceptance or the overall research goal. Backup tower takeover, detailed failure/
control/maintenance qualification, step convergence, dispatch evidence/risk,
evidence-driven heterogeneous work, interventions/recovery and independent research
comparison remain their later tickets. Private trajectories are not dispatch
evidence; engineering work completion is not repair or inspection confirmation.
Research trials/model calls/training are zero; field calibration PENDING and gain
NOT_ESTABLISHED. Global progress remains active/in_progress and was not modified.
