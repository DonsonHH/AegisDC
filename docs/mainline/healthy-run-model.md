# Complete-facility M1 engineering run

Ticket 03 executes one Zhengzhou-inspired **synthetic research facility**. Its
low-order working point and all numerical settings are research assumptions or
declared calculations. This is not an as-built Zhengzhou reconstruction, material
recommendation, field calibration, policy comparison or scientific-gain trial.
The fixed objective and remaining gates are in [MAINLINE](../MAINLINE.md).

## Interfaces and versions

```python
from aegis_dc.scenario import load_scenario
from aegis_dc.plant import simulate_scenario, describe_run, save_run

scenario = load_scenario("configs/full-facility-mainline-v2.json")
result = simulate_scenario(scenario, duration_s=600, step_s=1)
summary = describe_run(result)
save_run(result, "outputs/engineering/a-new-run-directory")
```

```bash
python -m aegis_dc simulate --output outputs/engineering/a-new-run-directory
python -m aegis_dc simulate --duration 10 --step 0.5 --inputs engineering-inputs.json
```

The Python result is a **private plant/evaluator** trajectory. It contains `trace`
(eight-domain state samples), `balances` (one independent boundary account per
integration interval), `events`, `work_records`, `inputs`, `source_config`, source
and property identities, and `summary`. No dispatch adapter or risk issue is
created. Local measurements in this result have `LOCAL_PLANT_ONLY` visibility;
later evidence tickets must independently implement availability/provenance rules.

The CLI prints the compact metadata/summary. `save_run` creates a fresh directory
containing `run.json`, `scenario.json`, `private-state.jsonl` and `balances.jsonl`.
The manifest records file hashes/counts, the canonical scenario hash, Git commit,
actual source-file hashes and whether implementation files differ from Git.
Existing directories are refused. The complete input dictionary is revalidated
and copied; runs do not modify it. The same inputs deterministically replay.

The default `scenario` CLI and old v1 configuration remain structural and
unchanged. V2 adds the runtime contract, 79 bounded SI parameters, an explicitly
powered internal pump and its local flow instrument: 40 shared entities, 8 domains,
33 physical / 18 functional / 14 control-information / 5 access edges. The runtime
supports this declared topology, not arbitrary graph execution. A topology digest
is checked against the implementation version; changing relations requires an
explicit model revision rather than silently running the old connections.

The quantity extensions are `hydraulic_resistance` (`Pa*s2/m6`), dimensionless
`fraction`, `temperature_difference` (`K`) and zero-capable `inventory_mass` (`kg`).
All physical coefficients/initial conditions/boundaries remain source-tagged SI
parameter records. Work/event times are finite, source-tagged engineering inputs.

## Evidence and assumptions

|Evidence type|Use in this model|Limit|
|---|---|---|
|Zhengzhou case sources|Eight-domain engineering reference, lake/plate-HX/internal-water and phase-cooling paths|No claim that the numerical working point or detailed synthetic connections are real|
|Published conservation models|[State-equation proposal](../research/20261104/facility-cases/state-equations.md), [model basis](../../evidence/mainline/engineering/property-reference/model-basis.md)|Low-order modeling choices, not site tuning|
|Frozen EOS reference|[R134a table](../../configs/materials/reference-r134a-saturation.json), CoolProp 8.0.0 / HEOS / DEF|Pure equilibrium surrogate only; actual Zhengzhou coolant is unknown|
|Derived research initialization|Equations below and v2 parameter source notes|One coupled synthetic steady working point|
|Unresolved site data|The scenario's separate `site_gaps` records remain null|No missing value becomes zero or an observed parameter|

## Eight coupled domains

|Domain|Actual state/rule in this run|Observable consequence|
|---|---|---|
|Power|AC input, switchboard and rectifier limits; efficiency and prioritized actual loads|Supply limitations change IT/auxiliary execution power and heat|
|Backup|UPS finite stored energy/output limit/efficiency; generator off/starting/running/fuel exhaustion with finite fuel|Protected auxiliary continuity and delayed generator service restoration|
|Facility cooling|Paid lake/internal pump operating points; two finite internal-water volumes and separate HX outlet ports|Resistance, speed and supplied pump power change flow, heat rejection and stored temperatures|
|Equipment/environment|Solid and room energy, refrigerant M/U/V and phase equilibrium, fixed humidity boundary|Stored solid heat persists after IT loses power; phase inventory and room temperature evolve|
|IT service|Exogenous demand and separate compute/network/storage actual capabilities|Joint delivery is the minimum required capability; unmet demand is retained|
|Local control/monitoring|Sampled local thermal/flow measurement, pump hysteresis and thermal/low-flow protection|Automatic commands change physical response without staff requests|
|Space/access|Separate nuisance-water inventory, finite drainage and threshold access state; qualified walking graph|Water/closed locations and access qualifications prevent work|
|People/tools/work|Worker/tool locations, qualification, shared tools, route travel, shift end and occupation/completion|Infeasible requests are rejected and accepted requests consume real time/resources|

Backup tower mode is explicitly `standby_uncommanded`. Full tower takeover,
maintenance, common causes and validated reserve coverage remain ticket 10; the
backup domain already acts through finite UPS and generator states. M1 does not
claim that every future mode of every asset has been implemented.

## Electrical and service boundaries

Controller, internal pump, intake pump, room auxiliaries and IT are served in that
declared order. UPS paths protect the first three only, and are separately power
limited. The generator starts after a complete grid outage and its declared delay;
it does not parallel-start for a partial grid shortfall in this model. Generator
electrical output consumes `P_generator / eta_diesel` fuel energy; the difference
leaves through its external waste-heat boundary. UPS recharge is not modeled.

`P_rectifier_out = eta_rectifier * P_rectifier_in`. Actual supplied IT power is
allocated proportionally to the bounded requests. Requested execution power is
the configured per-unit operating power times `min(service_demand, capacity)`;
compute protection can set compute execution to zero. Compute, network and storage
capability is each bounded by its configured capacity and actual power divided by
its nominal power per unit of service. These per-unit powers are explicit research
coefficients; their real workload-dependent curves are not known.

Joint delivered service is `min(demand, compute, network, storage)`. The account
integrates requested and delivered service-unit seconds separately. The normalized
deficit time integrates `(demand - delivered) / demand` when demand is positive,
and zero when demand is zero. Two simultaneously limited components do not count
the same service deficit twice. No electrical shedding deletes the exogenous demand.

## Hydraulic and thermal closure

Each paid pump uses ideal quasi-steady head `dp = dp_unit * n^2`, loop resistance
`dp = K*q^2`, and electrical power `dp*q/eta`. A power limitation reduces speed
with the cubic power law and recomputes head/flow. The lake filter multiplier acts
on its declared aggregate resistance. Nominal flow parameters are model capacity
bounds. No elevation, pump inertia, cavitation or parallel-pump inference is made.

`pump_fluid_heat_fraction` allocates **total electrical pump power** between that
pump's own fluid and the room. Hydraulic power is diagnostic, not a second heat
source. Lake pump heat raises the separate lake HX inlet port. Internal pump heat
enters the internal hot volume. All remaining pump heat enters the room once.

For capacity rates `Ci = rho*cp*qi`, `Cl = rho*cp*ql`, the counterflow plate HX uses
the epsilon/NTU relation with declared UA. Its one signed heat transfer is
`Qhx = epsilon * min(Ci,Cl) * (Th - Tl_hx_in)`. With either side stopped, this
flow-mediated transfer is zero; stagnant wall conduction is outside this model.
Outlet ports are `Ti_hx_out = Th-Qhx/Ci` and `Tl_hx_out = Tl_hx_in+Qhx/Cl`.
The finite cold-volume temperature is never forced equal to its HX outlet port.

Internal water retains its own closed hot/cold masses:

```text
Ch * dTh/dt = Qcond + Pstorage + Pinternal_pump_fluid - Ci*(Th-Tc)
Cc * dTc/dt = Ci*(Th-Tc) - Qhx
Qcond = (1-exp(-UAcond/Ci)) * Ci * (Tr-Tc)    [zero when Ci=0]
Cs * dTs/dt = Pcompute_actual - Gsr*(Ts-Tr) - Gsa*(Ts-Ta)
dUr/dt = Gsr*(Ts-Tr) - Qcond
```

The condenser's water outlet is implied by `Tc+Qcond/Ci` in the hot-volume inlet
enthalpy. Condenser heat is not added again as a refrigerant flow/latent-heat
source. Likewise `q_internal_hx` and `q_to_lake` are accounting views of the **same**
plate-HX enthalpy transfer, not additional heat loads. Lake, internal water,
refrigerant and nuisance floor water retain separate mass identities.

The room receives actual network/controller/room auxiliary power, rectifier/UPS
losses, its pump heat fractions and `Gsa*(Ts-Ta)`. Its passive effective external
heat rejection is `Groom*(Ta-Tambient)`. Room auxiliary power is a heat source;
it is not unpowered refrigeration. Humidity is a fixed declared boundary in M1.

The refrigerant control volume includes bath, vapor passage and refrigerant side
of the condenser. It is pure, fixed-volume, closed and in two-phase equilibrium;
there are no air/noncondensable, makeup, vent or leak flows here. `M` is conserved;
`U` evolves with solid/condenser heat. The property interface interpolates T, v and
u in ln(p), derives `rho=1/v`, `h=u+p*v`, and solves M/U/V across **every** table
segment. Multiplying the energy equation by the positive phase-volume difference
gives a quadratic per segment, so interior roots are also checked. Absent,
nonunique or out-of-domain roots fail. Quality is never clipped. One-ulp rounding
of `exp(log(endpoint))` inside an already valid segment is handled as coordinate
roundoff. No single-phase continuation or real boiling/pressure transient is claimed.

## Coupled normal initialization

The frozen table working point is `p=800000 Pa`, `x=0.1`, `M=2000 kg`. The table
gives `Tr=304.477510064146 K`; consistent mixture sums give
`V=6.647467643830208 m3` and `U=516335850.31469756 J`. These are table-derived
research initial conditions. The independent external-EOS reference at the same
pressure is `304.477463163277 K`; its slight difference is interpolation error.

For the normal actual powers, lake/internal flow is `0.1/0.12 m3/s`, pump electrical
power is `21428.5714286/19200 W`, IT compute/network/storage power is
`2000000/100000/100000 W`, and rectifier loss is `68041.2371134 W`.

1. Internal water receives `Qwater = 2000000 + 100000 + 19200 = 2119200 W`.
2. The plate-HX relation sets `Th = Tl + Plake/Cl + Qwater/(epsilon*Cmin)`.
3. The finite cold volume uses `Tc = Th - Qwater/Ci`.
4. `UAcond = -Ci*ln(1 - 2000000/(Ci*(Tr-Tc)))` closes the 2 MW condenser duty.
5. `Ts = Tr + 2000000/Gsr`, with explicit `Gsa=0` for this working point.
6. `Ta = Tambient + (Pnetwork + Pcontroller + Proom_aux + Prectifier_loss)/Groom`.

The resulting temperatures are `Th=300.529561676306 K`, `Tc=296.296214599377 K`,
`Ts=308.477510064146 K`, `Ta=298.951374570447 K`, with
`UAcond=335444.686243954 W/K`. Each derived value and source note is in v2. The
normal run is stationary under these explicit equations, not under unrelated v1
temperature labels. Perturbed inputs deliberately create nonzero thermal evolution.

## Local control, access and work

Local sampling has its own configured period, independent of the maximum numeric
step. Ideal local refrigerant temperature and internal flow can trip compute.
Thermal protection resets only below the separate reset threshold with adequate
flow. Pump commands use high/low hysteresis; loss of controller power holds the
declared fail-safe pump command and removes compute permission at the next sample.
No human dispatch is required for protection. Delayed/noisy dispatch evidence and
control communication faults remain later tickets.

Floor water is an explicit **external ambient-temperature nuisance-water source**,
not a loss from either cooling inventory. Its sensible-energy inflow/drain boundaries
use `cp*Tambient`. Drainage stops at exact zero inventory. Rising threshold crossing
closes `loc_it`; falling crossing opens it. This does not yet represent live coolant
leakage, flood damage, humidity balance or a geometry-resolved room.

An optional inputs file has schema `aegisdc-engineering-inputs-v1`, `work_requests`
and `boundary_events` lists. Each work request declares `id`, `time_s`, `worker_id`,
`work_interface_id`, `target_id` and `source_note`. Each boundary event declares
`time_s`, `parameter_id`, `value`, `source_note`; only the listed exogenous inputs
are allowed and values must stay inside their original SI parameter ranges.

Jobs require the interface qualification, compatible available tools, a qualified
open path via tool pickup, and completion within the declared shift. Tools are
reserved across travel/work and carried locations follow the worker. Equal-time
completions release resources before incoming requests. Route ties are deterministic.
Requests with qualification, worker, tool, access or shift conflicts are rejected.
Accepted jobs retain separate scheduled arrival/completion and actual arrival/
completion times; work extending beyond the run is pending rather than completed.
Access is rechecked at gates and work locations; a newly blocked destination aborts
the job at the last safe gate, with travel time already spent retained. Shared tools
are released where actually carried. Without requests, all workers remain idle.

The four professional workers include a declared dual-qualified control/cooling
worker, so two qualified workers can compete for the same portable flow meter.
All jobs produce `ENGINEERING_WORK_RECORD_ONLY_NO_REPAIR_OR_EVIDENCE`: completion
does not diagnose a failure, repair it or create an error-free inspection report.
Evidence-driven parallel dispatch, specialized task quality, moving-target work,
authorized interventions and recovery verification remain tickets 21–24.

## Numerical and conservation checks

Forward energy updates use a bounded configured maximum step and split at timed
inputs, control samples, generator start, UPS/fuel depletion, floor empty/access
crossing, requests, route arrivals and work completion. Finite reserves cannot
serve a full interval past exhaustion. Exact depletion events set the known empty
inventory at the computed event time; this is not negative-inventory clipping.

Each interval records before/after energy inventories, component energy rates,
shared heat transfers, electrical residual, per-medium mass in/out/inventories,
capacity slacks and separately integrated service/personnel/tool accounts. Whole
facility storage includes thermal, refrigerant, UPS, fuel and floor-water energy.
External energy is grid plus floor inlet, minus lake/room/generator-waste/floor-drain
outputs. Generator/UPS conversion is internal to that boundary. A separate whole-run
residual is also checked. Closed-loop mass zero residuals follow actual matched
port flows, not mixing lake and internal water or inventing coolant makeup.

Energy residual acceptance is `0.01 J + 1e-10 * boundary throughput`; mass tolerance
is `1e-9 kg` in this configuration. All tolerances are explicit parameters. State
temperature ranges and maximum temperature jump are enforced. Nonfinite data,
unsupported topology, missing parameters, excessive step changes, capacity
violations and invalid two-phase states fail rather than return successful status.
The checks are finite engineering verification; rigorous step-error/domain
qualification remains ticket 12 and subsequent model-validity work.

Independent checks cover the frozen external M/U/V flashes, 100 kPa / 0.01 m3/s /
50% pump, 40 kW HX, 3 K analytic thermal rise, 100/95/5 kW conversion, 32.4 s UPS
exhaustion and the joint-service 4 s deficit. Controlled supply/filter/protection/
drainage/work counterexamples establish behavior beyond static domain labels.
M1 and the full research objective remain subject to root integration acceptance;
this engineering fixture is not completion of M2–M7 or evidence of policy benefit.
