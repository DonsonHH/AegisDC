"""Run and freshly verify source-attributed engineering artifacts, never trials."""
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario
from patrol_rsi.contracts import digest


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / 'configs/full-facility-mainline-water-v3.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def event(parameter, value, time=0.25):
    return {'time_s': time, 'parameter_id': parameter, 'value': value,
            'source_note': 'Predeclared synthetic engineering boundary fixture; no policy trial or human intervention.'}


def cases():
    thermal = {'protection_temperature': 306, 'protection_reset_temperature': 305}
    hand = dict(pump_pressure_rise=100000, internal_pump_pressure_rise=100000,
        lake_hydraulic_resistance=6e8, internal_hydraulic_resistance=6e8,
        lake_valve_open_resistance=1e8, internal_valve_open_resistance=1e8,
        lake_valve_opening=0.5, internal_valve_opening=0.5,
        pump_efficiency=0.5, internal_pump_efficiency=0.5, pump_fluid_heat_fraction=0.5,
        water_specific_heat=4000, water_density=1000, lake_temperature=300,
        initial_hot_temperature=320, initial_cold_temperature=310, plate_hx_conductance=40000)
    request = {'id': 'inspect-internal-valve', 'time_s': 0, 'worker_id': 'worker_cooling',
        'work_interface_id': 'inspect_facility_cooling', 'target_id': 'internal_valve_group',
        'source_note': 'Engineering visit only: no diagnosis, inspection evidence or repair result.'}
    return [
        {'id': 'normal', 'duration_s': 600, 'overrides': {}, 'events': [], 'work': []},
        {'id': 'hand-399500W', 'duration_s': 1, 'overrides': hand, 'events': [], 'work': []},
        {'id': 'filter', 'duration_s': 20, 'overrides': {}, 'events': [event('filter_resistance_multiplier', 4)], 'work': []},
        {'id': 'quarter-head', 'duration_s': 20, 'overrides': {}, 'events': [event('pump_pressure_rise', 37500)], 'work': []},
        {'id': 'hx-degradation', 'duration_s': 180, 'overrides': thermal, 'events': [event('plate_hx_conductance', 10000)], 'work': []},
        {'id': 'internal-shutoff', 'duration_s': 2, 'overrides': {}, 'events': [event('internal_valve_opening', 0)], 'work': []},
        {'id': 'internal-reopen', 'duration_s': 3, 'overrides': {}, 'events': [event('internal_valve_opening', 0), event('internal_valve_opening', 1, 1.25)], 'work': []},
        {'id': 'lake-shutoff', 'duration_s': 180, 'overrides': thermal, 'events': [event('lake_valve_opening', 0)], 'work': []},
        {'id': 'valve-visit', 'duration_s': 31, 'overrides': {}, 'events': [], 'work': [request]},
    ]


def fresh_check(directory):
    manifest = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    require(manifest['code_identity']['implementation_has_changes'] is False,
            'Accepted engineering runs must attribute committed implementation')
    require(manifest['research_trials'] == manifest['model_calls'] == manifest['training_calls'] == 0,
            'Engineering fixtures must not create research/AI/training trials')
    hashes = {}
    for name, record in manifest['artifacts'].items():
        data = (directory / name).read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        require(hashes[name] == record['sha256'], 'Fresh artifact SHA mismatch: ' + name)
        count = 1 if name == 'scenario.json' else len(data.splitlines())
        require(count == record['records'], 'Fresh record count mismatch: ' + name)
    scenario = json.loads((directory / 'scenario.json').read_text(encoding='utf-8'))
    require(digest(scenario) == manifest['scenario_sha256'], 'Fresh canonical scenario identity mismatch')
    p = {row['id']: row['value'] for row in scenario['parameters']}
    trace = [json.loads(line) for line in (directory / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    balances = [json.loads(line) for line in (directory / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
    max_hx_error, max_head_error = 0.0, 0.0
    for sample in trace:
        require(set(sample['domains']) == {domain['id'] for domain in scenario['domains']}, 'Missing behavior domain')
        water = sample['domains']['facility_cooling']
        for loop, load in [('lake', 'intake_pump'), ('internal', 'internal_pump')]:
            pump = water[loop + '_pump']
            error = abs(pump['pressure_rise_Pa'] - pump['passive_pressure_drop_Pa'] - pump['valve_pressure_drop_Pa'])
            max_head_error = max(max_head_error, error)
            require(error < 1e-6, 'Pump differential head does not close across series losses')
            require(abs(pump['electric_power_W'] - sample['domains']['power']['actual_powers_W'][load]) < 1e-6,
                    'Pump has unpaid electrical operation')
            if pump['closed_valve_interlock']:
                require(all(pump[key] == 0 for key in ('volume_flow_m3_s', 'pressure_rise_Pa',
                    'electric_power_W', 'hydraulic_power_W', 'requested_power_W')), 'Shutoff interlock is not stopped')
        ci = water['internal_mass_flow_kg_s'] * p['water_specific_heat']
        cl = water['lake_mass_flow_kg_s'] * p['water_specific_heat']
        hot = ci * (water['hot_temperature_K'] - water['internal_hx_outlet_K'])
        cold = cl * (water['lake_hx_outlet_K'] - water['lake_hx_inlet_K'])
        max_hx_error = max(max_hx_error, abs(hot-water['plate_hx_heat_W']), abs(cold-water['plate_hx_heat_W']))
        require(abs(hot-water['plate_hx_heat_W']) < 1e-5 and abs(cold-water['plate_hx_heat_W']) < 1e-5,
                'HX port enthalpy transfer mismatch')
    max_energy, max_mass = 0.0, 0.0
    for balance in balances:
        for account in balance['mass_accounts_kg'].values():
            residual = math.fsum([account['before_kg'], account['in_kg'], -account['out_kg'], -account['after_kg']])
            max_mass = max(max_mass, abs(residual))
            require(abs(residual) <= p['mass_absolute_tolerance'], 'Fresh per-medium mass imbalance')
        delta = math.fsum(balance['storage_after_J'].values()) - math.fsum(balance['storage_before_J'].values())
        residual = delta - balance['boundary_input_J'] + balance['boundary_output_J']
        max_energy = max(max_energy, abs(residual))
        tolerance = p['energy_absolute_tolerance'] + p['balance_relative_tolerance'] * (
            abs(balance['boundary_input_J']) + abs(balance['boundary_output_J']))
        require(abs(residual) <= tolerance, 'Fresh whole-facility energy imbalance')
    summary = manifest['summary']
    require(abs(summary['demand_service_unit_s'] - summary['duration_s']) < 1e-10,
            'External unit demand was erased by a physical consequence')
    protected = next((sample['time_s'] for sample in trace
                      if sample['domains']['control_monitoring']['mode'] == 'protected'), None)
    return {'classification': 'ENGINEERING_FIXTURE_FRESH_READ_ONLY',
            'source_commit': manifest['code_identity']['git_commit'],
            'source_tree_sha256': manifest['code_identity']['source_tree_sha256'],
            'scenario_sha256': manifest['scenario_sha256'], 'artifact_sha256': hashes,
            'state_records': len(trace), 'balance_records': len(balances),
            'fresh_max_energy_residual_J': max_energy, 'fresh_max_mass_residual_kg': max_mass,
            'max_HX_port_enthalpy_error_W': max_hx_error, 'max_head_split_error_Pa': max_head_error,
            'service_deficit_time_s': summary['service_deficit_time_s'],
            'first_sampled_protection_s': protected, 'whole_run_energy_residual_J': summary['whole_run_energy_residual_J'],
            'work_records': manifest['work_records'], 'research_trials': 0, 'gain': 'NOT_ESTABLISHED'}


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    book = {'classification': 'ENGINEERING_FIXTURES_ONLY', 'research_protocol': None,
            'base_input': CONFIG.relative_to(ROOT).as_posix(),
            'base_input_sha256': hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
            'fixture_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'cases': cases()}
    (output / 'runbook.json').write_text(json.dumps(book, indent=2) + '\n', encoding='utf-8', newline='\n')
    results = {}
    for case in book['cases']:
        attempt = {'id': case['id'], 'classification': 'ENGINEERING_ONLY', 'input_sha256': digest(case)}
        try:
            scenario = load_scenario(CONFIG)
            for row in scenario['parameters']:
                if row['id'] in case['overrides']:
                    row.update(value=case['overrides'][row['id']], basis='synthetic_assumption',
                        source_refs=['Rwater'], source_note='Predeclared 05 ' + case['id']
                        + ' engineering override of the base synthetic setting; see the runbook. Not field calibrated.')
            run = simulate_scenario(scenario, duration_s=case['duration_s'],
                boundary_events=case['events'], work_requests=case['work'])
            save_run(run, output / case['id'])
            results[case['id']] = fresh_check(output / case['id'])
            attempt.update(status='FRESH_READ_PASS', source_commit=run['code_identity']['git_commit'],
                           scenario_sha256=run['scenario_sha256'])
        except Exception:
            attempt.update(status='FAILED', traceback=traceback.format_exc())
            (output / (case['id'] + '-failure.txt')).write_text(attempt['traceback'], encoding='utf-8')
            raise
        finally:
            with (output / 'engineering-attempts.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(attempt, allow_nan=False) + '\n')
    require(results['normal']['service_deficit_time_s'] == 0, 'Normal fixture service deficit')
    require(results['internal-shutoff']['service_deficit_time_s'] == 1, 'Independent shutoff deficit case')
    require(results['internal-reopen']['service_deficit_time_s'] == 1, 'Independent reopen deficit case')
    require(results['lake-shutoff']['first_sampled_protection_s'] is not None, 'No thermal consequence from lake shutoff')
    (output / 'fresh-read-receipt.json').write_text(json.dumps(results, indent=2, allow_nan=False) + '\n',
                                                   encoding='utf-8', newline='\n')
    print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
