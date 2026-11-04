# Fixed-volume phase domain: ticket 06

The complete eight-domain synthetic facility retains ticket 03's pure-fluid,
fixed-volume homogeneous-equilibrium control volume. Ticket 06 verifies its heat,
phase inventory and condenser response and corrects a numerical endpoint refusal.
This is finite engineering verification within [the mainline](../MAINLINE.md),
not site calibration or a scheduling-effect result.

## Source and assumptions

|Kind|Declaration|
|---|---|
|Engineering reference|The Zhengzhou source pack motivates the equipment/condenser/internal-water path; it does not identify the site's refrigerant or these numerical settings.|
|Frozen numerical reference|CoolProp 8.0.0 / HEOS / R134a / DEF; the accepted 512-row table SHA is `9494001ac94e04c6b2474b1c70fdf78ff4b5958b3f5c39f9790581561097329c`.|
|Model assumptions|One pure substance, equilibrium, no noncondensable gas, no open refrigerant mass flow, fixed control volume; pressure range 0.1–3 MPa.|
|Synthetic settings|The v2 working point, masses, volumes, conductances, operating power and controlled perturbations are declared research inputs.|
|Unresolved site facts|Actual fluid/composition, gas contamination, boiling/pressure transients and field calibration remain unknown.|

The runtime consumes only frozen JSON. The offline
[author program](../../evidence/mainline/engineering/06-phase/create_eos_reference.py)
uses an explicitly supplied isolated EOS installation, never imports `aegis_dc`,
and refuses an existing output directory. It is not a runtime/test dependency.
The [new frozen reference](../../evidence/mainline/engineering/06-phase/eos-reference-01/direct-eos-reference.json)
records its script, extension, table, v2 input and previous reference-receipt
identities. The source/API are the official
[CoolProp API](https://coolprop.org/coolprop/HighLevelAPI.html) and
[R134a EOS page](https://coolprop.org/fluid_properties/fluids/R134a.html).

## State and shared interface

`SaturationTable.from_file` / `at_pressure` / `flash` are the public replaceable
property boundary. `simulate_scenario` executes the accepted v2 full-facility
scenario and exposes private evaluator trajectories and boundary accounts.
No dispatcher receives these states.

`M` is constant and `U` receives `Q_solid_to_refrigerant - Q_condenser`. The same
signed `Q_condenser` enters the internal-water hot volume once. Internal phase
redistribution does not add mass or a separate latent-heat source. The control
volume already includes the bath, vapor passage and refrigerant condenser side.
Water and refrigerant inventories remain distinct; `h=u+p*v` and `rho=1/v` are
derived from the same interpolated T/v/u primitives.

For the nominal working point, a 2 MJ heat addition increases pressure and vapor
inventory; removing 2 MJ reverses those changes. These signs are verified for
that declared state, not assumed universally for all filling ratios. Warm water
can return heat through a negative condenser transfer. Zero internal flow removes
this flow-mediated transfer while stored solid heat can continue into refrigerant.

The inverse enumerates every interpolation segment's possible roots, requires
`0 <= x <= 1`, and refuses absent/nonunique roots. Single-phase continuation,
mixtures and noncondensable gas are outside this model. A run that heats beyond
the pressure table fails before returning a successful trajectory.

## Endpoint correction and checks

The original quadratic inverse rounded some legal endpoint roots outside its
closed interpolation interval. Four of fourteen frozen EOS endpoint cases failed
at the accepted predecessor. The retained
[red/green logs](../../evidence/mainline/engineering/06-phase/red-endpoints-01/)
record the failure and correction.

The inverse now independently checks segment endpoints using their own T/v/u
rows. An endpoint candidate must already have a legal quality and reconstruct
specific energy within eight ulps of the reconstructed/target energy; its pressure
coordinate is the exact frozen endpoint. The existing general root residual
check remains in force. Quality and a physical out-of-domain root are never
clipped. A finite 0.1 J/kg energy excursion beyond the tested table endpoints is
still refused. This is a floating-point acceptance condition, not an extension
of the thermodynamic domain.

The public-interface suite verifies:

- Fourteen saturation endpoint states, including qualities 0, 1, `1e-10`,
  `1e-5`, 0.5 and their vapor-rich counterparts.
- Nine direct EOS density/internal-energy flashes at fixed M/V: signed heat at
  the v2 nominal state and liquid/vapor-rich initial states (x=0.001/0.99).
- Four external-EOS states intentionally outside the table/two-phase domain;
  finite endpoint excursions, zero/nonfinite/boolean inputs, and an explicitly
  labeled algebraic nonunique-root fixture.
- Full-facility positive/negative 2 MJ hand cases, reciprocal condenser/water
  energy, reverse transfer, stopped-flow stored heat, closed high/low filling,
  and a run that crosses the upper pressure boundary.

The nine direct EOS states use predeclared limits of `1e-5` relative pressure,
`0.0005 K` temperature and `5e-6` absolute quality. Alongside the previous 25
flashes and 543 off-grid probes, these are **finite numerical cross-checks of the
same EOS**. They are not independent empirical validation or evidence about the
real site's coolant. General step convergence and physical-domain qualification
remain their later tickets. M1 and the total research goal remain active gates.
