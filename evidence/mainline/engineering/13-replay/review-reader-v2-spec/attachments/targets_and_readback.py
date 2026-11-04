"""Selected refusal tests and immutable saved trajectories only."""
from contextlib import redirect_stdout, redirect_stderr
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(r'C:/Users/Donson/Documents/ChatGPT/Renly/.work/worktrees/full-site-13')
OUT = Path(__file__).resolve().parent
CAPTURE = ROOT / 'evidence/mainline/engineering/13-replay/capture-04'
receipt = json.loads((CAPTURE / 'receipt.json').read_bytes())
prior = json.loads((OUT / 'independent-check-01.json').read_bytes())
names = set(prior['guarded_sha256'])
names |= {str((CAPTURE / name).relative_to(ROOT)).replace('\\', '/') for name in receipt['artifacts']}
names |= set(receipt['prior_durable_files'])
identity = lambda: {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(names)}
before = identity()
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT / 'tests')]
from aegis_dc import replay
calls = []
def no_plant(*args, **kwargs):
    calls.append(kwargs)
    raise AssertionError('No physical execution allowed in this review')
replay.simulate_scenario = no_plant
import test_replay_reader_authority as tests
methods = [name for name in dir(tests.ReplayReaderAuthorityTests)
           if name.startswith('test_') and name != 'test_failed_request_can_retain_invalid_declared_duration_without_claiming_completion']
stream = io.StringIO()
suite = unittest.TestSuite(tests.ReplayReaderAuthorityTests(name) for name in methods)
with redirect_stdout(stream), redirect_stderr(stream):
    tested = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
log = stream.getvalue()
(OUT / 'selected-tests.log').write_text(log, encoding='utf-8', newline='\n')
assert tested.testsRun == 7 and tested.wasSuccessful() and not tested.skipped
saved = {folder.name: replay.read_attempt(folder) for folder in CAPTURE.iterdir()
         if folder.is_dir() and (folder / 'attempt.json').exists()}
completed = [name for name, row in saved.items() if row['record']['status'] == 'COMPLETED']
failed = [name for name, row in saved.items() if row['record']['status'] == 'FAILED']
assert len(saved) == 18 and len(completed) == 6 and len(failed) == 12
for original, repeated in [('normal-600s', 'normal-600s-replay'), ('combined-episode-CLI', 'combined-episode-CLI-replay')]:
    a, b = saved[original]['run'], saved[repeated]['run']
    for key in ('trace', 'balances', 'events', 'work_records', 'inputs'):
        assert a[key] == b[key], (original, key)
a, b = saved['causal-baseline']['run'], saved['causal-command']['run']
assert a['summary']['demand_service_unit_s'] == b['summary']['demand_service_unit_s'] == 2
assert a['summary']['delivered_service_unit_s'] == 2 and b['summary']['delivered_service_unit_s'] == 1
assert a['trace'] != b['trace']
assert before == identity() and all(before[name] == value for name, value in prior['guarded_sha256'].items())
assert not calls
result = dict(candidate=prior['candidate'], execution=prior['execution'], delivery=prior['delivery'],
    selected_tests=dict(run=tested.testsRun, failures=len(tested.failures), errors=len(tested.errors), skipped=0,
                        methods=methods, log_sha256=sha256(log.encode()).hexdigest()),
    saved_readback=dict(terminal_attempts=18, completed=6, failed=12, exact_pairs=2, causal_offered_each=2,
                        causal_delivered=[2, 1], plant_rerun=False, full_suite_rerun=False),
    source_and_original_guard='PASS', guarded_files=len(names), guarded_sha256=before,
    plant_calls=0, full_suite_runs=0, research_trials=0, model_calls=0)
with (OUT / 'targets-and-readback-01.json').open('x', encoding='utf-8', newline='\n') as target:
    target.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key:value for key,value in result.items() if key != 'guarded_sha256'}))
