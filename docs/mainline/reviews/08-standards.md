# Standards review: ticket 08

Fixed baseline: `8141615448e33ed930338162d35d9d1ef1c6df73`.
Candidate: `1fb8981b970e1e120e64598c5ce95c566037dfed`.
Diff: `git diff 81416154...1fb8981b`.
Commits reviewed: `2c328cab`, `60f21f25`, `d06996c7`, `04ae737b`, `1fb8981b`.

## Standards

**Documented-standard violations: 0. Actionable heuristic findings: 0.**

Reviewed against AGENTS.md, GLOSSARY.md, docs/agents/domain.md, ADRs 0001-0003, the mainline specification, pyproject.toml and .gitattributes. Fowler smells were judgment calls with repository rules taking priority; tooling-owned formatting was not reported.

The production diff only extends the existing exogenous-event allowlist with the three already declared component service capacities. It retains finite/range/source/time validation, event splitting and the private plant/evaluator boundary. No nominal power coefficient, scenario snapshot, old result, dispatcher input or protocol is rewritten.

The tests and authored documentation consistently preserve external demand during execution throttling, account for overlapping component loss once, and distinguish interval-normalized deficit seconds from normalized work. Units and the linear power assumptions are explicit; no physical FLOP/s calibration, hardware diagnosis from throttling or strategy benefit is claimed. Public run/CLI seams and independently worked literal intervals are appropriate. The evidence program writes fresh destinations, preserves expected rejections and verifies saved artifacts without production-private calls.

Fresh read-only verification: 8/8 focused tests passed, zero skips; this includes the actual CLI/save test. All 59 artifacts in the eleven-run engineering receipt were freshly rehashed and matched. Worktree status stayed clean. No full regression or new research experiment was run for this review.

Enabled-Torch combined acceptance and root milestone decisions remain separate. No Standards finding blocks ticket 08 integration; this is not M1 completion or a scientific-gain conclusion.
