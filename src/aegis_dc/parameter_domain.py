"""Build named, jointly constrained engineering cases for the complete V6 facility."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from patrol_rsi.contracts import strict_json

from .decision_view import validate_nominal
from .plant import validate_boundary_events
from .refrigerant_initialization import assess_refrigerant_initialization, prepare_refrigerant_initialization
from .scenario import validate_scenario
from .sensor_channels import validate_channel_profile
from .thermodynamics import finite_number
from .time_coordinates import same_time
from .water_envelope import WATER_EVENT_PARAMETERS, assess_water_envelope
from .workforce_dispatch import validate_profile

ROOT = Path(__file__).resolve().parents[2]
DECLARATION = ROOT / 'configs/full-facility-parameter-domain-v1.json'
REFERENCES = {
    'baseline': 'configs/full-facility-mainline-reserve-v6.json',
    'fixed_sensor_reference': 'configs/full-facility-sensor-channels-v1.json',
    'public_nominal_reference': 'configs/full-facility-decision-v1/public-nominal.json',
}
PROFILE_FIELDS = {'id','duration_s','axes','initial_overrides','phase','boundary_events','enabled_fixed_measurements'}
INITIAL_AXES = frozenset({
    'service_demand','lake_temperature','grid_capacity','initial_floor_water_mass','internal_hot_leak_mass_flow',
    'drainage_mass_flow','walk_short','walk_long','inspection_time','shift_end_time',
    'network_service_capacity','ups_in_service','filter_resistance_multiplier',
})
POWER_AXES = frozenset({
    'grid_capacity','shared_distribution_available','ups_in_service','ups_transfer_ok',
    'diesel_in_service','diesel_start_ok','diesel_transfer_ok','service_demand',
    'compute_service_capacity','network_service_capacity','storage_service_capacity',
})


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _read(raw):
    return strict_json(raw.decode('utf-8'))


def _declaration():
    raw = DECLARATION.read_bytes()
    doc = _read(raw)
    _require(type(doc) is dict and set(doc) == {'schema','id',*REFERENCES,'references_sha256',
             'maximum_step_s','field_calibration','scope','cases'}, 'Unknown named domain declaration')
    _require(doc['schema'] == 'aegisdc-finite-parameter-domain-v1'
             and doc['maximum_step_s'] == .01 and doc['field_calibration'] == 'PENDING',
             'Use the fixed V6 finite domain and its declared engineering step')
    _require(all(doc[role] == path for role,path in REFERENCES.items())
             and set(doc['references_sha256']) == set(REFERENCES.values()), 'Domain reference roles changed')
    reference = {}
    for role, path in REFERENCES.items():
        content = (ROOT / path).read_bytes()
        _require(sha256(content).hexdigest() == doc['references_sha256'][path], 'Domain reference bytes changed: '+path)
        reference[role] = _read(content)
    cases = {}
    _require(type(doc['cases']) is list and doc['cases'], 'Declare named domain cases')
    for row in doc['cases']:
        _require(type(row) is dict and set(row) == PROFILE_FIELDS and type(row['id']) is str
                 and bool(row['id']) and row['id'] not in cases, 'Unknown or repeated case declaration')
        cases[row['id']] = row
    return doc, reference, cases, sha256(raw).hexdigest()


def _parameters(scenario):
    return {row['id']:row for row in scenario['parameters']}


def _power_service(p, events):
    """Topology ceilings only, before delays, controls or simultaneous allocation."""
    p = dict(p)
    stages = [(0.0,{})]
    for event in events:
        name, time = event['parameter_id'], event['time_s']
        if name not in POWER_AXES:
            continue
        if not same_time(time,stages[-1][0]):
            stages.append((time,{}))
        stages[-1][1][name] = event['value']
    output = []
    for time, values in stages:
        p.update(values)
        shared = p['shared_distribution_available']
        output.append(dict(start_s=time, offered_demand=p['service_demand'],
            grid_path_upper_W=shared * min(p['grid_capacity'],p['switchboard_capacity']),
            diesel_path_upper_W=shared * min(p['diesel_capacity'],p['switchboard_capacity'])
                if p['diesel_in_service'] and p['diesel_start_ok'] and p['diesel_transfer_ok']
                   and p['diesel_initial_fuel_energy'] > 0 and p['generator_initial_start_energy'] > 0 else 0,
            ups_protected_path_upper_W=shared * p['ups_output_capacity']
                if p['ups_in_service'] and p['ups_transfer_ok'] and p['ups_energy'] > 0 else 0,
            service_nameplate_ceiling=min(p[key] for key in (
                'compute_service_capacity','network_service_capacity','storage_service_capacity'))))
    return dict(regimes=output,scope='Separate route ceilings are not additive, not guaranteed available, and do not include independent control battery loads.')


def _public_static(reference, selected, scenario, p):
    nominal = validate_nominal(reference['public_nominal_reference'])
    _require(nominal['facility_id'] == scenario['id'], 'Domain public/physical facility identity differs')
    profile = dict(schema='aegisdc-workforce-profile-v1',id='V6-29-public-work-timing-v1',
        facility_id=scenario['id'],nominal_knowledge_id=nominal['id'],basis='synthetic_assumption',
        source_note='Declared public planning timings from the same scenario; no site measurement.',
        time_unit='s',access_check_s=.25,feedback_latency_s=.5,
        walk_times_s={edge['id']:p[edge['duration_parameter']] for edge in scenario['graphs']['access']},
        work_times_s={interface['id']:p[interface['duration_parameter']]
                      for domain in scenario['domains'] for interface in domain['work_interfaces']},
        shifts={row['id']:[0,p['shift_end_time']] for row in scenario['entities'] if row['kind']=='worker'})
    validate_profile(profile,nominal)
    sensors = deepcopy(reference['fixed_sensor_reference'])
    enabled = selected['enabled_fixed_measurements']
    _require(type(enabled) is list and all(type(value) is str for value in enabled)
             and len(enabled)==len(set(enabled))
             and set(enabled)<={row['id'] for row in sensors['measurements']}, 'Unknown fixed measurement selection')
    _require(sensors['ledger']['records'] == [], 'Do not prefill actual sensor records')
    for row in sensors['measurements']:
        row['enabled'] = row['id'] in enabled
    validate_channel_profile(sensors)
    return dict(nominal_knowledge=nominal,workforce_profile=profile,fixed_sensor_profile=sensors)


def prepare_domain_case(case_id):
    """Build a named initialization candidate; never advance the facility or dispatch."""
    doc, reference, cases, declaration_sha = _declaration()
    _require(type(case_id) is str and case_id in cases, 'Unknown named domain case')
    chosen = cases[case_id]
    scenario = deepcopy(reference['baseline'])
    parameters = _parameters(scenario)
    changes = chosen['initial_overrides']
    _require(type(changes) is dict and set(changes)<=INITIAL_AXES, 'Initial overrides are outside the declared coordinate families')
    for name,value in changes.items():
        parameters[name].update(value=finite_number(value,name),basis='synthetic_assumption',source_refs=['R0'],
            source_note='Declared named synthetic sensitivity coordinate; no site measurement.')
    phase = chosen['phase']
    if phase is not None:
        _require(type(phase) is dict and set(phase)=={'mass_kg','pressure_Pa'}, 'Unknown two-phase coordinates')
        prepared = prepare_refrigerant_initialization(scenario,**phase)
        scenario, phase_state = prepared['scenario'], prepared['initialization']
    else:
        phase_state = assess_refrigerant_initialization(scenario)
    duration = finite_number(chosen['duration_s'],'Domain horizon',positive=True)
    events = validate_boundary_events(scenario,chosen['boundary_events'],duration_s=duration)
    p = {name:row['value'] for name,row in _parameters(scenario).items()}
    _require(type(chosen['axes']) is list and chosen['axes'] and
             all(type(value) is str and bool(value) for value in chosen['axes']), 'Declare the named sensitivity axes')
    _require(scenario['id']==reference['baseline']['id'] and scenario['graphs']==reference['baseline']['graphs']
             and scenario['site_gaps']==reference['baseline']['site_gaps'], 'A named case cannot change topology or site evidence')
    water = assess_water_envelope(scenario,horizon_s=duration,
        events=[row for row in events if row['parameter_id'] in WATER_EVENT_PARAMETERS])
    return dict(schema='aegisdc-prepared-domain-case-v1',domain_id=doc['id'],case_id=case_id,
        status='ADMITTED_INITIALIZATION_NOT_TRAJECTORY_QUALIFIED',field_calibration='PENDING',
        declaration_sha256=declaration_sha,axes=deepcopy(chosen['axes']),scenario=scenario,boundary_events=events,
        duration_s=duration,maximum_step_s=doc['maximum_step_s'],
        initialization=dict(phase=phase_state,water=water,power_and_service=_power_service(p,events)),
        public_static=_public_static(reference,chosen,scenario,p),
        visibility='Scenario, actual exogenous events and initialization are for facility/evaluator. Public static declarations alone are not an arrived evidence frame.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = prepare_domain_case(args.case)
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')


if __name__=='__main__':
    main()
