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


    def test_scalar_legal_pressure_and_charge_can_have_no_fixed_volume_phase(self):
        from aegis_dc.refrigerant_initialization import prepare_refrigerant_initialization

        # At the upper table row, 500 kg would require v=0.01329 m³/kg,
        # which exceeds v_v=0.0052814 m³/kg. Both individual inputs are legal.
        scenario = load_scenario(BASE)
        before = deepcopy(scenario)
        with self.assertRaisesRegex(ValueError, 'do not form an interior two-phase state'):
            prepare_refrigerant_initialization(scenario, mass_kg=500, pressure_Pa=3_000_000)
        self.assertEqual(scenario, before)

    def test_scalar_valid_energy_can_be_incompatible_with_the_entire_property_table(self):
        from aegis_dc.refrigerant_initialization import assess_refrigerant_initialization
        from aegis_dc.scenario import validate_scenario

        scenario = load_scenario(BASE)
        parameters(scenario)['coolant_initial_energy']['value'] = 1_000_000
        self.assertIs(validate_scenario(scenario), scenario)
        # U/M=500 J/kg, below the frozen minimum liquid energy of
        # 165369.28 J/kg and thus below every admitted equilibrium mixture.
        with self.assertRaisesRegex(ValueError, 'exactly one domain-valid root; found 0'):
            assess_refrigerant_initialization(scenario)

    def test_joint_phase_review_does_not_change_geometry_to_fit_a_state(self):
        from aegis_dc.refrigerant_initialization import assess_refrigerant_initialization

        scenario = load_scenario(BASE)
        parameters(scenario)['coolant_control_volume']['value'] = 7
        with self.assertRaisesRegex(ValueError, 'must keep the fixed V6 control volume'):
            assess_refrigerant_initialization(scenario)
