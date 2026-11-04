# Spec review: mainline ticket 09

Fixed baseline: `de5dbc69d105fb86f97e3e4d067dd91663f32760`.
Reviewed candidate: `1ed6669221fd32a7ecfcc09d20292170505e89a8`.
Command: `git diff de5dbc69...1ed66692` in the dedicated `full-site-09` worktree.
Contracts: ticket 09, full-facility specification, MAINLINE, ADR0003, accepted control design and verification declarations.

## Spec

**Findings: 0.** No missing/partial requirement, scope creep or incorrect implementation was established within this finite local-control slice.

The profile and its five required typed parameters become accepted together with actual nonideal behavior. Signed measurement offsets have separate quantity types; physical quantities retain their domains. Static/timed availability is strictly binary. Unsupported profiles, missing/wrong parameters and incompatible events fail explicitly.

The plant constructs reports only on its local sampling clock. The transition consumes reported measurements instead of evaluator truth; biases change actual commands without replacing physical flow, temperature or conservation state. Invalid reports enter the declared fail-safe, power cycling preserves a held latch, supervisory loss leaves local protection autonomous, and neither link recovery nor an in-band valid report overrides reset gates. Output remains private/local. Prior post-control room-access ordering and dynamic leakage/storage physics remain intact.

Independently executed all 16 targets, passing without skips. Fresh-read verification matched 12 saved cases, 74 saved engineering files, 164 older packaged originals, six legacy input hashes/Git blobs and frozen source identities. The six expected refusals remain separately recorded. Author optional-Torch skips are disclosed; root full acceptance remains separate.

An additional compound probe uses .7 s sampling and .37 s integration, chaining a high report, hysteresis-band report, supervisory loss, power cycle, invalid channel, link return and safe new sample. The literal expected mode sequence passes; protection remains latched until the 3.5 s reset sample, producing 3.5 s deficit and .6 normalized service-unit s delivery. Exact script, input and output are saved in `aegisdc-review-09-spec-attachments/` beside this report.

No full suite, repository edit or future policy/research run was performed. M1, field calibration and scientific gains remain separate gates.

Spec total: **0 findings**; no blocking issue.
