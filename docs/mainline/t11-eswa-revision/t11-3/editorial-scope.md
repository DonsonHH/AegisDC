# Editorial scope for the ESWA revision

The journal is *Expert Systems with Applications*. The working title follows the recommended option in the accepted [positioning record](../positioning-and-outline.md). The article assigns sections 1–8 to the decision problem and complexity, scheduling, confirmatory comparisons, descriptive duration strata, incident analogues, the post hoc panel, conditional risk, and feedback. The section numbers, table letters, figure letters and pagination are editorial locators.

| PI review item | Source fixed before the rewrite | Required reading |
|---|---|---|
| Myopic inspection | [Pre-run interpretation](../t11-1/interpretation-before-run.md), [paired rows](../t11-1/results/analysis/panel.md#L11-L16) | Exact rowwise service identity. Dispatch sequences, personnel and charges differ on three rows. |
| Finite-budget POMCP | [Estimates, closure and tree accounting](../t11-1/results/analysis/panel.md) | Service direction unresolved. Give labour, fees, verified closure, the elective and no-admissible-branch counts, depth and simulation budget. |
| Post hoc strata | [Reserve and duration rows](../t11-1/results/analysis/panel.md#L82-L88) | Both named rows belong in supplementary results, outside the abstract and conclusions. |
| Labour price | [OAT](../t11-1/results/analysis/panel.md#L63-L72) | Present paired service and personnel differences together at the higher price. The frozen comparison remains the unit of interpretation. |
| Clocks and qualification | [Stage-zero receipt](../t11-1/stage0-receipt.md) | Label the centre's outer IPC replay wall clock in the text, timing table and figure caption. The centre's internal CPU was unavailable. Retain the failed witness and identify the one-line fix in Supplement B. |

The two Slurm gaps were read directly through the project login. Both were other-account allocations. The append-only accounting commit is `10b3f7a08462623c22b87b3ae0dae7abe3c95378`. At that revision the original T11-1 checker passed with checkout-byte verification for all 124 files. Its refreshed index SHA-256 is `42dad67b2a63befa5e9626e311e16c7178731d1295262bc4fd02f3e98c100fd4`.

The accounting correction and the qualification correction concern different records. The accepted stage-zero receipt already retains job 135630, the initial 9/10 outcome at `55d37ee8`, and the corrected 10/10 outcome at `3a096231`. Comparing the two versions of `worker.py` identifies the single changed assignment, JSON 2.0 to 2. The timing source is job 135631. These are records of the preceding study.

All manuscript work in this directory uses public, previously released materials. The formal target of review is the present paper package. The venue decision, review requirements and manuscript preparation do not authorize submission.
