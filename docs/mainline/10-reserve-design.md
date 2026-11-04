# Ticket 10 preparation: finite reserves and a paid backup cooling boundary

Prepared 2026-11-04 at integration `81416154`; **design only, not implemented or
accepted**. Owner: `donson/mainline-10-reserve`, `.work/worktrees/full-site-10`.
Ticket 10 stays ready-for-agent until the implementation follow-up. No runtime,
scenario, test, progress or previous evidence file changes belong to this round.
The complete eight-domain objective and M1 gate remain open.

## Evidence and current starting point

- [CSCEC procurement announcement](https://www.cscec.com.cn/xwzx_new/zqydt_new/202508/3897038.html),
  published 2025-08-04, second body paragraph, freshly read 2026-11-04: the
  project scope includes UPS, diesel generators and a cooling-tower backup cold
  source. This is procurement/installation scope, not an as-built operating
  topology. Coverage, capacity, fuel/storage, switching and mutual-backup piping
  remain unprovided by this page.
- The [Zhengzhou source review](../research/20261104/source-review/zhengzhou-sugon8000.md)
  and [three-case pack](../research/20261104/facility-cases/README.md) retain those
  gaps. Frontier/El Capitan supply interface and boundary examples; their fluid,
  equipment counts and capacities do not become Zhengzhou inputs.
- [LBNL Buildings v13 heat-exchanger documentation](https://simulationresearch.lbl.gov/modelica/releases/v13.0.0/help/Buildings_Fluid_HeatExchangers.html)
  distinguishes sensible effectiveness/NTU models from moisture-transfer models.
  [Modelica fluid balances](https://build.openmodelica.org/Documentation/Modelica.Fluid.UsersGuide.ComponentDefinition.BalanceEquations.html)
  motivate matched mass/energy boundaries. These primary references were read
  2026-11-04; no library default is selected as a site parameter.

Accepted `power.py` /`plant.py` already have finite UPS/fuel inventories,
efficiencies, limited output, exact depletion splitting and a diesel start delay.
UPS protects only controller/internal pump/intake pump; generator output shares
the switchboard budget. The existing tower state is `standby_uncommanded`.
Maintenance, failed transfers and an active cooling boundary are not implemented.
UPS recharge, start/idle fuel and electrical waveforms are also outside that
accepted slice. Existing profiles and CLI defaults must retain their behavior.

## Proposed implementation assembly

Derive a separate `full-facility-mainline-reserve-v6.json` from the **accepted**
env-v4, or accepted control-v5 if 09 has landed. Do not fork/replace their energy
updates. A candidate `reserve_profile="aegisdc-reserve-response-v1"` is design
vocabulary only: validation must reject it until behavior and required quantities
are implemented together. Exact model/profile naming is frozen at implementation.

An active reserve needs physical heat/electrical edges, not only existing
`backup_tower -> internal_water` functional edge `f11`. Keep `backup_tower` as the
shared asset ID; propose its paid AC input, existing water heat-input interface,
and a heat-output port to a declared external-air boundary. Add matching control
relations and source-tagged parameter references. The new topology needs its own
validated digest and environment/water behavior membership. No fake liquid pipe,
air/water mixing or site P&ID is implied by this effective heat interface.

## Electrical paths, states and delays

Keep finite, named coverage. Proposed reserve-profile UPS coverage remains the
three accepted protected auxiliary loads; IT, room auxiliaries and the new fan
are not UPS loads. Grid/diesel may serve the fan through their paid shared AC
budget, ahead of IT according to an explicit profile priority. A declared common
downstream-distribution outage gates both ordinary and UPS-protected paths; it
does not disappear because UPS energy and generator fuel are still positive.
This common-cause mapping is a synthetic topology choice, not a site fact.

|Subsystem|Proposed states/rule|
|---|---|
|UPS|available/bypass, waiting-transfer, supplying, depleted, maintenance, transfer-failed. Output is zero until the transfer delay ends and coverage/power/energy gates pass.|
|Diesel|off, starting, ready-waiting-transfer, supplying, fuel-exhausted, maintenance, start/transfer-failed. Startup and connection delays are separate; readiness alone supplies no load.|
|Backup cooling|standby, switching, active, maintenance, transfer-failed. Heat transfer is zero before a successful connection, even when a functional path exists.|
|Maintenance/failure|Remove usable capacity immediately. Reset pending connection timers; leaving maintenance or restoring a failure flag requires a fresh accepted request, not an automatic stale completion.|
|Mains restoration|Cancel pending outage-only startup/connection requests. First profile uses no grid/generator parallel operation; minimum run/cooldown and recharge are separate future extensions.|

Clock origins are accepted physical/local commands, not hidden future faults.
Record the local mains/power indication or engineering request that initiated
each transition. A new request needs powered local control; supervisory loss
alone must not silently disable autonomous local protection. Initial draft
neglects separate actuator work and diesel start/idle fuel; this explicit
low-order assumption must remain visible, with no real endurance claim.

Split at transfer deadlines, maintenance/failure inputs and exact reserve
depletion. At equal time, apply unavailability before a scheduled connection.
Never serve an interval past depletion and then clip negative storage.

```text
dE_UPS/dt = -P_UPS_out / eta_UPS
UPS loss to room = P_UPS_out * (1/eta_UPS - 1)
dE_fuel/dt = -P_generator_out / eta_diesel
generator waste to outside = P_generator_out * (1/eta_diesel - 1)
```

Only usable output meets load requests. Both stores are inside the facility
energy inventory; neither discharge nor fuel conversion is another grid input.

## Proposed paid sensible cooling variant

First variant: an effective sensible water-to-external-air heat-rejection
boundary, not a prediction of the real evaporative tower. It has negligible
additional hold-up and exchanges no water mass. Actual tower evaporation,
makeup/blowdown, wet-bulb performance and physical piping remain site gaps.

Use existing paid internal circulation: `Cw=rho*cp*q_internal_actual` and hot-volume
`Th`. Select primary or reserve heat rejection mutually exclusively; do not give
both exchangers the full circulation twice. During switching there is no reserve
heat removal. Retain the existing aggregate hydraulic resistance as an explicit
matched-path approximation; a later distinct liquid path needs its own resistance
and mass-port account.

For active/available reserve, `f=P_fan_actual/P_fan_nominal` lies in [0,1]. A
provisional declared performance map uses `Ca=f*Ca_nominal`, `UA=f*UA_nominal`;
it is an effective map, not a measured fan curve. Use the existing counterflow
epsilon/NTU relation and a separate finite transport cap:

```text
Q_NTU = epsilon(UA,Cw,Ca) * min(Cw,Ca) * (Th - T_external)
Q_reserve = sign(Q_NTU) * min(abs(Q_NTU), Q_reserve_cap)
Q_to_external_air = Q_reserve + P_fan_actual
```

Zero water flow, zero actual fan power or disconnected/failed/maintenance mode
gives `Q_reserve=0`; a powered fan with stopped water still rejects its own paid
electric power outside. All fan work/loss goes to that external-air boundary
once, not also to room/water. The nominal external temperature can share the
declared outside-ambient boundary used by room heat rejection, retaining the
common hot-weather cause. Signed reverse heat is retained under a forced command;
control may subsequently isolate an unfavorable source at its own sample time.

For 07's actual dynamic inventory, retain its hot equation including leakage:

```text
dU_hot/dt  = Q_cond + P_storage + P_internal_pump_fluid - Q_circulation - Q_hot_leak
dU_cold/dt = Q_circulation - Q_primary_active - Q_reserve
```

Do not force the finite cold temperature to an HX outlet, remove heat from both
water volumes, add condenser/latent heat twice, or add reserve water as floor
makeup. The whole-facility external output gains only `Q_reserve+P_fan_actual`;
07's leaked-water transfer into floor inventory remains internal to that boundary.

## Draft parameters and domain

All selected values need SI quantity, valid range, basis/source note and explicit
initial state in the new profile. No unknown site value becomes a numerical zero.

|Group|Proposed declared domain|
|---|---|
|Existing stores/efficiencies/output limits|Retain J/W and current bounded efficiency ranges; initial inventories nonnegative, outputs bounded by inventory/coverage/usable capacity.|
|Transfer delays|UPS 0–30 s, generator connection 0–60 s, cooling connection 0–300 s; separate from existing diesel start time. These are proposed research bounds.|
|Availability/switch flags|UPS, diesel, cooling in-service and transfer-success flags, plus shared-distribution availability: exact numeric 0/1, not arbitrary fractions.|
|Cooling equipment|`P_fan_nominal>0` W, `Ca_nominal>0` W/K, `UA_nominal>=0` W/K, `Q_reserve_cap>=0` W; finite bounds selected before fixture execution.|
|Outside/flow domain|Existing accepted outside/water temperature and pump-flow ranges; Ca is an effective heat-capacity rate, not an invented evaporative-water flow.|

## Independent acceptance proposal: not executed

Use the agreed scenario/run/CLI seams, one behavior slice at a time. A separately
varying reserve transition/HX component boundary is justified only if needed;
do not test private plant methods. Freeze inputs, expectations and fresh output
names before execution, retain actual failures, then run one full regression.
The store examples assume a fixed delivered load and no other source during the
stated outage. HX energy totals below are constant-port component hand budgets;
the finite facility temperatures must evolve rather than being held to those
ports for a 20 s trajectory.

|Hand case|Independent expected outcome|
|---|---|
|UPS 3.6 MJ, eta .9, protected 100 kW|32.4 s of output after connection, 3.24 MJ delivered and .36 MJ room loss. With .2 s connection delay, depletion is at 32.6 s measured from request; unprotected IT remains unserved.|
|Diesel request at 0, 3 s start +2 s connection; 2.5 MJ fuel, eta .4, 100 kW output|No output before 5 s; then 10 s output, 1 MJ electricity and 1.5 MJ outside waste, exhaustion at 15 s under the declared zero start/idle-fuel approximation.|
|Maintenance/failed transfer/shared bus|Positive inventories and multiple devices do not supply through an unavailable path. Same-time failure wins over connection; restoration requires a fresh request.|
|Paid HX: Cw=4 kW/K, Ca=8 kW/K, Th=320 K, Text=300 K, UA=8000*ln(1.5) W/K, fan=2 kW|epsilon=.5, water heat=40 kW, water outlet 310 K, air HX outlet 305 K and post-fan 305.25 K. Over 20 s at those fixed ports: water -800 kJ, grid fan +40 kJ, outside +840 kJ.|
|Same HX with 30 kW transport cap|Water heat 30 kW, water outlet 312.5 K, post-fan air 304 K; no full-capacity cold sink.|
|No fan /no water /warm sink|Zero power or zero flow removes coolant heat transfer; powered stopped-flow fan heat still exits once. At Th=290 K /Text=300 K otherwise identical, Q=-20 kW and outside=-18 kW; no absolute-value cooling trick.|
|Request .25 s, 2 s cooling connection delay|No reserve Q before 2.25 s. After connection, actual paid power, flow, UA/cap and temperature govern Q; availability labels alone prove no rescue.|
|Same-facility coupling|Retain external service demand, 07 hot-leak/floor-energy/access accounts and 09 local latches. Limited reserve can fail to prevent service loss; such an engineering negative is retained.|

## Compatibility and pending decisions

07's owner reports frozen candidate source `ab6094bf`, assembled with 08 at
`5ca3c3a0`; root review/acceptance is still pending. The communicated fields are
`self.hot_mass`, changing hot
capacity, `hot_leak_kg_s/hot_leak_heat_W`, actual `floor_energy` and integrated
drain energy. Cold mass remains fixed; coolant makeup is not implemented and
condensation is only a private risk criterion. Its `minimum_internal_hot_mass`,
`it_access_permit` and `maximum_room_work_temperature` guards and post-control
room-access/event ordering must survive the reserve extension. Review the final
accepted `environment-verification.md` and source before coding; this preparation
does not establish acceptance of that candidate or copy its older hot/floor formulas.

09 preparation at `27889c30` proposes `local_control_profile` and control-v5 on
env-v4. It is not implemented; 07 currently rejects that field. Keep local
measurement/thermal/sensor latches distinct from reserve modes, preserve 08's
service-capacity events, and add no dispatch truth channel. Coordinate the
profile/model-membership and new topology digest after 07/09 acceptance.

Pending implementation freeze: exact profile names/parameter bounds, physical
power priority and shared-bus mapping, command cancellation/retry semantics and
whether neglected start/actuator energy needs a separately bounded term. Do not
add recharge, real evaporative-tower internals, arbitrary pump parallelism or an
N+1 availability probability without an independently specified new scope.
