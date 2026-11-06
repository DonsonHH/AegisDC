# Online bridge for v4 policy declarations

Status: implemented D-stage development after the shared numerical path, with actual same-facility and CLI runs. Frozen finite engineering capture, independent D review, fresh delivery and root acceptance remain pending. Earlier planning text below records the intended boundary; actual outcomes and preservation are listed at the end.

## Schema boundary

The existing facility run program-v3 already carries the policy declaration, public profiles, private realizations, preparation requests and optional closure template. A policy-program-v4 can be transported there without inventing a separate run-program-v4 merely because the policy version increased. The bridge must explicitly support that combination and preserve the closed contracts of earlier run/policy schemas.

Before online execution, use public declarations to verify that projection.inspection_profile exactly equals the executor's public inspection profile and that projection.background_sensor_profile exactly equals the executor's public fixed profile, including null/absent-channel identity. The private realization stays exclusively in the executor. Mismatches must fail before the proposed action can be issued. Public validation must not invoke a private inspection session as a feasibility oracle, query future samples or create a decision before its declared clock time. Model/preflight calls, if any, must be counted as such.

## Inheritance that must be completed

The v4 path must inherit every v3 rule, including the same public intervention declaration as execution; inspection-versus-intervention kind binding; target/tool/qualification and known measurement-work checks; actual arrived feedback; permanent cumulative admission spending; final public resource ledger; future authorization; exact decision instants; closure fed only by actual arrived action reports. Both closest baseline and candidate need the same bridge validation. The current explicit v3 equality checks in `policy_execution.py` and the plant's final resource-ledger condition are incomplete for v4 and require deliberate public slices.

Pure `choose_work` validation order remains authoritative: malformed nested declarations raise contract errors before binding lookup. Constructor validation should reuse closed public rules and never compute a hypothetical decision from future evidence to validate structure. Static capabilities and actual private execution remain separate gates.

## Proposed same-facility witnesses

A useful engineering witness can keep the complete eight-domain model, actual handheld measurement, same actor/tool and sparse fixed polling. A fixed power channel with period10s, phase0 and delay0.5s continues sampling; decision times1,2.5,2.75,4.5 within a6s run see the initial fixed record and no new fixed arrival in the predicted inspection window. Under the same neutral power likelihood, declared independent handheld pair, shared support regime and shared valuation basis, issue inspection at1, measure at2.25, make the record available at2.75, then optionally issue action and complete it at4.0; its report arrives4.5. An optional closure template must remain pending without sufficient post-action restoration evidence.

The existing network bottleneck remains0.25, so literal demand6 unit-s, delivery1.5 unit-s and deficit4.5s remain an independent service witness. This does not establish strategy benefit. Every compared policy receives the same world, resources and declared information; fixed sampling is not disabled to create candidate admissibility.

A paired context with a known pending fixed arrival must produce an unknown contingent inspection value while direct/defer remain defined. Additional finite direct and defer cases must be reported as actual execution/selection behavior, without asserting that all scenarios favor checking. Paid rejection, aborted work or unsuitable/indeterminate observations must return the real executor feedback and preserve the forecast-assumption mismatch, not a fabricated successful record.

## Delivery gates

Work one public behavior at a time, retaining failed logs and exact source identity. The final finite engineering protocol, source, tools, declared durable set and budget are frozen before capture in a new dated output directory. These development cases do not constitute a frozen formal protocol. Independent saved-result review, actual rendered physical-data and architecture figures, fresh-checkout verification, root integrated checks and publication are still required. Ticket26 remains claimed and the complete research goal active.

## D-stage development outcomes

RED34 completed the actual inspection/action trajectory but failed its public final-ledger assertion because the plant output included that ledger only for v3. GREEN35 adds the v4 ledger path and verifies the one-facility timing,6/1.5/4.5 service integrals,2 actual work person-s and20/20/2 admission envelopes. Fixed polling continues; the physical6s horizon and per-decision relative forecast6s window remain different objects. The first decision's forecast window is1–7s, not an implied extension of the saved physical run.

RED36/GREEN37 require exact matching public inspection/background profiles (including null) for both value policies before any online decision. RED38/GREEN39 inherit the v3 action-declaration and task-kind constructor gates; v4 uses the full shared closed model validation at its actual decision instant instead of calling an incomplete early value-binding consumer to generate a future or preflight choice. No private observation realization or future measured value enters selection.

Existing behavior boundaries40–43 pass without manufactured failures: known pending fixed arrivals give a null contingent value but still allow actual direct work; an actual unsuitable measurement remains a missing/unknown record with `UNCONFIRMED` feedback; a state-constant report likelihood can be admitted yet favor direct intervention because it offers no modeled benefit; and zero modeled impairment can produce deferral with no generated tour. That last case is a limited/mistaken modeled belief, not an actual healthy plant: the same real network bottleneck still produces4.5s deficit.

The closest baseline with optional actual-arrived closure feedback completed the expected trajectory in44, but the test incorrectly expected `ACTION_NOT_AVAILABLE` at the pre-action decision. The real closure contract reports `OPEN_UNCONFIRMED`. The failed assertion and completed physical original are unchanged;45 checks that same saved run under the corrected literal, including `ACTION_COMPLETED_PENDING_VERIFICATION` after the actual action report, without a physical retry. The test source's expected literal was corrected for future runs.

The CLI attempt46 was interrupted by tool transport. Its original log is0bytes, process is no longer live, and no terminal receipt or saved output exists. That is an unobserved outcome, not proven success, failure or proof that physics never started. A separate observation record preserves those facts. New attempt47 uses a new UUID, completes the actual CLI run, and invokes the CLI again against the existing output; the second invocation is rejected before simulation and every original output hash remains unchanged. It is a separately accounted development attempt, not an invisible retry or a repeat of a sealed protocol trial.

## Durable development preservation and gaps

The [2026-11-07 D original package](../../evidence/mainline/engineering/26-candidate/development-originals-20261107-01/receipt.json) declares six durable files and529 ZIP members, including original attempts/terminals, all saved scenario/run/private-state/balance files, captured runtime/test-tool snapshots, explicit hash-matched source recovery, and the independent interruption observation. It covers30 public attempt directories:16 known completed integrations,12 original error terminals without a completed run, one pre-simulation overwrite refusal and one unobserved interruption. Known completed durations sum to approximately48.08s; the unknown call is not silently treated as0s. Completion of physics is not acceptance of a test assertion:34 and44 remain failed test logs.

All2010 recorded runtime-file hashes are accounted for, including a labelled exact inverse-patch reconstruction of early dirty bridge source where it matches the original attempt hash. Such recovery is not represented as an original pre-call snapshot. Twenty-six cases have explicitly recorded historical input or authoring-tool capture gaps; early refused-call inputs without authoritative originals are not fabricated. Completed-run inputs can be recovered as the actual declared scenario/program from their original save-run files, without claiming original preflight input bytes. Newer calls capture exact input JSON and runtime/test tools before execution. Automatic caches are excluded.

`scripts/verify_candidate_development.py` only reads saved bytes and Git blobs; it reports `PASS_WITH_DECLARED_HISTORICAL_DEVELOPMENT_GAPS`, not ticket acceptance. No formal engineering case or scientific gain is proved by this development archive. The later frozen protocol must capture complete inputs, tools, source and attempt outcomes before new calls.
