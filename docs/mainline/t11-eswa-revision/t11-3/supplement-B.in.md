# Supplement B. Online comparisons, sensitivity, timing and qualification

**Post hoc, nonconfirmatory.** All 72 original development conditions enter each full-panel contrast. Each of ten additional roles contributed 72 complete and compliant positions. The centre uses its original facility scores. In the tables below, a service interval is a marginal two-sided 95% within-family paired percentile interval. Conditional purchase splits describe observed actions after assignment. They cannot identify the effect of buying a report on selected rows.

## Service deficit by family and public maintenance duration

The difference is centre minus comparator, in normalized deficit-seconds. Durations and families partition the same 72 conditions in different ways. Each of the nine scopes is displayed. Associated absolute scores, paired sample counts and full-denominator identification bounds are in the accompanying data archive.

{{STRATA}}

The full-panel myopic difference was 0.00 [0.00, 0.00] s, with exact equality on every row and three differing dispatch sequences. The full-panel POMCP difference was −57.50 [−118.06, +9.36] s. A marginal subset estimate does not establish a duration interaction or a generally preferable policy.

## One-at-a-time changes

These rows give variant minus centre, which reverses the online-comparator orientation. All eight changes use 72/72 pairs each. Only the labour price, the fee equivalent, the fixed-sensor likelihood or the forecast's uninterpretable-report probability changes. Actual facility, execution costs and scoring are common.

{{OAT}}

## Outer IPC timing

Values are milliseconds from request serialization through parsing the complete returned proposal. The centre values came from isolated replay in job 135631. All 4,392 replayed public proposals matched the archived identities. The original worker's internal CPU clock was unavailable. Other rows are measured online. The detailed timing table separates startup, worker CPU where observed, tree transitions, terminal evaluation, and decisions for each return reason. A tree-wide median over all calls includes mandatory and non-search decisions.

{{TIMES}}

Only 903 of the 4,392 POMCP calls entered elective search (VALUE). On 3,156 calls no complete elective branch passed admission. The search budget was 128 simulated trajectories at an elective root, up to four public decision times each. A sampled world provided hypothetical outcomes; admission used node history. Relevant timing denominators and sources accompany every row in the machine-readable tables.

## Qualification and retained failure

The first public engineering attempt, source 55d37ee8, passed nine of ten witnesses. For the high labour price the worker serialized JSON 2.0 while the frozen descriptor and witness required integer 2. Commit 3a096231 changed that one line in worker.py. All ten witnesses then passed with the original witness specification. Both attempt receipts and both public-witness outputs remain in the data archive. Both attempts were in allocation 135630 and made zero facility calls. No scientific position was retried on the basis of this correction. Centre timing in allocation 135631 produced no centre score. The public readback and accounting record the historical releases and their identities. [Stage-zero receipt](https://github.com/DonsonHH/AegisDC/blob/93748f272939166b81ae4188299f096b0fa23fe2/docs/mainline/t11-eswa-revision/t11-1/stage0-receipt.md) · [Single-line worker correction](https://github.com/DonsonHH/AegisDC/commit/3a096231d6b7dd35c8661e4c29444fe7d78520f7)

## Complete data tables

The companion archive `supplement-B-tables.zip` preserves the original public files byte for byte from the accepted T11-1 release. Its catalogue `supplement-B-index.tsv` gives each entry's origin, record count when applicable, byte length and SHA-256. TSV is tab separated and JSONL contains one JSON object per line.

| Public file | Unit and contents | How to read it |
|---|---|---|
| scope-contrasts.tsv | One scope, comparison and endpoint. Includes complete planned and pairable denominators, estimates, intervals, directional counts and bounds. | Compare centre with each online baseline. Compare each OAT variant with centre. |
| scope-absolute.tsv | One scope, role and endpoint, including archived centre and original comparators where applicable. | Gives absolute service, staff, tools, fees, refusals, unfinished work and valid closure. |
| purchase-splits.tsv | Joint observed initial purchase status for both arms in each comparison and scope. | Read the class and pairable counts with every conditional mean. |
| timing.tsv | One role, clock, reason and metric. | Distinguish calls observed, calls measured and the units in the metric name. |
| positions.tsv and position-details.jsonl | One planned new position, condition, role, status and recorded outcomes, with the fuller work-order details in JSONL. | Issued stages I/A/R/X and closure snapshots use their recorded denominators. |
| witnesses.tsv | Conditional examples, linked to the comparison, subject or task, actual outcomes and comparison arm. | Mechanism illustrations retain their observed selection and scope. |
| analysis.json and panel.md | Complete structured report and the original human-readable tables. | Includes first/current closure, fraction of unmet demand, tree and leaf counters, all comparison scopes and missingness. |
| native-evidence-index.tsv and native-readback-receipt.json | Position-level release identities and the original readback receipt. | An index points to the archived original. Receipt status refers to the original readback. |
| jobs.tsv, per-role-ledger.tsv and accounting.json | Historical allocations, role costs, complete returns, scientific retry counts and total CPU use. | Allocation and batch steps are kept distinct in the accompanying accounting file. |
| qualification, center-timing and stage0 files | Initial failure, repaired outcome, fixed witness reports, the replay status and the version evidence. | These records identify engine qualification and timing provenance. |

The accompanying public risk tables give all family and scenario means for the frequency-weighted comparison, separately versioned at e3484fd1. No raw private trajectory is part of this archive.
