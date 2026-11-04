"""Offline author only: freeze direct CoolProp inputs/outputs in a fresh directory.

Never imported by tests or the plant. No aegis_dc implementation is used to
generate expected states. Supply an isolated CoolProp 8.0.0 target explicitly.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eos-target', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise FileExistsError('A new author output directory is required')
    sys.path.insert(0, str(arguments.eos_target.resolve()))
    import CoolProp
    import CoolProp.CoolProp as CP

    assert CoolProp.__version__ == '8.0.0'
    assert CoolProp.__gitrevision__ == 'ae81610e7d23efc57f9d051c8e70a4d66e87537f'
    extension_sha = file_sha(Path(CP.__file__))
    assert extension_sha == 'eba3061d6e3cf1435573156f61310389ea2e2c8918b893032d9ca5737ed56440'
    CP.set_reference_state('R134a', 'DEF')
    eos = CP.AbstractState('HEOS', 'R134a')
    root = Path(__file__).resolve().parents[4]
    table = root / 'configs/materials/reference-r134a-saturation.json'
    assert file_sha(table) == '9494001ac94e04c6b2474b1c70fdf78ff4b5958b3f5c39f9790581561097329c'
    source_config = root / 'configs/full-facility-mainline-v2.json'

    # Limits are declared before any numerical results are generated. These
    # qualify finite interpolation errors, not EOS or site accuracy.
    limits = {'pressure_relative': 1e-5, 'temperature_abs_K': 0.0005,
              'quality_abs': 5e-6, 'specific_energy_residual_abs_J_kg': 1e-6}

    def state():
        return {'pressure_Pa': eos.p(), 'temperature_K': eos.T(),
                'quality': eos.Q(), 'density_kg_m3': eos.rhomass(),
                'specific_energy_J_kg': eos.umass(), 'phase_index': int(eos.phase())}

    def flash(mass, energy, volume):
        eos.update(CP.DmassUmass_INPUTS, mass / volume, energy / mass)
        return state()

    def pq_inventory(pressure, quality, mass):
        eos.update(CP.PQ_INPUTS, pressure, quality)
        return {'mass_kg': mass, 'internal_energy_J': mass * eos.umass(),
                'volume_m3': mass / eos.rhomass()}

    # Existing v2 table-derived research initial condition, copied literally.
    # EOS supplies the expected states for these independent Dmass/Umass inputs.
    histories = []
    initializations = [('nominal-v2', {'mass_kg': 2000.0,
                         'internal_energy_J': 516335850.31469756,
                         'volume_m3': 6.647467643830208}, [-2000000.0, 0.0, 2000000.0])]
    for label, quality in [('liquid-rich', 0.001), ('vapor-rich', 0.99)]:
        initializations.append((label, pq_inventory(800000.0, quality, 2000.0),
                                [-100000.0, 0.0, 100000.0]))
    for label, initial, changes in initializations:
        records = []
        for heat in changes:
            energy = initial['internal_energy_J'] + heat
            expected = flash(initial['mass_kg'], energy, initial['volume_m3'])
            assert expected['phase_index'] == int(CP.iphase_twophase)
            assert 0.0 <= expected['quality'] <= 1.0
            records.append({'net_heat_J': heat, 'internal_energy_J': energy,
                            'expected_EOS': expected})
        histories.append({'id': label, 'initial_MUV': initial, 'states': records})

    endpoints = []
    for pressure in (100000.0, 3000000.0):
        for quality in (0.0, 1e-10, 1e-5, 0.5, 0.99999, 1.0 - 1e-10, 1.0):
            inventory = pq_inventory(pressure, quality, 1.0)
            endpoints.append({'given_pressure_Pa': pressure, 'given_quality': quality,
                              'MUV': inventory, 'expected_EOS_PQ': state()})

    refused = []
    for pressure in (90000.0, 3100000.0):
        inventory = pq_inventory(pressure, 0.5, 2000.0)
        refused.append({'id': 'outside-pressure-' + str(int(pressure)),
                        'MUV': inventory, 'expected_EOS': state(),
                        'expected_table_outcome': 'REJECT_OUTSIDE_PRESSURE_DOMAIN'})
    for label, temperature in [('subcooled', 290.0), ('superheated', 350.0)]:
        eos.update(CP.PT_INPUTS, 800000.0, temperature)
        inventory = {'mass_kg': 2000.0, 'internal_energy_J': 2000.0 * eos.umass(),
                     'volume_m3': 2000.0 / eos.rhomass()}
        expected = state()
        assert expected['phase_index'] != int(CP.iphase_twophase)
        refused.append({'id': label, 'MUV': inventory, 'expected_EOS': expected,
                        'expected_table_outcome': 'REJECT_NO_TWO_PHASE_ROOT'})

    document = {'schema': 'aegisdc-phase-direct-eos-reference-v1',
                'recorded_UTC': datetime.now(timezone.utc).isoformat(),
                'scope': 'Finite same-EOS numerical cross-check; no empirical/field validation or research trial',
                'source': {'library': 'CoolProp', 'version': CoolProp.__version__,
                           'gitrevision': CoolProp.__gitrevision__, 'backend': 'HEOS',
                           'fluid': 'R134a', 'reference_state': 'DEF',
                           'extension_sha256': extension_sha,
                           'official_API': 'https://coolprop.org/coolprop/HighLevelAPI.html',
                           'official_fluid': 'https://coolprop.org/fluid_properties/fluids/R134a.html',
                           'previous_receipt_sha256': file_sha(root / 'evidence/mainline/engineering/property-reference/receipt.json')},
                'author': {'python': platform.python_version(),
                           'script_sha256': file_sha(Path(__file__).resolve()),
                           'imports_aegis_dc': False},
                'property_table_sha256': file_sha(table),
                'input_v2_config_sha256': file_sha(source_config),
                'predeclared_limits': limits, 'fixed_volume_histories': histories,
                'saturation_endpoint_cases': endpoints, 'refused_cases': refused,
                'field_medium_identity': 'UNKNOWN', 'research_trials': 0, 'training_calls': 0}
    arguments.output.mkdir(parents=True, exist_ok=False)
    output_file = arguments.output / 'direct-eos-reference.json'
    output_file.write_text(json.dumps(document, indent=2, allow_nan=False) + '\n',
                           encoding='utf-8', newline='\n')
    print(json.dumps({'file': str(output_file), 'sha256': file_sha(output_file),
                      'fixed_volume_states': 9, 'endpoint_states': 14,
                      'explicit_refusals': 4}))


if __name__ == '__main__':
    main()
