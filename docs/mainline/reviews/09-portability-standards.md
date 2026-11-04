# Ticket 09 portability Standards delta review

Baseline: 1ed6669221fd32a7ecfcc09d20292170505e89a8.
Candidate: 082547e2ff32c98448a2b118519cb91f26e156b7.

Hard standards: 0 material findings. The single root portability finding is addressed without rewriting its historical evidence. All 24 changed paths are confined to ticket/current explanations, the new v2 inventory/verifier and preserved portability-validation records. Runtime source, configuration and tests are byte-identical. All 162 Git-delivered files from the original 164-entry observation, the original receipt, v1 helper and legacy inputs retain their Git identities and original hashes. The copied original root blocker readback is byte-identical.

The new classification covers exactly those 162 durable files and the two specifically named, historically untracked interpreter caches. Their original observed hashes remain recorded. No arbitrary failed hash is skipped. The verifier requires its own bytes, the classification manifest and durable current files to match HEAD Git blobs; durable originals also match the historical delivery. Recorded physical source is checked at execution commit 363c5edf and current-source equality is reported separately. Twelve saved cases, 74 artifacts, six refusals and six legacy inputs remain distinct from new execution.

Heuristic baseline: 0 material findings. A standalone read-only evidence tool keeps historical behavior intact and avoids runtime/author imports. Reviewed five preserved validation records and their hashes: old-v1 failure, three v2 passes across differing cache states, and changed-tool rejection. Candidate attributes pass whitespace checks. No physical tests, simulation or full regression were repeated for this review.
