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
from .business_endpoints import evaluate_business_endpoints, validate_business_program
from .composite_endpoints import execution_input_binding
from .cost_endpoints import _audit_timing
from .plant import (ENGINEERING_COMMAND_PARAMETERS, _action_commands, save_run, simulate_scenario,
                    validate_boundary_events)
from .scenario import validate_scenario
from .replay_format import (LIFECYCLE_SCHEMA, balance_rows, balance_time_axis, bind_execution_inputs, completed_request, declaration_header,
                            engineering_run_header, lifecycle_rows, terminal_header, trace_rows)

ROOT = Path(__file__).resolve().parents[2]
INPUT_SCHEMA = 'aegisdc-facility-replay-inputs-v1'
ONLINE_INPUT_SCHEMA = 'aegisdc-facility-replay-inputs-v2'
BUSINESS_INPUT_SCHEMA = 'aegisdc-facility-replay-inputs-v3'
RUNTIME_IDENTITY_FIELDS = ('schema', 'files', 'source_tree_sha256', 'python')
REVISION_FIELDS = ('git_commit', 'implementation_has_changes')
RUN_SOURCE_FIELDS = ('files', 'source_tree_sha256', *REVISION_FIELDS)
COMPOSITE_RESULT_SCHEMA = 'aegisdc-business-composite-result-v1'
STANDALONE_COST_SCHEMAS = ('aegisdc-business-cost-result-v1', 'aegisdc-business-cost-result-v2')
AUDIT_TIMING_FIELDS = (('elapsed_ns', 'selector_elapsed_ns'),
                       ('condition_assessment_elapsed_ns', 'condition_assessment_elapsed_ns'))


class AttemptReadError(ValueError):
    """An origin-validation refusal with a durable diagnostic stage and artifact."""

    def __init__(self, stage, artifact, message):
        super().__init__(message)
        self.stage, self.artifact = stage, artifact


def _checked_read(directory, name, stage, validator=lambda value: value, *, lines=False):
    try:
        value = ([strict_json(line) for line in (directory / name).read_text(encoding='utf-8').splitlines()]
                 if lines else _read_json(directory / name))
        return validator(value)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, ArithmeticError) as error:
        raise AttemptReadError(stage, name, str(error)) from error


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
                python=dict(implementation=platform.python_implementation(), version=sys.version,
                            executable_sha256=_file_sha(Path(sys.executable))))


def _inputs(value):
    fields = {'schema', 'seed', 'exogenous_events', 'action_commands', 'work_requests'}
    if not isinstance(value, dict) or value.get('schema') not in (INPUT_SCHEMA, ONLINE_INPUT_SCHEMA, BUSINESS_INPUT_SCHEMA):
        raise ValueError('Use the closed versioned facility replay inputs contract')
    online = value['schema'] != INPUT_SCHEMA
    business = value['schema'] == BUSINESS_INPUT_SCHEMA
    program_fields = ({'dispatch_program'} if online else set()) | ({'business_program'} if business else set())
    if set(value) != fields | program_fields:
        raise ValueError('Use the closed versioned facility replay inputs contract')
    if value['seed'] is not None and type(value['seed']) is not int:
        raise ValueError('Seed must be an explicit integer or null for a frozen event schedule')
    for field in fields - {'schema', 'seed'}:
        if not isinstance(value[field], list):
            raise ValueError('Declare a frozen list for ' + field)
    if online and (not isinstance(value['dispatch_program'], dict) or value['work_requests']):
        raise ValueError('Online replay requires a dispatch program and empty legacy work requests')
    if business and not isinstance(value['business_program'], dict):
        raise ValueError('Business replay requires a private business program')
    result = deepcopy(value)
    for row in result['exogenous_events']:
        if not isinstance(row, dict) or row.get('parameter_id') in ENGINEERING_COMMAND_PARAMETERS:
            raise ValueError('Control parameters belong to action_commands, not exogenous_events')
    if business:
        # The diagnostic reference binds the submitted schedule, before plant normalization.
        return result
    for field in ('exogenous_events', 'action_commands'):
        result[field].sort(key=lambda row: (row['time_s'], row['parameter_id']))
    result['work_requests'].sort(key=lambda row: (row['time_s'], row['id']))
    return result


def _lifecycle(directory, state, **values):
    row = dict(schema=LIFECYCLE_SCHEMA, state=state, recorded_at_utc=datetime.now(timezone.utc).isoformat(), **values)
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
                  source_files=None, origin_directory=None, preflight_stage='replay_origin', origin_artifact=None):
    directory = Path(directory)
    try:
        directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise ValueError('Output directory already exists; use a new attempt directory') from error
    snapshots = {}
    if origin_directory is not None:
        origin = Path(origin_directory)
        for name in dict.fromkeys(['attempt.json', 'declaration.json', 'lifecycle.jsonl'] + ([origin_artifact] if origin_artifact else [])):
            try:
                path = origin / name
                if path.resolve().is_relative_to(origin.resolve()) and path.is_file():
                    snapshots['origin/' + name] = path.read_bytes()
            except OSError as error:
                preflight_error = (preflight_error + '; ' if preflight_error else '') + 'Origin snapshot ' + name + ': ' + str(error)
                preflight_stage = 'replay_origin.snapshot'
        if required_source and not preflight_error:
            try:
                raw_record = snapshots['origin/attempt.json']
                if sha256(raw_record).hexdigest() != replay_of['attempt_sha256']:
                    raise ValueError('Origin terminal changed after validation')
                expected = strict_json(raw_record.decode('utf-8'))['artifacts']
                for name in ('declaration.json', 'lifecycle.jsonl'):
                    if sha256(snapshots['origin/' + name]).hexdigest() != expected[name]:
                        raise ValueError('Origin ' + name + ' changed after validation')
            except (KeyError, ValueError) as error:
                preflight_error, preflight_stage = str(error), 'replay_origin.snapshot'
    record = dict(schema='aegisdc-facility-attempt-v2', attempt_id=str(uuid4()),
                  attempt_kind=attempt_kind, execution_kind='NOT_STARTED', state_visibility='PRIVATE_PLANT_EVALUATOR_ONLY',
                  research_registration=research_registration, research_trials=0, model_calls=0, training_calls=0,
                  field_calibration='PENDING', research_gain_claim='NOT_ESTABLISHED',
                  source_identity=execution_source_identity(), replay_of=replay_of, retry_of=None,
                  origin_validation=dict(directory=str(origin_directory), stage=preflight_stage) if origin_directory is not None else None)
    base_files = ['declaration.json', 'lifecycle.jsonl', 'request.json', 'scenario-input.json', 'inputs.json']
    submitted_files = ['submitted-' + name + '.json' for name in (source_files or {})]
    completed_files = base_files + submitted_files + list(snapshots) + ['frozen-inputs.json', 'trajectory/run.json',
                      'trajectory/scenario.json', 'trajectory/private-state.jsonl', 'trajectory/balances.jsonl']
    declaration = dict(schema='aegisdc-attempt-declaration-v2', required_when_completed=sorted(completed_files),
                       allowed_before_finalization=sorted(completed_files),
                       lifecycle_schema=LIFECYCLE_SCHEMA, origin_snapshot_files=sorted(snapshots),
                       terminal_manifest='attempt.json', runtime_caches='NOT_DELIVERABLE',
                       tools='source_identity in terminal manifest; runtime bytes plus exact Python version',
                       incomplete='STARTED without terminal manifest is running or interrupted, never success')
    _write_json(directory / 'declaration.json', declaration)
    _lifecycle(directory, 'STARTED', attempt_id=record['attempt_id'])
    stage = 'freeze_inputs'
    try:
        for name, raw in snapshots.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)
        _write_json(directory / 'request.json', dict(duration_s=duration_s, maximum_step_s=step_s,
                                                    retry_of=str(retry_of) if retry_of is not None else None,
                                                    retry_reason=retry_reason, attempt_kind=attempt_kind,
                                                    research_registration=research_registration,
                                                    source_files={name: str(path) for name, path in (source_files or {}).items()}))
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
        stage = preflight_stage
        if preflight_error:
            raise ValueError(preflight_error)
        if required_source:
            stage = 'replay_origin.source_identity'
            for field in RUNTIME_IDENTITY_FIELDS:
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
        online_options = {name: frozen[name] for name in ('dispatch_program', 'business_program') if name in frozen}
        record.update(seed=frozen['seed'], scenario_sha256=digest(scenario),
                      inputs_sha256=digest(frozen),
                      duration_s=parameters['duration'] if duration_s is None else duration_s,
                      maximum_step_s=parameters['step_time'] if step_s is None else step_s,
                      randomness=('DECLARED_PRODUCER_REALIZATIONS_FROZEN_IN_DISPATCH_PROGRAM' if online_options else
                                  'NONE; seed is recorded, event schedule is fully frozen'))
        stage = 'simulate_scenario'
        record['execution_kind'] = 'ENGINEERING_FIXTURE'
        result = simulate_scenario(scenario, duration_s=duration_s, step_s=step_s,
                                   boundary_events=frozen['exogenous_events'],
                                   action_commands=frozen['action_commands'],
                                   work_requests=frozen['work_requests'], **online_options)
        stage = 'verify_execution_source'
        after = execution_source_identity()
        if after != record['source_identity'] or result['code_identity']['files'] != after['files']:
            raise ValueError('Execution source changed during the attempt; no reproducible success is certified')
        stage = 'save_run'
        save_run(result, directory / 'trajectory')
        record.update(status='COMPLETED', failure=None)
    except Exception as error:
        record.update(status='FAILED', failure=dict(stage=stage, type=type(error).__name__, message=str(error)))
    _lifecycle(directory, record['status'], failure=record['failure'], attempt_id=record['attempt_id'])
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
    try:
        return _read_attempt(Path(directory))
    except AttemptReadError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, ArithmeticError) as error:
        raise AttemptReadError('origin_structure', None, str(error)) from error


def _bind_business_trajectory(record, scenario, frozen, request, execution_inputs, run):
    artifact = 'trajectory/run.json'
    inputs, duration = run['inputs'], execution_inputs['duration_s']
    try:
        parameters = {row['id']: row for row in scenario['parameters']}
        runtime = scenario['runtime']
        events = validate_boundary_events(scenario, frozen['exogenous_events'], duration_s=duration)
        commands = _action_commands(frozen['action_commands'], parameters, duration, model=runtime['model'],
                                    control_profile=runtime.get('local_control_profile'),
                                    reserve_profile=runtime.get('reserve_profile'))
        times = {name: float(value) if request[name] is not None else value for name, value in execution_inputs.items()}
        expected = dict(**times, boundary_events=events, work_requests=frozen['work_requests'],
                        dispatch_program=frozen['dispatch_program'], business_program=frozen['business_program'])
        if commands:
            expected['action_commands'] = commands
        if ('business_program' in run or digest(inputs) != digest(expected)
                or digest(run['source_config']) != record['scenario_sha256'] or run['facility_id'] != scenario['id']
                or digest(run['summary']['duration_s']) != digest(times['duration_s'])):
            raise ValueError('Actual business trajectory inputs, facility or window differ from the frozen attempt')
        program = validate_business_program(
            frozen['business_program'], scenario['id'], duration, frozen['dispatch_program'],
            scenario=scenario, boundary_events=frozen['exogenous_events'],
            execution_binding=execution_input_binding(scenario, inputs))
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, ArithmeticError) as error:
        raise AttemptReadError('trajectory_business_program', artifact, str(error)) from error
    try:
        counts = {'scenario.json': 1, 'private-state.jsonl': len(run['trace']), 'balances.jsonl': len(run['balances'])}
        expected = {name: dict(sha256=record['artifacts']['trajectory/' + name], records=count)
                    for name, count in counts.items()}
        if digest(run['artifacts']) != digest(expected):
            raise ValueError('Private trajectory inventory differs from its verified artifacts')
        if digest(run['business_evaluation']) != digest(evaluate_business_endpoints(run, program)):
            raise ValueError('Saved business result differs from re-extracted private endpoints')
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, ArithmeticError) as error:
        raise AttemptReadError('trajectory_business_result', artifact, str(error)) from error


def _read_attempt(directory):
    directory = Path(directory)
    if not (directory / 'attempt.json').exists():
        declaration = None
        if (directory / 'declaration.json').exists():
            declaration = _checked_read(directory, 'declaration.json', 'declaration_header', declaration_header)
        elif not (directory / 'lifecycle.jsonl').exists():
            raise ValueError('Unknown replay origin; no supported declaration or lifecycle record')
        lifecycle = (_checked_read(directory, 'lifecycle.jsonl', 'lifecycle', lifecycle_rows, lines=True)
                     if (directory / 'lifecycle.jsonl').exists() else [])
        if declaration is None and not lifecycle:
            raise ValueError('Unknown replay origin; no supported declaration or STARTED lifecycle')
        if declaration and declaration['schema'].endswith('-v2') and any(row.get('schema') != LIFECYCLE_SCHEMA for row in lifecycle):
            raise AttemptReadError('lifecycle', 'lifecycle.jsonl', 'v2 declaration requires explicitly versioned lifecycle rows')
        if declaration and declaration['schema'].endswith('-v1') and any('schema' in row for row in lifecycle):
            raise AttemptReadError('lifecycle', 'lifecycle.jsonl', 'Historical v1 declaration requires its known legacy lifecycle rows')
        return dict(record=dict(schema='aegisdc-unfinalized-attempt-v1',
                                status='UNFINALIZED_RUNNING_OR_INTERRUPTED',
                                attempt_id=lifecycle[0].get('attempt_id') if lifecycle else None),
                    record_sha256=None, scenario=None, inputs=None, submitted_inputs=None,
                    request=None, execution_inputs=None, run=None, integrity='UNFINALIZED', lifecycle=lifecycle)
    record = _checked_read(directory, 'attempt.json', 'terminal_header', terminal_header)
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and not _runtime_cache(path)}
    if actual != set(record['artifacts']) | {'attempt.json'}:
        raise ValueError('Unexpected or missing durable attempt artifacts')
    for name, expected in record['artifacts'].items():
        path = directory / name
        if _runtime_cache(name) or not path.resolve().is_relative_to(directory.resolve()) or _file_sha(path) != expected:
            raise ValueError('Attempt artifact hash mismatch: ' + name)
    declaration = _checked_read(directory, 'declaration.json', 'declaration_header', declaration_header)
    if record['schema'].rsplit('-', 1)[1] != declaration['schema'].rsplit('-', 1)[1]:
        raise AttemptReadError('declaration_header', 'declaration.json', 'Terminal and declaration versions differ')
    if not set(record['artifacts']) <= set(declaration['allowed_before_finalization']) \
            or record['status'] == 'COMPLETED' and set(record['artifacts']) != set(declaration['required_when_completed']):
        raise ValueError('Durable artifacts differ from the initial declaration')
    source = record['source_identity']
    if source['schema'] != 'aegisdc-execution-source-v1' or digest(source['files']) != source['source_tree_sha256']:
        raise ValueError('Inconsistent execution source identity')
    lifecycle = _checked_read(directory, 'lifecycle.jsonl', 'lifecycle', lifecycle_rows, lines=True)
    if record['schema'].endswith('-v2') and any(row.get('schema') != LIFECYCLE_SCHEMA for row in lifecycle):
        raise AttemptReadError('lifecycle', 'lifecycle.jsonl', 'v2 terminal requires explicitly versioned lifecycle rows')
    if record['schema'].endswith('-v1') and any('schema' in row for row in lifecycle):
        raise AttemptReadError('lifecycle', 'lifecycle.jsonl', 'Historical v1 terminal requires its known legacy lifecycle rows')
    if len(lifecycle) != 2 or [row['state'] for row in lifecycle] != ['STARTED', record['status']] \
            or lifecycle[0]['attempt_id'] != record['attempt_id'] or lifecycle[-1]['failure'] != record['failure']:
        raise ValueError('Terminal attempt and append-only lifecycle disagree')
    scenario = _checked_read(directory, 'scenario-input.json', 'scenario_input') if (directory / 'scenario-input.json').exists() else None
    submitted = _checked_read(directory, 'inputs.json', 'submitted_input') if (directory / 'inputs.json').exists() else None
    frozen = _checked_read(directory, 'frozen-inputs.json', 'frozen_input', _inputs) if (directory / 'frozen-inputs.json').exists() else submitted
    request = (_checked_read(directory, 'request.json', 'request', completed_request if record['status'] == 'COMPLETED' else lambda value: value)
               if (directory / 'request.json').exists() else None)
    if 'inputs_sha256' in record and digest(frozen) != record['inputs_sha256']:
        raise ValueError('Frozen input identity differs from the executed attempt')
    if 'scenario_sha256' in record and digest(scenario) != record['scenario_sha256']:
        raise ValueError('Frozen scenario identity differs from the executed attempt')
    run, execution_inputs = None, None
    if record['status'] == 'COMPLETED':
        if request is None:
            raise AttemptReadError('request', 'request.json', 'Completed attempt lacks its request')
        run = _checked_read(directory, 'trajectory/run.json', 'trajectory', engineering_run_header)
        run.update(source_config=_checked_read(directory, 'trajectory/scenario.json', 'trajectory_scenario'),
                   trace=_checked_read(directory, 'trajectory/private-state.jsonl', 'trajectory_trace', trace_rows, lines=True),
                   balances=_checked_read(directory, 'trajectory/balances.jsonl', 'trajectory_balances', balance_rows, lines=True))
        try:
            execution_inputs = bind_execution_inputs(request, scenario, record, run['inputs'])
        except ValueError as error:
            raise AttemptReadError('request', 'request.json', str(error)) from error
        try:
            balance_time_axis(run['balances'], run['trace'], **execution_inputs)
        except ValueError as error:
            raise AttemptReadError('trajectory_balances', 'trajectory/balances.jsonl', str(error)) from error
        if any(run['code_identity'][field] != source[field] for field in RUN_SOURCE_FIELDS) \
                or run['scenario_sha256'] != record['scenario_sha256'] or run['source_config'] != scenario:
            raise ValueError('Private trajectory and frozen execution source/config identity differ')
        actual_inputs = run['inputs']
        if frozen['schema'] == BUSINESS_INPUT_SCHEMA:
            if not record['schema'].endswith('-v2') or digest(submitted) != digest(frozen) or record['seed'] != frozen['seed']:
                raise AttemptReadError('submitted_input', 'inputs.json',
                                       'Submitted business inputs or seed differ from the frozen v3 attempt')
            _bind_business_trajectory(record, scenario, frozen, request, execution_inputs, run)
        else:
            if {'business_program', 'business_evaluation'} & (set(actual_inputs) | set(run)):
                raise AttemptReadError('trajectory_business_program', 'trajectory/run.json',
                                       'Legacy replay inputs cannot carry a business program or result')
            if isinstance(submitted, dict) and {'business_program', 'business_evaluation'} & set(submitted):
                raise AttemptReadError('submitted_input', 'inputs.json', 'Legacy submitted inputs cannot carry business fields')
            if actual_inputs['boundary_events'] != frozen['exogenous_events'] \
                    or actual_inputs.get('action_commands', []) != frozen['action_commands'] \
                    or actual_inputs['work_requests'] != frozen['work_requests'] \
                    or actual_inputs['duration_s'] != record['duration_s'] \
                    or actual_inputs['maximum_step_s'] != record['maximum_step_s']:
                raise ValueError('Private trajectory input identity differs from the frozen attempt')
        if ('dispatch_program' in actual_inputs) != ('dispatch_program' in frozen) or (
            'dispatch_program' in frozen and digest(actual_inputs['dispatch_program']) != digest(frozen['dispatch_program'])
        ):
            raise AttemptReadError('trajectory_dispatch_program', 'trajectory/run.json',
                                   'Private trajectory dispatch program differs from the frozen attempt')
    return dict(record=record, record_sha256=_file_sha(directory / 'attempt.json'),
                scenario=scenario, inputs=frozen, submitted_inputs=submitted,
                request=request, execution_inputs=execution_inputs, run=run)


def replay_attempt(original, directory, *, action_commands=None):
    """Re-execute frozen inputs only when runtime bytes and interpreter match."""
    try:
        prior = read_attempt(original)
    except AttemptReadError as error:
        return _run_recorded(None, directory, inputs=None,
                             replay_of=dict(requested_directory=str(original)),
                             preflight_error='Invalid replay origin: ' + str(error),
                             origin_directory=original, origin_artifact=error.artifact,
                             preflight_stage='replay_origin.' + error.stage)
    if prior['record']['status'] == 'UNFINALIZED_RUNNING_OR_INTERRUPTED':
        return _run_recorded(None, directory, inputs=None,
                             replay_of=dict(requested_directory=str(original)),
                             preflight_error='Unfinalized origin is running or interrupted; no completed replay input is certified',
                             origin_directory=original, preflight_stage='replay_origin.unfinalized_setup')
    if prior['record']['status'] != 'COMPLETED':
        return _run_recorded(prior['scenario'], directory, inputs=prior['inputs'],
                             replay_of=dict(attempt_id=prior['record']['attempt_id'], attempt_sha256=prior['record_sha256']),
                             preflight_error='Failed origins require an explicit retry, not replay', origin_directory=original,
                             preflight_stage='replay_origin.failed_origin')
    execution_inputs = prior['execution_inputs']
    inputs = deepcopy(prior['inputs'])
    if inputs['schema'] == BUSINESS_INPUT_SCHEMA:
        # Reuse the original request so plant defaults keep their native JSON number type.
        execution_inputs = prior['request']
    command_file = isinstance(action_commands, (str, Path))
    if action_commands is not None and not command_file:
        inputs['action_commands'] = action_commands
    return _run_recorded(prior['scenario'], directory, inputs=inputs,
                         duration_s=execution_inputs['duration_s'], step_s=execution_inputs['maximum_step_s'],
                         required_source=prior['record']['source_identity'],
                         origin_directory=original,
                         replay_of=dict(attempt_id=prior['record']['attempt_id'],
                                        attempt_sha256=prior['record_sha256'],
                                        mode='EXACT_REEXECUTION' if action_commands is None
                                        else 'PAIRED_EXOGENOUS_NEW_ENGINEERING_COMMANDS'),
                         source_files={'action_commands': action_commands} if command_file else None)


def _comparison_identity(original, replayed):
    first, second = original['record'], replayed['record']
    expected_link = dict(attempt_id=first.get('attempt_id'), attempt_sha256=original['record_sha256'],
                         mode='EXACT_REEXECUTION')
    if first['status'] != 'COMPLETED' or second['status'] != 'COMPLETED' \
            or second['attempt_id'] == first['attempt_id'] or second['replay_of'] != expected_link:
        raise AttemptReadError('comparison_origin', 'attempt.json',
                               'Comparison requires two completed attempts linked by exact replay')
    if second['schema'].endswith('-v2'):
        snapshots = {'attempt.json': original['record_sha256'],
                     **{name: first['artifacts'][name] for name in ('declaration.json', 'lifecycle.jsonl')}}
        if any(second['artifacts'].get('origin/' + name) != value for name, value in snapshots.items()):
            raise AttemptReadError('comparison_origin', 'attempt.json', 'Replay origin snapshot differs')
    if any(digest(original[field]) != digest(replayed[field]) for field in ('scenario', 'inputs', 'execution_inputs')):
        raise AttemptReadError('comparison_input', 'frozen-inputs.json', 'Replay scenario or frozen execution inputs differ')
    left, right = first['source_identity'], second['source_identity']
    relationship = ('SAME_COMMIT' if left['git_commit'] == right['git_commit']
                    else 'DIFFERENT_COMMIT_SAME_RUNTIME_BYTES')
    if second.get('replay_source_rule') != 'EXACT_RUNTIME_BYTES_AND_INTERPRETER' \
            or second.get('replay_revision_relationship') != relationship \
            or any(left[key] != right[key] for key in RUNTIME_IDENTITY_FIELDS):
        raise AttemptReadError('comparison_source', 'attempt.json', 'Replay runtime bytes or interpreter identity differs')
    return relationship, [key for key in REVISION_FIELDS if left[key] != right[key]]


def _timing_slots(run, cost, cost_path):
    """Identify only declared timing values after checking the unmodified raw copies."""
    audits = run.get('policy_computation_audit', [])
    if not isinstance(audits, list) or any(not isinstance(row, dict) for row in audits):
        raise ValueError('Malformed policy computation audit')
    computation = None
    if cost is not None:
        computation = cost['computation']
        if digest(computation['audit_record_details']) != digest(audits):
            raise ValueError('Cost audit is not an exact copy of the raw policy audit')
    slots = []
    for key, aggregate in AUDIT_TIMING_FIELDS:
        # This also checks the type and sign of every present raw value, including partial coverage.
        expected = _audit_timing(audits, key)
        for index, row in enumerate(audits):
            if key in row:
                slots.append((f'policy_computation_audit[{index}].{key}', row, key))
                if computation is not None:
                    slots.append((f'{cost_path}.computation.audit_record_details[{index}].{key}',
                                  computation['audit_record_details'][index], key))
        if computation is not None:
            measurement = computation[aggregate]
            if digest(measurement) != digest(expected):
                raise ValueError('Cost timing aggregate disagrees with the raw policy audit: ' + aggregate)
            if measurement['value'] is not None:
                slots.append((f'{cost_path}.computation.{aggregate}.value', measurement, 'value'))
    return slots


def _comparison_run(attempt, revision_fields):
    run = deepcopy(attempt['run'])
    evaluation = run.get('business_evaluation')
    cost, cost_path = None, None
    source_copies = {'code_identity': run['code_identity']}
    if evaluation is not None:
        source_copies['business_evaluation.execution_code_identity'] = evaluation['execution_code_identity']
        if evaluation['schema'] == COMPOSITE_RESULT_SCHEMA:
            for name in ('diagnostic', 'instance_closure', 'costs'):
                source_copies[f'business_evaluation.components.{name}.execution_code_identity'] = \
                    evaluation['components'][name]['execution_code_identity']
            cost, cost_path = evaluation['components']['costs'], 'business_evaluation.components.costs'
        elif evaluation['schema'] in STANDALONE_COST_SCHEMAS:
            cost, cost_path = evaluation, 'business_evaluation'
    expected = digest(run['code_identity'])
    if any(digest(identity) != expected for identity in source_copies.values()):
        raise AttemptReadError('comparison_source', 'trajectory/run.json', 'Business execution source copy differs')
    try:
        slots = _timing_slots(run, cost, cost_path)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, ArithmeticError) as error:
        raise AttemptReadError('comparison_timing', 'trajectory/run.json', str(error)) from error
    times = {}
    for path, row, key in slots:
        times[path] = row[key]
        row[key] = 0
    source_paths = []
    for path, identity in source_copies.items():
        for key in revision_fields:
            source_paths.append(f'{path}.{key}')
            identity[key] = None
    return digest(run), times, source_paths, cost_path


def compare_attempts(original, replayed):
    """Compare fresh, linked engineering attempts without executing the plant."""
    first, second = read_attempt(original), read_attempt(replayed)
    relationship, revision_fields = _comparison_identity(first, second)
    left, left_times, left_sources, left_cost = _comparison_run(first, revision_fields)
    right, right_times, right_sources, right_cost = _comparison_run(second, revision_fields)
    equal = left == right
    return dict(schema='aegisdc-recorded-semantic-comparison-v1',
                status='EXACT_REPLAY_SEMANTICS_MATCH' if equal else 'SEMANTIC_MISMATCH',
                strict_values_match=equal, original_attempt_sha256=first['record_sha256'],
                replay_attempt_sha256=second['record_sha256'],
                semantic_sha256=dict(original=left, replay=right),
                source=dict(rule='EXACT_RUNTIME_BYTES_AND_INTERPRETER', revision_relationship=relationship,
                            runtime_tree_sha256=first['record']['source_identity']['source_tree_sha256'],
                            original_commit=first['record']['source_identity']['git_commit'],
                            replay_commit=second['record']['source_identity']['git_commit'],
                            normalized_revision_paths=sorted(set(left_sources) | set(right_sources))),
                timing=dict(rule='DECLARED_NS_VALUES_ONLY_AFTER_RAW_AUDIT_AND_AGGREGATE_VALIDATION',
                            original_cost_root=left_cost, replay_cost_root=right_cost,
                            original_masked_values=len(left_times), replay_masked_values=len(right_times),
                            changed_value_paths=sorted(path for path in left_times.keys() & right_times.keys()
                                                       if left_times[path] != right_times[path])))
