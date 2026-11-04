"""Derive one explicit environment profile while preserving all older inputs."""
import hashlib
import json
from pathlib import Path

from patrol_rsi.contracts import digest


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'configs/full-facility-mainline-water-v3.json'
TARGET = ROOT / 'configs/full-facility-mainline-environment-v4.json'


def main():
    if TARGET.exists():
        raise ValueError('Preserve the existing environment profile; do not overwrite it')
    scenario = json.loads(BASE.read_text(encoding='utf-8'))
    scenario['id'] = 'aegisdc-zhengzhou-inspired-full-facility-environment-v4'
    scenario['sources']['Renv'] = {'classification': 'reference_calculation',
        'uri': 'docs/mainline/environment-verification.md',
        'scope': 'Declared hot-water leakage, sensible floor-water storage, risk-only condensation boundary and independent access-permission engineering model; not site calibration.'}
    scenario['sources']['Rpsychro'] = {'classification': 'published_model',
        'uri': 'https://raw.githubusercontent.com/psychrometrics/psychrolib/2.5.0/src/c/psychrolib.c',
        'scope': 'Verify ASHRAE 2017 ch.1 eq.6 liquid-water saturation-pressure coefficients only. No moisture/latent-heat model or dispatch evidence is imported.'}
    for name, quantity, unit, value, limits, note in [
        ('internal_hot_leak_mass_flow', 'mass_flow', 'kg/s', 0, [0, 10],
         'Imposed actual well-mixed hot-buffer water leakage to the floor pool. This is not a hole/pressure law or an inferred hidden fault; thermal energy cp*T leaves the hot inventory and enters the pool once.'),
        ('minimum_internal_hot_mass', 'mass', 'kg', 9000, [1, 50000],
         'Explicit minimum inventory for this constant hydraulic working-domain approximation. A positive-rate loss beyond it fails, rather than inventing low-inventory pump/cavitation geometry.'),
        ('it_access_permit', 'fraction', '1', 1, [0, 1],
         'Binary imposed access-gate permission: 0 forbids IT-zone work, 1 permits only when independent access/qualification/tool/environment conditions also hold. No physical-network reachability grants access.'),
        ('maximum_room_work_temperature', 'temperature', 'K', 313.15, [273.16, 333.15],
         'Declared synthetic work-permission temperature threshold, not an occupational or observed site limit. Rising crossing closes work; falling crossing opens it with event splitting and directional equality semantics.'),
    ]:
        scenario['parameters'].append({'id': name, 'quantity': quantity, 'unit': unit,
            'value': value, 'valid_range': limits, 'basis': 'synthetic_assumption',
            'source_refs': ['Renv'], 'source_note': note})
    parameters = {row['id']: row for row in scenario['parameters']}
    parameters['internal_hot_mass']['source_note'] = 'Initial hot-buffer inventory; dynamic leakage debits this mass and its sensible energy. Synthetic research setting, not a site measurement.'
    parameters['internal_hot_mass']['source_refs'] = ['Renv']
    parameters['room_humidity']['valid_range'] = [0, 1]
    parameters['room_humidity']['source_refs'] = ['Renv', 'Rpsychro']
    parameters['room_humidity']['source_note'] = 'Prescribed RH boundary for risk-only vapor/surface saturation comparison. No evolving air-moisture inventory, condensate mass, evaporation or latent heat is computed.'
    entities = {row['id']: row for row in scenario['entities']}
    entities['internal_water']['ports']['leak_out'] = {'direction': 'out', 'carrier': 'fluid',
        'medium': 'internal_water', 'parameter_ref': 'internal_hot_leak_mass_flow'}
    entities['internal_water']['parameter_refs'] += ['internal_hot_leak_mass_flow', 'minimum_internal_hot_mass']
    entities['room']['parameter_refs'].append('maximum_room_work_temperature')
    entities['drainage']['ports']['cooling_leak_in'] = {'direction': 'in', 'carrier': 'fluid',
        'medium': 'internal_water', 'parameter_ref': 'internal_hot_leak_mass_flow'}
    entities['drainage']['source_refs'] = ['Renv']
    entities['drainage']['source_note'] = 'Well-mixed adiabatic floor pool and drain; it receives actual hot-water leakage plus separately declared ambient nuisance water. No evaporation, contamination or inferred site geometry.'
    entities['drainage']['parameter_refs'].append('internal_hot_leak_mass_flow')
    gate = {'id': 'it_access_gate', 'kind': 'asset', 'domain': 'space_access',
        'label': 'Synthetic IT-zone access permission gate', 'location_id': 'loc_control',
        'ports': {}, 'parameter_refs': ['it_access_permit'], 'basis': 'synthetic_assumption',
        'source_refs': ['Renv'], 'source_note': 'Identifiable discrete permission gate on the independent personnel-access relation; no mechanical door geometry or powered actuator dynamics.'}
    scenario['entities'].append(gate)
    domains = {row['id']: row for row in scenario['domains']}
    domains['space_access']['entity_ids'].append('it_access_gate')
    domains['space_access']['work_interfaces'][0]['target_ids'].append('it_access_gate')
    domains['space_access']['states'] += ['floor_water_mass', 'floor_water_sensible_energy', 'floor_water_temperature', 'it_access_permit']
    domains['space_access']['states'].append('room_temperature_work_permission')
    domains['space_access']['behaviors'] += ['Actual hot-water transfer and ambient nuisance inflow mix before temperature-dependent drainage; independent access permission can abort unsafe work']
    domains['facility_cooling']['states'] += ['remaining_hot_water_mass', 'internal_hot_leak_mass_flow']
    domains['equipment_environment']['states'].append('condensation_boundary_risk_only')
    domains['equipment_environment']['behaviors'].append('Prescribed RH times air saturation pressure compared with saturation at the cold-buffer bulk surface proxy; no condensate or latent heat')
    scenario['graphs']['physical'].append({'id': 'w_hot_leak_to_floor', 'from': 'internal_water',
        'to': 'drainage', 'kind': 'fluid', 'from_port': 'leak_out', 'to_port': 'cooling_leak_in',
        'basis': 'synthetic_assumption', 'source_refs': ['Renv'],
        'source_note': 'Actual internal hot-water mass and cp*T sensible energy transfer to a distinct floor pool; no refrigerant debit, no external energy source.'})
    scenario['graphs']['functional'].append({'id': 'f_it_access_gate', 'from': 'it_access_gate',
        'to': 'loc_it', 'kind': 'access_condition', 'parameter_refs': ['it_access_permit'],
        'basis': 'synthetic_assumption', 'source_refs': ['Renv'],
        'source_note': 'Access permission restricts the declared personnel graph independently of electrical/fluid connectivity.'})
    scenario['graphs']['functional'].append({'id': 'f_room_work_temperature', 'from': 'room',
        'to': 'loc_it', 'kind': 'access_condition', 'parameter_refs': ['maximum_room_work_temperature'],
        'basis': 'synthetic_assumption', 'source_refs': ['Renv'],
        'source_note': 'Explicit research thermal-work cutoff on the personnel graph; not an occupational standard or site operating limit.'})
    scenario['graphs']['control_information'].append({'id': 'c_it_access_permission',
        'from': 'it_access_gate', 'to': 'local_controller', 'kind': 'report',
        'basis': 'synthetic_assumption', 'source_refs': ['Renv'],
        'source_note': 'Private plant gate-permission state only; not a future/instantaneous dispatch alarm or an implemented authorization action.'})
    scenario['media']['floor_water']['description'] = 'Distinct floor-water pool mixing external ambient nuisance water and explicitly transferred hot internal water; same assumed constant cp, no cooling return path.'
    scenario['assumptions'] += [
        'Environment-v4 starts at the same healthy water-v3 working point; actual hot-water leakage defaults to zero and gate permission to one.',
        'Remaining hot-water mass changes its thermal capacity. Hydraulic behavior is valid only at or above the declared minimum hot inventory; below it the run fails without inventing suction geometry or clipping inventory.',
        'Hot leakage exports cp*T using the same zero-K sensible reference as the liquid inventory and floor pool; pressure work and kinetic/elevation terms are outside this bounded incompressible model.',
        'The separate external nuisance-water source and initial floor pool are at the declared ambient temperature. The floor pool mixes adiabatically and drains at its evolving actual temperature; no evaporation, latent heat or floor-to-room transfer is modeled.',
        'Air sensible storage and liquid heat remain separately accounted. RH is an imposed diagnostic boundary with no moisture-mass inventory or condensate production.',
        'Cold-buffer bulk temperature is an explicit proxy for an exposed cold surface, not a wall/insulation model. The risk criterion uses liquid-water saturation only at 273.16 to 333.15 K, without extrapolation.',
        'IT access requires binary gate permission, open environmental conditions and the independent access graph with all qualifications/tools. A gate closes work permission but does not erase elapsed labor or move personnel/tools.',
        'The explicit room work-temperature threshold closes on rising crossing and opens on falling crossing. Equality uses the direction of the continuous sensible-temperature trajectory; a stationary initial equality is closed. No step-sized extra work is granted.',
    ]
    scenario['runtime']['model'] = 'aegisdc-low-order-facility-environment-v3'
    scenario['runtime']['topology_sha256'] = digest(scenario['graphs'])
    data = json.dumps(scenario, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    TARGET.write_text(data, encoding='utf-8', newline='\n')
    receipt = {'classification': 'SYNTHETIC_ENGINEERING_PROFILE_ONLY',
        'base_input': BASE.relative_to(ROOT).as_posix(), 'base_sha256': hashlib.sha256(BASE.read_bytes()).hexdigest(),
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'output': TARGET.relative_to(ROOT).as_posix(), 'output_sha256': hashlib.sha256(data.encode('utf-8')).hexdigest(),
        'topology_sha256': scenario['runtime']['topology_sha256']}
    with Path(__file__).with_name('config-source-receipt.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
