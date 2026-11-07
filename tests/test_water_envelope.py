"""Independent mass and energy examples for the public V6 water envelope."""
from pathlib import Path
import unittest

from aegis_dc.scenario import load_scenario, validate_scenario

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'configs/full-facility-mainline-reserve-v6.json'


def case(**changes):
    scenario = load_scenario(BASE)
    for row in scenario['parameters']:
        if row['id'] in changes:
            row['value'] = changes[row['id']]
    return validate_scenario(scenario)


def event(time_s, parameter_id, value):
    return dict(time_s=time_s, parameter_id=parameter_id, value=value, source_note='Independent water envelope example.')


class WaterEnvelopeTests(unittest.TestCase):
    def test_late_leak_cannot_consume_more_than_the_available_hot_inventory(self):
        from aegis_dc.water_envelope import assess_water_envelope

        scenario = case(internal_hot_mass=9001)
        # One second at one half kg/s removes exactly one half kg. The
        # corresponding loss at 1.5 kg/s leaves 8999.5, below the 9000 guard.
        result = assess_water_envelope(scenario, horizon_s=2, events=[event(1, 'internal_hot_leak_mass_flow', .5)])
        self.assertEqual(result['hot_inventory']['declared_loss_kg'], .5)
        self.assertEqual(result['hot_inventory']['terminal_hot_mass_kg'], 9000.5)
        self.assertEqual(result['hot_inventory']['margin_kg'], .5)
        self.assertEqual(result['status'], 'STATIC_WATER_ENVELOPE_ONLY')
        with self.assertRaisesRegex(ValueError, 'hot-water inventory.*below'):
            assess_water_envelope(scenario, horizon_s=2, events=[event(1, 'internal_hot_leak_mass_flow', 1.5)])
