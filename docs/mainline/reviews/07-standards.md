# Standards review: ticket 07

Fixed baseline: `5da917895bc12d23eba37243215c8e42cc76fc9b`.
Committed source candidate: `5ca3c3a03d05802458cef1bdd10e66928d75bc1b`.
Diff: `git diff 5da91789...5ca3c3a0`; implementation `ab6094bf` plus the accepted-service integration merge.

## Standards

**Documented-standard violations: 0. Actionable heuristic findings: 0.**

Reviewed changed environment/plant/runtime code, the explicit v4 configuration, 22 focused tests and authored documentation against AGENTS.md, GLOSSARY.md, domain rules, ADRs 0001-0003, the mainline spec, pyproject.toml and scoped attributes. Fowler smells were judgment calls subordinate to repository decisions; tooling-owned formatting was excluded.

The profile retains all eight domains and shared asset identities. New leak and gate connections, hydraulic inventory boundary and room-work threshold are explicitly synthetic, with SI/range/provenance records. Legacy inputs/defaults are preserved. Unsupported control-profile declarations fail instead of silently selecting ideal behavior.

Hot leakage transfers the same mass and sensible energy into the separately stored floor pool, without adding external heat or removing refrigerant. Nuisance inflow and drainage remain actual external boundaries; drain energy uses the stable direct integral and a known exact-zero branch. The existing repaired roundoff cases are covered, not reported again. Condensation output is an explicitly private boundary criterion: no condensate, latent heat or outward perfect alarm is invented.

Access comes from the independent personnel graph, permission and declared physical conditions. Work is stopped with spent occupation/travel and actual carried-tool location retained. At room-threshold equality, the code uses the actual post-protection heat direction. The research work-temperature threshold is not represented as an occupational limit.

The public-seam tests use independent hand/Decimal/reference cases and actual full-facility trajectories. Fresh focused execution passed 22/22 with zero skips. Review made no repository changes and ran no full suite or research experiment. The author's untracked acceptance artifacts were still being assembled; their later source/hash/receipt acceptance remains the root's separate gate. No Standards finding blocks source integration, and no M1, field-validation or scientific-gain conclusion is implied.

## Final-evidence supplement

Candidate `d68425915d5a5d9308add320a22c96764db11812` retains identical reviewed source. The later ticket, model-documentation and evidence changes add nine successes, one retained expected domain failure and a separate CLI case; they retain the original execution/dirty-probe attribution. Fresh reads matched all 146 prior engineering hashes and six frozen input hashes/Git blobs. Whitespace exceptions cover generated originals only. M1, root acceptance and effect research remain unclaimed. No new hard-standard or heuristic findings; totals remain **0/0**. Tests were not repeated.
