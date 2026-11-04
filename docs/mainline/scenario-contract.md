# Full-facility scenario contract

Ticket 02 defines a structural input for the complete research facility. The public loader checks the source-declared contract; it does not execute the eight domain behaviors, validate a physical trajectory, or establish research gains.

```bash
python -m aegis_dc scenario
python -m aegis_dc scenario --model configs/full-facility-mainline-v1.json
```

The default [configuration](../../configs/full-facility-mainline-v1.json) is Zhengzhou-inspired and explicitly synthetic: 8 domain contracts, 38 shared entities, 38 individually bounded SI parameters, four relation views, four professional executors and unresolved site-data gaps. Counts are research configuration choices, not equipment/personnel counts from Zhengzhou.

The Python interface is small:

```python
from aegis_dc.scenario import load_scenario, describe_scenario

scenario = load_scenario("configs/full-facility-mainline-v1.json")
summary = describe_scenario(scenario)
parameters = {record["id"]: record["value"] for record in scenario["parameters"]}
```

`load_scenario(path)` reads strict JSON and returns the validated dictionary. Contract violations raise `ValueError`; file-read errors remain `OSError`. `describe_scenario(scenario)` expects the validated loader result and returns source/parameter/entity/relation records with status `STRUCTURE_DEFINED_NOT_SIMULATED`. Callers that edit a scenario must validate the edited file again before describing or consuming it.

## Records and units

- Each domain declares states, inputs, outputs, behaviors, service/work effect and a qualified work interface. These are declarations at this stage, not proof that the corresponding code has run.
- Entities have one domain and one shared ID, a role, source scope, optional location, physical ports and parameter references. Worker specialties/qualifications, compatible tool references and work targets/durations are checked.
- Active parameters carry `quantity`, canonical SI `unit`, finite numeric `value`, `valid_range`, `basis`, source references and a source note. Boolean/nonfinite/unknown values and wrong units cannot stand in for numbers. The quantity vocabulary is deliberately limited to this facility contract.
- Unresolved real-site data stay in `site_gaps` with `value: null`. They cannot shadow an active parameter or become zero-valued model input.
- Source references are checked for metadata and referential integrity, not independently certified by the loader. Numerical ranges are explicitly research choices unless a reference basis is declared.

## Four relation views

Physical edges connect an output asset port to an input asset port with equal carrier and medium identity. Electric ports also require compatible nominal voltage parameters; conversion is represented by an asset with different input/output ports. Lake and internal-water fluid identities remain separate; an intervening heat edge carries energy, not mass.

Functional edges describe required/capacity/backup/control-permit or access-condition roles. They declare dependencies; they do not compute failure probabilities, redundancy availability or service loss. Control/information edges connect measurement targets, record points and local command assets. Access edges connect only location identities, with positive SI time parameters and optional qualification gates.

## Remaining implementation

The output keeps `dynamic_model_executed: false`, `field_calibration: PENDING` and `research_gain_claim: NOT_ESTABLISHED`. Individual parameter ranges do not prove coupled initialization, phase EOS consistency, stability, conservation, reserve coverage or work feasibility. Those behaviors remain the explicit successors of [ticket 02](../../.scratch/full-facility-mainline/issues/02-scenario-contract.md); this structural contract does not complete milestone M1.
