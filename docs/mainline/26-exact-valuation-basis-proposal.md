# Shared exact valuation basis: explicit revision

Status: implemented public numerical-path development after the A/B review boundary7798ce9d. Online execution and acceptance remain pending. The original representation-unsupported RED24/GREEN25 and all recorded v1/v2 outputs remain unchanged.

## Problem and invariant

The accepted action-value evaluator takes a serialized posterior float, converts its decimal representation to a Fraction and renormalizes before forming world masses. The counterfactual updater can supply the original exact finite Bayes mass instead. For a nondyadic posterior such as16/59 these are close but not identical. The current candidate explicitly records this as a representation-unsupported case; no epsilon hides it. Keeping that restriction forever would make the candidate needlessly unavailable on ordinary inputs.

The smallest proposed correction gives the closest baseline and candidate the same explicitly declared exact mass basis. It changes neither observations nor likelihoods, transitions, outcome catalog, work, physical response, authority or budget. It is a numerical delivery revision shared by the two methods, not an independent source of candidate gain.

## Versioned common input

The explicit `aegisdc-evidence-projection-v3` has all v2 fields plus the closed field `valuation_mass_basis`, whose initial value is `EXACT_FINITE_PUBLIC_BELIEF_CONTEXT_V1`. Existing projection-v1/v2 schemas stay closed and retain the accepted serialized valuation basis. Both new-v4 policy methods receive the same v3 declaration; other transparent rules can receive the same accessible public model declaration without becoming value planners.

The public action-value function accepts the explicit keyword `valuation_mass_basis`, defaulting to `SERIALIZED_PUBLIC_POSTERIOR_V1`. Only the explicit exact basis reads the same public finite model through `exact_belief_context` and uses its rational hypothesis masses for the existing catalog/outcome and service/resource calculations. It retains every belief/value variant and current world weight. Defaults and recorded historical outputs do not silently change. Caller-supplied mass dictionaries, unknown basis labels and extra projection fields are contract errors; arbitrary external rational masses are never trusted as the belief model's result.

The candidate's compatibility check must then compare projected exact outcome masses with those very same exact valuation masses. Direct intervention, defer and inspection alternatives all use the declared shared basis; the candidate does not get a special precise world model while its baseline keeps the old approximation. No comparison tolerance, rounded-posterior equality or likelihood modification is introduced. Existing float presentation of final predictions and deterministic ranking remains shared and must not be described as an exact optimizer.

## Audit and cost

Only an explicit exact-basis result adds the declared mass basis and exact current outcome ratios by belief variant. Default serialized responses keep the previous shape as well as the numerical path; no exact-basis metadata is added unconditionally to earlier responses. Model-call diagnostics distinguish ordinary value/risk assessments, exact contexts used for valuation, and extra counterfactual contexts. The current v4 validation/final-evaluation path performs two exact valuation reads and records `valuation_exact_belief_context=2` for both value policies; the candidate additionally records its ordinary prospective belief calls and three exact context calls used by the branch compatibility check. No hidden preflight computation is removed from cost accounting. This development path does not add a world-state cache.

Incompatible per-assumption contextual updates remain unknown. Exact numerical weights do not solve a missing background law, random support, stale nonneutral record replacement, cross-epoch dynamics, provenance ambiguity or a coarse catalog's report-conditioned outcome mismatch.

## Independently specified next public behavior

The root's pure-Fraction nondyadic witness was prepared before this proposed implementation: current masses(36,16,1,6)/59, original positive report law(1/10,4/5,1/10,1/10), six-second model. Positive/negative report masses are171/590 and419/590; impairment posteriors are128/171 and32/419. Defer, direct and compatible-inspection deficits are96/59,63/59 and619/590. Both methods on the new shared basis should select the compatible inspection. The historical v2 candidate should continue to report its old representation restriction under the old basis.

The negative adjacent case lets nonneutral fixed evidence expire: the future handheld-only updater yields8/11, not the current-world-conditioned128/171. That remains an implementation-context-unsupported/null inspection plan even after numerical correction. A per-assumption failure must not be hidden by a numeric envelope, deleted variant or changed catalog.

RED29 preserves the first failure of the unrecognized v3 declaration; GREEN30 passes the shared16/59 public witness for both policies using the original independently specified619/590,63/59,96/59 deficits and128/171,32/419 report posteriors. Boundary check31 keeps the nonneutral-expiry mismatch unknown. Check32 verifies the default response equals explicit serialized-basis output without new exact fields, older projection-v2 still has its recorded representation restriction, invalid/supplied bases fail, and the new projection contract is closed for both policies. These are public value/selection development checks, with no new plant simulation, formal engineering capture, full regression or registered effect trial. Online execution and final ticket gates remain separate.

One targeted compatibility command executed at numerical runtime source4713c365: `python -B -X utf8 -m unittest test_evidence_consistent_policy test_action_value test_belief -v`, with `PYTHONPATH=src;tests`. Its original log33 records43 methods passing in6.139s, zero failures/errors/skips. This command contains no facility simulation. Existing serialized value/belief tests and the earlier mixed-outcome, pending-record, clock and schema boundaries pass alongside the new common exact path. This numerical correction is common engineering support for both value policies, not an extra scientific mechanism or measured improvement attributed to the candidate.
