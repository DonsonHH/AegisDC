"""Independent environment, water-transfer and access engineering behavior."""
import unittest
from copy import deepcopy
from pathlib import Path

from aegis_dc.scenario import load_scenario


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = ROOT / 'configs/full-facility-mainline-environment-v4.json'


def environment_parameters(**values):
    scenario = load_scenario(ENVIRONMENT)
    if not set(values) <= {row['id'] for row in scenario['parameters']}:
        raise ValueError('Unknown engineering-fixture parameter')
    for row in scenario['parameters']:
        if row['id'] in values:
            row['value'] = values[row['id']]
    return scenario


class FloorWaterTests(unittest.TestCase):
    def test_mixed_small_drain_matches_an_independent_70_digit_reference(self):
        from aegis_dc.environment import floor_water_step
        # Independent Decimal evaluation of the analytic M/T solution, with no
        # aegis_dc import: evidence/.../decimal-drain-reference.json.
        point = floor_water_step(0.1, 125462.7, 4180, 0.031, 36299.2454, 1e-16, 0.37)
        self.assertAlmostEqual(point['drained_energy_J'], 4.625613472984329e-11, delta=1e-23)

    def test_small_positive_drain_uses_the_known_flux_without_large_inventory_subtraction(self):
        from aegis_dc.environment import floor_water_step
        # 4180*300.15=1,254,627 J/kg. A 1e-14 kg withdrawal carries
        # 1.254627e-8 J, even when that change is below the inventory's ulp.
        point = floor_water_step(1000, 1254627000, 4180, 0, 0, 1e-12, 0.01)
        self.assertAlmostEqual(point['drained_energy_J'], 1.254627e-8, delta=1e-20)

    def test_zero_drain_has_exactly_zero_export_for_a_noninteger_fill_interval(self):
        from aegis_dc.environment import floor_water_step
        # Root's independent valid-input probe exposed cancellation in an
        # identically zero boundary: Eafter rounded up by less than one ulp.
        point = floor_water_step(0.1, 125462.7, 4180, 0.031, 36299.2454, 0, 0.37)
        self.assertEqual(point['drained_mass_kg'], 0)
        self.assertEqual(point['drained_energy_J'], 0)
        self.assertGreater(point['mass_kg'], 0.1)

    def test_variable_mass_mixing_matches_a_rational_hand_case(self):
        from aegis_dc.environment import floor_water_step
        # M0=10 kg at 300 K. In: 2 kg/s at 320 K; out: 1 kg/s; dt=10 s.
        # M1=20 kg, T1=320-20*(10/20)^2=315 K; drain exports 12.4 MJ.
        point = floor_water_step(10, 12000000, 4000, 2, 2560000, 1, 10)
        self.assertEqual(point['mass_kg'], 20)
        self.assertAlmostEqual(point['temperature_K'], 315, delta=1e-10)
        self.assertAlmostEqual(point['energy_J'], 25200000, delta=1e-6)
        self.assertAlmostEqual(point['drained_energy_J'], 12400000, delta=1e-6)

    def test_empty_pool_throughflow_and_exact_empty_boundary_preserve_energy(self):
        from aegis_dc.environment import floor_water_step
        filled = floor_water_step(0, 0, 4000, 2, 2560000, 1, 2)
        self.assertEqual(filled['mass_kg'], 2)
        self.assertAlmostEqual(filled['temperature_K'], 320, delta=1e-10)
        self.assertAlmostEqual(filled['drained_energy_J'], 2560000, delta=1e-6)
        emptied = floor_water_step(10, 12000000, 4000, 1, 1280000, 2, 10)
        self.assertEqual(emptied['mass_kg'], 0)
        self.assertEqual(emptied['energy_J'], 0)
        self.assertIsNone(emptied['temperature_K'])
        self.assertAlmostEqual(emptied['drained_energy_J'], 24800000, delta=1e-6)

    def test_isothermal_withdrawal_preserves_temperature_and_exports_the_removed_energy(self):
        from aegis_dc.environment import floor_water_step
        # 1000 kg at 320 K, cp=4000: E=1.28 GJ. Removing 2 kg/s for 2 s
        # exports 5.12 MJ, leaving 996 kg at exactly the original 320 K.
        point = floor_water_step(1000, 1280000000, 4000, 0, 0, 2, 2)
        self.assertEqual(point['mass_kg'], 996)
        self.assertAlmostEqual(point['energy_J'], 1274880000, delta=1e-6)
        self.assertAlmostEqual(point['temperature_K'], 320, delta=1e-12)
        self.assertAlmostEqual(point['drained_energy_J'], 5120000, delta=1e-6)

    def test_continuous_mixing_matches_independent_constant_mass_tank_solution(self):
        from aegis_dc.environment import floor_water_step
        # 1000 kg, 300 K, cp=4000; 2 kg/s at 320 K in and 2 kg/s out.
        # At t=500 s: T=320-20/e=312.64241117657116 K. The drain exports
        # 1.2 GJ initial +1.28 GJ inlet -1.2505696447062846 GJ remaining.
        point = floor_water_step(1000, 1200000000, 4000, 2, 2560000, 2, 500)
        self.assertEqual(point['mass_kg'], 1000)
        self.assertAlmostEqual(point['temperature_K'], 312.64241117657116, delta=1e-10)
        self.assertAlmostEqual(point['energy_J'], 1250569644.7062845, delta=1e-6)
        self.assertAlmostEqual(point['drained_energy_J'], 1229430355.2937155, delta=1e-6)


class CondensationBoundaryTests(unittest.TestCase):
    def test_invalid_RH_ice_branch_and_nonfinite_inputs_fail_without_clipping(self):
        from aegis_dc.environment import condensation_risk
        for arguments in [(298.15, -0.1, 290), (298.15, 1.1, 290),
                          (298.15, 0.5, 273.15), (334, 0.5, 290),
                          (float('nan'), 0.5, 290)]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                condensation_risk(*arguments)

    def test_boundary_straddles_the_independent_published_dewpoint_example(self):
        from aegis_dc.environment import condensation_risk
        # Official PsychroLib API example: 25 C and RH=.8 gives dewpoint
        # 21.309397163661785 C. This verifies only the boundary, not dew mass.
        # https://psychrometrics.github.io/psychrolib/api_docs.html
        wet = condensation_risk(298.15, 0.8, 294.4493971636618)
        dry = condensation_risk(298.15, 0.8, 294.4693971636618)
        self.assertTrue(wet['condensation_risk'])
        self.assertFalse(dry['condensation_risk'])
        self.assertEqual(wet['classification'], 'BOUNDARY_RISK_ONLY_NO_CONDENSATE_OR_LATENT_HEAT')


class EnvironmentFacilityTests(unittest.TestCase):
    def test_threshold_equality_uses_the_actual_post_protection_heat_direction(self):
        from aegis_dc.plant import simulate_scenario
        # At equality, requested compute would make rectifier heat exceed room
        # rejection. The t=0 low-flow protection removes that compute power;
        # actual controller-only heat is below rejection, so the room is cooling.
        scenario = environment_parameters(room_temperature=300.15, maximum_room_work_temperature=300.15,
            room_thermal_capacity=1000000, room_ambient_temperature=290, room_conductance=5000,
            controller_power=5000, room_aux_power=0, network_demand_power=0, storage_demand_power=0,
            pump_pressure_rise=0, internal_pump_pressure_rise=0,
            solid_coolant_conductance=0, solid_air_conductance=0)
        for entity in scenario['entities']:
            if entity['id'] in {'worker_cooling', 'tool_flow_meter'}:
                entity['location_id'] = 'loc_it'
        result = simulate_scenario(scenario, duration_s=1, work_requests=[{
            'id': 'after-local-protection', 'time_s': 0, 'worker_id': 'worker_cooling',
            'work_interface_id': 'inspect_equipment_environment', 'target_id': 'room',
            'source_note': 'Thermal work permission must use the actual right-hand heat rate after local protection.'}])
        first = result['trace'][0]['domains']
        self.assertEqual(first['control_monitoring']['mode'], 'protected')
        self.assertEqual(first['power']['actual_powers_W']['compute'], 0)
        self.assertFalse(first['space_access']['room_work_access_blocked'])
        self.assertTrue(result['work_records'][0]['accepted'])

    def test_thermal_work_equality_is_directional_and_stationary_equality_is_closed(self):
        from aegis_dc.plant import simulate_scenario
        base = dict(room_temperature=300.15, maximum_room_work_temperature=300.15,
            controller_power=0, network_demand_power=0, compute_demand_power=0,
            storage_demand_power=0, pump_pressure_rise=0, internal_pump_pressure_rise=0,
            solid_coolant_conductance=0, solid_air_conductance=0)
        for cooling, expected_accept in [(False, False), (True, True)]:
            with self.subTest(cooling=cooling):
                scenario = environment_parameters(**base, room_aux_power=0,
                    room_conductance=10000 if cooling else 0, room_ambient_temperature=290)
                for entity in scenario['entities']:
                    if entity['id'] in {'worker_cooling', 'tool_flow_meter'}:
                        entity['location_id'] = 'loc_it'
                result = simulate_scenario(scenario, duration_s=1, work_requests=[{
                    'id': 'equality-work', 'time_s': 0, 'worker_id': 'worker_cooling',
                    'work_interface_id': 'inspect_equipment_environment', 'target_id': 'room',
                    'source_note': 'Explicit right-hand thermal threshold equality case.'}])
                self.assertEqual(result['work_records'][0]['accepted'], expected_accept)

    def test_cooling_crossing_opens_before_a_midstep_request_without_waiting_a_whole_step(self):
        from aegis_dc.plant import simulate_scenario
        scenario = environment_parameters(room_temperature=300.2, maximum_room_work_temperature=300.15,
            room_thermal_capacity=1000000, room_ambient_temperature=290, room_conductance=10000,
            controller_power=0, room_aux_power=0, network_demand_power=0,
            compute_demand_power=0, storage_demand_power=0,
            pump_pressure_rise=0, internal_pump_pressure_rise=0,
            solid_coolant_conductance=0, solid_air_conductance=0)
        for entity in scenario['entities']:
            if entity['id'] in {'worker_cooling', 'tool_flow_meter'}:
                entity['location_id'] = 'loc_it'
        result = simulate_scenario(scenario, duration_s=1, work_requests=[{
            'id': 'after-cooling', 'time_s': 0.5, 'worker_id': 'worker_cooling',
            'work_interface_id': 'inspect_equipment_environment', 'target_id': 'room',
            'source_note': 'Request after the held-rate crossing, before the 1 s numeric step.'}])
        opened = next(event for event in result['events'] if event['kind'] == 'room_work_access_opened')
        # First held heat=-102 kW; .05 K/(.102 K/s)=.49019607843137253 s.
        self.assertAlmostEqual(opened['time_s'], 0.49019607843137253, delta=1e-9)
        self.assertTrue(result['work_records'][0]['accepted'])

    def test_room_sensible_heat_reaches_a_declared_work_limit_without_heating_liquid(self):
        from aegis_dc.plant import simulate_scenario
        scenario = environment_parameters(room_temperature=300, room_thermal_capacity=1000000,
            maximum_room_work_temperature=300.15, room_conductance=0,
            room_aux_power=100000, controller_power=0, network_demand_power=0,
            compute_demand_power=0, storage_demand_power=0,
            pump_pressure_rise=0, internal_pump_pressure_rise=0,
            solid_coolant_conductance=0, solid_air_conductance=0)
        for entity in scenario['entities']:
            if entity['id'] in {'worker_cooling', 'tool_flow_meter'}:
                entity['location_id'] = 'loc_it'
        result = simulate_scenario(scenario, duration_s=2, work_requests=[{
            'id': 'warm-room-work', 'time_s': 0, 'worker_id': 'worker_cooling',
            'work_interface_id': 'inspect_equipment_environment', 'target_id': 'room',
            'source_note': 'Declared research work-temperature cutoff, not an occupational standard.'}])
        # 100 kW /1 MJ/K =.1 K/s; the declared .15 K headroom lasts 1.5 s.
        record = result['work_records'][0]
        self.assertEqual(record['status'], 'aborted')
        self.assertAlmostEqual(record['finished_at_s'], 1.5, delta=1e-9)
        self.assertAlmostEqual(result['summary']['worker_work_person_s'], 1.5, delta=1e-9)
        first, last = result['trace'][0]['domains'], result['trace'][-1]['domains']
        self.assertAlmostEqual(last['equipment_environment']['room_temperature_K'], 300.2, delta=1e-10)
        self.assertEqual(last['facility_cooling']['hot_temperature_K'], first['facility_cooling']['hot_temperature_K'])
        self.assertEqual(last['facility_cooling']['cold_temperature_K'], first['facility_cooling']['cold_temperature_K'])
        self.assertEqual(last['space_access']['floor_water_mass_kg'], 0)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)

    def test_closed_permission_rejects_entry_despite_healthy_physical_connectivity(self):
        from aegis_dc.plant import simulate_scenario
        scenario = environment_parameters(it_access_permit=0)
        result = simulate_scenario(scenario, duration_s=1, work_requests=[{
            'id': 'closed-room', 'time_s': 0, 'worker_id': 'worker_cooling',
            'work_interface_id': 'inspect_equipment_environment', 'target_id': 'room',
            'source_note': 'Qualified/tool-compatible job, rejected solely by independent gate permission.'}])
        self.assertEqual(result['work_records'][0]['reason'], 'access_unreachable')
        self.assertEqual(result['trace'][0]['domains']['it_service']['delivered'], 1)
        self.assertIn('loc_it', result['trace'][0]['domains']['space_access']['blocked_location_ids'])

    def test_closed_destination_is_not_entered_and_travel_is_retained_at_its_gate(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(ENVIRONMENT), duration_s=121,
            work_requests=[{'id': 'approach-room', 'time_s': 0, 'worker_id': 'worker_cooling',
                'work_interface_id': 'inspect_equipment_environment', 'target_id': 'room',
                'source_note': 'Coarse access traversal must check the destination gate before entering.'}],
            boundary_events=[{'time_s': 90, 'parameter_id': 'it_access_permit', 'value': 0,
                'source_note': 'Close permission before the declared 120 s arrival at the IT gate.'}])
        record = result['work_records'][0]
        self.assertEqual(record['status'], 'aborted')
        self.assertEqual(record['finished_at_s'], 120)
        self.assertNotIn('arrived_at_s', record)
        last = result['trace'][-1]['domains']['people_tools_work']
        self.assertEqual(last['workers']['worker_cooling']['location_id'], 'loc_control')
        self.assertEqual(last['tools']['tool_flow_meter']['location_id'], 'loc_control')
        self.assertEqual(result['summary']['worker_travel_person_s'], 120)
        self.assertEqual(result['summary']['worker_work_person_s'], 0)

    def test_actual_hot_leak_crossing_blocks_and_aborts_existing_work(self):
        from aegis_dc.plant import simulate_scenario
        scenario = environment_parameters(internal_hot_leak_mass_flow=2)
        for entity in scenario['entities']:
            if entity['id'] in {'worker_cooling', 'tool_flow_meter'}:
                entity['location_id'] = 'loc_it'
        result = simulate_scenario(scenario, duration_s=10, work_requests=[{
            'id': 'already-in-room', 'time_s': 0, 'worker_id': 'worker_cooling',
            'work_interface_id': 'inspect_equipment_environment', 'target_id': 'room',
            'source_note': 'Declared initial worker/tool positions, ongoing job stopped by floor water.'}])
        # Leak 2 kg/s minus 0.1 kg/s drainage reaches 10 kg at 100/19 s.
        record = result['work_records'][0]
        self.assertEqual(record['status'], 'aborted')
        self.assertAlmostEqual(record['finished_at_s'], 5.2631578947368425, delta=1e-10)
        self.assertAlmostEqual(result['summary']['worker_work_person_s'], 5.2631578947368425, delta=1e-10)
        self.assertAlmostEqual(result['summary']['internal_hot_leaked_mass_kg'], 20, delta=1e-10)
        self.assertEqual(result['summary']['floor_water_inlet_mass_kg'], 0)
        self.assertAlmostEqual(result['trace'][-1]['domains']['space_access']['floor_water_mass_kg'], 19, delta=1e-10)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)
        self.assertLess(result['summary']['max_mass_residual_kg'], 1e-9)

    def test_RH_risk_change_creates_no_condensate_or_latent_energy(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(ENVIRONMENT), duration_s=1, boundary_events=[{
            'time_s': 0.25, 'parameter_id': 'room_humidity', 'value': 1,
            'source_note': 'Prescribed RH boundary change for criterion verification only.'}])
        first, last = result['trace'][0]['domains'], result['trace'][-1]['domains']
        self.assertFalse(first['equipment_environment']['condensation_boundary']['condensation_risk'])
        self.assertTrue(last['equipment_environment']['condensation_boundary']['condensation_risk'])
        self.assertEqual(last['space_access']['floor_water_mass_kg'], 0)
        self.assertEqual(last['space_access']['floor_water_sensible_energy_J'], 0)
        self.assertEqual(result['summary']['internal_hot_leaked_mass_kg'], 0)
        self.assertEqual(result['summary']['service_deficit_time_s'], 0)

    def test_hot_inventory_validity_boundary_is_explicit_and_never_clipped(self):
        from aegis_dc.plant import simulate_scenario
        scenario = environment_parameters(internal_hot_mass=1000, minimum_internal_hot_mass=999,
            internal_hot_leak_mass_flow=2, drainage_mass_flow=0)
        at_limit = simulate_scenario(scenario, duration_s=0.5)
        self.assertEqual(at_limit['trace'][-1]['domains']['facility_cooling']['hot_mass_kg'], 999)
        with self.assertRaisesRegex(ValueError, 'hydraulic validity minimum'):
            simulate_scenario(scenario, duration_s=1)

    def test_unknown_control_profile_and_nonbinary_gate_state_are_rejected(self):
        from aegis_dc.plant import simulate_scenario
        from aegis_dc.scenario import validate_scenario
        scenario = load_scenario(ENVIRONMENT)
        undeclared = deepcopy(scenario)
        undeclared['runtime']['local_control_profile'] = 'unimplemented-fault-profile'
        with self.assertRaisesRegex(ValueError, 'closed contract'):
            validate_scenario(undeclared)
        with self.assertRaisesRegex(ValueError, 'binary'):
            simulate_scenario(environment_parameters(it_access_permit=0.5), duration_s=1)
        with self.assertRaisesRegex(ValueError, 'binary'):
            simulate_scenario(scenario, duration_s=1, boundary_events=[{
                'time_s': 0.25, 'parameter_id': 'it_access_permit', 'value': 0.5,
                'source_note': 'Invalid partial access permission must not be rounded.'}])

    def test_permission_closure_aborts_work_at_its_actual_location_and_keeps_spent_resources(self):
        from aegis_dc.plant import simulate_scenario
        request = {'id': 'room-visit', 'time_s': 0, 'worker_id': 'worker_cooling',
            'work_interface_id': 'inspect_equipment_environment', 'target_id': 'room',
            'source_note': 'Declared cooling engineer visit via the independent personnel graph.'}
        result = simulate_scenario(load_scenario(ENVIRONMENT), duration_s=126,
            work_requests=[request], boundary_events=[
                {'time_s': 125, 'parameter_id': 'it_access_permit', 'value': 0,
                 'source_note': 'Imposed permission closure during an already active room job.'}])
        record = result['work_records'][0]
        self.assertTrue(record['accepted'])
        self.assertEqual(record['arrived_at_s'], 120)
        self.assertEqual(record['status'], 'aborted')
        self.assertEqual(record['finished_at_s'], 125)
        self.assertEqual(record['reason'], 'access_changed')
        self.assertNotIn('completed_at_s', record)
        last = result['trace'][-1]['domains']['people_tools_work']
        self.assertEqual(last['workers']['worker_cooling']['location_id'], 'loc_it')
        self.assertEqual(last['tools']['tool_flow_meter']['location_id'], 'loc_it')
        self.assertIsNone(last['tools']['tool_flow_meter']['reserved_by'])
        self.assertEqual(result['summary']['worker_travel_person_s'], 120)
        self.assertEqual(result['summary']['worker_work_person_s'], 5)

    def test_actual_isothermal_hot_water_leak_moves_mass_and_energy_once_to_the_floor(self):
        from aegis_dc.plant import simulate_scenario
        scenario = environment_parameters(internal_hot_mass=1000, minimum_internal_hot_mass=900,
            internal_hot_leak_mass_flow=2, drainage_mass_flow=0, water_specific_heat=4000,
            initial_hot_temperature=320, initial_cold_temperature=310,
            pump_pressure_rise=0, internal_pump_pressure_rise=0, compute_demand_power=0,
            network_demand_power=0, storage_demand_power=0, controller_power=0, room_aux_power=0,
            solid_coolant_conductance=0, solid_air_conductance=0, room_conductance=0,
            room_temperature=293.15)
        result = simulate_scenario(scenario, duration_s=2)
        last = result['trace'][-1]['domains']
        self.assertEqual(last['facility_cooling']['hot_mass_kg'], 996)
        self.assertAlmostEqual(last['facility_cooling']['hot_temperature_K'], 320, delta=1e-10)
        self.assertEqual(last['space_access']['floor_water_mass_kg'], 4)
        self.assertAlmostEqual(last['space_access']['floor_water_temperature_K'], 320, delta=1e-10)
        self.assertAlmostEqual(last['space_access']['floor_water_sensible_energy_J'], 5120000, delta=1e-6)
        self.assertEqual(result['summary']['internal_hot_leaked_mass_kg'], 4)
        self.assertEqual(result['summary']['floor_water_inlet_mass_kg'], 0)
        self.assertEqual(result['summary']['grid_energy_J'], 0)
        self.assertAlmostEqual(result['summary']['final_stored_energy_J'], result['summary']['initial_stored_energy_J'], delta=1e-5)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)
        self.assertLess(result['summary']['max_mass_residual_kg'], 1e-9)

    def test_new_environment_profile_keeps_the_same_eight_domain_normal_working_point(self):
        from aegis_dc.plant import simulate_scenario
        scenario = load_scenario(ENVIRONMENT)
        result = simulate_scenario(scenario, duration_s=10)
        first, last = result['trace'][0]['domains'], result['trace'][-1]['domains']
        self.assertEqual(len(last), 8)
        self.assertEqual(last['facility_cooling']['hot_mass_kg'], 10000)
        self.assertEqual(last['space_access']['floor_water_mass_kg'], 0)
        self.assertIsNone(last['space_access']['floor_water_temperature_K'])
        self.assertFalse(last['equipment_environment']['condensation_boundary']['condensation_risk'])
        self.assertEqual(last['equipment_environment']['room_temperature_K'], first['equipment_environment']['room_temperature_K'])
        self.assertEqual(last['facility_cooling']['hot_temperature_K'], first['facility_cooling']['hot_temperature_K'])
        self.assertEqual(result['summary']['service_deficit_time_s'], 0)


if __name__ == '__main__':
    unittest.main()
