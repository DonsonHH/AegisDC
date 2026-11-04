"""Independent hydraulic/thermal engineering cases through public boundaries."""
import unittest
from copy import deepcopy
from pathlib import Path

from aegis_dc.scenario import load_scenario


ROOT = Path(__file__).resolve().parents[1]
WATER = ROOT / 'configs/full-facility-mainline-water-v3.json'
LEGACY = ROOT / 'configs/full-facility-mainline-v2.json'


def water_parameters(**values):
    scenario = load_scenario(WATER)
    for row in scenario['parameters']:
        if row['id'] in values:
            row['value'] = values[row['id']]
    return scenario


class ValveLoopTests(unittest.TestCase):
    def test_partial_opening_adds_quadratic_resistance_and_spends_power(self):
        from aegis_dc.heat_transfer import valve_loop_operating_point
        # A 100 kPa ideal pump against 0.6e9 pipe K plus a valve with
        # Kopen=0.1e9: at a=0.5 valve K=0.4e9, hence q=0.01 m3/s,
        # pipe/valve drops 60/40 kPa and 1/2 kW hydraulic/electrical power.
        point = valve_loop_operating_point(100000, 6e8, 1e8, 0.5, 0.5, 1)
        self.assertAlmostEqual(point['volume_flow_m3_s'], 0.01, delta=1e-12)
        self.assertAlmostEqual(point['pressure_rise_Pa'], 100000, delta=1e-7)
        self.assertAlmostEqual(point['passive_pressure_drop_Pa'], 60000, delta=1e-7)
        self.assertAlmostEqual(point['valve_pressure_drop_Pa'], 40000, delta=1e-7)
        self.assertAlmostEqual(point['hydraulic_power_W'], 1000, delta=1e-9)
        self.assertAlmostEqual(point['electric_power_W'], 2000, delta=1e-9)

    def test_closed_valve_interlock_stops_pump_without_free_head_or_heat(self):
        from aegis_dc.heat_transfer import valve_loop_operating_point
        point = valve_loop_operating_point(100000, 6e8, 1e8, 0, 0.5, 1)
        self.assertTrue(point['closed_valve_interlock'])
        self.assertIsNone(point['valve_resistance_Pa_s2_m6'])
        for field in ('volume_flow_m3_s', 'speed', 'pressure_rise_Pa',
                      'valve_pressure_drop_Pa', 'passive_pressure_drop_Pa',
                      'hydraulic_power_W', 'electric_power_W', 'requested_power_W'):
            self.assertEqual(point[field], 0, field)

    def test_power_limit_scales_flow_and_pressure_instead_of_giving_unpaid_head(self):
        from aegis_dc.heat_transfer import valve_loop_operating_point
        # 250 W is 1/8 of the 2 kW unit-speed electrical request. The cubic
        # affinity law gives n=.5, q=.005, dp=25 kPa, drops 15/10 kPa.
        point = valve_loop_operating_point(100000, 6e8, 1e8, 0.5, 0.5, 1,
                                           available_power_W=250)
        self.assertAlmostEqual(point['requested_power_W'], 2000, delta=1e-9)
        self.assertAlmostEqual(point['electric_power_W'], 250, delta=1e-9)
        self.assertAlmostEqual(point['hydraulic_power_W'], 125, delta=1e-9)
        self.assertAlmostEqual(point['volume_flow_m3_s'], 0.005, delta=1e-12)
        self.assertAlmostEqual(point['pressure_rise_Pa'], 25000, delta=1e-7)
        self.assertAlmostEqual(point['passive_pressure_drop_Pa'], 15000, delta=1e-7)
        self.assertAlmostEqual(point['valve_pressure_drop_Pa'], 10000, delta=1e-7)

    def test_open_valve_zero_head_speed_or_power_has_no_flow_or_dynamic_pressure(self):
        from aegis_dc.heat_transfer import valve_loop_operating_point
        for head, speed, available in [(0, 1, None), (100000, 0, None), (100000, 1, 0)]:
            with self.subTest(head=head, speed=speed, available=available):
                point = valve_loop_operating_point(head, 6e8, 1e8, 0.5, 0.5, speed,
                                                   available_power_W=available)
                self.assertFalse(point['closed_valve_interlock'])
                for field in ('volume_flow_m3_s', 'pressure_rise_Pa',
                              'valve_pressure_drop_Pa', 'hydraulic_power_W', 'electric_power_W'):
                    self.assertEqual(point[field], 0)

    def test_invalid_valve_states_are_rejected_instead_of_clipped(self):
        from aegis_dc.heat_transfer import valve_loop_operating_point
        for opening in (-0.1, 1.1, float('inf'), float('nan'), True, 1e-300):
            with self.subTest(opening=opening), self.assertRaises(ValueError):
                valve_loop_operating_point(100000, 6e8, 1e8, opening, 0.5, 1)


class WaterFacilityTests(unittest.TestCase):
    def test_water_model_rejects_heat_split_that_excludes_hydraulic_dissipation(self):
        from aegis_dc.plant import simulate_scenario
        # Full electrical heat fraction f must include hydraulic eta*P in the
        # same fluid. With eta_lake=.7 and eta_internal=.75, f=.5 is impossible.
        with self.assertRaisesRegex(ValueError, 'hydraulic dissipation'):
            simulate_scenario(water_parameters(pump_fluid_heat_fraction=0.5), duration_s=1)

    def test_heat_split_constraint_applies_to_active_legacy_pumps_but_not_disabled_or_unpowered_pumps(self):
        from aegis_dc.plant import simulate_scenario
        for configuration in (LEGACY, WATER):
            with self.subTest(configuration=configuration.name):
                scenario = load_scenario(configuration)
                values = {row['id']: row for row in scenario['parameters']}
                values['pump_fluid_heat_fraction']['value'] = 0.5
                with self.assertRaisesRegex(ValueError, 'hydraulic dissipation'):
                    simulate_scenario(scenario, duration_s=1)
                # Only the lake pump is active: eta=.5, f=.5, while the inactive
                # internal pump's eta=.75 has no hydraulic work to allocate.
                values['pump_efficiency']['value'] = 0.5
                values['internal_pump_pressure_rise']['value'] = 0
                allowed = simulate_scenario(scenario, duration_s=1)
                self.assertEqual(allowed['trace'][0]['domains']['facility_cooling']['internal_pump']['hydraulic_power_W'], 0)
                # With no grid/UPS/fuel, neither positive-head pump can run.
                values['pump_fluid_heat_fraction']['value'] = 0
                values['internal_pump_pressure_rise']['value'] = 120000
                for name in ('grid_capacity', 'ups_energy', 'diesel_initial_fuel_energy'):
                    values[name]['value'] = 0
                dark = simulate_scenario(scenario, duration_s=1)
                self.assertEqual(dark['trace'][0]['domains']['facility_cooling']['lake_pump']['hydraulic_power_W'], 0)

    def test_later_pump_enable_cannot_introduce_an_impossible_fluid_heat_split(self):
        from aegis_dc.plant import simulate_scenario
        scenario = water_parameters(pump_pressure_rise=0, internal_pump_pressure_rise=0,
                                     pump_fluid_heat_fraction=0)
        with self.assertRaisesRegex(ValueError, 'hydraulic dissipation'):
            simulate_scenario(scenario, duration_s=1, boundary_events=[
                {'time_s': 0.25, 'parameter_id': 'pump_pressure_rise', 'value': 150000,
                 'source_note': 'Enable a paid pump; its hydraulic dissipation must enter its fluid.'},
            ])

    def test_declared_water_variant_preserves_normal_working_point_and_valve_identity(self):
        from aegis_dc.plant import simulate_scenario
        scenario = load_scenario(WATER)
        self.assertEqual(len(scenario['domains']), 8)
        domain = next(row for row in scenario['domains'] if row['id'] == 'facility_cooling')
        self.assertTrue({'lake_valve_group', 'internal_valve_group'} <= set(domain['entity_ids']))
        targets = set(domain['work_interfaces'][0]['target_ids'])
        self.assertTrue({'lake_valve_group', 'internal_valve_group'} <= targets)
        result = simulate_scenario(scenario, duration_s=10)
        first = result['trace'][0]['domains']['facility_cooling']
        last = result['trace'][-1]['domains']['facility_cooling']
        self.assertAlmostEqual(first['lake_pump']['volume_flow_m3_s'], 0.1, delta=1e-12)
        self.assertAlmostEqual(first['internal_pump']['volume_flow_m3_s'], 0.12, delta=1e-12)
        self.assertEqual(first['valve_groups']['lake_valve_group']['opening'], 1)
        self.assertEqual(first['valve_groups']['internal_valve_group']['opening'], 1)
        self.assertAlmostEqual(last['cold_temperature_K'], 296.29621459937725, delta=1e-6)
        self.assertEqual(result['summary']['service_deficit_time_s'], 0)

    def test_midstep_closure_stops_only_its_pump_before_the_next_sample_and_then_trips_service(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(WATER), duration_s=2, boundary_events=[
            {'time_s': 0.25, 'parameter_id': 'internal_valve_opening', 'value': 0,
             'source_note': 'Imposed actual shutoff engineering fixture, not a dispatch intervention.'},
        ])
        shut = next(row['domains'] for row in result['trace'] if row['time_s'] == 0.25)
        control, water = shut['control_monitoring'], shut['facility_cooling']
        self.assertEqual(control['local_measurement']['observed_at_s'], 0)
        self.assertEqual(control['pump_speed_command'], 1)
        self.assertFalse(control['hardwired_pump_permits']['internal_pump'])
        self.assertTrue(control['hardwired_pump_permits']['intake_pump'])
        self.assertEqual(water['internal_pump']['electric_power_W'], 0)
        self.assertEqual(water['internal_pump']['pressure_rise_Pa'], 0)
        self.assertEqual(water['internal_pump']['volume_flow_m3_s'], 0)
        self.assertEqual(water['plate_hx_heat_W'], 0)
        self.assertEqual(water['condenser_heat_W'], 0)
        self.assertAlmostEqual(water['lake_pump']['volume_flow_m3_s'], 0.1, delta=1e-12)
        trip = next(row['domains'] for row in result['trace'] if row['time_s'] == 1)
        self.assertEqual(trip['control_monitoring']['mode'], 'protected')
        self.assertEqual(trip['power']['actual_powers_W']['compute'], 0)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 1, delta=1e-12)
        self.assertEqual(result['summary']['demand_service_unit_s'], 2)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)
        self.assertLess(result['summary']['max_mass_residual_kg'], 1e-9)

    def test_hand_case_separates_finite_water_temperatures_and_HX_ports_and_closes_balances(self):
        from aegis_dc.plant import simulate_scenario
        # Both sides: q=.01 m3/s, rho=1000 kg/m3, cp=4000 J/kg/K => C=40 kW/K.
        # With UA=40 kW/K, epsilon=.5. 2 kW/side pump with f=.5 adds 1 kW
        # to its fluid; lake HX inlet=300.025 K. Duty=399.5 kW, both ports
        # 310.0125 K. Lake external output=400.5 kW; no extra dp*q heat.
        scenario = water_parameters(pump_pressure_rise=100000, internal_pump_pressure_rise=100000,
            lake_hydraulic_resistance=6e8, internal_hydraulic_resistance=6e8,
            lake_valve_open_resistance=1e8, internal_valve_open_resistance=1e8,
            lake_valve_opening=0.5, internal_valve_opening=0.5,
            pump_efficiency=0.5, internal_pump_efficiency=0.5, pump_fluid_heat_fraction=0.5,
            water_specific_heat=4000, water_density=1000, lake_temperature=300,
            initial_hot_temperature=320, initial_cold_temperature=310, plate_hx_conductance=40000)
        result = simulate_scenario(scenario, duration_s=1)
        water = result['trace'][0]['domains']['facility_cooling']
        self.assertAlmostEqual(water['lake_hx_inlet_K'], 300.025, delta=1e-10)
        self.assertAlmostEqual(water['plate_hx_heat_W'], 399500, delta=1e-7)
        self.assertAlmostEqual(water['internal_hx_outlet_K'], 310.0125, delta=1e-10)
        self.assertAlmostEqual(water['lake_hx_outlet_K'], 310.0125, delta=1e-10)
        self.assertEqual(water['cold_temperature_K'], 310)
        self.assertAlmostEqual(result['summary']['lake_heat_J'], 400500, delta=1e-7)
        balance = result['balances'][0]
        for medium in ('internal_hot', 'internal_cold', 'lake_throughflow'):
            self.assertAlmostEqual(balance['mass_accounts_kg'][medium]['in_kg'], 10, delta=1e-10)
            self.assertAlmostEqual(balance['mass_accounts_kg'][medium]['out_kg'], 10, delta=1e-10)
        self.assertEqual(balance['mass_accounts_kg']['refrigerant']['in_kg'], 0)
        self.assertEqual(balance['mass_accounts_kg']['floor_water']['in_kg'], 0)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)
        self.assertLess(result['summary']['max_mass_residual_kg'], 1e-9)

    def test_filter_multiplier_changes_its_own_resistance_without_rewriting_valve_curve(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(WATER), duration_s=2, boundary_events=[
            {'time_s': 0.25, 'parameter_id': 'filter_resistance_multiplier', 'value': 4,
             'source_note': 'Independent resistance fixture: passive K=48e6, valve K=3e6.'},
        ])
        changed = next(row['domains']['facility_cooling'] for row in result['trace'] if row['time_s'] == 0.25)
        # Hand solve 150000=(48e6+3e6)*q^2; the valve curve remains K=3e6.
        self.assertAlmostEqual(changed['lake_pump']['volume_flow_m3_s'], 0.05423261445466405, delta=1e-12)
        self.assertEqual(changed['lake_pump']['valve_resistance_Pa_s2_m6'], 3000000)
        self.assertEqual(changed['lake_pump']['passive_resistance_Pa_s2_m6'], 48000000)
        self.assertAlmostEqual(changed['internal_pump']['volume_flow_m3_s'], 0.12, delta=1e-12)
        self.assertGreater(result['trace'][-1]['domains']['facility_cooling']['cold_temperature_K'],
                           result['trace'][0]['domains']['facility_cooling']['cold_temperature_K'])

    def test_quarter_pump_head_halves_flow_and_eighths_electrical_power(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(WATER), duration_s=1, boundary_events=[
            {'time_s': 0.25, 'parameter_id': 'pump_pressure_rise', 'value': 37500,
             'source_note': 'Imposed available differential-head characteristic, not gauge pressure.'},
        ])
        changed = next(row['domains']['facility_cooling'] for row in result['trace'] if row['time_s'] == 0.25)
        self.assertAlmostEqual(changed['lake_pump']['volume_flow_m3_s'], 0.05, delta=1e-12)
        self.assertAlmostEqual(changed['lake_pump']['pressure_rise_Pa'], 37500, delta=1e-7)
        self.assertAlmostEqual(changed['lake_pump']['electric_power_W'], 2678.5714285714284, delta=1e-8)
        self.assertAlmostEqual(changed['internal_pump']['volume_flow_m3_s'], 0.12, delta=1e-12)

    def test_qualified_work_can_identify_and_visit_the_internal_valve_group(self):
        from aegis_dc.plant import simulate_scenario
        request = {'id': 'inspect-internal-valve', 'time_s': 0,
                   'worker_id': 'worker_cooling', 'work_interface_id': 'inspect_facility_cooling',
                   'target_id': 'internal_valve_group',
                   'source_note': 'Engineering visit only; no diagnosis, evidence or repair result.'}
        # Worker, shared flow meter and this valve are all declared at loc_hx;
        # no walking is needed and the configured inspection takes 30 s.
        result = simulate_scenario(load_scenario(WATER), duration_s=31, work_requests=[request])
        record = result['work_records'][0]
        self.assertTrue(record['accepted'])
        self.assertEqual(record['status'], 'completed')
        self.assertEqual(record['arrived_at_s'], 0)
        self.assertEqual(record['completed_at_s'], 30)
        self.assertEqual(result['trace'][-1]['domains']['people_tools_work']['workers']['worker_cooling']['location_id'], 'loc_hx')

    def test_HX_conductance_reduction_changes_heat_and_temperatures_before_any_service_trip(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(WATER), duration_s=2, boundary_events=[
            {'time_s': 0.25, 'parameter_id': 'plate_hx_conductance', 'value': 10000,
             'source_note': 'Imposed UA degradation, not an assigned service penalty.'},
        ])
        first = result['trace'][0]['domains']['facility_cooling']
        changed = next(row['domains']['facility_cooling'] for row in result['trace'] if row['time_s'] == 0.25)
        self.assertLess(changed['plate_hx_heat_W'], first['plate_hx_heat_W'])
        self.assertGreater(result['trace'][-1]['domains']['facility_cooling']['cold_temperature_K'],
                           first['cold_temperature_K'])
        self.assertEqual(result['summary']['service_deficit_time_s'], 0)

    def test_lake_shutoff_reaches_service_through_stored_heat_and_thermal_protection(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(water_parameters(protection_temperature=306,
            protection_reset_temperature=305), duration_s=180, boundary_events=[
                {'time_s': 0.25, 'parameter_id': 'lake_valve_opening', 'value': 0,
                 'source_note': 'Lake shutoff with declared 306/305 K engineering thermal protection.'},
            ])
        changed = next(row['domains'] for row in result['trace'] if row['time_s'] == 0.25)
        self.assertEqual(changed['facility_cooling']['lake_pump']['electric_power_W'], 0)
        self.assertEqual(changed['facility_cooling']['plate_hx_heat_W'], 0)
        self.assertEqual(changed['it_service']['delivered'], 1)
        self.assertAlmostEqual(changed['facility_cooling']['internal_pump']['volume_flow_m3_s'], 0.12, delta=1e-12)
        protected = next(row['domains'] for row in result['trace']
                         if row['domains']['control_monitoring']['mode'] == 'protected')
        self.assertGreaterEqual(protected['control_monitoring']['local_measurement']['temperature_K'], 306)
        self.assertGreater(protected['control_monitoring']['local_measurement']['internal_volume_flow_m3_s'], 0.01)
        self.assertEqual(protected['power']['actual_powers_W']['compute'], 0)
        self.assertGreater(result['summary']['service_deficit_time_s'], 0)
        self.assertLess(result['summary']['service_deficit_time_s'], 180)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)

    def test_reopening_restores_flow_without_bypassing_the_sampled_protection_reset(self):
        from aegis_dc.plant import simulate_scenario
        events = [{'time_s': time, 'parameter_id': 'internal_valve_opening', 'value': value,
                   'source_note': 'Declared shutoff/reopen engineering position sequence.'}
                  for time, value in [(0.25, 0), (1.25, 1)]]
        result = simulate_scenario(load_scenario(WATER), duration_s=3, boundary_events=events)
        opened = next(row['domains'] for row in result['trace'] if row['time_s'] == 1.25)
        self.assertAlmostEqual(opened['facility_cooling']['internal_pump']['volume_flow_m3_s'], 0.12, delta=1e-12)
        self.assertEqual(opened['it_service']['delivered'], 0)
        self.assertTrue(opened['control_monitoring']['protection_latched'])
        reset = next(row['domains'] for row in result['trace'] if row['time_s'] == 2)
        self.assertFalse(reset['control_monitoring']['protection_latched'])
        self.assertEqual(reset['it_service']['delivered'], 1)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 1, delta=1e-12)

    def test_modified_topology_or_invalid_runtime_model_is_not_silently_ignored(self):
        from aegis_dc.scenario import validate_scenario
        scenario = load_scenario(WATER)
        changed = deepcopy(scenario)
        changed['graphs']['control_information'][-1]['source_note'] += ' modified'
        with self.assertRaisesRegex(ValueError, 'Unsupported runtime topology'):
            validate_scenario(changed)
        for model in ([], {}, 'unsupported'):
            changed = deepcopy(scenario)
            changed['runtime']['model'] = model
            with self.subTest(model=model), self.assertRaises(ValueError):
                validate_scenario(changed)


if __name__ == '__main__':
    unittest.main()
