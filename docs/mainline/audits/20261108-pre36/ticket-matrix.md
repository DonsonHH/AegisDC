# 01–35 substantive evidence matrix

Audited source `2dfe5537e4f95fa605f325b060ef32223dafb4f6`; accepted labels/CI are not used as substantive proof.

## 01 01: 固定总目标、场景身份和验收契约

Meeting: R1, R3, R5, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Single synthetic full-facility goal;42 dependent tickets, conditionalAI/RSI and incomplete overall goal.

Source: docs/MAINLINE.md; docs/adr/0003-complete-facility-mainline.md; .scratch/full-facility-mainline/spec.md

Saved behavior: 35 source-pinned ticket criteria;164 phase attempts;36+ unstarted

## 02 02: 读取并核验独立全设施场景

Meeting: R2, R3, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Closed loader validates eight domains, typed shared identities/four graphs, SI/ranges/provenance and unknown site gaps.

Source: src/aegis_dc/scenario.py:validate_scenario/load_scenario; src/aegis_dc/runtime_contract.py

Saved behavior: V6 inventory8/45/113/91 directly counted

Limit/gap: Structural validation alone is not a dynamics proof.

## 03 03: 跑通八域正常工况竖切片

Meeting: R1, R3, R4. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Coupled plant uses actual power/heat/service; default empty work list produces no automatic tour.

Source: src/aegis_dc/plant.py:simulate_scenario/point/integrate/snapshot; src/aegis_dc/workforce.py

Saved behavior: Original600s healthy run: demand=delivered600, zero work and zero deficit

Limit/gap: Originalv2 witness retains its own version; later V6 coupling checked separately.

## 04 04: 在全场传播供电容量和失电

Meeting: R3, R4. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Capacity-limited power allocation, prioritized protected loads, finite reserve inventory and explicit conversion losses.

Source: src/aegis_dc/power.py:allocate_power/allocate_reserve_power

Saved behavior: 11 coupled sharedAC/rectifier/distribution cases

Limit/gap: Ideal aggregateMV/LV boundary; no separate voltage, transformer-loss or branch-protection model. Allowed explicit fidelity limit.

## 05 05: 在全场传播滤阻、泵阀和板换变化

Meeting: R3, R4. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Paid hydraulic/valve operating points and HX heat exchange feed the same plant.

Source: src/aegis_dc/heat_transfer.py; src/aegis_dc/plant.py:point/integrate

Saved behavior: 11 internal-valve/phase and capacity cases; saved mass/energy accounts

Limit/gap: Fixed supported topology and declared lumped model; not a general site hydraulic network.

## 06 06: 闭合相变库存、内能和冷凝响应

Meeting: R3, R4, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

ReferenceR134a fixed-volume M/U phase state, EOS-domain failure and condenser coupling.

Source: src/aegis_dc/thermodynamics.py:SaturationTable; src/aegis_dc/refrigerant_initialization.py; src/aegis_dc/plant.py

Saved behavior: Numerical/phase saved witnesses and frozen reference table

Limit/gap: Actual site working fluid unknown; no site-fluid inference or arbitrary-domain error theorem.

## 07 07: 让房间、泄漏与访问条件影响作业

Meeting: R3, R4, R6. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Room heat/water/temperature conditions block access and can stop actual crew work.

Source: src/aegis_dc/environment.py; src/aegis_dc/plant.py:update_room_work_access; src/aegis_dc/workforce_dispatch.py

Saved behavior: 21 safety-closure actual abort;11 room/gate counterexamples

## 08 08: 让计算、网络和存储决定服务缺额

Meeting: R3, R4, R6. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Delivered service is constrained jointly; external demand remains even during protection/derating.

Source: src/aegis_dc/power.py; src/aegis_dc/plant.py:point/integrate

Saved behavior: Healthy demand=delivered; registered saved trace/ledger independently reconciled

Limit/gap: Normalized service capacity; no MW-to-FLOP/s claim.

## 09 09: 使本地控制与自动保护实际响应

Meeting: R2, R3, R4. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Local samples/control/protection advance independently of dispatch and can react before people.

Source: src/aegis_dc/local_control.py; src/aegis_dc/plant.py:sample_control

Saved behavior: 11 bias/link/latch and invalid-flow cases

Limit/gap: Local instrumentation permission does not become dispatch-wide observability.

## 10 10: 让UPS、柴油与维护改变保障能力

Meeting: R3, R4, R6. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

UPS, starter/fuel, maintenance and switching/backup-cooling delays affect actual protected supply.

Source: src/aegis_dc/reserve.py; src/aegis_dc/power.py; src/aegis_dc/plant.py:update_reserves

Saved behavior: 11 finite-generator case;23 backup-request native case

Limit/gap: Only declared protected loads; no equipment-count availability estimate.

## 11 11: 验收同一全设施模型的跨系统行为

Meeting: R3, R4. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Integrated eight-domain event/capacity/crew counterexamples retain one facility and shared bottlenecks.

Source: src/aegis_dc/plant.py; src/aegis_dc/runtime_contract.py

Saved behavior: 14 named coupled saved cases including resource conflicts, room, control and shared capacity

Limit/gap: Finite engineering scope, not field validation.

## 12 12: 用独立算例验证数值与步长

Meeting: R4, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Analytic/reference and refinement witnesses plus explicit domain failures; oldNO-GO preserved.

Source: src/aegis_dc/thermodynamics.py; src/aegis_dc/heat_transfer.py; src/aegis_dc/plant.py

Saved behavior: 12 final assessment/refinement artifacts and original failed captures

Limit/gap: Frozen5/4/2 ladders and named cases; no universal trajectory error bound.

## 13 13: 重放外生作业、故障与维护场景

Meeting: R4, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Recorded input/source/interpreter binding, unique outputs, effective horizon/step and balance-axis integrity.

Source: src/aegis_dc/replay.py:run_recorded/read_attempt/replay_attempt; src/aegis_dc/replay_format.py

Saved behavior: 13 causal baseline/command and lifecycle originals

Limit/gap: Replay of a world does not add an independent statistical unit.

## 14 14: 接收有到达时间和共同来源的记录

Meeting: R2, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Arrived snapshots retain missing/expired/conflicting/copy/provenance distinctions.

Source: src/aegis_dc/evidence_ledger.py:validate_ledger/EvidenceLedger.snapshot

Saved behavior: 14 snapshot: negativehuman report remainsFalse; future records absent; independence not presumed

## 15 15: 验证决策视图不泄漏真实故障

Meeting: R1, R2, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Closed public frame excludes backend objects; online policy receives arrived evidence and task-local feedback.

Source: src/aegis_dc/decision_view.py:DecisionGateway/validate_current_frame; src/aegis_dc/policy_execution.py:_frame/process

Saved behavior: SavedA/B common public frames equal despite different private worlds

Limit/gap: Finite noninterference witnesses; no hostile-host security guarantee.

## 16 16: 让稀疏测点、偏差和迟到形成可用信息

Meeting: R2, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Sparse enabled channels carry public observation law and private realization separately.

Source: src/aegis_dc/sensor_channels.py; src/aegis_dc/live_sensor_execution.py

Saved behavior: 16 saved future-hidden, missing-not-zero and bias/noninterference checks

Limit/gap: Coverage is declared; uninstrumented assets do not obtain synthetic full-state arrays.

## 17 17: 让历史、人工和手持检查提供证据

Meeting: R2, R6, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

History/manual/work-order claims and typed saved-signal observations retain original time/provenance; numeric and binary errors explicit.

Source: src/aegis_dc/nonfixed_evidence.py:NonfixedEvidenceProducer/NonfixedSession

Saved behavior: At97.999 three pending handheld records absent; at98 numeric/false-alarm/miss records present

Limit/gap: Binary fixture errors are signal-law examples, not field alarm rates or formal-study generic fault labels.

## 18 18: 建立随证据和时间变化的风险认识

Meeting: R2, R4, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Finite belief filtering handles age, correlation, duplicate channels, model conflicts and unknowns without repair actions.

Source: src/aegis_dc/belief.py:infer_belief/exact_belief_context

Saved behavior: 64-atom exact synthetic calibration; normalized law and declared wrong comparators

Limit/gap: Synthetic calibration only; not empirical site priors/performance.

## 19 19: 把FEMA情景、后果和能力映射到风险

Meeting: R1, R4. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Risk questions have scenarios, windows, joint service consequences, options and explicit unknown probability/consequence.

Source: src/aegis_dc/risk_scenarios.py:assess_risks

Saved behavior: Saved joint witness matches15877/16480s; template8 questions with6UNMODELED

Limit/gap: Unmodeled domains retain gaps/bounds; not full calibrated facility failure prediction.

## 20 20: 比较检查信息与可执行处置的价值

Meeting: R1, R4, R6. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Defer/direct/inspect-then-act share information/model and full branch resource commitments; information itself changes no plant.

Source: src/aegis_dc/action_value.py:assess_action_value

Saved behavior: Saved prior1/4 alternatives25/20/12.5s and0/20/15.5person-s

Limit/gap: Finite predictive law, not actual or field effect.

## 21 21: 执行专业、工具、路径和占用约束

Meeting: R1, R3, R6. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Actual typed multi-role crew travel, queue/rendezvous, qualification/tool/access and resource occupation.

Source: src/aegis_dc/workforce_dispatch.py:CrewWorkforce/prepare_work

Saved behavior: Team starts61/completes91;60workperson-s; actual safety case aborted before work

Limit/gap: Personnel are domain actors, not LLM agents; not optimal global crew assignment.

## 22 22: 把检查执行与现场证据接起来

Meeting: R2, R6, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Measurements require current actual completion, work duration, named tool/qualification and signal scope; reports delayed.

Source: src/aegis_dc/inspection_execution.py:InspectionSession

Saved behavior: Saved public counts0/0/1 around2.25completion and2.75arrival

Limit/gap: Confirmation is named-signal threshold only; not a fault diagnosis or risk closure.

## 23 23: 让处置延时、残余效果与服务响应闭环

Meeting: R1, R4, R6. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Four named authorized operations apply once after actual completion; expiry/abort yields no effect; demand retained.

Source: src/aegis_dc/intervention_execution.py:prepare_intervention/InterventionSession; src/aegis_dc/plant.py:event order

Saved behavior: 23 network/filter/compute/backup and authority-negative originals

Limit/gap: Lumped parameter effect is not verified physical repair.

## 24 24: 用恢复证据关闭问题

Meeting: R2, R6, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Action completion, symptom retreat, verified closure, false-alarm review, escalation and risk acceptance are distinct.

Source: src/aegis_dc/verified_closure.py:assess_closure/_check

Saved behavior: Saved action-only pending, condition-only symptom, verifiedclosed cases

Limit/gap: Declared sampled criteria only; formal31–35 deliberately have no post-action closure protocol.

## 25 25: 在同一设施运行透明比较策略

Meeting: R1, R4, R6. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

No-human, due-check, FIFO, risk-condition and near-problem lookahead use shared public action/permission boundary.

Source: src/aegis_dc/dispatch_policy.py:choose_work; src/aegis_dc/policy_execution.py

Saved behavior: 25 saved no-human/FIFO and explicit periodic/risk/closure cases

Limit/gap: Periodic is a comparator; it is not the default task definition or a one-factor intervention contrast.

## 26 26: 实现一个可证伪的联合核查处置候选

Meeting: R1, R2, R4. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Candidate changes prospective report interpretation under the declared updater, allowing defer/direct/inspection.

Source: src/aegis_dc/lookahead_policy.py; src/aegis_dc/evidence_projection.py

Saved behavior: 26 exact/nonadaptive/informative saved decision cases; later primary has12identifiable worlds

Limit/gap: Curated finite candidate tasks; not autonomous sitewide discovery or new general optimization algorithm.

## 27 27: 重放完整设施的跨系统闭环

Meeting: R1, R3, R6. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

One same-facility replay couples exogenous load/maintenance/fault, protection, work/action and later closure.

Source: src/aegis_dc/policy_execution.py; src/aegis_dc/plant.py; src/aegis_dc/verified_closure.py

Saved behavior: 27 actual timeline:4automatic service recovery,6cleaning,8.5arrived-evidence closure

Limit/gap: Engineering demonstration and original replay failures stay separate from research units.

## 28 28: 验证正常、误报和来不及挽救的情景

Meeting: R1, R6, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Normal/false cue/automatic recovery/too-late intervention retain real costs and failure/no-benefit traces.

Source: src/aegis_dc/inspection_execution.py; src/aegis_dc/intervention_execution.py; src/aegis_dc/verified_closure.py

Saved behavior: 28 frozen four negative-control trajectories

Limit/gap: Selected engineering controls do not estimate general false-alarm or miss rates.

## 29 29: 冻结可行参数域和模型可信度边界

Meeting: R3, R4, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Parameter provenance and coupled admissibility separate scalar ranges, named joint points and site gaps.

Source: src/aegis_dc/parameter_domain.py; src/aegis_dc/water_envelope.py; src/aegis_dc/refrigerant_initialization.py

Saved behavior: 113parameter inventory and eight33s finite joint trajectories

Limit/gap: 106synthetic assumptions/7derivations; four site gaps retained; not a Cartesian or field-qualified domain.

## 30 30: 预注册独立比较问题、指标和预算

Meeting: R4, R6, R7. Assessment: PARTIAL_REPORTING_GAP_F1.

Primary criteria/units/pairing/methods/budgets/source/nonces/failure rules frozen before runs.

Source: docs/mainline/30-comparison-protocol-v1.json; scripts/comparison_release.py

Saved behavior: Original protocol/source lock and held-phase input release gates

Limit/gap: Several promised secondary endpoints lack operational definitions or an explicit published status; seeF1.

## 31 31: 在已见条件开发和诊断方法

Meeting: R1, R6, R7. Assessment: PARTIAL_REPORTING_GAP_F1.

36 unique development runs retain resources, opportunity/choice diagnostics and negative mean; held conditions not used for tuning.

Source: scripts/registered_development.py; scripts/development_journal.py; scripts/analyze_registered_development.py

Saved behavior: Saved6world primary mean−1/24s,36/360/360 ledger

Limit/gap: Development output reports work counts but not generic confirmation/miss endpoints;F1 crosses subsequent reporting.

## 32 32: 核对执行源码、配置和原件生命周期

Meeting: R6, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

Input/source/interpreter/cache and exact durable artifact lifecycle frozen, including original preparation failure.

Source: scripts/prepare_confirmation.py; scripts/comparison_release.py

Saved behavior: 96input hashes; fixed64 interface and two hydraulic corrections recorded before any confirmation outcome

Limit/gap: Old failures and superseded prospective locks retain their actual source.

## 33 33: 执行封存独立条件

Meeting: R6, R7. Assessment: CONSISTENT_WITH_DECLARED_FINITE_SCOPE.

96 original starts billed before calls, fixed matched inputs/order and source, exact raw archives and no retries.

Source: scripts/registered_confirmation.py; scripts/development_journal.py

Saved behavior: 96completed/960s/960decisions native capture; data/source identities and frozen input parity

Limit/gap: No raw-frame inflation of independent16world denominator.

## 34 34: 形成主要结果、成本和约束结论

Meeting: R6, R7. Assessment: PARTIAL_REPORTING_GAP_F1.

Fixed16world primary/cost/stratum/missing-outcome arithmetic and all six methods published without upgrading negative result.

Source: scripts/analyze_registered_confirmation.py; scripts/summarize_comparison_facts.py

Saved behavior: Primary+.03515625s, paid−.96875; nohuman/candidate mean3.8125;NO_PRACTICAL_GAIN

Limit/gap: Promised confirmation/report-error/completion-status readout omitted or left implicit;F1 must be closed before36.

## 35 35: 隔离信息、依赖知识和协作机制

Meeting: R2, R4, R6, R7. Assessment: PARTIAL_REPORTING_GAP_F1.

Original three planner masks preserve byte-identical actual inputs; private nominal mapping keeps typed executor gates.

Source: scripts/ablation_planner.py; scripts/ablation_run_evidence.py; scripts/registered_ablation.py

Saved behavior: 8worlds/32runs,128native members,56submission mappings and independent24contrasts

Limit/gap: Dependency is bundled consequence/edge knowledge; team availability is not optimal assignment. Secondary readout remainsF1.

