# 16: 让稀疏测点、偏差和迟到形成可用信息

**What to build:** 固定测点可稀疏、停用、有噪声或延迟；控制和记录按各自时刻更新。

**Blocked by:** 14

**Status:** claimed

**Milestone:** M3

- [ ] 测点掩码不是全资产数组的隐含真值。
- [ ] 测量误差/偏差和共同来源机制可单独改变；观测与故障过程不硬绑定成必报。
- [ ] 无固定测点输入时，历史/人工/现场证据路径仍可工作。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

The user confirmed that fixed sensors exist but cannot cover every location because of cost and other constraints (ADR 0002, 2026-11-05 clarification). Include sparse fixed measurements in the primary scenario. Missing/disabled/no-fixed-input cases test information availability; they do not redefine the primary facility as sensor-free. Historical/asset records, human reports/work orders and on-site portable measurements remain allowed evidence sources.

## Evidence

Owner `/root/mainline_12_full_standards` now implements ticket 16 only (the
earlier Standards reports remain historical reviews of other tickets).
Branch `donson/mainline-16-sensors`, owned worktree `.work/worktrees/full-site-16`,
verified clean base `6fe8313d5780bbda86c4c9bec51071a570f0fd72`.
Root assigned this ready ticket after accepting 14; 15 and 17 have separate
owners/worktrees. No ledger/schema, physical model, or other worktree changes.

The authorized seams are a closed observation-profile loader, an evaluator-only
saved-trace sampling adapter producing a detached legal ticket-14 ledger and
separate private audit, a static public observation-model view, and an isolated
CLI. Tests use literal private signals at that seam and one separately frozen
full-V6 saved-trajectory capture. The sampling adapter does not run or alter the
plant, infer risk, or create a policy trial. Source/tool and delivery acceptance
remain pending independent root reviews.

Recovery owner `/root/m3_16_continue` continued the existing tree after root
confirmed the previous handle had disappeared and no active process used it.
The complete implementation is frozen at `6e31403a`; the actual engineering
adapter execution is `84209346` and retains the original physical producer
`89f47b6f`. Its 1,134-record nominal/mismatch outputs, 652 polls per realization,
ten snapshots and three data-driven SVGs are saved without a new physical run.

The original full regression remains **FAIL** (390 run / 388 executed / one
failure / one error / two explicit optional Torch skips): two legacy CLI children
could not import `aegis_dc` because the outer command omitted `PYTHONPATH`.
`capture-01` and its exact missing `source-guard.json` role are preserved; no
receipt or failure was upgraded. The separately frozen additive environment
closure `a732b376` runs only the two original real CLI tests and passes both,
with actual child stderr saved. It is not a successful 390-test rerun.

See `docs/mainline/evidence/16.json` and
`evidence/mainline/engineering/16-sensors/README.md` for the original-source,
delivery and fresh-checkout proofs. The observation component passes; status is
**IMPLEMENTED_PENDING_ROOT_ACCEPTANCE_WITH_RECORDED_ENVIRONMENT_FAILURE**.
Ticket lifecycle stays claimed pending root Standards/Spec reviews and the
integrated correct-environment/Torch regression. M3, mechanism comparisons,
agent/RSI eligibility and the complete-facility objective are not resolved.
