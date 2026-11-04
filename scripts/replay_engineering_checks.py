"""Read-only outcome checks for frozen full-facility replay engineering data."""
import json
from hashlib import sha256
from pathlib import Path

from aegis_dc.replay import read_attempt
from coupled_engineering_checks import check_case

ATTEMPTS = ['normal-600s', 'normal-600s-replay', 'combined-episode-CLI', 'combined-episode-CLI-replay',
            'causal-baseline', 'causal-command', 'physical-failure', 'explicit-retry',
            'forbidden-demand-command', 'coincident-command-conflict', 'invalid-replay-origin',
            'research-before-protocol', 'malformed-CLI-input']


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def semantic_run(run):
    """Retain all run semantics; exclude only source and serialized-file identities."""
    return {name: value for name, value in run.items() if name not in {'code_identity', 'artifacts'}}


def check_package(root, directory):
    directory, root = Path(directory), Path(root)
    book = json.loads((directory / 'runbook-copy.json').read_text(encoding='utf-8'))
    prior = json.loads((root / book['prior_runbook']).read_text(encoding='utf-8'))
    records = {name: read_attempt(directory / name) for name in ATTEMPTS}
    pairs, independent = {}, {}
    for identifier in book['exact_replay_cases']:
        original, replayed = records[identifier], records[identifier + '-replay']
        _require(original['record']['status'] == replayed['record']['status'] == 'COMPLETED', 'Replay did not complete')
        _require(semantic_run(original['run']) == semantic_run(replayed['run']), 'Replay changed a physical/event/account semantic')
        _require(replayed['record']['replay_of']['attempt_sha256'] == original['record_sha256'], 'Replay origin hash mismatch')
        _require(original['inputs'] == replayed['inputs'], 'Replay changed frozen inputs')
        item = next(row for row in prior['cases'] if row['id'] == identifier)
        independent[identifier] = check_case(item, original['run'], original['scenario'],
                                            original['run']['trace'], original['run']['balances'])
        pairs[identifier] = dict(status='EXACT_ALL_RUN_SEMANTICS',
                                 state_points=len(original['run']['trace']), intervals=len(original['run']['balances']),
                                 eight_domains=len(original['run']['trace'][-1]['domains']),
                                 offered_service_unit_s=original['run']['summary']['demand_service_unit_s'])
    baseline, controlled = records['causal-baseline'], records['causal-command']
    _require(baseline['record']['status'] == controlled['record']['status'] == 'COMPLETED', 'Causal pair did not complete')
    _require(baseline['scenario'] == controlled['scenario'], 'Causal pair changed the facility')
    _require(baseline['inputs']['exogenous_events'] == controlled['inputs']['exogenous_events'], 'Commands rewrote exogenous events')
    expected = book['causal_case']['independent_expectations']
    for run in (baseline['run'], controlled['run']):
        _require(run['summary']['demand_service_unit_s'] == expected['offered_demand_service_unit_s_each'], 'Offered demand was removed')
    _require(baseline['run']['summary']['delivered_service_unit_s'] == expected['baseline_delivered_service_unit_s'], 'Baseline hand account failed')
    _require(controlled['run']['summary']['delivered_service_unit_s'] == expected['command_delivered_service_unit_s'], 'Control hand account failed')
    command_time = book['causal_case']['action_commands'][0]['time_s']
    after = next(row['domains'] for row in controlled['run']['trace'] if row['time_s'] == command_time)
    _require(after['facility_cooling']['internal_mass_flow_kg_s'] == expected['internal_mass_flow_at_command_kg_s'], 'Valve command was ignored')
    trip = next(row['time_s'] for row in controlled['run']['trace'] if row['domains']['control_monitoring']['protection_latched'])
    _require(trip == expected['protection_trip_at_s'], 'Declared V6 sampled protection was bypassed')
    _require(baseline['run']['trace'][-1]['domains']['equipment_environment'] != controlled['run']['trace'][-1]['domains']['equipment_environment'], 'Internal thermal trajectory was precomputed')
    commands = [row for row in controlled['run']['events'] if row['kind'] == 'engineering_control_command']
    _require(len(commands) == 1 and commands[0]['id'] == 'close-internal-valve', 'Command origin was relabeled exogenous')
    failed, retried = records['physical-failure'], records['explicit-retry']
    for attempt in (failed, retried):
        _require(attempt['record']['status'] == 'FAILED' and attempt['run'] is None, 'Domain failure became a completed trajectory')
        _require('hydraulic validity minimum' in attempt['record']['failure']['message'], 'Wrong physical domain refusal')
    _require(retried['record']['retry_of']['attempt_sha256'] == failed['record_sha256'], 'Explicit retry lost the original failure')
    for name in book['required_refusals']:
        if name == 'existing-output':
            continue
        _require(records[name]['record']['status'] == 'FAILED' and records[name]['run'] is None, 'Refusal failed: ' + name)
    overwrite = json.loads((directory / 'overwrite-refusal.json').read_text(encoding='utf-8'))
    _require(overwrite['returncode'] == 2 and overwrite['before'] == overwrite['after'], 'Existing output was overwritten')
    current = {path.relative_to(directory / 'normal-600s').as_posix(): sha256(path.read_bytes()).hexdigest()
               for path in (directory / 'normal-600s').rglob('*') if path.is_file()}
    _require(current == overwrite['before'], 'Original changed after overwrite refusal')
    for name, attempt in records.items():
        record = attempt['record']
        _require(record['research_trials'] == record['model_calls'] == record['training_calls'] == 0, 'Engineering evidence claims a research run')
        _require(record['state_visibility'] == 'PRIVATE_PLANT_EVALUATOR_ONLY', 'Replay data became dispatch evidence')
    for label in ('normal-600s', 'normal-600s-replay', 'combined-episode-CLI', 'combined-episode-CLI-replay', 'malformed-CLI-input'):
        _require(json.loads((directory / (label + '-stdout.json')).read_text(encoding='utf-8')) == records[label]['record'], 'CLI stdout differs from terminal attempt')
    return dict(status='PASS', exact_replay_pairs=pairs, inherited_independent_case_checks=independent,
                engineering_causal_pair=dict(baseline_delivered_service_unit_s=2, command_delivered_service_unit_s=1,
                                             offered_service_unit_s_each=2, physical_trajectory_differs=True,
                                             command_is_not_exogenous=True),
                terminal_attempts=len(records), completed_attempts=6, failed_attempts=7,
                explicit_retries=1, refused_overwrite_preserved=True,
                research_trials=0, model_calls=0, training_calls=0, field_calibration='PENDING')
