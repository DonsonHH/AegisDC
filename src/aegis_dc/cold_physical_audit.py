"""Private measurements at existing event epochs; this module never schedules an event."""

def physical_face(plant, point):
    service=point['service']
    p=plant.p
    return dict(params=[p['filter_resistance_multiplier'],p['network_service_capacity']],
        flow=[point['lake_pump']['volume_flow_m3_s'],point['internal_pump']['volume_flow_m3_s']],
        heat=point['hx']['heat_W'],service=[service['demand'],service['delivered'],
            *[service['capacities'][k] for k in ('compute','network','storage')]],
        protection=[plant.control['protection_latched'],plant.control['compute_permitted']],
        stocks=dict(plant.energy,floor_water=plant.floor_energy))
