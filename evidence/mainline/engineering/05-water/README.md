# Ticket 05 engineering records

All records here are synthetic **engineering fixtures/checks**, not registered
research trials, policy comparisons, field calibration or gain evidence. The
complete facility and research goal remain in `docs/MAINLINE.md`.

Implementation is `8db1e95a`; merge `e8555f76471dd98e9f2d6c67a2b028803daa61e1`
incorporates the integration tip `8fb76ad9`. The accepted run source tree is
`eb8fec51c8e95e4e2aa3938a2a1a56d71c3f8cf540ea778859e069a2cbbc0a9f`.
All accepted run manifests say `implementation_has_changes=false`, and include
the actual source-file, scenario and frozen property identities.

Use the primary runtime with this worktree's `src` on `PYTHONPATH`. Each numbered
check was executed by `check.py`, which creates a fresh directory containing its
exact command, working directory, interpreter, source/input SHA-256, exit code,
stdout and stderr. No prior result directory was reused. Consult the actual
receipt/exit code, not the name of a planned check, to determine success.

## Red/green and existing behavior

|Check|Observed result and interpretation|
|---|---|
|01-component-red|One ImportError: the new public series-valve component did not exist|
|02-component-green|100 kPa / 60+40 kPa / .01 m3/s / 1+2 kW hand case passed|
|03-closure-red|Exact opening zero was rejected by the positive-opening formula|
|04-closure-green|Separate shutoff/interlock branch passed with all dynamic outputs zero|
|05-variant-red|New water configuration did not exist|
|06-variant-green|**Failed**, despite the planned label: first control graph tried to issue a command from the valve domain and was correctly rejected. Exact rejected config, generator and generation receipt are retained here|
|07-variant-green|Correct report -> aggregate local control -> pump-permissive graph loaded and preserved the normal working point|
|08-local-interlock-red|Private control trajectory did not yet distinguish hardwired permits from sampled commands|
|09-local-interlock-green|Immediate pump-stop and delayed sampled compute trip both observable; 2 s demand, 1 s deficit|
|10-heat-domain-red|The physically impossible f=.5 with active eta=.7/.75 was accepted|
|11-heat-domain-green|Initial V3 cross-parameter rejection passed; later refined to actual active operation|
|12-independent-cases|14 independent/public cases passed, including already implemented hydraulic/thermal behavior|
|13-active-heat-domain-red|One failure/one error: V2 still accepted an impossible active split, while V3 overconstrained an inactive pump|
|14-active-heat-domain-green|16 cases passed; actual positive hydraulic work now gates the per-pump heat constraint, including timed enable|
|15-existing-facility-regression|53 executed at that revision, zero skips/failures/errors, covering old scenario/run/CLI and then-current water cases|
|16-final-water-cases|One incorrect test expectation: worker/tool/valve were already co-located, rather than requiring the guessed 60 s walk|
|17-corrected-work-fixture|18 executed, zero skips/failures/errors after reading declared static locations and correcting arrival/completion to 0/30 s; no plant change for this fixture mistake|
|18-compile|AegisDC, water tests and engineering scripts compile successfully|
|19-full-acceptance|Full-repository result is in `acceptance-e8555f76/summary.json`; exact command and source identities in the numbered check|
|20-source-attributed-fixtures|Nine committed-source runs passed fresh file/hash/count/mass/energy/HX-port/head-split checks|
|21-explicit-water-CLI|Explicit new `--model` plus timed internal shutoff succeeds; defaults remain unchanged|
|22-CLI-fresh-read|Fresh CLI output file/hash/count/physical checks passed; deficit is the independent 1 s expectation|
|23-integrated-full-acceptance|After merging power ticket 04: 206 discovered /204 executed, zero failures/errors, two existing optional Torch skips, no unexpected skips, engineering/evidence/overall PASS and 20 original-file hashes valid|
|24-integrated-fixtures|The same nine predeclared cases re-executed at committed merge 122f73bd and passed their fresh checks in a new directory; earlier outputs preserved|
|25-final-fresh-read|Final fresh reads, semantic trajectory comparison across power integration, preserved-input Git blob checks and a hash receipt for all prior engineering files|

No red was manufactured for an already implemented capability. The existing
epsilon/NTU exchanger, finite hot/cold volumes, paid fixed-head pump and filter
response were evaluated and reused. Only the missing valve path, observable
shutoff relay and physical heat-allocation domain required new behavior.

## Accepted artifact inputs and fresh reads

`fixtures-e8555f76/runbook.json` declares every configuration override, event,
duration and engineering visit. Each overridden parameter retains a synthetic
override source note in its saved scenario. `engineering-attempts.jsonl` records
all nine attempts. Each case has `run.json`, `scenario.json`,
`private-state.jsonl` and `balances.jsonl`; `fresh-read-receipt.json` recomputes
actual file hashes/counts and physical boundary identities from disk.

- `normal`: 600 s, 601 states /600 balances, no service deficit.
- `hand-399500W`: independent 399.5 kW HX /400.5 kW lake case, 10 kg/s distinct
  water throughflows and no refrigerant/floor-water inflow.
- `filter`: passive lake resistance x4 without changing the valve coefficient.
- `quarter-head`: 37.5 kPa lake head, .05 m3/s and 2678.5714285714284 W.
- `hx-degradation`: declared 306/305 K thermal protection, UA=10 kW/K at .25 s;
  first sampled protection at 57 s, service deficit 43 s over 180 s.
- `internal-shutoff`: .25 s immediate interlock, 1 s sampled low-flow trip,
  service deficit 1 s over 2 s.
- `internal-reopen`: reopening at 1.25 s restores water flow, with sampled
  compute reset at 2 s; service deficit 1 s over 3 s.
- `lake-shutoff`: declared 306/305 K thermal protection, first sampled trip
  at 56 s, service deficit 42 s over 180 s; internal flow remains available.
- `valve-visit`: qualified identifiable internal-valve job completes at 30 s;
  completion is an engineering work record, not inspection evidence or repair.

The 306/305 K settings are explicit engineering fixture choices, not a real
site controller recommendation or a method selected for positive research gain.
Maximum fresh per-interval whole-facility energy residual across these runs is
`4.4833868741989136e-6 J`; mass residual `4.547473508864641e-13 kg`; HX-port
enthalpy mismatch `1.4202669262886047e-8 W`; series-head mismatch
`2.3646862246096134e-11 Pa`. Whole-run residuals also satisfy their original
source-tagged tolerance. This establishes finite model/account consistency,
not a timestep-convergence qualification.

The explicit CLI case is separately retained in `cli-e8555f76/`, with source
inputs in `cli-inputs.json` and fresh-read output in check 22. Research trials,
LLM/model calls and training calls are zero in every accepted manifest.

## Integration recheck

After the root integrated power ticket 04, this branch merged integration tip
`47dda5d7`, producing `122f73bd7fcd38fb18d3911227a58aaf8aafaafd`. The new source
tree identity is `d92aaa9f735b535a40fd14861d12af505e9a2711a39430df8034e9596b1f866d`.
`fixtures-122f73bd/` preserves a second nine-run set with the same frozen
engineering runbook and its own actual source attribution/fresh-read receipt.
The first `e8555f76` set remains historical and unchanged. The original full
acceptance was 197 discovered /195 executed; the final integrated acceptance
adds nine electrical checks, for 206 discovered /204 executed. Both have the
same two declared optional Torch skips and zero failures/errors/unexpected skips.
Root owns enabled-Torch coverage, independent review and milestone acceptance.
