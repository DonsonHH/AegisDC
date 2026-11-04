"""Finite engineering regression only: controller power cycle and trip hysteresis."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def run(label):
    directory = HERE / label
    directory.mkdir(exist_ok=False)
    base = load_scenario(ROOT / 'configs/full-facility-mainline-v2.json')
    events = [
        {'time_s': 0.25, 'parameter_id': 'grid_capacity', 'value': 0,
         'source_note': 'Engineering controller power-loss regression; no real device action.'},
        {'time_s': 1.25, 'parameter_id': 'grid_capacity', 'value': 10000000,
         'source_note': 'Engineering controller power-restoration regression; no policy or gain trial.'},
    ]
    summary = {'scope': __doc__, 'cases': {}, 'research_trials': 0}
    for name, reset_temperature, timed_inputs in [
        ('uninterrupted', 290, []), ('power-cycle', 290, events),
        ('below-reset', 303.5, events),
    ]:
        scenario = deepcopy(base)
        values = {'protection_temperature': 304, 'protection_reset_temperature': reset_temperature,
                  'initial_solid_temperature': 300, 'ups_energy': 0, 'diesel_initial_fuel_energy': 0}
        for record in scenario['parameters']:
            if record['id'] in values:
                record.update(value=values[record['id']], basis='synthetic_assumption', source_refs=['Rrun'],
                              source_note='Declared engineering controller-power-cycle regression input; no site observation or calibrated working point.')
        result = simulate_scenario(scenario, duration_s=2, boundary_events=timed_inputs)
        manifest = save_run(result, directory / name)
        final = result['trace'][-1]['domains']
        summary['cases'][name] = {
            'source_commit': manifest['code_identity']['git_commit'],
            'implementation_has_changes': manifest['code_identity']['implementation_has_changes'],
            'source_tree_sha256': manifest['code_identity']['source_tree_sha256'],
            'final_mode': final['control_monitoring']['mode'],
            'protection_latched': final['control_monitoring'].get('protection_latched'),
            'final_temperature_K': final['equipment_environment']['refrigerant']['temperature_K'],
            'reset_temperature_K': reset_temperature,
            'compute_power_W': final['power']['actual_powers_W']['compute'],
            'internal_volume_flow_m3_s': final['facility_cooling']['internal_pump']['volume_flow_m3_s'],
        }
    with (directory / 'summary.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.label), indent=2, allow_nan=False))
