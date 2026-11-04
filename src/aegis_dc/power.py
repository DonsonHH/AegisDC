"""Explicit low-order electrical allocation and conversion boundary.

Controller, internal pump, intake pump, room auxiliaries and IT are prioritized
in that order. Only the first three have the declared UPS protection path.

Grid capacity is the available AC power at one ideal aggregate MV/LV feed;
switchboard and distribution have unit efficiency in this model. Rectifier,
UPS and generator conversion losses are explicit. No voltage, reactive power,
cable/transformer loss, branch-protection or site-availability model is implied.
"""
from .thermodynamics import finite_number


def allocate_power(parameters, pump_requests_W, compute_permitted, ups_energy_J,
                   generator_running, fuel_energy_J):
    """Allocate one operating point; numeric requests/capacities are finite SI.

    Reserves are available here only while their nonnegative inventory is above
    zero. The caller integrates depletion and splits intervals at exhaustion.
    """
    nonnegative = (
        'grid_capacity', 'switchboard_capacity', 'rectifier_capacity',
        'ups_output_capacity', 'diesel_capacity', 'controller_power', 'room_aux_power',
        'compute_demand_power', 'network_demand_power', 'storage_demand_power',
        'compute_service_capacity', 'network_service_capacity', 'storage_service_capacity',
        'service_demand',
    )
    p = {name: finite_number(parameters[name], 'Electrical ' + name) for name in nonnegative}
    if min(p.values()) < 0:
        raise ValueError('Electrical capacities and requests must be nonnegative')
    for name in ('rectifier_efficiency', 'ups_discharge_efficiency', 'diesel_efficiency'):
        p[name] = finite_number(parameters[name], 'Electrical ' + name, positive=True)
        if p[name] > 1:
            raise ValueError('Electrical conversion efficiency must be in (0,1]')
    ups_energy_J = finite_number(ups_energy_J, 'UPS energy')
    fuel_energy_J = finite_number(fuel_energy_J, 'Fuel energy')
    if min(ups_energy_J, fuel_energy_J) < 0:
        raise ValueError('Electrical reserve inventories must be nonnegative')
    pump_requests_W = {name: finite_number(pump_requests_W[name], name + ' power request')
                       for name in ('internal_pump', 'intake_pump')}
    if min(pump_requests_W.values()) < 0:
        raise ValueError('Electrical pump requests must be nonnegative')
    grid_available = min(p['grid_capacity'], p['switchboard_capacity'])
    generator_available = min(p['diesel_capacity'], p['switchboard_capacity'] - grid_available) \
        if generator_running and fuel_energy_J > 0 else 0.0
    ac_available = grid_available + generator_available
    ups_available = p['ups_output_capacity'] if ups_energy_J > 0 else 0.0
    ac_used = ups_used = 0.0
    actual = {}
    requests = {'local_controller': p['controller_power'],
                'internal_pump': pump_requests_W['internal_pump'],
                'intake_pump': pump_requests_W['intake_pump'], 'room': p['room_aux_power']}
    for name, request in requests.items():
        primary = min(request, ac_available - ac_used)
        protected = min(request - primary, ups_available - ups_used) if name != 'room' else 0.0
        actual[name] = primary + protected
        ac_used += primary
        ups_used += protected
    for name in ('compute', 'network', 'storage'):
        requests[name] = p[name + '_demand_power'] * min(p['service_demand'], p[name + '_service_capacity'])
    if not compute_permitted:
        requests['compute'] = 0.0
    requested_dc = sum(requests[name] for name in ('compute', 'network', 'storage'))
    rectifier_input = min(requested_dc / p['rectifier_efficiency'],
                          p['rectifier_capacity'], ac_available - ac_used)
    delivered_dc = rectifier_input * p['rectifier_efficiency']
    ratio = delivered_dc / requested_dc if requested_dc else 0.0
    actual.update({name: requests[name] * ratio for name in ('compute', 'network', 'storage')})
    ac_used += rectifier_input
    grid = min(ac_used, grid_available)
    generator = ac_used - grid
    return {'actual_powers_W': actual, 'requested_powers_W': requests,
            'grid_draw_W': grid, 'generator_output_W': generator, 'ups_output_W': ups_used,
            'rectifier_input_W': rectifier_input, 'rectifier_loss_W': rectifier_input - delivered_dc,
            'ups_depletion_W': ups_used / p['ups_discharge_efficiency'],
            'ups_loss_W': ups_used * (1 / p['ups_discharge_efficiency'] - 1),
            'fuel_depletion_W': generator / p['diesel_efficiency'],
            'generator_waste_W': generator * (1 / p['diesel_efficiency'] - 1),
            'capacity_slack_W': {
                'grid': p['grid_capacity'] - grid,
                'switchboard': p['switchboard_capacity'] - ac_used,
                'rectifier': p['rectifier_capacity'] - rectifier_input,
                'generator': p['diesel_capacity'] - generator,
                'ups': p['ups_output_capacity'] - ups_used,
            }}


def allocate_reserve_power(parameters, pump_requests_W, compute_permitted, *,
                           ups_energy_J, fuel_energy_J, starter_energy_J,
                           ups_mode, generator_mode, cooling_mode):
    """Explicit reserve actor power, preserving the legacy allocator boundary.

    Internal UPS control is upstream of its protected output converter. AC power
    is actually reserved in the shared budget before a battery fallback is used.
    Its battery output is included in source power, with no extra conversion loss.
    """
    if cooling_mode not in {'primary', 'switching', 'active', 'maintenance', 'transfer_failed'}:
        raise ValueError('Unknown reserve cooling mode')
    if ups_mode not in {'bypass', 'waiting', 'supplying', 'maintenance', 'depleted', 'unpowered', 'transfer_failed'}:
        raise ValueError('Unknown UPS mode')
    if generator_mode not in {'off', 'starting', 'transferring', 'supplying', 'maintenance',
                               'fuel_exhausted', 'starter_depleted', 'unpowered', 'start_failed', 'transfer_failed'}:
        raise ValueError('Unknown generator mode')
    starter = finite_number(starter_energy_J, 'Starter energy')
    if starter < 0:
        raise ValueError('Starter energy must be nonnegative')
    # Validate unchanged electrical inputs through their established boundary.
    allocate_power(parameters, pump_requests_W, compute_permitted, ups_energy_J,
                   False, fuel_energy_J)
    p = dict(parameters)
    for name in ('shared_distribution_available', 'ups_in_service', 'ups_transfer_ok',
                 'diesel_in_service', 'diesel_start_ok', 'diesel_transfer_ok',
                 'backup_cooling_in_service', 'backup_cooling_transfer_ok'):
        value = finite_number(p[name], name)
        if value not in (0, 1):
            raise ValueError(name + ' must be exact numeric 0/1')
    control_request = finite_number(p['ups_internal_control_power'], 'UPS internal control power', positive=True)
    generator_control_request = finite_number(p['generator_internal_control_power'], 'Generator control power', positive=True)
    crank_request = finite_number(p['generator_start_power'], 'Generator starting power', positive=True)
    idle_request = finite_number(p['diesel_idle_fuel_power'], 'Diesel idle fuel power')
    if idle_request < 0:
        raise ValueError('Diesel idle fuel power must be nonnegative')
    grid_available = min(p['grid_capacity'], p['switchboard_capacity']) * p['shared_distribution_available']
    generator_running = (generator_mode == 'supplying' and p['diesel_in_service']
                         and p['diesel_transfer_ok'] and fuel_energy_J > 0)
    generator_available = (min(p['diesel_capacity'], p['switchboard_capacity'] - grid_available)
                           * p['shared_distribution_available'] if generator_running else 0)
    ac_available = grid_available + generator_available
    control_ac = min(control_request, ac_available)
    control_battery = control_request - control_ac if ups_energy_J > 0 else 0.0
    control = control_ac + control_battery
    generator_control_ac = min(generator_control_request, ac_available - control_ac)
    generator_control_battery = generator_control_request - generator_control_ac if starter > 0 else 0.0
    generator_control = generator_control_ac + generator_control_battery
    crank = (crank_request if generator_mode == 'starting' and starter > 0
             and generator_control >= generator_control_request and p['diesel_in_service'] else 0.0)
    prefix_ac = control_ac + generator_control_ac
    prefix_grid, prefix_generator = min(prefix_ac, grid_available), max(0, prefix_ac - grid_available)
    p['grid_capacity'] = grid_available - prefix_grid
    p['diesel_capacity'] = generator_available - prefix_generator
    p['switchboard_capacity'] = p['grid_capacity'] + p['diesel_capacity']
    p['ups_output_capacity'] = (p['ups_output_capacity'] if ups_mode == 'supplying'
                                 and p['ups_in_service'] and p['ups_transfer_ok']
                                 and p['shared_distribution_available'] and control >= control_request else 0)
    route = bool(p['backup_cooling_in_service'] and (cooling_mode == 'switching'
                 or cooling_mode == 'active' and p['backup_cooling_transfer_ok']))
    pump_requests_W = dict(pump_requests_W)
    if route:
        pump_requests_W['intake_pump'] = 0.0
    fan_nominal = finite_number(p['backup_fan_nominal_power'], 'Nominal backup fan power', positive=True)
    fan_request = fan_nominal if route and cooling_mode == 'active' else 0.0
    auxiliary_only = dict(p, room_aux_power=0, compute_demand_power=0,
                          network_demand_power=0, storage_demand_power=0)
    auxiliaries = allocate_power(auxiliary_only, pump_requests_W, compute_permitted,
                                 ups_energy_J, generator_running, fuel_energy_J)
    fan_available = max(0.0, p['grid_capacity'] + p['diesel_capacity']
                        - auxiliaries['grid_draw_W'] - auxiliaries['generator_output_W'])
    fan = min(fan_request, fan_available)
    fan_grid = min(fan, p['grid_capacity'])
    fan_generator = fan - fan_grid
    p['grid_capacity'] -= fan_grid
    p['diesel_capacity'] -= fan_generator
    p['switchboard_capacity'] -= fan
    prefix_grid += fan_grid
    prefix_generator += fan_generator
    probe = dict(p, ups_output_capacity=0)
    primary = allocate_power(probe, pump_requests_W, compute_permitted, 0, generator_running, fuel_energy_J)
    result = allocate_power(p, pump_requests_W, compute_permitted, ups_energy_J, generator_running, fuel_energy_J)
    result['ups_transfer_needed'] = any(primary['actual_powers_W'][name] < primary['requested_powers_W'][name]
                                        for name in ('local_controller', 'internal_pump', 'intake_pump'))
    result['ups_protected_output_W'] = result['ups_output_W']
    result['actual_powers_W']['ups_control'] = control
    result['actual_powers_W']['generator_control'] = generator_control
    result['actual_powers_W']['generator_starter'] = crank
    result['actual_powers_W']['backup_fan'] = fan
    result['requested_powers_W']['ups_control'] = control_request
    result['requested_powers_W']['generator_control'] = generator_control_request
    result['requested_powers_W']['generator_starter'] = crank_request if generator_mode == 'starting' else 0.0
    result['requested_powers_W']['backup_fan'] = fan_request
    result['grid_draw_W'] += prefix_grid
    result['generator_output_W'] += prefix_generator
    result['ups_output_W'] += control_battery
    result['ups_depletion_W'] += control_battery
    result['ups_control_power_W'] = control
    result['ups_control_from_battery_W'] = control_battery
    result['reserve_room_heat_W'] = control
    result['reserve_external_electric_heat_W'] = generator_control + crank + fan
    result['starter_output_W'] = result['starter_depletion_W'] = generator_control_battery + crank
    result['generator_control_power_W'] = generator_control
    idle = (idle_request if generator_mode in {'starting', 'transferring', 'supplying'}
            and p['diesel_in_service'] and fuel_energy_J > 0
            and generator_control >= generator_control_request else 0.0)
    result['fuel_depletion_W'] += prefix_generator / p['diesel_efficiency'] + idle
    result['generator_waste_W'] += prefix_generator * (1 / p['diesel_efficiency'] - 1) + idle
    result['mains_present'] = grid_available > 0
    result['primary_cooling_active'] = not route
    result['reserve_cooling_connected'] = bool(route and cooling_mode == 'active')
    result['capacity_slack_W']['grid'] = parameters['grid_capacity'] - result['grid_draw_W']
    result['capacity_slack_W']['switchboard'] = parameters['switchboard_capacity'] - result['grid_draw_W'] - result['generator_output_W']
    result['capacity_slack_W']['generator'] = parameters['diesel_capacity'] - result['generator_output_W']
    return result
