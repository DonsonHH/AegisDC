# Ticket 06 engineering evidence

Source implementation: `1562473b6afe6d49c8a60961cf275e7449c0a1bc` on
`donson/mainline-06-phase`, from accepted integration `0ee160cd`.
The fixed complete-facility objective remains active. These are engineering
fixtures and expected rejection cases, with zero research trials/model calls/
training, PENDING field calibration and NOT_ESTABLISHED scientific gain.

The source change corrects legal saturation endpoint refusal in the existing
fixed-M/U/V inverse. It adds no single-phase model or general material framework.
The fixed R134a surrogate table and the accepted v2 scenario are preserved.
The actual site's coolant remains unknown.

|Artifact|What it establishes|
|---|---|
|[Domain and assumptions](../../../../docs/mainline/phase-domain.md)|Pure equilibrium/no noncondensable conditions, shared water interface and rejection limits|
|[Red/green record](red-green.md)|A real four-subcase failure, correction and eleven focused public behavior tests|
|[Frozen direct EOS inputs/outputs](eos-reference-01/direct-eos-reference.json)|Nine fixed-volume signed-heat states, fourteen endpoint states and four unsupported states; same-EOS numerical cross-check only|
|[Offline EOS author](create_eos_reference.py)|Direct CoolProp calls with predeclared limits; never imports the implementation|
|[Engineering capture program](capture_engineering.py)|Public run/save/property APIs only; freezes input variants before running, writes fresh directories and verifies saved bytes/counts by readback|
|[Run receipt](runs-1562473b-01/receipt.json)|Eleven complete-facility trajectories, five expected refusals and 47 fresh-read artifact hashes|
|[Full regression](acceptance-1562473b-01/summary.json)|190 discovered, 188 executed, zero failures/errors, two declared optional Torch skips; twenty original-file hashes pass|

The fourteen endpoint cases were frozen before correcting the inverse. Four
failed at the predecessor and all pass after the correction. An endpoint needs
an already admissible quality and an energy match within eight ulps. Physical
out-of-domain pressure/quality is not clipped; 0.1 J/kg finite excursions beyond
the tested endpoints and a heated full-facility run leaving 3 MPa are refused.

The independent first-step energy examples hold the declared beginning-of-step
2 MW interface over one 1 s explicit balance interval. Their U changes are
`+2000000 J` and `-2000000 J`; neither adds a latent-heat source. At constant
2000 kg inventory, nominal pressure moves from 800 kPa to 812848.488 Pa or
787268.687 Pa. Condensation adds exactly 2 MJ to the companion water state.
The reverse-temperature example transfers approximately 1.350028 MJ from water
to refrigerant, preserving its sign and reciprocal energy.

Both 10 s transient fixtures keep all eight operational domains in the same
scenario. Across the eleven runs, maximum interval energy residual is
`3.87127511203289e-6 J`, whole-run residual `4.328787326812744e-6 J`, and mass/
phase-mass residual `2.2737367544323206e-13 kg`. These checks establish finite
conservation/domain behavior, not time-step convergence, real boiling transients,
empirical fluid accuracy or site applicability.

The full regression used the primary Python 3.12.14 with only this worktree's
`src` prepended. The two optional historical neural checks were skipped because
the isolated Torch library was not on that interpreter's path; no unexpected
skip occurred. The root integration review owns the enabled-Torch check.

Reproduce the engineering capture from the chosen source tree (fresh output):

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python evidence/mainline/engineering/06-phase/capture_engineering.py --output <new-engineering-output>
```

Neither this command nor the tests import CoolProp. The separate reference
author requires an explicitly provided isolated 8.0.0 installation; the retained
receipt records its exact extension/version/source identities. Its results are
finite checks of the **same EOS**, not an independent empirical validation set.

Original table, ticket-03 artifacts and pre-meeting materials remain byte
preserved. No global milestone/status was advanced by this ticket.
