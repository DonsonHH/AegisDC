# Ticket 10: finite actor power, transfers and paid standby cooling

This is a finite engineering acceptance of the same eight-domain synthetic
facility. The fixed research objective and M1 gate remain active. Research,
training and model-call counters are zero; gain is NOT_ESTABLISHED and field
calibration PENDING.

|Identity|Role|
|---|---|
|`efb7bbdc`|Final physical/26-target pin; same-time fix `7e9015c0`|
|`179094ed28b482fd75c50396c6213472870eed3d`|Clean execution revision, including frozen runbook and capture tools|
|`2172dab0f2ba7e7913c926bc196f8a6c0a3f0ea9`|Committed durable execution/full-check data, independently checked in a fresh detached worktree|

- [Physical/control assumptions](../../../../docs/mainline/10-reserve-implementation.md)
  describe the separately powered controllers, ideal finite starter store,
  normal/protected distribution, signed heat and preserved 07/09 update order.
- [Frozen runbook](runbook-v1.json) declares twenty full-facility cases and
  independent literal budgets or qualitative thermal/protection conditions.
- [Capture receipt](fixtures-179094ed-01/receipt.json) records twenty runs, six
  expected refusals,134 declared new artifacts and36 prior durable files.
- [One complete regression](acceptance-179094ed-01/summary.json) passes with289
  discovered /287 executed, no failure/error, two existing optional Torch skips,
  no unexpected skip and twenty preserved historical-file hashes.
- [Fresh-checkout delivery proof](delivery-readback-2172dab0-fresh-01.json) is an
  actual PASS against both execution Git and committed delivery blobs. It checks
  229 private samples /209 balances and requires no runtime caches.
- [Development record](red-green.md) and [fixture preparation ledger](preflight-ledger.json)
  preserve actual reds, input corrections and their evidence limits.

The capture receipt's original `PENDING_COMMIT_AND_FRESH_CHECKOUT` delivery field
is preserved as its pre-delivery state. The later fresh-checkout proof supplies
the completed delivery gate; the original receipt was not rewritten.

The UPS internal controller can start without the dead main PLC. Its AC input is
actually reserved in the budget, with finite battery fallback while output is
disconnected. Generator local control/cranking have a separate finite store;
empty start energy cannot be replaced by main fuel or an unsupplied main PLC.
After connection actual AC may sustain control, while future restart still needs
start energy. Exact depletion and transfer times split integration intervals.

UPS covers only the original controller/internal-pump/intake-pump subset.
Maintenance, failed transfers and shared distribution failure remove usable
output despite positive nominal capacities/stores. The fan is paid AC, shares
one actual internal circulation with the exclusive primary path, and has finite
UA/air capacity/heat cap. Water heat is removed from cold storage once; fan,
generator-control/cranking and engine loss leave through their declared outside
boundaries, while UPS control/conversion loss enter room once.

The independent whole-UPS budget gives3.24 MJ protected output,360 kJ conversion
loss and32.6 kJ internal control from3.6326 MJ storage, depleted at32.6 s after a
.2 s connection delay. A generator3+2 s hand case connects at5 s and exhausts
42750 J main fuel at15 s, delivering11100 J electricity plus31650 J engine waste;
starter/control dissipation is separate. Both selector directions settle UPS need
at the current paid sample without resampling the PLC or waiting a numeric step.

Actual hot leakage, mixed floor energy, work-access gates and biased local-control
latches remain in the combined profile. An unusable cold source reaches service
through true thermal protection in a deliberately sensitive engineering case;
those thresholds are synthetic, not real equipment limits. Maximum frozen-package
interval energy residual is `4.403875209391117e-6 J`, whole-run
`6.38933852314949e-6 J`, mass `4.547473508864641e-13 kg`.

Real Zhengzhou standby piping, capacity, controls and coverage remain unresolved.
The sensible performance map is an explicit research approximation with no
evaporation/makeup, detailed battery chemistry, electrical waveform or real N+1
availability claim. Numerical-domain/step qualification and policy-effect
research remain their later gates.

From a fresh checkout of the delivery commit, verify without rerunning physics:

```powershell
python scripts/verify_reserve_candidate.py --directory evidence/mainline/engineering/10-reserve/fixtures-179094ed-01 --full-index evidence/mainline/engineering/10-reserve/full-acceptance-index-179094ed.json --delivery-commit 2172dab0f2ba7e7913c926bc196f8a6c0a3f0ea9
```

Replay the physics only at the recorded execution source, with its frozen
runbook and a new output directory. Automatic `__pycache__`, `.pyc` and `.pyo`
files were classified non-deliverable before hashing. All declared persistent
files are required; no hash failure is skipped. The completed full-check files
were sealed separately after both parallel processes had finished. Root owns the
final unified Torch/metadata integration check; this milestone is not M1 or
overall research completion.
