"""Author the explicit reserve-v6 research profile once, without changing v1-v5."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from patrol_rsi.contracts import digest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'configs/full-facility-mainline-reserve-v6.json')
    output = parser.parse_args().output
    if output.exists():
        raise FileExistsError('Use a new profile path; existing originals are never overwritten')
    parent = ROOT / 'configs/full-facility-mainline-control-v5.json'
    scenario = json.loads(parent.read_text(encoding='utf-8'))
    scenario['id'] = 'zhengzhou-inspired-synthetic-full-facility-reserve-v6'
    scenario['scope'] = 'Same complete synthetic facility with explicit finite reserve actors and paid sensible backup cooling; not as-built Zhengzhou or calibrated tower performance.'
    scenario['sources']['Rreserve'] = {'classification': 'synthetic_assumption',
        'uri': 'docs/mainline/10-reserve-implementation.md',
        'scope': 'Finite autonomous UPS/generator control, starter inventory, common distribution and sensible cooler; explicit research design, not site facts.'}
    scenario['sources']['Rreserve_parent'] = {'classification': 'reference_calculation',
        'uri': 'configs/full-facility-mainline-control-v5.json',
        'scope': 'Parent bytes SHA-256 ' + sha256(parent.read_bytes()).hexdigest()}
    definitions = [
        ('ups_internal_control_power', 'power', 'W', 100, [1, 10000]),
        ('generator_internal_control_power', 'power', 'W', 10, [1, 10000]),
        ('generator_start_power', 'power', 'W', 1000, [1, 100000]),
        ('generator_initial_start_energy', 'energy', 'J', 100000, [0, 10000000]),
        ('diesel_idle_fuel_power', 'power', 'W', 1000, [0, 1000000]),
        ('ups_transfer_delay', 'delay_time', 's', 0.2, [0, 30]),
        ('diesel_transfer_delay', 'delay_time', 's', 2, [0, 60]),
        ('backup_cooling_transfer_delay', 'delay_time', 's', 2, [0, 300]),
        ('backup_fan_nominal_power', 'power', 'W', 20000, [1, 1000000]),
        ('backup_air_capacity_rate', 'heat_capacity_rate', 'W/K', 500000, [1, 10000000]),
        ('backup_conductance', 'thermal_conductance', 'W/K', 300000, [0, 10000000]),
        ('backup_heat_capacity', 'power', 'W', 1500000, [0, 10000000]),
    ]
    flags = ['shared_distribution_available', 'ups_in_service', 'ups_transfer_ok',
             'diesel_in_service', 'diesel_start_ok', 'diesel_transfer_ok',
             'backup_cooling_in_service', 'backup_cooling_transfer_ok', 'backup_cooling_requested']
    definitions += [(name, 'fraction', '1', 0 if name == 'backup_cooling_requested' else 1, [0, 1]) for name in flags]
    for name, quantity, unit, value, limits in definitions:
        scenario['parameters'].append({'id': name, 'quantity': quantity, 'unit': unit, 'value': value,
            'valid_range': limits, 'basis': 'synthetic_assumption', 'source_refs': ['Rreserve'],
            'source_note': 'Declared bounded reserve-profile research input; actual site value/coverage is unknown.'})
    parameters = {p['id']: p for p in scenario['parameters']}
    parameters['room_temperature']['value'] += parameters['ups_internal_control_power']['value'] / parameters['room_conductance']['value']
    parameters['room_temperature']['source_refs'] = ['Rrun', 'Rreserve_parent']
    parameters['room_temperature']['source_note'] = 'Parent steady room temperature plus paid UPS internal-control heat divided by room conductance; derived synthetic initialization.'

    entities = {e['id']: e for e in scenario['entities']}
    note = 'Explicit synthetic reserve topology; coverage and backup piping at the real site remain unknown.'
    def port(direction, carrier='electric'):
        return {'direction': direction, 'carrier': carrier,
                'medium': 'ac_lv' if carrier == 'electric' else 'thermal_transfer',
                'parameter_ref': 'lv_voltage' if carrier == 'electric' else None}
    def asset(identifier, domain, label, location, ports, refs):
        return {'id': identifier, 'kind': 'asset', 'domain': domain, 'label': label,
                'location_id': location, 'ports': ports, 'parameter_refs': refs,
                'basis': 'synthetic_assumption', 'source_refs': ['Rreserve'], 'source_note': note}
    additions = [asset('load_distribution', 'power', 'Shared distribution enclosure with separate normal/protected rails',
                       'loc_electrical', {'normal_in': port('in'), 'normal_out': port('out'),
                                          'protected_in': port('in'), 'protected_out': port('out')},
                       ['shared_distribution_available']),
                 asset('reserve_external_air', 'facility_cooling', 'Declared external sensible-heat boundary',
                       'loc_hx', {'heat': port('in', 'heat')}, ['room_ambient_temperature'])]
    scenario['entities'].extend(additions)
    for item in additions:
        next(d for d in scenario['domains'] if d['id'] == item['domain'])['entity_ids'].append(item['id'])
    entities['backup_tower']['ports'].update(power=port('in'), heat_out=port('out', 'heat'))
    entities['backup_tower']['parameter_refs'] = [name for name, *_ in definitions if name.startswith('backup_')]
    entities['backup_tower']['source_note'] = 'Effective sensible, no-evaporation surrogate with finite paid fan/UA/capacity; not a real tower curve.'
    entities['generator']['ports']['control_power'] = port('in')
    entities['generator']['parameter_refs'] += [name for name, *_ in definitions if name.startswith(('generator_', 'diesel_'))]
    entities['ups']['parameter_refs'] += ['ups_internal_control_power', 'ups_transfer_delay', 'ups_in_service', 'ups_transfer_ok']
    physical = scenario['graphs']['physical']
    for edge in physical:
        if edge['from'] == 'main_switchboard':
            edge.update({'from': 'load_distribution', 'from_port': 'normal_out', 'source_note': note})
        elif edge['from'] == 'ups' and edge['kind'] == 'electric':
            edge.update({'from': 'load_distribution', 'from_port': 'protected_out', 'source_note': note})
    def edge(identifier, source, target, kind, **details):
        return dict(id=identifier, **{'from': source, 'to': target}, kind=kind,
                    basis='synthetic_assumption', source_refs=['Rreserve'], source_note=note, **details)
    physical += [edge('p_normal_distribution', 'main_switchboard', 'load_distribution', 'electric', from_port='aux', to_port='normal_in'),
                 edge('p_protected_distribution', 'ups', 'load_distribution', 'electric', from_port='protected_out', to_port='protected_in'),
                 edge('p_generator_control', 'load_distribution', 'generator', 'electric', from_port='normal_out', to_port='control_power'),
                 edge('p_backup_fan', 'load_distribution', 'backup_tower', 'electric', from_port='normal_out', to_port='power'),
                 edge('q_backup_water', 'internal_water', 'backup_tower', 'heat', from_port='heat_out', to_port='heat'),
                 edge('q_backup_air', 'backup_tower', 'reserve_external_air', 'heat', from_port='heat_out', to_port='heat')]
    scenario['graphs']['functional'] += [edge('f_common_distribution', 'load_distribution', 'critical_service', 'requires', parameter_refs=['shared_distribution_available'])]
    scenario['graphs']['control_information'] += [edge('c_backup_selector', 'local_controller', 'backup_tower', 'command')]
    scenario['assumptions'] += [
        'UPS internal control and generator internal control/cranking have distinct finite paid supply; they do not depend on an unsupplied main PLC.',
        'Generator starter energy is a separate ideal DC store inside the generator asset; no recharge is modeled. Its output dissipates outside once.',
        'The shared distribution enclosure gates normal and protected rails under one explicit common cause, while UPS coverage remains only the original three auxiliary loads.',
        'The effective standby sensible exchanger shares one actual internal circulation capacity with the mutually exclusive primary path, adds no water mass, and has no evaporation model.',
        'Fan and generator control/cranking heat exits outside; UPS internal control heat enters the room. Site tower/storage/coverage data remain unresolved.']
    scenario['runtime'].update(model='aegisdc-low-order-facility-reserve-v4',
                               reserve_profile='aegisdc-reserve-response-v1',
                               topology_sha256=digest(scenario['graphs']))
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(scenario, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'file': str(output), 'topology_sha256': scenario['runtime']['topology_sha256'],
                      'sha256': sha256(output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
