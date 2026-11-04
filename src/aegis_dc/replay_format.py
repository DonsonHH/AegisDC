"""Version and structure authority for private recorded-attempt envelopes."""
from datetime import datetime
import math
from pathlib import PurePosixPath

from patrol_rsi.contracts import digest

ATTEMPT_SCHEMAS = {'aegisdc-facility-attempt-v1', 'aegisdc-facility-attempt-v2'}
DECLARATION_SCHEMAS = {'aegisdc-attempt-declaration-v1', 'aegisdc-attempt-declaration-v2'}
TERMINAL_STATES = {'COMPLETED', 'FAILED'}
LIFECYCLE_SCHEMA = 'aegisdc-attempt-lifecycle-v1'


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _sha(value, length=64):
    return isinstance(value, str) and len(value) == length and set(value) <= set('0123456789abcdef')


def _path(value):
    return (_text(value) and '\\' not in value and ':' not in value
            and not PurePosixPath(value).is_absolute() and '..' not in PurePosixPath(value).parts
            and value != '.' and PurePosixPath(value).as_posix() == value
            and '__pycache__' not in {part.lower() for part in PurePosixPath(value).parts}
            and PurePosixPath(value).suffix.lower() not in {'.pyc', '.pyo'})


def _paths(value):
    return isinstance(value, list) and all(_path(item) for item in value) and len(set(value)) == len(value)


def _hashes(value):
    return isinstance(value, dict) and bool(value) and all(_path(name) and _sha(identity) for name, identity in value.items())


def _fields(value, required, optional, label):
    _require(isinstance(value, dict) and required <= set(value) <= required | optional,
             'Invalid ' + label + ' object fields/structure')


def _positive(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _failure(value):
    _fields(value, {'stage', 'type', 'message'}, set(), 'failure')
    _require(all(isinstance(value[name], str) for name in value) and _text(value['stage']) and _text(value['type']),
             'Invalid failure fields')


def source_identity(value):
    _fields(value, {'schema', 'git_commit', 'implementation_has_changes', 'files', 'source_tree_sha256', 'python'}, set(), 'source identity')
    _require(value['schema'] == 'aegisdc-execution-source-v1', 'Unsupported execution source schema/version')
    _require(_hashes(value['files']) and digest(value['files']) == value['source_tree_sha256'], 'Inconsistent execution source identity')
    _require(value['git_commit'] is None or _sha(value['git_commit'], 40), 'Invalid source Git identity')
    _require(value['implementation_has_changes'] is None or type(value['implementation_has_changes']) is bool, 'Invalid source dirty-state flag')
    _fields(value['python'], {'implementation', 'version', 'executable_sha256'}, set(), 'interpreter identity')
    _require(_text(value['python']['implementation']) and _text(value['python']['version']) and _sha(value['python']['executable_sha256']),
             'Invalid interpreter identity')


def terminal_header(value):
    if not isinstance(value, dict) or value.get('schema') not in ATTEMPT_SCHEMAS:
        raise ValueError('Unsupported terminal attempt schema/version')
    if value.get('status') not in TERMINAL_STATES:
        raise ValueError('Unsupported terminal status/state')
    required = {'schema', 'attempt_id', 'attempt_kind', 'execution_kind', 'state_visibility',
                'research_registration', 'research_trials', 'model_calls', 'training_calls',
                'field_calibration', 'research_gain_claim', 'source_identity', 'replay_of', 'retry_of',
                'status', 'failure', 'artifacts'}
    optional = {'seed', 'scenario_sha256', 'inputs_sha256', 'duration_s', 'maximum_step_s', 'randomness',
                'replay_source_rule', 'replay_revision_relationship'}
    if value['schema'].endswith('-v2'):
        required.add('origin_validation')
    _fields(value, required, optional, 'terminal attempt')
    _require(_text(value['attempt_id']) and _text(value['attempt_kind']), 'Invalid terminal attempt identity/kind')
    _require(value['execution_kind'] in {'NOT_STARTED', 'ENGINEERING_FIXTURE'}, 'Invalid terminal execution kind')
    _require(value['state_visibility'] == 'PRIVATE_PLANT_EVALUATOR_ONLY' and value['field_calibration'] == 'PENDING'
             and value['research_gain_claim'] == 'NOT_ESTABLISHED', 'Unsupported attempt visibility or research authority')
    _require(all(type(value[name]) is int and value[name] == 0 for name in ('research_trials', 'model_calls', 'training_calls')),
             'This attempt format has no registered research authority')
    _require(_hashes(value['artifacts']), 'Invalid terminal artifact inventory')
    source_identity(value['source_identity'])
    if value['status'] == 'FAILED':
        _failure(value['failure'])
    else:
        _require(value['failure'] is None and value['attempt_kind'] == 'engineering_fixture'
                 and value['execution_kind'] == 'ENGINEERING_FIXTURE' and value['research_registration'] is None,
                 'COMPLETED status conflicts with failure or execution authority')
        _require({'seed', 'scenario_sha256', 'inputs_sha256', 'duration_s', 'maximum_step_s', 'randomness'} <= set(value),
                 'Completed terminal lacks frozen input identity')
    for name in ('scenario_sha256', 'inputs_sha256'):
        if name in value:
            _require(_sha(value[name]), 'Invalid terminal input identity')
    if 'seed' in value:
        _require(value['seed'] is None or type(value['seed']) is int, 'Invalid terminal seed')
    if 'randomness' in value:
        _require(_text(value['randomness']), 'Invalid terminal randomness declaration')
    if 'replay_source_rule' in value:
        _require(value['replay_source_rule'] == 'EXACT_RUNTIME_BYTES_AND_INTERPRETER', 'Unsupported replay source rule')
    if 'replay_revision_relationship' in value:
        _require(value['replay_revision_relationship'] in {'SAME_COMMIT', 'DIFFERENT_COMMIT_SAME_RUNTIME_BYTES'}, 'Unsupported replay revision relationship')
    for name in ('duration_s', 'maximum_step_s'):
        if name in value and value['status'] == 'COMPLETED':
            _require(_positive(value[name]), 'Invalid terminal time input')
    for name in ('replay_of', 'retry_of'):
        reference = value[name]
        if reference is not None:
            _fields(reference, set(), {'attempt_id', 'attempt_sha256', 'requested_directory', 'mode', 'reason'}, name)
            _require((_text(reference.get('requested_directory')) or _text(reference.get('attempt_id'))
                      and _sha(reference.get('attempt_sha256'))), 'Invalid replay/retry origin identity')
            if 'mode' in reference:
                _require(reference['mode'] in {'EXACT_REEXECUTION', 'PAIRED_EXOGENOUS_NEW_ENGINEERING_COMMANDS'}, 'Unknown replay origin mode')
            if name == 'retry_of':
                _require(_text(reference.get('reason')), 'Invalid retry reason')
    if value.get('origin_validation') is not None:
        _fields(value['origin_validation'], {'directory', 'stage'}, set(), 'origin validation')
        _require(all(_text(item) for item in value['origin_validation'].values()), 'Invalid origin validation identity')
    return value


def declaration_header(value):
    if not isinstance(value, dict) or value.get('schema') not in DECLARATION_SCHEMAS:
        raise ValueError('Unsupported attempt declaration schema/version')
    required = {'schema', 'required_when_completed', 'allowed_before_finalization', 'terminal_manifest',
                'runtime_caches', 'tools', 'incomplete'}
    if value['schema'].endswith('-v2'):
        required |= {'lifecycle_schema', 'origin_snapshot_files'}
    _fields(value, required, set(), 'declaration')
    _require(_paths(value['required_when_completed']) and _paths(value['allowed_before_finalization']), 'Invalid declaration artifact paths')
    _require(set(value['required_when_completed']) == set(value['allowed_before_finalization']), 'Unsupported declaration output roles')
    base = {'declaration.json', 'lifecycle.jsonl', 'request.json', 'scenario-input.json', 'inputs.json',
            'frozen-inputs.json', 'trajectory/run.json', 'trajectory/scenario.json', 'trajectory/private-state.jsonl', 'trajectory/balances.jsonl'}
    optional = {'submitted-scenario.json', 'submitted-inputs.json', 'submitted-action_commands.json'}
    origin = value.get('origin_snapshot_files', [])
    _require(_paths(origin) and all(name.startswith('origin/') for name in origin), 'Invalid declaration origin snapshot roles')
    _require(base | set(origin) <= set(value['required_when_completed']) <= base | set(origin) | optional,
             'Unsupported declaration durable roles')
    _require(value['terminal_manifest'] == 'attempt.json' and value['runtime_caches'] == 'NOT_DELIVERABLE'
             and _text(value['tools']) and _text(value['incomplete']), 'Invalid declaration lifecycle/cache/tool authority')
    if 'lifecycle_schema' in value:
        _require(value['lifecycle_schema'] == LIFECYCLE_SCHEMA, 'Unsupported declared lifecycle schema/version')
    return value


def lifecycle_rows(rows):
    if not isinstance(rows, list) or len(rows) > 2:
        raise ValueError('Invalid lifecycle sequence structure')
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError('Each lifecycle row must be an object')
        explicit = 'schema' in row
        if explicit and row['schema'] != LIFECYCLE_SCHEMA:
            raise ValueError('Unsupported lifecycle schema/version')
        expected = {'state', 'recorded_at_utc', 'attempt_id' if index == 0 else 'failure'}
        if explicit:
            expected |= {'schema', 'attempt_id'}
        if set(row) != expected or row['state'] not in ({'STARTED'} if index == 0 else TERMINAL_STATES):
            raise ValueError('Invalid lifecycle row fields or state')
        if 'attempt_id' in row and (not isinstance(row['attempt_id'], str) or not row['attempt_id'].strip()):
            raise ValueError('Invalid lifecycle attempt identity')
        if not isinstance(row['recorded_at_utc'], str):
            raise ValueError('Invalid lifecycle timestamp')
        try:
            epoch = datetime.fromisoformat(row['recorded_at_utc'])
        except ValueError as error:
            raise ValueError('Invalid lifecycle timestamp') from error
        if epoch.utcoffset() is None:
            raise ValueError('Lifecycle timestamp requires an explicit offset')
        if index == 1:
            if row['state'] == 'FAILED':
                _failure(row['failure'])
            else:
                _require(row['failure'] is None, 'Completed lifecycle cannot contain a failure')
            if explicit:
                _require(row['attempt_id'] == rows[0]['attempt_id'], 'Lifecycle attempt identity changed')
    if len(rows) == 2 and datetime.fromisoformat(rows[1]['recorded_at_utc']) < datetime.fromisoformat(rows[0]['recorded_at_utc']):
        raise ValueError('Lifecycle terminal time precedes STARTED')
    return rows


def completed_request(value):
    _fields(value, {'duration_s', 'maximum_step_s', 'retry_of', 'retry_reason', 'attempt_kind', 'research_registration'},
            {'source_files'}, 'completed request')
    _require(all(value[name] is None or _positive(value[name]) for name in ('duration_s', 'maximum_step_s')), 'Invalid request time input')
    _require(value['attempt_kind'] == 'engineering_fixture' and value['research_registration'] is None, 'Unsupported completed request authority')
    for name in ('retry_of', 'retry_reason'):
        _require(value[name] is None or _text(value[name]), 'Invalid completed request retry identity')
    supplied = value.get('source_files', {})
    _require(isinstance(supplied, dict) and set(supplied) <= {'scenario', 'inputs', 'action_commands'}
             and all(_text(path) for path in supplied.values()), 'Invalid request submitted-file identity')
    return value


def bind_execution_inputs(request, scenario, terminal, run_inputs):
    """Resolve request defaults and bind them to both recorded actual inputs."""
    result = {}
    for name, parameter in (('duration_s', 'duration'), ('maximum_step_s', 'step_time')):
        effective = request[name]
        if effective is None:
            _require(isinstance(scenario, dict) and isinstance(scenario.get('parameters'), list), 'Frozen scenario lacks request defaults')
            matches = [row for row in scenario['parameters'] if isinstance(row, dict) and row.get('id') == parameter]
            _require(len(matches) == 1, 'Frozen scenario requires one default for ' + parameter)
            effective = matches[0].get('value')
        _require(_positive(effective) and _positive(terminal.get(name)) and _positive(run_inputs.get(name)), 'Invalid effective execution input ' + name)
        _require(effective == terminal[name] == run_inputs[name], 'Request effective ' + name + ' differs from the frozen actual execution')
        result[name] = terminal[name]
    return result


def engineering_run_header(value):
    _require(isinstance(value, dict) and value.get('schema') == 'aegisdc-engineering-facility-run-v1', 'Unsupported private trajectory schema/version')
    _require(value.get('status') == 'ENGINEERING_FIXTURE_COMPLETED' and value.get('state_visibility') == 'PRIVATE_PLANT_EVALUATOR_ONLY', 'Invalid trajectory status/visibility')
    _require(isinstance(value.get('inputs'), dict) and isinstance(value.get('code_identity'), dict), 'Invalid trajectory input/source structure')
    _require(isinstance(value.get('summary'), dict) and isinstance(value.get('events'), list)
             and isinstance(value.get('work_records'), list)
             and all(isinstance(row, dict) for row in value['events'] + value['work_records']), 'Invalid trajectory summary/event/work structure')
    return value


def trace_rows(rows):
    _require(isinstance(rows, list) and len(rows) >= 2, 'Invalid private trajectory row sequence')
    for row in rows:
        _fields(row, {'time_s', 'domains'}, set(), 'private trajectory row')
        _require(type(row['time_s']) in (int, float) and (row['time_s'] == 0 or _positive(row['time_s'])) and isinstance(row['domains'], dict),
                 'Invalid private trajectory time/domains structure')
    return rows


def balance_rows(rows):
    _require(isinstance(rows, list) and bool(rows), 'Invalid interval balance sequence')
    _require(all(isinstance(row, dict) and {'start_s', 'end_s'} <= set(row) for row in rows), 'Invalid interval balance row structure')
    for index, row in enumerate(rows):
        _require(type(row['start_s']) in (int, float) and (row['start_s'] == 0 or _positive(row['start_s']))
                 and _positive(row['end_s']), 'Balance timestamps require finite nonnegative numeric values')
        _require(row['end_s'] > row['start_s'], 'Balance interval must have positive duration')
        if index:
            _require(row['start_s'] == rows[index - 1]['end_s'], 'Balance intervals must be contiguous and nonoverlapping')
    return rows


def balance_time_axis(rows, trace, duration_s, maximum_step_s):
    """Check saved coordinates against their trace and frozen run boundaries."""
    _require(len(trace) == len(rows) + 1, 'Balance/trace interval counts differ')
    _require(trace[0]['time_s'] == rows[0]['start_s'] == 0
             and trace[-1]['time_s'] == rows[-1]['end_s'] == duration_s,
             'Balance/trace time axis must cover exactly the frozen run')
    for index, row in enumerate(rows):
        _require(row['start_s'] == trace[index]['time_s'] and row['end_s'] == trace[index + 1]['time_s'],
                 'Balance interval coordinates differ from the stored trace')
        _require(0 <= row['start_s'] < row['end_s'] <= duration_s, 'Balance interval is outside the frozen run')
        # This is the same declared coordinate upper bound, not a physical
        # tolerance or a subtraction-based test that can add rounding error.
        _require(row['end_s'] <= row['start_s'] + maximum_step_s, 'Balance interval exceeds the frozen maximum step')
    return rows
