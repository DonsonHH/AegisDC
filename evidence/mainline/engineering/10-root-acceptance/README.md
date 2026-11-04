# Finite reserve engineering acceptance

Ticket 10 makes reserve availability depend on actual power, stored energy,
connection, maintenance, timing and common distribution. The UPS internal
controller, generator starter/control and main PLC have separate supply rules.
An unpowered main PLC cannot issue a new cooling command; positive fuel alone
does not provide black-start control energy.

At combined source `5b1d30d6`, root acceptance executed **289/289 tests** with zero
failures, errors or skips and twenty historical originals verified. The author's
289 collected /287 executed /2 optional Torch skips remains an earlier record.
The [root receipt](receipt.json) and [raw root output](acceptance-5b1d30d6/summary.json)
keep these checks separate.

## Actual interfaces and accounts

- Only the declared controller/internal-pump/intake-pump auxiliary paths have
  UPS protection. The new fan has no UPS path. Shared downstream distribution
  can defeat multiple nominal reserve paths while stores remain positive.
- Generator starter/control energy and fuel are separate finite inventories.
  Start, transfer, maintenance, failure, fresh-request recovery and depletion
  change usable output. A ready asset is not automatically a connected supply.
- Main and reserve cooling use one actual internal circulation path. The paid
  reserve is an effective signed sensible-heat boundary with explicit capacity
  and air-side assumptions. Fan work leaves through its declared external heat
  account once. This is a synthetic interface, not a real evaporative-tower map.

The [implementation declaration](../../../../docs/mainline/10-reserve-implementation.md)
states the supply priorities, heat destinations, model domains and source gaps.
The existing environment inventories, reported-measurement control and old
profiles/defaults remain intact.

The root [finite-store readback](root-delivery/finite-accounts.json) independently
rechecks the saved budget examples. For the UPS example, 3.6326 MJ supplies
3.24 MJ protected load, 32.6 kJ internal control and 360 kJ conversion loss,
exhausting at 32.6 s. A separately specified 12.5 kJ UPS probe with a .125 s
transfer delay matches exhaustion at `2025/208 s`; its [frozen source guard and
precise results](independent-source-probe/) remain available. These are finite
hand-budget checks, not a claim about site endurance.

## Same-instant state correction

Author regression found one real ordering defect before formal capture: a paid
PLC source-selection sample could remove intake demand while the UPS retained
its obsolete waiting state until the next numerical step. The retained red led
to bounded autonomous reserve settlement after one PLC sample. The PLC is not
sampled again; nonconvergence fails explicitly and access uses the final point.

Both directions are checked. In the reverse case a command arrives at 2.25 s,
the paid sample accepts it at 3 s, UPS waiting starts at 3 s and connection occurs
at 3.2 s. Maximum steps 1/.25 s agree; the PLC's last sample remains 3 s.
The [source Spec report](../../../../docs/mainline/reviews/10-spec.md) closes this
finding, and [Standards](../../../../docs/mainline/reviews/10-standards.md) records
the final guarded targets and compatibility checks.

## Durable delivery

Twenty successful whole-facility cases, six explicit refusals, 134 declared new
artifacts and 36 earlier durable files pass [root delivery verification](root-delivery/fresh-delivery.json).
Execution `179094ed` and delivery `2172dab0` have distinct Git identities. The
initial capture's pending-delivery lifecycle field is retained; the later
committed/fresh-checkout evidence establishes actual delivery. Runtime caches
are excluded by the original declaration and none is required.

The [delivery Standards](../../../../docs/mainline/reviews/10-delivery-standards.md)
and [delivery Spec](../../../../docs/mainline/reviews/10-delivery-spec.md) checks
found no additional issue. The independent delivery records recheck all actual
inputs, 229 private state samples and 209 balance intervals without rerunning
physics. Original failures and earlier unsealed observations remain labeled.

Individual M1 module gates are now accepted. Ticket 11 must still accept the
same complete configuration's eight-domain coupled behavior. Numerical/domain
qualification, outward evidence, heterogeneous decisions and independent effect
studies follow the [mainline](../../../../docs/MAINLINE.md); no research trial,
training or agent call has been added by this engineering milestone.
