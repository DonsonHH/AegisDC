# Spec review: ticket 11 coupled facility acceptance

Baseline: `743898591152da34643c96ede6adced004723464`.
Runtime/test/runbook pin: `b135ecffb5fe5c3fecaa44859afbf925b8549bb1`.
Corrected architecture author: `2727adfce8128feb543efd2f489d37eb4a9bbd73`; visual delivery: `eb5df8e8bdd6448363b6bbcd29db86d439f22644`.
Contracts: ticket 11, full-facility specification, MAINLINE and ADR0003.

## Spec

**Findings: 1; verified closed: 1; remaining: 0.** No runtime/model defect or missing joint-domain behavior was established.

The visual finding concerns MAINLINE:15, "共用实体身份，语义分开". Original `plot_mainline_coupled.py:202` forced single-headed arrows for all relations, but V6 access a1–a5 are bidirectional. In particular the drawing contradicted the worker's loc_hx-to-control traversal. The separately versioned architecture author now derives arrowheads from each original bidirectional field and routes a4 around loc_hx. Independent original-resolution PNG inspection confirms all five double arrows and legible paths; SVG contains 81 editable text elements and no raster embedding. Source/data/artifact hashes and the superseded receipt reconcile. The original 125-file capture and old plot tool remain unchanged.

Seventeen public-seam targets independently pass under before/after guards matching nineteen frozen runtime/test/input files. The deterministic runbook builder contains declarative literals and frozen reference inputs, without reading ticket-11 outputs or calling the runtime; its rebuilt object equals the frozen 129-condition runbook.

Independent saved-data review passes all seventeen cases, three explicit domain/permission refusals, 125 artifact hashes, 1,272 states and 1,255 intervals. Entity identities/four graphs stay the same V6. Six-hundred-second normal stability and each domain's real counterexample are present. Shared capacities/common causes, distinct water/phase inventories, electrical/thermal boundaries, exogenous joint service, local biased/invalid control, qualification/access/tool/occupation constraints and retained spent work are exercised together.

The actual 240-second CLI episode matches independent input arithmetic: 275 requested, 231.8 delivered service-unit seconds, 36 interval-normalized deficit seconds, 145.5-second work abort, 120 travel-person seconds and 25.25 work-person seconds. Leakage closes as 20 =11.95 drained +8.05 retained kg under the declared common cp*T reference. Preparation arithmetic/reader mistakes remain identified separately from model defects.

Guarded tests, independent account recomputation and visual closure receipts are in `C:/Users/Donson/AppData/Local/Temp/aegisdc-review-11-spec-attachments/`. The plot correction reruns neither physics nor the full suite. M1 root acceptance, numerical qualification, field calibration and policy/AI conclusions remain separate gates.
