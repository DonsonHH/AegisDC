# AegisDC research execution

For research continuation, read `docs/MAINLINE.md`, then `docs/mainline/progress.json` and the current ticket. Keep the complete-facility objective and its acceptance gates through context changes. A plan, component test, demo, or passing CI is a milestone, not completion of the research goal.

Work the first ready ticket in the dependency graph. Record accepted artifacts and their checks before resolving it. Report a negative result as a research result; revise hypotheses through an explicit protocol revision instead of changing the target or reusing sealed outcomes.

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

Integrate one reviewed ticket at a time. Re-read the integration tip before coding in a worktree; preserve concurrent work, run appropriate checks, and publish milestone evidence. Read `docs/mainline/progress.json` again before deciding what is complete.
