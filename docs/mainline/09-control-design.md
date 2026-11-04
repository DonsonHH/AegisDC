# Ticket 09 preparation: local control and faulty measurements

Prepared 2026-11-04 at base `e12a2d76`; **design only, not implemented or accepted**.
Owner: `donson/mainline-09-control`, `.work/worktrees/full-site-09`.
The eight-domain [mainline](../MAINLINE.md), accepted ADRs and ticket 09 remain the
contract. M1, effect research, field calibration and the total goal stay open.

## Current implementation and boundaries

The accepted plant samples local refrigerant temperature and internal volume flow
at an independently split `control_sample_time`. It trips compute for temperature
at/above `protection_temperature` or flow below `minimum_internal_volume_flow`.
Only temperature at/below `protection_reset_temperature` plus adequate flow clears
the existing latch. Controller power loss presently removes compute permission,
commands full pump speed and preserves the latch. Pump temperature control has a
two-threshold hold band and commands only 1 or `pump_min_speed`.

Current accepted V3 settings are explicitly synthetic: 340/330 K trip/reset,
303.15 K cooling setpoint, 2 K hysteresis, 1 s sampling, 0.01 m3/s minimum internal
flow, and 0.5 minimum pump command. They are not inferred real site thresholds.
Existing measurements are ideal and carry `LOCAL_PLANT_ONLY` visibility. There is
no supervisory outage input or sensor validity/bias behavior yet. A source
inspection is not execution evidence for the proposed behavior.

## Primary references and modeling choices

- [EPICS Base Analog Input Record](https://docs.epics-controls.org/projects/base/en/latest/aiRecord.html),
  read 2026-11-04: engineering-unit conversion/offset, explicit undefined-value
  status, configured limits and hysteresis, and evaluation during processing are
  real examples of distinct measurement and limit-state semantics. This source
  supports those concepts, not this plant's equipment settings or a safety claim.
- [NIST SP 800-82 Rev. 3](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-82r3.pdf),
  section 5.3.1, printed p.79 / PDF p.96, read 2026-11-04: failure responses and
  tolerable disrupted operation should be defined for the process. Loss of network
  communication can be a trigger, but the source does not prescribe the exact
  response selected here. This is the 2023 revision, not a claim about the latest
  draft or site compliance.

The following deterministic bias model, independent supervisory connection and
fail-safe rules are **research assumptions**. They model neither an EPICS
installation nor a certified safety controller. Random noise, sensor acquisition
latency, common-source evidence and delayed dispatch belong to later tickets.

## Agreed integration seam with ticket 07

Ticket 07's owner confirmed on 2026-11-04 that `local_control_profile` is the agreed
runtime field name. After env-v4 is integrated and accepted, derive an independent
`configs/full-facility-mainline-control-v5.json` from that accepted full facility.
Use its unchanged physical/control/access graphs and `ENVIRONMENT_MODEL`; no new
physical topology is needed for this measurement/logic variant. Keep its
`WATER_MODELS` membership and `ENVIRONMENT_QUANTITIES` intact.

The optional closed runtime extension would be:

```json
"local_control_profile": "aegisdc-local-control-faults-v1"
```

**It must not be accepted before the nonideal behavior actually exists.** If 07
adds any schema hook earlier, unknown/nonimplemented profile values must explicitly
fail; the hook must not silently fall back to ideal measurements. Until 09 lands,
this design does not authorize modifying 07's current five-field runtime contract.
09 will add strict profile/parameter validation and actual behavior together.

No profile means the accepted ideal sampling behavior. V1/V2/V3 source inputs,
CLI defaults, old raw trajectories and accepted property data remain unchanged.
Profile support is an explicit behavior selection, not a hidden numerical default.

Proposed required profile parameters (each with source_refs, source_note, basis,
SI unit and valid_range in the new config):

|ID|Quantity/unit|Initial value|Proposed finite research range|
|---|---|---:|---|
|local_temperature_bias|temperature_difference / K|0|-50 to 50|
|local_internal_flow_bias|volume_flow / m3/s|0|-0.2 to 0.2|
|local_temperature_sensor_valid|fraction / 1|1|0 or 1 only|
|local_internal_flow_sensor_valid|fraction / 1|1|0 or 1 only|
|supervisory_link_available|fraction / 1|1|0 or 1 only|

These are draft bounded experimental inputs, not calibrated error distributions.
Allow timed changes only under the implemented profile and the normal provenance,
range and split-event rules. A fractional flag such as 0.5 must be rejected even
though it lies numerically between 0 and 1. Missing profile parameters are errors.

## Public component and plant responsibilities

Introduce one replaceable public local-control transition boundary in
`aegis_dc.local_control`: previous control state, current local measurement record,
existing settings, supplied controller power, sample time and supervisory status
produce the next control state. It receives no future state, fault label or
plant-wide evaluator object. Exact function naming can follow implementation.

The plant constructs the current biased local measurement only at its actual
sample time, calls the component at the existing `sample_control` integration
point and retains the current event-splitting clock. Biased reported values are
not substituted into true temperatures, flows, energy or mass accounts. Invalid
channels serialize a validity reason/null as appropriate, never NaN. An impossible
reported absolute temperature or negative reported flow is invalid, not clipped
into a plausible observation. Command saturation is already the declared bounded
pump-command range [pump_min_speed, 1].

All local measurements, validity states and controller modes remain private
plant/evaluator records with `LOCAL_PLANT_ONLY` scope. Supervisory link recovery
is not a dispatch observation or perfect alarm delivery. Later evidence tickets
must implement any timestamped/quality-limited outward records separately.

Priority and recovery proposal for the nonideal profile:

1. Insufficient controller supply: compute prohibited, full pump command; retain
   an existing protection latch. Power failure alone does not create a new thermal
   latch, preserving the accepted ideal-controller rule; any existing latch still
   requires a fresh valid reset sample. Sensor invalidity has its separate
   explicitly latched behavior below.
2. Invalid temperature or flow channel: compute prohibited, full pump command,
   sensor-failure latch set. A later fresh valid sample must satisfy temperature
   reset and adequate flow before clearing it; restoring a validity bit alone
   between samples does not restore compute.
3. Valid powered local sample: same trip/reset gates and pump hold-band rules as
   above. High/low equality semantics are retained. Status records whether the
   supervisory channel is connected; a disconnected channel does not disable
   the local measurement, protection or pump loop.
4. Reconnection alone does not override a thermal/sensor latch. Autonomous
   operation under a disconnected supervisory link is a declared synthetic
   architecture, not a claim that all communication failures are harmless.

Do not touch 07's hot-water leakage, floor-water mixing, environmental energy,
minimum-inventory or access rules. Do not preempt 08's service-capacity inputs.
Do not add risk policies, intervention permissions or outward evidence to 09.

## Proposed public run/CLI acceptance slices

The already approved test seams are the loader, public facility run and CLI;
the new component boundary is justified by this independently varying logic.
Implement one red/green behavior slice at a time, preserving attempted commands,
inputs, raw failures and subsequent fixes in new directories.

- Independent comparator: zero-bias/valid/connected control-v5 normal run remains
  stable, with eight domains and a private local measurement. Legacy ideal
  configurations continue to load and execute unchanged.
- High bias: initial true refrigerant temperature is about 304.48 K; a declared
  +40 K report crosses the existing 340 K trip at the first sample. Actual compute
  power becomes zero; exogenous demand remains. True state does not jump by 40 K.
- Masked low flow: a declared positive flow bias can make stopped real flow look
  adequate, changing compute permission while the true hydraulic/heat-transfer
  state remains stopped. A brief finite scenario demonstrates the distinction;
  it is a defective-control engineering case, not a policy safety success.
- Invalid channel at 0.25 s, valid again at 1.25 s, sample period 1 s: fail-safe
  begins at 1 s and fresh valid reset can occur at 2 s. A 3 s normal thermal case
  has exactly 1 service-deficit second. Between-sample flags cannot change held
  controller state.
- Supervisory loss/restoration while local sensors remain valid: prove continued
  automatic temperature/low-flow response without a work request or dispatch
  message. Add an abnormal local input during the lost-link interval so the test
  proves an active loop rather than an unchanged label.
- Hysteresis/latching: demonstrate hold within the temperature deadband, valid
  low/high changes, command bounds, equality cases, and the existing power-cycle
  regression. Neither power nor link restoration may erase a held protection.
- Rejection: unknown profile, missing quantities, wrong SI unit, nonfinite bias,
  fractional availability, and a profile event applied to legacy config fail
  explicitly. Unsupported graph changes still fail.
- Full-facility saved runs and one actual CLI: verify hashes/counts, actual code/
  input/property identities and mass/energy/capacity residuals from fresh reads.
  Work outputs remain engineering records; model/training/research counters stay
  zero. Do not overwrite previous outputs or use old result names as fresh proof.

The exact engineering runbook should be frozen before its acceptance execution.
Full regression is run once after behavior slices; root performs enabled-Torch
integration acceptance and independent review. No M1 or scientific gain claim
follows from this preparation file or a passing controller unit test.
