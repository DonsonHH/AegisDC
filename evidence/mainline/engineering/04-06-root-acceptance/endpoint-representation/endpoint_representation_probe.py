"""Reproduce the review's finite endpoint-representation probe.

This is an engineering input-representation diagnostic, not a scientific trial
or an independent empirical/EOS validation. It does not clip admissible quality
and does not assert that nominal construction guarantees exact encoded M/U/V.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    if args.output.exists():
        raise FileExistsError(args.output)
    sys.path.insert(0, str(repo / 'src'))
    from aegis_dc.thermodynamics import SaturationTable
    table_path = repo / 'configs/materials/reference-r134a-saturation.json'
    implementation_path = repo / 'src/aegis_dc/thermodynamics.py'
    table = SaturationTable.from_file(table_path)
    indices = [0, 1, 40, 100, 200, 300, 400, 510, 511]
    qualities = [0, 1e-10, 1e-5, .1, .5, .99, 1-1e-10, 1]
    masses = [.1, 1, 3, 10, 2000, 12345]
    failures, outcomes = [], []
    for index in indices:
        row = table.rows[index]
        for nominal_quality in qualities:
            for mass in masses:
                # Preserve the exact operation order of the original review.
                volume = mass * ((1-nominal_quality) * row['v_l_m3_kg']
                                 + nominal_quality * row['v_v_m3_kg'])
                energy = mass * ((1-nominal_quality) * row['u_l_J_kg']
                                 + nominal_quality * row['u_v_J_kg'])
                specific_volume = volume / mass
                target = energy / mass
                reconstructed_quality = ((specific_volume - row['v_l_m3_kg'])
                                         / (row['v_v_m3_kg'] - row['v_l_m3_kg']))
                record = {
                    'table_row_index': index,
                    'nominal_pressure_Pa': row['p_Pa'],
                    'nominal_quality': nominal_quality,
                    'inputs': {'mass_kg': mass, 'internal_energy_J': energy,
                               'volume_m3': volume},
                    'inputs_float_hex': {
                        'mass_kg': float(mass).hex(),
                        'internal_energy_J': energy.hex(),
                        'volume_m3': volume.hex(),
                    },
                    'frozen_row_primitives': {
                        name: row[name] for name in ('p_Pa', 'v_l_m3_kg', 'v_v_m3_kg',
                                                   'u_l_J_kg', 'u_v_J_kg')},
                    'construction_expected': {
                        'method': 'Analytic equilibrium mixture of frozen row primitives, then scaled by nominal mass.',
                        'nominal_pressure_Pa': row['p_Pa'],
                        'nominal_quality': nominal_quality,
                        'qualification': 'Nominal construction expectation only. Floating-point encoded M/U/V may lie outside strict quality admissibility; this is not a requirement to clip it.'},
                    'representation_observation': {
                        'specific_volume_m3_kg': specific_volume,
                        'specific_energy_J_kg': target,
                        'reconstructed_quality': reconstructed_quality,
                        'reconstructed_quality_float_hex': reconstructed_quality.hex(),
                        'specific_volume_minus_saturated_vapor_m3_kg': specific_volume - row['v_v_m3_kg'],
                        'specific_energy_minus_saturated_vapor_J_kg': target - row['u_v_J_kg'],
                        'quality_admissible_at_nominal_pressure': 0 <= reconstructed_quality <= 1,
                    },
                }
                try:
                    state = table.flash(mass, energy, volume)
                    wrong = abs(state['pressure_Pa'] / row['p_Pa'] - 1) > 1e-8
                    record['outcome'] = {'status': 'WRONG_PRESSURE' if wrong else 'RETURNED',
                                         'pressure_Pa': state['pressure_Pa'],
                                         'quality': state['quality']}
                    if wrong:
                        failures.append(record)
                except Exception as error:
                    record['outcome'] = {'status': 'REFUSED', 'exception_type': type(error).__name__,
                                         'exception_message': str(error)}
                    failures.append(record)
                outcomes.append(record)
    result = {
        'schema': 'aegisdc-review-endpoint-representation-probe-v1',
        'classification': 'FINITE_ENGINEERING_NUMERICAL_REPRESENTATION_DIAGNOSTIC',
        'source': {
            'worktree': str(repo),
            'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo,
                                                  text=True).strip(),
            'property_table_sha256': sha256(table_path.read_bytes()).hexdigest(),
            'thermodynamics_source_sha256': sha256(implementation_path.read_bytes()).hexdigest(),
            'author_program_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'interpreter': sys.executable, 'python_version': sys.version,
        },
        'probe': {'row_indices': indices, 'nominal_qualities': qualities, 'masses_kg': masses,
                  'case_count': len(outcomes), 'refused_or_wrong_count': len(failures)},
        'interpretation': 'The five nominal pure-vapor constructions reconstruct x=1.0000000000000002 after mass/volume roundoff. Refusal is consistent with the current strict [0,1] no-quality-clipping contract. This diagnostic quantifies input representation; it neither extends the physical domain nor establishes a required code change.',
        'refused_or_wrong_cases': failures,
        'all_outcomes': outcomes,
        'research_trials': 0,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                     allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'case_count': len(outcomes), 'refused_or_wrong_count': len(failures),
                      'output': str(args.output.resolve()),
                      'sha256': sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
