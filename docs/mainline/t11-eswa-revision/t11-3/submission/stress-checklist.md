# STRESS reporting checklist

*Cost-aware value-of-information scheduling of inspections and interventions in maintenance-degraded computing facilities*

Discrete work and evidence events operate on a physical simulation clock. We use STRESS-DES as the closest reporting framework. Locations refer to this English revision. “Partial” identifies the limit of the information reported. [Monks et al., Journal of Simulation](https://doi.org/10.1080/17477778.2018.1442155)

| Item | Reporting topic | Location | Coverage |
|---|---|---|---|
| 1.1 | Purpose | §1, opening and decision state | Select the next feasible field job under sparse evidence and a time-limited permit. |
| 1.2 | Outputs | §1 endpoints, §§3–7, Suppl. B | Full-window deficit, unmet service quantity, person/tool time, charged fees, events and verified closure. |
| 1.3 | Questions | §§1, 3, 5–8 | Same-policy ablation, whole-policy comparators, incident endpoints, extra online planners, sensitivity, frequency and transfer. Each has an explicit evidential role. |
| 2.1 | Overview of logic | §§1–2 | Graph relationships, common service, public view, decision, admission, execution and independent scoring. |
| 2.2 | Base-model logic | §1 state/endpoints, §2 admission | Concurrent bottlenecks enter a single service measurement. Local protection operates in each arm. |
| 2.3 | Scenario logic | §§3–5, 7, Suppl. A | Common conditions and independent dynamic instances. Scheduled maintenance and both incident mechanisms identified. |
| 2.4 | Algorithms | §§1–2, §6, Suppl. A | Belief update, report-conditioned continuation, objective, complexity, admission and comparator search budget. |
| 2.5 | Components and routing | §§1–2, Suppl. A | Assets, orders, routes, workers, tools, work admission, queues, priority obligations and terminal receipts. Partial for the inventory of individual routes and queues. |
| 3.1 | Data sources | §§1, 5, 7, Suppl. A | Facility scale references, operator incident reports, synthetic quota design and published policy scores have separate roles. |
| 3.2 | Input parameters | §§1–2, 4, 6, Suppl. A/B | Clocks, priors, likelihood, UNKNOWN branch, prices, timing, nominal and perturbed values, panel and manifest identities. |
| 3.3 | Data preparation | §§2–3, 5, Suppl. A | Shared-provenance records are deduplicated. Confirmatory incident overlaps retain their original denominator. No site telemetry fitting. |
| 3.4 | Assumptions | §§1–2, 4, 7 | Limited backup, permit, hypothetical priors, feasibility, exposure frequencies and field calibration limits. |
| 4.1 | Initial conditions | §§1, 3, Suppl. A | Each arm owns independent initial state for the same external condition. Partial for a site-calibrated initial-state distribution. |
| 4.2 | Run length | §1 endpoints, §3 | Full finite window, native clock and public decision step. No steady-state warm-up. |
| 4.3 | Estimation | §§3–7, Tables A–F, Suppl. B | Pairing, resampling, gate order, block-variance rule, multiplicity handling, post hoc margins and conditional mixture means. |
| 5.1 | Implementation | §2, Suppl. A/B | Named native core, public worker, fixed release identities, original qualification failure and correction. |
| 5.2 | Sampling | §§2–3, 5–7, Suppl. A | Within-family quotas, scenario probabilities, root sampling and resampling units. Partial for independently replaying private condition generation. |
| 5.3 | Execution | §§3, 6, Suppl. A/B | Admitted first requests, independent instances, scope-specific counts, outcomes, retries, return reason and timing sources. |
| 5.4 | Computing platform | §6 Table E and Figure A, Suppl. A/B | Slurm accounting and clock scope reported. Partial for machine-to-machine latency comparison and the unavailable historical worker CPU clock. |
| 6.1 | Code access | Availability, Suppl. A/B/C | Versioned public implementation, release tables, signed provenance and custody limits. Private per-position trajectories have separate access arrangements. |
