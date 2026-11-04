"""Independent joint-service hand cases at the full-facility run/CLI seams."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aegis_dc.plant import simulate_scenario
from aegis_dc.scenario import load_scenario


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / 'configs/full-facility-mainline-v2.json'


def event(time_s, parameter_id, value):
    return {'time_s': time_s, 'parameter_id': parameter_id, 'value': value,
            'source_note': 'Ticket 08 synthetic engineering input; not a site event or research trial.'}


class MainlineServiceTests(unittest.TestCase):
    def test_timed_compute_capacity_limits_service_without_changing_demand(self):
        # Demand is 1 for 2 s. Half compute capacity for exactly 1 s loses
        # 0.5 service-unit s and 0.5 normalized deficit seconds.
        result = simulate_scenario(load_scenario(SCENARIO), duration_s=2, boundary_events=[
            event(0.25, 'compute_service_capacity', 0.5),
            event(1.25, 'compute_service_capacity', 1),
        ])
        self.assertEqual(result['summary']['demand_service_unit_s'], 2)
        self.assertEqual(result['summary']['delivered_service_unit_s'], 1.5)
        self.assertEqual(result['summary']['service_deficit_time_s'], 0.5)
        limited = next(row['domains'] for row in result['trace'] if row['time_s'] == 0.25)
        self.assertEqual(limited['it_service'], {'demand': 1, 'delivered': 0.5,
                         'capacities': {'compute': 0.5, 'network': 1, 'storage': 1}, 'unserved': 0.5})
        self.assertEqual(limited['power']['actual_powers_W']['compute'], 1000000)
        self.assertEqual(limited['power']['actual_powers_W']['network'], 100000)
        self.assertEqual(limited['power']['actual_powers_W']['storage'], 100000)

    def test_overlapping_network_and_storage_losses_are_counted_once(self):
        # Joint delivery over the five intervals is .25+.30+.20+.20+.25=1.20.
        # Adding the individual .4 s network and .6 s storage losses would be
        # wrong: their overlapping contribution belongs to the same service.
        result = simulate_scenario(load_scenario(SCENARIO), duration_s=2, boundary_events=[
            event(0.25, 'network_service_capacity', 0.6),
            event(0.75, 'storage_service_capacity', 0.4),
            event(1.25, 'network_service_capacity', 1),
            event(1.75, 'storage_service_capacity', 1),
        ])
        self.assertEqual(result['summary']['demand_service_unit_s'], 2)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], 1.2, delta=1e-12)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], 0.8, delta=1e-12)
        overlap = next(row['domains'] for row in result['trace'] if row['time_s'] == 0.75)
        self.assertEqual(overlap['it_service']['capacities'], {'compute': 1, 'network': 0.6, 'storage': 0.4})
        self.assertEqual(overlap['it_service']['delivered'], 0.4)
        self.assertEqual(overlap['power']['actual_powers_W']['compute'], 2000000)
        self.assertEqual(overlap['power']['actual_powers_W']['network'], 60000)
        self.assertEqual(overlap['power']['actual_powers_W']['storage'], 40000)

    def test_any_required_component_can_stop_the_service_while_the_others_remain_powered(self):
        for component in ('compute', 'network', 'storage'):
            with self.subTest(component=component):
                result = simulate_scenario(load_scenario(SCENARIO), duration_s=2, boundary_events=[
                    event(0.25, component + '_service_capacity', 0),
                    event(1.25, component + '_service_capacity', 1),
                ])
                stopped = next(row['domains'] for row in result['trace'] if row['time_s'] == 0.25)
                self.assertEqual(stopped['it_service']['delivered'], 0)
                self.assertEqual(stopped['it_service']['capacities'][component], 0)
                for remaining in {'compute', 'network', 'storage'} - {component}:
                    self.assertEqual(stopped['it_service']['capacities'][remaining], 1)
                    self.assertGreater(stopped['power']['actual_powers_W'][remaining], 0)
                self.assertEqual(result['summary']['demand_service_unit_s'], 2)
                self.assertEqual(result['summary']['delivered_service_unit_s'], 1)
                self.assertEqual(result['summary']['service_deficit_time_s'], 1)

    def test_zero_demand_intervals_add_no_deficit_and_positive_demand_resumes_its_account(self):
        result = simulate_scenario(load_scenario(SCENARIO), duration_s=2, boundary_events=[
            event(0, 'service_demand', 0),
            event(0, 'network_service_capacity', 0.25),
            event(1, 'service_demand', 1),
        ])
        self.assertEqual(result['trace'][0]['domains']['it_service']['demand'], 0)
        self.assertEqual(result['trace'][0]['domains']['it_service']['delivered'], 0)
        self.assertEqual(result['balances'][0]['service_deficit_time_s'], 0)
        self.assertEqual(result['summary']['demand_service_unit_s'], 1)
        self.assertEqual(result['summary']['delivered_service_unit_s'], 0.25)
        self.assertEqual(result['summary']['service_deficit_time_s'], 0.75)

    def test_fractional_and_changing_demand_keep_interval_specific_denominators(self):
        # First second: demand .5, delivery .25 -> .5 deficit seconds.
        # Next second: demand 2, delivery .25 -> .875 deficit seconds.
        # Requested work is 2.5 normalized service-unit s, delivery .5.
        result = simulate_scenario(load_scenario(SCENARIO), duration_s=2, boundary_events=[
            event(0, 'service_demand', 0.5),
            event(0, 'network_service_capacity', 0.25),
            event(1, 'service_demand', 2),
        ])
        self.assertEqual(result['summary']['demand_service_unit_s'], 2.5)
        self.assertEqual(result['summary']['delivered_service_unit_s'], 0.5)
        self.assertEqual(result['summary']['service_deficit_time_s'], 1.375)

    def test_execution_throttling_or_pause_does_not_erase_requested_service(self):
        # These are execution-request changes, not hardware-failure surrogates.
        # Restoring execution cannot retroactively erase the intervening loss.
        for requested_power, lost_service in ((0, 1), (1000000, 0.5)):
            with self.subTest(execution_request_W=requested_power):
                result = simulate_scenario(load_scenario(SCENARIO), duration_s=3, boundary_events=[
                    event(0.5, 'compute_demand_power', requested_power),
                    event(1.5, 'compute_demand_power', 2000000),
                ])
                self.assertTrue(all(row['domains']['it_service']['demand'] == 1 for row in result['trace']))
                self.assertEqual(result['summary']['demand_service_unit_s'], 3)
                self.assertEqual(result['summary']['delivered_service_unit_s'], 3 - lost_service)
                self.assertEqual(result['summary']['service_deficit_time_s'], lost_service)
                self.assertEqual(result['trace'][-1]['domains']['it_service']['unserved'], 0)
                limited = next(row['domains'] for row in result['trace'] if row['time_s'] == 0.5)
                self.assertEqual(limited['power']['actual_powers_W']['compute'], requested_power)
                self.assertEqual(limited['power']['actual_powers_W']['network'], 100000)
                self.assertEqual(limited['power']['actual_powers_W']['storage'], 100000)

    def test_capacity_events_require_finite_bounded_values_source_and_unambiguous_time(self):
        for invalid in (-0.1, 2.1, float('nan'), float('inf'), True):
            with self.subTest(capacity=invalid), self.assertRaises(ValueError):
                simulate_scenario(load_scenario(SCENARIO), duration_s=2,
                                  boundary_events=[event(0.25, 'network_service_capacity', invalid)])
        no_source = event(0.25, 'storage_service_capacity', 0.5)
        no_source['source_note'] = ''
        cases = [[no_source],
                 [event(-0.01, 'compute_service_capacity', 0.5)],
                 [event(3, 'compute_service_capacity', 0.5)],
                 [event(0.25, 'compute_service_capacity', 0.5), event(0.25, 'compute_service_capacity', 1)],
                 [event(0.25, 'compute_nominal_power', 1000000)]]
        for events in cases:
            with self.subTest(events=events), self.assertRaises(ValueError):
                simulate_scenario(load_scenario(SCENARIO), duration_s=2, boundary_events=events)

    def test_CLI_saves_the_same_timed_service_account_and_source_records(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            inputs_path = temporary / 'inputs.json'
            events = [event(0.25, 'compute_service_capacity', 0.5),
                      event(1.25, 'compute_service_capacity', 1)]
            inputs_path.write_text(json.dumps({'schema': 'aegisdc-engineering-inputs-v1',
                                               'work_requests': [], 'boundary_events': events}), encoding='utf-8')
            output = temporary / 'new-output'
            environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
            process = subprocess.run([sys.executable, '-m', 'aegis_dc', 'simulate',
                                      '--duration', '2', '--step', '1', '--inputs', str(inputs_path),
                                      '--output', str(output)], cwd=ROOT, env=environment,
                                     check=True, capture_output=True, text=True, encoding='utf-8')
            printed = json.loads(process.stdout)
            saved = json.loads((output / 'run.json').read_text(encoding='utf-8'))
            self.assertEqual(printed, saved)
            self.assertEqual(saved['summary']['demand_service_unit_s'], 2)
            self.assertEqual(saved['summary']['delivered_service_unit_s'], 1.5)
            self.assertEqual(saved['summary']['service_deficit_time_s'], 0.5)
            self.assertEqual(saved['inputs']['boundary_events'], events)
            self.assertEqual(saved['state_visibility'], 'PRIVATE_PLANT_EVALUATOR_ONLY')
            trace = [json.loads(line) for line in (output / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertTrue(any(row['time_s'] == 0.25 for row in trace))
            self.assertTrue(any(row['time_s'] == 1.25 for row in trace))


if __name__ == '__main__':
    unittest.main()
