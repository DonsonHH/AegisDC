# AegisDC research execution

## User-directed research reset (2026-11-12)

The user replaced the old milestone queue with a new review-gated research design. Read [MAINLINE](docs/MAINLINE.md), [the R0–R6 plan](docs/mainline/review-gated/plan.md) and [progress.json](docs/mainline/progress.json) before research work. The user-authorized finite [R2 package](docs/mainline/review-gated/R2/execution/README.md) is delivered: 97 frozen execution units and 9 pair groups passed remotely at d57b19b8. Read its result and progress ledger; wait for user acceptance, do not automatically rerun or continue. Frozen inputs/expectations, original failures and source pins are retained. Q11 deferred workflows remain uncovered, never waived. R3/R4/R5, method/RSI comparisons, Netherlands and RESP remain unauthorized. Do not resume old 39c–42 work from an old ready status. PR #3 was merged into the current 39c branch as maintenance only.

Preserve the three frozen slice 57 files, formal protocols, original results and failures byte for byte. The [pre-reset snapshots](docs/mainline/history/20261112-before-reset/README.md) are historical evidence, not the active queue. New engineering work, once authorized, uses the [lightweight template](docs/agents/lightweight-engineering.md). Incident-source reading and proposed counterfactual/RSI designs do not authorize simulations or model experiments.

## Compute and storage (user requirement, 2026-11-09)

Use the existing remote servers for dependency installation, training, inference, evaluation and large computation. Keep this desktop to editing, SSH, integrity checks, necessary file transfers and viewing results. If a remote service is unavailable, report the blocker and retain inputs; wait for an explicit change of instruction before using local computation.

For server access, environment setup, jobs, result storage or cleanup, read `docs/agents/compute-storage.md`. Cluster work must follow the installed `use-renly-slurm` skill, including live identity/topology/queue discovery and Slurm allocation for computation. Keep detailed outputs and checkpoints on the private server; retrieve necessary figures and summaries. Preserve current directories, uncommitted/unpushed work, unique data and required reproduction evidence. Before deleting a local-only large artifact, verify the remote copy's identity and readability. Remove historical worktrees through normal Git operations; retain uncertain content and record why. These storage rules do not change the research objective or acceptance gates.

For research continuation, follow the approved gate and its acceptance criteria through context changes. A plan, component test, demo, or passing CI is a milestone, not completion of the research goal. The new plan's scientific choices remain proposals until user review.

Work only the explicitly authorized gate; record its artifacts and checks before presenting it for review. Acceptance of one gate does not automatically authorize the next. Report negative results honestly and revise hypotheses through an explicit protocol revision instead of changing the target or reusing sealed outcomes.

Before claiming, inspect the active-work hints in progress and confirm live agent/worktree state. A ticket's claimed status may still be only on its unmerged worktree; do not duplicate a live assigned implementation or restart it solely because an observation timed out.

The existing Zhengzhou-inspired eight-domain synthetic facility is a reusable research asset. Its reuse and any incident-model scope must satisfy the new approved design; old acceptance does not certify a Google site reconstruction. Keep source facts, design claims, assumptions and unknowns explicit. Preserve physical, functional, control/information and access semantics. Distinguish method effectiveness, conditional counterfactual claims, ordinary feedback improvement and independently tested RSI increment.

Keep actual state private to the plant/evaluator. Dispatch receives only records available at decision time and declared static knowledge. Correlated/copied records need shared provenance. Existing local automatic protection remains part of the plant.

New work belongs in the AegisDC implementation and new mainline records. Preserve pre-meeting source/evidence, protocols, failures and reports. New research runs use a new frozen protocol, attempt ledger and unique output directory. Engineering fixtures are labeled separately from research trials; no fixture proves a scientific gain.

## Agent skills

### Issue tracker

Current authority is the R0–R6 gate ledger above. `docs/agents/issue-tracker.md` describes retained legacy ticket mechanics; old ready tickets cannot bypass the user-review gate.

### Domain docs

Single context: read `GLOSSARY.md` for terms and the relevant `docs/adr/` decision. Consumer rules: `docs/agents/domain.md`.

### Triage labels

Local role vocabulary: `docs/agents/triage-labels.md`.

### Interfaces and verification

The shared implementation/testing boundaries are the scenario loader, facility run interface, evidence-only decision view, and CLI. Their contracts and limits are in `.scratch/full-facility-mainline/spec.md`. Use red/green behavior slices at those interfaces, with conservation/analytic examples and independently specified outcomes.

Define the durable delivery set before hashing: declared inputs/outputs, immutable records and pinned authoring/verification tools. Automatic `__pycache__`, `.pyc` and `.pyo` files are runtime caches, not delivered evidence. Verify declared artifacts against their manifests and committed delivery blobs in a fresh checkout; check runtime source against its recorded execution revision. If an old manifest mixed caches with durable files, retain the original and add an exact classification correction rather than skipping arbitrary hash failures or rewriting originals.

Integrate one reviewed ticket at a time. Re-read the integration tip before coding in a worktree; preserve concurrent work, run appropriate checks, and publish milestone evidence. Read `docs/mainline/progress.json` again before deciding what is complete.
