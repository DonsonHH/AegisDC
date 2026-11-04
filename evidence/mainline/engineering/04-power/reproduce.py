"""Reproduce ticket 04 engineering evidence through public component/run/CLI APIs.

Run from this worktree with PYTHONPATH=<worktree>/src and a new --output path.
These are finite synthetic engineering checks, never registered effect trials.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from aegis_dc import plant
from aegis_dc.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'configs/full-facility-mainline-v2.json'
HERE = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8', newline='\n')


def fixture(changes):
    scenario = load_scenario(BASE)
    for record in scenario['parameters']:
        if record['id'] in changes:
            record['value'] = changes[record['id']]
            record['source_note'] = 'Ticket 04 synthetic electrical hand-case input; not a site setting.'
    return scenario


def expect(checks, label, actual, expected, tolerance=0):
    passed = abs(actual - expected) <= tolerance
    checks.append({'check': label, 'observed': actual, 'expected': expected,
                   'absolute_tolerance': tolerance, 'pass': passed})


def check_run(name, result):
    checks, trace, summary = [], result['trace'], result['summary']
    first, last = trace[0]['domains'], trace[-1]['domains']
    expect(checks, 'eight domains in every state', min(len(row['domains']) for row in trace), 8)
    expect(checks, 'registered trials', result['research_trials'], 0)
    expect(checks, 'model calls', result['model_calls'], 0)
    expect(checks, 'training calls', result['training_calls'], 0)
    expect(checks, 'committed source implementation', result['code_identity']['implementation_has_changes'], False)
    expect(checks, 'maximum electrical residual W',
           max(abs(row['electrical_residual_W']) for row in result['balances']), 0, 1e-7)
    expect(checks, 'maximum component energy residual J', summary['max_energy_residual_J'], 0, 0.01)
    expect(checks, 'maximum mass residual kg', summary['max_mass_residual_kg'], 0, 1e-9)
    tolerance = 0.01 + 1e-10 * (abs(summary['boundary_input_J']) + abs(summary['boundary_output_J']))
    expect(checks, 'whole facility energy residual J', summary['whole_run_energy_residual_J'], 0, tolerance)
    for capacity, slack in summary['minimum_capacity_slack_W'].items():
        expect(checks, capacity + ' capacity never exceeded', slack >= -1e-8, True)
    if name == 'normal-60s':
        expect(checks, 'demand service-unit s', summary['demand_service_unit_s'], 60)
        expect(checks, 'delivered service-unit s', summary['delivered_service_unit_s'], 60)
        expect(checks, 'deficit s', summary['service_deficit_time_s'], 0)
    elif name in ('rectifier-half', 'feeder-half', 'switchboard-half'):
        power = first['power']
        for component, expected in {'compute': 40000, 'network': 5000, 'storage': 2500,
                                    'local_controller': 1000, 'internal_pump': 19200,
                                    'intake_pump': 21428.57142857143, 'room': 5000}.items():
            expect(checks, component + ' actual power W', power['actual_powers_W'][component], expected, 1e-8)
        expect(checks, 'rectifier AC input W', power['rectifier_input_W'], 50000, 1e-8)
        expect(checks, 'rectifier loss W', power['rectifier_loss_W'], 2500, 1e-8)
        expect(checks, 'demand service-unit s', summary['demand_service_unit_s'], 2)
        expect(checks, 'delivered service-unit s', summary['delivered_service_unit_s'], 1, 1e-12)
        expect(checks, 'deficit s', summary['service_deficit_time_s'], 1, 1e-12)
        expect(checks, 'insulated solid temperature rise K',
               last['equipment_environment']['solid_temperature_K']
               - first['equipment_environment']['solid_temperature_K'], 0.04, 1e-10)
    elif name == 'rectifier-off':
        for component in ('compute', 'network', 'storage'):
            expect(checks, component + ' actual power W', first['power']['actual_powers_W'][component], 0)
        expect(checks, 'room auxiliary W', first['power']['actual_powers_W']['room'], 5000)
        expect(checks, 'deficit s', summary['service_deficit_time_s'], 2)
        expect(checks, 'demand service-unit s', summary['demand_service_unit_s'], 2)
    elif name.startswith('protected-'):
        for component, expected in {'local_controller': 1000, 'internal_pump': 19200,
                                    'intake_pump': 0, 'room': 0, 'compute': 0,
                                    'network': 0, 'storage': 0}.items():
            expect(checks, component + ' actual power W', first['power']['actual_powers_W'][component], expected)
        expect(checks, 'UPS output energy J', summary['ups_output_energy_J'], 40400)
        expect(checks, 'UPS loss energy J', summary['ups_loss_energy_J'], 3513.04347826087, 1e-8)
        expect(checks, 'demand service-unit s', summary['demand_service_unit_s'], 2)
        expect(checks, 'deficit s', summary['service_deficit_time_s'], 2)
        expect(checks, 'lake heat-exchanger transfer W', first['facility_cooling']['plate_hx_heat_W'], 0)
    elif name == 'compute-trip':
        for component, expected in {'compute': 0, 'network': 100000, 'storage': 100000}.items():
            expect(checks, component + ' actual power W', first['power']['actual_powers_W'][component], expected)
        expect(checks, 'demand service-unit s', summary['demand_service_unit_s'], 2)
        expect(checks, 'deficit s', summary['service_deficit_time_s'], 2)
    elif name == 'cli-outage-restore':
        outage = next(row['domains'] for row in trace if row['time_s'] == 0.25)
        restored = next(row['domains'] for row in trace if row['time_s'] == 1.25)
        expect(checks, 'outage actual compute W', outage['power']['actual_powers_W']['compute'], 0)
        expect(checks, 'outage stored-heat transfer W',
               outage['equipment_environment']['solid_coolant_heat_W'], 2000000, 1e-7)
        expect(checks, 'restored compute W', restored['power']['actual_powers_W']['compute'], 2000000)
        expect(checks, 'demand service-unit s', summary['demand_service_unit_s'], 3)
        expect(checks, 'delivered service-unit s', summary['delivered_service_unit_s'], 2)
        expect(checks, 'deficit s', summary['service_deficit_time_s'], 1)
    return {'name': name, 'pass': all(row['pass'] for row in checks), 'checks': checks,
            'scenario_sha256': result['scenario_sha256'], 'code_identity': result['code_identity'],
            'property_reference': result['property_reference'],
            'summary': summary, 'parameter_changes_are_synthetic': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    output = parser.parse_args().output.resolve()
    if Path(plant.__file__).resolve() != ROOT / 'src/aegis_dc/plant.py':
        raise ValueError('Set PYTHONPATH to this worktree/src; imported another checkout')
    output.mkdir(parents=True, exist_ok=False)
    receipt = {'schema': 'aegisdc-ticket-04-engineering-verification-v1', 'status': 'RUNNING',
               'scope': 'finite synthetic full-facility engineering checks; no field calibration or policy effect',
               'registered_research_trials': 0, 'model_calls': 0, 'training_calls': 0,
               'base_config_file_sha256': sha256(BASE.read_bytes()).hexdigest(),
               'verification_script_file_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
               'python': sys.executable, 'module': str(Path(plant.__file__).resolve()), 'cases': []}
    small_it = {'compute_demand_power': 80000, 'network_demand_power': 10000,
                'storage_demand_power': 5000, 'compute_nominal_power': 80000,
                'network_nominal_power': 10000, 'storage_nominal_power': 5000,
                'it_thermal_capacity': 2000000, 'solid_coolant_conductance': 0,
                'solid_air_conductance': 0, 'rectifier_efficiency': 0.95}
    cases = [('normal-60s', {}, 60),
             ('rectifier-half', dict(small_it, rectifier_capacity=50000), 2),
             ('feeder-half', dict(small_it, grid_capacity=676400 / 7), 2),
             ('switchboard-half', dict(small_it, switchboard_capacity=676400 / 7), 2),
             ('rectifier-off', dict(small_it, rectifier_capacity=0), 2),
             ('protected-grid-outage', {'grid_capacity': 0, 'ups_output_capacity': 20200}, 2),
             ('protected-switchboard-outage', {'switchboard_capacity': 0, 'ups_output_capacity': 20200}, 2),
             ('compute-trip', {'protection_temperature': 304, 'protection_reset_temperature': 303}, 2)]
    try:
        for name, changes, duration in cases:
            result = plant.simulate_scenario(fixture(changes), duration_s=duration)
            plant.save_run(result, output / name)
            receipt['cases'].append(check_run(name, result))
        inputs = {'schema': 'aegisdc-engineering-inputs-v1', 'work_requests': [], 'boundary_events': [
            {'time_s': 0.25, 'parameter_id': 'grid_capacity', 'value': 0,
             'source_note': 'Ticket 04 synthetic source outage, not a research trial.'},
            {'time_s': 1.25, 'parameter_id': 'grid_capacity', 'value': 10000000,
             'source_note': 'Ticket 04 synthetic source restoration.'}]}
        write_json(output / 'cli-inputs.json', inputs)
        command = [sys.executable, '-X', 'utf8', '-m', 'aegis_dc', 'simulate',
                   '--model', str(BASE), '--duration', '3', '--inputs', str(output / 'cli-inputs.json'),
                   '--output', str(output / 'cli-outage-restore')]
        completed = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
                                   capture_output=True, text=True, encoding='utf-8')
        (output / 'cli.stdout.json').write_text(completed.stdout, encoding='utf-8', newline='\n')
        (output / 'cli.stderr.txt').write_text(completed.stderr, encoding='utf-8', newline='\n')
        receipt['cli'] = {'command': command, 'exit_code': completed.returncode}
        if completed.returncode:
            raise ValueError('CLI failed; preserved stdout/stderr')
        directory = output / 'cli-outage-restore'
        result = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
        result['source_config'] = json.loads((directory / 'scenario.json').read_text(encoding='utf-8'))
        result['trace'] = [json.loads(line) for line in (directory / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
        result['balances'] = [json.loads(line) for line in (directory / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
        receipt['cases'].append(check_run('cli-outage-restore', result))
        logs = []
        for path in sorted(HERE.glob('attempt-*/tests.log')):
            content = path.read_text(encoding='utf-8')
            count = re.search(r'Ran (\d+) tests?', content)
            logs.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha256(path.read_bytes()).hexdigest(),
                         'tests': int(count[1]) if count else None,
                         'result': 'EXPECTED_RED' if 'FAILED (' in content else 'PASS_WITH_DECLARED_SKIPS'
                         if 'OK (skipped=' in content else 'PASS' if '\nOK\n' in content else 'UNCLASSIFIED'})
        write_json(output / 'test-attempts.json', logs)
        receipt['status'] = 'PASS' if all(case['pass'] for case in receipt['cases']) else 'FAILED_CHECKS'
        if receipt['status'] != 'PASS':
            raise ValueError('An independent engineering check failed; see receipt')
    except Exception as error:
        receipt['status'] = 'FAILED'
        receipt['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        write_json(output / 'receipt.json', receipt)
    print(json.dumps({'status': receipt['status'], 'cases': len(receipt['cases']),
                      'checks': sum(len(case['checks']) for case in receipt['cases']), 'output': str(output)}))


if __name__ == '__main__':
    main()
