"""Explicit low-order electrical allocation and conversion boundary.

Controller, internal pump, intake pump, room auxiliaries and IT are prioritized
in that order. Only the first three have the declared UPS protection path.
"""


def allocate_power(parameters, pump_requests_W, compute_permitted, ups_energy_J,
                   generator_running, fuel_energy_J):
    p = parameters
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
