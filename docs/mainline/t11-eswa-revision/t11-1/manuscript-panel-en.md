# Supplementary panel: online planning and policy-parameter sensitivity

**Post hoc, nonconfirmatory.** The panel was fixed to the 72 previously consumed development conditions. The archived centre policy retained its original scores. Each new arm had its own state, evidence, resources and receipts.

## Alternative online methods

Differences below are centre minus comparator. Negative service deficit means the centre lost less service. Intervals are two-sided 95% marginal percentile intervals from the registered 10,000 paired, within-family resamples.

| Comparator | Compliant pairs / planned | Deficit difference, s [95% interval] | Labour difference, person-s [95% interval] | Fee difference [95% interval] |
|---|---:|---:|---:|---:|
| Myopic VoI | 72/72 | 0.00 [0.00, 0.00] | 1.46 [-0.97, 4.38] | 0.04 [-0.03, 0.12] |
| Finite-budget POMCP | 72/72 | -57.50 [-118.06, 9.36] | -72.78 [-93.96, -52.71] | -1.35 [-1.69, -1.00] |

**Myopic VoI.** The interval included zero. This comparison did not establish a directional advantage. The raw deficit was equal on all 72 conditions. The issued request sequence differed on 3 conditions.

**Finite-budget POMCP.** The interval included zero. This comparison did not establish a directional advantage.

## One-at-a-time sensitivity

Each row changes one setting of the frozen centre. Differences now run from variant to centre (variant minus centre). Positive deficit means more service lost by the variant. The physical facility and accounting rules use their original settings.

| Changed parameter | Pairs / planned | Absolute deficit, s | Deficit difference, s [95% interval] | Absolute labour, person-s | Fee units |
|---|---:|---:|---:|---:|---:|
| Labour price λ = 0.5 | 72/72 | 525.59 | 3.54 [-8.75, 22.92] | 141.94 | 2.96 |
| Labour price λ = 2 | 72/72 | 580.86 | 58.81 [6.67, 124.69] | 93.40 | 2.00 |
| Fee equivalent κ = 15 | 72/72 | 521.63 | -0.42 [-1.25, 0.00] | 135.62 | 2.78 |
| Fee equivalent κ = 60 | 72/72 | 525.38 | 3.33 [0.00, 10.00] | 128.40 | 2.67 |
| Sensor match p = 0.85 | 72/72 | 522.67 | 0.62 [0.00, 1.88] | 136.11 | 2.79 |
| Sensor match p = 0.99 | 72/72 | 522.05 | 0.00 [0.00, 0.00] | 135.62 | 2.78 |
| Uninterpretable report q = 1/64 | 72/72 | 522.67 | 0.62 [0.00, 1.88] | 136.11 | 2.79 |
| Uninterpretable report q = 1/16 | 72/72 | 522.05 | 0.00 [0.00, 0.00] | 135.62 | 2.78 |

Raising the labour price from 1 to 2 changed mean labour by -42.22 [-57.85, -27.78] person-seconds and mean service deficit by 58.81 [6.67, 124.69] s. These one-factor contrasts describe the registered settings on the consumed panel.

## Absolute service, resource use and work closure

Rows give condition means over each complete compliant scope. Refusals count the recorded candidate/admission refusal entries. Failed or unfinished work is reported from the actual workforce records. NA and PV count valid closures at window end, respectively without intervention and after verification of an applied intervention.

| Policy | Deficit, s | Person-s | Tool-s | Fees | Refusal entries | Failed / unfinished work | NA / PV at 3,600 s | Hard / unresolved started positions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen centre | 522.05 | 135.62 | 135.62 | 2.78 | 242.71 | 0.00 / 0.00 | 0.19 / 0.50 | 0 / 0 |
| Myopic VoI | 522.05 | 134.17 | 134.17 | 2.74 | 245.00 | 0.00 / 0.00 | 0.19 / 0.47 | 0 / 0 |
| Finite-budget POMCP | 579.55 | 208.40 | 208.40 | 4.12 | 230.58 | 0.00 / 0.00 | 0.19 / 0.72 | 0 / 0 |
| Labour price λ = 0.5 | 525.59 | 141.94 | 141.94 | 2.96 | 238.43 | 0.00 / 0.00 | 0.19 / 0.56 | 0 / 0 |
| Labour price λ = 2 | 580.86 | 93.40 | 93.40 | 2.00 | 250.17 | 0.00 / 0.00 | 0.15 / 0.38 | 0 / 0 |
| Fee equivalent κ = 15 | 521.63 | 135.62 | 135.62 | 2.78 | 242.76 | 0.00 / 0.00 | 0.19 / 0.50 | 0 / 0 |
| Fee equivalent κ = 60 | 525.38 | 128.40 | 128.40 | 2.67 | 243.58 | 0.00 / 0.00 | 0.18 / 0.47 | 0 / 0 |
| Sensor match p = 0.85 | 522.67 | 136.11 | 136.11 | 2.79 | 242.71 | 0.00 / 0.00 | 0.19 / 0.50 | 0 / 0 |
| Sensor match p = 0.99 | 522.05 | 135.62 | 135.62 | 2.78 | 242.71 | 0.00 / 0.00 | 0.19 / 0.50 | 0 / 0 |
| Uninterpretable report q = 1/64 | 522.67 | 136.11 | 136.11 | 2.79 | 244.17 | 0.00 / 0.00 | 0.21 / 0.49 | 0 / 0 |
| Uninterpretable report q = 1/16 | 522.05 | 135.62 | 135.62 | 2.78 | 242.53 | 0.00 / 0.00 | 0.19 / 0.50 | 0 / 0 |

## Decision time and scope

| Policy / measurement | Returned timed decisions | Median, ms | 95th percentile, ms | Maximum, ms |
|---|---:|---:|---:|---:|
| Frozen centre / isolated worker replay | 4392 | 1.292 | 4.200 | 17.065 |
| Myopic VoI / new online as run | 4392 | 1.434 | 2.218 | 5.246 |
| Finite-budget POMCP / new online as run | 4392 | 1.390 | 28.697 | 52.730 |

Wall time spans public request serialization through response parsing. The centre timing source is identified in the table. Isolated replay uses archived public decisions whose returned proposals match their historical digests. Replay creates no new facility score. The timing ledger separates startup and reports worker CPU where observed, tree time and terminal evaluation time.

The run charged 720 native entries and retained 720 complete compliant scores. The two additional comparisons qualify the interpretation of C1 on this development panel. C1 and C2 retain partial support, the registered C3 transfer advantage remains unsupported, and an independent C4 increment remains unestablished. Original hypothesis tests and incident results retain their previous dispositions.

[Absolute resources, refusals and closures](results/analysis/scope-absolute.tsv) · [Paired endpoints and identification bounds](results/analysis/scope-contrasts.tsv) · [Timing by role and reason](results/analysis/timing.tsv) · [Complete development report](results/analysis/panel.md)
