# 53：同一次设施运行的联合业务评价

Engineering red/green at the already agreed facility-run seam. Red runtime df003d544dfb18b3a648c7645fa19773818d8fef; green separately frozen after the red terminal. Original180research trials, all prior failures and NO_PRACTICAL_GAIN remain unchanged.

## Closed input and actual binding

Add `aegisdc-business-composite-evaluation-v1`: schema,id,facility_id,basis,time_unit,source_note,run_binding,components only. Components are exactly diagnostic(v3), instance_closure(v2), costs(v2); reject unknown/nested versions. All four program IDs are distinct. Native dispatch must be v5, every component must pass its own validator and share facility/basis/SI/window.

run_binding has exactly scenario_sha256, dispatch_program_sha256, boundary_events_sha256, action_commands_sha256, duration_s, maximum_step_s. Hashes use existing canonical JSON SHA256. Scenario and full dispatch are the actual supplied objects; boundary events and engineering commands are the **validated, float-normalized and execution-sorted** lists used by the plant. Bind after input normalization but before physical state construction/integration. Legacy diagnostic reference hashes keep their original submitted-input rules. The actual result binding must equal the declared common binding; component evaluators receive the same RunResult and never call another simulation.

Add only the declared diagnostic-v3/native-v5 combination; keep old diagnostic-v1/v2 native-v4 restriction. The v3 wrapper may explicitly ask its v2 base validator for this new native combination. Declare `intake_pump.mass_flow` as the existing private `domains.facility_cooling.lake_mass_flow_kg_s`, unitkg/s, targetintake_pump, so private truth uses the same quantity/unit as the already public fixed flow channel. It adds a named sampler mapping, not a new physical state or automatic public observation. Inspection/evidence production still requires its own declared source, scope, quality and availability.

## One joint output

Return `aegisdc-business-composite-result-v1`, PRIVATE_EVALUATOR_ONLY, with complete diagnostic/instance_closure/costs results, common actual run_binding, whole business_program SHA and per-component program SHA, facility/window/execution identity, fieldPENDING and no gain claim. Every component result must have matching facility/window/private visibility and source identity. Save_run already retains business inputs/output; do not splice old captures. No business declaration, truth predicate, timing profile or private ID may enter public dispatch.

## Literal positive

Start from51's complete V6 input. Keep plant, workers/tools, inspection/intervention declarations, closure/review rules and actual resource budget. Change the existing two fixed meters' phase from4to0 (period1/delay0.5/no noise unchanged), add only decision0.5, and use the new private composite. Horizon6, maximumstep0.01,8returned decisions.

The initial flow is below99.7kg/s: the declared full-speed pump has150000Pa and resistance4*12000000+3000000Pa*s2/m6, density1000kg/m3. The first actual fixed sample observed0 arrives0.5; public confirmation0.5. Private initial fault reference is left-censored at0, never a measured onset/positive prevention lead. Fixed reference inspection could start0 and report3.75 (travel2+access0.25+work1+report0.5); cutoff4. The single initial fault is mature/eligible and timely confirmed. Planned deadline6 gives5.5seconds margin; no paired counterfactual/prevention claim.

Action-0 completes3.25/report3.75, own recheck-0 completes5/report5.5, q0 first physically closes5.5. q1 actually opens5.75 and is only administratively accepted then: own action/recheck and physical close null, risk_closed=false. Only those two old tasks execute. Actual service deficit remains0 in this declared healthy-network engineering point; sampled service-loss reference is right-censored at6 with conditional later-event lowerbound5.5, not proof of prevention.

Actual occupation: travel2person_s, work2person_s, wait/access0.5person_s, personnel4.5person_s; tooloccupation4.5tool_s and toolwork2tool_s; issued fees2declared_research_cost. All eight task-attribution dimensions reconcile. Admission envelopes remain separate. Rendezvous positive and joint negative cases remain later qualifications.

## Refusals, budget and delivery

In the same selected test, refuse a maximum_step binding mismatch with `Composite run binding differs from actual execution inputs`; refuse an extra component with `Declare exactly diagnostic, instance_closure and costs components`. Also preserve legacy diagnostic-v2/native-v5 refusal `Declare a separate public diagnostic profile`. Four interface entries each phase; red0windows/0returns, green1window6s/8returns; no directchoose/model/GPU/research call. One invocation per phase, original failures and partial outputs retained, corrections require a new protocol and unique directory.

Freeze contract/protocol/full input/test/material reference/runner/stager/runtime blobs. Preserve actual attempt/terminal/log, complete composite/public summaries and member hashes; full trace/balances remain private. Cache files excluded. No whole39c acceptance: joint crew/no-human/service negatives, business record/read/exact replay and whole-ticket review/zero-skiproot/fresh remain required before39d.
