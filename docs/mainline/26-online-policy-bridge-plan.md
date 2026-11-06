# Online bridge for v4 policy declarations

Status: planned next stage after the A/B review. Current pure selection support is not evidence that the candidate runs online. No runtime change or new physical run is made by this plan.

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

Work one public behavior at a time, retaining failed logs and exact source identity. The final finite engineering protocol, source, tools, declared durable set and budget are frozen before capture in a new dated output directory. These planned cases have not been frozen or run. Independent saved-result review, actual rendered physical-data and architecture figures, fresh-checkout verification, root integrated checks and publication are still required. Ticket26 remains claimed and the complete research goal active.
