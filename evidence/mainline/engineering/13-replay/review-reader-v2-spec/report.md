# Spec review: ticket 13 reader-v2

Baseline `aaa4d8cba3738e47e700c2134000a72bd2390cc0`; candidate `9a68ea7fb2eeee580d3fa0b794e8cbe0fb734a97`. Actual execution/delivery remain `cf9b3390` / `3e508cbe`.

**Original finding: 1 closed. New findings: 1 open, P2.**

The five original version/state/setup/lifecycle cases now refuse correctly or retain UNKNOWN. Supported v1 and v2 originals remain readable. New refused requests preserve origin bytes and stages; existing output ownership and zero research authority hold.

**P2 — completed request parameters are not bound to the actual frozen execution.** The contract says replay “executes the frozen scenario, duration, maximum step, events” (`13-replay-contract.md:51–53`); specification story 13 requires deterministic replay. At `replay.py:321`, a completed request receives shape/type validation, but `:342–343` compares run duration/step only with the terminal record. In separate copies of the new v2 causal baseline, changing only `request.duration_s` from 2 to 3, or `maximum_step_s` from .5 to .25, and coherently updating its declared artifact SHA still returns COMPLETED. Terminal and actual run retain 2/.5. At `:370–376`, replay directly adopts the divergent request values. The reader thus grants internally inconsistent execution authority. These are observed reader counterexamples; no plant was executed.

Resolve null request values against the frozen scenario, verify effective duration/step against the terminal and run, and replay validated execution parameters. Inconsistent origins must produce a new staged FAILED request before simulation, preserving their bad request bytes.

Seven selected reader/refusal tests passed with zero skips. Saved readback verifies eighteen requests (six completed/twelve failed), both exact trace/balance/event/work/input pairs and offered demand 2 each versus delivered 2/1. A 647-file before/after guard passes; 131 source/tool/original files additionally match candidate Git blobs. Zero physics/full-suite/research/model runs occurred. The recorded author full 345/343 and two optional skips were not rerun.

Standards separately reports a balance-time typing defect; it is not duplicated in this Spec count. Ticket 12 numerical qualification and the complete goal remain open.

Evidence: `aegisdc-review-13-reader-v2-spec-attachments/independent-check-01.json`, `targets-and-readback-01.json`, and `review-receipt.json`.
