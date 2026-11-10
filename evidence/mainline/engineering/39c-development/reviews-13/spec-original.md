# Cost42 original finite Spec findings

Independent `/root/review39c33_spec`,111bff75...ec6a26fc. Two findings; not a Spec PASS.

1. **39C-COST-SPEC-07,P2:** `_computation` aggregates only model_evaluations and discards the existing `policy_computation_audit.instance_closure_evaluations`. Preserve the observed counter and coverage; internal nested calls stay unknown. The42closure=null witness cannot detect this omission.
2. **39C-COST-SPEC-08,P3:** absent admission ledger yields fee statusNOT_RECORDED,where contract42 requiresNOT_APPLICABLE. Distinguish absence of the fee concept from a missing fee record.

Other first-slice units/actual totals/unknowns/private evaluation conform. Frozen input/test,56red source records and receipt hashes match. Green execution was outside the review. No test or remote operation; not fullcost/39c acceptance.
