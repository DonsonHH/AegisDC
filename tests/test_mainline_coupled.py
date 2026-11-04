"""One V6 facility, tested only through scenario/run/save and actual CLI seams."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aegis_dc.plant import describe_run, save_run, simulate_scenario
from aegis_dc.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'configs/full-facility-mainline-reserve-v6.json'
RUNBOOK = ROOT / 'docs/mainline/11-coupled-runbook.json'


def case(identifier):
    return next(item for item in json.loads(RUNBOOK.read_text(encoding='utf-8'))['cases']
                if item['id'] == identifier)


def configured(item):
    scenario = load_scenario(PROFILE)
    for row in scenario['parameters']:
        if row['id'] in item.get('overrides', {}):
            row.update(value=item['overrides'][row['id']], basis='synthetic_assumption',
                       source_note='Frozen ticket 11 synthetic engineering case: ' + item['id'])
    return scenario


def run(identifier):
    item = case(identifier)
    return simulate_scenario(configured(item), duration_s=item['duration_s'], step_s=item['step_s'],
                             work_requests=item.get('work_requests', []),
                             boundary_events=item.get('events', []))


def at(result, time_s):
    return next(row['domains'] for row in result['trace'] if abs(row['time_s'] - time_s) < 1e-9)


class CoupledFacilityAcceptanceTests(unittest.TestCase):
    def test_same_V6_stays_at_its_normal_working_point_for_ten_minutes(self):
        result = run('normal-600s')
        self.assertEqual(result['summary']['delivered_service_unit_s'], 600)
        self.assertEqual(result['summary']['service_deficit_time_s'], 0)
        before, after = at(result, 0), at(result, 600)
        self.assertEqual(len(after), 8)
        for domain, name in [('facility_cooling', 'hot_temperature_K'),
                             ('facility_cooling', 'cold_temperature_K'),
                             ('equipment_environment', 'solid_temperature_K'),
                             ('equipment_environment', 'room_temperature_K')]:
            self.assertAlmostEqual(before[domain][name], after[domain][name], delta=1e-7)
        self.assertEqual(after['equipment_environment']['refrigerant']['mass_kg'], 2000)
        self.assertAlmostEqual(after['equipment_environment']['refrigerant']['vapor_mass_kg'], 200, delta=1e-8)
        self.assertEqual(after['backup']['ups_energy_J'], 18000000)
        self.assertEqual(after['backup']['starter_energy_J'], 100000)
        self.assertEqual(after['backup']['fuel_energy_J'], 500000000)
        self.assertLess(abs(result['summary']['whole_run_energy_residual_J']), .01)

    def test_one_AC_budget_limits_all_three_IT_groups_and_actual_heat(self):
        result = run('shared-AC-capacity')
        first = at(result, 0)
        self.assertAlmostEqual(first['power']['rectifier_input_W'], 53261.42857142857)
        self.assertAlmostEqual(first['it_service']['delivered'], .02348344805194805)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], .0469668961038961)
        self.assertAlmostEqual(result['summary']['grid_energy_J'], 200000)
        self.assertLess(at(result, 2)['equipment_environment']['solid_temperature_K'], 308.47751006414603)
        self.assertEqual(first['backup']['reserve_states']['ups']['mode'], 'bypass')
        self.assertEqual(first['backup']['generator_mode'], 'off')

    def test_one_rectifier_limits_service_despite_plentiful_mains(self):
        result = run('shared-rectifier-capacity')
        self.assertEqual(at(result, 0)['power']['rectifier_input_W'], 100000)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], 1 / 22)

    def test_common_distribution_defeats_positive_reserves_and_PLC_recovery_waits_for_its_clock(self):
        result = run('common-distribution')
        dark = at(result, 1)
        self.assertEqual(dark['power']['generator_output_W'], 0)
        self.assertEqual(dark['power']['ups_protected_output_W'], 0)
        self.assertGreater(dark['backup']['ups_energy_J'], 0)
        self.assertGreater(dark['backup']['fuel_energy_J'], 0)
        self.assertEqual(dark['control_monitoring']['mode'], 'unpowered_fail_safe')
        self.assertEqual(at(result, 1.75)['control_monitoring']['local_measurement']['sampled_at_s'], 1)
        self.assertEqual(result['summary']['delivered_service_unit_s'], .25)
        self.assertEqual(result['summary']['service_deficit_time_s'], 1.75)

    def test_joint_service_uses_the_limiting_compute_network_or_storage_capacity_once(self):
        result = run('joint-compute-network-storage')
        self.assertEqual(at(result, .25)['it_service']['delivered'], .5)
        self.assertEqual(at(result, 2.25)['it_service']['delivered'], .25)
        self.assertEqual(at(result, 4.25)['it_service']['delivered'], 0)
        self.assertEqual(at(result, 4.25)['power']['actual_powers_W']['compute'], 1000000)
        self.assertEqual(result['summary']['demand_service_unit_s'], 8)
        self.assertEqual(result['summary']['delivered_service_unit_s'], 3.5)
        self.assertEqual(result['summary']['service_deficit_time_s'], 4.5)

    def test_shutoff_stops_HX_and_condensation_before_sampled_protection_but_keeps_phase_inventory(self):
        result = run('internal-valve-phase')
        closed = at(result, .25)
        self.assertEqual(closed['facility_cooling']['internal_mass_flow_kg_s'], 0)
        self.assertEqual(closed['facility_cooling']['plate_hx_heat_W'], 0)
        self.assertEqual(closed['facility_cooling']['condenser_heat_W'], 0)
        self.assertEqual(closed['power']['actual_powers_W']['compute'], 2000000)
        heated = at(result, 1)['equipment_environment']['refrigerant']
        self.assertAlmostEqual(heated['internal_energy_J'], 517835850.31469756, delta=.001)
        self.assertAlmostEqual(heated['liquid_mass_kg'] + heated['vapor_mass_kg'], 2000)
        self.assertGreater(heated['pressure_Pa'], 800000)
        self.assertGreater(heated['vapor_mass_kg'], 200)
        self.assertEqual(at(result, 1)['control_monitoring']['protection_latched'], True)
        self.assertEqual(result['summary']['service_deficit_time_s'], .25)

    def test_biased_local_trip_survives_link_loss_power_cycle_and_link_recovery(self):
        result = run('bias-link-power-latch')
        self.assertEqual(at(result, .25)['control_monitoring']['local_measurement']['sampled_at_s'], 0)
        protected = at(result, 1)
        self.assertAlmostEqual(protected['equipment_environment']['refrigerant']['temperature_K'], 304.47751006414603)
        self.assertAlmostEqual(protected['control_monitoring']['local_measurement']['temperature_K'], 314.47751006414603)
        self.assertEqual(protected['control_monitoring']['supervisory_mode'], 'autonomous')
        self.assertEqual(at(result, 2)['control_monitoring']['mode'], 'unpowered_fail_safe')
        self.assertTrue(at(result, 2)['control_monitoring']['protection_latched'])
        self.assertTrue(at(result, 4)['control_monitoring']['protection_latched'])
        self.assertEqual(at(result, 4)['control_monitoring']['supervisory_mode'], 'connected')
        self.assertEqual(result['summary']['service_deficit_time_s'], 3)

    def test_invalid_flow_is_not_clipped_and_recovery_uses_a_fresh_clock_sample(self):
        result = run('invalid-flow-channel')
        invalid = at(result, 1)['control_monitoring']
        self.assertEqual(invalid['mode'], 'sensor_invalid_fail_safe')
        self.assertAlmostEqual(invalid['local_measurement']['internal_volume_flow_m3_s'], -.08)
        self.assertFalse(invalid['local_measurement']['valid'])
        self.assertEqual(at(result, 1.25)['control_monitoring']['local_measurement']['sampled_at_s'], 1)
        self.assertEqual(at(result, 2)['control_monitoring']['mode'], 'normal')
        self.assertEqual(result['summary']['service_deficit_time_s'], 1)

    def test_generator_start_and_fuel_are_finite_in_the_combined_V6(self):
        result = run('finite-generator-hand')
        self.assertEqual(at(result, 3)['backup']['generator_mode'], 'transferring')
        connected = at(result, 5)
        self.assertEqual(connected['backup']['generator_mode'], 'supplying')
        self.assertEqual(connected['power']['generator_output_W'], 1110)
        self.assertAlmostEqual(connected['backup']['starter_energy_J'], 6950)
        self.assertEqual(connected['backup']['fuel_energy_J'], 37750)
        self.assertEqual(at(result, 15)['backup']['fuel_energy_J'], 0)
        self.assertEqual(at(result, 15)['backup']['generator_mode'], 'fuel_exhausted')

    def test_personnel_walk_with_one_meter_and_reject_real_qualification_tool_worker_and_route_conflicts(self):
        result = run('personnel-resource-conflicts')
        records = result['work_records']
        self.assertEqual(records[0]['arrived_at_s'], 120.25)
        self.assertEqual(records[0]['completed_at_s'], 150.25)
        self.assertEqual([row['reason'] for row in records[1:]],
                         ['tool_busy', 'qualification_mismatch', 'worker_busy', 'access_unreachable'])
        walking = at(result, .5)['people_tools_work']
        self.assertIsNone(walking['workers']['worker_cooling']['location_id'])
        self.assertEqual(walking['tools']['tool_flow_meter']['reserved_by'], 'holds-meter')
        self.assertEqual(result['summary']['worker_travel_person_s'], 120)
        self.assertEqual(result['summary']['worker_work_person_s'], 30)
        self.assertEqual(result['summary']['tool_occupation_tool_s'], 150)
        self.assertTrue(all(row['effect'] == 'ENGINEERING_WORK_RECORD_ONLY_NO_REPAIR_OR_EVIDENCE' for row in records))

    def test_gate_permission_stops_arrival_without_stopping_the_healthy_service(self):
        result = run('gate-before-arrival')
        record = result['work_records'][0]
        self.assertEqual(record['status'], 'aborted')
        self.assertEqual(record['finished_at_s'], 120)
        self.assertNotIn('arrived_at_s', record)
        self.assertEqual(at(result, 121)['people_tools_work']['tools']['tool_flow_meter']['location_id'], 'loc_control')
        self.assertEqual(result['summary']['worker_travel_person_s'], 120)
        self.assertEqual(result['summary']['worker_work_person_s'], 0)
        self.assertEqual(result['summary']['delivered_service_unit_s'], 121)

    def test_actual_room_heat_aborts_work_at_the_independent_thermal_limit(self):
        result = run('room-thermal-work-limit')
        self.assertEqual(result['work_records'][0]['status'], 'aborted')
        self.assertAlmostEqual(result['work_records'][0]['finished_at_s'], 1.5)
        self.assertAlmostEqual(result['summary']['worker_work_person_s'], 1.5)
        self.assertAlmostEqual(at(result, 2)['equipment_environment']['room_temperature_K'], 300.2022)
        self.assertEqual(at(result, 2)['space_access']['floor_water_mass_kg'], 0)

    def test_same_time_selector_cancels_old_UPS_need_and_creates_new_need_without_extra_PLC_samples(self):
        cancellation = run('selector-cancels-old-need')
        self.assertEqual(at(cancellation, 0)['backup']['reserve_states']['ups']['mode'], 'bypass')
        self.assertEqual(at(cancellation, 2)['power']['actual_powers_W']['backup_fan'], 5000)
        self.assertEqual(cancellation['summary']['backup_fan_energy_J'], 10000)
        primary = run('selector-creates-new-need')
        waiting = at(primary, 3)['backup']['reserve_states']['ups']
        self.assertEqual(waiting['requested_at_s'], 3)
        self.assertEqual(waiting['ready_at_s'], 3.2)
        self.assertEqual(at(primary, 3.2)['backup']['reserve_states']['ups']['mode'], 'supplying')
        self.assertEqual(at(primary, 3.2)['control_monitoring']['local_measurement']['sampled_at_s'], 3)

    def test_actual_CLI_saves_one_combined_episode_with_work_interruption_and_exogenous_service_accounts(self):
        item = case('combined-episode-CLI')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            model, inputs = directory / 'model.json', directory / 'inputs.json'
            model.write_text(json.dumps(configured(item)), encoding='utf-8')
            inputs.write_text(json.dumps({'schema': 'aegisdc-engineering-inputs-v1',
                'boundary_events': item['events'], 'work_requests': item['work_requests']}), encoding='utf-8')
            process = subprocess.run([sys.executable, '-m', 'aegis_dc', 'simulate', '--model', str(model),
                '--inputs', str(inputs), '--duration', '240', '--output', str(directory / 'run')],
                cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            saved = json.loads((directory / 'run/run.json').read_text(encoding='utf-8'))
            self.assertEqual(json.loads(process.stdout), saved)
            self.assertEqual(saved['inputs']['boundary_events'], item['events'])
            self.assertEqual(saved['work_records'][0]['status'], 'aborted')
            self.assertAlmostEqual(saved['work_records'][0]['finished_at_s'], 145.5)
            self.assertEqual(saved['summary']['demand_service_unit_s'], 275)
            self.assertAlmostEqual(saved['summary']['service_deficit_time_s'], 36)
            self.assertAlmostEqual(saved['summary']['delivered_service_unit_s'], 231.8)
            self.assertAlmostEqual(saved['summary']['worker_work_person_s'], 25.25)
            self.assertAlmostEqual(saved['summary']['internal_hot_leaked_mass_kg'], 20)
            self.assertAlmostEqual(saved['summary']['floor_water_drained_mass_kg'], 11.95)
            rows = [json.loads(line) for line in (directory / 'run/private-state.jsonl').read_text(encoding='utf-8').splitlines()]
            trace = {'trace': rows}
            self.assertEqual(at(trace, 65.7)['power']['actual_powers_W']['backup_fan'], 0)
            self.assertEqual(at(trace, 65.7)['control_monitoring']['local_measurement']['sampled_at_s'], 65)
            self.assertAlmostEqual(rows[-1]['domains']['space_access']['floor_water_mass_kg'], 8.05)
            self.assertEqual(len(rows[-1]['domains']), 8)

    def test_finite_UPS_exhaustion_never_creates_IT_coverage_or_negative_energy(self):
        result = run('finite-UPS-hand')
        self.assertEqual(at(result, .2)['power']['ups_protected_output_W'], 100000)
        self.assertEqual(at(result, 32.6)['backup']['ups_energy_J'], 0)
        self.assertAlmostEqual(result['summary']['ups_output_energy_J'], 3272600, delta=.001)
        self.assertAlmostEqual(result['summary']['ups_loss_energy_J'], 360000, delta=.001)
        self.assertAlmostEqual(result['summary']['reserve_room_control_heat_J'], 32600, delta=.001)
        self.assertEqual(result['summary']['delivered_service_unit_s'], 0)
        empty = run('empty-starter-with-fuel')
        self.assertEqual(at(empty, 0)['backup']['generator_mode'], 'starter_depleted')
        self.assertEqual(at(empty, 6)['backup']['fuel_energy_J'], 42750)
        self.assertEqual(at(empty, 6)['power']['generator_output_W'], 0)

    def test_public_run_refuses_phase_hydraulic_and_permission_domain_exits(self):
        for item in json.loads(RUNBOOK.read_text(encoding='utf-8'))['rejections']:
            with self.subTest(case=item['id']), self.assertRaisesRegex(ValueError, item['error_contains']):
                simulate_scenario(configured(item), duration_s=item['duration_s'], step_s=item['step_s'],
                                  boundary_events=item['events'])

    def test_describe_and_save_preserve_the_eight_domain_original_and_never_overwrite_it(self):
        result = run('internal-valve-phase')
        compact = describe_run(result)
        self.assertNotIn('trace', compact)
        self.assertNotIn('source_config', compact)
        self.assertEqual(compact['state_visibility'], 'PRIVATE_PLANT_EVALUATOR_ONLY')
        self.assertEqual([compact[key] for key in ('research_trials', 'model_calls', 'training_calls')], [0, 0, 0])
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'original'
            manifest = save_run(result, output)
            saved = json.loads((output / 'run.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest, saved)
            self.assertEqual(saved['artifacts']['private-state.jsonl']['records'], len(result['trace']))
            self.assertEqual(json.loads((output / 'scenario.json').read_text(encoding='utf-8')), result['source_config'])
            with self.assertRaises(FileExistsError):
                save_run(result, output)


if __name__ == '__main__':
    unittest.main()
