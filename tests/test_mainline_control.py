"""Local-control measurement and lifecycle behavior at declared public seams."""
from copy import deepcopy
import json
import os
import subprocess
import sys
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


def control_parameters(**changes):
    scenario = load_scenario(CONTROL)
    records = {r['id']:r for r in scenario['parameters']}
    if not set(changes) <= set(records):
        raise ValueError('Unknown control engineering input')
    for name, value in changes.items():
        records[name].update(value=value, basis='synthetic_assumption',
            source_note='Ticket 09 controlled engineering override; not an observed field parameter.')
    return scenario


def event(time_s, parameter_id, value):
    return {'time_s':time_s, 'parameter_id':parameter_id, 'value':value,
            'source_note':'Ticket 09 imposed control engineering input; not a registered research trial.'}


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


    def test_profile_requires_implemented_name_typed_offsets_and_binary_static_states(self):
        for bad_profile in (None,False,'unknown',[],{}):
            bad=control_parameters();bad['runtime']['local_control_profile']=bad_profile
            with self.subTest(profile=bad_profile),self.assertRaises(ValueError):
                validate_scenario(bad)
        for flag in ('local_temperature_sensor_valid','local_internal_flow_sensor_valid','supervisory_link_available'):
            for value in (0.5,True):
                with self.subTest(flag=flag,value=value),self.assertRaises(ValueError):
                    validate_scenario(control_parameters(**{flag:value}))
        for name in ('local_temperature_bias','local_internal_flow_bias'):
            for field,value in [('unit','incorrect'),('value',float('nan'))]:
                bad=control_parameters();next(r for r in bad['parameters'] if r['id']==name)[field]=value
                with self.subTest(parameter=name,field=field),self.assertRaises(ValueError):
                    validate_scenario(bad)
        missing=control_parameters()
        missing['parameters']=[r for r in missing['parameters'] if r['id']!='local_temperature_bias']
        for e in missing['entities']:
            if 'local_temperature_bias' in e['parameter_refs']:e['parameter_refs'].remove('local_temperature_bias')
        with self.assertRaisesRegex(ValueError,'Local control profile requires'):
            validate_scenario(missing)


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


    def test_invalid_channel_and_recovery_wait_for_fresh_local_samples(self):
        from aegis_dc.plant import simulate_scenario
        result = simulate_scenario(control_parameters(), duration_s=3, boundary_events=[
            event(0.25,'local_temperature_sensor_valid',0),
            event(1.25,'local_temperature_sensor_valid',1)])
        at = {r['time_s']:r['domains']['control_monitoring'] for r in result['trace']}
        self.assertEqual(at[0.25]['mode'], 'normal')
        self.assertEqual(at[1]['mode'], 'sensor_invalid_fail_safe')
        self.assertEqual(at[1.25]['mode'], 'sensor_invalid_fail_safe')
        self.assertEqual(at[1.25]['local_measurement']['observed_at_s'], 1)
        self.assertEqual(at[2]['mode'], 'normal')
        self.assertFalse(at[2]['protection_latched'])
        self.assertEqual(result['summary']['demand_service_unit_s'],3)
        self.assertEqual(result['summary']['delivered_service_unit_s'],2)
        self.assertEqual(result['summary']['service_deficit_time_s'],1)


    def test_flow_bias_can_mask_low_real_flow_without_creating_water_or_heat_transfer(self):
        from aegis_dc.plant import simulate_scenario
        closing = [event(0.25,'internal_valve_opening',0)]
        honest = simulate_scenario(control_parameters(), duration_s=2, boundary_events=closing)
        biased = simulate_scenario(control_parameters(), duration_s=2,
            boundary_events=closing+[event(0.25,'local_internal_flow_bias',0.12)])
        at = next(r['domains'] for r in biased['trace'] if r['time_s']==1)
        self.assertEqual(at['facility_cooling']['internal_pump']['volume_flow_m3_s'],0)
        self.assertEqual(at['facility_cooling']['condenser_heat_W'],0)
        self.assertEqual(at['control_monitoring']['local_measurement']['internal_volume_flow_m3_s'],0.12)
        self.assertEqual(at['control_monitoring']['mode'],'normal')
        self.assertEqual(at['power']['actual_powers_W']['compute'],2000000)
        self.assertEqual(honest['summary']['service_deficit_time_s'],1)
        self.assertEqual(biased['summary']['service_deficit_time_s'],0)
        self.assertEqual(biased['summary']['demand_service_unit_s'],2)


    def test_negative_temperature_offset_changes_local_protection_without_cooling_the_true_state(self):
        from aegis_dc.plant import simulate_scenario
        settings = {'protection_temperature':304,'protection_reset_temperature':303.5}
        honest = simulate_scenario(control_parameters(**settings),duration_s=1)
        biased = simulate_scenario(control_parameters(**settings,local_temperature_bias=-5),duration_s=1)
        initial = biased['trace'][0]['domains']
        self.assertEqual(honest['trace'][0]['domains']['control_monitoring']['mode'],'protected')
        self.assertEqual(initial['control_monitoring']['mode'],'normal')
        self.assertAlmostEqual(initial['equipment_environment']['refrigerant']['temperature_K'],304.477510064146,delta=1e-9)
        self.assertAlmostEqual(initial['control_monitoring']['local_measurement']['temperature_K'],299.477510064146,delta=1e-9)
        self.assertEqual(honest['summary']['service_deficit_time_s'],1)
        self.assertEqual(biased['summary']['service_deficit_time_s'],0)


    def test_supervisory_loss_keeps_local_trip_and_link_recovery_does_not_clear_it(self):
        from aegis_dc.plant import simulate_scenario
        result=simulate_scenario(control_parameters(),duration_s=4,boundary_events=[
            event(0.25,'supervisory_link_available',0),event(0.25,'local_temperature_bias',40),
            event(1.25,'supervisory_link_available',1),event(2.25,'local_temperature_bias',0)])
        at={r['time_s']:r['domains']['control_monitoring'] for r in result['trace']}
        self.assertEqual(at[1]['supervisory_mode'],'autonomous')
        self.assertEqual(at[1]['mode'],'protected')
        self.assertEqual(at[2]['supervisory_mode'],'connected')
        self.assertTrue(at[2]['protection_latched'])
        self.assertEqual(at[3]['mode'],'normal')
        self.assertEqual(result['summary']['service_deficit_time_s'],2)
        self.assertEqual(result['summary']['demand_service_unit_s'],4)
        self.assertEqual(result['work_records'],[])
        self.assertEqual(result['state_visibility'],'PRIVATE_PLANT_EVALUATOR_ONLY')


    def test_controller_power_cycle_preserves_a_trip_until_actual_fresh_reset_gates(self):
        from aegis_dc.plant import simulate_scenario
        params=dict(protection_temperature=304,protection_reset_temperature=290,
            initial_solid_temperature=300,ups_energy=0,diesel_initial_fuel_energy=0)
        inputs=[event(0.25,'grid_capacity',0),event(1.25,'grid_capacity',10000000)]
        result=simulate_scenario(control_parameters(**params),duration_s=2,boundary_events=inputs)
        dark=next(r['domains']['control_monitoring'] for r in result['trace'] if r['time_s']==1)
        self.assertEqual(dark['mode'],'unpowered_fail_safe')
        self.assertTrue(dark['protection_latched'])
        self.assertIsNone(dark['local_measurement']['temperature_K'])
        final=result['trace'][-1]['domains']['control_monitoring']
        self.assertEqual(final['mode'],'protected')
        self.assertTrue(final['protection_latched'])
        self.assertFalse(final['compute_permitted'])
        params['protection_reset_temperature']=303.5
        reset=simulate_scenario(control_parameters(**params),duration_s=2,boundary_events=inputs)
        self.assertFalse(reset['trace'][-1]['domains']['control_monitoring']['protection_latched'])
        self.assertEqual(reset['trace'][-1]['domains']['power']['actual_powers_W']['compute'],2000000)


    def test_nonphysical_negative_flow_report_is_invalid_not_clipped_to_an_acceptable_value(self):
        from aegis_dc.plant import simulate_scenario
        result=simulate_scenario(control_parameters(local_internal_flow_bias=-0.2),duration_s=1)
        first=result['trace'][0]['domains']
        control=first['control_monitoring']
        self.assertEqual(control['mode'],'sensor_invalid_fail_safe')
        self.assertFalse(control['local_measurement']['flow_valid'])
        self.assertAlmostEqual(control['local_measurement']['internal_volume_flow_m3_s'],-0.08,delta=1e-12)
        self.assertAlmostEqual(first['facility_cooling']['internal_pump']['volume_flow_m3_s'],0.12,delta=1e-12)
        self.assertEqual(first['power']['actual_powers_W']['compute'],0)


    def test_control_events_require_profile_finite_bounds_and_binary_availability(self):
        from aegis_dc.plant import simulate_scenario
        for flag in ('local_temperature_sensor_valid','local_internal_flow_sensor_valid','supervisory_link_available'):
            for value in (0.5,True):
                with self.subTest(flag=flag,value=value),self.assertRaises(ValueError):
                    simulate_scenario(control_parameters(),duration_s=2,boundary_events=[event(0.25,flag,value)])
        for value in (-51,float('nan'),float('inf')):
            with self.subTest(offset=value),self.assertRaises(ValueError):
                simulate_scenario(control_parameters(),duration_s=2,boundary_events=[event(0.25,'local_temperature_bias',value)])
        legacy=control_parameters();legacy['runtime'].pop('local_control_profile')
        with self.assertRaisesRegex(ValueError,'explicit control profile'):
            simulate_scenario(legacy,duration_s=2,boundary_events=[event(0.25,'local_temperature_bias',-2)])
        shifted=simulate_scenario(control_parameters(),duration_s=2,boundary_events=[event(0.25,'local_temperature_bias',-2)])
        at=next(r['domains'] for r in shifted['trace'] if r['time_s']==1)
        self.assertAlmostEqual(at['control_monitoring']['local_measurement']['temperature_K'],302.477510064146,delta=1e-9)


    def test_zero_error_profile_preserves_the_accepted_environment_physical_trajectory(self):
        from aegis_dc.plant import simulate_scenario
        legacy=simulate_scenario(load_scenario(ENVIRONMENT),duration_s=3)
        profiled=simulate_scenario(control_parameters(),duration_s=3)
        self.assertEqual(legacy['summary'],profiled['summary'])
        for before,after in zip(legacy['trace'],profiled['trace']):
            for domain in set(before['domains'])-{'control_monitoring'}:
                self.assertEqual(before['domains'][domain],after['domains'][domain])
        self.assertEqual(legacy['balances'],profiled['balances'])
        self.assertEqual(legacy['trace'][0]['domains']['control_monitoring']['local_measurement']['visibility'],'LOCAL_PLANT_ONLY')


    def test_explicit_CLI_saves_the_same_control_inputs_account_and_private_records(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);inputs=base/'inputs.json';output=base/'new-control-output'
            events=[event(0.25,'local_internal_flow_sensor_valid',0),event(1.25,'local_internal_flow_sensor_valid',1)]
            inputs.write_text(json.dumps({'schema':'aegisdc-engineering-inputs-v1','work_requests':[],
                'boundary_events':events}),encoding='utf-8')
            process=subprocess.run([sys.executable,'-B','-m','aegis_dc','simulate','--model',str(CONTROL),
                '--duration','3','--inputs',str(inputs),'--output',str(output)],cwd=ROOT,
                env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True,text=True,encoding='utf-8',check=True)
            manifest=json.loads((output/'run.json').read_text(encoding='utf-8'))
            self.assertEqual(json.loads(process.stdout),manifest)
            self.assertEqual(manifest['inputs']['boundary_events'],events)
            self.assertEqual(manifest['summary']['demand_service_unit_s'],3)
            self.assertEqual(manifest['summary']['service_deficit_time_s'],1)
            self.assertEqual(manifest['state_visibility'],'PRIVATE_PLANT_EVALUATOR_ONLY')
            scenario=json.loads((output/'scenario.json').read_text(encoding='utf-8'))
            self.assertEqual(scenario['runtime']['local_control_profile'],'aegisdc-local-control-faults-v1')
            trace=[json.loads(line) for line in (output/'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertTrue(all(r['domains']['control_monitoring']['local_measurement']['visibility']=='LOCAL_PLANT_ONLY' for r in trace))


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


    def test_unrepresentable_report_enters_invalid_channel_mode_without_clipping(self):
        from aegis_dc.local_control import sample_local_control
        previous = {'mode':'normal', 'protection_latched':False, 'compute_permitted':True,
                    'pump_speed_command':1, 'local_measurement':None}
        settings = {'controller_power':100, 'protection_temperature':320,
                    'protection_reset_temperature':310, 'minimum_internal_volume_flow':0.01,
                    'cooling_setpoint':305, 'control_hysteresis':5, 'pump_min_speed':0.5}
        measured = {'observed_at_s':0, 'temperature_K':10**1000, 'internal_volume_flow_m3_s':0.02,
                    'temperature_valid':True, 'flow_valid':True, 'supervisory_connected':True}
        state = sample_local_control(previous, settings, measured, controller_power_W=100)
        self.assertEqual(state['mode'], 'sensor_invalid_fail_safe')
        self.assertIsNone(state['local_measurement']['temperature_K'])
        self.assertFalse(state['compute_permitted'])


    def test_literal_hysteresis_sequence_holds_commands_and_latch_between_thresholds(self):
        from aegis_dc.local_control import sample_local_control
        state={'mode':'normal','protection_latched':False,'compute_permitted':True,
               'pump_speed_command':1,'local_measurement':None}
        settings={'controller_power':100,'protection_temperature':320,'protection_reset_temperature':310,
            'minimum_internal_volume_flow':0.01,'cooling_setpoint':305,'control_hysteresis':5,'pump_min_speed':0.5}
        # Independent state-machine hand sequence, including high/low equality.
        sequence=[(300,0.02,0.5,False),(302,0.02,0.5,False),(305,0.02,1,False),
                  (302,0.02,1,False),(320,0.02,1,True),(315,0.02,1,True),
                  (310,0.01,1,False),(304,0.009,1,True),(315,0.02,1,True),(310,0.01,1,False)]
        for time_s,(temperature,flow,command,latched) in enumerate(sequence):
            measured={'observed_at_s':time_s,'temperature_K':temperature,'internal_volume_flow_m3_s':flow,
                'temperature_valid':True,'flow_valid':True,'supervisory_connected':True}
            state=sample_local_control(state,settings,measured,controller_power_W=100)
            with self.subTest(time_s=time_s):
                self.assertEqual(state['pump_speed_command'],command)
                self.assertEqual(state['protection_latched'],latched)
                self.assertEqual(state['compute_permitted'],not latched)


    def test_invalid_report_values_stay_invalid_and_the_state_is_json_serializable(self):
        from aegis_dc.local_control import sample_local_control
        state={'mode':'normal','protection_latched':False,'compute_permitted':True,
            'pump_speed_command':1,'local_measurement':None}
        settings={'controller_power':100,'protection_temperature':320,'protection_reset_temperature':310,
            'minimum_internal_volume_flow':0.01,'cooling_setpoint':305,'control_hysteresis':5,'pump_min_speed':0.5}
        for temperature,flow in [(-1,0.02),(304,-0.01),(float('nan'),0.02),
                                 (304,float('inf')),(True,0.02),(304,None)]:
            measurement={'observed_at_s':0,'temperature_K':temperature,'internal_volume_flow_m3_s':flow,
                'temperature_valid':True,'flow_valid':True,'supervisory_connected':True}
            with self.subTest(temperature=temperature,flow=flow):
                result=sample_local_control(state,settings,measurement,controller_power_W=100)
                self.assertEqual(result['mode'],'sensor_invalid_fail_safe')
                self.assertFalse(result['local_measurement']['valid'])
                json.dumps(result,allow_nan=False)


if __name__ == '__main__':
    unittest.main()
