# AegisDC research execution

## Compute and storage (user requirement, 2026-11-09)

Use the existing remote servers for dependency installation, training, inference, evaluation and large computation. Keep this desktop to editing, SSH, integrity checks, necessary file transfers and viewing results. If a remote service is unavailable, report the blocker and retain inputs; wait for an explicit change of instruction before using local computation.

For server access, environment setup, jobs, result storage or cleanup, read `docs/agents/compute-storage.md`. Cluster work must follow the installed `use-renly-slurm` skill, including live identity/topology/queue discovery and Slurm allocation for computation. Keep detailed outputs and checkpoints on the private server; retrieve necessary figures and summaries. Preserve current directories, uncommitted/unpushed work, unique data and required reproduction evidence. Before deleting a local-only large artifact, verify the remote copy's identity and readability. Remove historical worktrees through normal Git operations; retain uncertain content and record why. These storage rules do not change the research objective or acceptance gates.

For research continuation, read `docs/MAINLINE.md`, then `docs/mainline/progress.json` and the current ticket. Keep the complete-facility objective and its acceptance gates through context changes. A plan, component test, demo, or passing CI is a milestone, not completion of the research goal.

Work the ready frontier in dependency order; the primary current ticket is the earliest ready item. Independent ready tickets may run in parallel within the same mainline, each with one owner/worktree. Record accepted artifacts and their checks before resolving it. Report a negative result as a research result; revise hypotheses through an explicit protocol revision instead of changing the target or reusing sealed outcomes.

Before claiming, inspect the active-work hints in progress and confirm live agent/worktree state. A ticket's claimed status may still be only on its unmerged worktree; do not duplicate a live assigned implementation or restart it solely because an observation timed out.

Use one Zhengzhou-inspired **synthetic research facility** with eight operational domains. Keep source facts, design claims, modeling assumptions, and unresolved site data explicit. Maintain physical, functional, control/information and access relations with shared entity identities. Personnel are domain actors; AI decision modules are a later, independently evaluated choice.

Keep actual state private to the plant/evaluator. Dispatch receives only records available at decision time and declared static knowledge. Correlated/copied records need shared provenance. Existing local automatic protection remains part of the plant.

New work belongs in the AegisDC implementation and new mainline records. Preserve pre-meeting source/evidence, protocols, failures and reports. New research runs use a new frozen protocol, attempt ledger and unique output directory. Engineering fixtures are labeled separately from research trials; no fixture proves a scientific gain.

## Agent skills

### Issue tracker

Version-controlled local Markdown tickets and dependencies: `docs/agents/issue-tracker.md`. Run the dependency frontier, not an arbitrary future ticket.

### Domain docs

Single context: read `GLOSSARY.md` for terms and the relevant `docs/adr/` decision. Consumer rules: `docs/agents/domain.md`.

### Triage labels

Local role vocabulary: `docs/agents/triage-labels.md`.

### Interfaces and verification

The shared implementation/testing boundaries are the scenario loader, facility run interface, evidence-only decision view, and CLI. Their contracts and limits are in `.scratch/full-facility-mainline/spec.md`. Use red/green behavior slices at those interfaces, with conservation/analytic examples and independently specified outcomes.

Define the durable delivery set before hashing: declared inputs/outputs, immutable records and pinned authoring/verification tools. Automatic `__pycache__`, `.pyc` and `.pyo` files are runtime caches, not delivered evidence. Verify declared artifacts against their manifests and committed delivery blobs in a fresh checkout; check runtime source against its recorded execution revision. If an old manifest mixed caches with durable files, retain the original and add an exact classification correction rather than skipping arbitrary hash failures or rewriting originals.

Integrate one reviewed ticket at a time. Re-read the integration tip before coding in a worktree; preserve concurrent work, run appropriate checks, and publish milestone evidence. Read `docs/mainline/progress.json` again before deciding what is complete.
