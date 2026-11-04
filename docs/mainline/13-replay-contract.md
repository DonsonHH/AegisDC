# Versioned private facility replay

Ticket 13 adds deterministic engineering replay to the accepted full V6 facility.
It is a Zhengzhou-inspired synthetic research facility with eight operational
domains and four relation types. Site calibration, the actual coolant and
as-built topology remain pending. This is M2 engineering infrastructure, not a
mechanism comparison, professional repair layer, AI result or research trial.

## Public inputs and command authority

`run_recorded(scenario, directory, inputs=..., duration_s=..., step_s=...)` uses
the public scenario validator, `simulate_scenario` and `save_run` interfaces.
`record_files` additionally retains the exact submitted model/input file bytes.
The new closed input envelope is `aegisdc-facility-replay-inputs-v1`:

- `seed`: an integer, or null when using only the frozen event schedule. The
  current plant is deterministic and consumes no random numbers. A seed does
  not generate an unspecified fault schedule or imply a stochastic experiment.
- `exogenous_events`: frozen `time_s`, `parameter_id`, `value`, `source_note`
  records. Offered service demand, lake/room weather, capacity disturbances,
  sensor faults and external maintenance availability belong here.
- `action_commands`: the same timed fields plus a distinct nonempty `id`.
  The implemented engineering command authority is limited to
  `lake_valve_opening`, `internal_valve_opening`, `pump_pressure_rise`,
  `internal_pump_pressure_rise` and `backup_cooling_requested`.
- `work_requests`: the existing finite engineering worker/interface/target
  records. Their resource and access constraints execute in the plant; they do
  not diagnose, repair, generate inspection evidence or close a risk issue.

The strict replay envelope rejects control parameters in `exogenous_events`.
Commands cannot change offered demand, weather, latent faults, failure flags or
service capacity. Commands represent a predeclared engineer-controlled input
to existing plant parameters. Tickets 21-24 must implement professional
execution/repair authority separately. The legacy `simulate --inputs` v1
contract and defaults remain supported: its `boundary_events` keep their old
engineering boundary semantics and do not acquire an action attribution.

Both event origins pass through the actual plant. Commands are logged as
`engineering_control_command`; external inputs as `exogenous_boundary_input`.
All input assignments at a due instant occur before local protection and
reserve/control settling. The numerical time convention is the same versioned
binary64 convention introduced by ticket 12. Raw requested `time_s` is retained,
and `applied_at_s` records the processing epoch. Same-parameter conflicts at
coincident times, including across origins, are rejected. Independent parameter
records sort by `(time_s, parameter_id)`. The replay envelope orders simultaneous
work requests by `(time_s, id)`, rather than caller list order; existing work
completions precede new work requests.

## Re-execution and source identity

`replay_attempt(original, new_directory)` fresh-reads and verifies the original
attempt, then executes the frozen scenario, duration, maximum step, events,
commands and jobs again. It never reads a stored true-state trajectory as a
plant input. `action_commands=...` explicitly requests a paired exogenous
re-execution: only the command list is replaced. Original configuration,
offered demand, weather and fault/maintenance schedules remain frozen, so
different command-induced internal states and service losses remain visible.

`aegisdc-execution-source-v1` records SHA-256 for every AegisDC runtime `.py`
file and the shared strict-JSON/hash contract, their aggregate identity, Git
execution revision and dirty-source indicator, plus exact Python implementation
and version and the interpreter executable's SHA-256. Replay requires identical
runtime bytes and interpreter. A changed
Git commit with identical runtime bytes is explicitly recorded as
`DIFFERENT_COMMIT_SAME_RUNTIME_BYTES`; a changed runtime/interpreter produces a
new FAILED attempt. Historical outputs are never rewritten or silently
reclassified as a replay under new code.

Exact replay compares physical/service/control/personnel traces, interval
balances, events, work records and run inputs. Attempt UUIDs, wall-clock
lifecycle times, output paths and Git metadata are execution identities, not
physical outcomes. A changed command can change the integration/event grid;
paired comparisons must retain complete traces rather than aligning rows by
array index or replaying a precomputed ground-truth path.

## Lifecycle, privacy and durable delivery

Each new directory declares its durable roles before execution and hashing.
The terminal `attempt.json` hashes the declared artifacts, including submitted
bytes where available, canonical frozen inputs, configuration, request,
append-only lifecycle and the existing run's private trajectory/interval files.
`attempt.json` is the terminal envelope, not a self-hashed file. Runtime
`__pycache__`, `.pyc` and `.pyo` files are explicitly non-deliverable. An extra,
missing or changed durable file fails verification; a later delivery receipt
pins the terminal envelope itself to a committed Git blob.

Lifecycle is STARTED then COMPLETED or FAILED. Failed validation, invalid
submitted JSON, source refusal and physical-domain exceptions retain their
inputs and failure stage/type/message. Failed simulation returns no completed
trajectory; it does not invent a last-valid time or a completed service result.
A directory without its terminal envelope is
`UNFINALIZED_RUNNING_OR_INTERRUPTED`, not a success or an inferred failure.
Read-only verification cannot determine whether its writer is still alive.
Existing output directories are rejected before their contents are changed.

Reader-authority revision (new v2 captures): writers now emit
`aegisdc-facility-attempt-v2` and `aegisdc-attempt-declaration-v2`, with explicit
`aegisdc-attempt-lifecycle-v1` rows. The reader supports the known v1 historical
terminal/declaration pair and its exact legacy lifecycle row structure, and
the new v2 pair; unknown versions, mixed terminal/declaration versions, unknown
terminal states and malformed objects are refused before trajectory authority
is granted. Timestamps, field types, execution/research authority, artifact
roles and completed request structure are validated. Historical v1 bytes and
their original execution claims stay unchanged.

A supported declaration interrupted before lifecycle creation is also
`UNFINALIZED_RUNNING_OR_INTERRUPTED`. Empty or unrecognized origins have no
authority. Malformed lifecycle rows (including scalar JSON such as `42`) are
validation refusals. Replay records these and source refusals as a new FAILED
request at a named `replay_origin.*` stage. The new request stores exact readable
origin terminal/declaration/lifecycle bytes under its declared `origin/` roles,
plus the offending file when identified. These snapshots are private data,
never executable state. The original directory is read-only; unreadable or
missing bytes are not fabricated. Unknown or unfinished origins are never
promoted to completed or failed historical attempts. The new FAILED record
describes the refused request, not the unknown historical outcome.

There are no automatic retries. An engineering retry must use a new directory
and explicitly name the prior finalized FAILED attempt and a nonempty reason.
The new record pins the prior attempt ID/hash. Corrected configuration or code
is a new attempt, not an equivalent replay. No engineering retry consumes,
resets or increases a scientific budget.

Only `engineering_fixture` executes. A request for registered research, or a
research registration attached to an engineering request, is retained as a
FAILED request with zero research trials. Ticket 30 must first open a new
frozen protocol, registration and budget lifecycle. Old research protocols or
budgets are not imported by this module. Ticket 32 will independently qualify
the eventual research execution lifecycle.

Frozen future faults, engineering commands, control flow and actual state are
`PRIVATE_PLANT_EVALUATOR_ONLY`. Replay metadata is not dispatch knowledge. It
creates no observation, available-at timestamp, perfect risk issue or repair
recommendation. Tickets 14-15 must expose only evidence that has legally
arrived with declared provenance, while local automatic protection continues
to use its existing plant-local instrumentation.

## Commands

```powershell
$env:PYTHONPATH='src'
python -m aegis_dc record --model configs/full-facility-mainline-reserve-v6.json --inputs configs/full-facility-replay-example-v1.json --duration 2 --step .5 --output NEW_DIRECTORY
python -m aegis_dc replay --attempt ORIGINAL_DIRECTORY --output ANOTHER_NEW_DIRECTORY
python -m aegis_dc replay --attempt ORIGINAL_DIRECTORY --commands NEW_COMMAND_LIST.json --output NEW_PAIRED_DIRECTORY
```

`record`/`replay` print the terminal record, returning exit code 0 for a completed
engineering run, 1 for a recorded failure, and 2 for argument/output-ownership
errors. Existing commands and their default models remain unchanged.
