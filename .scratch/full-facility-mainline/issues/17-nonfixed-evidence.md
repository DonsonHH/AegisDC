# 17: 让历史、人工和手持检查提供证据

**What to build:** 历史维护、人工报障和现场专业结果可改变认知，并在来源/迟到/有效期上接受统一处理。

**Blocked by:** 14

**Status:** claimed

**Milestone:** M3

- [ ] 正常和阴性结果可记录，误报/漏报及覆盖范围显式。
- [ ] 检查结果在动作完成后才可用，设施在检查期间继续演化。
- [ ] 同源信息和陈旧历史不能无条件重复叠乘。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

## Evidence

Pending implementation and acceptance.

## Owner and public behavior slices

Owner `/root/mainline_02_merge`, branch `donson/mainline-17-nonfixed`, sole worktree `.work/worktrees/full-site-17`. Base6fe and metadata integration9992 were re-read; live15/16/17 ownership and worktree state were confirmed before this claim. Root remains primary15; no global milestone is accepted here.

Pre-agreed seams are the authorized nonfixed record producer into existing14 `ingest`/`snapshot`, and a typed producer-side completion gate with a private exact-saved-signal adapter. Tests use these public boundaries, never private plant/ledger methods. History/manual claims test declared source/time/quality/provenance and delayed/stale admission, not truth calibration. Completion/measurement slices test coverage, status/declared qualification, actual completion/latency and reproducible declared error models; they do not test the professional route/resource executor (21/22). The existing M1 completed work effect is NO_REPAIR_OR_EVIDENCE and is not a completion token.

Implementation contract: `docs/mainline/17-nonfixed-evidence.md`. Root authorized these producer/adapter seams in the assignment; no additional permission gate is inferred from TDD. Red/green slices, frozen engineering capture and independent root review remain required.
