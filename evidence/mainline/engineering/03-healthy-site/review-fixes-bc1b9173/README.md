# Post-resolution review corrections

The implementer's original ticket resolution was not root acceptance. Root review
found two contract defects in the 37432b25 implementation. Both were reproduced
through public interfaces before correction. The prior normal/work/acceptance
artifacts retain their original 37432b25 source attribution and exact bytes.

|Review finding|Observed red|Correction / green|
|---|---|---|
|Standards: unhashable schema|Array/object schema raised loader `TypeError`; both `scenario` and `simulate` CLI returned a traceback/exit 1|`037d82fb0348d89b33f1f76585c49eace5fb18f4` checks text type before schema-set lookup; public loader raises `ValueError`, both CLIs return clean argparse error/exit 2|
|Spec: protection lost during controller power cycle|An initial trip, .25 s loss and 1.25 s restoration produced `mode=normal`, compute=2 MW at 2 s while Tr=303.17935754 K remained above 290 K reset; uninterrupted control stayed protected|`bc1b9173d8b0deb796b7a2938924dc146e0e4588` keeps `protection_latched` independently of powered/unpowered mode; restoration stays protected/compute=0 until a powered below-reset + adequate-flow sample|

The reset counterexample uses the same power cycle with reset=303.5 K. Tr is
303.17935754 K and internal flow=.12 m3/s, so protection can correctly clear.
The correction preserves the declared hysteresis rather than changing its target.
The test inputs are explicit finite engineering fixtures within the original
parameter ranges, not actual facility settings or scientific comparisons.

`../schema-review-fix/` contains the actual red log (4 failures/2 errors), the
subsequent 36-test green target log, and tested source hashes. `../latch-review-fix/`
contains its actual red/37-test green logs, tested source hashes and a public-API
reproducer. Its `red-037d82fb/` and `green-bc1b9173/` directories preserve all three
cases as config/manifest/private-state/balance artifacts. The red physical run is
attributed to the clean schema-fix source snapshot, which still had the latch bug;
the green physical run is attributed to the clean bc1b9173 snapshot.

`acceptance/` records current engineering/evidence/overall PASS: 179 discovered,
177 executed, zero failures/errors, two precisely identified pre-existing optional
Torch skips and no unexpected skips; all 37 facility target tests execute. The
20 historical original files verify. This full run uses the primary interpreter
and an explicit worktree `PYTHONPATH`, without an isolated Torch path. Root owns
enabled-Torch and final integration acceptance.

`receipt.json` fresh-reads all run artifact identities and critical outcomes,
checks actual green-tested source bytes, and confirms that all 13 files registered
in the original receipt remain byte-identical. It does not relabel old results as
having run under corrected code. This checkpoint's source verifier expects the
bc1b9173 implementation content; later implementation changes need their own
checkpoint rather than overwriting this evidence.

Commands used the primary interpreter at
`C:/Users/Donson/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`,
working directory `C:/Users/Donson/Documents/ChatGPT/Renly/.work/worktrees/full-site-03`
and that worktree's `src` in `PYTHONPATH`:

```powershell
python -X utf8 -m unittest discover -s tests -p test_full_facility_scenario.py -v
python -X utf8 -m unittest discover -s tests -p test_full_facility_plant.py -v
python -X utf8 -m unittest discover -s tests -p 'test_full_facility*.py' -v
python -X utf8 evidence/mainline/engineering/03-healthy-site/latch-review-fix/reproduce.py --label red-037d82fb
python -X utf8 evidence/mainline/engineering/03-healthy-site/latch-review-fix/reproduce.py --label green-bc1b9173
python -X utf8 evidence/mainline/engineering/03-healthy-site/review-fixes-bc1b9173/verify_review.py
```

Existing reproduction labels are refused; use a fresh label for another run. The
full acceptance used `scripts/acceptance.py:verify` with this directory's new
`acceptance/` output. Scoped Git artifact rules preserve native CRLF acceptance
bytes and unittest's intentional subtest progress spaces in the red log. Target
logs are captured as UTF-8/LF text.

Root Standards/Spec and integration acceptance remain pending. Ticket 03's
implementation is resolved with review corrections recorded; M1 and the overall
research objective remain active. No research trial, model call, training job or
real-device action was performed.
