"""Independent electrical hand cases and complete-facility power responses."""
import unittest
from pathlib import Path

from aegis_dc.plant import simulate_scenario
from aegis_dc.power import allocate_power
from aegis_dc.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / 'configs/full-facility-mainline-v2.json'


def changed_scenario(**changes):
    scenario = load_scenario(SCENARIO)
    for parameter in scenario['parameters']:
        if parameter['id'] in changes:
            parameter['value'] = changes[parameter['id']]
            parameter['source_note'] = 'Ticket 04 synthetic electrical hand-case input; not a site setting.'
    return scenario


def small_it_scenario(**changes):
    values = {
        'compute_demand_power': 80000, 'network_demand_power': 10000,
        'storage_demand_power': 5000, 'compute_nominal_power': 80000,
        'network_nominal_power': 10000, 'storage_nominal_power': 5000,
        'it_thermal_capacity': 2000000, 'solid_coolant_conductance': 0,
        'solid_air_conductance': 0, 'rectifier_efficiency': 0.95,
    }
    values.update(changes)
    return changed_scenario(**values)


def electrical_hand_case(**changes):
    parameters = {
        'grid_capacity': 120000, 'switchboard_capacity': 100000,
        'rectifier_capacity': 100000, 'rectifier_efficiency': 0.95,
        'ups_output_capacity': 30000, 'ups_discharge_efficiency': 0.9,
        'diesel_capacity': 100000, 'diesel_efficiency': 0.4,
        'controller_power': 1000, 'room_aux_power': 5000,
        'compute_demand_power': 80000, 'network_demand_power': 10000,
        'storage_demand_power': 5000, 'service_demand': 1,
        'compute_service_capacity': 1, 'network_service_capacity': 1,
        'storage_service_capacity': 1,
    }
    parameters.update(changes)
    return parameters


class MainlinePowerTests(unittest.TestCase):
    def test_electrical_component_refuses_negative_pump_request(self):
        with self.assertRaisesRegex(ValueError, 'pump.*nonnegative'):
            allocate_power(electrical_hand_case(),
                           {'internal_pump': -1, 'intake_pump': 5000}, True, 0, False, 0)

    def test_electrical_component_refuses_invalid_supply_and_conversion_inputs(self):
        cases = [
            ({'grid_capacity': -1}, 0, 0),
            ({'switchboard_capacity': float('nan')}, 0, 0),
            ({'controller_power': -1}, 0, 0),
            ({'rectifier_efficiency': 0}, 0, 0),
            ({'ups_discharge_efficiency': 1.1}, 0, 0),
            ({'diesel_efficiency': float('inf')}, 0, 0),
            ({}, -1, 0),
            ({}, 0, float('nan')),
        ]
        for changes, ups_energy, fuel_energy in cases:
            with self.subTest(changes=changes, ups_energy=ups_energy, fuel_energy=fuel_energy):
                with self.assertRaises(ValueError):
                    allocate_power(electrical_hand_case(**changes),
                                   {'internal_pump': 10000, 'intake_pump': 5000},
                                   True, ups_energy, False, fuel_energy)

    def test_feeder_and_switchboard_each_enforce_the_100_kW_hand_budget(self):
        # The four auxiliaries need 21 kW; the remaining 79 kW gives
        # 75.05 kW DC and 3.95 kW loss at 95% conversion efficiency.
        for changes, spare_grid, spare_switchboard in [
            ({'grid_capacity': 100000, 'switchboard_capacity': 120000}, 0, 20000),
            ({'grid_capacity': 120000, 'switchboard_capacity': 100000}, 20000, 0),
        ]:
            with self.subTest(changes=changes):
                point = allocate_power(electrical_hand_case(**changes),
                                       {'internal_pump': 10000, 'intake_pump': 5000},
                                       True, 0, False, 0)
                self.assertEqual(point['actual_powers_W'], {
                    'local_controller': 1000, 'internal_pump': 10000, 'intake_pump': 5000,
                    'room': 5000, 'compute': 63200, 'network': 7900, 'storage': 3950,
                })
                self.assertEqual(point['grid_draw_W'], 100000)
                self.assertEqual(point['rectifier_input_W'], 79000)
                self.assertEqual(point['rectifier_loss_W'], 3950)
                self.assertEqual(point['capacity_slack_W']['grid'], spare_grid)
                self.assertEqual(point['capacity_slack_W']['switchboard'], spare_switchboard)

    def test_rectifier_limit_preserves_auxiliaries_and_heats_only_actual_execution(self):
        # 50 kW AC -> 47.5 kW DC: exactly half of the independent
        # 80/10/5 kW IT requests. An insulated 2 MJ/K solid rises 0.04 K in 2 s.
        result = simulate_scenario(small_it_scenario(rectifier_capacity=50000), duration_s=2)
        first, last = result['trace'][0]['domains'], result['trace'][-1]['domains']
        self.assertEqual(first['power']['actual_powers_W']['compute'], 40000)
        self.assertEqual(first['power']['actual_powers_W']['network'], 5000)
        self.assertEqual(first['power']['actual_powers_W']['storage'], 2500)
        self.assertEqual(first['power']['actual_powers_W']['local_controller'], 1000)
        self.assertEqual(first['power']['actual_powers_W']['room'], 5000)
        self.assertEqual(first['power']['rectifier_loss_W'], 2500)
        self.assertAlmostEqual(first['facility_cooling']['lake_pump']['volume_flow_m3_s'], 0.1)
        self.assertAlmostEqual(first['facility_cooling']['internal_pump']['volume_flow_m3_s'], 0.12)
        self.assertEqual(first['it_service']['capacities'], {'compute': 0.5, 'network': 0.5, 'storage': 0.5})
        self.assertEqual(result['summary']['demand_service_unit_s'], 2)
        self.assertEqual(result['summary']['delivered_service_unit_s'], 1)
        self.assertEqual(result['summary']['service_deficit_time_s'], 1)
        self.assertAlmostEqual(last['equipment_environment']['solid_temperature_K']
                               - first['equipment_environment']['solid_temperature_K'], 0.04, delta=1e-10)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)
        self.assertEqual(result['research_trials'], 0)

    def test_full_facility_feeder_or_switchboard_shortfall_is_a_capacity_loss(self):
        # Baseline auxiliaries are 326400/7 W (1000+19200+150000*0.1/0.7+5000).
        # A 676400/7 W source leaves exactly 50 kW for the rectifier.
        for capacity in ('grid_capacity', 'switchboard_capacity'):
            with self.subTest(capacity=capacity):
                result = simulate_scenario(small_it_scenario(**{capacity: 676400 / 7}), duration_s=2)
                first = result['trace'][0]['domains']
                self.assertEqual(len(first), 8)
                self.assertAlmostEqual(first['power']['rectifier_input_W'], 50000, delta=1e-8)
                self.assertAlmostEqual(first['power']['actual_powers_W']['compute'], 40000, delta=1e-8)
                self.assertEqual(first['power']['actual_powers_W']['internal_pump'], 19200)
                self.assertEqual(first['control_monitoring']['mode'], 'normal')
                self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], 1, delta=1e-12)
                self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 1, delta=1e-12)
                self.assertEqual(result['summary']['demand_service_unit_s'], 2)
                self.assertTrue(all(value >= -1e-8 for value in result['summary']['minimum_capacity_slack_W'].values()))

    def test_live_UPS_path_preserves_only_its_capacity_limited_protected_loads(self):
        for source_failure in ({'grid_capacity': 0}, {'switchboard_capacity': 0}):
            with self.subTest(source_failure=source_failure):
                result = simulate_scenario(changed_scenario(ups_output_capacity=20200, **source_failure), duration_s=2)
                point = result['trace'][0]['domains']
                self.assertEqual(point['power']['actual_powers_W'], {
                    'local_controller': 1000, 'internal_pump': 19200, 'intake_pump': 0,
                    'room': 0, 'compute': 0, 'network': 0, 'storage': 0,
                })
                self.assertEqual(point['control_monitoring']['mode'], 'normal')
                self.assertAlmostEqual(point['facility_cooling']['internal_pump']['volume_flow_m3_s'], 0.12)
                self.assertEqual(point['facility_cooling']['lake_pump']['volume_flow_m3_s'], 0)
                self.assertEqual(point['facility_cooling']['plate_hx_heat_W'], 0)
                self.assertEqual(result['summary']['ups_output_energy_J'], 40400)
                self.assertAlmostEqual(result['summary']['ups_loss_energy_J'], 3513.04347826087, delta=1e-8)
                self.assertEqual(result['summary']['service_deficit_time_s'], 2)
                self.assertEqual(result['summary']['demand_service_unit_s'], 2)
                self.assertEqual(result['summary']['grid_energy_J'], 0)

    def test_outage_and_restore_keep_exogenous_demand_and_stored_heat(self):
        result = simulate_scenario(load_scenario(SCENARIO), duration_s=3, boundary_events=[
            {'time_s': 0.25, 'parameter_id': 'grid_capacity', 'value': 0,
             'source_note': 'Ticket 04 synthetic source outage, not a research trial.'},
            {'time_s': 1.25, 'parameter_id': 'grid_capacity', 'value': 10000000,
             'source_note': 'Ticket 04 synthetic source restoration.'},
        ])
        outage = next(row['domains'] for row in result['trace'] if row['time_s'] == 0.25)
        restored = next(row['domains'] for row in result['trace'] if row['time_s'] == 1.25)
        self.assertEqual(outage['power']['actual_powers_W']['compute'], 0)
        self.assertEqual(outage['power']['actual_powers_W']['room'], 0)
        self.assertEqual(outage['power']['actual_powers_W']['internal_pump'], 19200)
        self.assertEqual(outage['power']['rectifier_loss_W'], 0)
        self.assertAlmostEqual(outage['equipment_environment']['solid_coolant_heat_W'], 2000000, delta=1e-7)
        self.assertEqual(restored['power']['actual_powers_W']['compute'], 2000000)
        self.assertEqual(result['summary']['demand_service_unit_s'], 3)
        self.assertEqual(result['summary']['delivered_service_unit_s'], 2)
        self.assertEqual(result['summary']['service_deficit_time_s'], 1)
        self.assertGreater(outage['equipment_environment']['solid_temperature_K'],
                           restored['equipment_environment']['solid_temperature_K'])

    def test_compute_protection_preserves_separately_powered_network_and_storage(self):
        result = simulate_scenario(changed_scenario(protection_temperature=304,
                                  protection_reset_temperature=303), duration_s=2)
        point = result['trace'][0]['domains']
        self.assertEqual(point['control_monitoring']['mode'], 'protected')
        self.assertEqual(point['power']['actual_powers_W']['compute'], 0)
        self.assertEqual(point['power']['actual_powers_W']['network'], 100000)
        self.assertEqual(point['power']['actual_powers_W']['storage'], 100000)
        self.assertEqual(point['power']['actual_powers_W']['room'], 5000)
        self.assertEqual(point['it_service']['capacities'], {'compute': 0, 'network': 1, 'storage': 1})
        self.assertEqual(result['summary']['demand_service_unit_s'], 2)
        self.assertEqual(result['summary']['service_deficit_time_s'], 2)

    def test_generator_and_grid_share_the_same_switchboard_budget(self):
        point = allocate_power(electrical_hand_case(grid_capacity=60000),
                               {'internal_pump': 10000, 'intake_pump': 5000},
                               True, 1000000, True, 1000000)
        self.assertEqual(point['grid_draw_W'], 60000)
        self.assertEqual(point['generator_output_W'], 40000)
        self.assertEqual(point['ups_output_W'], 0)
        self.assertEqual(point['fuel_depletion_W'], 100000)
        self.assertEqual(point['generator_waste_W'], 60000)
        self.assertEqual(point['capacity_slack_W']['switchboard'], 0)
        self.assertEqual(point['actual_powers_W']['compute'], 63200)


if __name__ == '__main__':
    unittest.main()
