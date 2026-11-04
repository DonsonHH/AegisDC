# Ticket 10 Standards source review

Fixed baseline: 1ec2503d6c88d5f4a31088777886977d9920bc23.
Reviewed source pin: dca40ac97c0e1c1d9a8eb101dadaeaabf174edca.
Scope: reserve/power/plant/runtime/scenario, v6 configuration, authoring tool, 24 tests and design/implementation contract; later capture metadata is outside this source review.

## Hard standards: 0 new material findings

Applied AGENTS (including durable-delivery/cache and execution-revision rules), GLOSSARY/domain, ADRs 0001-0003, shared specification, pyproject and scoped attributes. UPS detection/control has explicitly paid AC or finite internal energy; generator control/cranking has finite starter energy and fuel/idle accounting; only a paid sampled main controller accepts new cooling commands. Fan power is allocated from the shared AC budget, with defined UPS coverage and common-distribution failure. Storage depletion/deadlines participate in physical-event splitting. The sensible backup boundary retains signed heat and actual flow/power limits; electrical dissipation, heat rejection, hot leakage and floor energy have explicit destinations.

The implemented model/profile is opt-in with a frozen topology digest. New SI delay/rate quantities do not relax old positive-time or physical/signed-offset domains. All new numerical inputs/topology are source-tagged synthetic assumptions. Eight domains, private evaluator/local-control records, legacy profiles/default CLI and pre-meeting patrol/paper are retained.

## Judgment-based heuristics: 0 material findings

Applied all twelve Fowler heuristics. Separate actor transitions and the paid heat/power boundaries have concrete independent behaviors. Legacy allocation remains a compatibility boundary; no actionable duplication, naming, coupling or speculative abstraction was found.

## Verification and limits

Independently executed the frozen pin's 24 reserve targets: 24 passed, zero failures/errors/skips. Candidate whitespace/attribute checks pass. An attempted subsequent compatibility run stopped at its source-freeze guard when the owner added a new test; it did not execute or modify the tree. The separate Spec-axis same-time selector/obsolete UPS-need finding is being addressed by the owner and is not closed by this Standards report. New source requires a delta review. No full regression, saved engineering capture or research trial was run here; portable artifact acceptance remains pending.

## Final-source supplement

Final pin: efb7bbdc1d9140d8686cc28ad6ab998d0bb22321. Delta dca-to-efb: 0 additional hard-standard/heuristic findings. plant.py's post-sample loop settles autonomous reserves within four passes, accepts sampled commands once, recomputes the final point before access, and fails explicitly on nonconvergence. Both UPS-need directions update at the same instant; return-primary starts at3s and connects at3.2s for1/.25s steps, without resampling PLC. Before/after guards verified101 tracked source/config/test files unchanged. Executed26 reserve+22 environment+16 control tests:64 passed, zero failure/error/skip. The old24 observation remains attributed to dca. Metadata/artifact acceptance remains pending; no merge or full regression.
