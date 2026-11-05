# Current decision inputs and public feasibility

Ticket 15 uses the already authorized decision-view/CLI seams. Its backend
`DecisionGateway` owns a ticket-14 ledger and a frozen **public** decision
schedule. Only the evaluator calls `next_frame()`; no arbitrary query time is
accepted. The consumer receives detached plain JSON, never the gateway, ledger,
plant, trajectory or private scenario. A public tick is released even when no
record has arrived; private events do not create additional decision ticks.

Nominal public knowledge is a separate, closed document authored from the
canonical public V6 profile. Current parameter overrides, resource occupation,
physical access and future event lists are not nominal knowledge. The full
engineering fixture retains the 45 V6 identities, eight domains and four
relation kinds. Its public work intentions are declared before the paired
hidden-world comparison; a hidden fault does not create an intention/problem.

Ledger/nominal entity membership is checked as a set of unique IDs. Released
entity IDs follow the independent canonical public nominal document's order;
source/observable registries and coverage lists use ID order. Templates from
tickets 16/17 can therefore present the same registry in a different order.
Observation values, timestamps, carried origins and first accepted duplicate
encodings are not rewritten. The public intention order remains meaningful for
the deliberately simple demo selection rule.

The pure `public_feasibility(frame, request_id)` and `decision_options(frame)`
interfaces use only this frame. Their mask means **eligible for preparation or
planning under public inputs**, not certified execution or permission to enter.
Nominal qualifications/tools can rule out a request. A declared, arrived
restriction report may conservatively defer a request and carries its record
IDs/quality; it is not promoted into actual-state truth. Otherwise dynamic
access, current positions and resource occupation remain unverified. Actual
M1 safety checks remain private and unchanged.

Each reported constraint explicitly declares a boolean `blocking_value`. A
permit-style channel normally declares `false`, while a restriction/alarm-style
channel can declare `true`. The interface never guesses this meaning from an
observable name or the private world. Any matching current reported value uses
the declared conservative rule; unknown quality remains visible and no actual
access state is certified.

The deterministic demo chooses the first eligible public intention in its
declared order. It is a tracer, not a dispatch algorithm or effect claim. No
execution method exposes an instantaneous private rejection. Later execution
must obtain remote status through a declared channel/time or reach a safe gate
and pay the declared travel/wait/check costs before an observation is released.
Records/observation generation and real execution remain with their own tickets.

Own standalone entry point avoids changes to the shared command module:
`python -m aegis_dc.decision_view --nominal FILE --ledger FILE --plan FILE --output NEW_DIRECTORY`.
It is an offline evaluator tracer. The accumulated hindsight trace is explicitly
private and is rejected by the per-current-frame consumer interface. The driver
passes only each current frame into the pure consumer before appending its
result; a policy does not receive the completed trace or the loader/gateway.
All new fixtures are engineering data; registered research/model/training
counters remain zero.
