# Spec review: mainline ticket 07

Fixed baseline: `5da917895bc12d23eba37243215c8e42cc76fc9b`.
Reviewed source candidate: `5ca3c3a03d05802458cef1bdd10e66928d75bc1b`.
Final evidence tip: `d68425915d5a5d9308add320a22c96764db11812`; source/config/test diff from the candidate is empty.
Command: `git diff 5da91789...5ca3c3a0` in the dedicated `full-site-07` worktree.
Contracts: ticket 07, complete-facility specification, MAINLINE and ADR0003. Author-produced evidence was read afterward without modifying it.

## Spec

**Findings: 0.** No missing/partial requirement, scope creep or incorrect implementation was established within this finite environment/access slice.

Actual hot-water withdrawal decreases the dynamic hot mass and proportional sensible energy, transfers both to one mixed floor pool, and exports drain energy at the evolving pool temperature. The minimum hot inventory is an explicit validity boundary; below-domain operation is refused. Air, liquid, internal transfer and external nuisance-water accounts stay separate.

Gate permission, floor mass and directional room-temperature crossings act through the independent access graph. Ongoing jobs stop with spent time and actual carried-tool locations retained. Coarse traversal checks destination permission before entry; it does not claim continuous geometry or evacuation. Equality uses actual post-control heat direction. The unknown future control-profile field is refused.

The condensation result is explicitly a prescribed-RH boundary criterion with a cold-bulk surface proxy and a bounded liquid-water temperature domain; it creates no moisture, latent heat or dispatch evidence. Coefficients match the [official PsychroLib 2.5.0 SI liquid branch](https://raw.githubusercontent.com/psychrometrics/psychrolib/2.5.0/src/c/psychrolib.c); the [official API dewpoint example](https://psychrometrics.github.io/psychrolib/api_docs.html) supports the independent boundary check. This is not empirical facility validation.

Verification: independently executed all 22 targets, passing without skips. Expanded access-threshold verification covers 108 inlet/drain/threshold/step combinations: all stop at the analytic crossing. A separate 70-digit Decimal whole-facility mixing case predicts 16 kg floor water at 304.6563251666353 K, 2,421,995.1893353392 J drained and 996 kg hot water remaining at 320 K; observed accounts agree. Fresh reads pass 10 saved runs (nine engineering plus CLI), 30 artifact hashes/counts and six preserved input hashes.

Probe script/precise inputs/results are in `aegisdc-review-07-spec-attachments/` beside this report. No full suite, repository edit or new research run was performed; root acceptance, M1, field calibration and scientific gains remain separate gates.

Spec total: **0 findings**; no blocking issue.
