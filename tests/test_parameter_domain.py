"""Named joint cases keep geometry and public assumptions distinct."""
from pathlib import Path
import unittest

from aegis_dc.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'configs/full-facility-mainline-reserve-v6.json'


class ParameterDomainTests(unittest.TestCase):
    def test_wet_access_case_keeps_geometry_and_matches_work_timing(self):
        from aegis_dc.parameter_domain import prepare_domain_case

        prepared = prepare_domain_case('wet-access-slow-work')
        original = load_scenario(BASE)
        scenario = prepared['scenario']
        p = {row['id']:row['value'] for row in scenario['parameters']}
        nominal = {row['id']:row['value'] for row in original['parameters']}
        self.assertEqual(scenario['graphs'], original['graphs'])
        self.assertEqual(scenario['site_gaps'], original['site_gaps'])
        self.assertEqual(p['coolant_control_volume'], nominal['coolant_control_volume'])
        self.assertEqual(prepared['duration_s'], 4.5)
        self.assertEqual(p['initial_floor_water_mass'], 9.75)
        self.assertAlmostEqual(prepared['initialization']['water']['hot_inventory']['declared_loss_kg'], .9, delta=1e-12)
        profile = prepared['public_static']['workforce_profile']
        self.assertEqual(sorted(profile['walk_times_s'].values()), [75,75,75,75,150])
        self.assertEqual(profile['work_times_s']['inspect_it_service'], 45)
        self.assertEqual(profile['shifts']['worker_it'], [0,600])
        measured = prepared['public_static']['fixed_sensor_profile']['measurements']
        self.assertEqual({row['id'] for row in measured if row['enabled']}, {'lake-flow','local-temperature-report'})
        self.assertNotIn('scenario',prepared['public_static'])
        self.assertNotIn('boundary_events',prepared['public_static'])
        self.assertEqual(prepared['status'], 'ADMITTED_INITIALIZATION_NOT_TRAJECTORY_QUALIFIED')

    def test_common_distribution_cut_limits_both_source_paths_without_lowering_demand(self):
        from aegis_dc.parameter_domain import prepare_domain_case

        result = prepare_domain_case('shared-path-loss')
        available = result['initialization']['power_and_service']['regimes']
        self.assertEqual([row['start_s'] for row in available], [0,1,2.5])
        self.assertEqual([row['grid_path_upper_W'] for row in available], [10_000_000,0,10_000_000])
        self.assertEqual([row['ups_protected_path_upper_W'] for row in available], [100_000,0,100_000])
        self.assertEqual([row['offered_demand'] for row in available], [1,1,1])
        with self.assertRaisesRegex(ValueError, 'Unknown named domain case'):
            prepare_domain_case('unfrozen-cartesian-combination')
