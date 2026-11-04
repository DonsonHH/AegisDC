# Ticket 04 engineering evidence

Source implementation: `a50b1e5e6f87397a57b226f805992fd5470a6f7f`.
Scope and hand calculations: [`power-verification.md`](../../../../docs/mainline/power-verification.md).
These outputs are synthetic engineering fixtures, with zero registered research
trials, training runs or agent/model calls. Field calibration remains pending.

`run-01-committed-public-validation/receipt.json` records 9 public full-facility
cases and 209 passing checks. The CLI case preserves input, stdout, stderr and
the separately saved run. Each case binds source/config/property identities and
retains private evaluator states and balances. `artifact-integrity.json` is a
fresh-read verification of all 27 generated data files against manifest hashes
and record counts.

`attempt-01` and `attempt-03` are expected red tests and are retained. The first
shows a negative pump request created a nonphysical operating point. The second
shows invalid electrical inputs were not consistently rejected. The intervening
green runs show each correction, and `attempt-05` through `attempt-11` verify
existing correct behavior with independent literals. `attempt-12` runs the prior
22 facility/property/CLI tests. `attempt-13` runs the full suite: 188 collected,
186 executed, 2 existing optional Torch skips, zero failures/errors. The exact
logs and their hashes are listed in `run-01-committed-public-validation/test-attempts.json`.

Reproduce using `reproduce.py --output <new-directory>` with this checkout's `src`
on `PYTHONPATH`. The script refuses an existing output directory and rejects an
import from a different checkout. It records failures without replacing any prior
run. Full integration acceptance is a separate root responsibility; this evidence
does not complete M1 or the fixed research objective.
