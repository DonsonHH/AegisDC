"""Committed-source environment engineering runs with independent fresh reads."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import traceback

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario
from patrol_rsi.contracts import digest


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / 'configs/full-facility-mainline-environment-v4.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def event(name, value, time):
    return {'time_s': time, 'parameter_id': name, 'value': value,
            'source_note': 'Predeclared synthetic environmental engineering boundary, not a research policy intervention.'}


def job(identifier='room-work'):
    return {'id': identifier, 'time_s': 0, 'worker_id': 'worker_cooling',
        'work_interface_id': 'inspect_equipment_environment', 'target_id': 'room',
        'source_note': 'Finite qualified engineering work only, without diagnosis/evidence/repair effect.'}


def cases():
    isolated = dict(internal_hot_mass=1000, minimum_internal_hot_mass=900,
        water_specific_heat=4000, initial_hot_temperature=320, initial_cold_temperature=310,
        pump_pressure_rise=0, internal_pump_pressure_rise=0, compute_demand_power=0,
        network_demand_power=0, storage_demand_power=0, controller_power=0, room_aux_power=0,
        solid_coolant_conductance=0, solid_air_conductance=0, room_conductance=0, room_temperature=293.15)
    local = {'worker_cooling': 'loc_it', 'tool_flow_meter': 'loc_it'}
    return [
        dict(id='normal', duration_s=600, parameters={}, events=[], jobs=[], locations={}),
        dict(id='isothermal-hot-leak', duration_s=2, parameters=dict(isolated, internal_hot_leak_mass_flow=2, drainage_mass_flow=0), events=[], jobs=[], locations={}),
        dict(id='actual-leak-work', duration_s=10, parameters={'internal_hot_leak_mass_flow': 2}, events=[], jobs=[job()], locations=local),
        dict(id='ambient-nuisance-work', duration_s=10, parameters={'floor_water_inflow': 2}, events=[], jobs=[job()], locations=local),
        dict(id='mixed-pool', duration_s=60, parameters=dict(isolated, internal_hot_leak_mass_flow=0.2, floor_water_inflow=0.1, drainage_mass_flow=0.15, initial_floor_water_mass=20), events=[], jobs=[], locations={}),
        dict(id='permission-during-work', duration_s=126, parameters={}, events=[event('it_access_permit', 0, 125)], jobs=[job()], locations={}),
        dict(id='permission-before-entry', duration_s=121, parameters={}, events=[event('it_access_permit', 0, 90)], jobs=[job()], locations={}),
        dict(id='room-sensible-heat', duration_s=2, parameters=dict(isolated, room_temperature=300, room_thermal_capacity=1000000, maximum_room_work_temperature=300.15, room_aux_power=100000), events=[], jobs=[job()], locations=local),
        dict(id='RH-risk-only', duration_s=1, parameters={}, events=[event('room_humidity', 1, 0.25)], jobs=[], locations={}),
        dict(id='minimum-inventory-domain', duration_s=1, parameters=dict(isolated, minimum_internal_hot_mass=999, internal_hot_leak_mass_flow=2, drainage_mass_flow=0), events=[], jobs=[], locations={}, expected_error='hydraulic validity minimum'),
    ]


def fresh_check(directory):
    manifest = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    require(manifest['code_identity']['implementation_has_changes'] is False, 'Run source was not committed')
    require(manifest['research_trials'] == manifest['model_calls'] == manifest['training_calls'] == 0, 'Engineering scope violation')
    hashes = {}
    for name, record in manifest['artifacts'].items():
        data = (directory / name).read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        require(hashes[name] == record['sha256'], 'Fresh artifact SHA mismatch: ' + name)
        require((1 if name == 'scenario.json' else len(data.splitlines())) == record['records'], 'Fresh artifact count mismatch')
    scenario = json.loads((directory / 'scenario.json').read_text(encoding='utf-8'))
    require(digest(scenario) == manifest['scenario_sha256'], 'Canonical input identity changed')
    p = {row['id']: row['value'] for row in scenario['parameters']}
    trace = [json.loads(line) for line in (directory / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    balances = [json.loads(line) for line in (directory / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
    samples = {row['time_s']: row['domains'] for row in trace}
    max_mass, max_energy, max_floor_energy, max_hot_transfer = 0.0, 0.0, 0.0, 0.0
    for row in balances:
        dt = row['end_s'] - row['start_s']
        for account in row['mass_accounts_kg'].values():
            residual = math.fsum([account['before_kg'], account['in_kg'], -account['out_kg'], -account['after_kg']])
            max_mass = max(max_mass, abs(residual))
            require(abs(residual) <= p['mass_absolute_tolerance'], 'Fresh per-medium water account failed')
        change = math.fsum(row['storage_after_J'].values()) - math.fsum(row['storage_before_J'].values())
        residual = change - row['boundary_input_J'] + row['boundary_output_J']
        max_energy = max(max_energy, abs(residual))
        tolerance = p['energy_absolute_tolerance'] + p['balance_relative_tolerance'] * (abs(row['boundary_input_J']) + abs(row['boundary_output_J']))
        require(abs(residual) <= tolerance, 'Fresh facility energy account failed')
        floor = row['storage_after_J']['floor_water'] - row['storage_before_J']['floor_water']
        floor -= row['floor_inlet_energy_J'] + row['internal_hot_leak_energy_J'] - row['floor_drain_energy_J']
        max_floor_energy = max(max_floor_energy, abs(floor))
        require(abs(floor) <= tolerance, 'Internal leakage was lost or counted twice in floor energy')
        before, after = samples[row['start_s']], samples[row['end_s']]
        hot = before['facility_cooling']['hot_temperature_K']
        transfer_error = row['internal_hot_leak_energy_J'] - row['internal_hot_leaked_mass_kg'] * p['water_specific_heat'] * hot
        max_hot_transfer = max(max_hot_transfer, abs(transfer_error))
        require(abs(transfer_error) <= tolerance, 'Hot leakage does not carry its corresponding sensible energy')
        require(abs(before['facility_cooling']['hot_mass_kg'] - after['facility_cooling']['hot_mass_kg'] - row['internal_hot_leaked_mass_kg']) < 1e-9, 'Hot leak mass did not come from the hot inventory')
        require(abs(row['mass_accounts_kg']['floor_water']['in_kg'] - row['floor_water_inlet_mass_kg'] - row['internal_hot_leaked_mass_kg']) < 1e-9, 'Nuisance source and real leak mass were conflated')
    first, last = trace[0]['domains'], trace[-1]['domains']
    require(all(len(row['domains']) == 8 for row in trace), 'A complete-facility behavior domain was omitted')
    return {'classification': 'ENGINEERING_FRESH_READ_ONLY',
        'source_commit': manifest['code_identity']['git_commit'], 'source_tree_sha256': manifest['code_identity']['source_tree_sha256'],
        'scenario_sha256': manifest['scenario_sha256'], 'artifact_sha256': hashes,
        'state_records': len(trace), 'balance_records': len(balances),
        'fresh_max_mass_residual_kg': max_mass, 'fresh_max_energy_residual_J': max_energy,
        'fresh_max_floor_energy_residual_J': max_floor_energy, 'max_hot_transfer_energy_error_J': max_hot_transfer,
        'final_hot_mass_kg': last['facility_cooling']['hot_mass_kg'],
        'hot_temperature_drift_K': last['facility_cooling']['hot_temperature_K'] - first['facility_cooling']['hot_temperature_K'],
        'room_temperature_drift_K': last['equipment_environment']['room_temperature_K'] - first['equipment_environment']['room_temperature_K'],
        'final_floor_mass_kg': last['space_access']['floor_water_mass_kg'],
        'final_floor_temperature_K': last['space_access']['floor_water_temperature_K'],
        'leaked_mass_kg': manifest['summary']['internal_hot_leaked_mass_kg'],
        'nuisance_inlet_mass_kg': manifest['summary']['floor_water_inlet_mass_kg'],
        'work_records': manifest['work_records'], 'events': manifest['events'],
        'worker_work_person_s': manifest['summary']['worker_work_person_s'],
        'service_deficit_time_s': manifest['summary']['service_deficit_time_s'],
        'research_trials': 0, 'field_calibration': 'PENDING', 'gain': 'NOT_ESTABLISHED'}


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    sources = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((ROOT / 'src/aegis_dc').glob('*.py'))}
    book = {'classification': 'ENGINEERING_ONLY_NO_RESEARCH_PROTOCOL', 'source_commit': commit,
        'source_sha256': sources, 'base_input': CONFIG.relative_to(ROOT).as_posix(),
        'base_input_sha256': hashlib.sha256(CONFIG.read_bytes()).hexdigest(), 'cases': cases()}
    (output / 'runbook.json').write_text(json.dumps(book, indent=2) + '\n', encoding='utf-8', newline='\n')
    results = {}
    for case in book['cases']:
        attempt = {'id': case['id'], 'classification': 'ENGINEERING_ONLY', 'input_sha256': digest(case), 'source_commit': commit}
        scenario = load_scenario(CONFIG)
        for row in scenario['parameters']:
            if row['id'] in case['parameters']:
                row.update(value=case['parameters'][row['id']], basis='synthetic_assumption', source_refs=['Renv'],
                    source_note='Predeclared '+case['id']+' engineering override; see runbook. Not site calibrated.')
        for entity in scenario['entities']:
            if entity['id'] in case['locations']:
                entity.update(location_id=case['locations'][entity['id']], source_refs=['Renv'],
                    source_note='Declared initial engineering-fixture position, not movement during a run.')
        try:
            run = simulate_scenario(scenario, duration_s=case['duration_s'], work_requests=case['jobs'], boundary_events=case['events'])
            require('expected_error' not in case, 'The declared domain failure unexpectedly returned success')
            save_run(run, output / case['id'])
            results[case['id']] = fresh_check(output / case['id'])
            attempt['status'] = 'FRESH_READ_PASS'
        except Exception as error:
            target = output / (case['id'] + '-failure')
            target.mkdir(exist_ok=False)
            (target / 'scenario.json').write_text(json.dumps(scenario, indent=2) + '\n', encoding='utf-8', newline='\n')
            (target / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8', newline='\n')
            expected = isinstance(error, ValueError) and case.get('expected_error', '\0') in str(error)
            attempt.update(status='EXPECTED_DOMAIN_FAILURE' if expected else 'UNEXPECTED_FAILURE',
                exception_type=type(error).__name__, message=str(error), scenario_sha256=digest(scenario))
            results[case['id']] = dict(attempt)
            if not expected:
                raise
        finally:
            with (output / 'engineering-attempts.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(attempt, allow_nan=False) + '\n')
    require(results['normal']['service_deficit_time_s'] == 0 and abs(results['normal']['hot_temperature_drift_K']) < 1e-6, 'Healthy profile was not stable')
    require(results['isothermal-hot-leak']['final_hot_mass_kg'] == 996 and abs(results['isothermal-hot-leak']['hot_temperature_drift_K']) < 1e-10, 'Isothermal withdrawal hand case failed')
    require(abs(results['mixed-pool']['final_floor_temperature_K'] - 302.5363258026159) < 1e-8, 'Independent mixed-pool hand case failed')
    require(abs(results['room-sensible-heat']['worker_work_person_s'] - 1.5) < 1e-9, 'Independent thermal cutoff time failed')
    require(results['minimum-inventory-domain']['status'] == 'EXPECTED_DOMAIN_FAILURE', 'Inventory limit was silently bypassed')
    (output / 'fresh-read-receipt.json').write_text(json.dumps(results, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
