# Joint-service accounting: ticket 08

The accepted complete synthetic facility already computes one joint service from
compute, network and storage execution. Ticket 08 retains those accounts and
allows timed changes to the three existing component service-capacity parameters.
The [fixed objective and gates](../MAINLINE.md) remain active; this is finite
engineering verification, with no strategy comparison or scientific-gain claim.

## Quantities and model assumptions

|Quantity|Meaning and unit|
|---|---|
|`service_demand`|Exogenous offered-service rate divided by the declared synthetic reference rate; dimensionless `1`.|
|`*_service_capacity`|Each required component's available ceiling in the same normalized service-rate units; dimensionless `1`, existing range [0,2].|
|`it_service.capacities`|Effective capacity at the current execution/power point: the smaller of the declared ceiling and actual component power divided by its explicit nominal coefficient.|
|`*_nominal_power`|Assumed W per unit normalized service-rate multiplier. These coefficients are research inputs, not measured workload curves.|
|`*_demand_power`|Requested execution power per normalized workload multiplier; an explicit engineering throttle/pause can change this request while external service demand remains fixed.|
|`demand_service_unit_s`, `delivered_service_unit_s`|Separate time integrals of requested and delivered normalized service rate; normalized service-unit seconds. They are not job counts.|
|`service_deficit_time_s`|Time integral of the unserved fraction of positive offered demand, in s. Zero-demand intervals contribute zero.|

The reference service has no calibrated absolute throughput. These quantities
are not FLOP/s, network bit/s or storage IOPS; none is inferred from MW. The
coefficient linking actual power to normalized execution is an explicit low-order
research assumption. Power/heat uses actual supplied execution. The linear model
does not resolve component idle power or real failure power signatures.

At each operating point the delivered rate is the minimum of offered demand and
the three effective component capacities. Unserved rate is offered minus
delivered. A required component can stop the joint service while the other two
remain fully powered. Overlapping component losses belong to one service and
are not added once per failed component.

Requested and delivered integrals remain separate. Their difference is unserved
normalized work. The normalized deficit-time account uses each interval's demand
as its denominator; it cannot in general be reconstructed by dividing total
unserved work by one horizon-wide demand value when demand changes.

## Timed engineering boundary

The public `simulate_scenario` and `python -m aegis_dc simulate --inputs` contract
now permits `compute_service_capacity`, `network_service_capacity` and
`storage_service_capacity` events, using the existing four fields:

```json
{"time_s": 0.25, "parameter_id": "network_service_capacity", "value": 0.6,
 "source_note": "Synthetic declared normalized-capacity reduction; not a site event."}
```

Values stay inside the original parameter's range and must be finite numbers.
Each event needs a nonempty source note and a valid time; conflicting assignments
to the same parameter/time are rejected. Nominal calibration coefficients remain
static. The integrator splits at event times, including fractional seconds, and
retains all source-tagged inputs in the private evaluator run manifest.

These events specify an externally imposed effective capacity ceiling. Separate
execution-request events are labeled throttling/pausing; reduced requested power
is not used as evidence that hardware failed. Neither kind of event changes
`service_demand`. An explicit `service_demand` event represents a change in offered
demand and must be held fixed across future method comparisons.

No job queue or scheduler is introduced here. During an execution pause, the
unchanged offered demand continues to accrue. Restoration resumes current
delivery; it does not erase the recorded past deficit or invent completed work.
Task arrivals/deadlines, backlog/catch-up policies and multiple service classes
belong to later modeling and policy work.

## Independent hand cases

The [frozen engineering cases](../../evidence/mainline/engineering/08-service/hand-cases-v1.json)
contain literal expected accounts, declared before artifact capture. Eight tests
exercise the public full-facility run and CLI, using the accepted scenario.

|Case|Requested / delivered normalized service-unit s|Deficit time|
|---|---|---|
|Compute at half ceiling for 1 s of a 2 s run|2 /1.5|0.5 s|
|Network 0.6 from .25–1.25 s, storage 0.4 from .75–1.75 s|2 /1.2|0.8 s; individual .4+.6 s losses overlap|
|Any single required component unavailable for 1 s|2 /1|1 s|
|Zero demand for 1 s, then demand 1 with network ceiling .25|1 /.25|.75 s|
|Demand .5 then 2 for 1 s each, network ceiling .25|2.5 /.5|1.375 s|
|Execution paused for 1 s in a 3 s run|3 /2|1 s remains after restoration|
|Execution requested at half nominal for 1 s in a 3 s run|3 /2.5|.5 s remains after restoration|
|Zero demand throughout|0 /0|0 s|

The event boundary was initially absent: the first timed-capacity test failed
with an unsupported-exogenous-parameter error. Adding the three names to the
existing allowlist makes it pass; the existing joint-minimum and integration
logic already passed the remaining independent hand cases. The retained
[red/green record](../../evidence/mainline/engineering/08-service/red-green.md)
distinguishes the corrected behavior from behavior accepted unchanged.

The evidence establishes finite accounting and replay behavior in the same eight
domains. It does not establish field calibration, FLOP/s capability, a workload
queue model, method benefit or M1/full-research completion. Plant/evaluator state
remains private and no dispatch adapter is added.
