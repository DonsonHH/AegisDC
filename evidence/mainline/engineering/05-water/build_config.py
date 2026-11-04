"""Derive the explicit water-v3 fixture without changing the v1/v2 inputs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from patrol_rsi.contracts import digest


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'configs/full-facility-mainline-v2.json'
TARGET = ROOT / 'configs/full-facility-mainline-water-v3.json'


def main():
    if TARGET.exists():
        raise ValueError('The water fixture already exists; preserve the input')
    scenario = json.loads(BASE.read_text(encoding='utf-8'))
    scenario['id'] = scenario['id'].removesuffix('-v2') + '-water-v3'
    scenario['sources']['Rwater'] = {
        'classification': 'reference_calculation',
        'uri': 'docs/mainline/water-verification.md',
        'scope': 'Synthetic series-valve characteristic, shutoff interlock and independent water engineering checks; no field calibration.',
    }
    parameters = {row['id']: row for row in scenario['parameters']}
    for name, value in [('lake_hydraulic_resistance', 12000000),
                        ('internal_hydraulic_resistance', 5000000)]:
        parameters[name].update(value=value, source_refs=['Rwater'], source_note=
            'Passive filter/pipe resistance only, excluding the explicit series valve. Research decomposition preserves the v2 full-open operating point; not a site measurement.')
    parameters['filter_resistance_multiplier']['source_note'] = (
        'Multiplier of passive lake filter/pipe resistance only. The independent valve characteristic is not multiplied. Synthetic research assumption.')
    parameters['filter_resistance_multiplier']['source_refs'] = ['Rwater']
    for loop, full_open in [('lake', 3000000), ('internal', 3333333.333333334)]:
        for suffix, quantity, unit, value, limits, note in [
            ('valve_open_resistance', 'hydraulic_resistance', 'Pa*s2/m6', full_open,
             [1, 1000000000], 'Full-open valve-group K; K(a)=Kopen/a^2 for 0<a<=1, with Kv assumed proportional to opening. Research characteristic, not vendor data.'),
            ('valve_opening', 'fraction', '1', 1, [0, 1],
             'Imposed actual aggregate valve opening. a=0 invokes an immediate hardwired pump-stop interlock; no deadhead mode or actuator dynamics. Research action/state setting.'),
        ]:
            scenario['parameters'].append({
                'id': loop + '_' + suffix, 'quantity': quantity, 'unit': unit,
                'value': value, 'valid_range': limits, 'basis': 'synthetic_assumption',
                'source_refs': ['Rwater'], 'source_note': note,
            })
    entities = {row['id']: row for row in scenario['entities']}
    entities['local_controller']['source_note'] += (
        ' Water-v3 includes a hardwired shutoff permissive relay, independent of powered sampled thermal logic, in this aggregate local control asset.')
    # The old internal pump was thermally/electrically explicit but hydraulically
    # lumped; v3 declares its fluid interfaces in the same single circulation loop.
    for direction in ('in', 'out'):
        entities['internal_pump']['ports'][direction] = {
            'direction': direction, 'carrier': 'fluid',
            'medium': 'internal_water', 'parameter_ref': None,
        }
    domain = next(row for row in scenario['domains'] if row['id'] == 'facility_cooling')
    domain['states'] += ['lake_valve_opening', 'internal_valve_opening', 'closed_valve_interlock']
    domain['inputs'] += ['imposed_actual_valve_opening']
    domain['behaviors'] += ['Series valve Kopen/a^2; exact shutoff stops its pump without deadhead']
    for loop, medium, location, pump, consumer in [
        ('lake', 'lake_water', 'loc_lake', 'intake_pump', 'plate_hx'),
        ('internal', 'internal_water', 'loc_hx', 'internal_pump', 'internal_water'),
    ]:
        identifier = loop + '_valve_group'
        ports = {direction: {'direction': direction, 'carrier': 'fluid',
                            'medium': medium, 'parameter_ref': None}
                 for direction in ('in', 'out')}
        scenario['entities'].append({
            'id': identifier, 'kind': 'asset', 'domain': 'facility_cooling',
            'label': 'Synthetic ' + loop + ' series valve group', 'location_id': location,
            'ports': ports, 'parameter_refs': [loop + '_valve_open_resistance', loop + '_valve_opening'],
            'basis': 'synthetic_assumption', 'source_refs': ['Rwater'],
            'source_note': 'One identifiable aggregate series valve; research approximation, not actual site valve selection.',
        })
        domain['entity_ids'].append(identifier)
        domain['work_interfaces'][0]['target_ids'].append(identifier)
        scenario['graphs']['functional'].append({
            'id': 'f_' + identifier, 'from': identifier, 'to': consumer, 'kind': 'requires',
            'basis': 'synthetic_assumption', 'source_refs': ['Rwater'],
            'source_note': 'Declared series-flow dependency; opening changes physical flow and cooling.',
            'parameter_refs': [loop + '_valve_opening', loop + '_valve_open_resistance'],
        })
        scenario['graphs']['control_information'].append({
            'id': 'c_' + identifier + '_status', 'from': identifier, 'to': 'local_controller',
            'kind': 'report', 'basis': 'synthetic_assumption', 'source_refs': ['Rwater'],
            'source_note': 'Actual shutoff position drives the local hardwired pump permissive; private plant signal, not dispatch evidence.',
        })
        scenario['graphs']['control_information'].append({
            'id': 'c_' + identifier + '_interlock', 'from': 'local_controller', 'to': pump,
            'kind': 'command', 'basis': 'synthetic_assumption', 'source_refs': ['Rwater'],
            'source_note': 'Aggregate local control includes a hardwired shutoff limit permissive that removes pump drive at actual opening=0, independent of controller power and sampled thermal software. Imposed position events have no actuator dynamics.',
        })
    physical = scenario['graphs']['physical']
    edges = {row['id']: row for row in physical}
    lake_feed = deepcopy(edges['w_hx'])
    lake_feed.update(id='w_lake_valve_feed', to='lake_valve_group', to_port='in', source_refs=['Rwater'])
    lake_feed['source_note'] = 'Declared synthetic series valve inserted between filter and lake HX inlet.'
    physical.append(lake_feed)
    edges['w_hx'].update({'from': 'lake_valve_group', 'source_refs': ['Rwater'],
                         'source_note': 'Valve outlet feeds lake HX side; lake and internal water remain mass separated.'})
    edges['w_internal_hot'].update(to='internal_pump', to_port='in', source_refs=['Rwater'],
                                    source_note='Explicit single internal circulation loop: buffer -> pump -> valve -> plate HX -> buffer.')
    for identifier, start, end, destination in [
        ('w_internal_pump_valve', 'internal_pump', 'internal_valve_group', 'in'),
        ('w_internal_valve_hx', 'internal_valve_group', 'plate_hx', 'internal_in'),
    ]:
        physical.append({'id': identifier, 'from': start, 'to': end, 'kind': 'fluid',
                         'from_port': 'out', 'to_port': destination,
                         'basis': 'synthetic_assumption', 'source_refs': ['Rwater'],
                         'source_note': 'Explicit single internal-water series flow; no coolant/lake mixing.'})
    scenario['assumptions'] += [
        'Water-v3 adds two aggregate series valves, each with independent Kopen/a^2, and preserves v2 full-open total resistance and thermal initialization.',
        'Valve openings are imposed actual plant states in engineering inputs. A zero opening immediately stops its own pump through a declared local hardwired interlock; static trapped pressures, deadhead heating, leakage and actuator dynamics are outside this model.',
        'Valve/pipe pressure drops are differential dynamic losses, not gauge pressures. Their hydraulic dissipation is already inside each pump total electrical heat allocation and is not added again.',
        'Positive openings whose derived resistance cannot be represented finitely are outside the numerical domain and fail explicitly.',
    ]
    scenario['runtime']['model'] = 'aegisdc-low-order-facility-water-v2'
    scenario['runtime']['topology_sha256'] = digest(scenario['graphs'])
    data = json.dumps(scenario, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    TARGET.write_text(data, encoding='utf-8', newline='\n')
    receipt = {'classification': 'SYNTHETIC_ENGINEERING_CONFIGURATION_ONLY',
               'base_input': str(BASE.relative_to(ROOT)),
               'base_sha256': hashlib.sha256(BASE.read_bytes()).hexdigest(),
               'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'output': str(TARGET.relative_to(ROOT)),
               'output_sha256': hashlib.sha256(data.encode('utf-8')).hexdigest(),
               'topology_sha256': scenario['runtime']['topology_sha256']}
    target_receipt = Path(__file__).with_name('config-source-receipt.json')
    with target_receipt.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
