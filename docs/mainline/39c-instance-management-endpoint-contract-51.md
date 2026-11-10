# 51：私有实例管理端点

Classification: engineering qualification, not a research comparison. Scope is the facility run interface already fixed in `.scratch/full-facility-mainline/spec.md`. Red source is `294e4f9b89935efca17e27339194edca308d241d`; green has a separately frozen commit. Protocol50's completed run is not repeated:51 declares a new private evaluation over a new actual execution with the same physical/public input values.

## Input and compatibility

Add `aegisdc-business-instance-closure-evaluation-v2` with the existing program fields. Each episode additionally declares `recheck_task_id`. Bind question/action/recheck to one public template and slot, and bind every observed assessment to that episode's actual opening and all three identities. Require native run v5 with public problem policy v2 and public instance closure v1 or v2. Private evaluation v1 retains its original public-v1 restriction; no existing result schema changes.

## Output

Return `aegisdc-business-instance-closure-result-v2`, PRIVATE_EVALUATOR_ONLY. Keep existing physical closure fields and carry each actual public question assessment as a detached complete value, including own_recheck, checks, trace, review_evaluations and historical_dispositions when present. Do not invent absent optional public fields. Include the declared recheck identity, actual completion and first public recheck report arrival separately from action completion/report.

`first_risk_accepted_at_s`, `first_escalated_at_s` and `first_false_alarm_reviewed_at_s` mean the first actual decision whose **current selected status** has that value. `first_question_closed_at_s` means the first actual assessment with question_closed=true. None means no such actual assessment, even if a later assessment reconstructs an earlier historical disposition. These are assessment clocks, not inferred physical transition times.

Collect current management trace records with observed_at_s, arrived_at_s, evaluated_at_s, status_at_evaluation and selected_at_evaluation; retain simultaneous lower-priority dispositions without calling them selected. Copy historical dispositions separately with the actual evaluated_at_s that exposed them. Historical arrival, current evaluation and first selected status must remain distinguishable. Management outcomes never set physical risk closure, claim restoration, change plant truth or alter diagnostic opportunity denominators.

## Literal positive and refusal examples

The frozen51 fixture differs from50 only in private business_program. One6-second V6 execution returns7 decisions. q0 opens0, action completes3.25/report3.75, own recheck completes5/report5.5, and first physical and question closure are5.5. q1 opens5.75 and is RISK_ACCEPTED at5.75: first_question_closed5.75, first_risk_accepted5.75, first physical closure null, no action or recheck completion/report and own_recheck.passed=false. Its review observation, arrival and first evaluation are5.75; the later evaluation6 is distinct. Only action-0/recheck-0 execute. Full private assessments equal the corresponding public assessments, without stripping identity or evidence fields.

Before physical integration, reject a mismatched recheck slot with `Business event must bind one declared public question/action/recheck rule`. Also retain the old private-v1 refusal of public-v2 closure with its original error. One selected test makes three facility-interface entries per phase; red completes no horizon and green completes one6-second horizon/seven returns. No direct choose, model, GPU or registered research call. One invocation per phase; preserve every failure and use a new protocol/root for any correction.

Expiry, escalation and evidence-reviewed false-alarm propagation require a later qualification; this positive slice alone does not accept those branches or39c. Diagnostic v3/native-v5 compatibility, the composite evaluator, recorded reading/replay, independent whole-ticket review, zero-skip root and fresh delivery remain open.

## Durable delivery

Freeze contract, protocol, exact full input, test, material reference, native runner/stager and runtime Git blobs. Preserve attempt/terminal/log, compact public/private endpoint and execution summaries with member hashes; keep full native traces/balances on the private server. Cache files are not delivered evidence. Compare all declared durable files with the manifest and execution source, without modifying old records.
