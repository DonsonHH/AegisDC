# Ticket 03: engineering fixtures

Implementation source: `37432b25a994c1c4e37d6747e9e9228a9ea3a44a`,
`donson/mainline-03-healthy`. These are finite engineering fixtures, not research
trials or evidence of policy/AI/RSI gain. The full facility and research objective
remain active. Field calibration is PENDING.

- `normal-37432b25/`: default 600 s v2 operating point, 601 private state records,
  600 balance records, demand/delivery 600 service-unit seconds, zero deficit and
  zero worker/tool occupation. Water/solid/room/phase states stay at their derived
  normal point. Maximum recorded interval energy residual is
  `1.257285475730896e-8 J`; whole-run residual is `3.814697265625e-6 J`.
- `work-37432b25/`: 151 s with the finite requests in `work-inputs-v1.json`,
  158 private state records and 157 balance intervals. One job travels for 120 s,
  arrives at 120.25 s, works for 30 s and completes at 150.25 s. Four others are
  rejected for shared-tool, professional qualification, busy worker and qualified
  access conflicts. Occupation is 120 person-s travel, 30 person-s work and 150
  tool-s; no job repairs equipment or produces inspection evidence.
- `acceptance-37432b25/`: source-clean complete engineering/evidence acceptance,
  176 tests run, 174 executed, no failures/errors, exactly two optional neural
  checks skipped because the isolated Torch runtime is not on this interpreter's
  path. All 21 new plant/property/CLI checks execute. Existing 20 original-file
  hashes verify. The root agent owns enabled-Torch and integration acceptance.
- `receipt-37432b25.json`: accepted source/config/property/output identities and
  fresh-read checks. The verification script independently re-reads per-step
  before/after stored energy and external in/out totals, recomputes mass balances,
  checks nonnegative/phase/volume/capacity conditions, normal-point literals,
  default no-patrol behavior and exact finite-work outcomes. Fresh-read maximum
  facility energy residual is `6.05359673500061e-9 J` in both saved runs.
- `red-green.md`: observed implementation slices and the distinction between
  newly failing behaviors and already-green regression guards.

Every run manifest attributes actual source-file hashes, canonical scenario hash,
property-table hash and the complete input snapshot. Both manifests have
`implementation_has_changes: false`. Trace data are
`PRIVATE_PLANT_EVALUATOR_ONLY`; no dispatch decision view is implemented.

Commands were run in
`C:/Users/Donson/Documents/ChatGPT/Renly/.work/worktrees/full-site-03`, with
`PYTHONPATH` explicitly set to that worktree's `src`. Interpreter:
`C:/Users/Donson/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

```powershell
python -X utf8 -m unittest discover -s tests -p test_full_facility_plant.py -v
python -X utf8 -m unittest discover -s tests -p 'test_full_facility*.py' -v
python -X utf8 -m compileall -q src/aegis_dc
python -X utf8 -m aegis_dc simulate --output evidence/mainline/engineering/03-healthy-site/normal-37432b25
python -X utf8 -m aegis_dc simulate --duration 151 --inputs evidence/mainline/engineering/03-healthy-site/work-inputs-v1.json --output evidence/mainline/engineering/03-healthy-site/work-37432b25
python -X utf8 evidence/mainline/engineering/03-healthy-site/verify_fixtures.py
git diff --check
```

The saved run commands intentionally refuse their existing output directories;
use a new directory for replay. The acceptance command loaded
`scripts/acceptance.py` via `importlib.util.spec_from_file_location` and called
`verify(Path.cwd(), Path.cwd() / 'evidence/mainline/engineering/03-healthy-site/acceptance-37432b25')`.
It returned engineering/evidence/overall PASS and saved its full test log.

No new dependency, real-device action, research model call, training job or
registered mechanism comparison was run. The scoped low-order assumptions,
supported topology, equations, initialization and remaining capabilities are in
[the model description](../../../../docs/mainline/healthy-run-model.md). Full
anomaly/control/backup qualification, delayed/noisy evidence, risk scheduling,
intervention/verification and numerical convergence remain their mainline tickets.

Review corrections after the implementer's resolution are recorded separately in
`review-fixes-bc1b9173/`, `schema-review-fix/` and `latch-review-fix/`. They preserve
the original 37432b25 run/acceptance bytes and their historical source attribution.
Ticket 03 still requires root Standards/Spec and integration acceptance; the
original implementation resolution did not constitute that acceptance.
