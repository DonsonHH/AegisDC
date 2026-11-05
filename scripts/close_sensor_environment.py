"""Run only the two original legacy CLI failures with a declared Python path."""
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from capture_evidence_engineering import file_sha, git_blob_sha, write
from sensor_engineering_checks import require

PROTOCOL = 'docs/mainline/16-sensor-delivery-addendum-v1.json'


def check_original(root, book):
    folder = root / book['original_capture']
    require(file_sha(folder / 'receipt.json') == book['original_receipt_sha256'], 'Original failed receipt changed')
    receipt = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
    require(receipt['engineering_capture'] == book['original_capture_status'] == 'FAIL', 'Original failure cannot become a pass')
    for name, expected in receipt['artifacts'].items():
        require(file_sha(folder / name) == expected, 'Original failed-capture artifact changed: ' + name)
    for group in ('runtime_sources', 'authoring_verification_tools', 'frozen_inputs'):
        for name, expected in receipt[group].items():
            require(file_sha(root / name) == git_blob_sha(root, receipt['execution_commit'], name) == expected,
                    'Original execution source/tool/input drifted: ' + name)
    log = (folder / 'full-check/tests.log').read_text(encoding='utf-8')
    outcomes = [dict(kind=kind, test_id=identifier) for kind, _, identifier in
                re.findall(r'^(ERROR|FAIL): (.+) \(([^)]+)\)$', log, re.MULTILINE)]
    require(outcomes == book['original_results'] and 'No module named aegis_dc' in log,
            'Original full failure differs from the registered environment incident')
    return receipt


def close():
    book = json.loads((ROOT / PROTOCOL).read_text(encoding='utf-8'))
    execution = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip(), 'Freeze the new closure tools first')
    original = check_original(ROOT, book)
    tool_pins = {name: file_sha(ROOT / name) for name in book['new_verification_paths']}
    for name, expected in tool_pins.items():
        require(git_blob_sha(ROOT, execution, name) == expected, 'Closure tool/protocol is not frozen: ' + name)
    folder = ROOT / book['closure_output']
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'cli').mkdir()
    artifacts = ['declaration.json', 'protocol-copy.json', 'tests.log', 'children.json', 'source-guard.json', 'failure.txt']
    artifacts += ['cli/' + str(index) + '.' + stream + '.txt' for index in range(2) for stream in ('stdout', 'stderr')]
    write(folder / 'declaration.json', dict(schema='aegisdc-sensor-environment-closure-declaration-v1',
        declared_artifacts=artifacts, terminal_receipt='receipt.json', runtime_caches='NOT_DELIVERABLE'))
    (folder / 'protocol-copy.json').write_bytes((ROOT / PROTOCOL).read_bytes())
    receipt = dict(schema='aegisdc-sensor-environment-closure-receipt-v1', status='FAIL', execution_commit=execution,
        started_at_utc=datetime.now(timezone.utc).isoformat(), new_verification_tools=tool_pins,
        original_capture_execution=original['execution_commit'], original_capture_status='FAIL',
        original_full_regression_remains='FAIL', global_regression_gate=book['global_regression_gate'],
        full_regression_reruns=0, observation_adapter_reruns=0, new_physical_runs=0,
        registered_research_trials=0, model_calls=0, training_calls=0)
    failure, children, active, stream = '', [], {}, io.StringIO()
    real_run = subprocess.run
    try:
        os.environ['PYTHONPATH'] = os.pathsep.join(str(ROOT / name) for name in book['pythonpath_components'])
        receipt['effective_pythonpath'] = os.environ['PYTHONPATH']
        sys.path.insert(0, str(ROOT / 'tests'))

        class ObservedResult(unittest.TextTestResult):
            def startTest(self, test):
                active['test_id'] = test.id()
                super().startTest(test)

        def observed_run(*args, **kwargs):
            # Observe the real subprocess without changing its command, kwargs or result.
            done = real_run(*args, **kwargs)
            index = len(children)
            require(index < 2, 'The narrow closure spawned extra child processes')
            for name in ('stdout', 'stderr'):
                value = getattr(done, name)
                require(type(value) is str, 'Record the text-mode child output used by the original test')
                (folder / 'cli' / (str(index) + '.' + name + '.txt')).write_text(value, encoding='utf-8', newline='\n')
            children.append(dict(test_id=active['test_id'], argv=done.args, exit_code=done.returncode,
                output_representation='UTF8_TEXT_NORMALIZED_BY_ORIGINAL_SUBPROCESS_TEXT_MODE'))
            return done

        subprocess.run = observed_run
        suite = unittest.defaultTestLoader.loadTestsFromNames([row['test_id'] for row in book['original_results']])
        tested = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=ObservedResult).run(suite)
        subprocess.run = real_run
        receipt['narrow_tests'] = dict(run=tested.testsRun, failures=len(tested.failures), errors=len(tested.errors), skipped=len(tested.skipped))
        require(tested.testsRun == book['test_executions'] == 2 and tested.wasSuccessful() and not tested.skipped,
                'Narrow environment closure failed; retain this new attempt')
        require([row['test_id'] for row in children] == [row['test_id'] for row in book['original_results']], 'Actual CLI execution set differs')
        require(children[0]['exit_code'] == 0 and children[1]['exit_code'] != 0, 'Actual CLI child outcomes differ')
        require((folder / 'cli/0.stderr.txt').read_text(encoding='utf-8') == ''
                and 'Duplicate JSON object key' in (folder / 'cli/1.stderr.txt').read_text(encoding='utf-8'), 'Expected child stderr differs')
        check_original(ROOT, book)
        after = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        require(after == execution and not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip(),
                'Closure source changed during the two tests')
        for name, expected in tool_pins.items():
            require(file_sha(ROOT / name) == expected, 'New closure tool changed during execution: ' + name)
        write(folder / 'source-guard.json', dict(status='PASS', before_commit=execution, after_commit=after,
            observation_execution_commit=original['execution_commit'], original_capture_bytes_unchanged=True,
            original_runtime_tool_input_bytes_unchanged=True, closure_tool_bytes_unchanged=True))
        receipt['status'] = 'PASS_NARROW_ENVIRONMENT_CLOSURE_ONLY'
    except Exception as error:
        failure = traceback.format_exc()
        receipt['failure'] = dict(type=type(error).__name__, message=str(error))
    finally:
        subprocess.run = real_run
        (folder / 'tests.log').write_text(stream.getvalue(), encoding='utf-8', newline='\n')
        (folder / 'failure.txt').write_text(failure, encoding='utf-8', newline='\n')
        write(folder / 'children.json', children)
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
        receipt['missing_declared_artifacts'] = sorted(set(artifacts) - actual)
        receipt['unexpected_durable_artifacts'] = sorted(actual - set(artifacts))
        if receipt['missing_declared_artifacts'] or receipt['unexpected_durable_artifacts']:
            receipt['status'] = 'FAIL'
        receipt['artifacts'] = {name: file_sha(folder / name) for name in sorted(actual)}
        write(folder / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    result = close()
    print(json.dumps({name: result.get(name) for name in ('status', 'execution_commit', 'narrow_tests', 'failure')}))
    raise SystemExit(0 if result['status'] == 'PASS_NARROW_ENVIRONMENT_CLOSURE_ONLY' else 1)
