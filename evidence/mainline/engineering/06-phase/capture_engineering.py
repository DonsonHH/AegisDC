"""Capture ticket 06 public-interface engineering artifacts in a new directory.

Consumes frozen JSON; no EOS library, private plant access, strategy or training.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario
from aegis_dc.thermodynamics import SaturationTable


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'evidence/mainline/engineering/06-phase'


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def configured(values):
    scenario = load_scenario(ROOT / 'configs/full-facility-mainline-v2.json')
    for parameter in scenario['parameters']:
        if parameter['id'] in values:
            parameter.update(value=values[parameter['id']], basis='synthetic_assumption',
                             source_note='Controlled ticket 06 engineering input; not field data.')
    return scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    reference_path = BASE / 'eos-reference-01/direct-eos-reference.json'
    reference = json.loads(reference_path.read_text(encoding='utf-8'))
    declared = [
        {'id': 'normal', 'duration_s': 2, 'step_s': 0.5, 'parameters': {}},
        {'id': 'heating-2MJ', 'duration_s': 1, 'step_s': 1,
         'parameters': {'condenser_conductance': 0}, 'expected_delta_U_J': 2000000},
        {'id': 'cooling-2MJ', 'duration_s': 1, 'step_s': 1,
         'parameters': {'solid_coolant_conductance': 0}, 'expected_delta_U_J': -2000000},
        {'id': 'both-closed', 'duration_s': 1, 'step_s': 1,
         'parameters': {'solid_coolant_conductance': 0, 'condenser_conductance': 0}},
        {'id': 'reverse-condenser', 'duration_s': 1, 'step_s': 1,
         'parameters': {'solid_coolant_conductance': 0,
                        'initial_cold_temperature': 310, 'initial_hot_temperature': 310}},
        {'id': 'reverse-closed', 'duration_s': 1, 'step_s': 1,
         'parameters': {'solid_coolant_conductance': 0, 'condenser_conductance': 0,
                        'initial_cold_temperature': 310, 'initial_hot_temperature': 310}},
        {'id': 'stopped-internal-flow', 'duration_s': 1, 'step_s': 1,
         'parameters': {'internal_pump_pressure_rise': 0}, 'expected_delta_U_J': 2000000},
        {'id': 'heating-transient', 'duration_s': 10, 'step_s': 0.25,
         'parameters': {'condenser_conductance': 0}},
        {'id': 'cooling-transient', 'duration_s': 10, 'step_s': 0.25,
         'parameters': {'solid_coolant_conductance': 0}},
    ]
    for history in reference['fixed_volume_histories'][1:]:
        initial = history['initial_MUV']
        declared.append({'id': history['id'], 'duration_s': 1, 'step_s': 1,
                         'parameters': {'solid_coolant_conductance': 0, 'condenser_conductance': 0,
                                        'coolant_inventory': initial['mass_kg'],
                                        'coolant_initial_energy': initial['internal_energy_J'],
                                        'coolant_control_volume': initial['volume_m3']}})
    endpoint = reference['saturation_endpoint_cases'][10]['MUV']
    expected_rejection = {'id': 'runtime-upper-domain-exit', 'duration_s': 0.01, 'step_s': 0.01,
                          'parameters': {'coolant_inventory': 2000,
                                         'coolant_initial_energy': 2000 * endpoint['internal_energy_J'],
                                         'coolant_control_volume': 2000 * endpoint['volume_m3'],
                                         'initial_solid_temperature': 370, 'condenser_conductance': 0}}
    write_new(output / 'declared-inputs.json', {'scope': 'ENGINEERING_FIXTURES_ONLY',
              'runs': declared, 'expected_rejection': expected_rejection})
    runs, summaries = {}, {}
    for item in declared:
        name = item['id']
        result = simulate_scenario(configured(item['parameters']), duration_s=item['duration_s'], step_s=item['step_s'])
        save_run(result, output / name)
        # Validate saved bytes and counts by fresh read, not the return from save.
        manifest = json.loads((output / name / 'run.json').read_text(encoding='utf-8'))
        for artifact, identity in manifest['artifacts'].items():
            path = output / name / artifact
            assert file_sha(path) == identity['sha256']
            assert len(path.read_text(encoding='utf-8').splitlines()) == identity['records'] or artifact == 'scenario.json'
        assert manifest['code_identity']['implementation_has_changes'] is False
        assert manifest['property_reference']['sha256'] == reference['property_table_sha256']
        assert result['research_trials'] == result['model_calls'] == result['training_calls'] == 0
        trace = [json.loads(line) for line in (output / name / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
        balance_rows = [json.loads(line) for line in (output / name / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
        phases = [row['domains']['equipment_environment']['refrigerant'] for row in trace]
        assert all(len(row['domains']) == 8 for row in trace)
        assert all(0 <= state['quality'] <= 1 for state in phases)
        delta = phases[-1]['internal_energy_J'] - phases[0]['internal_energy_J']
        if 'expected_delta_U_J' in item:
            assert abs(delta - item['expected_delta_U_J']) < 1e-6
        summaries[name] = {'source_commit': manifest['code_identity']['git_commit'],
                           'scenario_sha256': manifest['scenario_sha256'],
                           'phase_start': phases[0], 'phase_end': phases[-1], 'delta_U_J': delta,
                           'max_phase_mass_error_kg': max(abs(p['liquid_mass_kg'] + p['vapor_mass_kg'] - p['mass_kg']) for p in phases),
                           'max_energy_residual_J': manifest['summary']['max_energy_residual_J'],
                           'max_mass_residual_kg': manifest['summary']['max_mass_residual_kg'],
                           'whole_run_energy_residual_J': manifest['summary']['whole_run_energy_residual_J'],
                           'trace_records': len(phases), 'balances': len(balance_rows)}
        runs[name] = balance_rows

    def final_water(name):
        storage = runs[name][-1]['storage_after_J']
        return storage['hot'] + storage['cold']

    condensation_water = final_water('cooling-2MJ') - final_water('both-closed')
    reverse_water = final_water('reverse-condenser') - final_water('reverse-closed')
    assert abs(condensation_water - 2000000) < 1e-6
    assert abs(reverse_water + summaries['reverse-condenser']['delta_U_J']) < 1e-5

    table = SaturationTable.from_file(ROOT / 'configs/materials/reference-r134a-saturation.json')
    rejections = []
    for item in reference['refused_cases']:
        try:
            table.flash(**item['MUV'])
        except ValueError as error:
            rejections.append({'id': item['id'], 'input_MUV': item['MUV'],
                               'expected_EOS': item['expected_EOS'], 'error': str(error)})
        else:
            raise AssertionError('An intentionally unsupported EOS state was accepted')
    scenario = configured(expected_rejection['parameters'])
    try:
        simulate_scenario(scenario, duration_s=0.01, step_s=0.01)
    except ValueError as error:
        rejections.append({'id': expected_rejection['id'], 'error': str(error),
                           'input': expected_rejection, 'successful_trajectory_returned': False})
        write_new(output / 'domain-exit-scenario.json', scenario)
    else:
        raise AssertionError('The runtime silently continued beyond its table domain')
    write_new(output / 'expected-rejections.json', rejections)
    files = {str(path.relative_to(output)).replace('\\', '/'): file_sha(path)
             for path in sorted(output.rglob('*')) if path.is_file()}
    receipt = {'schema': 'aegisdc-phase-engineering-receipt-v1', 'status': 'PASS',
               'scope': 'Finite eight-domain engineering fixtures; no empirical/field validation',
               'implementation_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'author_script_sha256': file_sha(Path(__file__).resolve()),
               'direct_eos_reference_sha256': file_sha(reference_path),
               'property_sha256': reference['property_table_sha256'], 'runs': summaries,
               'shared_condenser_checks': {'cooling_water_gain_J': condensation_water,
                                           'reverse_water_gain_J': reverse_water,
                                           'reverse_refrigerant_gain_J': summaries['reverse-condenser']['delta_U_J']},
               'expected_rejections': len(rejections), 'artifacts': files,
               'runtime_imported_CoolProp': any(name.startswith('CoolProp') for name in sys.modules),
               'registered_research_trials': 0, 'training_calls': 0, 'model_calls': 0,
               'field_calibration': 'PENDING', 'research_gain': 'NOT_ESTABLISHED',
               'M1_gate': 'IN_PROGRESS', 'overall_goal': 'ACTIVE'}
    assert receipt['runtime_imported_CoolProp'] is False
    write_new(output / 'receipt.json', receipt)
    print(json.dumps({'status': receipt['status'], 'runs': len(summaries),
                      'expected_rejections': len(rejections),
                      'receipt_sha256': file_sha(output / 'receipt.json')}))


if __name__ == '__main__':
    main()
