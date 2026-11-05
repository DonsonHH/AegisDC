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

Owner `/root/m4_26_candidate`, branch `donson/mainline-26-candidate`, reused worktree `C:/Users/Donson/.codex/worktrees/mainline23-intervention/Renly`, base accepted25 publication48d223db. One candidate mechanism under design: explicitly account for prospective observation admissibility under the existing public evidence/provenance/dependence rules, keeping the declared loss/physical/execution models and resource rules fixed. A proposal is not an accepted algorithm or gain; first establish a falsifiable public behavior and a bounded prediction contract. Do not reuse any policy engineering result as a registered effect trial.
