# Cost-aware value-of-information scheduling of inspections and interventions in maintenance-degraded computing facilities

## Abstract

A maintenance crew can inspect a backup path before intervening, but the time spent obtaining a reading can consume the permit window for the work it recommends. We developed an online scheduler that weighs this delay against the service consequences of acting on incomplete evidence. It maintains a finite distribution over facility states, groups states that would give the same inspection report, and chooses the next feasible job under staff, tool and access constraints. An independent evaluator measures undelivered service over the entire window. Across {{D14.3|144}} paired synthetic conditions, mean normalized service deficit fell by {{D14.4|−343.90#abs}} s relative to a transparent direct-action rule. Enabling initial inspection in the same scheduler gave a paired difference of {{D15.4|−55.83}} s ({{D12.5|95}}% interval {{D15.5|[−110.00, −11.61]}}), with higher staff occupancy. In synthetic incident families, the scheduler reduced mean deficit relative to existing protection and alarm response. The event-rate contrast remained indeterminate. On a previously used development panel, myopic inspection produced the same deficit on every condition. A finite-budget tree planner used more labour and verified more completed interventions, with an uncertain service difference. These comparisons identify the conditional value of access to inspection and the resources it consumes. Estimating annual site losses also requires the frequency of maintenance exposures and the distribution of conditions within them.

**Keywords**　Value of information, inspection scheduling, decision support, maintenance, computing facilities, partially observable planning

## 1. Decision support during maintenance

A supply monitor can report voltage while a backup path is disconnected. A receipt can establish that a transfer succeeded while a cooling pump remains stopped. In either case, a dispatcher must decide whether to send a technician, authorize corrective work directly, or keep capacity available for another job. The next reading matters only through the actions that remain possible when it arrives. Walking time, an occupied tool or a shared change permit can reverse the choice. Our question is which job to issue now when the criterion is service delivered over the maintenance window.

Formal models of data centres connect electrical, thermal and network failures [@F01,F05,F06]. Measurements from Frontier and its liquid-cooling digital twin illustrate what a facility model can check against instrumented power, heat and flow [@F02,F03]. Studies of hybrid air–liquid cooling, integrated heat pipes and immersion cooling characterize changes in support capacity [@F04,F07,F08]. Work on multiple cooling sources and water-side free cooling likewise connects operating mode to energy performance [@F09,F10]. Our model couples subsystem limits at the point of service delivery, then adds the work needed to change those limits. An operator’s attempt to restore cooling can be late, refused or ineffective, even when the physical model predicts a benefit from a successful repair.

The model represents power distribution, backup, facility cooling, equipment cooling and environment, IT service, controls and monitoring, spatial access, and staff and tools. Separate graphs describe physical transfer, functional dependence, information and control, and access for field work. Existing local protection operates in every arm. Exogenous demand and fault conditions are paired. Each arm owns its evolving facility state, evidence, budget and receipts. Overlapping bottlenecks constrain a single delivered service. A lost unit of service enters the score once even when both power and cooling constrain it.

### Decision state and endpoints

Let *x(t)* denote the private plant state, including delivery capacity, pending events and physical action effects. Dispatch receives a static catalogue *u* and a public history *h*. The catalogue gives job types, routes, shifts, permit windows and budget rules. History contains only records sampled and delivered by the decision time, records of the dispatcher's own work, and valid execution receipts. Observations can expire. A copy carries its original provenance. A paid reading binds to the work order, worker, tool, execution identity and configuration it observed. Demand and delivered service, the next private event, and the evaluator's hindsight schedule remain private.

The horizon is {{M7|3,600}} s, with public decisions every {{M7|60}} s and native physical updates every {{M7|0.25}} s. Write *d(t)* for demand and *y(t)* for delivery. The evaluator integrates the shortfall relative to simultaneous demand over times of positive demand. The resulting *L* is measured in equivalent seconds of completely unmet demand. It also records the unnormalized quantity *U*, staff and tool occupation, fees, and the validity of work-order closure.

{{EQ:endpoints}}

### Computational demand of a dispatch decision

Let *N* be the number of possible worlds, *r* the number of records, *s* the number of relevant subjects and outstanding obligations, and *m* the number of remaining primary writes within their windows. At most one deferral and an inspection and direct action for each eligible subject form the root menu. For a candidate inspection, *g* distinct report signatures partition the supported worlds. Enumerating all prefixes of length up to *m* produces *P<sub>m</sub>* possible write sequences, including the empty sequence. With belief-update cost *C<sub>b</sub>*, root count *F*, calendar-check cost *C*<sub>cal</sub> and single-world scoring cost *C*<sub>eval</sub>, the time bound per public decision is

{{EQ:complexity}}

The factorial term limits use when many orders are open. The calendar scans the remaining public decision times, checking priority work, travel and occupation. Matching records by source and recomputing predictions can require quadratic work in the number of records. The interval-based service forecast can also incur quadratic work in uncached curve segments. Streaming root plans requires space for the posterior, candidate sequences, report-conditioned continuations and the bounded forecast caches. These are bounds on the implemented search. Section {{S6|6}} reports the measured cost on the study's catalogue.

## 2. Choosing the next inspection or intervention

The value of an observation is the change it permits in subsequent decisions and their consequences [@V01]. In sequential maintenance, component inspection, permanent monitoring and system scheduling can each change the action taken [@V02]. Aperiodic inspection models choose a time for inspection or replacement from its expected information value [@V03]. Here the crew must finish the ensuing job and verify its effect before the corresponding permission expires. Results showing that a negative inspection can itself have value, and that imperfect inspection and repair can have different effects, motivate separate records for the report and the completed intervention [@V04,V12,V13].

### Updating the belief from public records

The scheduler starts with design priors over a finite catalogue of possible worlds. The ordinary architecture gives equal prior mass to the water, network, reserve and cooling-access families. Each incident architecture marginalizes over {{T56|12}} prescribed combinations. Only the catalogue appropriate to the public architecture is available. The realized cause and family label are hidden. At each decision the policy recomputes weights from the prior using eligible records, so that retaining an old record across decisions cannot count it twice.

A registration hint and an alarm contribute likelihoods for arrival or silence when their channel could have delivered a record. A returned permit, an interpretable paid reading or a completed write can exclude inconsistent worlds. Fixed sensors often share a bottleneck. For *mₛ* valid sensor types, of which *k* match a world, the scheduler applies one mixture likelihood, ({{M24|1}} − *p*) + ({{M24|2@2}}*p* − {{M24|−1#abs@3}})*k/mₛ*. With no such reading its likelihood is neutral. Write R and A for the record and alarm likelihoods, I for consistency with returned permits, paid reports and writes, and S for the shared fixed-sensor likelihood. Given prior mass *b*<sub>{{M18|0}}</sub>, the normalized posterior is

{{EQ:posterior}}

Only surviving worlds can contribute positive posterior mass. The fixed-sensor matching parameter *p* is {{M24|0.95}}. An unsupported posterior results in a recorded deferral. Time-varying monitoring quality, state-dependent inspection errors and dependent component failures motivate keeping these observation assumptions explicit [@V08,V09,V10,V11]. Sensor placement and maintenance planning with Bayesian networks address related choices about what can be observed [@V05,V06,V07].

### Scoring and admitting a field job

An eligible primary order can receive an initial paid inspection (*I*) or a direct intervention (*A*). An applied intervention creates a verification obligation (*R*) tied to that execution. A follow-up inspection (*X*) is available only when its prerequisites hold. Staff location, travel time, shift, tool occupation, the shared permit and remaining budgets must permit the work. An issued stage cannot be issued twice. An open verification obligation can consume resources that would otherwise be available for a new intervention.

For a feasible continuation π, the policy minimizes the expected predicted service deficit plus the price of labour and issued fees. The caret distinguishes the scheduler's forecast from the score the evaluator subsequently obtains.

{{EQ:objective}}

The fixed price λ is {{M34|1}} deficit-second per person-second. The fee equivalent κ is {{M34|30}} person-seconds per issued fee unit. Tools also have a hard capacity constraint. These prices affect which action is chosen. Labour, tools and fees remain separate outcomes in evaluation.

For a possible inspection *i*, the predicted report at the planned sampling time groups the worlds by the public signature *z*. Its posterior mass is μ<sub>z</sub>. All worlds yielding that report share one feasible continuation. With probability *q* = {{M36|1/32}}, a planned report is uninterpretable. On that branch optional writes stop while already committed obligations remain. If *C* includes the first job and its continuation, *b<sub>z</sub>* is the posterior conditional on the report, and ∅ denotes no further optional write, the inspection score is

{{EQ:inspection}}

**Dispatch procedure.** At each public decision, process newly available evidence and attempt any due verification or follow-up first. Defer while awaiting an issued initial inspection or when evidence supports no world. Otherwise enumerate deferral and every admitted first inspection or intervention. For each candidate, schedule the remaining writes and mandatory checks, retaining a complete feasible plan for every positive-mass report branch. Rank candidates by expected cost, staff occupation and fees, then by the specified preference for deferral and stable job identities. Issue only the winning first request. The executor applies its own admission check and returns the actual receipt. At the next decision the scheduler plans again from the evidence then available.

Partially observable Markov models describe belief as a sufficient planning state [@P01]. Predictive and time-dependent observation models, continuous corrosion states, and joint spare inventory decisions address distinct maintenance problems [@P04,P05,P06,P07]. Constrained deep reinforcement learning offers another way to choose inspection and maintenance actions under incomplete information [@P02]. Learned rail, manufacturing, balanced-system and repair policies likewise address coordinated intervention [@P08,P09,P10,P11]. Our scheduler exposes each report-conditioned continuation and admits it against a job calendar. The same-calendar online comparators in Section {{S6|6}} let us ask whether that additional continuation search changes delivered service.

Inspection routing studies account for synchronized vehicles, energy and persistent resource coverage [@I01,I02,I03], connectivity on patrol cycles and alternative patrolling algorithms [@I04,I05]. In this journal, learning a patrol over unknown spatial importance, routing an inspection robot through a constrained environment and planning multi-site safety inspections make the cost of reaching information explicit [@E01,E02,E03]. Here travel competes with a corrective job for the same crew and permit. Related expert systems coordinate maintenance across manufacturing levels or dependent components, reschedule work after a prediction, use feedback to select wafer inspections and allocate workers under precedence constraints [@E04,E05,E06,E07,E08]. We evaluate the whole sequence through delivered service and execution-linked receipts.

## 3. Preregistered service comparisons

The confirmation panel contained {{T69|24}} conditions in each of six families, {{D14.3|144}} in total. Families covered water-side heat, network power, reserve transfer, cooling access and the two incident analogues. Within a condition, each policy started from a separate copy of the common initial state. Direct rule B ordered publicly eligible jobs and requested intervention. The cost-aware direct rule also used public maintenance terms. The same-policy ablation removed permission to buy the initial reading, retaining deferral, direct action, verification and follow-up. Both arms ran from the start. Deleting a reading from a completed trace would have kept decisions made using that reading. The accompanying STRESS checklist locates the model logic, inputs, sampling units and execution records [@STRESS].

Table A reports the contrasts in their registered order. Each within-family draw resampled the complete condition with all of its arms. The protocol pooled families over {{D9|10,000}} paired resamples and required the upper two-sided {{D12.5|95}}% percentile limit to be strictly below zero before proceeding. The contrast is scheduler minus comparator. The estimated difference for access to inspection includes conditions on which no inspection was bought.

**Table A. Preregistered paired differences in normalized service deficit.** All intervals are in deficit-seconds.

| Test and comparator | Pairs | Mean difference (s) | Interval (s) | Registered result |
|---|---:|---:|---|---|
| {{D14.1|H1}} · transparent direct action | {{D14.3|144/144}} | {{D14.4|−343.90}} | {{D14.5|[−445.94, −244.22]}} | Met |
| {{D15.1|H2}} · same scheduler, initial inspection disabled | {{D15.3|144/144}} | {{D15.4|−55.83}} | {{D15.5|[−110.00, −11.61]}} | Met |
| {{D16.1|H3}} · cost-aware direct action | {{D16.3|144/144}} | {{D16.4|−390.48}} | {{D16.5|[−488.63, −292.83]}} | Met |

The middle contrast isolates access to initial inspection under this decision rule. Mean staff occupancy was {{D29.5|128.92}} person-seconds with access and {{D30.5|107.57}} without it. Whole-policy differences against the direct rules also include when to wait and which job to issue first. Against B, the scheduler recorded less deficit on {{T98|54}} conditions, tied on {{T98|76}} and lost more service on {{T98|14}}. A favourable mean thus coexisted with individual conditions in which direct action delivered more service.

## 4. Waiting for a reading across maintenance durations

The synthetic maintenance mechanism makes an early intervention consequential. A qualifying write during maintenance can cap support at {{T60|0.50}} of capacity. The shared change permit adds a {{T60|180}} s recovery interval. These are frozen synthetic mechanisms. The durations were public at dispatch. Table B reports the original descriptive strata for access to a paid initial reading. The sampling units and the comparator are the same as in the middle row of Table A.

**Table B. Within-stratum paired differences, initial inspection available minus disabled.** The brackets give marginal {{D12.5|95}}% percentile intervals.

| Public maintenance duration (s) | Conditions | Mean difference [interval], s |
|---:|---:|---|
| {{D45.1|0}} | {{D45.2|48}} | {{D45.4|+0.62 [0.00, +1.88]}} |
| {{D46.1|600}} | {{D46.2|48}} | {{D46.4|−86.16 [−179.79, −15.99]}} |
| {{D47.1|1,200}} | {{D47.2|48}} | {{D47.4|−81.97 [−197.32, +14.65]}} |

The middle stratum's interval lay below zero. The long-duration interval spanned zero. These estimates describe three subsets of the original panel. A threshold rule for future maintenance windows would require a between-stratum comparison and evidence under the weights of the intended operating site.

Two earlier development traces show how the same reporting delay can have opposite consequences. In case {{T98|3-03}}, a reading at {{T98|50}} s allowed the crew to omit a network write. With the read disabled, direct intervention at {{T98|60}} s produced {{T98|600}} deficit-seconds. With the inspection available, the deficit was {{T98|0}}. In case {{T98|3-02@7}}, intervention was needed. Waiting for the report delayed dispatch from {{T98|0@10}} to {{T98|60@11}} s. The deficit rose from {{T98|326.25}} to {{T98|371.25}} s. The useful information in the first case was the reason to leave the device alone. In the second case, its cost included service lost before the necessary job could start.

## 5. Two synthetic incident families

The London report describes a disconnected backup path and an upstream indication that inhibited automatic start. The Netherlands report describes a transfer overload and pumps that failed to restart after their controllers went offline [@LONDON,NL]. These accounts constrain which causal pathways are credible. They do not supply the shift's original work permits, evidence at dispatch or action times. We therefore instantiated the mechanisms in the synthetic facility. In the London family, the crew can restore backup readiness before a challenge. In the Netherlands family, regrouping supply and recovering cooling are distinct operations. A successful transfer alone does not certify pump service.

Each family contributed {{I7|60}} conditions. Each policy had its own evidence and resources. All {{I9|120}} rows, including {{I9|16}} realized inputs overlapping earlier work, entered the original analysis. Family means were equally weighted. The severity endpoint was mean *L*. A synthetic service event occurred when unrounded *L* was positive. The registered analysis used marginal two-sided intervals with Holm adjustment of the hypothesis tests. Block structure governs the uncertainty in this comparison.

**Table C. Confirmatory incident-family comparisons.** Severity differences are in seconds. The event-rate difference is in percentage points.

| Test and comparator | Endpoint | Difference [marginal interval] | Decision |
|---|---|---|---|
| HA · existing protection | Deficit | {{I23.3|−580.00}} {{I23.4|[−595.52, −564.48]}} | Met |
| HB · response to arrived alarms | Deficit | {{I24.3|−582.08}} {{I24.4|[−612.65, −551.51]}} | Met |
| HC · existing protection | Event rate | {{I25.3|−37.50}} pp, interval indeterminate | Indeterminate |

Of {{I31|90}} conditions with a deficit under existing protection, {{I31|45}} reached zero under the scheduler. Among the {{I31|30}} conditions without an event under protection there were no new events. Paired event-rate differences had zero between-block variance in both families. The event-count point estimate is observable, but the registered interval and directional test are indeterminate. The severity comparisons support a whole-policy effect in these synthetic families. They leave both field event frequencies and the historical incidents' avoidability unidentified.

The records also explain why earlier action is difficult. In a London development case, the scheduler directly restored the backup path at {{T120|720}} s. Its first paid reading at {{T120|830}} s verified that intervention. In a Netherlands development case, the evaluator identified {{T120|540}} s as the latest necessary start. The scheduler was still waiting then and first attempted to restart a pump at {{T120|2,040}} s, without buying a reading during the window. A deadline reconstructed by the evaluator was unavailable as a dispatch signal.

## 6. Alternative online planners and sensitivity (post hoc, nonconfirmatory)

The supplementary panel reused {{P3|72}} development conditions whose outcomes under the centre policy had already been observed. The two online comparators and the parameter changes used the same inputs and scoring rules. Each had independent state, receipts and resources. The frozen centre retained its archived scores. The additional arms yielded {{P3|720}} complete, compliant positions. The interpretation table and the supplementary protocol were fixed before their execution. The earlier confirmatory comparisons keep their original comparators and decisions.

The myopic value-of-information (VoI) rule prices delay and labour over the same full window. After an optional inspection it considers at most one elective intervention, with the same verification obligations. The tree comparator uses Partially Observable Monte Carlo Planning (POMCP) with public action–observation histories. It samples a world from the root belief for each simulation, shares feasible actions across indistinguishable histories, and charges service, work and fees at the leaf. Unmodelled future free channels supply no new simulated evidence. The budget is {{J119|128}} simulations per elective decision and depth {{J120|4}}. Monte Carlo tree planning, risk-aware shielding, graph search and online model adaptation offer different ways to spend such a budget [@P03,POMCP,P12,P13,P14]. The comparison here pertains to the particular public model, budget and fixed random stream used.

### Service, resource use and completed verification

The service deficit was identical on all {{P16|72}} conditions for the centre and myopic VoI. The {{P16|3}} conditions with different issued request sequences also differed in personnel, tool occupation and fees. Equal service delivery on this panel therefore coexisted with different decisions and costs.

**Table D. Centre minus comparator on the development panel.** Brackets give paired marginal {{P7|95}}% intervals. Fee units are charged on issue.

| Comparator | Deficit (s) | Staff occupation (person-s) | Fees (units) |
|---|---|---|---|
| Myopic VoI | {{P11.3|0.00 [0.00, 0.00]}} | {{P11.6|+1.46 [−0.97, +4.38]}} | {{P11.8|+0.04 [−0.03, +0.12]}} |
| Finite-budget POMCP | {{P12.3|−57.50 [−118.06, +9.36]}} | {{P12.6|−72.78 [−93.96, −52.71]}} | {{P12.8|−1.35 [−1.69, −1.00]}} |

For POMCP, the service interval crossed zero. POMCP used more staff time and incurred more fees. It also closed more work orders with valid verification of its own completed intervention at window end (PV). Across {{P45.2|207}} named work orders in each arm, the count was {{P45.8|36@4}} for the centre and {{P47.8|52@4}} for POMCP. Of {{P146.2|4,392}} POMCP decisions, {{P147.2|903}} entered elective search (VALUE). Another {{P151.2|3,156}} returned NO_COMPLETE_ADMITTED_BRANCH when no complete elective branch passed admission. The remainder followed other registered decision paths. A median over all calls includes these much cheaper returns. The development panel showed no additional service advantage over either online comparator. Their ranking under a larger search budget remains open.

Two descriptive slices illustrate the variation across this panel. Among {{P88.2|24}} development conditions with {{P88.1|1,200}} s of maintenance, centre minus POMCP was {{P88.9|−200.96 [−296.92, −103.75]}} deficit-seconds. In the reserve-transfer family ({{P82.2|12}} conditions), it was {{P82.9|−150.00 [−282.50, −32.50]}} s. These are post hoc marginal intervals for subsets of a reused panel. The design established neither an interaction nor a conditional selection rule. Supplement B includes all family and duration rows.

### Sensitivity and decision latency

Each one-at-a-time variant changed a planning assumption while keeping the physical facility and its accounting fixed. Raising λ from {{P66.4|1}} to {{P66.3|2}} shifted the mean deficit by {{P66.6|+58.81 [+6.67, +124.69]}} s and staff occupation by {{P66.8|−42.22 [−57.85, −27.78]}} person-s, both expressed as variant minus centre. This was the only service interval among the eight variants that excluded zero. Charging more for staff time led the scheduler to save labour at a cost in service. The comparison describes the engineering trade-off at the specified price. The centre used in confirmation retains its original price. Supplement B gives both sides of each registered parameter change.

**Table E. Outer interprocess communication (IPC) wall time per returned decision.** The centre was measured by isolated replay in job {{K20|135631}}. The original worker's internal CPU clock was unavailable. The other rows are live timings from the supplementary study.

| Method and clock source | Timed calls | Median (ms) | {{P129.5|95}}th percentile (ms) | Maximum (ms) |
|---|---:|---:|---:|---:|
| Centre · isolated public-worker replay | {{P131.3|4,392}} | {{P131.4|1.292}} | {{P131.5|4.200}} | {{P131.6|17.065}} |
| Myopic VoI · online | {{P132.3|4,392}} | {{P132.4|1.434}} | {{P132.5|2.218}} | {{P132.6|5.246}} |
| Finite-budget POMCP · online | {{P133.3|4,392}} | {{P133.4|1.390}} | {{P133.5|28.697}} | {{P133.6|52.730}} |

![Outer IPC timing at the median, upper percentile and maximum for each policy](figures/decision-latency.svg)

*Figure A. Outer IPC wall time from request serialization through parsing the response. The centre's points come from isolated public-worker replay in job {{K20|135631}}. Internal CPU time for the original worker was unavailable. The other points come from the online runs. Markers show the median, {{P129.5|95}}th percentile and maximum on a common millisecond scale.*

### Interpreting the clocks

Replaying archived public histories reproduced their proposal digests without creating new centre scores. On the active POMCP search path, median tree time was {{P147.7|9.664}} ms and median terminal-evaluation time was {{P147.9|11.807}} ms. These clocks measure components on calls that actually entered search. The online full-call medians above describe a different denominator. Computational feasibility at a larger catalogue size remains to be measured.

## 7. Conditional risk per maintenance exposure

A facility operator deciding whether to staff an inspection needs both its consequence if used and the frequency with which the relevant circumstance arises. Following the frequency–consequence decomposition used in FEMA's National Risk Index [@FEMA], we take entry into a maintenance-degraded window as the exposure unit. Let π<sub>f</sub> be the assumed probability of family *f* conditional on entry. Let Ȳ<sub>fa</sub> be the archived mean of a consequence for policy *a* within that family. Its conditional expectation is the sum of π<sub>f</sub>Ȳ<sub>fa</sub> across families. Multiplying by a measured annual exposure rate ν would yield an annualized expectation in the same physical units. Joint bottlenecks have already contributed once to service delivery within each window.

Table F applies three prespecified hypothetical mixtures to the same development records. Within each family, the {{R10|12}} conditions receive equal weight. The family order is water-side heat, network power, reserve transfer, cooling access, London analogue and Netherlands analogue. Personnel and service retain their own units.

**Table F. Reweighting released development means.** The six entries are mixture numerators with a common denominator of {{R21|60}}. Differences are inspection available minus disabled, per maintenance exposure.

| Assumed mixture | Weights in family order | Mean deficit difference (s/window) | Mean staff difference (person-s/window) |
|---|---|---:|---:|
| Balanced | {{R23.2|10, 10, 10, 10, 10, 10}} | {{R23.6|−53.67}} | {{R23.7|+23.33}} |
| Ordinary architectures emphasized | {{R24.2|12, 12, 12, 12, 6, 6}} | {{R24.6|−59.91}} | {{R24.7|+24.79}} |
| Incident analogues emphasized | {{R25.2|3, 3, 3, 3, 24, 24}} | {{R25.6|−31.85}} | {{R25.7|+18.23}} |

Changing the assumed mix altered the size of the service difference. Staff occupation increased in all three scenarios. Field annualization requires a maintenance log with an exposure denominator, the distribution of initiating conditions, actual demand and a mapping from lost service to consequences at the site. The synthetic quotas and public incident narratives supply none of these frequencies. The estimates in Table F are conditional finite-panel means.

## 8. Boundaries of feedback-based improvement

A selector developed using previous outcomes transferred poorly. On {{T126|36}} fresh conditions it lost {{T126|80.49}} s more service than its frozen comparator (interval {{T126|[41.31, 123.48]}}). The registered transfer advantage was unsupported. Under an equal evaluation budget, ordinary search and a search procedure capable of rewriting its proposal rule selected the same edit. Rewriting added no paid candidate. Their service and labour differences were both zero. On the selection panel the Netherlands mean labour increase over the parent was {{T149.2|+36.458333}} person-s, above the registered allowance of {{T61|+5}}. The study ended at selection. An independent benefit from recursive rewriting remains unestablished. The historical selection panel used a shared account for procedural overlap checking (Supplement C).

### Conclusions

For these paired synthetic conditions, giving a cost-aware dispatcher the option to inspect reduced average service deficit at a labour cost. The intervention the reading can still change, the resources it occupies and the time the permit remains open determine its operational meaning. The two synthetic incident mechanisms supported severity comparisons. On the reused development panel, myopic inspection matched the centre's service deficit on every condition. The direction of the service difference with finite-budget tree search remained unresolved. An operator considering deployment would need the site's exposure and service records to convert these conditional results into an annual consequence.

### Data and code availability

The implementation, frozen protocols and aggregate results are publicly versioned. Supplements A and B identify the released inputs, comparators, score summaries and limits of public reproduction. Native trajectories and custody material are held separately. The public tables are sufficient to verify the numerical statements in this article.

### Declaration of generative AI and AI-assisted technologies

OpenAI Codex and AI writing tools assisted with English drafting, revision, code and document preparation. Human authors retain responsibility for the manuscript and its submission.
