# Ticket 04: full-facility electrical capacity and outage verification

This accepts a finite engineering slice of the same eight-domain synthetic
facility. It does not resolve the complete-facility research objective or the M1
gate. The [healthy-run model](healthy-run-model.md) and
[fixed mainline](../MAINLINE.md) retain their scope. Registered research trials,
training runs and agent/model calls remain zero; field calibration is pending.

## What was already implemented and what changed

The accepted v2 runtime already enforced one aggregate feeder, the shared AC
switchboard, the rectifier's **AC input** capacity, finite UPS output and generator
output. It allocated actual power before computing heat and delivered service.
These existing behaviors are accepted here through independent hand examples and
public full-facility runs rather than replacement with a larger electrical model.

The new implementation is an input-domain correction at the actual electrical
component boundary, `aegis_dc.power.allocate_power`. Negative pump requests
previously released fictitious power; negative capacities, nonfinite quantities,
invalid efficiencies and negative reserve inventories could also produce invalid
points or incidental arithmetic errors. The component now rejects these inputs
with `ValueError`. Its allocation rules and the v2 numerical snapshot are unchanged.
The source implementation and nine focused tests are commit
`a50b1e5e6f87397a57b226f805992fd5470a6f7f`.

## Electrical mapping and evidence level

The supported topology is the scenario's frozen, version-checked topology, not a
generic graph reachability solver. The physical and functional relations share
the declared asset IDs. Their `R0`/`Rrun` source notes label instance connections,
coverage, priorities and numerical values as synthetic assumptions. The separate
`site_feeders` record remains null: as-built feeder, protection and backup coverage
has not been obtained. Zhengzhou sources motivate engineering categories and
selected interfaces; they do not calibrate these power limits or connections.

|Declared path|Implemented response|Model boundary|
|---|---|---|
|`grid -> main_switchboard`|Available grid power is bounded by both capacities|One ideal aggregate MV/LV feed; no independent feeder branches|
|`generator -> main_switchboard`|Running generator uses remaining shared switchboard capacity and finite fuel|An input to allocation; complete-outage start delay is the existing plant rule|
|`main_switchboard -> local_controller, internal_pump, intake_pump, room`|AC is allocated in that order before IT|Priority is a research setting, not a site protection coordination claim|
|`ups -> local_controller, internal_pump, intake_pump`|Only these three loads can use finite, output-limited UPS power|UPS input/recharge and detailed reserve coverage remain outside this slice|
|`main_switchboard -> rectifier -> compute, network, storage`|Rectifier input is capacity-limited; available DC is proportional to bounded requests|Per-service powers are explicit synthetic coefficients, not a MW-to-FLOPs relation|

The aggregate MV/LV feed, switchboard and distribution have unit efficiency.
Consequently this slice does **not** claim to include transformer/cable losses,
voltage/current constraints, reactive power, short circuits or branch protection.
Rectifier, UPS discharge and diesel conversion are the explicitly modeled losses.
This is an electrical power/energy budget at a declared ideal AC boundary.

The electrical account is
`grid + generator + UPS_output = sum(actual loads) + rectifier_loss`.
UPS stored energy decreases by `UPS_output / eta_UPS`; its difference becomes
room heat. Fuel decreases by `generator_output / eta_diesel`; its difference exits
the external generator waste-heat boundary. Neither reserve is an extra grid
input in the whole-facility energy account.

Actual compute power enters the solid, network/controller/room power enters the
room, storage power enters internal water, and pump heat uses the existing one-time
fluid/room allocation. Rectifier and UPS losses enter the room once. Removing
compute power removes new compute heat; it does not delete stored thermal energy.

## Independent expected outcomes

All tests use `allocate_power` or `simulate_scenario`; the CLI evidence uses
`python -m aegis_dc simulate`. No private plant methods, mocks or hidden dispatch
state are used. The following numbers were specified from hand budgets before the
verification runs.

|Case|Independent budget/outcome|Observed result|
|---|---|---|
|100 kW feeder or switchboard hand case|Auxiliaries need 1+10+5+5 = 21 kW; 79 kW AC leaves 75.05 kW DC and 3.95 kW rectifier loss at 95%|Compute/network/storage receive 63.2/7.9/3.95 kW; whichever source has 100 kW has zero slack|
|Shared grid/generator hand case|60 kW grid + 40 kW generator fill a 100 kW switchboard; 40% diesel efficiency consumes 100 kW fuel and rejects 60 kW waste|Exact hand values; UPS is unused despite positive stored reserve|
|50 kW rectifier input|95% conversion gives 47.5 kW DC, half of 80/10/5 kW IT requests|40/5/2.5 kW actual IT; auxiliaries continue; 2 s demand gives 1 service-unit s delivery and 1 s deficit|
|Aggregate feeder or switchboard limitation|Baseline auxiliaries use 326400/7 W. A 676400/7 W limit leaves 50 kW AC for IT|Same half-service response; control remains normal and both pumps retain normal flow|
|Zero rectifier capacity|IT has no DC; declared AC auxiliaries still have power|Zero IT delivery, 2 s deficit, powered room/control/pumps|
|Grid or switchboard outage with 20.2 kW UPS|1 kW controller + 19.2 kW internal pump exhaust its output budget|Lake pump, room and IT get zero; 2 s UPS output is 40400 J and loss is 3513.04347826087 J|
|Compute local protection|Only compute permission is removed|Compute is zero, network/storage remain 100/100 kW; joint service deficit is counted once|
|CLI outage at 0.25 s, restore at 1.25 s|Three seconds of exogenous demand remain; one second has no IT execution|3 demand service-unit s, 2 delivered, 1 s deficit; 2 MW stored-heat transfer persists at outage onset|

The half-service fixtures deliberately use an insulated solid with 2 MJ/K heat
capacity. Forty kW for two seconds independently predicts a 0.04 K rise; all three
full-facility supply-limit runs match it. This is a labeled analytic fixture,
not an asserted normal plant operating point. The unchanged normal v2 run is a
separate 60 s case with zero service deficit. The predecessor's accepted 600 s
normal and 180 s supply/work evidence remains in
`evidence/mainline/engineering/03-root-demonstration/`.

## Executed evidence and reproduction

The committed-source public evidence is
[`run-01-committed-public-validation/receipt.json`](../../evidence/mainline/engineering/04-power/run-01-committed-public-validation/receipt.json).
Nine cases pass 209 checks. Across them the largest absolute whole-run energy
residual is below `3.91e-6 J`; the largest component residual is below `3.28e-6 J`.
Mass residuals and electrical residuals pass the recorded `1e-9 kg` and `1e-7 W`
checks. All minimum electrical capacity slacks are nonnegative within `1e-8 W`
roundoff. The report does not establish time-step convergence; that remains ticket 12.

The [fresh-read integrity report](../../evidence/mainline/engineering/04-power/run-01-committed-public-validation/artifact-integrity.json)
matches all 27 saved scenario/trajectory/balance files to their manifest hashes and
record counts. Every case has eight domains, the same committed source tree and
the frozen R134a property identity
`9494001ac94e04c6b2474b1c70fdf78ff4b5958b3f5c39f9790581561097329c`.
This property model is the existing pure-fluid equilibrium research surrogate.
No actual site coolant identity is inferred.

The v2 input file is unchanged, SHA-256
`6641e8014a9e1bf7a601f92b699fdfb79667d46b357240ec60110fa9cb6cd51a`.
The nine engineering runs record source-tree identity
`7245a3917197d419ddb15123f91b1a04ce5cb84a15d00457cbfa761d3776c938`
and `implementation_has_changes=false`. The reproducer hash is in the receipt.
Each run retains `scenario.json`, `private-state.jsonl`, `balances.jsonl` and
`run.json`; evaluator state is explicitly private and no dispatch view is created.

The [test-attempt ledger](../../evidence/mainline/engineering/04-power/run-01-committed-public-validation/test-attempts.json)
preserves two intentional red runs and every subsequent green run. The first red
shows a negative pump request was accepted. The second has seven failed subcases
and a zero-efficiency arithmetic error. Their fixes pass before further acceptance
checks are added. Existing correct allocation/thermal behaviors pass on first
verification and are labeled as existing behaviors in the attempt directories.

Focused checks: **9/9 passed**. Existing facility/property/CLI checks: **22/22
passed**. Full regression: **188 collected, 186 executed, 2 declared optional Torch
skips, zero failures/errors**. The skips are the existing two
`SupplementalModelTests` and remain visible in `attempt-13-full-regression/tests.log`.
This worktree's main Python did not include the root checkout's isolated Torch
directory. Root integration will perform its own enabled-Torch acceptance; this
record does not claim a zero-skip result.

From the chosen worktree, with the specified main Python:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& 'C:/Users/Donson/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s tests -p test_mainline_power.py -v
& 'C:/Users/Donson/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s tests -p test_full_facility_plant.py -v
& 'C:/Users/Donson/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s tests -v
& 'C:/Users/Donson/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' evidence/mainline/engineering/04-power/reproduce.py --output evidence/mainline/engineering/04-power/<fresh-run-directory>
```

Use a new directory for reproduction. Existing outputs, red logs, source inputs
and predecessor evidence are preserved. These checks establish bounded synthetic
engineering behavior; they establish neither site availability nor an inspection,
AI, RSI or policy-effect gain.
