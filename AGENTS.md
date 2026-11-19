# AegisDC research execution

## Full-facility method and incident validation (2026-11-20)

Read [MAINLINE](docs/MAINLINE.md), the [full-facility method and implementation handoff](docs/mainline/full-facility-method-handoff.md), and [progress](docs/mainline/progress.json). The user clarified the project direction: the paper studies risk-driven on-demand inspection, constrained action, ordinary improvement and RSI in the complete coupled facility with sparse evidence, as set out in the [3 November record](docs/meetings/2026-11-03-research-reset.md) and [ADR-0003](docs/adr/0003-complete-facility-mainline.md). Google incidents supply a bounded effectiveness-validation chapter. Retain the [accepted London v1.3](docs/mainline/review-gated/R6/london-pre-manuscript-v1.3/acceptance-20261119.md) and its [original reading PDF](docs/mainline/review-gated/R6/london-pre-manuscript-v1.3/manuscript.pdf). The handoff recommends one V6 intake-flow investigation / authorized filter-maintenance slice. Subsequent implementation and execution require an explicitly scoped work package. The former advisor-direction wait is superseded.

Preserve the three frozen slice 57 files, formal protocols, original results and failures byte for byte. The [pre-reset snapshots](docs/mainline/history/20261112-before-reset/README.md) are historical evidence, not the active queue. New engineering work, once authorized, uses the [lightweight template](docs/agents/lightweight-engineering.md). Incident-source reading and proposed counterfactual/RSI designs do not authorize simulations or model experiments.

## Compute and storage (user requirement, 2026-11-09)

Use the existing remote servers for dependency installation, training, inference, evaluation and large computation. Keep this desktop to editing, SSH, integrity checks, necessary file transfers and viewing results. If a remote service is unavailable, report the blocker and retain inputs; wait for an explicit change of instruction before using local computation.

For server access, environment setup, jobs, result storage or cleanup, read `docs/agents/compute-storage.md`. Cluster work must follow the installed `use-renly-slurm` skill, including live identity/topology/queue discovery and Slurm allocation for computation. Keep detailed outputs and checkpoints on the private server; retrieve necessary figures and summaries. Preserve current directories, uncommitted/unpushed work, unique data and required reproduction evidence. Before deleting a local-only large artifact, verify the remote copy's identity and readability. Remove historical worktrees through normal Git operations; retain uncertain content and record why. These storage rules do not change the research objective or acceptance gates.

For research continuation, follow the approved gate and its acceptance criteria through context changes. A plan, component test, demo, or passing CI is a milestone, not completion of the research goal. The new plan's scientific choices remain proposals until user review.

Work only the explicitly authorized gate; record its artifacts and checks before presenting it for review. Acceptance of one gate does not automatically authorize the next. Report negative results honestly and revise hypotheses through an explicit protocol revision instead of changing the target or reusing sealed outcomes.

Before claiming, inspect the active-work hints in progress and confirm live agent/worktree state. A ticket's claimed status may still be only on its unmerged worktree; do not duplicate a live assigned implementation or restart it solely because an observation timed out.

Use the existing Zhengzhou-inspired eight-domain synthetic facility as the main research object. Reuse capabilities within their tested boundaries. Keep the four graph semantics, private state boundary, fixed automatic protection, original negative results and outstanding qualifications intact. The [R0-R6 incident plan](docs/mainline/review-gated/plan.md) governs its own validation chapter.

Keep actual state private to the plant/evaluator. Dispatch receives only records available at decision time and declared static knowledge. Correlated/copied records need shared provenance. Existing local automatic protection remains part of the plant.

New work belongs in the AegisDC implementation and new mainline records. Preserve pre-meeting source/evidence, protocols, failures and reports. New research runs use a new frozen protocol, attempt ledger and unique output directory. Engineering fixtures are labeled separately from research trials; no fixture proves a scientific gain.

## Agent skills

### Issue tracker

Current scope is recorded in the full-facility method handoff and progress ledger. R0–R6 records retain their incident-chapter scope. The legacy issue tracker in `docs/agents/issue-tracker.md` cannot authorize queued implementations.

### Domain docs

Single context: read `GLOSSARY.md` for terms and the relevant `docs/adr/` decision. Consumer rules: `docs/agents/domain.md`.

### Triage labels

Local role vocabulary: `docs/agents/triage-labels.md`.

### Interfaces and verification

The shared implementation/testing boundaries are the scenario loader, facility run interface, evidence-only decision view, and CLI. Their contracts and limits are in `.scratch/full-facility-mainline/spec.md`. Use red/green behavior slices at those interfaces, with conservation/analytic examples and independently specified outcomes.

Define the durable delivery set before hashing: declared inputs/outputs, immutable records and pinned authoring/verification tools. Automatic `__pycache__`, `.pyc` and `.pyo` files are runtime caches, not delivered evidence. Verify declared artifacts against their manifests and committed delivery blobs in a fresh checkout; check runtime source against its recorded execution revision. If an old manifest mixed caches with durable files, retain the original and add an exact classification correction rather than skipping arbitrary hash failures or rewriting originals.

Integrate one reviewed ticket at a time. Re-read the integration tip before coding in a worktree; preserve concurrent work, run appropriate checks, and publish milestone evidence. Read `docs/mainline/progress.json` again before deciding what is complete.
