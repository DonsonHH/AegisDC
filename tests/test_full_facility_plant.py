"""Engineering checks at the property, scenario/run and CLI boundaries."""
import unittest
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from aegis_dc.scenario import load_scenario
from aegis_dc.thermodynamics import SaturationTable

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'configs/materials/reference-r134a-saturation.json'
SCENARIO = ROOT / 'configs/full-facility-mainline-v2.json'


def changed_parameters(**values):
    scenario = load_scenario(SCENARIO)
    for record in scenario['parameters']:
        if record['id'] in values:
            record['value'] = values[record['id']]
    return scenario


def work_request(identifier, time_s, worker_id, interface_id, target_id):
    return {'id': identifier, 'time_s': time_s, 'worker_id': worker_id,
            'work_interface_id': interface_id, 'target_id': target_id,
            'source_note': 'Predeclared engineering work; no diagnosis or repair effect.'}


class HealthyFacilityTests(unittest.TestCase):
    def test_runtime_scenario_keeps_all_eight_domains_with_declared_SI_inputs(self):
        scenario = load_scenario(SCENARIO)
        self.assertEqual(len(scenario['domains']), 8)
        self.assertEqual(scenario['runtime']['model'], 'aegisdc-low-order-facility-v1')
        self.assertIn('internal_pump', {entity['id'] for entity in scenario['entities']})
        self.assertTrue(all(parameter['source_note'] and parameter['valid_range']
                            for parameter in scenario['parameters']))

    def test_pump_has_paid_power_and_fourfold_resistance_halves_flow(self):
        from aegis_dc.heat_transfer import pump_operating_point
        nominal = pump_operating_point(100000, 1e9, 0.5, 1.0)
        restricted = pump_operating_point(100000, 4e9, 0.5, 1.0)
        self.assertAlmostEqual(nominal['volume_flow_m3_s'], 0.01, delta=1e-12)
        self.assertAlmostEqual(nominal['hydraulic_power_W'], 1000, delta=1e-9)
        self.assertAlmostEqual(nominal['electric_power_W'], 2000, delta=1e-9)
        self.assertAlmostEqual(restricted['volume_flow_m3_s'], 0.005, delta=1e-12)

    def test_heat_exchanger_matches_independent_forty_kW_hand_case(self):
        from aegis_dc.heat_transfer import counterflow_exchange
        result = counterflow_exchange(3243.720864865315, 4000, 8000, 320, 300)
        self.assertAlmostEqual(result['heat_W'], 40000, delta=1e-8)
        self.assertAlmostEqual(result['hot_outlet_K'], 310, delta=1e-10)
        self.assertAlmostEqual(result['cold_outlet_K'], 305, delta=1e-10)
        self.assertAlmostEqual(result['effectiveness'], 0.5, delta=1e-12)

    def test_same_full_facility_runs_at_a_closed_normal_operating_point(self):
        from aegis_dc.plant import simulate_scenario
        scenario = load_scenario(SCENARIO)
        result = simulate_scenario(scenario, duration_s=10)
        self.assertEqual(result['status'], 'ENGINEERING_FIXTURE_COMPLETED')
        self.assertEqual(result['state_visibility'], 'PRIVATE_PLANT_EVALUATOR_ONLY')
        self.assertEqual(set(result['trace'][-1]['domains']),
                         {domain['id'] for domain in scenario['domains']})
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 0, delta=1e-12)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], 10, delta=1e-12)
        initial = result['trace'][0]['domains']
        final = result['trace'][-1]['domains']
        for key in ('hot_temperature_K', 'cold_temperature_K'):
            self.assertAlmostEqual(initial['facility_cooling'][key],
                                   final['facility_cooling'][key], delta=1e-6)
        self.assertAlmostEqual(final['equipment_environment']['solid_temperature_K'],
                               308.47751006414603, delta=1e-6)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)
        self.assertLess(result['summary']['max_mass_residual_kg'], 1e-9)
        self.assertEqual(result['work_records'], [])
        self.assertEqual(result['research_trials'], 0)

    def test_midstep_loss_of_grid_preserves_demand_and_stored_heat(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(SCENARIO), duration_s=2, boundary_events=[
            {'time_s': 0.25, 'parameter_id': 'grid_capacity', 'value': 0,
             'source_note': 'Engineering power-loss fixture, no real device action.'},
        ])
        self.assertAlmostEqual(result['summary']['demand_service_unit_s'], 2, delta=1e-12)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 1.75, delta=1e-12)
        after = next(row['domains'] for row in result['trace'] if row['time_s'] == 0.25)
        self.assertEqual(after['power']['actual_powers_W']['compute'], 0)
        self.assertGreater(after['equipment_environment']['solid_coolant_heat_W'], 1000000)
        self.assertGreater(after['backup']['ups_energy_J'], 0)
        self.assertLess(result['summary']['max_energy_residual_J'], 0.01)

    def test_UPS_matches_32_point_4_second_exhaustion_without_negative_energy(self):
        from aegis_dc.plant import simulate_scenario
        scenario = changed_parameters(
            grid_capacity=0, ups_energy=3600000, ups_discharge_efficiency=0.9,
            controller_power=100000, pump_pressure_rise=0, internal_pump_pressure_rise=0,
            room_aux_power=0, compute_demand_power=0, network_demand_power=0,
            storage_demand_power=0, diesel_start_time=100,
        )
        result = simulate_scenario(scenario, duration_s=40)
        self.assertAlmostEqual(result['summary']['ups_output_energy_J'], 3240000, delta=1e-6)
        self.assertAlmostEqual(result['summary']['ups_loss_energy_J'], 360000, delta=1e-6)
        event = next(row for row in result['events'] if row['kind'] == 'ups_depleted')
        self.assertAlmostEqual(event['time_s'], 32.4, delta=1e-12)
        self.assertTrue(all(row['domains']['backup']['ups_energy_J'] >= 0 for row in result['trace']))
        self.assertEqual(result['trace'][-1]['domains']['backup']['ups_energy_J'], 0)

    def test_qualified_work_moves_reserves_and_completes_at_exact_times(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(SCENARIO), duration_s=151, work_requests=[
            work_request('cooling-job', 0.25, 'worker_cooling',
                         'inspect_facility_cooling', 'intake_pump'),
        ])
        record = result['work_records'][0]
        self.assertEqual(record['status'], 'completed')
        self.assertEqual(record['arrived_at_s'], 120.25)
        self.assertEqual(record['completed_at_s'], 150.25)
        self.assertEqual(record['effect'], 'ENGINEERING_WORK_RECORD_ONLY_NO_REPAIR_OR_EVIDENCE')
        busy = next(row['domains']['people_tools_work'] for row in result['trace'] if row['time_s'] == 0.25)
        self.assertEqual(busy['workers']['worker_cooling']['status'], 'travelling')
        self.assertEqual(busy['tools']['tool_flow_meter']['reserved_by'], 'cooling-job')
        final = result['trace'][-1]['domains']['people_tools_work']
        self.assertEqual(final['workers']['worker_cooling']['location_id'], 'loc_lake')
        self.assertEqual(final['workers']['worker_cooling']['status'], 'idle')
        self.assertIsNone(final['tools']['tool_flow_meter']['reserved_by'])
        self.assertAlmostEqual(result['summary']['worker_travel_person_s'], 120, delta=1e-10)
        self.assertAlmostEqual(result['summary']['worker_work_person_s'], 30, delta=1e-10)

    def test_pending_work_keeps_planned_arrival_separate_from_actual_arrival(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(load_scenario(SCENARIO), duration_s=1, work_requests=[
            work_request('still-walking', 0.25, 'worker_cooling',
                         'inspect_facility_cooling', 'intake_pump'),
        ])
        record = result['work_records'][0]
        self.assertEqual(record['status'], 'travelling')
        self.assertEqual(record['scheduled_arrival_at_s'], 120.25)
        self.assertNotIn('arrived_at_s', record)
        self.assertNotIn('completed_at_s', record)
        person = result['trace'][-1]['domains']['people_tools_work']
        self.assertIsNone(person['tools']['tool_flow_meter']['location_id'])
        self.assertEqual(person['tools']['tool_flow_meter']['carried_by'], 'worker_cooling')

    def test_work_rejects_qualification_tool_worker_and_access_conflicts(self):
        from aegis_dc.plant import simulate_scenario
        requests = [
            work_request('holds-tool', 0, 'worker_cooling', 'inspect_facility_cooling', 'intake_pump'),
            work_request('tool-conflict', 0.1, 'worker_control', 'inspect_facility_cooling', 'plate_hx'),
            work_request('wrong-qualification', 0.2, 'worker_it', 'inspect_power', 'rectifier'),
            work_request('worker-conflict', 0.3, 'worker_cooling', 'inspect_facility_cooling', 'filter'),
            work_request('access-qualification', 0.4, 'worker_control', 'inspect_control_monitoring', 'point_power'),
        ]
        records = simulate_scenario(load_scenario(SCENARIO), duration_s=1,
                                    work_requests=requests)['work_records']
        reasons = {row['id']: row.get('reason') for row in records}
        self.assertEqual(reasons, {'holds-tool': None, 'tool-conflict': 'tool_busy',
                                  'wrong-qualification': 'qualification_mismatch',
                                  'worker-conflict': 'worker_busy',
                                  'access-qualification': 'access_unreachable'})
        scenario = load_scenario(SCENARIO)
        scenario['runtime']['closed_location_ids'] = ['loc_it']
        closed = simulate_scenario(scenario, duration_s=1, work_requests=[
            work_request('closed-room', 0, 'worker_cooling', 'inspect_equipment_environment', 'immersion'),
        ])
        self.assertEqual(closed['work_records'][0]['reason'], 'access_unreachable')

    def test_drainage_opens_access_at_crossing_and_never_drains_negative_mass(self):
        from aegis_dc.plant import simulate_scenario
        scenario = changed_parameters(initial_floor_water_mass=20, drainage_mass_flow=10)
        result = simulate_scenario(scenario, duration_s=3, work_requests=[
            work_request('before-draining', 0.5, 'worker_cooling', 'inspect_equipment_environment', 'immersion'),
            work_request('after-crossing', 1, 'worker_cooling', 'inspect_equipment_environment', 'immersion'),
        ])
        self.assertEqual(result['work_records'][0]['reason'], 'access_unreachable')
        self.assertTrue(result['work_records'][1]['accepted'])
        final = result['trace'][-1]['domains']['space_access']
        self.assertEqual(final['floor_water_mass_kg'], 0)
        self.assertEqual(final['drain_kg_s'], 0)
        self.assertNotIn('loc_it', final['blocked_location_ids'])
        self.assertEqual(result['summary']['floor_water_inlet_mass_kg'], 0)
        self.assertEqual(result['summary']['floor_water_drained_mass_kg'], 20)
        self.assertAlmostEqual(result['summary']['floor_drain_energy_J'], 24507340, delta=1e-8)

    def test_joint_service_deficit_is_not_added_once_per_limited_component(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(changed_parameters(network_service_capacity=0.6,
                                                       storage_service_capacity=0.6), duration_s=10)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 4, delta=1e-12)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], 6, delta=1e-12)
        first, last = result['trace'][0]['domains'], result['trace'][-1]['domains']
        self.assertEqual(first['power']['actual_powers_W']['network'], 60000)
        self.assertLess(last['equipment_environment']['room_temperature_K'],
                        first['equipment_environment']['room_temperature_K'])

    def test_initial_access_threshold_can_drain_toward_the_open_side(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(changed_parameters(initial_floor_water_mass=10, drainage_mass_flow=1),
                    duration_s=1, work_requests=[work_request('draining-equality', 0.5,
                    'worker_cooling', 'inspect_equipment_environment', 'immersion')])
        self.assertTrue(result['work_records'][0]['accepted'])
        self.assertNotIn('loc_it', result['trace'][-1]['domains']['space_access']['blocked_location_ids'])

    def test_filter_and_sampled_local_protection_change_physical_response(self):
        from aegis_dc.plant import simulate_scenario
        changed = simulate_scenario(load_scenario(SCENARIO), duration_s=2, boundary_events=[
            {'time_s': 0.25, 'parameter_id': 'filter_resistance_multiplier', 'value': 4,
             'source_note': 'Independent fixed-head filter-resistance engineering case.'},
        ])
        after = next(row['domains']['facility_cooling'] for row in changed['trace'] if row['time_s'] == 0.25)
        self.assertAlmostEqual(after['lake_pump']['volume_flow_m3_s'], 0.05, delta=1e-12)
        self.assertAlmostEqual(after['internal_pump']['volume_flow_m3_s'], 0.12, delta=1e-12)
        self.assertGreater(changed['trace'][-1]['domains']['facility_cooling']['cold_temperature_K'],
                           changed['trace'][0]['domains']['facility_cooling']['cold_temperature_K'])
        protected = simulate_scenario(changed_parameters(protection_temperature=304,
                                                          protection_reset_temperature=303), duration_s=2)
        self.assertEqual(protected['trace'][0]['domains']['control_monitoring']['mode'], 'protected')
        self.assertEqual(protected['trace'][0]['domains']['power']['actual_powers_W']['compute'], 0)
        self.assertEqual(protected['summary']['service_deficit_time_s'], 2)

    def test_generator_start_delay_is_a_split_event_and_fuel_is_finite(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(changed_parameters(grid_capacity=0, diesel_start_time=2.5), duration_s=3)
        running = next(row for row in result['events'] if row['kind'] == 'generator_running')
        self.assertEqual(running['time_s'], 2.5)
        self.assertEqual(result['summary']['service_deficit_time_s'], 2.5)
        self.assertGreater(result['summary']['generator_output_energy_J'], 0)
        self.assertLess(result['trace'][-1]['domains']['backup']['fuel_energy_J'], 500000000)

    def test_thermal_inertia_and_power_conversion_match_independent_hand_cases(self):
        from aegis_dc.plant import simulate_scenario
        heated = simulate_scenario(changed_parameters(it_thermal_capacity=2000000,
                    compute_demand_power=100000, network_demand_power=0, storage_demand_power=0,
                    solid_coolant_conductance=0, solid_air_conductance=0), duration_s=60)
        before, after = (row['domains']['equipment_environment']['solid_temperature_K']
                         for row in (heated['trace'][0], heated['trace'][-1]))
        self.assertAlmostEqual(after - before, 3, delta=1e-10)
        converted = simulate_scenario(changed_parameters(rectifier_efficiency=0.95,
                    compute_demand_power=95000, network_demand_power=0, storage_demand_power=0), duration_s=1)
        point = converted['trace'][0]['domains']['power']
        self.assertEqual(point['rectifier_input_W'], 100000)
        self.assertEqual(point['actual_powers_W']['compute'], 95000)
        self.assertEqual(point['rectifier_loss_W'], 5000)

    def test_replay_is_deterministic_and_does_not_mutate_the_source_scenario(self):
        from aegis_dc.plant import simulate_scenario
        scenario = load_scenario(SCENARIO)
        original = deepcopy(scenario)
        requests = [work_request('finite-job', 0.25, 'worker_cooling', 'inspect_facility_cooling', 'plate_hx')]
        first = simulate_scenario(scenario, duration_s=2, work_requests=requests)
        second = simulate_scenario(scenario, duration_s=2, work_requests=requests)
        self.assertEqual(scenario, original)
        self.assertEqual(first, second)

    def test_nonfinite_uninitialized_unsupported_and_unstable_runs_are_refused(self):
        from aegis_dc.plant import simulate_scenario
        for arguments in ({'duration_s': float('nan')}, {'step_s': float('inf')},
                          {'step_s': 2}, {'duration_s': True}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                simulate_scenario(load_scenario(SCENARIO), **arguments)
        with self.assertRaisesRegex(ValueError, 'initialized v2'):
            simulate_scenario(load_scenario(ROOT / 'configs/full-facility-mainline-v1.json'))
        scenario = load_scenario(SCENARIO)
        scenario['graphs']['access'][0]['duration_parameter'] = 'walk_long'
        with self.assertRaisesRegex(ValueError, 'Unsupported runtime topology'):
            simulate_scenario(scenario)
        with self.assertRaisesRegex(ValueError, 'finite'):
            simulate_scenario(changed_parameters(compute_demand_power=float('nan')))
        with self.assertRaisesRegex(ValueError, 'exactly one domain-valid root'):
            simulate_scenario(changed_parameters(coolant_initial_energy=2000000000), duration_s=1)
        with self.assertRaisesRegex(ValueError, 'Excessive temperature change'):
            simulate_scenario(changed_parameters(compute_demand_power=0, maximum_temperature_step=0.01), duration_s=1)


class PropertyReferenceTests(unittest.TestCase):
    def test_fixed_volume_flash_matches_external_EOS_reference(self):
        # Frozen independent-input CoolProp flash, not reconstructed with this code.
        table = SaturationTable.from_file(TABLE)
        state = table.flash(10.0, 2581678.41571952, 0.03323720367146753)
        self.assertAlmostEqual(state['pressure_Pa'], 800000.0, delta=8.0)
        self.assertAlmostEqual(state['temperature_K'], 304.47746316327664,
                               delta=0.0004)
        self.assertAlmostEqual(state['quality'], 0.1, delta=0.000003)
        self.assertAlmostEqual(state['liquid_mass_kg'] + state['vapor_mass_kg'],
                               10.0, delta=1e-12)

    def test_property_domain_and_nonfinite_inventory_are_refused(self):
        table = SaturationTable.from_file(TABLE)
        for pressure in (50000, 3030000, float('nan'), True):
            with self.subTest(pressure=pressure), self.assertRaises(ValueError):
                table.at_pressure(pressure)
        for inventory in ((0, 1, 1), (10, float('inf'), 1), (10, 1e12, 0.01),
                          (10, 1e6, 100.0)):
            with self.subTest(inventory=inventory), self.assertRaises(ValueError):
                table.flash(*inventory)

    def test_all_25_frozen_external_flash_inputs_and_table_endpoints(self):
        table = SaturationTable.from_file(TABLE)
        reference = json.loads((ROOT / 'evidence/mainline/engineering/property-reference/finite-verification.json').read_text(encoding='utf-8'))
        for record in reference['initial_state_inverse']['cases']:
            with self.subTest(pressure=record['given_pressure_Pa'], quality=record['given_quality']):
                state = table.flash(record['M_kg'], record['U_J'], record['V_m3'])
                self.assertAlmostEqual(state['pressure_Pa'] / record['given_pressure_Pa'], 1, delta=1e-5)
                self.assertAlmostEqual(state['temperature_K'], record['external_EOS_flash']['T_K'], delta=0.0004)
                self.assertAlmostEqual(state['quality'], record['given_quality'], delta=3e-6)
        for pressure in (100000, 3000000):
            properties = table.at_pressure(pressure)
            # Inversion closure at the declared table boundary, not EOS validation.
            state = table.flash(10, 5 * (properties['u_l_J_kg'] + properties['u_v_J_kg']),
                                5 * (properties['v_l_m3_kg'] + properties['v_v_m3_kg']))
            self.assertAlmostEqual(state['pressure_Pa'], pressure, delta=1e-6)


class FacilityRunCLITests(unittest.TestCase):
    def test_CLI_saves_private_trajectory_in_a_fresh_directory_and_prints_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'new-engineering-run'
            command = [sys.executable, '-X', 'utf8', '-m', 'aegis_dc', 'simulate',
                       '--duration', '2', '--output', str(target)]
            env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
            completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads(completed.stdout)
            self.assertEqual(summary['status'], 'ENGINEERING_FIXTURE_COMPLETED')
            self.assertNotIn('trace', summary)
            self.assertNotIn('source_config', summary)
            self.assertEqual(summary['artifacts']['private-state.jsonl']['records'], 3)
            self.assertEqual(len((target / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()), 3)
            self.assertEqual(json.loads((target / 'scenario.json').read_text(encoding='utf-8'))['id'],
                             'aegisdc-zhengzhou-inspired-full-facility-v2')
            repeated = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn('exists', repeated.stderr)
            self.assertNotIn('Traceback', repeated.stderr)


if __name__ == '__main__':
    unittest.main()
