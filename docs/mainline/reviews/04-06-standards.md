# Standards review: tickets 04, 05 and 06

Fixed baseline: `8fb76ad9ff09761621ebab3229e5c70bb886ecd0`.
Reviewed candidates: `503ac3232fa36d6f1da79d7596fd831c86b4956a` (04+05) and `2325a69261895de1b29b20f2ae585491d109dc64` (06), using three-dot diffs. Ticket 04 was reviewed once.

## Standards

**0 documented-standard violations; 0 actionable smell findings.**

Sources checked: `AGENTS.md`, `GLOSSARY.md`, `docs/agents/domain.md`, accepted ADRs 0001-0003, `.scratch/full-facility-mainline/spec.md`, `pyproject.toml`, and `.gitattributes`. Fowler smells were treated as judgment calls, with repository rules taking priority.

The changes retain the eight-domain synthetic facility, distinguish assumptions from site facts, preserve the legacy inputs/evidence and separate engineering checks from effect research. Runtime topology versions remain explicit. The new valve component has one real physical/verification boundary; its parameters and model branches do not warrant an abstraction-only refactor. Plant snapshots remain private evaluator outputs; no dispatcher, hidden-truth feed or unregistered effect study is introduced.

Hydraulic work is included once within the pump electrical heat allocation. Active-operation validation does not constrain a stopped pump's unused efficiency. Endpoint flash acceptance retains legal quality, finite floating-point tolerance and strict refusal outside the declared domain. The new tests use public seams and independently specified budgets/EOS references rather than copies of the production algorithm.

Fresh focused execution: water 18/18, phase 11/11, power 9/9; all passed, zero skips. The reviewed worktree stayed clean. Full enabled-Torch integration acceptance and combined-source physical behavior remain the root's separate gate; this review does not claim M1, field calibration or scientific gain.

Scope: changed source, focused tests, model configuration and authored ticket/model documentation; generated trajectories were inspected through their receipts and selected contract checks, not exhaustively reanalysed line by line.
