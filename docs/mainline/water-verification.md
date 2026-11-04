# Water-response engineering verification

Ticket 05 extends the same eight-domain Zhengzhou-inspired **synthetic research
facility**. The water-v3 numbers, aggregate valve characteristic and shutoff relay
are explicit research assumptions. No real Zhengzhou valve selection, pump curve,
control action, commissioning point or parallel-plant availability is inferred.
The fixed objective and remaining gates stay in [MAINLINE](../MAINLINE.md).

## Supported version and public boundaries

`configs/full-facility-mainline-water-v3.json` retains the scenario-v2 schema and
uses runtime `aegisdc-low-order-facility-water-v2`. Its supported four-graph digest
is `40852da7230c6db601d8ab7d5a360b45e61356df929826fe62a90016305aeea2`.
The old runtime/digest is still supported; any changed relation requires a new
explicit model revision. There is no generic graph solver or ignored topology.
V1, V2, the frozen property table and both CLI defaults are preserved as inputs.

```python
from aegis_dc.scenario import load_scenario
from aegis_dc.plant import simulate_scenario, save_run

scenario = load_scenario("configs/full-facility-mainline-water-v3.json")
result = simulate_scenario(scenario, duration_s=2, boundary_events=[
    {"time_s": 0.25, "parameter_id": "internal_valve_opening", "value": 0,
     "source_note": "Imposed actual shutoff engineering fixture."},
])
save_run(result, "outputs/engineering/a-new-water-run")
```

```bash
python -m aegis_dc simulate --model configs/full-facility-mainline-water-v3.json --duration 2 --output outputs/engineering/a-new-water-run
```

`valve_loop_operating_point` in `aegis_dc.heat_transfer` is the replaceable
component boundary. Facility tests use `load_scenario`/`validate_scenario` and
`simulate_scenario`; artifacts use `save_run`. Results are private plant/evaluator
trajectories. An imposed position is a physical engineering input, with no
dispatch access, diagnosis, authorized human intervention or actuator delay.

New timed engineering inputs are `lake_valve_opening`, `internal_valve_opening`,
`pump_pressure_rise`, `internal_pump_pressure_rise` and `plate_hx_conductance`.
They keep their source note, bounded SI parameter and event-split time. Legacy
V2 has no valve parameters, so valve events on that version are rejected.

## Identifiable flow and control paths

V3 adds the assets `lake_valve_group` and `internal_valve_group` in
`facility_cooling`, at `loc_lake` and `loc_hx`, with medium-specific in/out ports.
Both are targets of the existing qualified cooling-work interface and shared
portable flow meter. They do not add workers or capacity redundancy.

The lake path is lake -> intake pump -> filter -> lake valve -> lake side of
plate HX -> lake. The internal path is internal buffer -> explicit internal pump
-> internal valve -> internal side of plate HX -> buffer. Refrigerant, internal
water, lake throughflow and nuisance floor water retain separate mass accounts.

Valve position reports and pump permissive commands have the same entity IDs in
the control graph. The aggregate local control asset includes an immediate
hardwired shutoff relay, independent of its powered sampled thermal software.
`hardwired_pump_permits` records that relay separately from the held speed
command and last sample. It only prevents running a pump against a declared
closed series valve; thermal/low-flow compute protection still samples on its
own existing clock. This relay and the exact zero threshold are research rules.

## Hydraulic characteristic and shutoff branch

For positive opening `a` in `(0,1]`, the assumed valve flow coefficient is
proportional to opening. Its pressure-loss coefficient is therefore
`Kv(a)=Kopen/a^2`, in `Pa*s2/m6`. This is a selected low-order characteristic,
not an equal-percentage or measured vendor valve curve. The characteristic does
not change when a filter multiplier changes.

The ideal pump curve remains flat differential head at fixed speed:

```text
dp = dp_unit*n^2
Klake = Kpassive_lake*filter_multiplier + Kvalve_lake(a)
Kinternal = Kpassive_internal + Kvalve_internal(a)
q = n*sqrt(dp_unit/Ktotal)
P_hydraulic = dp*q; P_electric = P_hydraulic/eta
dp_passive = Kpassive*q^2; dp_valve = Kvalve*q^2
```

An electrical limit reduces speed by the cubic affinity law, then recomputes
flow, head and both pressure drops. Pressure fields are differential dynamic
losses. They are not gauge pressures; no absolute pressure, static elevation,
cavitation, inertia, water hammer or trapped differential pressure is solved.

At exactly `a=0`, a separate branch removes that pump's drive. Actual speed,
flow, pressure rise, dynamic pressure drops and requested/electrical/hydraulic
power are all zero. No artificial finite closed resistance or free fixed head
is used. The serialized valve resistance is `null` because the positive-opening
formula is inapplicable to this branch, while the state explicitly says closed.
No deadheaded-pump heating, shutoff leakage or stagnant HX-wall conduction is
claimed. Positive openings with nonfinite derived resistance fail; none is
silently clipped to a minimum opening or treated as closed.

|Loop|Passive K at multiplier 1|Full-open valve K|Preserved total K|
|---|---:|---:|---:|
|Lake|12,000,000|3,000,000|15,000,000|
|Internal|5,000,000|3,333,333.333333334|8,333,333.333333334|

These are explicit decompositions of the V2 synthetic equivalent resistances.
With `a=1`, the original normal flow/power/thermal initialization is preserved:
lake `0.1 m3/s`, `150 kPa`, `21,428.5714286 W`; internal `0.12 m3/s`, `120 kPa`,
`19,200 W`. A fourfold V3 filter multiplier gives total lake K `51,000,000`,
not four times the independent valve term; the solved flow is
`0.05423261445466405 m3/s`.

## Heat allocation and separated inventories

This low-order model has no additional pipe-to-room thermal loss or exported
pressure work: all `q*dp` is dissipated into its corresponding fluid. The declared
fraction `f` of **total electrical pump power** enters that fluid; the remainder
enters the room. Thus, for every pump with actual positive hydraulic power,
`f>=eta` is required. It includes hydraulic dissipation once and can add some
motor/pump loss to the fluid. Hydraulic and valve-loss diagnostics are not extra
heat sources. An impossible active split fails even if a whole-facility total
energy account could otherwise pass.

This cross-parameter operating-domain check also applies to runnable V2. Its
default `f=1` and accepted normal trajectories are unchanged. A zero-head,
unpowered or interlocked pump has no hydraulic dissipation to constrain `f`;
later timed enabling is checked at the actual operating point. V1 remains a
structural interface. Old artifacts are preserved, not reattributed.

Lake pump heat raises the lake HX inlet enthalpy; internal pump heat enters its
hot finite volume. Plate-HX transfer uses the existing signed counterflow
epsilon/NTU model, with one transfer appearing at each side's enthalpy boundary.
Finite cold-volume temperature is distinct from HX outlet temperature. Either
side at zero flow gives zero flow-mediated HX transfer; zero internal flow also
sets condenser transfer to zero. Stored heat continues to evolve. The remaining
equations, frozen EOS and conservation tolerances are in
[the healthy-run model](healthy-run-model.md).

## Independent engineering examples

|Case|Independent expected result|
|---|---|
|100 kPa, passive K=6e8, Kopen=1e8, a=.5, eta=.5|Valve K=4e8, q=.01 m3/s, passive/valve drops 60/40 kPa, hydraulic/electric 1/2 kW|
|Same loop with 250 W supplied electrical limit|n=.5, q=.005 m3/s, 25 kPa head, passive/valve drops 15/10 kPa, hydraulic/electric 125/250 W|
|Two hand-case loops, rho=1000, cp=4000, UA=40 kW/K, Th=320 K, lake=300 K, eta=f=.5|C=40 kW/K per side, epsilon=.5, lake HX inlet=300.025 K, HX duty=399.5 kW, outlet ports=310.0125 K, external lake heat=400.5 kW|
|Internal shutoff at .25 s, sample period 1 s|Immediate pump/head/flow/heat-transfer zero; lake pump stays at .1 m3/s; low-flow trip at 1 s; 2 s demand retained, service deficit 1 s|
|Reopen internal valve at 1.25 s|Flow returns immediately, compute remains latched off until the valid 2 s sample; 3 s run has 1 s deficit|
|Lake shutoff, declared engineering trip/reset 306/305 K|Internal flow remains .12 m3/s; service initially continues, then stored heat reaches sampled thermal protection and stops compute|
|Imposed quarter lake head|q=.05 m3/s, electric power=2678.5714285714284 W, no assigned service penalty|
|Internal-valve engineering visit|Worker/tool/valve all at loc_hx; arrival 0 s and completion 30 s under existing qualified work rules|

The hand thermal case has both active pump efficiencies `.5`; `f=.5` therefore
includes exactly the hydraulic work and sends the other 1 kW per pump to the
room. Both distinct water flows are `10 kg/s`; the refrigerant and nuisance-water
mass inflows remain zero. The 400.5 kW lake boundary includes 399.5 kW HX heat
and the lake pump's 1 kW fluid allocation, with no second `q*dp` addition.

`tests/test_full_facility_water.py` verifies these public behaviors and invalid
states. `evidence/mainline/engineering/05-water/` retains numbered red/green
checks and every failure, each with execution command and source/input SHA-256.
The rejected first control graph and generator are preserved under check 06.
Check 16 records a fixture expectation mistake: the worker/tool were already at
`loc_hx`; check 17 corrects the expected 0/30 s arrival/completion after reading
their declared static locations. No plant code was changed to fit that mistake.

Accepted source-attributed runs and fresh-read receipts will be appended after
the implementation commit. These checks are finite engineering verification,
not M1 acceptance, a registered research comparison or a measured mechanism gain.
Step convergence, field calibration, richer control, interventions and parallel
reserve coverage remain their separate gates. No research/AI/training run is
started by this ticket; the complete research goal stays active.
