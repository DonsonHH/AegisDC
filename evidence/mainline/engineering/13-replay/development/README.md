# Ticket 13 implementation slices

Development observations below are engineering/TDD records, not research
attempts or a scientific trial ledger. The authoritative terminal engineering
capture will be a separately named, frozen output directory. No historical
M1, pre-meeting protocol, outcome or data file was changed by these slices.

Base `77660da5` was checked against live agent/worktree inventory before the
unique ticket-13 worktree/branch was created. Public seams were already
authorized by `.scratch/full-facility-mainline/spec.md`.

Observed red/green slices used the primary Windows Python with `-Xutf8`,
`PYTHONPATH=src` (or `src;tests` for one named unittest), and the actual CLI:

- First frozen-V6 replay test: `ModuleNotFoundError: No module named
  'aegis_dc.replay'`; the new recorded-run/read/replay module then passed the
  exact physical/account/event comparison.
- Causal command slice: FAILED at `validate_inputs` with `Engineering action
  commands are not yet supported`; the minimal origin adapter then executed
  an internal-valve command through the existing plant. During test drafting,
  the initially asserted .5 service-unit s was corrected to the independently
  specified V6 result of 1: the PLC period is 1 s, not the .5 s maximum
  integration step. The test's nonexistent `internal_volume_flow_m3_s` path was
  corrected to the existing `internal_mass_flow_kg_s` public output.
- Explicit retry slice: the original re-execution simply repeated the physical
  domain exception, failing the required `explicit retry` assertion. Replay now
  refuses failed origins, and an explicit new retry pins the original failure.
- Extra durable output slice: the expected ValueError was not raised for an
  unlisted durable file; exact-set verification then passed.
- Research classification slice: `TypeError` for absent `attempt_kind`; the
  classification gate now preserves and refuses research requests before
  ticket 30, with zero research trials.
- Actual CLI slice: `record` was an invalid argparse choice. The new CLI
  commands then executed and replayed V6. An English `exists` assertion first
  encountered Windows' localized FileExistsError; ownership refusal now has a
  stable message and still leaves every original byte unchanged.
- Canonical work slice: the saved inputs remained `z-last,a-first`; canonical
  frozen inputs now retain `a-first,z-last` and the same real resource outcome
  regardless of caller list order.
- Unfinalized read slice: missing `attempt.json` raised FileNotFoundError;
  STARTED-only directories now report `UNFINALIZED_RUNNING_OR_INTERRUPTED`.
- Initial declaration slice: missing `declaration.json` raised
  FileNotFoundError; durable roles are now declared before execution/hashing.
- Input consistency review slice: changing the frozen seed and its file hash
  did not fail the attempt's input identity check; a separate canonical-input
  identity check and executed-input consistency check now reject that drift.

Shared ticket-12 time source `cf1550cc` was merged only after root's explicit
coordination authorization, as `018456de`, retaining both its applied-time
records and the command/exogenous origin fields. The numerical six-test target
passed after that merge. A mistyped development discovery pattern
`test_mainline_numerical.py` ran zero tests; it was not a passing check, and the
correct `test_mainline_numerics.py` target executed all six successfully.

Latest public replay target executed 13 tests, all passing. Source review also
added execution-identity checks before/after the plant and verified terminal
lifecycle consistency. Full-suite and fresh-checkout delivery results are
recorded only by the later formal capture/verification receipts.
