"""Engineering-only malformed-input and saved-origin checks for recorded dispatch."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from aegis_dc.replay import AttemptReadError, read_attempt, run_recorded
from test_full_loop_replay import online_replay_fixture, start_development_attempt
from test_full_loop_service import _json_new


def main(original):
    model, inputs = online_replay_fixture()
    failures = []
    for label in ('v1-with-dispatch', 'v2-with-legacy-work', 'v2-null-program'):
        bad = deepcopy(inputs)
        if label == 'v1-with-dispatch':
            bad['schema'] = 'aegisdc-facility-replay-inputs-v1'
        elif label == 'v2-with-legacy-work':
            bad['work_requests'] = [{'id': 'legacy-unbound-request'}]
        else:
            bad['dispatch_program'] = None
        output = start_development_attempt(model, bad, label)
        terminal = run_recorded(model, output, inputs=bad, duration_s=1.75, step_s=.01)
        assert terminal['status'] == 'FAILED' and terminal['failure']['stage'] == 'validate_inputs'
        assert terminal['execution_kind'] == 'NOT_STARTED' and not (output / 'trajectory').exists()
        failures.append(dict(case=output.parent.name, label=label, failure=terminal['failure']))
    old = ROOT / 'evidence/mainline/engineering/13-replay/capture-05'
    old_checks = []
    for name in ('defaults', 'defaults-replay', 'explicit', 'explicit-replay'):
        result = read_attempt(old / name)
        assert result['record']['status'] == 'COMPLETED' and result['inputs']['schema'].endswith('-v1')
        assert 'dispatch_program' not in result['run']['inputs']
        old_checks.append(dict(case=name, original_terminal_sha256=result['record_sha256']))
    # A content hash can be valid for altered bytes; the program must also
    # match the independently bound frozen inputs. Never alter the original.
    forged = ROOT / '.work/27-replay-boundary-fixtures' / ('wrong-program-' + uuid4().hex)
    shutil.copytree(original, forged)
    run_path = forged / 'trajectory/run.json'
    run = json.loads(run_path.read_bytes())
    run['inputs']['dispatch_program']['id'] = 'different-saved-program'
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    terminal_path = forged / 'attempt.json'
    terminal = json.loads(terminal_path.read_bytes())
    terminal['artifacts']['trajectory/run.json'] = sha256(run_path.read_bytes()).hexdigest()
    terminal_path.write_text(json.dumps(terminal, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    try:
        read_attempt(forged)
    except AttemptReadError as error:
        assert error.stage == 'trajectory_dispatch_program' and error.artifact == 'trajectory/run.json'
        refusal = dict(stage=error.stage, artifact=error.artifact, message=str(error))
    else:
        raise AssertionError('Hash-consistent wrong saved dispatch program was accepted')
    report = dict(status='PASS', input_refusals=failures, preserved_v1_saved_reads=old_checks,
        forged_saved_origin=forged.relative_to(ROOT).as_posix(), forged_refusal=refusal,
        malformed_record_calls=3, new_simulation_calls=0, new_selector_calls=0, registered_research_trials=0)
    _json_new(forged.parent / 'boundary-result-01.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
