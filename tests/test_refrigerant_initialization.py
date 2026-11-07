"""Physical constraints at the public fixed-geometry V6 initialization seam."""
from copy import deepcopy
from pathlib import Path
import unittest

from aegis_dc.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'configs/full-facility-mainline-reserve-v6.json'


def parameters(scenario):
    return {row['id']: row for row in scenario['parameters']}


class RefrigerantInitializationTests(unittest.TestCase):
    def test_new_charge_at_fixed_geometry_reconstructs_the_declared_two_phase_state(self):
        from aegis_dc.refrigerant_initialization import prepare_refrigerant_initialization

        scenario = load_scenario(BASE)
        before = deepcopy(scenario)
        result = prepare_refrigerant_initialization(scenario, mass_kg=2200, pressure_Pa=841409.554654894)
        prepared = parameters(result['scenario'])
        original = parameters(scenario)
        self.assertEqual(scenario, before)
        self.assertEqual(set(prepared), set(original))
        self.assertEqual({name for name in prepared if prepared[name] != original[name]},
                         {'coolant_inventory', 'coolant_initial_energy'})
        self.assertEqual(prepared['coolant_control_volume'], original['coolant_control_volume'])
        self.assertEqual(result['scenario']['graphs'], scenario['graphs'])
        self.assertEqual(result['scenario']['site_gaps'], scenario['site_gaps'])
        self.assertEqual(prepared['coolant_inventory']['value'], 2200)
        # Independent rational mixture arithmetic on frozen saturation row 320.
        self.assertAlmostEqual(prepared['coolant_initial_energy']['value'], 570733402.7828943, delta=1e-5)
        phase = result['initialization']
        self.assertAlmostEqual(phase['pressure_Pa'], 841409.554654894, delta=1e-5)
        self.assertAlmostEqual(phase['quality'], .09246212248404061, delta=1e-12)
        self.assertAlmostEqual(phase['liquid_mass_kg'] + phase['vapor_mass_kg'], 2200, delta=1e-9)
        self.assertEqual(result['status'], 'INITIALIZATION_ONLY')
        self.assertEqual(result['field_calibration'], 'PENDING')
