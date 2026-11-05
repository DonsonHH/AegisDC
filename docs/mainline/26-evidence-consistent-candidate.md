# Evidence-consistent contingent planning candidate

Status: proposed contract and first development witness, ticket26 claimed. No candidate implementation, acceptance or effect claim is established by this document. Base policy execution is the accepted25 implementation; its protocols and original outputs stay unchanged.

## Single mechanism

The candidate changes only whether the planned inspection's possible records can support the modeled contingent decision under the declared evidence updater. It retains the closest `one_observation_lookahead` baseline's loss catalog, current prior, report likelihoods, physical response assumptions, work/cost model, actor capabilities, authority, cumulative admission account and deterministic tie rules. The candidate may inspect, intervene directly or defer. It is a bounded first-action planner, not a claim of globally optimal maintenance or physically absent information.

The existing task/value binding does not supply a forecast record's source, observable, quality, provenance or validity. It also does not declare other records expected before the planned report. The candidate therefore requires the following new common public declaration. It cannot infer these fields from private execution state.

## Common public extension

Proposed `aegisdc-dispatch-policy-program-v4` has the v3 fields plus `evidence_projection`. All five existing policies may receive exactly the same extension; the closest baseline can ignore its forecasting mechanism while retaining it as accessible public input. Earlier schemas retain their closed contracts and behavior.

`evidence_projection` is a closed object with:

- `schema`: `aegisdc-evidence-projection-v1`.
- `basis`: `synthetic_assumption`.
- `source_note`: provenance of the finite prediction assumptions.
- `inspection_profile`: the public `aegisdc-inspection-profile-v1`, without realizations or any actual sample. Task/model/record identities, source/target/observable/unit, reported quality bound, provenance, latency and validity bind to the same declaration used by execution.
- `background_sensor_profile`: the public fixed-channel profile, or null when that input is absent. No realization, future values, private trace or backend handle is permitted.
- `context_assumption`: `NO_UNSCHEDULED_RECORD_ARRIVALS_UNTIL_PROJECTED_REPORT`.

The context assumption is a finite forecast restriction. Actual fixed sampling continues. Known background arrivals, including previously polled but still pending records, are derived from the public fixed profile's phases, periods and channel delays. If any other record will arrive between the current decision and the projected inspection report, and its joint report/context law is absent, the prospective inspection value is `UNMODELED`; the candidate never pretends that record is absent or reads its eventual value. Unscheduled manual reports can invalidate the forecast assumption in execution and must remain an explicit limitation.

The actual run bridge must match both public profiles to its execution declarations. Numeric projected record classes use the producer's bounded quality and positive/negative/threshold-straddling/missing partition; they are symbolic counterfactuals, never ingested into the live ledger. Projection cannot fabricate a genuine observation or change the original likelihood table.

## Admission and value contract

Use the declared travel, wait, work and report latency to predict observation/arrival times. Rebuild the public evidence snapshot at that arrival: expired rows remain historical; current/expired priority, declared channel order, same-channel replacement, provenance, dependency groups, conflicts and belief epochs follow the accepted updater. A current exclusion does not prove a future exclusion. The first implementation slice supports a single belief epoch; crossing an epoch is explicitly `UNMODELED` until a consistent dynamic projection is implemented.

Only when the projection covers every producer report class, has no unmodeled background arrival, and gives exactly the same admitted belief and continuation action for every class may it declare `NON_ADAPTIVE_UNDER_DECLARED_UPDATER`. For every original joint outcome h, marginalizing reports gives sum_b P(b|h,current history)=1. The branch therefore uses the unchanged original joint outcome mass and unchanged service/cost model, pays the inspection and its delay, and selects one common subsequent action. Probability1 here is marginalization over reports, not a fabricated true report, statistical independence claim or replacement likelihood.

If a possible class changes admission, belief, action or conflict handling and the requisite conditional law is missing, its contingent value is `UNMODELED` with a null score. Work can remain publicly feasible. Modeled direct/defer alternatives and the declared basic inspection fallback remain available; a null value is never zero gain. A useful admitted inspection may retain the original finite conditional report law only where it is compatible with the projected updater; no arbitrary state-independent likelihood is substituted to make a case pass.

Outputs must identify the assumption, predicted observation/arrival times, covered report classes, admitted or excluded factors, classification or missing law, chosen first action and separate model/computation costs. Every real task still passes the existing private executor. No actual plant state, future sensor value or private realization enters this calculation.

## First discriminating development witness

Use a new six-second finite service model: demand1 throughout; prior impairment probability1/4; impairment delivers0, other outcomes deliver1. Inspection has wait1/4s, work1s and report delay1/2s. Intervention has wait1/4s, work1s, during-work capacity0 and afterwards capacity1. The original prospective report law remains positive with probability4/5 under impairment and1/10 otherwise. A currently arrived higher-priority fixed report has equal likelihood under all states, remains current through the projected report, and is not declared independent of the prospective handheld channel. There are no competing records on the handheld binding, no epoch crossing and no other scheduled arrival in the projection interval.

Independent literal results under that model are: defer3/2s service deficit; direct intervention17/16s; the closest baseline's contingent inspection39/40s. Under a proved invariant updater the inspection cannot adapt: its best common continuation is defer, at3/2s deficit after paying the inspection. The candidate should therefore choose direct intervention while the baseline chooses inspection. These are model predictions, not measured physical improvements or research effect results.

The adjacent expiry witness must rebuild the projected snapshot: if the fixed report expires before the projected handheld arrival, the handheld can become the representative. The candidate must not reuse the old exclusion. Later slices must also cover informative independent evidence, pending/background arrivals with missing law, copies and conflicts, unknown quality, missing results, qualifications/authority/budgets, no useful service effect and exact time boundaries. This ticket remains claimed until the full frozen engineering, independent and root gates are satisfied; no registered effect comparison begins before30.
