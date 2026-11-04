# Ticket 08 engineering evidence

Implementation `2c328cab` permits timed changes to the three existing normalized
component service ceilings. It reuses the accepted joint-service and accounting
logic. Accepted integration `588cec81` was merged before capture, giving clean
execution source `60f21f25dc55765124398215b065c2c29bac0dfb`.

The fixed complete-facility objective and M1 gate remain active. These are finite
engineering fixtures, with zero research/model/training calls, PENDING field
calibration and NOT_ESTABLISHED scientific gain.

|Artifact|Accepted evidence|
|---|---|
|[Account contract and units](../../../../docs/mainline/service-accounting.md)|Normalized demand/capacity, separate integrals, interval-specific deficit denominator and unresolved absolute throughput|
|[Red/green record](red-green.md)|Actual missing-boundary failure and eight public run/CLI behavior tests|
|[Frozen hand cases](hand-cases-v1.json)|Eleven declared same-facility inputs and literal independent interval sums|
|[Capture program](capture_engineering.py)|Public run/CLI/save interfaces, new directories and fresh reads|
|[Run receipt](runs-60f21f25-01/receipt.json)|Eleven full eight-domain trajectories, six expected rejections and 59 artifact hashes|
|[Full regression](acceptance-60f21f25-01/summary.json)|225 discovered /223 executed, zero failure/error, two declared optional Torch skips, twenty original-file hashes pass|

Network and storage reductions overlap in the hand case: demand integrates to 2,
joint delivery to 1.2 normalized service-unit s, and deficit to 0.8 s. Adding the
individual .4 s and .6 s component losses would count the overlap twice.
Any individually unavailable required component interrupts joint delivery even
while the other two remain fully powered.

Demand .5 then 2 with a quarter-rate bottleneck gives requested/delivered work
2.5/.5 and normalized deficit 1.375 s. Zero-demand intervals contribute zero.
A 1 s execution pause within 3 s leaves requested work at 3, delivery at 2 and
deficit at 1 s after execution is restored. The pause is an execution-request
fixture, not a hardware failure; capacity changes use separate ceiling events.

Demand/capacity are dimensionless multipliers of a declared synthetic reference
service rate. Integrated work uses normalized service-unit seconds. No absolute
job rate, FLOP/s, bit/s or IOPS is calibrated, and none is inferred from MW.
Actual supplied execution power enters the heat account under the existing
declared linear-power assumption. Queue/backlog/deadline and multi-class policy
models remain later work; restored service does not erase already counted loss.

All eleven runs retain the same eight-domain v2 scenario and private evaluator
boundary. Maximum interval energy residual is `3.4851254895329475e-6 J`, whole-run
residual `2.5853514671325684e-6 J`, and mass residual
`2.2737367544323206e-13 kg`. This is finite numerical/accounting verification,
not field applicability, general step convergence or method-effect research.

The primary Python 3.12.14 used only this worktree's `src` in `PYTHONPATH`.
The two optional historical neural checks were skipped because the isolated
Torch library was absent from that interpreter path; no unexpected skip occurred.
The root owns enabled-Torch acceptance and independent review. The full suite ran
once on the assembled source; later source identity checks do not repeat it.

Capture again from a selected source tree, using a fresh destination:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python evidence/mainline/engineering/08-service/capture_engineering.py --output <new-engineering-directory>
```

Native red/green and full-regression outputs retain their original bytes under
the scoped whitespace attributes. All old evidence and shared scenario/runtime
files are preserved. Global progress was not edited by ticket 08.
