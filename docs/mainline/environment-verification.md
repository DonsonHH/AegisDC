# Environment, leakage and work-access engineering model

Ticket 07 extends the same eight-domain Zhengzhou-inspired **synthetic research
facility**. The new leakage path, inventory limit, access permission and room
work threshold are declared research choices, not as-built site facts or
occupational limits. The complete objective remains in [MAINLINE](../MAINLINE.md).
This is finite engineering verification, not a research comparison or gain.

## Public interfaces and profile

`configs/full-facility-mainline-environment-v4.json` derives from water-v3, without
modifying V1/V2/V3, their source facts/property data or the CLI defaults. It keeps
the scenario-v2 schema and engineering-inputs-v1 CLI contract. The explicit
runtime is `aegisdc-low-order-facility-environment-v3`, with topology digest
`16a1b495731abf52140c921e2dfd185e19cde6493b9f57e504965c9b82c755e4`.
It inherits both paid valve/pump branches through `WATER_MODELS`. Unsupported
graphs fail; there is no generic topology inference.

```python
from aegis_dc.scenario import load_scenario
from aegis_dc.plant import simulate_scenario, save_run

scenario = load_scenario("configs/full-facility-mainline-environment-v4.json")
result = simulate_scenario(scenario, duration_s=10, boundary_events=[
    {"time_s": 0.25, "parameter_id": "internal_hot_leak_mass_flow", "value": 0.2,
     "source_note": "Imposed actual hot-water leakage engineering case."},
])
save_run(result, "outputs/engineering/a-new-environment-run")
```

The same model works with `python -m aegis_dc simulate --model CONFIG --inputs
INPUTS --output NEWDIR`. The replaceable component boundaries are
`aegis_dc.environment.floor_water_step` and `condensation_risk`. Facility tests
use the scenario/run interfaces and CLI, not private plant state access.

All returned trajectories remain `PRIVATE_PLANT_EVALUATOR_ONLY`. No dispatcher
observation, warning, perfect diagnosis, human repair or authorization action is
created by this ticket. Runtime still has exactly its five supported fields;
unimplemented `local_control_profile` declarations are rejected. Later control
profiles must explicitly implement and validate their behavior.

## Declared parameters and defaults

|Parameter|SI unit|Default|Meaning|
|---|---|---:|---|
|`internal_hot_leak_mass_flow`|kg/s|0|Imposed actual withdrawal from well-mixed hot internal water to the floor pool|
|`minimum_internal_hot_mass`|kg|9000|Lower inventory validity boundary for the constant hydraulic model|
|`it_access_permit`|1|1|Strict binary gate permission; zero forbids IT-zone work|
|`maximum_room_work_temperature`|K|313.15|Synthetic work-permission threshold, not a site/occupational limit|

New environment-only timed inputs are the leak rate, binary permission,
`room_ambient_temperature`, `room_conductance` and `room_humidity`. They require
the explicit environment runtime. Existing nuisance-water and drainage inputs
continue to work. Events preserve source note/time/range checks and split the
integration interval. A value .5 is not a valid partial access permission.

Zero leakage/empty floor/open gate preserve the healthy water-v3 working point.
The unchanged normal room sensible balance remains actual network/controller/
room auxiliary heat, conversion losses, allocated motor heat and solid-to-air
heat, minus its declared effective ambient rejection. Liquid/condenser/HX heat
is separately accounted; room auxiliary power is not free refrigeration.

## Actual hot-water transfer and finite inventory

`internal_hot_mass` is now the initial condition for this profile, not a fixed
runtime mass. Actual state is `self.hot_mass`; hot capacity is `Mhot*cp`.
Cold-water, refrigerant and lake identities remain separate. The explicit
physical edge `w_hot_leak_to_floor` connects the hot-water port to drainage's
internal-water inlet. Its placement is a synthetic aggregate leakage path into
the IT-zone floor pool, not an inferred real piping layout.

For imposed leak rate L, hot sensible energy uses the existing zero-K reference:

```text
dMhot/dt = -L
dUhot/dt = Qcondenser + Pstorage + Pinternal_pump_fluid
            - Ci*(Th-Tc) - L*cp*Th
C_hot(t) = Mhot(t)*cp
```

The leaked mass and `L*cp*Th` enter the floor pool **once**, as an internal
transfer, not an external source or refrigerant loss. With no other heat, the
same-temperature withdrawal removes proportional mass and energy, so remaining
hot temperature does not fall. Pressure/kinetic/elevation energy is outside this
bounded incompressible sensible model. L is an exogenous physical input, not a
hole/pressure constitutive law or a fault label that directly changes service.

Normal pump/flow behavior is applicable only at or above the declared minimum
remaining hot inventory. A step splits at that boundary; continuing a positive
loss below it fails explicitly. No mass/quality clipping, invented suction
geometry, cavitation extrapolation or unaccounted makeup is used. This ticket
does not model cooling-water replenishment, refrigerant leakage or flood damage.

## Distinct nuisance source, mixed floor pool and drainage

The original `floor_water_inflow` is still **external ambient-temperature
nuisance water**, not coolant leakage or makeup. The initial floor inventory is
also at the declared initial ambient temperature. In environment-v4, the floor
pool stores its own mass and sensible energy instead of being forced back to
ambient after mixing or ambient changes.

The two incoming sensible streams have total mass I and power Pin; drain D takes
the pool's evolving temperature. The pool is adiabatic and well mixed, with the
same declared constant cp. No evaporation, latent heat, contamination, geometry
or floor-to-room heat-transfer coefficient is invented.

```text
dMfloor/dt = I - D
dEfloor/dt = Pin - D*cp*Tfloor
I = nuisance_inflow + hot_leak
Pin = nuisance_inflow*cp*Tambient + L*cp*Th
```

`floor_water_step` integrates this well-mixed tank analytically within each held
plant interval. For positive initial mass, with A=I-D and positive final mass:
`T1=Tin+(T0-Tin)*(M0/M1)^(I/A)` when A is nonzero; the equal-in/out limit is
`T1=Tin+(T0-Tin)*exp(-I*dt/M0)`. Empty filling, pure withdrawal, exact empty and
zero-drain boundaries are explicit branches. A run splits at empty inventory.

Drain energy is integrated directly with `expm1`, rather than subtracting large
stored energies to recover a small flux. Exact D=0 gives exactly zero exported
mass/energy. The independent root probe found 49 valid zero-drain refusals in
108 checks; the JSON and real red are preserved, followed by 49 successful
replays. A mixed `1e-16 kg/s` drain matches a separately computed 70-digit
Decimal analytic reference. No arbitrary negative heat is clipped.

Per-medium accounts include hot/cold/refrigerant/lake/floor and an independent
whole-water boundary. `internal_hot_leaked_mass_kg` and
`internal_hot_leak_energy_J` are internal transfers; existing
`floor_water_inlet_mass_kg` and `floor_inlet_energy_J` remain external nuisance
inputs. Drain heat leaves the facility; hot-to-floor heat does not appear again
as external energy. Floor temperature is null only when its inventory is empty.

## Condensation boundary without moisture production

The criterion compares `RH*psat(Tair)` with `psat(Tsurface)`. Saturation at or
below the air vapor partial pressure flags a boundary risk. The liquid-water SI
coefficients were verified against the official
[PsychroLib 2.5.0 source](https://raw.githubusercontent.com/psychrometrics/psychrolib/2.5.0/src/c/psychrolib.c),
which identifies ASHRAE 2017 Fundamentals chapter 1 equations 6/22; source SHA-256
and the independent 25 C /80% RH /21.309397163661785 C dewpoint example are in
`primary-source-receipt.json`. The surface/dewpoint meaning is consistent with
the [Met Office description](https://weather.metoffice.gov.uk/learn-about/weather/types-of-weather/temperature/dew).

This model deliberately supports only liquid-water criterion temperatures
273.16–333.15 K and RH in [0,1], with no clipping or ice/extrapolation branch.
Cold-buffer bulk temperature is an explicitly labeled proxy for an exposed
surface, with no wall/insulation model. Prescribed RH is a diagnostic boundary,
not an evolving air-water inventory. The output says
`BOUNDARY_RISK_ONLY_NO_CONDENSATE_OR_LATENT_HEAT`; it creates neither floor water
nor latent heat and is not dispatched as an instantaneous perfect alarm.

## Independent access, permission and unsafe work

`it_access_gate` is an identifiable asset/inspection target with a functional
access condition. Gate permission, floor-water threshold and room work
temperature can each block `loc_it`. Worker paths and access qualifications come
only from the existing independent access graph, never the cable/fluid graph.
Tools, worker occupancy, specialty and shift constraints remain enforced.

Room thermal access uses actual sensible temperature after local control and its
actual right-hand heat rate. Rising threshold crossing closes work, falling
crossing opens it. At equality, falling is open, rising is closed and stationary
initial equality is closed. Steps split at crossings; canonical event-coordinate
roundoff is explicit and remains in the energy residual. Thus a 1 MJ/K room
with 100 kW sensible input and .15 K headroom stops work at 1.5 s, not at the end
of an extra numeric step. A protection action that removes compute/rectifier
heat is evaluated before equality permission and equal-time work requests.

Already active work stops at the changed condition and retains actual arrival,
spent work/travel time and carried-tool location. The worker is not teleported
out of the blocked room. Coarse travel continues to its declared destination
gate, which is checked before entry; a closed gate aborts there with the last
safe discrete location and elapsed traversal retained. The model does not claim
continuous path geometry, emergency evacuation or retroactive travel erasure.

## Independent examples and remaining gates

The public tests include 1000 kg at 320 K losing 4 kg/5.12 MJ without changing
remaining temperature; 399.5 kW water/HX behavior remains in ticket 05. Floor
mixing cases give 315 K /12.4 MJ drained at variable mass and
312.64241117657116 K /1.2294303552937155 GJ drained at constant mass. Actual
2 kg/s leakage against .1 kg/s drainage reaches the 10 kg access threshold at
100/19 s and aborts existing work, with no nuisance-source mass invented.

Implementation is `ab6094bf`; accepted service integration is merged at run source
`5ca3c3a03d05802458cef1bdd10e66928d75bc1b`. Nine successful engineering runs,
one expected inventory-domain failure, and a separate CLI output are retained at
`evidence/mainline/engineering/07-environment/`, with complete runbook/attempt
ledger, actual source identities and fresh hash/count/mass/energy receipts.
Normal 600 s has zero room/hot drift and zero deficit. Successful fixture maximum
fresh interval energy residual is below `3.70e-6 J`, water mass residual below
`2.55e-12 kg`, and floor heat residual below `8.42e-9 J`; CLI fresh checks also pass.

`acceptance-5ca3c3a0/summary.json` records engineering/evidence/overall PASS:
247 discovered /245 executed, no failures/errors, exactly two pre-existing
optional isolated-Torch skips, no unexpected skips and 20 original-file hashes
valid. All 22 environment tests execute without skips. Root owns enabled-Torch
coverage, independent Standards/Spec review and integration acceptance.

All source facts, original failures and earlier artifacts are retained.
These engineering checks do not establish step convergence, field calibration,
inspection quality, interventions, policy benefit or M1/full-goal completion.
The later control and reserve profiles must consume these dynamic inventories
and heat accounts rather than overwrite them with old fixed-mass formulas.
