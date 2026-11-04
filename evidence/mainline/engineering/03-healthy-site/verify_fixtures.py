"""Fresh-read saved engineering fixtures; no simulation, EOS import or policy."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE_COMMIT = '37432b25a994c1c4e37d6747e9e9228a9ea3a44a'
DOMAINS = {'power', 'backup', 'facility_cooling', 'equipment_environment',
           'it_service', 'control_monitoring', 'space_access', 'people_tools_work'}


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify_run(name, duration):
    directory = HERE / name
    manifest = read_json(directory / 'run.json')
    assert manifest['status'] == 'ENGINEERING_FIXTURE_COMPLETED'
    assert manifest['state_visibility'] == 'PRIVATE_PLANT_EVALUATOR_ONLY'
    assert manifest['engineering_fixture'] and manifest['research_trials'] == 0
    assert manifest['model_calls'] == manifest['training_calls'] == 0
    assert manifest['code_identity']['git_commit'] == SOURCE_COMMIT
    assert manifest['code_identity']['implementation_has_changes'] is False
    for filename, record in manifest['artifacts'].items():
        content = (directory / filename).read_bytes()
        assert sha256(content).hexdigest() == record['sha256'], filename
        if filename.endswith('.jsonl'):
            assert len(content.splitlines()) == record['records'], filename
    scenario = read_json(directory / 'scenario.json')
    assert canonical_hash(scenario) == manifest['scenario_sha256']
    assert len(scenario['domains']) == 8
    assert len(scenario['entities']) == 40 and len(scenario['parameters']) == 79
    assert sha256((ROOT / scenario['runtime']['property_table']).read_bytes()).hexdigest() \
        == manifest['property_reference']['sha256']
    trace = [json.loads(line) for line in (directory / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    balances = [json.loads(line) for line in (directory / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(trace) == len(balances) + 1
    assert trace[0]['time_s'] == 0 and trace[-1]['time_s'] == duration
    max_energy, max_mass = 0.0, 0.0
    for index, balance in enumerate(balances):
        start, end = balance['start_s'], balance['end_s']
        assert start == trace[index]['time_s'] and end == trace[index + 1]['time_s']
        assert 0 < end - start <= 1
        energy_change = math.fsum(balance['storage_after_J'].values()) - math.fsum(balance['storage_before_J'].values())
        residual = energy_change - (balance['boundary_input_J'] - balance['boundary_output_J'])
        max_energy = max(max_energy, abs(residual))
        assert abs(residual) < 0.01
        for row in balance['mass_accounts_kg'].values():
            residual = math.fsum((row['before_kg'], row['in_kg'], -row['out_kg'], -row['after_kg']))
            max_mass = max(max_mass, abs(residual))
            assert abs(residual) < 1e-9
        assert min(balance['capacity_slack_W'].values()) >= 0
    for row in trace:
        domains = row['domains']
        assert set(domains) == DOMAINS
        phase = domains['equipment_environment']['refrigerant']
        assert 0 <= phase['quality'] <= 1
        assert abs(phase['liquid_mass_kg'] + phase['vapor_mass_kg'] - 2000) < 1e-9
        phase_volume = phase['liquid_mass_kg'] / phase['rho_l_kg_m3'] + phase['vapor_mass_kg'] / phase['rho_v_kg_m3']
        assert abs(phase_volume - phase['volume_m3']) < 1e-10
        assert domains['backup']['ups_energy_J'] >= 0 and domains['backup']['fuel_energy_J'] >= 0
        assert domains['space_access']['floor_water_mass_kg'] >= 0
    assert manifest['summary']['demand_service_unit_s'] == duration
    assert manifest['summary']['delivered_service_unit_s'] == duration
    assert manifest['summary']['service_deficit_time_s'] == 0
    current_matches = all((ROOT / name).is_file() and sha256((ROOT / name).read_bytes()).hexdigest() == value
                          for name, value in manifest['code_identity']['files'].items())
    return manifest, trace, {'trace_records': len(trace), 'balance_records': len(balances),
                             'fresh_read_max_energy_residual_J': max_energy,
                             'fresh_read_max_mass_residual_kg': max_mass,
                             'current_source_matches_recorded_snapshot': current_matches}


def verify():
    normal, trace, normal_check = verify_run('normal-37432b25', 600)
    assert not normal['work_records']
    for row in trace:
        people = row['domains']['people_tools_work']
        assert all(person['status'] == 'idle' for person in people['workers'].values())
        assert all(tool['reserved_by'] is None for tool in people['tools'].values())
        cooling, equipment = row['domains']['facility_cooling'], row['domains']['equipment_environment']
        assert abs(cooling['hot_temperature_K'] - 300.5295616763055) < 1e-6
        assert abs(cooling['cold_temperature_K'] - 296.2962145993765) < 1e-6
        assert abs(equipment['solid_temperature_K'] - 308.47751006414603) < 1e-6
        assert abs(equipment['room_temperature_K'] - 298.9513745704467) < 1e-6
    work, _, work_check = verify_run('work-37432b25', 151)
    records = {row['id']: row for row in work['work_records']}
    completed = records['qualified-cooling-job']
    assert completed['status'] == 'completed'
    assert completed['arrived_at_s'] == 120.25 and completed['completed_at_s'] == 150.25
    assert completed['effect'] == 'ENGINEERING_WORK_RECORD_ONLY_NO_REPAIR_OR_EVIDENCE'
    assert work['summary']['worker_travel_person_s'] == 120
    assert work['summary']['worker_work_person_s'] == 30
    assert work['summary']['tool_occupation_tool_s'] == 150
    for identifier, reason in [('shared-tool-conflict', 'tool_busy'),
                               ('qualification-mismatch', 'qualification_mismatch'),
                               ('worker-already-occupied', 'worker_busy'),
                               ('access-qualification-missing', 'access_unreachable')]:
        assert records[identifier]['status'] == 'rejected' and records[identifier]['reason'] == reason
    acceptance = read_json(HERE / 'acceptance-37432b25/summary.json')
    assert acceptance['overall'] == 'PASS'
    assert acceptance['tests']['run'] == 176 and acceptance['tests']['executed'] == 174
    assert acceptance['tests']['failures'] == acceptance['tests']['errors'] == 0
    assert len(acceptance['tests']['optional_neural_skips']) == 2
    assert acceptance['tests']['unexpected_skips'] == []
    files = {}
    for directory in ['normal-37432b25', 'work-37432b25', 'acceptance-37432b25']:
        for path in sorted((HERE / directory).iterdir()):
            files[str(path.relative_to(HERE)).replace('\\', '/')] = sha256(path.read_bytes()).hexdigest()
    for name in ['work-inputs-v1.json', 'verify_fixtures.py']:
        files[name] = sha256((HERE / name).read_bytes()).hexdigest()
    return {'schema': 'aegisdc-ticket03-fixture-verification-v1', 'status': 'PASS',
            'scope': 'Fresh reads and independent saved-boundary/analytic checks; engineering only, no new run or gain test',
            'source_commit': SOURCE_COMMIT, 'normal': normal_check, 'work': work_check,
            'tests': acceptance['tests'], 'historical_original_files_verified': acceptance['verified_original_files'],
            'research_trials': 0, 'field_calibration': 'PENDING', 'research_gain_claim': 'NOT_ESTABLISHED',
            'historical_identity_note': 'Later source revisions may differ; these saved fixtures remain attributed to their recorded source snapshot.',
            'files_sha256': files}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    result = verify()
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if arguments.output:
        with arguments.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
    print(content, end='')
