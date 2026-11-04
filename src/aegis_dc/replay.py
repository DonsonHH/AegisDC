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


def _run_recorded(scenario, directory, *, inputs, duration_s=None, step_s=None,
                  retry_of=None, retry_reason=None, replay_of=None, required_source=None,
                  preflight_error=None, attempt_kind='engineering_fixture', research_registration=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    record = dict(schema='aegisdc-facility-attempt-v1', attempt_id=str(uuid4()),
                  attempt_kind=attempt_kind, execution_kind='NOT_STARTED', state_visibility='PRIVATE_PLANT_EVALUATOR_ONLY',
                  research_registration=research_registration, research_trials=0, model_calls=0, training_calls=0,
                  field_calibration='PENDING', research_gain_claim='NOT_ESTABLISHED',
                  source_identity=execution_source_identity(), replay_of=replay_of, retry_of=None)
    _lifecycle(directory, 'STARTED', attempt_id=record['attempt_id'])
    stage = 'freeze_inputs'
    try:
        _write_json(directory / 'scenario-input.json', scenario)
        _write_json(directory / 'inputs.json', inputs)
        _write_json(directory / 'request.json', dict(duration_s=duration_s, maximum_step_s=step_s,
                                                    retry_of=str(retry_of) if retry_of is not None else None,
                                                    retry_reason=retry_reason, attempt_kind=attempt_kind,
                                                    research_registration=research_registration))
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
        stage = 'save_run'
        save_run(result, directory / 'trajectory')
        record.update(status='COMPLETED', failure=None)
    except Exception as error:
        record.update(status='FAILED', failure=dict(stage=stage, type=type(error).__name__, message=str(error)))
    _lifecycle(directory, record['status'], failure=record['failure'])
    record['artifacts'] = {path.relative_to(directory).as_posix(): _file_sha(path)
                           for path in sorted(directory.rglob('*')) if path.is_file() and not _runtime_cache(path)}
    _write_json(directory / 'attempt.json', record)
    return record


def read_attempt(directory):
    """Fresh-read the frozen inputs and verified private trajectory, if any."""
    directory = Path(directory)
    record = _read_json(directory / 'attempt.json')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not _runtime_cache(path)}
    if actual != set(record['artifacts']) | {'attempt.json'}:
        raise ValueError('Unexpected or missing durable attempt artifacts')
    for name, expected in record['artifacts'].items():
        path = directory / name
        if _runtime_cache(name) or not path.resolve().is_relative_to(directory.resolve()) or _file_sha(path) != expected:
            raise ValueError('Attempt artifact hash mismatch: ' + name)
    source = record['source_identity']
    if source['schema'] != 'aegisdc-execution-source-v1' or digest(source['files']) != source['source_tree_sha256']:
        raise ValueError('Inconsistent execution source identity')
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
                scenario=_read_json(directory / 'scenario-input.json'),
                inputs=_read_json(directory / 'inputs.json'),
                request=_read_json(directory / 'request.json'), run=run)


def replay_attempt(original, directory, *, action_commands=None):
    """Re-execute frozen inputs only when runtime bytes and interpreter match."""
    try:
        prior = read_attempt(original)
    except (OSError, ValueError, KeyError) as error:
        return _run_recorded(None, directory, inputs=None,
                             replay_of=dict(requested_directory=str(original)),
                             preflight_error='Invalid replay origin: ' + str(error))
    request = prior['request']
    inputs = deepcopy(prior['inputs'])
    if action_commands is not None:
        inputs['action_commands'] = action_commands
    return _run_recorded(prior['scenario'], directory, inputs=inputs,
                         duration_s=request['duration_s'], step_s=request['maximum_step_s'],
                         required_source=prior['record']['source_identity'],
                         preflight_error=None if prior['record']['status'] == 'COMPLETED'
                         else 'Failed or unfinished origins require an explicit retry, not replay',
                         replay_of=dict(attempt_id=prior['record']['attempt_id'],
                                        attempt_sha256=prior['record_sha256'],
                                        mode='EXACT_REEXECUTION' if action_commands is None
                                        else 'PAIRED_EXOGENOUS_NEW_ENGINEERING_COMMANDS'))
