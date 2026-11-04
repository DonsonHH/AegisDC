# Ticket 14 engineering evidence

This package exercises the timed evidence ledger for the same complete V6
Zhengzhou-inspired synthetic facility. It is not site telemetry or a registered
mechanism comparison. It does not run a physical scenario, a worker, a model,
training, risk inference, or RSI. The research mainline remains active.

- [Readable interface contract](../../../../../docs/mainline/14-evidence-contract.md)
- [Frozen literal runbook](../../../../../docs/mainline/14-evidence-runbook.json)
- [Observation/arrival/expiry timeline](capture-01/figures/arrival-timeline.svg)
- [Declared-source architecture](capture-01/figures/source-architecture.svg)
- [Original terminal capture receipt](capture-01/receipt.json)

The diagrams share the exact fixture driving the public snapshots. Their author
is `scripts/plot_evidence_ledger.py`, a Python standard-library SVG generator.
The capture pins fixture, authoring/verification sources, interpreter and declared
durable files. `figure-checks.json` records units, source digest, dimensions and
exact SVG digests. Inputs, terminal receipts and CLI failures are private
engineering records; they are not dispatch input.

`development/` preserves original red/green logs. Windows CRLF bytes are retained
using explicit leaf format classifications. Automatic Python caches are not
delivery artifacts. Each capture owns a new directory; failures are retained,
and an existing CLI output is never overwritten. The original terminal receipt
stays `PENDING_COMMIT_AND_FRESH_CHECKOUT`; delivery proof is a separate record.

Later tickets must independently qualify full decision-view isolation,
observation generation, risk inference and actual professional execution.
