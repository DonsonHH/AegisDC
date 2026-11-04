"""Local-control measurement and lifecycle behavior at declared public seams."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from aegis_dc.scenario import load_scenario, validate_scenario

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = ROOT / 'configs/full-facility-mainline-environment-v4.json'
CONTROL = ROOT / 'configs/full-facility-mainline-control-v5.json'


def offset_parameter(name, quantity, unit, value, limits):
    return {'id': name, 'quantity': quantity, 'unit': unit, 'value': value,
            'valid_range': limits, 'basis': 'synthetic_assumption', 'source_refs': ['Rrun'],
            'source_note': 'Ticket 09 bounded synthetic signed measurement offset; not physical flow/temperature.'}


class ControlScenarioTests(unittest.TestCase):
    def test_signed_measurement_offsets_load_without_relaxing_physical_domains(self):
        scenario = load_scenario(ENVIRONMENT)
        scenario['parameters'] += [
            offset_parameter('local_temperature_bias', 'temperature_offset', 'K', -2, [-50,50]),
            offset_parameter('local_internal_flow_bias', 'volume_flow_offset', 'm3/s', -0.1, [-0.2,0.2])]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'signed-offset.json'
            path.write_text(json.dumps(scenario), encoding='utf-8')
            loaded = load_scenario(path)
        self.assertEqual({r['id']:r['value'] for r in loaded['parameters']}['local_temperature_bias'], -2)
        for parameter in ('room_temperature', 'internal_volume_flow'):
            invalid = deepcopy(scenario)
            record = next(r for r in invalid['parameters'] if r['id']==parameter)
            record.update(value=-1, valid_range=[-2,1])
            with self.subTest(physical_parameter=parameter), self.assertRaises(ValueError):
                validate_scenario(invalid)


class ControlFacilityTests(unittest.TestCase):
    def test_high_local_temperature_bias_changes_protection_but_not_true_temperature(self):
        from aegis_dc.plant import simulate_scenario
        scenario = load_scenario(CONTROL)
        next(r for r in scenario['parameters'] if r['id']=='local_temperature_bias')['value'] = 40
        result = simulate_scenario(scenario, duration_s=2)
        first = result['trace'][0]['domains']
        self.assertEqual(len(first), 8)
        self.assertEqual(first['control_monitoring']['mode'], 'protected')
        self.assertEqual(first['power']['actual_powers_W']['compute'], 0)
        self.assertAlmostEqual(first['equipment_environment']['refrigerant']['temperature_K'], 304.477510064146, delta=1e-9)
        self.assertAlmostEqual(first['control_monitoring']['local_measurement']['temperature_K'], 344.477510064146, delta=1e-9)
        self.assertEqual(result['summary']['demand_service_unit_s'], 2)
        self.assertEqual(result['summary']['service_deficit_time_s'], 2)
        self.assertEqual(result['state_visibility'], 'PRIVATE_PLANT_EVALUATOR_ONLY')


class LocalControllerTests(unittest.TestCase):
    def test_invalid_local_channel_latches_fail_safe_without_reading_true_state(self):
        from aegis_dc.local_control import sample_local_control
        previous = {'mode':'normal', 'protection_latched':False, 'compute_permitted':True,
                    'pump_speed_command':0.5, 'local_measurement':None}
        settings = {'controller_power':100, 'protection_temperature':320,
                    'protection_reset_temperature':310, 'minimum_internal_volume_flow':0.01,
                    'cooling_setpoint':305, 'control_hysteresis':5, 'pump_min_speed':0.5}
        measured = {'observed_at_s':1, 'temperature_K':304, 'internal_volume_flow_m3_s':0.02,
                    'temperature_valid':False, 'flow_valid':True, 'supervisory_connected':False}
        state = sample_local_control(previous, settings, measured, controller_power_W=100)
        self.assertEqual(state['mode'], 'sensor_invalid_fail_safe')
        self.assertTrue(state['protection_latched'])
        self.assertFalse(state['compute_permitted'])
        self.assertEqual(state['pump_speed_command'], 1)
        self.assertEqual(state['supervisory_mode'], 'autonomous')
        self.assertEqual(state['local_measurement']['visibility'], 'LOCAL_PLANT_ONLY')
        self.assertFalse(previous['protection_latched'])


if __name__ == '__main__':
    unittest.main()
