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
