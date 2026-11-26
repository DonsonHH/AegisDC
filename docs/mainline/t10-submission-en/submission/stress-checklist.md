# STRESS reporting checklist

**Article:** When is a paid inspection worth waiting for during maintenance-induced degradation?

The facility combines a fixed physical clock with discrete work, observation and decision events. The DES checklist is the closest reporting framework. The item identifiers follow Tables 3 and 4 of Monks et al., the manuscript's existing reference [9]. The section numbers below apply to both the numbered source and the review manuscript. “Partial” identifies information the article does not supply. [Reporting framework](https://doi.org/10.1080/17477778.2018.1442155)

| Item | Reporting topic | Manuscript location | What a reader can verify |
|---|---|---|---|
| 1.1 | Model purpose | §§1–2 | The value of access to a paid inspection when information and operating authority can arrive at different times. |
| 1.2 | Outputs | §3.1, Tables 2–5 | Full-window normalized deficit L, unserved quantity U, staff, tools, charges and closure. The event endpoint is defined in §6. |
| 1.3 | Experimental questions | §§1, 4–8 | Same-method ablation, full-policy comparisons, synthetic incident severity and frequency, ordinary transfer and rewrite attribution. |
| 2.1 | Overview of model logic | §3, Figure 1 | The figure separates public decisions, private facility execution and end-of-window evaluation. |
| 2.2 | Base-model logic | §§3–3.2, Algorithm 1 | Coupled service limits, existing protection, evidence arrival and expiry, executor admission and separate scoring. |
| 2.3 | Scenario logic | §§4–6, Tables 1 and 3 | Common exogenous conditions, separate arm state, maintenance exposure and bounded incident mechanisms. |
| 2.4 | Algorithms | §3.1, Algorithm 1, §§7–8 | Belief updating, feasible continuations, action selection, tie-breaking, promotion and lineage attribution. |
| 2.5 | Components and routing | §§3–3.2, Figure 1, Table 1 | **Entities:** facility assets, work orders, observations and receipts. **Activities:** dispatch, travel, sampling, intervention and verification. **Resources:** staff, tools, permits, access, shifts and capacity. **Queues:** the policy chooses admissible work at public decision times and applies declared priorities. **Entry and exit:** evidence enters on delivery and work passes through admission and completion or refusal. Partial for an exhaustive queue-by-queue implementation inventory. |
| 3.1 | Data sources | §§2–3, 6 and 9 | Frontier measurements constrain scale, public incident reports constrain mechanisms and frozen design records specify synthetic inputs. |
| 3.2 | Input parameters | §3.2, Table 1 | Priors, observation quality, physical and decision clocks, prices and maintenance exposure are located in the frozen source. |
| 3.3 | Data preparation | §§3.1, 4 and 6 | Shared-provenance evidence is deduplicated. Overlapping historical inputs retain their original analysis denominator. Partial for source-specific telemetry preprocessing, which this study did not use to fit a field benefit. |
| 3.4 | Assumptions | §§3.2, 5 and 9 | Design priors, permitted jobs, resource limits, maintenance assumptions and the absence of field exposure denominators. |
| 4.1 | Initial conditions | §§4–5 | Arms start independently from a common condition. The ablation reruns from that state. Partial for a field-calibrated initial-state distribution. |
| 4.2 | Run length | §3.2, Table 1 and §4 | The finite reporting window and clock steps are specified. Evaluation integrates delivery over the full window. |
| 4.3 | Estimation | §§4–8, Tables 2–5 | Paired resampling, registered test order, family weighting, Holm correction, indeterminate endpoints and the distinction between FIT estimates and projections. |
| 5.1 | Implementation | §4 and §9, Data and code availability | The article identifies the scientific implementation and facility-core revisions. The public version index identifies source modules. Partial for the complete historical dependency environment in the article. |
| 5.2 | Sampling | §§3.2, 4, 6 and 9 | Quota sampling, within-family resampling, paired arms and sealed randomization material. The manuscript does not expose private seeds or specify every generator stream. |
| 5.3 | Execution | §§4, 7–8 and §9, Data and code availability | Within-condition state separation, paid positions, the shared parent and the FIT stop are identified. Trace-level replay is outside the public verification. |
| 5.4 | Computing platform | §9, Data and code availability | Partial. The availability section separates public code from private execution records. The article makes no hardware-performance claim and gives no complete machine specification. |
| 6.1 | Code access | §4 and §9, Data and code availability | Public source and versioned aggregates support the tables and figures. Custody governs access to native trajectories and seeds. |
