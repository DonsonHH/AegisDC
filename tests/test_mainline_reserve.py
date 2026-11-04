"""Independent finite-reserve actor and heat budgets; full-facility seams follow."""
import unittest

from aegis_dc.reserve import ups_transition


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


if __name__ == '__main__':
    unittest.main()
