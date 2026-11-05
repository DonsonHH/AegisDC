# Sparse fixed channels and reported control records

Ticket 16 is an evaluator-only observation producer. It converts declared
measurable signals from a private saved trace into the existing ticket-14
record schema. It does not change the plant/controller, infer risk, choose work,
or establish an inspection or AI benefit. Primary engineering examples contain
sparse fixed instruments and separately authorized reported control records.

`validate_channel_profile` detaches a closed static declaration. Its `ledger`
is a valid ticket-14 registry with an **empty records array**; pending history or
future measurements cannot be included in `public_model`. The declared target
coverage and signal whitelist are static, rather than an all-asset health mask.
Unchanneled historical/human sources may share that registry and accept records
through the unchanged ticket-14 API.

`sample_trace(profile, private_trace, realization)` is a private backend seam.
It returns a legal full ledger queue, static public model and separate private
audit. Dispatch receives only `EvidenceLedger(result['ledger']).snapshot(t)`
plus the static public model. The private production envelope, full future
queue, seed, draw buckets, actual bias and diagnostics are not dispatch data.

Polling epochs are decoded phase plus index times period, rounded once to the
supported numeric coordinate. At each poll the adapter uses the latest saved
point **at or before** it; no forward peek or interpolation is performed.
Fixed-signal observation time is the selected point's actual time. A reported
controller value retains its own `sampled_at_s`. Polling cached data does not
refresh its observation time or validity. Arrival is poll time plus declared
delay, rounded upward to a representable coordinate; exclusive expiry is
similarly derived from observation time plus validity. Ticket 14 still applies
its exact gate: even a one-ULP future arrival is unavailable.

Separate transfer IDs use the channel and polling index. Transfers of the same
measurement/actual observation coordinate retain a common origin. Noise and
read-availability use SHA-256 counter keys containing a private seed,
measurement ID, normalized decoded observation coordinate and draw purpose.
No mutable RNG or dispatch query count participates. Numeric perturbations are
bounded discrete-uniform draws; availability failures generate explicit null
readings, not zero. A statically disabled instrument emits no records.

Public quality is a **declared assumption**: nominal bias/noise limits and a
static quantization allowance, never `abs(actual_bias)` or the realized draw.
The quantization allowance covers at least one ULP over the nominal output
range when nominal errors are nonzero. Private error realizations may violate
these assumptions for miscalibration examples; public quality/note/model are
not retrospectively changed. Violations are private evaluator diagnostics.
Unknown controller calibration remains unknown. Controller validity flags are
reported fields, not direct fault labels or claims of physical truth.

Identity records preserve numeric zero and negative values. Declared threshold
and validity transforms produce JSON booleans; null readings have unknown
quality. Same-measurement threshold/raw packets share their carried origin,
while a declared shared calibration group remains visible in source metadata.

The current literal examples test public behavior only. A separately frozen
same-V6 saved-trajectory engineering capture, source/delivery byte proofs and
independent root reviews are required before ticket acceptance. Field
calibration, registered mechanism comparisons, agent and RSI stages remain
pending; source-level green tests do not complete M3 or the research goal.
