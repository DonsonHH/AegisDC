"""Author the finite M1 engineering runbook; no simulation or effect selection."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'docs/mainline/11-coupled-runbook.json'
NOTE = 'Predeclared ticket 11 synthetic engineering boundary; no site fault, policy, diagnosis or repair.'


def event(time_s, parameter_id, value):
    return dict(time_s=time_s, parameter_id=parameter_id, value=value, source_note=NOTE)


def job(identifier, time_s, worker, interface, target):
    return dict(id=identifier, time_s=time_s, worker_id=worker,
                work_interface_id=interface, target_id=target, source_note=NOTE)


def check(path, expected, *, time=None, op='equal', tolerance=1e-7):
    return dict(path=path, expected=expected, time_s=time, op=op, absolute_tolerance=tolerance)


def fixture(identifier, duration, rationale, *, overrides=None, events=(), jobs=(), checks=(), via_cli=False):
    return dict(id=identifier, duration_s=duration, step_s=1, rationale=rationale,
                overrides=overrides or {}, events=list(events), work_requests=list(jobs),
                checks=list(checks), via_cli=via_cli)


def build():
    cases = [fixture('normal-600s', 600,
        'Ten-minute normal V6 working point; 600 requested and delivered service-unit s, no store draw.',
        checks=[check('summary.demand_service_unit_s', 600), check('summary.delivered_service_unit_s', 600),
                check('summary.service_deficit_time_s', 0), check('summary.grid_energy_J', 1388867885.125184, tolerance=.001),
                check('backup.ups_energy_J', 18000000, time='final'),
                check('backup.starter_energy_J', 100000, time='final'),
                check('backup.fuel_energy_J', 500000000, time='final')])]
    cases += [fixture('shared-AC-capacity', 2,
        '100000 W AC minus 110 W reserve actors, 1000 W PLC, 19200 W circulation, '
        '150000/7 W intake and 5000 W room leaves 53261.42857142857 W rectifier input; '
        '0.97 efficiency and 2.2 MW total IT give service fraction 0.02348344805194805.',
        overrides={'grid_capacity': 100000}, checks=[
            check('power.grid_draw_W', 100000, time=0),
            check('power.rectifier_input_W', 53261.42857142857, time=0),
            check('it_service.delivered', .02348344805194805, time=0),
            check('summary.delivered_service_unit_s', .0469668961038961),
            check('summary.service_deficit_time_s', 1.953033103896104)])]
    cases += [fixture('shared-rectifier-capacity', 1,
        'One 100 kW AC rectifier at unity efficiency supplies all three IT groups; '
        'the independent service fraction is 100/2200 =1/22, despite ample mains.',
        overrides={'rectifier_capacity': 100000, 'rectifier_efficiency': 1}, checks=[
            check('power.rectifier_input_W', 100000, time=0),
            check('it_service.delivered', .045454545454545456, time=0),
            check('summary.delivered_service_unit_s', .045454545454545456)])]
    cases += [fixture('common-distribution', 2,
        'The common enclosure removes normal and protected load rails despite positive UPS/fuel/starter stores. '
        'Power returns at 1.75 s; the already unpowered PLC waits until its 2 s sample, so only the first .25 s is served.',
        events=[event(.25, 'shared_distribution_available', 0), event(1.75, 'shared_distribution_available', 1)],
        checks=[check('power.actual_powers_W.local_controller', 0, time=.25),
                check('power.ups_protected_output_W', 0, time=1),
                check('power.generator_output_W', 0, time=1),
                check('backup.ups_energy_J', 0, time=1, op='greater'),
                check('control_monitoring.mode', 'unpowered_fail_safe', time=1),
                check('control_monitoring.local_measurement.sampled_at_s', 1, time=1.75),
                check('summary.delivered_service_unit_s', .25), check('summary.service_deficit_time_s', 1.75)])]
    cases += [fixture('internal-valve-phase', 1.25,
        'A hardwired shutoff at .25 s stops only circulation immediately. The still-powered compute '
        'and stored solid heat put exactly 1.5 MJ into the closed 2000 kg refrigerant over the next .75 s; '
        'the first low-flow PLC sample at 1 s stops compute. No missing condenser heat is invented.',
        events=[event(.25, 'internal_valve_opening', 0)], checks=[
            check('facility_cooling.internal_mass_flow_kg_s', 0, time=.25),
            check('facility_cooling.condenser_heat_W', 0, time=.25),
            check('facility_cooling.plate_hx_heat_W', 0, time=.25),
            check('power.actual_powers_W.compute', 2000000, time=.25),
            check('equipment_environment.refrigerant.internal_energy_J', 517835850.31469756, time=1, tolerance=.001),
            check('control_monitoring.protection_latched', True, time=1),
            check('summary.delivered_service_unit_s', 1), check('summary.service_deficit_time_s', .25)])]
    cases += [fixture('joint-compute-network-storage', 8,
        'One common service, not three added losses: .25*1 +2*.5 +2*.25 +2*0 +1.75*1 =3.5 service-unit s, '
        'and 8-3.5 =4.5 normalized deficit s. External demand stays one.',
        events=[event(.25, 'compute_service_capacity', .5), event(2.25, 'network_service_capacity', .25),
                event(4.25, 'storage_service_capacity', 0), event(6.25, 'compute_service_capacity', 1),
                event(6.25, 'network_service_capacity', 1), event(6.25, 'storage_service_capacity', 1)],
        checks=[check('it_service.delivered', .5, time=.25), check('it_service.delivered', .25, time=2.25),
                check('it_service.delivered', 0, time=4.25),
                check('power.actual_powers_W.compute', 1000000, time=4.25),
                check('power.actual_powers_W.network', 25000, time=4.25),
                check('summary.demand_service_unit_s', 8), check('summary.delivered_service_unit_s', 3.5),
                check('summary.service_deficit_time_s', 4.5)])]
    cases += [fixture('bias-link-power-latch', 4,
        'Bias changes the local report at the 1 s sample while link loss leaves protection local. '
        'Removing both protected sources at 1.5 s makes the 2 s PLC unpowered. '
        'Power/link restoration does not erase the latch while true temperature exceeds the 300 K reset gate.',
        overrides={'protection_temperature': 310, 'protection_reset_temperature': 300},
        events=[event(.25, 'local_temperature_bias', 10), event(.5, 'supervisory_link_available', 0),
                event(1.25, 'local_temperature_bias', 0), event(1.5, 'grid_capacity', 0),
                event(1.5, 'ups_in_service', 0), event(1.5, 'diesel_in_service', 0),
                event(2.25, 'grid_capacity', 10000000), event(3.25, 'supervisory_link_available', 1)], checks=[
            check('control_monitoring.local_measurement.sampled_at_s', 0, time=.25),
            check('equipment_environment.refrigerant.temperature_K', 304.47751006414603, time=1),
            check('control_monitoring.local_measurement.temperature_K', 314.47751006414603, time=1),
            check('control_monitoring.supervisory_mode', 'autonomous', time=1),
            check('control_monitoring.mode', 'unpowered_fail_safe', time=2),
            check('control_monitoring.protection_latched', True, time=2),
            check('control_monitoring.mode', 'protected', time=3),
            check('control_monitoring.protection_latched', True, time='final'),
            check('control_monitoring.supervisory_mode', 'connected', time='final'),
            check('summary.delivered_service_unit_s', 1), check('summary.service_deficit_time_s', 3)])]
    cases += [fixture('invalid-flow-channel', 3,
        'A -0.2 m3/s bias on the real .12 m3/s report is invalid, rather than clipped. '
        'The change at .25 s takes effect only at sample 1; recovery at 1.25 waits for sample 2.',
        events=[event(.25, 'local_internal_flow_bias', -.2), event(1.25, 'local_internal_flow_bias', 0)], checks=[
            check('control_monitoring.mode', 'sensor_invalid_fail_safe', time=1),
            check('control_monitoring.local_measurement.internal_volume_flow_m3_s', -.08, time=1),
            check('control_monitoring.local_measurement.valid', False, time=1),
            check('control_monitoring.local_measurement.sampled_at_s', 1, time=1.25),
            check('control_monitoring.mode', 'normal', time=2),
            check('summary.delivered_service_unit_s', 2), check('summary.service_deficit_time_s', 1)])]
    cases += [fixture('personnel-resource-conflicts', 151,
        'The initial qualified cooling job walks two 60 s edges and works 30 s. '
        'Its one shared meter is reserved during both travel and work; qualification, worker and route limits reject other jobs.',
        jobs=[job('holds-meter', .25, 'worker_cooling', 'inspect_equipment_environment', 'immersion'),
              job('meter-conflict', .5, 'worker_control', 'inspect_facility_cooling', 'plate_hx'),
              job('qualification-conflict', .75, 'worker_it', 'inspect_power', 'rectifier'),
              job('worker-conflict', 1, 'worker_cooling', 'inspect_facility_cooling', 'filter'),
              job('route-qualification', 1.25, 'worker_control', 'inspect_control_monitoring', 'point_power')],
        checks=[check('summary.worker_travel_person_s', 120), check('summary.worker_work_person_s', 30),
                check('summary.tool_occupation_tool_s', 150), check('work_records.0.arrived_at_s', 120.25),
                check('work_records.0.completed_at_s', 150.25), check('work_records.1.reason', 'tool_busy'),
                check('work_records.2.reason', 'qualification_mismatch'), check('work_records.3.reason', 'worker_busy'),
                check('work_records.4.reason', 'access_unreachable'), check('summary.service_deficit_time_s', 0)])]
    cases += [fixture('gate-before-arrival', 121,
        'A healthy service path cannot authorize access. The gate closes before the 120 s arrival; '
        'the worker/meter stop at loc_control with 120 person s travel, zero actual arrival/work.',
        events=[event(90, 'it_access_permit', 0)],
        jobs=[job('approach-gate', 0, 'worker_cooling', 'inspect_equipment_environment', 'room')], checks=[
            check('work_records.0.status', 'aborted'), check('work_records.0.finished_at_s', 120),
            check('people_tools_work.workers.worker_cooling.location_id', 'loc_control', time='final'),
            check('summary.worker_travel_person_s', 120), check('summary.worker_work_person_s', 0),
            check('summary.delivered_service_unit_s', 121)])]
    cases += [fixture('room-thermal-work-limit', 2,
        'The room receives 100000+1000+100 =101100 W, with a 1 MJ/K air capacity and no outward heat. '
        'A .15165 K headroom lasts exactly 1.5 s. IT worker and tool begin at their normal loc_it identity.',
        overrides={'room_temperature': 300, 'room_thermal_capacity': 1000000,
            'maximum_room_work_temperature': 300.15165, 'room_conductance': 0, 'room_aux_power': 100000,
            'compute_demand_power': 0, 'network_demand_power': 0, 'storage_demand_power': 0,
            'pump_pressure_rise': 0, 'internal_pump_pressure_rise': 0,
            'solid_coolant_conductance': 0, 'condenser_conductance': 0},
        jobs=[job('warm-room', 0, 'worker_it', 'inspect_it_service', 'compute')], checks=[
            check('work_records.0.status', 'aborted'), check('work_records.0.finished_at_s', 1.5),
            check('summary.worker_work_person_s', 1.5),
            check('equipment_environment.room_temperature_K', 300.2022, time='final'),
            check('space_access.floor_water_mass_kg', 0, time='final')])]
    cases += [fixture('finite-generator-hand', 16,
        '3 s cranking at 1010 W and 2 s control at 10 W leave 6950 J starter. '
        'Idle fuel uses 5000 J before transfer; a 1110 W AC load at .4 efficiency plus 1000 W idle '
        'uses the remaining 37750 J in 10 s, exhausting at 15 s.',
        overrides={'grid_capacity': 0, 'diesel_start_time': 3, 'diesel_transfer_delay': 2,
            'diesel_initial_fuel_energy': 42750, 'generator_initial_start_energy': 10000,
            'pump_pressure_rise': 0, 'internal_pump_pressure_rise': 0, 'room_aux_power': 0,
            'compute_demand_power': 0, 'network_demand_power': 0, 'storage_demand_power': 0}, checks=[
            check('backup.generator_mode', 'transferring', time=3),
            check('backup.generator_mode', 'supplying', time=5),
            check('backup.starter_energy_J', 6950, time=5), check('backup.fuel_energy_J', 37750, time=5),
            check('power.generator_output_W', 1110, time=5),
            check('backup.fuel_energy_J', 0, time=15), check('backup.generator_mode', 'fuel_exhausted', time=15)])]
    cases += [fixture('selector-cancels-old-need', 4,
        '25310 W minus 110 W reserve actors, 1000 W PLC and 19200 W internal pump leaves 5000 W fan. '
        'The selector removes primary intake demand at the same time, cancelling stale UPS need.',
        overrides={'grid_capacity': 25310, 'backup_cooling_requested': 1}, checks=[
            check('backup.reserve_states.ups.mode', 'bypass', time=0),
            check('power.ups_transfer_needed', False, time=0),
            check('power.actual_powers_W.backup_fan', 5000, time=2),
            check('facility_cooling.backup_exchange.air_capacity_W_K', 125000, time=2),
            check('summary.backup_fan_energy_J', 10000)])]
    cases += [fixture('selector-creates-new-need', 4,
        'Returning to primary at the paid 3 s PLC sample creates a new UPS need immediately, '
        'with transfer at 3.2 s. Its report remains the single 3 s sample.',
        overrides={'grid_capacity': 25310, 'backup_cooling_requested': 1},
        events=[event(2.25, 'backup_cooling_requested', 0)], checks=[
            check('backup.reserve_states.ups.mode', 'waiting', time=3),
            check('backup.reserve_states.ups.requested_at_s', 3, time=3),
            check('backup.reserve_states.ups.ready_at_s', 3.2, time=3),
            check('backup.reserve_states.ups.mode', 'supplying', time=3.2),
            check('control_monitoring.local_measurement.sampled_at_s', 3, time=3.2),
            check('power.ups_protected_output_W', 16428.571428571428, time=3.2)])]
    events = [event(10.25, name, 1.2) for name in
              ('service_demand', 'compute_service_capacity', 'network_service_capacity', 'storage_service_capacity')]
    events += [event(30.5, 'filter_resistance_multiplier', 4), event(35.25, 'local_temperature_bias', -2),
        event(45.25, 'backup_cooling_requested', 1), event(60.25, 'supervisory_link_available', 0),
        event(65.5, 'grid_capacity', 0), event(105.25, 'grid_capacity', 10000000),
        event(110.25, 'backup_cooling_requested', 0), event(112.5, 'filter_resistance_multiplier', 1),
        event(115.25, 'supervisory_link_available', 1), event(120.5, 'internal_hot_leak_mass_flow', .5),
        event(160.5, 'internal_hot_leak_mass_flow', 0), event(170.25, 'local_temperature_bias', 0),
        event(175.25, 'local_temperature_sensor_valid', 0), event(179.25, 'local_temperature_sensor_valid', 1)]
    events += [event(185.25, name, 1) for name in
               ('service_demand', 'compute_service_capacity', 'network_service_capacity', 'storage_service_capacity')]
    cases += [fixture('combined-episode-CLI', 240,
        'Admissible engineering episode, chosen for interpretable coupling, not policy benefit. '
        'Demand 1.2 during 10.25..185.25 requests 275 service-unit s in total. '
        'Mains loss spans 65.5..105.25; autonomous generator supplies after 30+2 s at 97.5. '
        'The invalid temperature channel stops compute during 176..180. '
        'Leak .5 minus drain .1 reaches 10 kg after 25 s, at145.5, interrupting the qualified room job '
        'after 120 s travel and25.25 s work. Forty seconds of leak removes20 kg hot water; '
        'the floor drains11.95 kg by240, retaining8.05 kg.',
        events=events, jobs=[job('room-engineering-visit', .25, 'worker_cooling', 'inspect_equipment_environment', 'immersion'),
            job('meter-is-held', .5, 'worker_control', 'inspect_facility_cooling', 'plate_hx'),
            job('unqualified-electrical', .75, 'worker_it', 'inspect_power', 'rectifier')], via_cli=True,
        checks=[check('summary.demand_service_unit_s', 275),
            check('backup.reserve_states.cooling.requested_at_s', 46, time=46),
            check('backup.backup_tower_mode', 'active', time=48),
            check('facility_cooling.lake_mass_flow_kg_s', 0, time=48),
            check('backup.reserve_states.ups.mode', 'supplying', time=65.7),
            check('control_monitoring.local_measurement.sampled_at_s', 65, time=65.7),
            check('power.actual_powers_W.compute', 0, time=65.7),
            check('power.actual_powers_W.backup_fan', 0, time=65.7),
            check('backup.generator_mode', 'supplying', time=97.5),
            check('control_monitoring.supervisory_mode', 'autonomous', time=97.5),
            check('work_records.0.status', 'aborted'), check('work_records.0.arrived_at_s', 120.25),
            check('work_records.0.finished_at_s', 145.5), check('summary.worker_travel_person_s', 120),
            check('summary.worker_work_person_s', 25.25), check('summary.tool_occupation_tool_s', 145.25),
            check('summary.internal_hot_leaked_mass_kg', 20), check('summary.floor_water_drained_mass_kg', 11.95),
            check('facility_cooling.hot_mass_kg', 9980, time='final'),
            check('space_access.floor_water_mass_kg', 8.05, time='final'),
            check('control_monitoring.mode', 'sensor_invalid_fail_safe', time=176),
            check('control_monitoring.mode', 'normal', time=180),
            check('summary.service_deficit_time_s', 36), check('summary.delivered_service_unit_s', 231.8)])]
    cases += [fixture('finite-UPS-hand', 33,
        '1000 W battery control during .2 s disconnected, then 100 kW protected PLC at .9 efficiency. '
        '.2*1000 +32.4*(100000/.9+1000) =3632600 J; no IT coverage is created. '
        'The total battery output is3.24 MJ protected plus32600 J control and360000 J conversion loss.',
        overrides={'grid_capacity': 0, 'ups_energy': 3632600, 'ups_discharge_efficiency': .9,
            'ups_internal_control_power': 1000, 'controller_power': 100000,
            'generator_initial_start_energy': 0, 'diesel_initial_fuel_energy': 0,
            'compute_demand_power': 0, 'network_demand_power': 0, 'storage_demand_power': 0,
            'room_aux_power': 0, 'room_conductance': 0, 'solid_coolant_conductance': 0, 'condenser_conductance': 0,
            'initial_hot_temperature': 300, 'initial_cold_temperature': 300,
            'pump_pressure_rise': 346500, 'lake_hydraulic_resistance': 31650000,
            'internal_pump_pressure_rise': 309375, 'internal_hydraulic_resistance': 18151041.666666664}, checks=[
                check('backup.ups_energy_J', 0, time=32.6),
                check('power.ups_protected_output_W', 100000, time=.2),
                check('summary.ups_output_energy_J', 3272600, tolerance=.001),
                check('summary.ups_loss_energy_J', 360000, tolerance=.001),
                check('summary.reserve_room_control_heat_J', 32600, tolerance=.001),
                check('summary.delivered_service_unit_s', 0)])]
    cases += [fixture('empty-starter-with-fuel', 6,
        'With 42750 J fuel but zero starter energy and no mains, the generator cannot start. '
        'The independent UPS does not lend its store to the starter.',
        overrides={'grid_capacity': 0, 'diesel_initial_fuel_energy': 42750, 'generator_initial_start_energy': 0,
            'pump_pressure_rise': 0, 'internal_pump_pressure_rise': 0,
            'compute_demand_power': 0, 'network_demand_power': 0, 'storage_demand_power': 0}, checks=[
                check('backup.generator_mode', 'starter_depleted', time=0),
                check('backup.fuel_energy_J', 42750, time='final'),
                check('power.generator_output_W', 0, time='final')])]
    reference = json.loads((ROOT / 'evidence/mainline/engineering/06-phase/eos-reference-01/direct-eos-reference.json').read_text(encoding='utf-8'))
    endpoint = reference['saturation_endpoint_cases'][10]['MUV']
    rejections = [dict(id='phase-domain-exit', duration_s=.01, step_s=.01,
        overrides={'coolant_inventory': 2000, 'coolant_initial_energy': 2000 * endpoint['internal_energy_J'],
            'coolant_control_volume': 2000 * endpoint['volume_m3'], 'initial_solid_temperature': 370, 'condenser_conductance': 0},
        events=[], error_contains='exactly one domain-valid root',
        rationale='Legal 3 MPa x=.5 EOS endpoint plus stored solid heat exits the table; no extrapolated or clipped success is permitted.'),
        dict(id='hot-inventory-domain-exit', duration_s=1, step_s=1,
            overrides={'internal_hot_mass': 1000, 'minimum_internal_hot_mass': 999, 'internal_hot_leak_mass_flow': 2},
            events=[], error_contains='hydraulic validity minimum', rationale='1000 kg -2 kg/s falls below999 kg after .5 s; unsupported suction geometry must fail.'),
        dict(id='fractional-access-permit', duration_s=1, step_s=1, overrides={},
            events=[event(.25, 'it_access_permit', .5)], error_contains='binary', rationale='Permission is explicitly binary, not an invented partial authorization.')]
    return dict(schema='aegisdc-coupled-engineering-runbook-v1', classification='ENGINEERING_FIXTURES_NOT_RESEARCH_TRIALS',
        profile='configs/full-facility-mainline-reserve-v6.json', shared_facility_id='same accepted V6; parameter overrides retain entities/four graphs',
        scope='Bounded low-order synthetic facility inspired by Zhengzhou; actual fluid/topology/staff data remain unknown.',
        water_reference='Common zero-K sensible cp*T reference for internal water, leak, nuisance inflow, floor pool and drainage; carried energy is not an extra heat source.',
        source_kinds='All event/override numbers are explicit synthetic engineering assumptions, within V6 SI ranges; EOS reference is separately pinned.',
        research_trials=0, training_calls=0, model_calls=0, cases=cases, rejections=rejections)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DESTINATION)
    destination = parser.parse_args().output
    with destination.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(build(), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(destination)
