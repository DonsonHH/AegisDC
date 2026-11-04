# Supplemental Spec/delivery review: ticket 09 portability

Baseline: `1ed6669221fd32a7ecfcc09d20292170505e89a8`.
Frozen new tool/classification: `9ef2eb5a920b63c8e5cd48ad597b4774695684c9`.
Scope: read-only artifact delivery correction; the earlier physical/control Spec report is unchanged.

## Spec/delivery

**Root finding: 1; closed after revision: 1; remaining: 0.** The original author-local 164-row inventory contained two untracked interpreter caches. Treating that inventory's local PASS as a portable Git-delivery check caused the old verifier to fail on a fresh checkout. This was a delivery-verification defect; it does not invalidate or rerun the recorded physical execution.

The correction is explicit: 162 durable files plus exactly two named non-delivery caches, retaining both original cache hashes and reasons. The original receipt, all 162 indexed persistent files, old helper/verifier code and physical source/config/tests remain unchanged. The fixed diff has no intersection with the old inventory; independent durable-byte rehashing passed.

The new verifier checks its own and the classifier's HEAD identities, the pinned original receipt, exact inventory partition, every durable file's original-delivery and current HEAD blobs, six legacy input identities, 74 saved artifacts, twelve cases and six refusals. Execution-source hashes are checked against actual `363c5edf` Git blobs. Equality of current source bytes is reported separately; the old execution is not reattributed to a later commit.

Independently executed V2 successfully, confirming those counts and unchanged source identity. Reviewed real retained old-V1 missing-cache failure, V2 fresh-checkout missing-cache and different-cache successes, and tampered-new-verifier self-check refusal. All fifteen files underlying the five validation receipts passed fresh hash checks. No other hash failure is exempted.

Independent readback summary: `aegisdc-review-09-portability-readback.json` beside this report. This supplement performed no simulation, 16-target repetition, full regression or repository edit. M1, calibration and research outcomes remain separate gates.
