# Spec review: mainline ticket 08

Fixed baseline: `8141615448e33ed930338162d35d9d1ef1c6df73`.
Reviewed candidate: `1fb8981b970e1e120e64598c5ce95c566037dfed`.
Command: `git diff 81416154...1fb8981b` in the dedicated `full-site-08` worktree.
Contracts: ticket 08, full-facility specification, MAINLINE and ADR0003.

## Spec

**Findings: 0.** No missing requirement, scope creep or incorrect behavior was established in this bounded accounting slice.

The production diff adds only the three already declared component-capacity parameters to the existing source-tagged timed-input allowlist. Joint service remains the minimum of demand and the three execution/power-limited component capacities, so overlapping losses are counted once. Requested demand, delivered work and interval-normalized deficit seconds remain separate accounts; restoration does not delete recorded loss. The documentation correctly identifies synthetic normalized-rate units and assumed power coefficients, without inferring FLOP/s from MW or claiming a job queue, policy gain, field calibration or completed M1.

Independently executed all eight focused tests, including CLI parity, input refusals, overlap, zero/changing demand and throttle/restoration; eight passed with no skips. Read the original unsupported-event red log and checked the literal interval expectations. Fresh-read all eleven saved runs: 33 manifest artifact hashes/record counts and all 59 receipt hashes matched.

An additional independent six-interval probe combines fractional-time capacity overlap, offered-demand changes, a zero-demand interval, execution pause and restoration with maximum step .37 s. Both V2 and water-V3 give requested work 2.07, delivered work .495 and normalized deficit 1.315 s, matching literal hand sums within 1e-12. Script, precise inputs and results are saved in `aegisdc-review-08-spec-attachments/` beside this report. Existing v1/v2/v3 configurations and CLI defaults are unchanged by this diff.

No full regression, root modification or other ticket update was performed. Root enabled-Torch acceptance remains separate.

Spec total: **0 findings**; no blocking issue.
