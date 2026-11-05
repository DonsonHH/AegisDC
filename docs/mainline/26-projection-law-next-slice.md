# Proposed next projection-law slice

Status: design supplement only, after the four first-review boundary corrections. No new report law or informative candidate behavior is implemented by this note. The existing v1 projection remains closed and unchanged.

## The remaining input gap

The producer can emit a bounded numeric reading in a positive, negative or threshold-straddling bin, or a missing/unknown result. The existing action-value model specifies only P(positive|joint outcome) and its binary complement. Those two numbers do not establish probability zero for straddling or missing classes. Without an additional declared support restriction or a full conditional class law, a prospective informative check remains unmodeled.

The minimal proposed revision is `aegisdc-evidence-projection-v2`, keeping all v1 fields and adding `report_class_support`. Each closed row binds `question_id`, `inspection_task_id`, `record_id`, `assumption`, `source_note`; the supported initial assumption is `SUITABLE_COMPLETED_INSPECTION_RETURNS_DECISIVE_BINARY_BIN`. It explicitly assigns zero forecast mass to missing, unknown-quality and threshold-straddling classes, conditional on the declared suitable completed inspection. Positive mass is the unchanged existing value-model likelihood; negative mass is its complement. This is an uncalibrated synthetic forecast assumption, not a claim that the real producer cannot fail or become indeterminate. Actual execution, error realization, suitability checks and records remain unchanged. Both the baseline and candidate receive the same public declaration; no policy gets privileged data.

If that support assumption cannot be justified for a later research configuration, use an explicit versioned conditional class law with every class and outcome normalized, or keep the plan unknown. Do not derive missing/straddling probabilities from their absence in an engineering sample, guess a constant likelihood or select a probability to make the candidate pass.

## Two next finite witnesses

Keep the six-second service/work/report model, P(impairment)=1/4 and original positive likelihood4/5 versus1/10. The same existing neutral fixed report has identical state likelihood1/2; no current same-binding/provenance conflict, pending inspection or scheduled future background record is declared, and the projection remains in one belief epoch.

1. Declare the fixed and handheld channels conditionally independent under the existing model's public pair. The fixed report remains current through arrival; the symbolic positive/negative handheld factors are therefore admitted. Under the explicit binary support restriction, the candidate should select inspection with expected deficit39/40. Positive posterior impairment is8/11; negative is2/29. These expectations are from the original joint masses and work delays, not sampled future values.
2. Remove that independence pair and let the neutral fixed report expire before the planned handheld arrival. Rebuild current/expired priority: the prospective current handheld now precedes the expired fixed record. The candidate must not reuse the current-time exclusion. Removing a nonzero state-uniform factor cancels under exact normalization, so the projected branch beliefs and current joint world weights are compatible; the same inspection expectation39/40 applies. General nonneutral expiry is not covered by that cancellation proof. A change of future decision belief never redraws the evaluation world's current outcome weights.

Admission proof should use exact symbolic record identities, epochs and polarities or exact normalized masses, never rounded posterior equality or representative numeric sampling. A zero-support class can be omitted only because the public assumption says so. If a possible class changes the selected factors and compatible conditional context law cannot be established, return a null value with the reason.

## Retained limits

This next slice would add a forecast support assumption, not a sensor or plant intervention. It must bind to the public inspection model/target/tool/qualification/work/latency/validity/provenance declaration. It does not assume live fixed polling stops; known intervening arrivals without a joint law still make the plan unmodeled. Online v4 execution, equality of public inputs, no-problem/direct/defer alternatives, exact budgets/authority and actual failure feedback remain later required slices. No effect trial, tuning comparison or candidate acceptance follows from these two planned unit witnesses.
