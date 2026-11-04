"""Independent finite-reserve actor and heat budgets; full-facility seams follow."""
import unittest
from pathlib import Path
from copy import deepcopy
import json
import os
import subprocess
import sys
import tempfile

from aegis_dc.reserve import ups_transition

ROOT = Path(__file__).resolve().parents[1]
RESERVE = ROOT / 'configs/full-facility-mainline-reserve-v6.json'


def changed_reserve(**changes):
    from aegis_dc.scenario import load_scenario
    scenario = load_scenario(RESERVE)
    for row in scenario['parameters']:
        if row['id'] in changes:
            row.update(value=changes[row['id']], basis='synthetic_assumption', source_refs=['Rreserve'],
                       source_note='Ticket 10 declared engineering hand-case override; not site data.')
    return scenario


def boundary(time_s, parameter_id, value):
    return {'time_s': time_s, 'parameter_id': parameter_id, 'value': value,
            'source_note': 'Ticket 10 declared synthetic engineering condition; not a site fault or completed repair.'}


def hand_parameters(**changes):
    values = {'grid_capacity': 0, 'switchboard_capacity': 1000000,
              'rectifier_capacity': 1000000, 'rectifier_efficiency': 1,
              'ups_output_capacity': 100000, 'ups_discharge_efficiency': 0.9,
              'diesel_capacity': 1000000, 'diesel_efficiency': 0.4,
              'controller_power': 100000, 'room_aux_power': 0,
              'compute_demand_power': 0, 'network_demand_power': 0, 'storage_demand_power': 0,
              'compute_service_capacity': 1, 'network_service_capacity': 1,
              'storage_service_capacity': 1, 'service_demand': 1,
              'ups_internal_control_power': 1000, 'generator_internal_control_power': 100,
              'generator_start_power': 2000, 'diesel_idle_fuel_power': 500,
              'backup_fan_nominal_power': 2000, 'shared_distribution_available': 1,
              'ups_in_service': 1, 'ups_transfer_ok': 1, 'diesel_in_service': 1,
              'diesel_start_ok': 1, 'diesel_transfer_ok': 1,
              'backup_cooling_in_service': 1, 'backup_cooling_transfer_ok': 1}
    values.update(changes)
    return values


class ReserveComponentTests(unittest.TestCase):
    def test_dead_main_PLC_cannot_deadlock_the_independently_powered_UPS(self):
        # Its 1 kW internal controller is battery powered while protected output
        # and the main PLC are still dead. 200 J is consumed during .2 s delay.
        waiting = ups_transition(None, time_s=0, needed=True, available=1,
                                 transfer_ok=1, energy_J=3632600,
                                 control_power_W=1000, nominal_control_power_W=1000, delay_s=0.2)
        self.assertEqual(waiting['mode'], 'waiting')
        self.assertEqual(waiting['ready_at_s'], 0.2)
        supplying = ups_transition(waiting, time_s=0.2, needed=True, available=1,
                                   transfer_ok=1, energy_J=3632400,
                                   control_power_W=1000, nominal_control_power_W=1000, delay_s=0.2)
        self.assertEqual(supplying['mode'], 'supplying')
        self.assertEqual(supplying['request_actor'], 'UPS_INTERNAL_CONTROL')

    def test_UPS_internal_control_is_paid_even_before_its_output_connects(self):
        from aegis_dc.power import allocate_reserve_power
        arguments = dict(ups_energy_J=3632600, fuel_energy_J=10000000,
                         starter_energy_J=0, ups_mode='waiting',
                         generator_mode='off', cooling_mode='primary')
        waiting = allocate_reserve_power(hand_parameters(), {'internal_pump': 0, 'intake_pump': 0},
                                         True, **arguments)
        self.assertEqual(waiting['actual_powers_W']['local_controller'], 0)
        self.assertEqual(waiting['actual_powers_W']['ups_control'], 1000)
        self.assertEqual(waiting['ups_protected_output_W'], 0)
        self.assertEqual(waiting['ups_depletion_W'], 1000)
        self.assertEqual(waiting['grid_draw_W'], 0)
        arguments['ups_mode'] = 'supplying'
        supplying = allocate_reserve_power(hand_parameters(), {'internal_pump': 0, 'intake_pump': 0},
                                           True, **arguments)
        self.assertEqual(supplying['ups_protected_output_W'], 100000)
        self.assertAlmostEqual(supplying['ups_depletion_W'], 112111.11111111111)
        # .2 s disconnected +32.4 s supplied =3.6326 MJ, including 32.6 kJ
        # internal control and 360 kJ conversion loss. Main load gets 3.24 MJ.
        self.assertAlmostEqual(0.2 * waiting['ups_depletion_W'] + 32.4 * supplying['ups_depletion_W'],
                               3632600, delta=1e-8)

    def test_generator_requires_finite_local_start_energy_despite_plentiful_fuel(self):
        from aegis_dc.power import allocate_reserve_power
        from aegis_dc.reserve import generator_transition
        p = hand_parameters(controller_power=0, ups_internal_control_power=100)
        def point(mode, energy):
            return allocate_reserve_power(p, {'internal_pump': 0, 'intake_pump': 0}, True,
                                          ups_energy_J=0, fuel_energy_J=10000000,
                                          starter_energy_J=energy, ups_mode='depleted',
                                          generator_mode=mode, cooling_mode='primary')
        def transition(previous, time, energy, power):
            return generator_transition(previous, time_s=time, mains_present=False,
                         available=1, start_ok=1, transfer_ok=1, fuel_energy_J=10000000,
                         starter_energy_J=energy, control_power_W=power,
                         nominal_control_power_W=100, start_delay_s=3, transfer_delay_s=2)
        dead = point('off', 0)
        self.assertEqual(dead['generator_control_power_W'], 0)
        self.assertEqual(transition(None, 0, 0, 0)['mode'], 'starter_depleted')
        off = point('off', 10000)
        starting = transition(None, 0, 10000, off['generator_control_power_W'])
        self.assertEqual(starting['mode'], 'starting')
        crank = point('starting', 10000)
        self.assertEqual(crank['starter_depletion_W'], 2100)
        transferring = transition(starting, 3, 3700, 100)
        self.assertEqual(transferring['mode'], 'transferring')
        self.assertEqual(transferring['ready_at_s'], 5)
        self.assertEqual(point('transferring', 3700)['starter_depletion_W'], 100)
        running = transition(transferring, 5, 3500, 100)
        self.assertEqual(running['mode'], 'supplying')
        connected = point('supplying', 0)
        self.assertEqual(connected['starter_depletion_W'], 0)
        self.assertEqual(connected['generator_output_W'], 200)
        self.assertEqual(connected['fuel_depletion_W'], 1000)
        self.assertEqual(transition(running, 6, 0, 100)['mode'], 'supplying')

    def test_paid_heat_boundary_matches_the_independent_40_kW_port_budget(self):
        from aegis_dc.reserve import paid_backup_exchange
        parameters = {'backup_fan_nominal_power': 2000, 'backup_air_capacity_rate': 8000,
                      'backup_conductance': 3243.720864865315, 'backup_heat_capacity': 1000000}
        state = paid_backup_exchange(parameters, water_capacity_W_K=4000,
                                      water_inlet_K=320, external_inlet_K=300, fan_power_W=2000)
        self.assertAlmostEqual(state['heat_W'], 40000, delta=1e-8)
        self.assertAlmostEqual(state['water_outlet_K'], 310)
        self.assertAlmostEqual(state['air_outlet_K'], 305.25)
        self.assertAlmostEqual(state['outside_heat_W'], 42000, delta=1e-8)
        limited = paid_backup_exchange(dict(parameters, backup_heat_capacity=30000),
                                       water_capacity_W_K=4000, water_inlet_K=320,
                                       external_inlet_K=300, fan_power_W=2000)
        self.assertEqual(limited['heat_W'], 30000)
        self.assertEqual(limited['water_outlet_K'], 312.5)
        self.assertEqual(limited['air_outlet_K'], 304)

    def test_positive_but_insufficient_AC_is_not_fictitious_UPS_control_power(self):
        from aegis_dc.power import allocate_reserve_power
        p = hand_parameters(grid_capacity=500)
        arguments = dict(fuel_energy_J=10000000, starter_energy_J=0,
                         ups_mode='waiting', generator_mode='off', cooling_mode='primary')
        backed = allocate_reserve_power(p, {'internal_pump': 0, 'intake_pump': 0}, True,
                                        ups_energy_J=10000, **arguments)
        self.assertEqual(backed['grid_draw_W'], 500)
        self.assertEqual(backed['ups_control_power_W'], 1000)
        self.assertEqual(backed['ups_depletion_W'], 500)
        empty = allocate_reserve_power(p, {'internal_pump': 0, 'intake_pump': 0}, True,
                                       ups_energy_J=0, **arguments)
        self.assertEqual(empty['ups_control_power_W'], 500)
        self.assertEqual(empty['ups_protected_output_W'], 0)

    def test_common_distribution_failure_removes_usable_reserve_output(self):
        from aegis_dc.power import allocate_reserve_power
        point = allocate_reserve_power(hand_parameters(grid_capacity=1000000,
                     shared_distribution_available=0), {'internal_pump': 10000, 'intake_pump': 5000},
                     True, ups_energy_J=1000000, fuel_energy_J=10000000,
                     starter_energy_J=10000, ups_mode='supplying',
                     generator_mode='supplying', cooling_mode='primary')
        for component in ('local_controller', 'internal_pump', 'intake_pump', 'compute', 'network', 'storage'):
            self.assertEqual(point['actual_powers_W'][component], 0)
        self.assertEqual(point['grid_draw_W'], 0)
        self.assertEqual(point['generator_output_W'], 0)
        self.assertEqual(point['ups_protected_output_W'], 0)
        self.assertEqual(point['ups_depletion_W'], 1000)
        self.assertEqual(point['starter_depletion_W'], 100)

    def test_only_a_paid_sample_can_request_cooling_and_its_fan_is_not_a_UPS_load(self):
        from aegis_dc.reserve import cooling_transition
        from aegis_dc.power import allocate_reserve_power
        def step(previous, time, power, sampled):
            return cooling_transition(previous, time_s=time, sampled=sampled, requested=1,
                       available=1, transfer_ok=1, controller_power_W=power,
                       nominal_controller_power_W=1000, delay_s=2)
        dead = step(None, 0, 0, True)
        self.assertEqual(dead['mode'], 'primary')
        self.assertEqual(step(dead, 0.25, 1000, False)['mode'], 'primary')
        pending = step(dead, 1, 1000, True)
        self.assertEqual(pending['ready_at_s'], 3)
        active = step(pending, 3, 1000, False)
        self.assertEqual(active['mode'], 'active')
        p = hand_parameters(grid_capacity=200000, ups_output_capacity=120000)
        arguments = dict(ups_energy_J=1000000, fuel_energy_J=10000000, starter_energy_J=10000,
                         ups_mode='supplying', generator_mode='off', cooling_mode='active')
        pumps = {'internal_pump': 10000, 'intake_pump': 5000}
        paid = allocate_reserve_power(p, pumps, True, **arguments)
        self.assertEqual(paid['grid_draw_W'], 113100)
        self.assertEqual(paid['actual_powers_W']['backup_fan'], 2000)
        self.assertEqual(paid['actual_powers_W']['intake_pump'], 0)
        self.assertEqual(paid['reserve_external_electric_heat_W'], 2100)
        battery = allocate_reserve_power(dict(p, grid_capacity=0), pumps, True, **arguments)
        self.assertEqual(battery['ups_protected_output_W'], 110000)
        self.assertEqual(battery['actual_powers_W']['backup_fan'], 0)
        self.assertEqual(battery['actual_powers_W']['intake_pump'], 0)

    def test_failed_UPS_transfer_holds_then_restarts_a_fresh_delay(self):
        def step(previous, time, ok):
            return ups_transition(previous, time_s=time, needed=True, available=1,
                                  transfer_ok=ok, energy_J=10000, control_power_W=1000,
                                  nominal_control_power_W=1000, delay_s=0.2)
        pending = step(None, 0, 0)
        failed = step(pending, 0.2, 0)
        self.assertEqual(failed['mode'], 'transfer_failed')
        self.assertEqual(step(failed, 1, 0)['mode'], 'transfer_failed')
        restored = step(failed, 2, 1)
        self.assertEqual(restored['mode'], 'waiting')
        self.assertEqual(restored['ready_at_s'], 2.2)
        self.assertEqual(step(restored, 2.1, 1)['mode'], 'waiting')

    def test_unimplemented_reserve_modes_are_rejected(self):
        from aegis_dc.power import allocate_reserve_power
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            allocate_reserve_power(hand_parameters(), {'internal_pump': 0, 'intake_pump': 0}, True,
                                   ups_energy_J=1000, fuel_energy_J=10000, starter_energy_J=1000,
                                   ups_mode='invented', generator_mode='off', cooling_mode='primary')

    def test_backup_HX_preserves_signed_heat_and_zero_flow_power_boundaries(self):
        from aegis_dc.reserve import paid_backup_exchange
        p = {'backup_fan_nominal_power': 2000, 'backup_air_capacity_rate': 8000,
             'backup_conductance': 3243.720864865315, 'backup_heat_capacity': 1000000}
        reverse = paid_backup_exchange(p, water_capacity_W_K=4000, water_inlet_K=290,
                                        external_inlet_K=300, fan_power_W=2000)
        self.assertAlmostEqual(reverse['heat_W'], -20000, delta=1e-8)
        self.assertAlmostEqual(reverse['outside_heat_W'], -18000, delta=1e-8)
        stopped = paid_backup_exchange(p, water_capacity_W_K=0, water_inlet_K=320,
                                        external_inlet_K=300, fan_power_W=2000)
        self.assertEqual(stopped['heat_W'], 0)
        self.assertEqual(stopped['outside_heat_W'], 2000)
        unpowered = paid_backup_exchange(p, water_capacity_W_K=4000, water_inlet_K=320,
                                          external_inlet_K=300, fan_power_W=0)
        self.assertEqual(unpowered['heat_W'], 0)
        self.assertEqual(unpowered['outside_heat_W'], 0)


class ReserveFacilityTests(unittest.TestCase):
    def test_normal_profile_pays_its_internal_actors_and_preserves_all_eight_domains(self):
        from aegis_dc.scenario import load_scenario
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(RESERVE), duration_s=2)
        first, last = result['trace'][0]['domains'], result['trace'][-1]['domains']
        self.assertEqual(len(first), 8)
        self.assertEqual(first['backup']['starter_energy_J'], 100000)
        self.assertEqual(last['backup']['starter_energy_J'], 100000)
        self.assertEqual(last['backup']['ups_energy_J'], 18000000)
        self.assertEqual(last['backup']['fuel_energy_J'], 500000000)
        self.assertEqual(first['power']['actual_powers_W']['ups_control'], 100)
        self.assertEqual(first['power']['actual_powers_W']['generator_control'], 10)
        self.assertAlmostEqual(result['summary']['grid_energy_J'], 4629559.617083946, delta=1e-6)
        self.assertEqual(result['summary']['reserve_external_electric_heat_J'], 20)
        self.assertEqual(result['summary']['service_deficit_time_s'], 0)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)

    def test_full_facility_UPS_budget_exhausts_at_32_point_6_seconds_without_protecting_IT(self):
        from aegis_dc.plant import simulate_scenario
        scenario = changed_reserve(grid_capacity=0, ups_energy=3632600, ups_discharge_efficiency=0.9,
            ups_internal_control_power=1000, generator_initial_start_energy=0,
            diesel_initial_fuel_energy=0, compute_demand_power=0, network_demand_power=0,
            storage_demand_power=0, room_aux_power=0, room_conductance=0,
            solid_coolant_conductance=0, condenser_conductance=0,
            initial_hot_temperature=300, initial_cold_temperature=300,
            pump_pressure_rise=346500, lake_hydraulic_resistance=31650000,
            internal_pump_pressure_rise=309375, internal_hydraulic_resistance=18151041.666666664)
        result = simulate_scenario(scenario, duration_s=33)
        initial = result['trace'][0]['domains']
        self.assertEqual(initial['power']['actual_powers_W']['local_controller'], 0)
        self.assertEqual(initial['power']['actual_powers_W']['ups_control'], 1000)
        self.assertEqual(initial['backup']['reserve_states']['ups']['ready_at_s'], 0.2)
        connected = next(row['domains'] for row in result['trace'] if row['time_s'] == 0.2)
        self.assertAlmostEqual(connected['power']['ups_protected_output_W'], 100000, delta=1e-8)
        exhausted = next(row for row in result['events'] if row['kind'] == 'ups_depleted')
        self.assertAlmostEqual(exhausted['time_s'], 32.6, delta=1e-8)
        self.assertEqual(result['trace'][-1]['domains']['backup']['ups_energy_J'], 0)
        self.assertAlmostEqual(result['summary']['ups_output_energy_J'], 3272600, delta=1e-6)
        self.assertAlmostEqual(result['summary']['ups_loss_energy_J'], 360000, delta=1e-6)
        self.assertAlmostEqual(result['summary']['reserve_room_control_heat_J'], 32600, delta=1e-6)
        self.assertEqual(result['summary']['demand_service_unit_s'], 33)
        self.assertEqual(result['summary']['delivered_service_unit_s'], 0)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 33)

    def test_full_generator_start_and_transfer_draw_finite_starter_and_fuel_energy(self):
        from aegis_dc.plant import simulate_scenario
        scenario = changed_reserve(grid_capacity=0, diesel_start_time=3, diesel_transfer_delay=2,
            diesel_initial_fuel_energy=42750, generator_initial_start_energy=10000,
            pump_pressure_rise=0, internal_pump_pressure_rise=0, room_aux_power=0,
            compute_demand_power=0, network_demand_power=0, storage_demand_power=0)
        result = simulate_scenario(scenario, duration_s=16)
        at3 = next(row['domains'] for row in result['trace'] if row['time_s'] == 3)
        at5 = next(row['domains'] for row in result['trace'] if row['time_s'] == 5)
        self.assertEqual(at3['backup']['generator_mode'], 'transferring')
        self.assertEqual(at3['power']['generator_output_W'], 0)
        self.assertEqual(at5['backup']['generator_mode'], 'supplying')
        self.assertEqual(at5['power']['generator_output_W'], 1110)
        self.assertAlmostEqual(at5['backup']['starter_energy_J'], 6950, delta=1e-8)
        self.assertEqual(at5['backup']['fuel_energy_J'], 37750)
        depleted = next(row for row in result['events'] if row['kind'] == 'fuel_depleted')
        self.assertAlmostEqual(depleted['time_s'], 15, delta=1e-8)
        self.assertEqual(result['trace'][-1]['domains']['backup']['fuel_energy_J'], 0)
        self.assertAlmostEqual(result['summary']['generator_output_energy_J'], 11100, delta=1e-8)
        self.assertAlmostEqual(result['summary']['generator_waste_energy_J'], 31650, delta=1e-8)

    def test_empty_or_exhausted_start_store_cannot_be_replaced_by_main_fuel_or_main_PLC(self):
        from aegis_dc.plant import simulate_scenario
        for initial, expected_fuel in ((0, 1000000), (202, 999800)):
            with self.subTest(initial_starter_J=initial):
                result = simulate_scenario(changed_reserve(grid_capacity=0, diesel_start_time=3,
                    generator_initial_start_energy=initial, diesel_initial_fuel_energy=1000000), duration_s=2)
                final = result['trace'][-1]['domains']
                self.assertEqual(final['backup']['starter_energy_J'], 0)
                self.assertEqual(final['backup']['generator_mode'], 'starter_depleted')
                self.assertGreater(final['power']['actual_powers_W']['local_controller'], 0)
                self.assertEqual(final['power']['generator_control_power_W'], 0)
                self.assertEqual(result['summary']['generator_output_energy_J'], 0)
                self.assertAlmostEqual(result['summary']['starter_output_energy_J'], initial, delta=1e-8)
                self.assertAlmostEqual(final['backup']['fuel_energy_J'], expected_fuel, delta=1e-8)
                if initial:
                    event = next(row for row in result['events'] if row['kind'] == 'starter_depleted')
                    self.assertAlmostEqual(event['time_s'], 0.2, delta=1e-10)

    def test_common_distribution_outage_defeats_positive_stores_without_unpaid_main_commands(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(changed_reserve(shared_distribution_available=0,
                    diesel_start_time=3, backup_cooling_requested=1), duration_s=6)
        for row in result['trace']:
            domains = row['domains']
            power, states = domains['power'], domains['backup']['reserve_states']
            self.assertEqual(power['grid_draw_W'], 0)
            self.assertEqual(power['generator_output_W'], 0)
            self.assertEqual(power['ups_protected_output_W'], 0)
            self.assertEqual(power['actual_powers_W']['local_controller'], 0)
            self.assertIsNone(states['cooling']['requested_at_s'])
        self.assertEqual(result['summary']['delivered_service_unit_s'], 0)
        self.assertEqual(result['summary']['demand_service_unit_s'], 6)
        self.assertEqual(result['summary']['backup_fan_energy_J'], 0)
        self.assertAlmostEqual(result['summary']['starter_output_energy_J'], 3060, delta=1e-8)
        self.assertAlmostEqual(result['trace'][-1]['domains']['backup']['ups_energy_J'], 17999400)

    def test_maintenance_and_transfer_recovery_restart_real_connection_delays(self):
        from aegis_dc.plant import simulate_scenario
        maintained = simulate_scenario(changed_reserve(grid_capacity=0, diesel_start_time=3,
                    diesel_in_service=0), duration_s=8,
                    boundary_events=[boundary(1, 'diesel_in_service', 1)])
        connected = [row for row in maintained['events'] if row['kind'] == 'reserve_transition'
                     and row['actor'] == 'generator' and row['mode'] == 'supplying']
        self.assertEqual([row['time_s'] for row in connected], [6])
        self.assertEqual(maintained['summary']['demand_service_unit_s'], 8)
        self.assertEqual(maintained['summary']['delivered_service_unit_s'], 2)
        failed = simulate_scenario(changed_reserve(grid_capacity=0, diesel_start_time=3,
                    diesel_transfer_ok=0), duration_s=12,
                    boundary_events=[boundary(6, 'diesel_transfer_ok', 1)])
        states = [row for row in failed['events'] if row['kind'] == 'reserve_transition' and row['actor'] == 'generator']
        self.assertTrue(any(row['mode'] == 'transfer_failed' and row['time_s'] == 5 for row in states))
        self.assertEqual([row['time_s'] for row in states if row['mode'] == 'supplying'], [11])
        self.assertEqual(failed['summary']['demand_service_unit_s'], 12)
        self.assertEqual(failed['summary']['delivered_service_unit_s'], 1)

    def test_main_PLC_waits_for_an_autonomous_paid_generator_before_accepting_cooling(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(changed_reserve(grid_capacity=0, ups_in_service=0,
                    diesel_start_time=3, backup_cooling_requested=1), duration_s=8)
        for row in result['trace']:
            if row['time_s'] < 5:
                self.assertEqual(row['domains']['power']['actual_powers_W']['local_controller'], 0)
                self.assertIsNone(row['domains']['backup']['reserve_states']['cooling']['requested_at_s'])
        at5 = next(row['domains'] for row in result['trace'] if row['time_s'] == 5)
        self.assertEqual(at5['backup']['reserve_states']['cooling']['requested_at_s'], 5)
        self.assertEqual(at5['backup']['reserve_states']['cooling']['ready_at_s'], 7)
        at7 = next(row['domains'] for row in result['trace'] if row['time_s'] == 7)
        self.assertEqual(at7['backup']['backup_tower_mode'], 'active')
        self.assertEqual(at7['power']['actual_powers_W']['backup_fan'], 20000)

    def test_backup_cold_path_has_delay_finite_heat_and_one_paid_outside_sink(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(changed_reserve(backup_cooling_requested=1,
                    backup_heat_capacity=300000), duration_s=4)
        for row in result['trace']:
            domains = row['domains']
            self.assertEqual(domains['facility_cooling']['lake_mass_flow_kg_s'], 0)
            self.assertEqual(domains['facility_cooling']['plate_hx_heat_W'], 0)
            self.assertEqual(domains['facility_cooling']['backup_exchange']['heat_W'],
                             0 if row['time_s'] < 2 else 300000)
        self.assertEqual(result['summary']['backup_water_heat_J'], 600000)
        self.assertEqual(result['summary']['backup_fan_energy_J'], 40000)
        self.assertEqual(result['summary']['reserve_external_electric_heat_J'], 40040)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)

    def test_reserve_profile_retains_dynamic_hot_leak_floor_energy_and_control_latch(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(changed_reserve(backup_cooling_requested=1,
                    backup_heat_capacity=300000, internal_hot_leak_mass_flow=2,
                    drainage_mass_flow=0, local_temperature_bias=40), duration_s=6)
        final = result['trace'][-1]['domains']
        self.assertEqual(final['facility_cooling']['hot_mass_kg'], 9988)
        self.assertEqual(final['space_access']['floor_water_mass_kg'], 12)
        self.assertIn('loc_it', final['space_access']['blocked_location_ids'])
        self.assertAlmostEqual(final['space_access']['floor_water_sensible_energy_J'],
                               result['summary']['internal_hot_leak_energy_J'], delta=1e-5)
        self.assertGreater(final['space_access']['floor_water_temperature_K'], 298.15)
        self.assertTrue(final['control_monitoring']['protection_latched'])
        self.assertEqual(result['summary']['delivered_service_unit_s'], 0)
        self.assertEqual(result['summary']['demand_service_unit_s'], 6)
        self.assertEqual(result['summary']['backup_fan_energy_J'], 80000)
        self.assertEqual(result['summary']['backup_water_heat_J'], 1200000)

    def test_timed_backup_capacity_loss_removes_heat_transfer_while_paid_fan_keeps_running(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(changed_reserve(backup_cooling_requested=1,
                    backup_heat_capacity=300000), duration_s=6,
                    boundary_events=[boundary(3, 'backup_heat_capacity', 0),
                                     boundary(5, 'backup_heat_capacity', 300000)])
        self.assertEqual(result['summary']['backup_fan_energy_J'], 80000)
        self.assertEqual(result['summary']['backup_water_heat_J'], 600000)
        for row in result['trace']:
            if 3 <= row['time_s'] < 5:
                self.assertEqual(row['domains']['backup']['backup_tower_mode'], 'active')
                self.assertEqual(row['domains']['power']['actual_powers_W']['backup_fan'], 20000)
                self.assertEqual(row['domains']['facility_cooling']['backup_exchange']['heat_W'], 0)

    def test_backup_valve_failure_and_maintenance_remove_usable_cooling(self):
        from aegis_dc.plant import simulate_scenario
        failed = simulate_scenario(changed_reserve(backup_cooling_requested=1,
                    backup_heat_capacity=300000), duration_s=7,
                    boundary_events=[boundary(3, 'backup_cooling_transfer_ok', 0),
                                     boundary(4, 'backup_cooling_transfer_ok', 1)])
        self.assertEqual(failed['summary']['backup_water_heat_J'], 600000)
        self.assertEqual(failed['summary']['backup_fan_energy_J'], 40000)
        for row in failed['trace']:
            if 3 <= row['time_s'] < 6:
                self.assertEqual(row['domains']['facility_cooling']['backup_exchange']['heat_W'], 0)
        maintained = simulate_scenario(changed_reserve(backup_cooling_requested=1,
                    backup_heat_capacity=300000, backup_cooling_in_service=0), duration_s=4,
                    boundary_events=[boundary(1, 'backup_cooling_in_service', 1)])
        self.assertEqual(maintained['summary']['backup_fan_energy_J'], 20000)
        self.assertEqual(maintained['summary']['backup_water_heat_J'], 300000)

    def test_reserve_profile_is_closed_typed_bounded_and_requires_funded_actors(self):
        from aegis_dc.scenario import load_scenario, validate_scenario
        base = load_scenario(RESERVE)
        bad = deepcopy(base)
        bad['runtime']['reserve_profile'] = 'not-implemented'
        with self.assertRaisesRegex(ValueError, 'closed contract'):
            validate_scenario(bad)
        for name, field, value in [('ups_in_service', 'value', 0.5),
                                   ('backup_air_capacity_rate', 'quantity', 'thermal_conductance'),
                                   ('generator_start_power', 'unit', 'J')]:
            bad = deepcopy(base)
            next(row for row in bad['parameters'] if row['id'] == name)[field] = value
            with self.subTest(parameter=name), self.assertRaises(ValueError):
                validate_scenario(bad)
        bad = deepcopy(base)
        actor = next(row for row in bad['parameters'] if row['id'] == 'ups_internal_control_power')
        actor.update(value=0, valid_range=[0, 10000])
        with self.assertRaisesRegex(ValueError, 'positive'):
            validate_scenario(bad)
        old = load_scenario(ROOT / 'configs/full-facility-mainline-control-v5.json')
        old['runtime']['reserve_profile'] = base['runtime']['reserve_profile']
        with self.assertRaisesRegex(ValueError, 'closed contract'):
            validate_scenario(old)

    def test_CLI_uses_the_combined_profile_and_waits_for_a_paid_local_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            inputs = folder / 'inputs.json'
            inputs.write_text(json.dumps({'schema': 'aegisdc-engineering-inputs-v1', 'work_requests': [],
                              'boundary_events': [boundary(0.25, 'backup_cooling_requested', 1)]}), encoding='utf-8')
            output = folder / 'fresh-output'
            process = subprocess.run([sys.executable, '-m', 'aegis_dc', 'simulate', '--model', str(RESERVE),
                                      '--duration', '4', '--inputs', str(inputs), '--output', str(output)],
                                     cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
                                     check=True, capture_output=True, text=True, encoding='utf-8')
            saved = json.loads((output / 'run.json').read_text(encoding='utf-8'))
            self.assertEqual(json.loads(process.stdout), saved)
            self.assertEqual(saved['summary']['backup_fan_energy_J'], 20000)
            trace = [json.loads(line) for line in (output / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
            at_quarter = next(row['domains'] for row in trace if row['time_s'] == 0.25)
            self.assertIsNone(at_quarter['backup']['reserve_states']['cooling']['requested_at_s'])
            at1 = next(row['domains'] for row in trace if row['time_s'] == 1)
            self.assertEqual(at1['backup']['reserve_states']['cooling']['ready_at_s'], 3)
            self.assertEqual(saved['research_trials'], 0)
            self.assertEqual(saved['model_calls'], 0)
            self.assertEqual(saved['training_calls'], 0)

    def test_unusable_backup_cold_source_reaches_service_through_true_thermal_protection(self):
        from aegis_dc.plant import simulate_scenario
        # Declared sensitive engineering thresholds, not real equipment limits:
        # initial coolant is 304.4775 K; sustained failed rejection must heat it
        # to 304.6 K before protection can remove compute execution.
        result = simulate_scenario(changed_reserve(pump_pressure_rise=0,
                    backup_cooling_requested=1, backup_heat_capacity=0,
                    protection_temperature=304.6, protection_reset_temperature=304.5), duration_s=20)
        protected = [row['domains'] for row in result['trace']
                     if row['domains']['control_monitoring']['protection_latched']]
        self.assertTrue(protected)
        self.assertGreaterEqual(protected[0]['equipment_environment']['refrigerant']['temperature_K'], 304.6)
        self.assertEqual(protected[0]['power']['actual_powers_W']['compute'], 0)
        self.assertEqual(result['summary']['demand_service_unit_s'], 20)
        self.assertGreater(result['summary']['service_deficit_time_s'], 0)
        self.assertLess(result['summary']['delivered_service_unit_s'], 20)
        self.assertEqual(result['summary']['backup_water_heat_J'], 0)
        self.assertEqual(result['summary']['backup_fan_energy_J'], 360000)


if __name__ == '__main__':
    unittest.main()
