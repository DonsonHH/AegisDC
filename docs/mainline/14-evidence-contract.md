# Evidence ledger and explicit decision time

Ticket 14 adds `aegis_dc.evidence_ledger` to the complete V6 synthetic facility.
This is engineering information infrastructure. It does not estimate risk,
generate observations, execute a worker, or establish a mechanism benefit.
The existing hour-based foundation and private physical/control rules remain
separate. Tickets 15–17 add the decision-view audit and observation adapters;
ticket 22 connects actual professional execution to returned evidence.

`load_ledger(path)` reads strict JSON. `validate_ledger(document)` returns a
detached validated document. `EvidenceLedger(document).ingest(record)` atomically
returns `ADDED` or `ALREADY_PRESENT`. Repeating the same ID and equal validated
content adds no second sample; numeric `1` and `1.0` have the same JSON-number
meaning; an equal repeat retains the first accepted record representation.
Reusing an ID for different content raises `ValueError` without changing
the ledger. `snapshot(as_of_s)` returns detached plain JSON data.

The closed `aegisdc-evidence-ledger-v1` document declares a ledger/facility ID,
synthetic basis, seconds, entity IDs, typed SI observables, named sources and
records. A source declares its kind, basis, object/observable coverage, optional
dependency group and source note. Kinds cover asset records, maintenance
history, sparse fixed sensors, control records, human reports, work orders and
handheld results. Source kind does not establish independence or accuracy.

Records carry ID, source, target, observable, SI unit, scalar value, observation,
arrival and exclusive validity-end times, quality, and reported provenance.
Observation and arrival times may precede t=0. Observation must not follow
arrival. A null validity end declares no expiry; otherwise it must follow the
observation. A late arrival does not extend validity. At `as_of_s == valid_until_s`
the record is expired. No epsilon, event bucketing, or plant clock convention is
used: an arrival one binary64 ULP in the future remains hidden.

`snapshot` first selects `observed_at_s <= as_of_s` and
`arrived_at_s <= as_of_s`, then derives every record list, correlation and
conflict from those selected records alone. `records` includes received expired
and missing records for audit. `current_record_ids` includes only received,
present, unexpired values. Age is the exact difference of the decoded decision
and observation numbers, published as an integer when integral and otherwise
rounded once to binary64. An age outside the supported finite numeric output
domain is refused consistently. Equivalent integer/float timestamp encodings
therefore give equal ages. Selection and expiry comparisons never use this
rounded diagnostic age. Numeric zero,
negative offsets and JSON `false` are values; only null means missing. Binary
observations require JSON booleans, not numeric substitutes.

Numeric quality is either a declared nonnegative absolute `error_bound` in the
observable's SI unit, or `unknown` with a null bound. Boolean/category observations
use `reported` or `unknown`; neither means verified truth. Missing values require
unknown quality. The ledger does not convert unknown quality into a confidence,
posterior, true state, or independent sample count.

Each received record explicitly carries an opaque `origin_id`, plus an optional
`copied_from_record_id`. They are reported provenance, not private lookups. A work
order can arrive first and retain its carried origin token/reference even if the
original alarm never enters the ledger. Shared origin tokens and declared source
dependency groups produce correlation groups containing visible record IDs only.
Common explicitly carried copy references and visible direct copy links also
form correlation groups. A visible copy link with different claimed origins is
reported as `copy_origin_mismatch`; a completely visible copy cycle is reported
as `visible_copy_cycle`. These issues neither erase the known copy relationship
nor choose a trusted root. An unavailable parent creates no inferred issue.
The ledger never traverses a missing/future copy chain to discover another root,
source or payload. Distinct tokens are not proof of independence:
`independence` remains `NOT_ESTABLISHED`. Missing provenance cannot be guessed.

Conflict output is a transparent discrepancy ledger, not truth arbitration.
Only present values of the same target, observable and exact observation time
are compared. Disjoint declared numeric intervals are
`disjoint_declared_bounds`. Interval comparison uses exact rational arithmetic
on the already-decoded finite integer/binary64 numbers, so floating endpoint
rounding cannot erase a positive declared gap. It does not reinterpret decimal
input text as an exact decimal measurement or widen an error bound.
Different values with unbounded/reported quality are
`different_reported_values`. Overlapping intervals and sequential observations
are not flagged as contradictions. Expired discrepancies remain visible for
audit alongside each record's availability. No source wins a conflict here.

`id` is a declared public static ledger name, not a filename, case, seed, or
execution identity. Dispatch output contains only the declared static registry and selected records
with the derived audit lists. There is no whole-input SHA, record total including
pending records, private case/seed/attempt identity, wall-clock time, fault
schedule, physical trajectory, plant object or replay metadata. Input fingerprints
and execution identities belong to the private engineering capture. Plain JSON
validation runs before copying and rejects custom Python objects, callbacks,
cycles, nonfinite numbers, unknown fields and inconsistent types/units. Returned
registries/records and submitted input objects cannot mutate ledger state.

The frozen [engineering fixture](../../configs/full-facility-evidence-v1.json)
shares the V6 facility/entity identities, with only three declared fixed sensor
sources. Its hand-authored values are independent static examples, not a plant
adapter, site telemetry, or a claim that all entities are observed. The authoring
tool reads only V6 identity/entity IDs, never its parameters or runtime state.
The same fixture drives temporal snapshots and both SVG diagrams.

```powershell
$env:PYTHONPATH='src'
python -X utf8 -m aegis_dc evidence --ledger configs/full-facility-evidence-v1.json --as-of 11 --output NEW_DIRECTORY
```

The CLI prints/saves the public snapshot and refuses existing output directories.
The engineering capture freezes inputs, tools, literal expectations and durable
files before hashing. Its terminal receipt remains pending delivery verification;
a separate fresh-checkout proof compares all declared originals and source/tool
bytes to committed Git blobs. Runtime caches are never durable evidence.
