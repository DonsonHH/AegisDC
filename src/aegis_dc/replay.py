"""Private, versioned engineering attempts; replay recomputes the actual plant.

Frozen fault schedules, controls, configuration and true state belong only to
the evaluator. This module creates no dispatch evidence or research trial.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys
from uuid import uuid4

from patrol_rsi.contracts import digest, strict_json
from .plant import ENGINEERING_COMMAND_PARAMETERS, save_run, simulate_scenario
from .scenario import validate_scenario

ROOT = Path(__file__).resolve().parents[2]
INPUT_SCHEMA = 'aegisdc-facility-replay-inputs-v1'


def _write_json(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def _read_json(path):
    return strict_json(path.read_text(encoding='utf-8'))


def _file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def _runtime_cache(path):
    return '__pycache__' in {part.lower() for part in Path(path).parts} or Path(path).suffix.lower() in {'.pyc', '.pyo'}


def execution_source_identity():
    """Identity of executed runtime bytes and interpreter, excluding caches."""
    paths = sorted((ROOT / 'src/aegis_dc').glob('*.py')) + [ROOT / 'src/patrol_rsi/contracts.py']
    files = {path.relative_to(ROOT).as_posix(): _file_sha(path) for path in paths}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--',
                                             'src/aegis_dc', 'src/patrol_rsi/contracts.py'],
                                            cwd=ROOT, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return dict(schema='aegisdc-execution-source-v1', git_commit=commit,
                implementation_has_changes=dirty, files=files, source_tree_sha256=digest(files),
                python=dict(implementation=platform.python_implementation(), version=sys.version))


def _inputs(value):
    fields = {'schema', 'seed', 'exogenous_events', 'action_commands', 'work_requests'}
    if not isinstance(value, dict) or set(value) != fields or value['schema'] != INPUT_SCHEMA:
        raise ValueError('Use the closed versioned facility replay inputs contract')
    if value['seed'] is not None and type(value['seed']) is not int:
        raise ValueError('Seed must be an explicit integer or null for a frozen event schedule')
    for field in fields - {'schema', 'seed'}:
        if not isinstance(value[field], list):
            raise ValueError('Declare a frozen list for ' + field)
    result = deepcopy(value)
    for row in result['exogenous_events']:
        if not isinstance(row, dict) or row.get('parameter_id') in ENGINEERING_COMMAND_PARAMETERS:
            raise ValueError('Control parameters belong to action_commands, not exogenous_events')
    for field in ('exogenous_events', 'action_commands'):
        result[field].sort(key=lambda row: (row['time_s'], row['parameter_id']))
    result['work_requests'].sort(key=lambda row: (row['time_s'], row['id']))
    return result


def _lifecycle(directory, state, **values):
    row = dict(state=state, recorded_at_utc=datetime.now(timezone.utc).isoformat(), **values)
    with (directory / 'lifecycle.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def run_recorded(scenario, directory, *, inputs, duration_s=None, step_s=None,
                 retry_of=None, retry_reason=None, attempt_kind='engineering_fixture', research_registration=None):
    """Run one new engineering attempt, retaining its exact inputs and failure.

    An existing directory is never touched. Failed validation or execution is
    a terminal FAILED record, never an automatic retry or a completed trace.
    """
    return _run_recorded(scenario, directory, inputs=inputs, duration_s=duration_s, step_s=step_s,
                         retry_of=retry_of, retry_reason=retry_reason, attempt_kind=attempt_kind,
                         research_registration=research_registration)


def record_files(scenario_file, inputs_file, directory, **options):
    """Record exact submitted file bytes, including invalid CLI inputs."""
    return _run_recorded(None, directory, inputs=None,
                         source_files={'scenario': scenario_file, 'inputs': inputs_file}, **options)


def _run_recorded(scenario, directory, *, inputs, duration_s=None, step_s=None,
                  retry_of=None, retry_reason=None, replay_of=None, required_source=None,
                  preflight_error=None, attempt_kind='engineering_fixture', research_registration=None,
                  source_files=None):
    directory = Path(directory)
    try:
        directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise ValueError('Output directory already exists; use a new attempt directory') from error
    record = dict(schema='aegisdc-facility-attempt-v1', attempt_id=str(uuid4()),
                  attempt_kind=attempt_kind, execution_kind='NOT_STARTED', state_visibility='PRIVATE_PLANT_EVALUATOR_ONLY',
                  research_registration=research_registration, research_trials=0, model_calls=0, training_calls=0,
                  field_calibration='PENDING', research_gain_claim='NOT_ESTABLISHED',
                  source_identity=execution_source_identity(), replay_of=replay_of, retry_of=None)
    base_files = ['declaration.json', 'lifecycle.jsonl', 'request.json', 'scenario-input.json', 'inputs.json']
    submitted_files = ['submitted-' + name + '.json' for name in (source_files or {})]
    completed_files = base_files + submitted_files + ['frozen-inputs.json', 'trajectory/run.json',
                      'trajectory/scenario.json', 'trajectory/private-state.jsonl', 'trajectory/balances.jsonl']
    declaration = dict(schema='aegisdc-attempt-declaration-v1', required_when_completed=sorted(completed_files),
                       allowed_before_finalization=sorted(completed_files),
                       terminal_manifest='attempt.json', runtime_caches='NOT_DELIVERABLE',
                       tools='source_identity in terminal manifest; runtime bytes plus exact Python version',
                       incomplete='STARTED without terminal manifest is running or interrupted, never success')
    _write_json(directory / 'declaration.json', declaration)
    _lifecycle(directory, 'STARTED', attempt_id=record['attempt_id'])
    stage = 'freeze_inputs'
    try:
        _write_json(directory / 'request.json', dict(duration_s=duration_s, maximum_step_s=step_s,
                                                    retry_of=str(retry_of) if retry_of is not None else None,
                                                    retry_reason=retry_reason, attempt_kind=attempt_kind,
                                                    research_registration=research_registration))
        supplied, failures = {}, []
        for name, source_file in (source_files or {}).items():
            try:
                raw = Path(source_file).read_bytes()
                (directory / ('submitted-' + name + '.json')).write_bytes(raw)
                supplied[name] = strict_json(raw.decode('utf-8'))
            except (OSError, ValueError) as error:
                failures.append(name + ': ' + str(error))
        scenario = supplied.get('scenario', scenario)
        inputs = supplied.get('inputs', inputs)
        if 'action_commands' in supplied:
            inputs = deepcopy(inputs)
            inputs['action_commands'] = supplied['action_commands']
        _write_json(directory / 'scenario-input.json', scenario)
        _write_json(directory / 'inputs.json', inputs)
        if failures:
            raise ValueError('Cannot load submitted inputs: ' + '; '.join(failures))
        stage = 'attempt_classification'
        if attempt_kind != 'engineering_fixture' or research_registration is not None:
            raise ValueError('Only engineering fixtures execute here; registered research needs the unopened ticket 30 protocol/budget gate')
        stage = 'replay_origin'
        if preflight_error:
            raise ValueError(preflight_error)
        if required_source:
            for field in ('schema', 'files', 'source_tree_sha256', 'python'):
                if record['source_identity'][field] != required_source[field]:
                    raise ValueError('Replay execution source mismatch: ' + field)
            record['replay_source_rule'] = 'EXACT_RUNTIME_BYTES_AND_INTERPRETER'
            record['replay_revision_relationship'] = ('SAME_COMMIT' if required_source['git_commit']
                                                      == record['source_identity']['git_commit']
                                                      else 'DIFFERENT_COMMIT_SAME_RUNTIME_BYTES')
        stage = 'retry_registration'
        if retry_of is not None:
            if not isinstance(retry_reason, str) or not retry_reason.strip():
                raise ValueError('An explicit retry requires a nonempty reason')
            prior = read_attempt(retry_of)
            if prior['record']['status'] != 'FAILED':
                raise ValueError('An explicit retry must reference a finalized FAILED attempt')
            record['retry_of'] = dict(attempt_id=prior['record']['attempt_id'],
                                      attempt_sha256=prior['record_sha256'], reason=retry_reason)
        elif retry_reason is not None:
            raise ValueError('A retry reason requires retry_of')
        stage = 'validate_inputs'
        scenario = deepcopy(validate_scenario(scenario))
        frozen = _inputs(inputs)
        _write_json(directory / 'frozen-inputs.json', frozen)
        parameters = {row['id']: row['value'] for row in scenario['parameters']}
        record.update(seed=frozen['seed'], scenario_sha256=digest(scenario),
                      inputs_sha256=digest(frozen),
                      duration_s=parameters['duration'] if duration_s is None else duration_s,
                      maximum_step_s=parameters['step_time'] if step_s is None else step_s,
                      randomness='NONE; seed is recorded, event schedule is fully frozen')
        stage = 'simulate_scenario'
        record['execution_kind'] = 'ENGINEERING_FIXTURE'
        result = simulate_scenario(scenario, duration_s=duration_s, step_s=step_s,
                                   boundary_events=frozen['exogenous_events'],
                                   action_commands=frozen['action_commands'],
                                   work_requests=frozen['work_requests'])
        stage = 'verify_execution_source'
        after = execution_source_identity()
        if after != record['source_identity'] or result['code_identity']['files'] != after['files']:
            raise ValueError('Execution source changed during the attempt; no reproducible success is certified')
        stage = 'save_run'
        save_run(result, directory / 'trajectory')
        record.update(status='COMPLETED', failure=None)
    except Exception as error:
        record.update(status='FAILED', failure=dict(stage=stage, type=type(error).__name__, message=str(error)))
    _lifecycle(directory, record['status'], failure=record['failure'])
    durable = {path.relative_to(directory).as_posix(): path for path in directory.rglob('*')
               if path.is_file() and not _runtime_cache(path)}
    if not set(durable) <= set(declaration['allowed_before_finalization']) \
            or record['status'] == 'COMPLETED' and set(durable) != set(declaration['required_when_completed']):
        raise ValueError('Durable output set differs from the initial attempt declaration')
    record['artifacts'] = {name: _file_sha(path) for name, path in sorted(durable.items())}
    _write_json(directory / 'attempt.json', record)
    return record


def read_attempt(directory):
    """Fresh-read the frozen inputs and verified private trajectory, if any."""
    directory = Path(directory)
    if not (directory / 'attempt.json').exists():
        lifecycle = [strict_json(line) for line in (directory / 'lifecycle.jsonl').read_text(encoding='utf-8').splitlines()]
        return dict(record=dict(schema='aegisdc-unfinalized-attempt-v1',
                                status='UNFINALIZED_RUNNING_OR_INTERRUPTED',
                                attempt_id=lifecycle[0].get('attempt_id') if lifecycle else None),
                    record_sha256=None, scenario=None, inputs=None, submitted_inputs=None,
                    request=None, run=None, integrity='UNFINALIZED', lifecycle=lifecycle)
    record = _read_json(directory / 'attempt.json')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not _runtime_cache(path)}
    if actual != set(record['artifacts']) | {'attempt.json'}:
        raise ValueError('Unexpected or missing durable attempt artifacts')
    for name, expected in record['artifacts'].items():
        path = directory / name
        if _runtime_cache(name) or not path.resolve().is_relative_to(directory.resolve()) or _file_sha(path) != expected:
            raise ValueError('Attempt artifact hash mismatch: ' + name)
    declaration = _read_json(directory / 'declaration.json')
    if not set(record['artifacts']) <= set(declaration['allowed_before_finalization']) \
            or record['status'] == 'COMPLETED' and set(record['artifacts']) != set(declaration['required_when_completed']):
        raise ValueError('Durable artifacts differ from the initial declaration')
    source = record['source_identity']
    if source['schema'] != 'aegisdc-execution-source-v1' or digest(source['files']) != source['source_tree_sha256']:
        raise ValueError('Inconsistent execution source identity')
    lifecycle = [strict_json(line) for line in (directory / 'lifecycle.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(lifecycle) != 2 or [row['state'] for row in lifecycle] != ['STARTED', record['status']] \
            or lifecycle[0]['attempt_id'] != record['attempt_id'] or lifecycle[-1]['failure'] != record['failure']:
        raise ValueError('Terminal attempt and append-only lifecycle disagree')
    run = None
    if record['status'] == 'COMPLETED':
        folder = directory / 'trajectory'
        run = _read_json(folder / 'run.json')
        run.update(source_config=_read_json(folder / 'scenario.json'),
                   trace=[strict_json(line) for line in (folder / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()],
                   balances=[strict_json(line) for line in (folder / 'balances.jsonl').read_text(encoding='utf-8').splitlines()])
        if run['code_identity']['files'] != source['files'] or run['scenario_sha256'] != record['scenario_sha256']:
            raise ValueError('Private trajectory and frozen execution source/config identity differ')
    return dict(record=record, record_sha256=_file_sha(directory / 'attempt.json'),
                scenario=_read_json(directory / 'scenario-input.json') if (directory / 'scenario-input.json').exists() else None,
                inputs=_read_json(directory / ('frozen-inputs.json' if (directory / 'frozen-inputs.json').exists()
                                               else 'inputs.json')) if (directory / 'inputs.json').exists() else None,
                submitted_inputs=_read_json(directory / 'inputs.json') if (directory / 'inputs.json').exists() else None,
                request=_read_json(directory / 'request.json'), run=run)


def replay_attempt(original, directory, *, action_commands=None):
    """Re-execute frozen inputs only when runtime bytes and interpreter match."""
    try:
        prior = read_attempt(original)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _run_recorded(None, directory, inputs=None,
                             replay_of=dict(requested_directory=str(original)),
                             preflight_error='Invalid replay origin: ' + str(error))
    if prior['record']['status'] == 'UNFINALIZED_RUNNING_OR_INTERRUPTED':
        return _run_recorded(None, directory, inputs=None,
                             replay_of=dict(requested_directory=str(original)),
                             preflight_error='Unfinalized origin is running or interrupted; no completed replay input is certified')
    if prior['record']['status'] != 'COMPLETED':
        return _run_recorded(prior['scenario'], directory, inputs=prior['inputs'],
                             replay_of=dict(attempt_id=prior['record']['attempt_id'], attempt_sha256=prior['record_sha256']),
                             preflight_error='Failed origins require an explicit retry, not replay')
    request = prior['request']
    inputs = deepcopy(prior['inputs'])
    command_file = isinstance(action_commands, (str, Path))
    if action_commands is not None and not command_file:
        inputs['action_commands'] = action_commands
    return _run_recorded(prior['scenario'], directory, inputs=inputs,
                         duration_s=request['duration_s'], step_s=request['maximum_step_s'],
                         required_source=prior['record']['source_identity'],
                         preflight_error=None if prior['record']['status'] == 'COMPLETED'
                         else 'Failed or unfinished origins require an explicit retry, not replay',
                         replay_of=dict(attempt_id=prior['record']['attempt_id'],
                                        attempt_sha256=prior['record_sha256'],
                                        mode='EXACT_REEXECUTION' if action_commands is None
                                        else 'PAIRED_EXOGENOUS_NEW_ENGINEERING_COMMANDS'),
                         source_files={'action_commands': action_commands} if command_file else None)
