"""The explicit supported low-order facility, not a generic graph simulator."""
from patrol_rsi.contracts import digest

MODEL = 'aegisdc-low-order-facility-v1'
TOPOLOGY_SHA256 = 'f6a5fed4e33ef6ef26dfb35f6daf5c9070e2125587ce7e3b84fc9c2383709254'
WATER_MODEL = 'aegisdc-low-order-facility-water-v2'
ENVIRONMENT_MODEL = 'aegisdc-low-order-facility-environment-v3'
WATER_MODELS = {WATER_MODEL, ENVIRONMENT_MODEL}
SUPPORTED_TOPOLOGIES = {
    MODEL: TOPOLOGY_SHA256,
    WATER_MODEL: '40852da7230c6db601d8ab7d5a360b45e61356df929826fe62a90016305aeea2',
    ENVIRONMENT_MODEL: '16a1b495731abf52140c921e2dfd185e19cde6493b9f57e504965c9b82c755e4',
}
ENVIRONMENT_QUANTITIES = {'internal_hot_leak_mass_flow': 'mass_flow',
                          'minimum_internal_hot_mass': 'mass', 'it_access_permit': 'fraction',
                          'maximum_room_work_temperature': 'temperature'}
WATER_QUANTITIES = {
    'lake_valve_open_resistance': 'hydraulic_resistance',
    'internal_valve_open_resistance': 'hydraulic_resistance',
    'lake_valve_opening': 'fraction', 'internal_valve_opening': 'fraction',
}

# Physical inputs are SI/provenance/range records in the scenario, never hidden
# numerical defaults in the simulator. The names are part of this model version.
RUNTIME_QUANTITIES = {
    'grid_capacity': 'power', 'switchboard_capacity': 'power',
    'rectifier_capacity': 'power', 'rectifier_efficiency': 'efficiency',
    'ups_energy': 'energy', 'ups_discharge_efficiency': 'efficiency',
    'ups_output_capacity': 'power', 'diesel_capacity': 'power',
    'diesel_start_time': 'time', 'diesel_initial_fuel_energy': 'energy',
    'diesel_efficiency': 'efficiency', 'controller_power': 'power',
    'room_aux_power': 'power', 'lake_temperature': 'temperature',
    'lake_volume_flow': 'volume_flow', 'internal_volume_flow': 'volume_flow',
    'pump_pressure_rise': 'pressure', 'pump_efficiency': 'efficiency',
    'internal_pump_pressure_rise': 'pressure', 'internal_pump_efficiency': 'efficiency',
    'lake_hydraulic_resistance': 'hydraulic_resistance',
    'internal_hydraulic_resistance': 'hydraulic_resistance',
    'filter_resistance_multiplier': 'fraction', 'pump_fluid_heat_fraction': 'fraction',
    'pump_min_speed': 'fraction', 'plate_hx_conductance': 'thermal_conductance',
    'condenser_conductance': 'thermal_conductance',
    'internal_hot_mass': 'mass', 'internal_cold_mass': 'mass',
    'water_specific_heat': 'specific_heat', 'water_density': 'density',
    'coolant_inventory': 'mass', 'coolant_control_volume': 'volume',
    'coolant_initial_energy': 'energy', 'it_thermal_capacity': 'thermal_capacity',
    'room_thermal_capacity': 'thermal_capacity', 'room_temperature': 'temperature',
    'room_humidity': 'relative_humidity', 'initial_hot_temperature': 'temperature',
    'initial_cold_temperature': 'temperature', 'initial_solid_temperature': 'temperature',
    'solid_coolant_conductance': 'thermal_conductance', 'solid_air_conductance': 'thermal_conductance',
    'room_ambient_temperature': 'temperature', 'room_conductance': 'thermal_conductance',
    'compute_demand_power': 'power', 'network_demand_power': 'power',
    'storage_demand_power': 'power', 'compute_nominal_power': 'power',
    'network_nominal_power': 'power', 'storage_nominal_power': 'power',
    'compute_service_capacity': 'service_capacity', 'network_service_capacity': 'service_capacity',
    'storage_service_capacity': 'service_capacity', 'service_demand': 'service_capacity',
    'cooling_setpoint': 'temperature', 'control_hysteresis': 'temperature_difference',
    'protection_temperature': 'temperature', 'protection_reset_temperature': 'temperature',
    'control_sample_time': 'time', 'minimum_internal_volume_flow': 'volume_flow',
    'initial_floor_water_mass': 'inventory_mass', 'floor_water_inflow': 'mass_flow',
    'drainage_mass_flow': 'mass_flow', 'access_block_mass': 'mass',
    'step_time': 'time', 'duration': 'time', 'shift_end_time': 'time',
    'energy_absolute_tolerance': 'energy', 'mass_absolute_tolerance': 'mass',
    'balance_relative_tolerance': 'fraction', 'maximum_temperature_step': 'temperature_difference',
    'walk_short': 'time', 'walk_long': 'time', 'inspection_time': 'time',
}


def validate_runtime_contract(scenario, entities, parameters):
    runtime = scenario['runtime']
    expected = {'model', 'property_table', 'property_sha256', 'topology_sha256', 'closed_location_ids'}
    if not isinstance(runtime, dict) or set(runtime) != expected \
            or not isinstance(runtime['model'], str) or runtime['model'] not in SUPPORTED_TOPOLOGIES:
        raise ValueError('Declare the supported runtime model and its closed contract')
    if runtime['property_table'] != 'configs/materials/reference-r134a-saturation.json':
        raise ValueError('Runtime uses only the declared frozen saturation reference')
    identity = runtime['property_sha256']
    if not isinstance(identity, str) or len(identity) != 64 or any(c not in '0123456789abcdef' for c in identity):
        raise ValueError('Declare property SHA-256 identity')
    topology = SUPPORTED_TOPOLOGIES[runtime['model']]
    if runtime['topology_sha256'] != topology or digest(scenario['graphs']) != topology:
        raise ValueError('Unsupported runtime topology; revise the model explicitly rather than ignoring graph changes')
    required = dict(RUNTIME_QUANTITIES)
    if runtime['model'] in WATER_MODELS:
        required.update(WATER_QUANTITIES)
    if runtime['model'] == ENVIRONMENT_MODEL:
        required.update(ENVIRONMENT_QUANTITIES)
    for name, quantity in required.items():
        if name not in parameters or parameters[name]['quantity'] != quantity:
            raise ValueError('Runtime requires SI parameter ' + name + ' of quantity ' + quantity)
    values = {name: record['value'] for name, record in parameters.items()}
    for name in ('pump_min_speed', 'pump_fluid_heat_fraction'):
        if not 0 <= values[name] <= 1:
            raise ValueError(name + ' must stay in [0,1]')
    if runtime['model'] in WATER_MODELS:
        for name in ('lake_valve_opening', 'internal_valve_opening'):
            if not 0 <= values[name] <= 1 or parameters[name]['valid_range'][1] > 1:
                raise ValueError(name + ' and its declared range must stay in [0,1]')
        for name in ('lake_valve_open_resistance', 'internal_valve_open_resistance'):
            if values[name] <= 0:
                raise ValueError(name + ' must be positive in the runtime model')
    if runtime['model'] == ENVIRONMENT_MODEL:
        if not 273.16 <= values['maximum_room_work_temperature'] <= 333.15:
            raise ValueError('Room work-temperature threshold must stay inside the declared environment domain')
        if values['it_access_permit'] not in (0, 1):
            raise ValueError('IT access permission must be the declared binary 0/1 state')
        if not 0 < values['minimum_internal_hot_mass'] <= values['internal_hot_mass']:
            raise ValueError('Minimum hot-water inventory must be positive and no greater than initial inventory')
    for name in ('compute_nominal_power', 'network_nominal_power', 'storage_nominal_power',
                 'lake_hydraulic_resistance', 'internal_hydraulic_resistance', 'access_block_mass'):
        if values[name] <= 0:
            raise ValueError(name + ' must be positive in the runtime model')
    if values['protection_reset_temperature'] >= values['protection_temperature']:
        raise ValueError('Protection reset temperature must be below the trip temperature')
    closed = runtime['closed_location_ids']
    if not isinstance(closed, list) or any(not isinstance(item, str) for item in closed) \
            or len(closed) != len(set(closed)) \
            or any(item not in entities or entities[item]['kind'] != 'location' for item in closed):
        raise ValueError('Closed access IDs must be distinct declared locations')
