# 26: 实现一个可证伪的联合核查处置候选

**What to build:** 一个明确候选根据服务依赖、证据与异质可行性联合选择检查/处置/暂缓。

**Blocked by:** 20, 25

**Status:** claimed

**Milestone:** M4

- [ ] 一次只检验明确机制，避免同时加入未独立控制的额外优先级/预测器。
- [ ] 策略允许不检查和直接处置，并保留计算/决策成本。
- [ ] 同源证据和人员专业知识的作用能被后续消融。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

First development slice: `docs/mainline/26-evidence-consistent-candidate.md` defines the shared public v4 projection and its sufficient same-factor exclusion proof. `tests/test_evidence_consistent_policy.py` contains a new six-second public-selector witness; original report law and outcome weights remain unchanged. RED01/ GREEN02 and compatibility03 preserve failures and13 passing public candidate/action-value checks. No plant, online candidate, frozen capture, full regression, effect trial or acceptance has run for26. Online v4 inheritance, informative and unmodeled cases, adversarial boundaries and final gates remain required.

First independent static review at e6b372aa identified four public-boundary defects. Separate RED/GREEN slices04–12 correct validation order, pending issued measurements, nonadvancing binary64 work clocks and cross-facility/background registry mismatch; failed correction05 remains preserved. Source31fb3fd8 passes one targeted43-method regression in25.391s; that compatibility suite contains existing engineering plant simulations, without repeating any sealed25 policy capture or running a26 formal/full/effect study. Proposed informative/expiry support-law extension is design only in `docs/mainline/26-projection-law-next-slice.md`; ticket26 remains claimed.

A/B continuation339c09c8 through8454cff5 adds public hard inspection-binding validation, lawful insufficient-work unknown value, and the explicit per-world certain-report support domain. Independent/neutral-expiry exact outcome checks allow compatible inspections; an8/9-versus16/25 mixture remains unknown, and pure representation mismatch has its own audit. Original positive report law and catalog are not changed to force admission. One targeted39-method public candidate/action-value/belief check passes6.834s at8454cff5; original logs14–28 and native-header classifications remain preserved. The v2 support extension is now a limited implementation, not only the earlier design note. No online candidate/frozen26capture/root acceptance/effect result is yet established.

Shared numerical continuation4713c365 adds projection-v3's explicit exact mass basis for both the closest value baseline and candidate. Defaults and projection-v1/v2 retain the serialized path/shape; exact masses derive from the same public model, not caller-supplied truth. RED29/GREEN30 validate the independent16/59 world, deficits619/590,63/59,96/59 and branch masses128/171,32/419. Adjacent nonneutral expiry remains context unsupported; log32 checks old defaults and closed basis inputs. One targeted43-method value/belief compatibility run passes6.139s at4713c365 (log33), zero failures/errors/skips and no plant call. This shared numerical revision is not a candidate scientific gain. Online public run-v3/policy-v4 inheritance and final frozen/root gates remain pending.

Owner `/root/m4_26_candidate`, branch `donson/mainline-26-candidate`, reused worktree `C:/Users/Donson/.codex/worktrees/mainline23-intervention/Renly`, base accepted25 publication48d223db. One candidate mechanism under design: explicitly account for prospective observation admissibility under the existing public evidence/provenance/dependence rules, keeping the declared loss/physical/execution models and resource rules fixed. A proposal is not an accepted algorithm or gain; first establish a falsifiable public behavior and a bounded prediction contract. Do not reuse any policy engineering result as a registered effect trial.
