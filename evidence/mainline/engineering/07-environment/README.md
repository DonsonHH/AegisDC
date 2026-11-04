# Ticket 07 engineering evidence

This directory contains **synthetic engineering checks and fixtures only**.
No registered research protocol, policy comparison, AI/model/training trial,
field calibration or scientific gain is claimed. The fixed complete-facility
goal remains active; M1 acceptance belongs to the integration owner.

Implementation: `ab6094bf`. After merging accepted service ticket 08 from
integration `5da91789`, the committed run source is
`5ca3c3a03d05802458cef1bdd10e66928d75bc1b`, source tree
`d7a984e9852002d617bca2e4ff542d932a319ff663e687095cebd2011b663025`.
All successful run manifests say `implementation_has_changes=false`, and retain
actual source-file, configuration and frozen property identities.

`check.py` creates each numbered output directory exactly once and records the
exact interpreter, command, working directory, local `PYTHONPATH`, source/input
SHA-256, stdout/stderr and exit code. The directory name is an intended step;
the receipt/exit code is the actual result. No failure was overwritten.

## Red/green sequence

|Checks|Actual observation|
|---|---|
|01 /02|Missing floor-water component red; independent isothermal withdrawal green|
|03 /04|Unsupported mixed inflow red; constant-mass analytic mixing green|
|05 /06|Missing condensation boundary red; official independent dewpoint-example bracketing green|
|07 /08|Missing environment profile red; same healthy eight-domain working point green|
|09 /10|Actual hot leak previously left hot mass unchanged; mass/energy withdrawal and floor transfer green|
|11 /12|Gate event unavailable red; active work abort with retained location/time/tool green|
|13|15 independent/public cases green, including existing personnel/qualified access behavior reused without manufactured reds|
|14 /15|Room-work threshold absent red; explicitly sourced research threshold and exact crossing green. Earlier profile/generator/receipt preserved under 14|
|16 /17|Real root numerical counterexample: valid zero drain was rejected; small positive drain was lost by subtracting large energies. Both actual red outputs preserved|
|18 /19|Known zero boundary and stable analytic drain integral green; all 49 previously refused root cases replay with exact zero exported mass/energy|
|20 /21|21 environment boundaries green; 76 then-current facility interfaces green|
|22 /23|At threshold equality, stale pre-protection rectifier heat wrongly closed permission. Post-control actual heat direction fixes it; all 22 environment tests green|
|24|Source/tests/engineering scripts compile successfully|
|25|Full regression and preserved-evidence verification PASS: 247 discovered /245 executed, no failures/errors, exactly two existing optional Torch skips, no unexpected skips, 20 original-file hashes valid|
|26|Nine committed-source engineering runs fresh-read PASS; one declared minimum-inventory run fails explicitly and is retained as an expected domain failure|
|27 /28|Explicit environment CLI case and separate fresh reads PASS; .95 kg actual hot loss, no external nuisance mass invented|

The root's original `108` zero-drain probe, including `49` refusals, is copied
byte-for-byte under 16. Root subsequently reran the complete 108-input grid with
zero refusals; that raw green JSON is copied under 19 and remains correctly
labeled **pre-acceptance dirty-worktree diagnosis**, with its actual module SHA.
It is not reattributed to a committed run. The independently calculated
70-digit reference is `decimal-drain-reference.json`; its mixed tiny drain is
`4.62561347298432934445889740802541542778714915555413508e-11 J`.

## Committed artifacts and physical accounting

`fixtures-5ca3c3a0/runbook.json` declares all parameter overrides, imposed events,
initial worker/tool locations, durations and expected error. Every override is
saved with a synthetic source note. `engineering-attempts.jsonl` preserves all
ten attempts. Each successful case has a source manifest, saved scenario,
private state and interval balances. The one expected failure has its complete
input scenario and raw traceback; no successful post-domain trajectory exists.

`fresh-read-receipt.json` reopens the actual files, checks SHA/counts and canonical
scenario identity, then recomputes independent per-medium/global-water and
whole-facility energy accounts. It separately checks hot mass debit, matching
`cp*T` internal heat transfer, the floor sensible account and unchanged external
nuisance semantics. All eight behavior domains are retained.

|Artifact|Bounded engineering result|
|---|---|
|`normal`|600 s, 601 states /600 balances, zero room/hot temperature drift, zero deficit|
|`isothermal-hot-leak`|1000→996 kg at unchanged 320 K; floor gains 4 kg /5.12 MJ; no external nuisance water|
|`actual-leak-work`|2 kg/s hot loss minus .1 kg/s drain crosses 10 kg at 100/19 s, aborting the active job; final floor≈19 kg, actual hot loss=20 kg|
|`ambient-nuisance-work`|Same access crossing, but source is explicitly external ambient water; hot-water loss remains zero|
|`mixed-pool`|12 kg hot loss plus 6 kg nuisance inflow; initial 20 kg grows to ≈29 kg at 302.5363258026159 K, with actual-temperature drainage|
|`permission-during-work`|Arrival at 120 s, abort at permission close 125 s; 120 s travel and 5 s work retained; tool remains at loc_it|
|`permission-before-entry`|Gate closes at 90 s; attempted declared gate arrival at 120 s is aborted before entry, preserving traversal and last safe discrete location|
|`room-sensible-heat`|100 kW /1 MJ/K raises room by .2 K over 2 s; work abort at ≈1.5 s; liquid temperature unchanged|
|`RH-risk-only`|Boundary risk changes while floor inventory, leaked mass, latent production and physical service remain unchanged|
|`minimum-inventory-domain`|Explicit ValueError when continuing below the declared hot-inventory validity minimum; failed input and raw failure retained|

Across the nine successful runs, maximum fresh interval facility energy residual
is `3.695808118209243e-6 J`, water-mass residual `2.546574062733953e-12 kg`, and
floor energy residual `8.41100700199604e-9 J`. The CLI run is independently retained
at `cli-5ca3c3a0/`, with .95 kg hot loss, .475 kg floor accumulation and no
nuisance-water input; its fresh mass residual is below `5.83e-12 kg`.
These numerical checks establish finite accounting consistency, not step
convergence, field calibration or a policy effect.

The independent primary source check for the condensation equation/example is
`primary-source-receipt.json`; it pins PsychroLib 2.5.0 source SHA-256. This is
only a liquid-water RH/surface risk criterion. No moisture inventory, condensate,
latent heat, perfect dispatch observation or empirical site parameter is created.

Raw output line endings and emitted trailing spaces are preserved; the local
`.gitattributes` scopes whitespace handling to these raw artifacts. Source,
configuration and document whitespace checks remain active. The original V1/V2/
water-V3 snapshots, property table, CLI defaults and earlier artifacts remain
unaltered. Root owns independent review, enabled-Torch validation and integration
acceptance; the overall goal is not marked complete by this engineering ticket.
