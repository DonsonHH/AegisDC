# Explicit local-control measurement profile

Ticket 09 is in progress. This page describes the implemented interface, not
root acceptance, M1 completion, field calibration or method-effect evidence.
The research choices and primary conceptual sources are in
[the preparation record](09-control-design.md).

`configs/full-facility-mainline-control-v5.json` derives from the accepted
complete environment-v4 input. Its graphs and physical runtime model are
unchanged. `runtime.local_control_profile` explicitly selects
`aegisdc-local-control-faults-v1`. Missing/unsupported profiles do not silently
activate nonideal behavior. Without a profile the prior ideal sampling is kept.
Old V1-V4 input bytes and CLI defaults are preserved.

The five required source-tagged SI parameters are `local_temperature_bias`
(`temperature_offset`, K), `local_internal_flow_bias` (`volume_flow_offset`,
m3/s), `local_temperature_sensor_valid`, `local_internal_flow_sensor_valid`
and `supervisory_link_available` (dimensionless strictly binary states).
Only the two dedicated offset quantities permit negative bounds. Actual physical
flow, mass and absolute-temperature quantities retain their prior domains.
All five can be explicit, bounded source-tagged engineering events only when
this implemented profile is selected; changes are held until the local sample.

`local_control.sample_local_control(previous, parameters, measurement,
controller_power_W=...)` is the replaceable public transition boundary. It
consumes only a reported local temperature/flow, channel validity, current sample
time and supervisory connection state. It never receives the whole plant, future
fault labels or dispatch evidence. The existing plant sample clock adds declared
offsets to current actual quantities and delegates the transition. Biased reports
do not replace physical temperatures, flows or conservation accounts.

Invalid channels or physically impossible reports latch compute off and command
full pump speed. A new valid sample must meet thermal reset and sufficient-flow
gates before clearing that latch. Unpowered control commands the same fail-safe
outputs and preserves an existing latch; loss of power alone does not invent a
new thermal latch. Supervisory disconnection leaves valid local protection and
pump hysteresis autonomous. Reconnection cannot itself clear protection.
These are synthetic architecture rules, not certified safety behavior.

All returned measurements have `LOCAL_PLANT_ONLY` visibility. Reports and mode
records stay private to the evaluator; they create no perfect outward alarm,
operator notification or dispatch input. Invalid nonfinite reports serialize
nulls with validity/reason fields, never a clipped physically plausible value.

The environment/work-access ordering accepted in ticket 07 is retained:
actual post-control point before room-access update and work processing. Hot
leakage, changing water mass, mixed floor energy and independent gate semantics
are not replaced by the old fixed-inventory equations. `ENVIRONMENT_MODELS` and
`WATER_MODELS` keep their separate compatibility groups for later explicit
runtime variants; the control profile is independent of a particular topology.

Sixteen focused tests now pass, including signed-offset loading, static/timed
profile validation, exact sample-clock delay, biased reports masking real
conditions, invalid-channel recovery, autonomous protection during supervisory
loss, power-cycle latching, a literal hysteresis sequence, serialization of
impossible reports and actual CLI/source parity. Legacy environment physics
and interval accounts match the zero-error profile exactly in the comparator.
An unrepresentable integer report exposed an OverflowError; the retained red/green
corrects it to invalid-channel fail-safe without clipping the report.

The frozen engineering runbook is
`evidence/mainline/engineering/09-control/runbook-v1.json`: twelve predeclared
full-facility examples, including one actual CLI and combined hot leakage/control
interruption, with independent expected demand/delivery/deficit accounts. Source
freeze precedes its artifact execution and the single full regression.
Committed execution `363c5edf` produced twelve successful full-facility cases
(including actual CLI), six expected refusals and 74 freshly verified artifacts.
Normal 600 s has zero room/hot drift and zero deficit. Maximum step energy,
whole-run energy and water-mass residuals are respectively 3.3444e-6 J,
3.8147e-6 J and 2.9104e-12 kg. The combined leak/control case retains actual
hot mass/heat debit and evolving floor storage; reports never replace it.

The single author full regression discovers 263 /executes 261 checks, with no
failures/errors, exactly two prior optional isolated-Torch skips, no unexpected
skip and twenty old evidence hashes verified. See
[the evidence entry](../../evidence/mainline/engineering/09-control/README.md).
Independent review and root enabled-Torch acceptance remain pending.
No registered research, training or agent call is started by these checks.


The artifact audit uses the newer `verify_portable.py` / `portable-inventory-v2.json`
entry. The old 164-row v1 hash inventory is preserved as an author-local
observation: 162 committed persistent files plus two untracked interpreter-cache
hashes. It is not a 164-file checkout-delivery claim. V2 explicitly classifies
those two non-delivery rows, checks durable files and Git identities strictly,
and audits the unchanged 363c5edf execution without rerunning it. The physical
263-test regression and portable artifact gate are separate evidence.
