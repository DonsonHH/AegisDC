# Ticket 08 behavior slices

Base: `454408e33bc39a45a87ac2799c8dfd8ceff0a4ae`, the actual integration tip when
the dedicated `full-site-08` /`donson/mainline-08-service` worktree was created.
Ticket 03 is resolved with root acceptance. The live worktree/branch inventory
and progress hints were checked before claiming this independent ready ticket.
Ticket 06 and its originals were not modified.

The accepted seams are `load_scenario` /`simulate_scenario` /CLI and saved-run
artifacts. `implement` and `tdd` were read again for this assignment. The root
owns independent review and enabled-Torch acceptance; no additional agents were
launched by this implementer.

1. Add one public timed-compute-capacity hand case: demand 1 for 2 s, half
   capacity from .25 to 1.25 s, independently expected delivery 1.5 and deficit
   .5 s. `red-timed-capacity-01/tests.log` records the actual unsupported-input
   error before a source change.
2. Add the three existing component-capacity parameter names to the timed-input
   allowlist. `green.log` records the corrected behavior. No service equation,
   physical state model, calibration coefficient, runtime contract or scenario
   configuration is changed.
3. Add and execute one behavior at a time: overlapping network/storage loss,
   any individually required component unavailable, zero then positive demand,
   fractional/changing demand, execution pause/throttle without demand deletion,
   invalid event rejection, and CLI save/source parity. Each matching
   `green-*.log` preserves the observation. These account behaviors already
   existed and passed on first observation; they were not artificially broken.
4. Final focused suite: eight tests, all executed, no failures/errors/skips.
   Full-regression and saved engineering artifacts are produced after the source
   commit, in fresh directories, using explicit worktree `PYTHONPATH`.

Focused command (PowerShell in the selected worktree):

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest discover -s tests -p test_mainline_service.py -v
```

The hand-case expected accounts are literal independent interval sums, not
outputs reconstructed with the service implementation. All cases remain in the
same eight-domain synthetic facility. They are engineering fixtures, with zero
registered research trials, model calls or training. M1 and the overall goal
remain active gates.

Captured unittest logs retain their native CRLF bytes. The first staged
whitespace check flagged those carriage returns; the same scoped `cr-at-eol`
attribute already used by tickets 04/06 now declares them valid in this evidence
directory. No captured result bytes were rewritten to satisfy the check.
