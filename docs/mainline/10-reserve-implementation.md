# Ticket 10 implementation revision 1

Started 2026-11-05 after accepted environment integration `98fd8c4b`; stable 09
interface `4619dbfd` is consumed but remains subject to root acceptance. The
preparation `10-reserve-design.md` is retained as historical design. This revision
resolves its startup-power circularity before physical integration or run capture.

- UPS internal detection/transfer control is a separate actor from the main PLC.
  It receives explicitly allocated AC when available; otherwise it draws positive
  control power directly from finite UPS energy, independently of the protected
  output switch. Its room heat and battery depletion are accounted once.
- Generator local detection/control and cranking have a separately declared,
  finite starter/control energy store. Allocated AC can supply the controller;
  during black start it uses that store. Cranking/control dissipation leaves at
  the generator's outside boundary. An empty starter store prevents black start
  even with ample main fuel. After connection, allocated AC can sustain control;
  empty starter energy then prevents a later restart, not an already self-powered
  running engine. Running/starting idle fuel is separately positive and finite.
- The main PLC can accept backup-cooling commands only at a real powered local
  sample. No unsupplied main controller issues a new command. An already accepted
  physical selector may hold; newly requested changes need a powered actor.
- UPS protection remains controller/internal pump/intake pump only. The fan is
  paid AC after essential auxiliaries and before room/IT. Shared distribution
  failure gates all delivered paths, while finite internal actor energy may still
  be consumed in unsuccessful attempts.

Public behavior seams are independently varying reserve transitions, the paid
heat-exchange/electrical budget boundaries, and the agreed scenario/run/CLI.
Tests use literal independent budgets. Engineering attempts use fresh directories
and retain red results; they are not research trials or scientific-gain evidence.

## Implemented profile and power paths

`configs/full-facility-mainline-reserve-v6.json` derives the control-v5 full
facility. It selects model `aegisdc-low-order-facility-reserve-v4` and implemented
profile `aegisdc-reserve-response-v1`, retaining `local_control_profile` and all
environment/water groups. Unknown profiles, wrong quantities/units, fractional
availability and zero nominal control/start/fan power fail. `delay_time` permits
declared zero connection delay; existing positive `time` quantities keep their
old contract. Air capacity rate is W/K, separately typed from conductance.

The new `load_distribution` asset has segregated normal/protected ports, one
explicit common availability condition, and a frozen new topology. Normal AC
pays UPS control, generator control, essential loads, fan, room and IT in that
order; protected UPS output still reaches only the original three auxiliaries.
Generator control/cranking are internal actors of `generator`, and its separate
starter store is an ideal DC research approximation. No battery chemistry,
as-built starter system, voltage transient or N+1 reliability is inferred.

Default research settings are UPS control100 W, generator control10 W, cranking
1000 W, starter100 kJ, idle fuel1000 W, UPS connection .2 s, generator connection
2 s after its existing30 s start, and cooling connection2 s. The fan is20 kW,
air capacity500 kW/K, UA300 kW/K and transport cap1.5 MW. Every value and range
is an explicit SI record; the real site's values remain unknown. The normal room
initialization adds100 W/Groom to the parent temperature for paid UPS control
heat. With mains present, both internal controllers receive allocated AC and
neither reserve store drains; no recharge is modeled.

```text
grid + generator + UPS_output + starter_output
    = sum(actual electric actors/loads) + rectifier_loss
UPS_depletion = protected_output/eta_UPS + UPS_internal_control_from_battery
starter_depletion = generator_control_from_starter + cranking_power
fuel_depletion = generator_output/eta_diesel + running_or_starting_idle_fuel
```

`UPS_output` includes its direct battery-fed internal control; the protected
output capacity applies to the external converter branch. UPS conversion loss
and total UPS control heat enter room once. Generator conversion/idle waste,
generator control/cranking and fan electric heat exit outside once. The latter
device heat is separate from engine conversion waste, even when the generator
electrically supplies it. Starter energy is included in whole-facility storage.

The generator's internal actor starts on its ideal local absent-mains record,
not an unpowered main PLC request. A positive AC rating is insufficient: actual
power must be allocated. A starter empty before connection prevents black start;
depletion wins over a simultaneous connection deadline. Once connected, actual
allocated AC can sustain the generator controller with empty starter energy,
but a subsequent restart still needs starter energy. A shared-distribution
failure can leave a running engine burning idle fuel without delivering power.
The first profile does not parallel-start a generator for a partial mains budget.

## Thermal coupling and ordering

Only one primary/reserve heat-rejection path uses the actual paid internal
circulation. Switching isolates primary removal; standby fan power/heat remains
zero until connection. The effective sensible exchanger uses actual fan fraction
to scale UA and external-air capacity rate and retains signed heat under reverse
temperature. It is not a real evaporative tower curve. No added water inventory,
evaporation, makeup or separate valve-work model is claimed.

Cold-water energy receives `-Q_primary-Q_backup`; hot-water energy retains the
accepted condenser/storage/pump/advection/**actual hot leakage** equation. Outside
energy receives `Q_backup + fan/control/cranking electric heat`, with no second
fan-heat addition. Floor mass/energy and leakage transfer retain 07's equations.

Timed inputs apply first. Independent UPS/generator transitions use actual actor
power, then the point is recalculated. The original 09 sample runs on its own
clock; only a powered sample accepts a new cooling request. The point is then
recomputed before 07's directional room-access and work processing. An active
selector can hold an already accepted position without a new request; interrupted
switching returns to its declared passive primary position. Maintenance resets
pending clocks; recovery requests start fresh delays. All observations remain
private plant/evaluator records, with no dispatch truth channel.

## Finite hand checks and evidence status

Twenty-four public component/run/CLI targets pass before saved-run capture.
They include 3.6326 MJ UPS energy with .2 s waiting and32.4 s of100 kW protected
output:3.24 MJ load +360 kJ conversion loss +32.6 kJ internal control, exhausted
at32.6 s. A full generator case takes3+2 s to connect, then delivers1110 W for10 s;
42750 J fuel gives11100 J AC and31650 J engine waste, with separate starter heat.
Maintenance, failed transfers, empty/exhausted starter, common distribution,
finite cooling cap/paid fan, reverse heat, 07 leak/floor energy and09 latching have
independent cases. Failed rejection with declared sensitive304.6/304.5 K thresholds
reaches service through actual coolant warming/protection; it is an engineering
negative, not a measured real safety limit or policy-effect result.

The whole-UPS hand fixture retained three preparation failures: an attempted zero
plate-HX UA outside its existing range, omitted accepted valve resistance, and
the parent's .92 efficiency instead of declared .9. Only fixture inputs were
corrected; the three logs remain and no physical rule/expected budget was tuned.
The clean-source runbook will separately freeze the accepted complete inputs.

Durable delivery is declared before hashing. Runtime caches are classified as
non-deliverable from the start, never skipped because a hash failed. Saved runs
will carry execution Git/source/input/property identities; a separate delivery
revision and its committed blobs must also pass portable fresh-checkout checks.
Research trials/training/model calls remain zero; M1 and the total goal stay open.
