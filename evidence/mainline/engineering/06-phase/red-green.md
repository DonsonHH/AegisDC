# Ticket 06 behavior slices

Scope: engineering checks, no registered research trial, policy comparison,
training or AI-model call. Base implementation is `0ee160cdcdbd195acf35d552abd8040ef7e55b5c`.
The independent full-facility worktrees own power/water changes; only
`src/aegis_dc/thermodynamics.py` is modified in this ticket.

The mainline spec already authorizes the public property and facility-run seams.
`implement-spec`, `implement` and `tdd` were read. Independent root review owns
the two-axis review step; no additional agents were launched by this implementer.

Execution uses Python 3.12.14 at the primary runtime, with `PYTHONPATH` explicitly
set to this worktree's `src` (avoiding the root editable install).

1. Freeze `eos-reference-01/direct-eos-reference.json` with the offline author.
   Its outputs are direct CoolProp PQ and Dmass/Umass calls. Predeclared inputs,
   numerical limits and source hashes precede table implementation changes.
2. Add only the fourteen-endpoint public behavior test. `red-endpoints-01/tests.log`
   retains the initial result: one test, four failing subcases, all `found 0`.
   The failing states are 0.1 MPa x=`1e-10`, `0.99999`, `0.9999999999`, and
   3 MPa x=1.0.
3. Add explicit endpoint checks with a local floating-point energy condition.
   `green.log`: one test, all fourteen subcases accepted, no clipping.
4. Add one observable behavior at a time and execute the growing file after
   each: fixed-volume direct EOS states, 2 MJ heating, 2 MJ condenser/water
   reciprocity, outside-domain refusal, invalid inputs, nonunique rejection,
   reverse condenser transfer, stopped-flow stored heat, runtime domain exit,
   and high/low filling. Each matching `green-*.log` retains that run.
   These behaviors were already implemented by ticket 03 and passed on first
   observation; no artificial failing change was introduced to manufacture red.
5. Final focused file: eleven tests, no failures/errors/skips. Compilation and
   whitespace checks pass. Frozen engineering runs and full-regression receipts
   are recorded separately after committing the clean implementation.

Focused command (PowerShell, repository root):

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest discover -s tests -p test_mainline_phase.py -v
```

Offline author (explicit isolated library; fresh output only):

```powershell
python evidence/mainline/engineering/06-phase/create_eos_reference.py --eos-target <isolated-CoolProp-8.0.0> --output <new-author-directory>
```

The author was executed against the already hash-verified isolated extension in
the earlier property-reference receipt. Runtime and tests do not use that target.
