# 19: 把FEMA情景、后果和能力映射到风险

**What to build:** 每个开放风险问题具备情景、时间窗、服务后果、证据缺口和可执行选项。

**Blocked by:** 18, 08

**Status:** resolved

**Milestone:** M3

- [x] FEMA作为过程参照，数值评分/概率对象为本研究定义。
- [x] 相互重叠服务损失去重，多后果维度不混量纲。
- [x] 高风险可直接处置，不强制先检查；低风险问题允许暂缓。
- [x] 主来源相关工作对照明确已有部分可观测/多部件检查维护方法的假设与边界，区分已有方法复现、工程扩展和待检验的新机制，不把范围大或FEMA名词当作新颖性证明。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

Background reading prepared while03 was active: `docs/mainline/research/closest-methods.md`. Its finite access scope does not complete this ticket or establish novelty; assess applicability against the implemented model.

## Evidence

Pending implementation and acceptance.

Assigned implementation: `/root/m3_19_risk`, branch `donson/mainline-19-risk`, isolated managed worktree `C:/Users/Donson/.codex/worktrees/mainline19-risk/Renly`. Ticket18 Root authority and delivery proof now satisfy the blocker; this ticket still requires its own acceptance.

Author candidate: `docs/mainline/evidence/19.json`; public contract `docs/mainline/19-risk-scenarios.md`, original formal engineering source `1939cb2ff375f7a0632a0a05ada68ae98afbdc1a`, original data `7069f2bee86ef7cdfd8d4849bb98bb5dacbf59cc`. Read `evidence/mainline/engineering/19-risk-scenarios/README.md`. Fresh delivery, Root full regression and final independent closure remain pending; this ticket is not resolved.

Independent numeric-domain finding at original1939 is retained; separate corrected runtime and targeted closure are indexed by `docs/mainline/evidence/19-correction.json`. Original author capture/index remain immutable. Current corrected-runtime Root verification and independent closure are pending; status stays claimed.

Revision2 numeric closure: `docs/mainline/evidence/19-correction-v2.json`, current runtime99a2afea. Historical first Root448 PASS at7b9 is retained but not current acceptance after the independent full-horizon overflow finding. New review/fresh proof/full at the corrected runtime remain pending; ticket stays claimed.

Root acceptance: `docs/mainline/evidence/19-root.json`, actual corrected-source integration `6193cb24851e3ed435a78153ffb79a64da77ab63`, 450 tests all executed and720independentassertions. Original and correction candidates retain their historical pending identities; separate Root authority resolves this ticket.
