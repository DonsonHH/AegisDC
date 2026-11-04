"""Independent numerical qualification at the accepted V6 public seams."""
import json
import math
from pathlib import Path
import unittest

from aegis_dc.plant import simulate_scenario
from aegis_dc.scenario import load_scenario, validate_scenario
from aegis_dc.thermodynamics import SaturationTable

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / 'docs/mainline/12-numerical-runbook.json'


def numerical_case(identifier):
    book = json.loads(RUNBOOK.read_text(encoding='utf-8'))
    item = next(row for row in book['cases'] if row['id'] == identifier)
    scenario = load_scenario(ROOT / book['profile'])
    for row in scenario['parameters']:
        if row['id'] in item['overrides']:
            row.update(value=item['overrides'][row['id']], basis='synthetic_assumption',
                       source_note='Frozen ticket 12 numerical engineering case: ' + identifier)
    return item, scenario


class FullFacilityNumericalTests(unittest.TestCase):
    def test_isolated_room_agrees_with_independent_exponential_solution(self):
        # C=1 MJ/K, G=0.1 MW/K, initially 10 K above a constant 293.15 K
        # boundary. Exact solution at 10 s is 293.15 + 10/e K. This is
        # an analytic ODE solution, not the production Euler recurrence.
        item, scenario = numerical_case('isolated-room')
        result = simulate_scenario(scenario, duration_s=10, step_s=.025)
        end = result['trace'][-1]['domains']
        self.assertEqual(len(end), 8)
        self.assertAlmostEqual(end['equipment_environment']['room_temperature_K'],
                               296.8287944117144, delta=.005)
        self.assertEqual(end['facility_cooling']['internal_mass_flow_kg_s'], 0)
        self.assertEqual(end['facility_cooling']['condenser_heat_W'], 0)
        self.assertEqual(end['equipment_environment']['refrigerant']['mass_kg'], 2000)
        self.assertEqual(result['summary']['service_deficit_time_s'], 10)
        self.assertLess(abs(result['summary']['whole_run_energy_residual_J']), .001)

    def test_one_ulp_event_expression_does_not_change_the_sampled_protection_epoch(self):
        # 0.6 and .2*3 differ by one binary64 ulp. They describe the same
        # research time, whereas .600001 is a deliberately later instant.
        for when, delivered in ((.6, .6), (.2 * 3, .6), (.600001, .7)):
            with self.subTest(encoded_time=when.hex()):
                scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
                next(row for row in scenario['parameters'] if row['id'] == 'control_sample_time')['value'] = .1
                result = simulate_scenario(scenario, duration_s=1, step_s=.25,
                    boundary_events=[dict(time_s=when, parameter_id='local_temperature_bias',
                        value=50, source_note='One-ulp time-expression numerical engineering probe.')])
                self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], delivered, delta=1e-12)
                event = next(row for row in result['events'] if row['kind'] == 'exogenous_boundary_input')
                self.assertEqual(event['time_s'], when)
                self.assertLessEqual(abs(event['applied_at_s'] - when), 8 * math.ulp(when))
                self.assertEqual(result['time_coordinate_convention']['version'], 'aegisdc-binary64-time-v1')

    def test_eight_ulp_coincidence_is_bounded_and_does_not_roll_across_an_event_chain(self):
        for offset, expected in ((8, .5), (9, .75)):
            with self.subTest(offset_ulps=offset):
                scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
                next(row for row in scenario['parameters'] if row['id'] == 'control_sample_time')['value'] = .25
                when = .5 + offset * math.ulp(.5)
                result = simulate_scenario(scenario, duration_s=1, step_s=.25,
                    boundary_events=[dict(time_s=when, parameter_id='local_temperature_bias', value=50,
                        source_note='Boundary of declared numerical coincidence, not equipment resolution.')])
                self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], expected, delta=1e-12)
        scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
        events = [dict(time_s=.5 + offset * math.ulp(.5), parameter_id=name, value=value,
                       source_note='Non-transitive adjacent-event chain numerical probe.')
                  for offset, name, value in ((0, 'supervisory_link_available', 0),
                                              (8, 'network_service_capacity', .5),
                                              (16, 'storage_service_capacity', .25))]
        result = simulate_scenario(scenario, duration_s=1, step_s=.25, boundary_events=events)
        applied = [row['applied_at_s'] for row in result['events'] if row['kind'] == 'exogenous_boundary_input']
        self.assertEqual(applied, [.5, .5, .5 + 16 * math.ulp(.5)])
        self.assertEqual(result['inputs']['boundary_events'], events)

    def test_coincident_conflicting_parameter_values_are_rejected(self):
        scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
        events = [dict(time_s=when, parameter_id='service_demand', value=value,
                       source_note='Conflicting same-epoch numerical engineering inputs.')
                  for when, value in ((.6, 1), (.2 * 3, 1.5))]
        with self.assertRaisesRegex(ValueError, 'Conflicting boundary event'):
            simulate_scenario(scenario, duration_s=1, boundary_events=events)

    def test_sample_clock_stays_anchored_during_arbitrary_step_subdivision(self):
        scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
        next(row for row in scenario['parameters'] if row['id'] == 'control_sample_time')['value'] = .1
        result = simulate_scenario(scenario, duration_s=10, step_s=.037)
        sampled = sorted({row['domains']['control_monitoring']['local_measurement']['sampled_at_s']
                          for row in result['trace']})
        self.assertEqual(sampled, [index * .1 for index in range(101)])

    def test_access_at_a_threshold_uses_the_final_same_epoch_drain_direction(self):
        scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
        values = {'floor_water_inflow': 1.1, 'drainage_mass_flow': .1, 'access_block_mass': .6}
        for row in scenario['parameters']:
            if row['id'] in values:
                row['value'] = values[row['id']]
        result = simulate_scenario(scenario, duration_s=1, step_s=.25,
            boundary_events=[dict(time_s=.2 * 3, parameter_id='floor_water_inflow', value=0,
                source_note='Net 1 kg/s reaches .6 kg at .6 s, then drains.')],
            work_requests=[dict(id='threshold-work', time_s=.6, worker_id='worker_it',
                work_interface_id='inspect_it_service', target_id='compute',
                source_note='Public work boundary at the final right-hand threshold state.')])
        self.assertEqual(result['work_records'][0]['status'], 'working')
        self.assertAlmostEqual(result['summary']['worker_work_person_s'], .4, delta=1e-12)
        self.assertAlmostEqual(result['trace'][-1]['domains']['space_access']['floor_water_mass_kg'], .56)

    def test_dimensionally_incompatible_heat_mass_and_power_units_are_refused(self):
        for identifier, wrong_unit in [('water_specific_heat', 'J/kg'),
                                        ('coolant_inventory', 'kg/s'), ('grid_capacity', 'J')]:
            with self.subTest(parameter=identifier):
                scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
                next(row for row in scenario['parameters'] if row['id'] == identifier)['unit'] = wrong_unit
                with self.assertRaises(ValueError):
                    validate_scenario(scenario)

    def test_five_original_encoded_vapor_endpoint_refusals_remain_strict(self):
        path = ROOT / 'evidence/mainline/engineering/04-06-root-acceptance/endpoint-representation/probe-result-01.json'
        old = json.loads(path.read_text(encoding='utf-8'))
        table = SaturationTable.from_file(ROOT / 'configs/materials/reference-r134a-saturation.json')
        refused = [row for row in old['all_outcomes'] if row['outcome']['status'] == 'REFUSED']
        self.assertEqual(len(refused), 5)
        for row in refused:
            with self.subTest(inputs=row['inputs_float_hex']):
                self.assertGreater(row['representation_observation']['reconstructed_quality'], 1)
                with self.assertRaisesRegex(ValueError, 'exactly one domain-valid root'):
                    table.flash(**row['inputs'])

    def test_rounded_floor_crossing_does_not_delay_access_by_an_entire_step(self):
        item, scenario = numerical_case('combined-240s')
        result = simulate_scenario(scenario, duration_s=240, step_s=.5,
                                   boundary_events=item['events'], work_requests=item['work_requests'])
        work = next(row for row in result['work_records'] if row['id'] == 'room-engineering-visit')
        self.assertAlmostEqual(work['finished_at_s'], 145.5, delta=1e-8)
        self.assertAlmostEqual(result['summary']['worker_work_person_s'], 25.25, delta=1e-8)
        boundary = next(row for row in result['trace'] if row['time_s'] == 145.5)['domains']
        self.assertIn('loc_it', boundary['space_access']['blocked_location_ids'])
        self.assertAlmostEqual(boundary['space_access']['floor_water_mass_kg'], 10, delta=1e-10)

    def test_floor_boundary_stationary_and_reversed_right_limits_keep_their_declared_side(self):
        for h in (1, .5, .1):
            for initial, inlet, drain, after_inlet, blocked in (
                    (0, .5, .1, .1, True), (0, .5, .1, 0, False),
                    (20, 0, .4, .4, False), (20, 0, .4, .8, True)):
                with self.subTest(step=h, initial=initial, final_inlet=after_inlet):
                    scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
                    values = dict(initial_floor_water_mass=initial, floor_water_inflow=inlet, drainage_mass_flow=drain)
                    for row in scenario['parameters']:
                        if row['id'] in values:
                            row['value'] = values[row['id']]
                    result = simulate_scenario(scenario, duration_s=26, step_s=h,
                        boundary_events=[dict(time_s=25, parameter_id='floor_water_inflow', value=after_inlet,
                            source_note='Exact 25 s threshold: stop or reverse the right-hand flow.')],
                        work_requests=[dict(id='right-limit', time_s=25, worker_id='worker_it',
                            work_interface_id='inspect_it_service', target_id='compute',
                            source_note='Check access only after the final same-time flow.')])
                    self.assertEqual(result['work_records'][0]['accepted'], not blocked)
                    self.assertEqual('loc_it' in result['trace'][-1]['domains']['space_access']['blocked_location_ids'], blocked)
        scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
        for row in scenario['parameters']:
            if row['id'] == 'initial_floor_water_mass':
                row['value'] = 10
            if row['id'] == 'drainage_mass_flow':
                row['value'] = 0
        result = simulate_scenario(scenario, duration_s=.1)
        self.assertIn('loc_it', result['trace'][-1]['domains']['space_access']['blocked_location_ids'])

    def test_compensated_floor_inventory_empties_and_refills_without_old_residue_or_heat(self):
        for h in (1, .1, .025):
            with self.subTest(step=h):
                scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
                for row in scenario['parameters']:
                    if row['id'] == 'floor_water_inflow':
                        row['value'] = .7
                    if row['id'] == 'drainage_mass_flow':
                        row['value'] = .2
                result = simulate_scenario(scenario, duration_s=10, step_s=h,
                    boundary_events=[dict(time_s=t, parameter_id='floor_water_inflow', value=v,
                        source_note='Ambient water fill, complete drain, then refill; no internal leak.')
                        for t, v in [(2, 0), (8, .6)]])
                end = result['trace'][-1]['domains']['space_access']
                self.assertAlmostEqual(end['floor_water_mass_kg'], .8, delta=1e-12)
                self.assertAlmostEqual(end['floor_water_temperature_K'], 293.15, delta=1e-10)
                self.assertAlmostEqual(end['floor_water_sensible_energy_J'], 980293.6, delta=1e-5)
                self.assertTrue(any(row['domains']['space_access']['floor_water_mass_kg'] == 0
                                    for row in result['trace'] if 7 - 1e-8 <= row['time_s'] < 8))
                self.assertAlmostEqual(result['summary']['floor_water_inlet_mass_kg'], 2.6, delta=1e-12)
                self.assertAlmostEqual(result['summary']['floor_water_drained_mass_kg'], 1.8, delta=1e-12)
                self.assertLess(result['summary']['max_energy_residual_J'], .01)


if __name__ == '__main__':
    unittest.main()
