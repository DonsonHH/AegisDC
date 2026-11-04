# 14: 接收有到达时间和共同来源的记录

**What to build:** 调度侧可接收资产、历史、测点、人工及现场证据，并区分观察时刻、到达时刻、误差和同源关系。

**Blocked by:** 12, 13

**Status:** claimed

**Milestone:** M3

- [x] 未来、未到达和缺测记录不参与当前决策。
- [x] 告警复制工单保留根来源，不自动当两条独立证据。
- [x] 证据过期和来源冲突可见，未知质量不变成确定真值。

## Context

Read the fixed mainline, accepted scope ADR, specification, predecessor evidence and current progress. Work at the declared public interface. The scope remains one complete facility.

Read `docs/mainline/information-boundary.md` before defining dispatch-facing records. Evidence availability, candidate masks and execution feedback share the same information boundary; the private plant may enforce safety without exposing undeclared instantaneous observations.

## Evidence

Owner: `mainline_14_evidence`, branch `donson/mainline-14-evidence`, worktree
`.work/worktrees/full-site-14`, base `04e976c7934b4b2d54aa73794fe520482524be64`.
Implementation candidate is verified; root acceptance remains pending. The authorized public seams are the
closed evidence loader/ledger, explicit as-of snapshot, and CLI. The existing
hour-based foundation prototype and private V6 plant are preserved.

- Candidate record: `docs/mainline/evidence/14.json` (`IMPLEMENTED_PENDING_ROOT_ACCEPTANCE`).
- Prior precision/age runtime/tools execution: `28e8756d1014646952efb3661d323a68b68bd3ef`.
- Prior precision/age delivery: `4328c613e150474cb0e44dc9a11416680ebdc096`, 13 declared
  artifacts plus terminal receipt, independently checked in its fresh checkout.
- Current admission-corrected execution: `f9450246347e08dabfe9b40709e12da115a4de59`;
  delivery `4b1997b72ada11f3ae518db25c552c65d51e72a4`, nine declared
  artifacts plus terminal receipt; separate fresh proof passes, preserving 43
  prior originals and 200 prior corrected source/tool/input identities.
- Exact-bound, duplicate, time-scalar and finite-endpoint admission corrections:
  independent red/green examples and 20 passing evidence tests; current full regression awaits root
  integration. Original 371-test regression belongs only to execution `3c4e9640`.
- Original capture/delivery/fresh proof, failures and v1 figures remain unchanged.
- V2 figures use explicit off-scale arrows; root actual local raster inspection
  closed the original visual issue. No browser visual verification is claimed.
- No registered research trials, agent calls, training, posterior/risk mechanism,
  physical-core change, or completed M3/overall-goal claim.
